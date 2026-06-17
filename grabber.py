import asyncio
import aiohttp
from telethon import errors
from telethon.tl.functions.channels import (CreateChannelRequest, UpdateUsernameRequest)
import fragment
from settings import Settings


async def _create_channel(client, settings: Settings, username: str):
    """Создаёт один канал под конкретный тег. Возвращает объект канала."""
    title = f"{settings.get('channel_title')} {username}".strip()
    interval = settings.get("check_interval")
    while True:
        try:
            result = await client(CreateChannelRequest(
                title=title,
                about=settings.get("channel_about"),
                megagroup=False,
            ))
            channel = result.chats[0]
            print(f"Канал создан для @{username}: «{title}» id={channel.id}")
            return channel
        except errors.FloodWaitError as e:
            wait = max(interval, e.seconds)
            print(f"  [create] флуд-вейт {e.seconds}s, жду {wait}s")
            await asyncio.sleep(wait)


async def _is_free_on_telegram(client, username: str) -> bool:
    """True, если юзернейм реально свободен в Telegram."""
    try:
        await client.get_entity(username)
        return False  
    except errors.UsernameNotOccupiedError:
        return True
    except ValueError:
        return True  
    except errors.FloodWaitError:
        raise
    except Exception:
        return False


async def _claim_burst(client, settings: Settings, channel, username: str) -> bool:
    """Ускоренный захват: вешает ник на уже созданный канал в темпе
    claim_interval, пока не получится или ник не перехватят/окажется
    недопустимым. True — успех."""
    claim_interval = settings.get("claim_interval")
    while True:
        try:
            await client(UpdateUsernameRequest(channel, username))
            print(f"  ✅ захвачен @{username} (канал id={channel.id})")
            return True
        except errors.FloodWaitError as e:
            wait = max(claim_interval, e.seconds)
            print(f"  [claim] флуд-вейт {e.seconds}s, жду {wait}s")
            await asyncio.sleep(wait)
        except errors.UsernameOccupiedError:
            print(f"  @{username} перехватили — возвращаюсь к мониторингу")
            return False
        except (errors.UsernameInvalidError,
                errors.UsernamePurchaseAvailableError):
            print(f"  @{username} недопустим/на продаже — прекращаю")
            return False
        except errors.RPCError as e:
            print(f"  [claim] {e.code} {e.message} — повтор через {claim_interval}s")
            await asyncio.sleep(claim_interval)


async def run(client, settings: Settings, usernames: list[str]):
    pending = list(dict.fromkeys(usernames))  # уникальные, порядок сохранён

    # Заранее создаём по одному каналу на каждый тег, привязка по id.
    print(f"\nСоздаю каналы под {len(pending)} тег(ов)…")
    channels = {}
    for username in pending:
        channels[username] = await _create_channel(client, settings, username)

    # Мониторинг и захват.
    interval = settings.get("check_interval")
    grabbed: list[str] = []
    cycle = 0

    async with aiohttp.ClientSession() as session:
        while pending:
            cycle += 1
            print(f"\n=== Проход #{cycle}: проверяю {len(pending)} шт. ===")
            still_pending = []

            for username in pending:
                status = await fragment.check_status(session, username)
                print(f"@{username}: {status}")

                if status in (fragment.ON_SALE, fragment.SOLD):
                    print("  → продаётся/продан, прекращаю гоняться")
                    continue

                if status == fragment.UNAVAILABLE:
                    try:
                        free = await _is_free_on_telegram(client, username)
                    except errors.FloodWaitError as e:
                        print(f"  флуд-вейт {e.seconds}s, жду")
                        await asyncio.sleep(max(interval, e.seconds))
                        still_pending.append(username)
                        continue

                    if free:
                        print(f"  @{username} свободен — ускоренный захват")
                        if await _claim_burst(
                            client, settings, channels[username], username
                        ):
                            grabbed.append(username)
                            continue
                    else:
                        print("  → на Fragment unavailable, но в Telegram занят — жду")
                    still_pending.append(username)
                    continue

                # TAKEN или UNKNOWN → мониторим дальше
                still_pending.append(username)

            pending = still_pending
            if not pending:
                break

            print(f"Жду {interval}s до следующего прохода…")
            await asyncio.sleep(interval)

    print("\n--- Итог ---")
    if grabbed:
        print("Захвачено:", ", ".join("@" + u for u in grabbed))
    else:
        print("Ничего захватить не удалось.")
