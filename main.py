import asyncio
from telethon import TelegramClient
from grabber import run as run_grabber
from settings import FIELDS, Settings


def load_usernames(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.lstrip().startswith("#")
            ]
    except FileNotFoundError:
        return []


async def ask(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip()


def _display_value(key: str, value) -> str:
    """Маскирует api_hash при показе."""
    if key == "api_hash" and value:
        s = str(value)
        return s[:4] + "…" + s[-4:] if len(s) > 8 else "***"
    return str(value)


async def settings_menu(settings: Settings) -> None:
    while True:
        print("\n--- НАСТРОЙКИ ---")
        for i, (key, label, _typ) in enumerate(FIELDS, 1):
            print(f"{i}. {label}: {_display_value(key, settings.get(key))}")
        print("0. Назад")

        choice = await ask("Что изменить: ")
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(FIELDS)):
            print("Неизвестный пункт.")
            continue

        key, label, typ = FIELDS[int(choice) - 1]
        raw = await ask(f"Новое значение для «{label}»: ")

        if typ is int:
            if not raw.lstrip("-").isdigit():
                print("Нужно целое число.")
                continue
            val = int(raw)
            if key == "check_interval" and val < 5:
                print("Интервал слишком мал, ставлю 5 сек.")
                val = 5
            if key == "claim_interval" and val < 1:
                print("Интервал слишком мал, ставлю 1 сек.")
                val = 1
            settings.set(key, val)
        else:
            settings.set(key, raw)

        settings.save()
        print("Сохранено.")


async def main() -> None:
    settings = Settings.load()
    client: TelegramClient | None = None
    client_creds = None  

    while True:
        print("\n========== МЕНЮ ==========")
        print("1. Старт")
        print("2. Список юзернеймов")
        print("3. Настройки")
        print("0. Выход")
        choice = await ask("Выбор: ")

        if choice == "1":
            if not settings.is_configured:
                print("Сначала укажи API ID и API HASH в «Настройках» (пункт 3).")
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
                await client.start() 

            me = await client.get_me()
            handle = f"@{me.username}" if me.username else "(без юзернейма)"
            print(f"Авторизован как: {me.first_name} {handle}")

            usernames = load_usernames(settings.get("usernames_file"))
            if not usernames:
                print(f"Файл {settings.get('usernames_file')} пуст или не найден.")
                continue
            await run_grabber(client, settings, usernames)

        elif choice == "2":
            usernames = load_usernames(settings.get("usernames_file"))
            if usernames:
                print(f"\nЮзернеймы ({len(usernames)}):")
                for u in usernames:
                    print(f"  @{u}")
            else:
                print(f"Файл {settings.get('usernames_file')} пуст или не найден.")

        elif choice == "3":
            await settings_menu(settings)

        elif choice == "0":
            break

        else:
            print("Неизвестный пункт меню.")

    if client is not None:
        await client.disconnect()
    print("Пока.")


if __name__ == "__main__":
    asyncio.run(main())
