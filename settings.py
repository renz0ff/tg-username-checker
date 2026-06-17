import json
import os

SETTINGS_FILE = "settings.json"

DEFAULTS = {
    "api_id": 0,
    "api_hash": "",
    "session_name": "userbot",
    "channel_title": "tag",
    "channel_about": "",
    "check_interval": 60,
    "claim_interval": 5,
    "usernames_file": "usernames.txt",
}

FIELDS = [
    ("api_id", "API ID", int),
    ("api_hash", "API HASH", str),
    ("session_name", "Имя сессии", str),
    ("channel_title", "Префикс названия канала", str),
    ("channel_about", "Описание канала", str),
    ("check_interval", "Темп опроса Fragment, сек", int),
    ("claim_interval", "Темп захвата при освобождении, сек", int),
    ("usernames_file", "Файл юзернеймов", str),
]


class Settings:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls) -> "Settings":
        data = dict(DEFAULTS)
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, encoding="utf-8") as f:
                    data.update(json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                print(f"[settings] не удалось прочитать {SETTINGS_FILE}: {e}")
        return cls(data)

    def save(self) -> None:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self._data[key] = value

    @property
    def is_configured(self) -> bool:
        """True, если заданы API ID и API HASH."""
        return bool(self._data.get("api_id")) and bool(self._data.get("api_hash"))
