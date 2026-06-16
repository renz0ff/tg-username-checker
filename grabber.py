"""Основной цикл: мониторинг статусов и захват юзернеймов.

Логика для каждого юзернейма:
  - на продаже / продан  → убрать из списка;
  - taken                → продолжать проверять каждый check_interval;
  - unavailable          → проверить, свободен ли он в самом Telegram;
                           если да — создать канал и повесить юзернейм,
                           если нет — оставить в мониторинге.
"""
import asyncio

import aiohttp
from telethon import errors
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    UpdateUsernameRequest,
)

import fragment
from settings import Settings


async def _is_free_on_telegram(client, username: str) -> bool:
    """True, если юзернейм реально свободен в Telegram."""
    try:
        await client.get_entity(username)
        return False  # сущность нашлась → юзернейм занят
    except errors.UsernameNotOccupiedError:
        return True
    except ValueError:
        return True   # Telethon не нашёл сущность
    except errors.FloodWaitError:
        raise
    except Exception:
        return False


async def _claim(client, settings: Settings, username: str) -> bool:
    """Создаёт канал и вешает на него юзернейм. True — успех."""
    interval = settings.get("check_interval")
    try:
        result = await client(CreateChannelRequest(
            title=settings.get("channel_title"),
            about=settings.get("channel_about"),
            megagroup=False,
        ))
        channel = result.chats[0]
    except errors.FloodWaitError as e:
        wait = max(interval, e.seconds)
        print(f"  [claim] флуд-вейт {e.seconds}s при создании канала, жду {wait}s")
        await asyncio.sleep(wait)
        return False

    try:
        await client(UpdateUsernameRequest(channel, username))
        print(f"  \u2705 захвачен @{username} (канал id={channel.id})")
        return True
    except errors.FloodWaitError as e:
        wait = max(interval, e.seconds)
        print(f"  [claim] флуд-вейт {e.seconds}s при установке ника, жду {wait}s")
        await asyncio.sleep(wait)
        return False
    except errors.RPCError as e:
        print(f"  [claim] не удалось занять @{username}: {e.code} {e.message}")
        return False


async def run(client, settings: Settings, usernames: list[str]):
    """Гоняет список, пока не опустеет (всё захвачено/выкинуто)."""
    interval = settings.get("check_interval")
    pending = list(dict.fromkeys(usernames))  # уникальные, порядок сохранён
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
                    print("  → продаётся/продан, убираю из списка")
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
                        if await _claim(client, settings, username):
                            grabbed.append(username)
                            continue
                    else:
                        print("  → на Fragment unavailable, но в Telegram занят — жду")
                    still_pending.append(username)
                    continue

                # TAKEN или UNKNOWN → продолжаем мониторить
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
