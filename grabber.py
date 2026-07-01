import asyncio
import aiohttp
from telethon import errors
from telethon.tl.functions.channels import (CreateChannelRequest, UpdateUsernameRequest)
import fragment
from settings import Settings


async def _create_channel(client, settings: Settings, username: str):
    # Create one channel for this username. Returns the channel, or None on failure.
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
            print(f"Channel created for @{username}: '{title}' id={channel.id}")
            return channel
        except errors.FloodWaitError as e:
            wait = max(interval, e.seconds)
            print(f"  [create] flood wait {e.seconds}s, sleeping {wait}s")
            await asyncio.sleep(wait)
        except errors.RPCError as e:
            # Channel limit, missing rights, etc. Bail out instead of looping or
            # crashing the whole run.
            print(f"  [create] could not create channel for @{username}: "
                  f"{e.code} {e.message}")
            return None


async def _is_free_on_telegram(client, username: str) -> bool:
    # True if the username is actually free on Telegram.
    try:
        await client.get_entity(username)
        return False
    except errors.UsernameNotOccupiedError:
        return True
    except errors.FloodWaitError:
        raise
    except ValueError:
        # Telethon raises ValueError when it can't resolve the username, which
        # usually means there's no such account, i.e. it's free.
        return True
    except Exception as e:
        # Don't treat unexpected errors as "free", but don't swallow them either.
        print(f"  [tg] @{username}: check failed - {e}")
        return False


async def _claim_burst(client, settings: Settings, channel, username: str) -> bool:
    # Fast claim: keep assigning the username to the existing channel at
    # claim_interval until it works, gets taken, or turns out invalid.
    # Returns True on success.
    claim_interval = settings.get("claim_interval")
    max_rpc_retries = 5  # guard against looping forever on a persistent error
    rpc_retries = 0
    while True:
        try:
            await client(UpdateUsernameRequest(channel, username))
            print(f"  [ok] claimed @{username} (channel id={channel.id})")
            return True
        except errors.FloodWaitError as e:
            wait = max(claim_interval, e.seconds)
            print(f"  [claim] flood wait {e.seconds}s, sleeping {wait}s")
            await asyncio.sleep(wait)
        except errors.UsernameOccupiedError:
            print(f"  @{username} got taken, back to monitoring")
            return False
        except (errors.UsernameInvalidError,
                errors.UsernamePurchaseAvailableError):
            print(f"  @{username} invalid/for sale, giving up")
            return False
        except errors.RPCError as e:
            rpc_retries += 1
            if rpc_retries > max_rpc_retries:
                print(f"  [claim] @{username}: {e.code} {e.message} - "
                      f"{max_rpc_retries} failed attempts, giving up")
                return False
            print(f"  [claim] {e.code} {e.message} - retry "
                  f"{rpc_retries}/{max_rpc_retries} in {claim_interval}s")
            await asyncio.sleep(claim_interval)


async def run(client, settings: Settings, usernames: list[str]):
    pending = list(dict.fromkeys(usernames))  # unique, order preserved

    # Monitor and claim. Channels are created lazily, only once a username is
    # actually free, so we don't waste the channel creation quota.
    interval = settings.get("check_interval")
    channels: dict[str, object] = {}  # username -> channel, on demand
    grabbed: list[str] = []
    cycle = 0

    print(f"\nMonitoring {len(pending)} username(s)...")
    async with aiohttp.ClientSession() as session:
        while pending:
            cycle += 1
            print(f"\n=== Pass #{cycle}: checking {len(pending)} ===")
            still_pending = []

            for username in pending:
                status = await fragment.check_status(session, username)
                print(f"@{username}: {status}")

                if status in (fragment.ON_SALE, fragment.SOLD):
                    print("  -> on sale/sold, dropping it")
                    continue

                if status == fragment.UNAVAILABLE:
                    try:
                        free = await _is_free_on_telegram(client, username)
                    except errors.FloodWaitError as e:
                        print(f"  flood wait {e.seconds}s, sleeping")
                        await asyncio.sleep(max(interval, e.seconds))
                        still_pending.append(username)
                        continue

                    if free:
                        print(f"  @{username} is free, fast claim")
                        channel = channels.get(username)
                        if channel is None:
                            channel = await _create_channel(
                                client, settings, username
                            )
                            if channel is None:
                                # Channel creation failed, retry next pass.
                                still_pending.append(username)
                                continue
                            channels[username] = channel
                        if await _claim_burst(
                            client, settings, channel, username
                        ):
                            grabbed.append(username)
                            continue
                    else:
                        print("  -> unavailable on Fragment but taken on Telegram, waiting")
                    still_pending.append(username)
                    continue

                # TAKEN or UNKNOWN -> keep monitoring
                still_pending.append(username)

            pending = still_pending
            if not pending:
                break

            print(f"Sleeping {interval}s until next pass...")
            await asyncio.sleep(interval)

    print("\n--- Summary ---")
    if grabbed:
        print("Grabbed:", ", ".join("@" + u for u in grabbed))
    else:
        print("Nothing grabbed.")
