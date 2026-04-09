#!/usr/bin/env python3
"""
scraper.py — 8602741.xyz (değişen domain) üzerinden m3u8 link çekici

Nasıl çalışır:
  1) domain_finder'dan aktif domain'i öğren
  2) channels.json'daki her kanal için event.html?id=CHANNEL_ID URL'ini aç
  3) Sayfa HTML + JS kaynak kodundan checklist URL'ini çıkar
  4) checklist CDN'inden .m3u8 dosyasını doğrula (HEAD request)
  5) Selenium kullanarak network trafiğini dinle (JS rendered URL'ler için)
  6) Bulunan linkleri döndür
"""

import re, json, time, logging, requests
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Scraper")

CHANNELS_FILE = Path("channels.json")
STATE_FILE    = Path("state.json")
TIMEOUT       = 15
MAX_WORKERS   = 6
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://8602741.xyz/",
    "Accept": "*/*",
    "Origin": "https://8602741.xyz",
}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "current_domain": "8602741.xyz",
        "current_base_url": "https://8602741.xyz/event.html?id=",
        "checklist_base": "https://andro.evrenosoglu53.lat/checklist/",
    }


def load_channels() -> List[dict]:
    if not CHANNELS_FILE.exists():
        log.error(f"{CHANNELS_FILE} bulunamadı!")
        return []
    return json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))


def build_m3u8_url(checklist_base: str, channel_id: str, is_ios: bool = False) -> str:
    """
    Kaynak kodun getStreamSource() metodunu Python'da taklit eder.
    
    Mantık (JS'den birebir):
      - id == 'androstreamlivebs1' → receptestt.m3u8
      - id.startsWith('facebooklive') → {id}.m3u8
      - id.startsWith('androstreamlive') + iOS → 'facebooklive' + suffix + .m3u8  
      - id.startsWith('androstreamlive') + !iOS → {id}.m3u8
    """
    base = checklist_base.rstrip("/") + "/"
    cid = channel_id.strip()

    if cid == "androstreamlivebs1":
        return base + "receptestt.m3u8"

    if cid.startswith("facebooklive"):
        return base + cid + ".m3u8"

    if cid.startswith("androstreamlive"):
        if is_ios:
            suffix = cid[len("androstreamlive"):]
            fb_id = f"facebooklive{suffix}"
            return base + fb_id + ".m3u8"
        return base + cid + ".m3u8"

    # Bilinmeyen format — direkt dene
    return base + cid + ".m3u8"


def verify_m3u8(url: str, session: requests.Session) -> bool:
    """m3u8 URL'inin gerçekten erişilebilir olduğunu doğrular."""
    try:
        r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            if "mpegurl" in ct or "octet" in ct or ct == "":
                return True
        # HEAD başarısızsa GET ile content kontrol et
        r = session.get(url, timeout=TIMEOUT, stream=True)
        chunk = next(r.iter_content(256), b"")
        return b"#EXTM3U" in chunk or b"#EXT-X-" in chunk
    except:
        return False


def extract_from_page_source(html: str, checklist_base: str) -> Optional[str]:
    """Sayfa HTML'inden checklist base URL'ini günceller (dinamik değişim için)."""
    patterns = [
        r'"(https://[^"]+/checklist/)"',
        r"'(https://[^']+/checklist/)'",
        r"(https://andro\.\S+/checklist/)",
        r"randomBaseUrl\s*=\s*[\"'](https://[^\"']+)[\"']",
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def scrape_channel(ch: dict, state: dict, session: requests.Session) -> Optional[str]:
    """Tek bir kanal için m3u8 URL'ini bulur ve doğrular."""
    channel_id   = ch["id"]
    channel_name = ch["name"]
    base_url     = state["current_base_url"]
    checklist    = state["checklist_base"]
    domain       = state["current_domain"]

    page_url = f"{base_url}{channel_id}"
    log.info(f"[{channel_name}] Sayfa yükleniyor: {page_url}")

    # 1. Sayfa kaynağından checklist base'i güncelle
    try:
        r = session.get(page_url, timeout=TIMEOUT)
        extracted = extract_from_page_source(r.text, checklist)
        if extracted:
            checklist = extracted
            log.debug(f"[{channel_name}] Yeni checklist base: {checklist}")
    except Exception as e:
        log.warning(f"[{channel_name}] Sayfa yüklenemedi: {e}")

    # 2. Farklı ID varyantlarını dene
    variants = _build_id_variants(channel_id)
    for vid in variants:
        url = build_m3u8_url(checklist, vid, is_ios=False)
        if verify_m3u8(url, session):
            log.info(f"[{channel_name}] ✅ Doğrulandı: {url}")
            return url
        time.sleep(0.3)

    log.warning(f"[{channel_name}] ❌ Link bulunamadı (ID: {channel_id})")
    return None


def _build_id_variants(channel_id: str) -> List[str]:
    """Bir kanal ID'si için denenecek tüm varyantları üretir."""
    variants = [channel_id]
    # andro → facebook dönüşümü
    if channel_id.startswith("androstreamlive"):
        suffix = channel_id[len("androstreamlive"):]
        variants.append(f"facebooklive{suffix}")
    # facebook → andro dönüşümü
    if channel_id.startswith("facebooklive"):
        suffix = channel_id[len("facebooklive"):]
        variants.append(f"androstreamlive{suffix}")
    return variants


def scrape_all(state: dict) -> Dict[str, str]:
    """Tüm kanalları paralel olarak tarar. {kanal_adı: m3u8_url} döndürür."""
    channels = load_channels()
    if not channels:
        return {}

    session = requests.Session()
    session.headers.update({
        **HEADERS,
        "Referer": f"https://{state['current_domain']}/",
        "Origin": f"https://{state['current_domain']}",
    })

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(scrape_channel, ch, state, session): ch
            for ch in channels
        }
        for future in as_completed(futures):
            ch = futures[future]
            try:
                url = future.result()
                if url:
                    results[ch["name"]] = url
            except Exception as e:
                log.error(f"[{ch['name']}] Hata: {e}")

    log.info(f"✅ Toplam {len(results)}/{len(channels)} kanal başarılı")
    return results


if __name__ == "__main__":
    state = load_state()
    results = scrape_all(state)
    print(json.dumps(results, indent=2, ensure_ascii=False))
