# tg-username-checker

A Telethon userbot that watches username statuses on
[fragment.com](https://fragment.com) and creates a Telegram channel with the
username as soon as it becomes available.

> Warning: this runs as **your personal account** (userbot), not a bot. Mass
> username sniping can break Telegram's rules and get your account limited or
> banned. Use at your own risk.

## Requirements

- Python 3.12
- `api_id` and `api_hash` — get them at https://my.telegram.org

## Install

```bash
git clone https://github.com/renz0ff/tg-username-checker.git
cd tg-username-checker

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Menu:

```
1. Start          - run monitoring and claiming
2. Username list  - show usernames.txt
3. Settings       - set API ID, API HASH and other options
0. Exit
```

### First run

1. Open **3. Settings** and fill in **API ID** and **API HASH**.
2. Go back and pick **1. Start** — Telethon will ask for your phone number
   and the confirmation code, then create the session file
   `userbot.session`.

Usernames to track go in `usernames.txt`, one per line (no `@`); lines
starting with `#` are ignored.

## License

[MIT](LICENSE)
