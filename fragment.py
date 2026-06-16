"""Проверка статуса юзернейма на fragment.com.

Fragment отдаёт страницу /username/<name> с server-side разметкой,
в которой есть текстовый статус. Парсим его и классифицируем.

ВНИМАНИЕ: класс статус-элемента на Fragment может меняться. Парсер
сначала пробует найти его по характерному классу, а если не вышло —
ищет ключевые слова по всему тексту страницы. Если Fragment поменяет
вёрстку, правится функция _extract_status_text ниже.
"""
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

# SSL-контекст с корневыми сертификатами certifi.
# Решает SSLCertVerificationError на macOS, где системный Python
# не видит корневые сертификаты.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# Возможные статусы
UNAVAILABLE = "unavailable"  # не продаётся на Fragment → кандидат на захват
TAKEN = "taken"              # занят владельцем → продолжаем мониторить
ON_SALE = "on_sale"          # на продаже / аукционе → выкинуть из списка
SOLD = "sold"                # продан → выкинуть из списка
UNKNOWN = "unknown"          # не удалось определить → мониторим дальше

# Статус-элемент в шапке страницы Fragment
_STATUS_RE = re.compile(
    r'tm-section-header-status[^>]*>\s*([^<]+?)\s*<',
    re.IGNORECASE,
)


def _extract_status_text(html: str) -> str:
    """Достаёт текст статуса со страницы Fragment."""
    m = _STATUS_RE.search(html)
    if m:
        return m.group(1).strip()
    # запасной вариант — ищем явные фразы в тексте
    for phrase in ("Unavailable", "Taken", "For sale", "On auction", "Sold"):
        if re.search(rf">\s*{phrase}\s*<", html, re.IGNORECASE):
            return phrase
    return ""


def _classify(text: str) -> str:
    t = text.lower()
    if not t:
        return UNKNOWN
    if "unavailable" in t:       # проверяем раньше "available"
        return UNAVAILABLE
    if "sold" in t:
        return SOLD
    if "sale" in t or "auction" in t or "available" in t:
        return ON_SALE
    if "taken" in t:
        return TAKEN
    return UNKNOWN


async def check_status(session: aiohttp.ClientSession, username: str) -> str:
    """Возвращает один из статусов выше для указанного юзернейма."""
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
        print(f"[fragment] @{username}: ошибка запроса — {e}")
        return UNKNOWN

    return _classify(_extract_status_text(html))
