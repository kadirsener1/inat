#!/usr/bin/env python3
# scraper.py — v3.0 (channels.json bağımlılığı kaldırıldı)
# 8602741.xyz / netspor.tecostream.xyz / inattv1289.xyz

import re
import time
import logging
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# ─── TÜM KANAL LİSTESİ BURADA GÖMÜLÜ — harici dosyaya gerek yok ───────────────
BUILTIN_CHANNELS = [
    # ── 8602741.xyz kanalları (JS kaynak kodu analizi) ──────────────────────────
    # getStreamSource() metoduna göre:
    #   androstreamlivebs1 → receptestt.m3u8  (özel durum!)
    #   facebookliveXXX    → facebookliveXXX.m3u8
    #   androstreamliveXXX → iOS: facebookliveXXX.m3u8 | diğer: androstreamliveXXX.m3u8
    {
        "id": "androstreamlivebs1",
        "name": "BeIN Sports 1 HD",
        "group": "Spor",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Bein_sports_1.png/220px-Bein_sports_1.png",
        "source": "8602741",
        "stream_id": "androstreamlivebs1",
        "special": "receptestt",   # ← özel durum: receptestt.m3u8
    },
    {
        "id": "androstreamlivebs2",
        "name": "BeIN Sports 2 HD",
        "group": "Spor",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Bein_sports_2.png/220px-Bein_sports_2.png",
        "source": "8602741",
        "stream_id": "androstreamlivebs2",
    },
    {
        "id": "androstreamlivebs3",
        "name": "BeIN Sports 3 HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivebs3",
    },
    {
        "id": "androstreamlivebs4",
        "name": "BeIN Sports 4 HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivebs4",
    },
    {
        "id": "androstreamlivebsm1",
        "name": "BeIN Sports Max 1",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivebsm1",
    },
    {
        "id": "androstreamlivebsm2",
        "name": "BeIN Sports Max 2",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivebsm2",
    },
   
    {
        "id": "androstreamlivess1",
        "name": "S Sport HD",
        "group": "Spor",
        "logo": "https://upload.wikimedia.org/wikipedia/tr/4/49/S_Sport_logo.png",
        "source": "8602741",
        "stream_id": "androstreamlivess1",
    },
    {
        "id": "androstreamlivess2",
        "name": "S Sport 2 HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivess2",
    },
    {
        "id": "androstreamlivessplus1",
        "name": "S Sport Plus",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivessplus1",
    },
    {
        "id": "androstreamlivets",
        "name": "Tivibu Spor HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivets",
    },
    {
        "id": "androstreamlivets2",
        "name": "Tivibu Spor 2",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivets2",
    },
    {
        "id": "androstreamlivets3",
        "name": "Tivibu Spor 3",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivets3",
    },

     {
        "id": "androstreamlivets4",
        "name": "Tivibu Spor 4",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivets4",
    },

    
    {
        "id": "androstreamlivesm1",
        "name": "Smart Spor HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivesm1",
    },
{
        "id": "androstreamlivesm2",
        "name": "Smart Spor 2 HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivesm2",
    },
    {
        "id": "androstreamlivees1",
        "name": "Eurosport 1 HD",
        "group": "Spor",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Eurosport_1_logo_2015.svg/220px-Eurosport_1_logo_2015.svg.png",
        "source": "8602741",
        "stream_id": "androstreamlivees1",
    },
    {
        "id": "androstreamlivees2",
        "name": "Eurosport 2 HD",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivees2",
    },

    
    {
        "id": "androstreamlivetrts",
        "name": "TRT Spor HD",
        "group": "Spor",
        "logo": "https://upload.wikimedia.org/wikipedia/tr/thumb/f/f8/TRT_Spor_logo_%282022%29.svg/220px-TRT_Spor_logo_%282022%29.svg.png",
        "source": "8602741",
        "stream_id": "androstreamlivetrts",
    },
    {
        "id": "androstreamlivetrtsy",
        "name": "TRT Spor Yıldız",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivetrtsy",
    },
    
    {
        "id": "androstreamlivegs",
        "name": "GS TV",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivegs",
    },
    {
        "id": "androstreamlivefb",
        "name": "FB TV",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivefb",
    },
    {
        "id": "androstreamlivebjk",
        "name": "BJK TV",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivebjk",
    },
    
    {
        "id": "androstreamlivebsh",
        "name": "BeIN Sports Haber",
        "group": "Haber",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivebeinhaber",
    },
    
    {
        "id": "androstreamlivenba",
        "name": "NBA TV",
        "group": "Spor",
        "logo": "",
        "source": "8602741",
        "stream_id": "androstreamlivenba",
    },
   
]

