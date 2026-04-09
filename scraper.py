#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper.py — netspor.tecostream.xyz M3U8 Bulucu
Yazar: IPTV Scraper Suite
"""

import re
import time
import json
import logging
import urllib.parse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Selenium (opsiyonel — js gerektiren sayfalar için)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scraper")

# ── Hedef site ──────────────────────────────────────────────
BASE_URL   = "https://netspor.tecostream.xyz"
SOURCE_TAG = "netspor.tecostream.xyz"

# ── Kanal kataloğu ──────────────────────────────────────────
@dataclass
class Channel:
    name: str
    slug: str                   # URL son parçası veya sayfa adı
    group: str = "Spor"
    logo: str  = ""
    tvg_id: str = ""
    extra_paths: List[str] = field(default_factory=list)

CHANNELS: List[Channel] = [
    # BeIN Sports
    Channel("BeIN Sports 1 HD",  "bein-sports-1",   "Spor", "https://i.ibb.co/bRqf3s1/bein1.png",   "BeIN Sports 1",   ["/bs1", "/bs1", "/bein-1"]),
    Channel("BeIN Sports 2 HD",  "bein-sports-2",   "Spor", "https://i.ibb.co/bRqf3s1/bein2.png",   "BeIN Sports 2",   ["/kanal/bein-sports-2", "/bein2", "/bein-2"]),
    Channel("BeIN Sports 3 HD",  "bein-sports-3",   "Spor", "https://i.ibb.co/bRqf3s1/bein3.png",   "BeIN Sports 3",   ["/kanal/bein-sports-3", "/bein3"]),
    Channel("BeIN Sports 4 HD",  "bein-sports-4",   "Spor", "https://i.ibb.co/bRqf3s1/bein4.png",   "BeIN Sports 4",   ["/kanal/bein-sports-4", "/bein4"]),
    Channel("BeIN Sports Max 1", "bein-max-1",     "Spor", "https://i.ibb.co/bRqf3s1/beinmax.png",  "BeIN MAX 1",      ["/kanal/bein-max-1",  "/beinmax1"]),
    Channel("BeIN Sports Max 2", "bein-max-2",     "Spor", "https://i.ibb.co/bRqf3s1/beinmax.png",  "BeIN MAX 2",      ["/kanal/bein-max-2",  "/beinmax2"]),
    Channel("BeIN Sports Haber", "bein-haber",    "Spor", "https://i.ibb.co/bRqf3s1/beinhaber.png","BeIN SPORTS HABER",["/kanal/bein-haber"]),
    # S Sport
    Channel("S Sport HD",        "s-sport",       "Spor", "https://i.ibb.co/ZT4f8pB/ssport.png",   "S Sport",         ["/kanal/s-sport", "/ssport"]),
    Channel("S Sport Plus HD",   "s-sport-plus",  "Spor", "https://i.ibb.co/ZT4f8pB/ssportplus.png","S Sport Plus",    ["/kanal/s-sport-plus", "/ssport2", "/ssportplus"]),
    # TRT Spor
    Channel("TRT Spor HD",       "trt-spor",      "Spor", "https://i.ibb.co/JrHnZ2m/trtspor.png",  "TRT Spor",        ["/kanal/trt-spor", "/trtspor"]),
    Channel("TRT Spor Yıldız",   "trt-spor-yildiz","Spor", "https://i.ibb.co/JrHnZ2m/trtyildiz.png","TRT Spor Yildiz", ["/kanal/trt-spor-yildiz"]),
    # Tivibu
    Channel("Tivibu Spor HD",    "tivibu-spor",   "Spor", "https://i.ibb.co/MRZ3VQY/tivibu.png",   "Tivibu Spor",     ["/kanal/tivibu-spor", "/tivibu"]),
    Channel("Tivibu Spor 2 HD",  "tivibu-spor-2", "Spor", "https://i.ibb.co/MRZ3VQY/tivibu2.png",  "Tivibu Spor 2",   ["/kanal/tivibu-spor-2"]),
    # Smart / A Spor / HT Spor
    Channel("Smart Spor HD",     "smart-spor",    "Spor", "https://i.ibb.co/6H6Xqkw/smartspor.png","Smart Spor",      ["/kanal/smart-spor"]),
    Channel("A Spor HD",         "a-spor",        "Spor", "https://i.ibb.co/DY9KXYL/aspor.png",    "A Spor",          ["/kanal/a-spor", "/aspor"]),
    Channel("HT Spor HD",        "ht-spor",       "Spor", "https://i.ibb.co/7ykLvbm/htspor.png",   "HT Spor",         ["/kanal/ht-spor"]),
    # Eurosport / DAZN
    Channel("Eurosport 1 HD",    "eurosport-1",   "Spor", "https://i.ibb.co/CnNj2bz/euro1.png",    "Eurosport 1",     ["/kanal/eurosport-1", "/euro1"]),
    Channel("Eurosport 2 HD",    "eurosport-2",   "Spor", "https://i.ibb.co/CnNj2bz/euro2.png",    "Eurosport 2",     ["/kanal/eurosport-2", "/euro2"]),
    # Kombine
    Channel("CBC Sport HD",      "cbc-sport",     "Spor", "https://i.ibb.co/0VjF87G/cbcsport.png", "CBC Sport",       ["/kanal/cbc-sport"]),
    Channel("GS TV HD",          "gs-tv",         "Spor", "https://i.ibb.co/nfS3VvQ/gstv.png",     "GS TV",           ["/kanal/gs-tv"]),
    Channel("FB TV HD",          "fb-tv",         "Spor", "https://i.ibb.co/6bT5cq2/fbtv.png",     "FB TV",           ["/kanal/fb-tv"]),
    Channel("BJK TV HD",         "bjk-tv",        "Spor", "https://i.ibb.co/Jjj2b8F/bjktv.png",    "BJK TV",          ["/kanal/bjk-tv"]),
    Channel("TV8 HD",            "tv8",           "Genel","https://i.ibb.co/Gp4CLZM/tv8.png",      "TV8",             ["/kanal/tv8"]),
    Channel("TV8.5 HD",          "tv8-5",         "Genel","https://i.ibb.co/Gp4CLZM/tv85.png",     "TV8.5",           ["/kanal/tv8-5"]),
]

# ── Pattern listesi ─────────────────────────────────────────
M3U8_PATTERNS = [
    re.compile(r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?'),
    re.compile(r'src\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'file\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'source\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'hlsUrl\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'streamUrl\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'manifest\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'url\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'videoUrl\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
    re.compile(r'liveUrl\s*[=:]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'),
]

# ── Olası URL şablonları ────────────────────────────────────
def build_candidate_urls(ch: Channel) -> List[str]:
    candidates = [BASE_URL + p for p in ch.extra_paths]
    defaults = [
        f"{BASE_URL}/{ch.slug}",
        f"{BASE_URL}/kanal/{ch.slug}",
        f"{BASE_URL}/stream/{ch.slug}",
        f"{BASE_URL}/watch/{ch.slug}",
        f"{BASE_URL}/live/{ch.slug}",
        f"{BASE_URL}/izle/{ch.slug}",
        f"{BASE_URL}/player/{ch.slug}",
        BASE_URL + "/",          # ana sayfa (tüm kanallar burada olabilir)
    ]
    seen = set()
    result = []
    for u in candidates + defaults:
        if u not in seen:
            seen.add(u); result.append(u)
    return result

# ── HTTP Session ────────────────────────────────────────────
def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    s.headers.update({
        "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer":         BASE_URL,
        "Origin":          BASE_URL,
    })
    return s

# ── Pattern ile link çıkarıcı ───────────────────────────────
def extract_m3u8_from_text(text: str) -> List[str]:
    found = set()
    for pat in M3U8_PATTERNS:
        for m in pat.finditer(text):
            url = m.group(1) if m.lastindex else m.group(0)
            url = url.strip('"\'').rstrip(',')
            if ".m3u8" in url:
                found.add(url)
    return list(found)

# ── Requests ile tara ───────────────────────────────────────
def scrape_with_requests(url: str, session: requests.Session) -> List[str]:
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        links = extract_m3u8_from_text(r.text)

        # iFrame src'lerini de tara
        iframes = re.findall(r']+src=["\']([^"\']+)["\']', r.text, re.I)
        for src in iframes:
            if not src.startswith("http"):
                src = urllib.parse.urljoin(BASE_URL, src)
            try:
                ir = session.get(src, timeout=10)
                links += extract_m3u8_from_text(ir.text)
            except:
                pass
        return list(set(links))
    except Exception as e:
        log.warning(f"requests hata [{url}]: {e}")
        return []

# ── Selenium ile tara ───────────────────────────────────────
def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--mute-audio")
    opts.add_argument("--lang=tr-TR")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    try:
        svc = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=svc, options=opts)
    except:
        return webdriver.Chrome(options=opts)

def scrape_network_logs(driver) -> List[str]:
    found = []
    try:
        logs = driver.get_log("performance")
        for entry in logs:
            msg = json.loads(entry["message"]).get("message", {})
            if msg.get("method") == "Network.requestWillBeSent":
                req_url = msg.get("params", {}).get("request", {}).get("url", "")
                if ".m3u8" in req_url:
                    found.append(req_url)
    except:
        pass
    return found

def scrape_with_selenium(url: str, driver) -> List[str]:
    try:
        driver.get(url)
        # Sayfa + JS yüklensin
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(5)  # stream başlatma için ekstra bekleme

        links = extract_m3u8_from_text(driver.page_source)
        links += scrape_network_logs(driver)

        # iFrame içlerine gir
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for ifr in iframes:
            try:
                driver.switch_to.frame(ifr)
                links += extract_m3u8_from_text(driver.page_source)
                links += scrape_network_logs(driver)
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()

        return list(set(links))
    except Exception as e:
        log.warning(f"selenium hata [{url}]: {e}")
        return []

# ── Ana tarama fonksiyonu ────────────────────────────────────
def scrape_channel(ch: Channel, session: requests.Session,
                  driver=None) -> Optional[str]:
    candidates = build_candidate_urls(ch)
    all_links  = []

    for url in candidates:
        log.info(f"  Tarıyorum: {url}")
        links = scrape_with_requests(url, session)
        if not links and SELENIUM_OK and driver:
            links = scrape_with_selenium(url, driver)
        all_links.extend(links)
        if links:
            break  # ilk başarılı URL'den sonra dur

    if not all_links:
        log.warning(f"  [{ch.name}] link bulunamadı")
        return None

    # Kanal adı kelimelerini içeren linki tercih et
    name_kw = ch.slug.replace("-", "").lower()
    for lnk in all_links:
        if name_kw in lnk.lower():
            return lnk
    return all_links[0]

# ── Tüm kanalları tara ──────────────────────────────────────
def scrape_all(use_selenium: bool = True) -> Dict[str, str]:
    session = make_session()
    driver  = None
    results: Dict[str, str] = {}

    if use_selenium and SELENIUM_OK:
        log.info("Chrome headless başlatılıyor…")
        driver = make_driver()

    try:
        for ch in CHANNELS:
            log.info(f"[{ch.name}] tarıyorum…")
            link = scrape_channel(ch, session, driver)
            if link:
                results[ch.name] = link
                log.info(f"  ✓ {link}")
            else:
                log.warning(f"  ✗ {ch.name} — bulunamadı")
            time.sleep(2)  # rate-limit koruması
    finally:
        if driver:
            driver.quit()
        session.close()

    return results

if __name__ == "__main__":
    found = scrape_all()
    for name, url in found.items():
        print(f"{name}: {url}")
