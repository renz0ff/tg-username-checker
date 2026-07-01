import re
import ssl
import aiohttp
import certifi

FRAGMENT_URL = "https://fragment.com/username/{}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

UNAVAILABLE = "unavailable"
TAKEN = "taken"
ON_SALE = "on_sale"
SOLD = "sold"
UNKNOWN = "unknown"

_STATUS_RE = re.compile(
    r'tm-section-header-status[^>]*>\s*([^<]+?)\s*<',
    re.IGNORECASE,
)


def _extract_status_text(html: str) -> str:
    # Pull the status text out of a Fragment page.
    m = _STATUS_RE.search(html)
    if m:
        return m.group(1).strip()
    for phrase in ("Unavailable", "Taken", "For sale", "On auction", "Sold"):
        if re.search(rf">\s*{phrase}\s*<", html, re.IGNORECASE):
            return phrase
    return ""


def _classify(text: str) -> str:
    t = text.lower()
    if not t:
        return UNKNOWN
    if "unavailable" in t:
        return UNAVAILABLE
    if "sold" in t:
        return SOLD
    if "sale" in t or "auction" in t or "available" in t:
        return ON_SALE
    if "taken" in t:
        return TAKEN
    return UNKNOWN


async def check_status(session: aiohttp.ClientSession, username: str) -> str:
    url = FRAGMENT_URL.format(username)
    try:
        async with session.get(
            url, headers=HEADERS, timeout=20, ssl=_SSL_CTX
        ) as resp:
            if resp.status != 200:
                print(f"[fragment] @{username}: HTTP {resp.status}")
                return UNKNOWN
            html = await resp.text()
    except Exception as e:
        print(f"[fragment] @{username}: request failed - {e}")
        return UNKNOWN

    return _classify(_extract_status_text(html))