# ─── CDN Base URL (JS kaynak kodundan alındı) ───────────────────────────────────
CDN_BASE = "https://andro.evrenosoglu53.lat/checklist/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://8602741.xyz/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ─── M3U8 REGEX PATTERNLERİ ────────────────────────────────────────────────────
M3U8_PATTERNS = [
    re.compile(r'https?://[^\s\'"<>,\]]+\.m3u8[^\s\'"<>,\]]*', re.IGNORECASE),
    re.compile(r'["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'source["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'hlsUrl["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'streamUrl["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'manifest["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'videoUrl["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'file["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'src["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'playlist["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.IGNORECASE),
]


def load_channels() -> list:
    """
    Kanal listesini yükle.
    Önce channels.json'a bak (varsa harici override), yoksa dahili listeyi kullan.
    Bu sayede FileNotFoundError tamamen önlenir.
    """
    channels_file = Path("channels.json")
    if channels_file.exists():
        try:
            import json
            data = json.loads(channels_file.read_text(encoding="utf-8"))
            logger.info(f"channels.json okundu: {len(data)} kanal")
            return data
        except Exception as e:
            logger.warning(f"channels.json okunamadı ({e}), dahili liste kullanılıyor")

    logger.info(f"Dahili kanal listesi kullanılıyor: {len(BUILTIN_CHANNELS)} kanal")
    return BUILTIN_CHANNELS


def get_8602741_stream_url(channel: dict, domain: str) -> Optional[str]:
    """
    8602741.xyz JS kaynak kodundaki getStreamSource() metodunu Python'a çevirdik.
    
    Orijinal JS mantığı:
      if id == "androstreamlivebs1" || id == "facebooklivebs1":
          return baseUrl + "receptestt.m3u8"
      if id.startsWith("facebooklive"):
          return baseUrl + id + ".m3u8"
      if id.startsWith("androstreamlive"):
          if isIOS: suffix → facebooklive{suffix}.m3u8
          else:     return baseUrl + id + ".m3u8"
    """
    stream_id = channel.get("stream_id", "")
    special    = channel.get("special", "")

    # Özel durum: androstreamlivebs1 → receptestt.m3u8
    if special == "receptestt" or stream_id in ("androstreamlivebs1", "facebooklivebs1"):
        return CDN_BASE + "receptestt.m3u8"

    # facebooklive prefix
    if stream_id.startswith("facebooklive"):
        return CDN_BASE + stream_id + ".m3u8"

    # androstreamlive prefix
    if stream_id.startswith("androstreamlive"):
        # iOS varyantı (Türkiye'de daha kararlı)
        suffix = stream_id[len("androstreamlive"):]
        fb_id  = "facebooklive" + suffix
        # Önce fb varyantını dene, yoksa andro varyantı
        for candidate in [CDN_BASE + fb_id + ".m3u8", CDN_BASE + stream_id + ".m3u8"]:
            try:
                r = SESSION.head(candidate, timeout=8, allow_redirects=True)
                if r.status_code < 400:
                    logger.info(f"  ✓ {channel['name']}: {candidate}")
                    return candidate
            except Exception:
                continue

    return None


def get_tecostream_stream_url(channel: dict) -> Optional[str]:
    """netspor.tecostream.xyz için m3u8 ara."""
    slug = channel.get("slug", channel.get("id", ""))
    base = "https://netspor.tecostream.xyz"

    url_templates = [
        f"{base}/kanal/{slug}",
        f"{base}/izle/{slug}",
        f"{base}/watch/{slug}",
        f"{base}/stream/{slug}",
        f"{base}/live/{slug}",
        f"{base}/{slug}",
        f"{base}/embed/{slug}",
        f"{base}/player/{slug}",
    ]

    for url in url_templates:
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 200:
                m3u8 = _extract_m3u8(r.text, url)
                if m3u8:
                    return m3u8
        except Exception as e:
            logger.debug(f"  tecostream {url}: {e}")
            continue

    return None


def get_inattv_stream_url(channel: dict) -> Optional[str]:
    """inattv1289.xyz için m3u8 ara."""
    page = channel.get("page", channel.get("id", ""))
    base = "https://inattv1289.xyz"

    url_templates = [
        f"{base}/{page}",
        f"{base}/kanal/{page}",
        f"{base}/izle/{page}",
        f"{base}/watch/{page}",
    ]

    for url in url_templates:
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 200:
                m3u8 = _extract_m3u8(r.text, url)
                if m3u8:
                    return m3u8
        except Exception as e:
            logger.debug(f"  inattv {url}: {e}")
            continue

    return None


def _extract_m3u8(html: str, base_url: str) -> Optional[str]:
    """HTML/JS içinden m3u8 linkini çıkar."""
    for pat in M3U8_PATTERNS:
        matches = pat.findall(html)
        for m in matches:
            url = m if m.startswith("http") else urljoin(base_url, m)
            if ".m3u8" in url and "cdn.jsdelivr.net" not in url:
                return url
    return None


def scrape_channel(channel: dict, state: dict) -> Optional[str]:
    """Tek kanal için m3u8 URL bul."""
    source = channel.get("source", "")

    if source == "8602741":
        domain = state.get("domain_8602741", "8602741.xyz")
        return get_8602741_stream_url(channel, domain)
    elif source == "tecostream":
        return get_tecostream_stream_url(channel)
    elif source == "inattv":
        return get_inattv_stream_url(channel)

    return None


def scrape_all(state: dict) -> dict:
    """
    Tüm kanalları tara, m3u8 URL'lerini döndür.
    
    Returns:
        dict: {channel_id: m3u8_url}
    """
    channels = load_channels()   # ← artık FileNotFoundError atmaz!
    results  = {}

    logger.info(f"Toplam {len(channels)} kanal taranacak...")

    for i, ch in enumerate(channels, 1):
        cid  = ch.get("id", f"ch_{i}")
        name = ch.get("name", cid)
        logger.info(f"[{i}/{len(channels)}] {name} ({ch.get('source','?')})")

        url = scrape_channel(ch, state)
        if url:
            results[cid] = {
                "url":    url,
                "name":   name,
                "group":  ch.get("group", "Genel"),
                "logo":   ch.get("logo", ""),
                "source": ch.get("source", ""),
            }
            logger.info(f"  ✓ Bulundu: {url[:80]}...")
        else:
            logger.warning(f"  ✗ Link bulunamadı: {name}")

        time.sleep(0.5)   # rate-limit

    logger.info(f"Tamamlandı: {len(results)}/{len(channels)} kanal")
    return results
