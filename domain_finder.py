#!/usr/bin/env python3
# domain_finder.py — v3.0
# 8602741.xyz gibi sayısal domain değişimini 4 yöntemle yakalar

import re
import json
import logging
import requests
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

STATE_FILE   = Path("state.json")
KNOWN_DOMAIN = "8602741.xyz"     # Son bilinen domain
DOMAIN_REGEX = re.compile(r'\b(\d{5,8})\.xyz\b')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ─── STATE ──────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "domain_8602741": KNOWN_DOMAIN,
        "cdn_base":       "https://andro.evrenosoglu53.lat/checklist/",
        "last_check":     None,
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"State kaydedildi: {STATE_FILE}")


# ─── YÖNTEM 1: Eski domain yönlendirme kontrolü ─────────────────────────────────
def check_redirect(current_domain: str) -> Optional[str]:
    """Mevcut domain yeniye redirect ediyor mu?"""
    try:
        url = f"https://{current_domain}/event.html?id=androstreamlivebs1"
        r   = SESSION.get(url, timeout=10, allow_redirects=True)
        final = r.url
        m = DOMAIN_REGEX.search(final)
        if m:
            new_num = m.group(1)
            new_dom = f"{new_num}.xyz"
            if new_dom != current_domain:
                logger.info(f"Redirect yöntemi: {current_domain} → {new_dom}")
                return new_dom
    except Exception as e:
        logger.debug(f"Redirect kontrolü başarısız: {e}")
    return None


# ─── YÖNTEM 2: Wayback Machine CDX API ──────────────────────────────────────────
def check_wayback() -> Optional[str]:
    """Wayback Machine'de en son arşivlenen xxxxxx.xyz domain'ini bul."""
    try:
        api = "https://web.archive.org/cdx/search/cdx"
        params = {
            "url":        "*.xyz/event.html",
            "output":     "json",
            "fl":         "original,timestamp",
            "limit":      "20",
            "from":       "20240101",
            "filter":     "original:.*\\d{5,8}\\.xyz.*",
        }
        r = SESSION.get(api, params=params, timeout=15)
        if r.status_code == 200:
            rows = r.json()
            for row in reversed(rows[1:]):  # başlık satırını atla, en yeni önce
                m = DOMAIN_REGEX.search(row[0])
                if m:
                    found = f"{m.group(1)}.xyz"
                    logger.info(f"Wayback yöntemi: {found} (ts={row[1]})")
                    return found
    except Exception as e:
        logger.debug(f"Wayback kontrolü başarısız: {e}")
    return None


# ─── YÖNTEM 3: DNS Brute-force (±200 aralık) ────────────────────────────────────
def dns_bruteforce(current_domain: str) -> Optional[str]:
    """
    Mevcut domain numarasının ±200 aralığını HTTP HEAD ile tara.
    Önce büyük sayıları dene (domain artış eğilimi var).
    """
    m = DOMAIN_REGEX.search(current_domain)
    if not m:
        return None

    base_num = int(m.group(1))
    logger.info(f"DNS brute-force: {base_num-200} ~ {base_num+200}")

    candidates: List[int] = []
    # Büyükten küçüğe sırala (yeni domain genelde daha büyük)
    for delta in range(1, 201):
        candidates.append(base_num + delta)
    for delta in range(1, 51):
        candidates.append(base_num - delta)

    for num in candidates:
        if num <= 0:
            continue
        domain = f"{num}.xyz"
        try:
            r = SESSION.head(
                f"https://{domain}/event.html?id=androstreamlivebs1",
                timeout=5,
                allow_redirects=True,
            )
            if r.status_code in (200, 302, 301, 403):
                logger.info(f"DNS brute-force buldu: {domain} (HTTP {r.status_code})")
                return domain
        except Exception:
            continue

    return None


