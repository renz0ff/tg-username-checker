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
    ("session_name", "Session name", str),
    ("channel_title", "Channel title prefix", str),
    ("channel_about", "Channel description", str),
    ("check_interval", "Fragment poll interval, sec", int),
    ("claim_interval", "Claim interval on release, sec", int),
    ("usernames_file", "Usernames file", str),
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
                print(f"[settings] could not read {SETTINGS_FILE}: {e}")
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
        # True once API ID and API HASH are set.
        return bool(self._data.get("api_id")) and bool(self._data.get("api_hash"))
