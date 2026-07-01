import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from grabber import run as run_grabber
from settings import FIELDS, Settings


def load_usernames(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return [
                line.strip().lstrip("@")
                for line in f
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except FileNotFoundError:
        return []


async def ask(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip()


async def ensure_authorized(client: TelegramClient) -> None:
    # Sign in without blocking the event loop on a sync input() call.
    await client.connect()
    if await client.is_user_authorized():
        return

    phone = await ask("Phone (e.g. +1...): ")
    await client.send_code_request(phone)
    code = await ask("Code from Telegram: ")
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        password = await ask("Two-factor password: ")
        await client.sign_in(password=password)


def _display_value(key: str, value) -> str:
    # Hide most of api_hash when printing it.
    if key == "api_hash" and value:
        s = str(value)
        return s[:4] + "..." + s[-4:] if len(s) > 8 else "***"
    return str(value)


async def settings_menu(settings: Settings) -> None:
    while True:
        print("\n--- SETTINGS ---")
        for i, (key, label, _typ) in enumerate(FIELDS, 1):
            print(f"{i}. {label}: {_display_value(key, settings.get(key))}")
        print("0. Back")

        choice = await ask("What to change: ")
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(FIELDS)):
            print("Unknown option.")
            continue

        key, label, typ = FIELDS[int(choice) - 1]
        raw = await ask(f"New value for '{label}': ")

        if typ is int:
            if not raw.lstrip("-").isdigit():
                print("Expected an integer.")
                continue
            val = int(raw)
            if key == "check_interval" and val < 5:
                print("Interval too small, using 5s.")
                val = 5
            if key == "claim_interval" and val < 1:
                print("Interval too small, using 1s.")
                val = 1
            settings.set(key, val)
        else:
            settings.set(key, raw)

        settings.save()
        print("Saved.")


async def main() -> None:
    settings = Settings.load()
    client: TelegramClient | None = None
    client_creds = None

    while True:
        print("\n========== MENU ==========")
        print("1. Start")
        print("2. Username list")
        print("3. Settings")
        print("0. Exit")
        choice = await ask("Choice: ")

        if choice == "1":
            if not settings.is_configured:
                print("Set API ID and API HASH in Settings first (option 3).")
                continue

            creds = (settings.get("api_id"), settings.get("api_hash"))
            if client is None or client_creds != creds:
                if client is not None:
                    await client.disconnect()
                client = TelegramClient(
                    settings.get("session_name"), creds[0], creds[1]
                )
                client_creds = creds

            if not client.is_connected():
                await ensure_authorized(client)

            me = await client.get_me()
            handle = f"@{me.username}" if me.username else "(no username)"
            print(f"Signed in as: {me.first_name} {handle}")

            usernames = load_usernames(settings.get("usernames_file"))
            if not usernames:
                print(f"File {settings.get('usernames_file')} is empty or missing.")
                continue
            await run_grabber(client, settings, usernames)

        elif choice == "2":
            usernames = load_usernames(settings.get("usernames_file"))
            if usernames:
                print(f"\nUsernames ({len(usernames)}):")
                for u in usernames:
                    print(f"  @{u}")
            else:
                print(f"File {settings.get('usernames_file')} is empty or missing.")

        elif choice == "3":
            await settings_menu(settings)

        elif choice == "0":
            break

        else:
            print("Unknown menu option.")

    if client is not None:
        await client.disconnect()
    print("Bye.")


if __name__ == "__main__":
    asyncio.run(main())