# ─── YÖNTEM 4: Google Cache / Arama ─────────────────────────────────────────────
def check_google_cache() -> Optional[str]:
    """
    Google arama sonuçlarından yeni domain yakala.
    (GitHub Actions ortamında çalışmayabilir, opsiyonel)
    """
    try:
        search_url = "https://www.google.com/search?q=site%3A*.xyz+event.html+androstreamlive"
        r = SESSION.get(search_url, timeout=10)
        if r.status_code == 200:
            matches = DOMAIN_REGEX.findall(r.text)
            if matches:
                # En çok geçen numarayı al
                from collections import Counter
                most_common = Counter(matches).most_common(1)[0][0]
                found = f"{most_common}.xyz"
                logger.info(f"Google cache yöntemi: {found}")
                return found
    except Exception as e:
        logger.debug(f"Google cache başarısız: {e}")
    return None


# ─── CDN BASE URL GÜNCELLEME ─────────────────────────────────────────────────────
def verify_cdn_base(state: dict) -> str:
    """
    CDN base URL'ini doğrula. Değiştiyse yeni domain üzerinden bul.
    JS kaynak kodunda: https://andro.evrenosoglu53.lat/checklist/
    """
    current_cdn = state.get("cdn_base", "https://andro.evrenosoglu53.lat/checklist/")
    test_url    = current_cdn + "receptestt.m3u8"

    try:
        r = SESSION.head(test_url, timeout=10)
        if r.status_code < 400:
            logger.info(f"CDN base geçerli: {current_cdn}")
            return current_cdn
    except Exception:
        pass

    # CDN değiştiyse yeni domain'in kaynak kodundan çek
    logger.warning(f"CDN base erişilemez: {current_cdn}, JS'den yeni URL aranıyor...")
    try:
        domain = state.get("domain_8602741", KNOWN_DOMAIN)
        r = SESSION.get(
            f"https://{domain}/event.html?id=androstreamlivebs1",
            timeout=15,
        )
        if r.status_code == 200:
            cdn_pat = re.compile(r'https?://[^\s\'"]+/checklist/')
            m = cdn_pat.search(r.text)
            if m:
                new_cdn = m.group(0)
                logger.info(f"Yeni CDN base: {new_cdn}")
                return new_cdn
    except Exception as e:
        logger.debug(f"CDN bulma hatası: {e}")

    return current_cdn  # Değişiklik bulunamazsa eskiyi kullan


# ─── ANA FONKSİYON ───────────────────────────────────────────────────────────────
def find_current_domain() -> dict:
    """
    State'i yükle, domain'i doğrula/güncelle, kaydet ve döndür.
    
    Returns:
        dict: güncellenmiş state
    """
    state   = load_state()
    current = state.get("domain_8602741", KNOWN_DOMAIN)
    found   = None

    logger.info(f"Mevcut domain: {current}")

    # Mevcut domain hâlâ çalışıyor mu?
    try:
        r = SESSION.head(
            f"https://{current}/event.html?id=androstreamlivebs1",
            timeout=8,
        )
        if r.status_code < 400:
            logger.info(f"✓ Mevcut domain çalışıyor: {current}")
            # CDN'i de kontrol et
            state["cdn_base"] = verify_cdn_base(state)
            save_state(state)
            return state
    except Exception:
        logger.warning(f"✗ Mevcut domain erişilemez: {current}")

    # Domain değişti — 4 yöntemle ara
    logger.info("Domain arama başlıyor (4 yöntem)...")

    # 1. Redirect
    found = check_redirect(current)
    if found:
        logger.info(f"✓ Yöntem 1 (Redirect): {found}")

    # 2. Wayback Machine
    if not found:
        found = check_wayback()
        if found:
            logger.info(f"✓ Yöntem 2 (Wayback): {found}")

    # 3. Google Cache
    if not found:
        found = check_google_cache()
        if found:
            logger.info(f"✓ Yöntem 3 (Google): {found}")

    # 4. DNS Brute-force (en yavaş ama en güvenilir)
    if not found:
        found = dns_bruteforce(current)
        if found:
            logger.info(f"✓ Yöntem 4 (Brute-force): {found}")

    if found:
        state["domain_8602741"] = found
        logger.info(f"🎯 Yeni domain: {found}")
    else:
        logger.error(f"❌ Yeni domain bulunamadı, eski kullanılacak: {current}")

    # CDN base'i de güncelle
    state["cdn_base"] = verify_cdn_base(state)

    from datetime import datetime
    state["last_check"] = datetime.utcnow().isoformat()

    save_state(state)
    return state
