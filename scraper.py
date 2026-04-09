# -*- coding: utf-8 -*-
"""
scraper.py
inattv1289.xyz sitesinden m3u8 linklerini bulan modül.
Selenium (ChromeDriver headless) + requests ile çalışır.
"""

import re
import time
import json
import logging
import requests
from typing import List, Dict
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─── Sabitler ──────────────────────────────────────────────
BASE_URL = "https://inattv1289.xyz"
SOURCE_TAG = "#SOURCE:inattv1289.xyz"  # M3U dosyasındaki kaynak etiketi

CHANNEL_SLUGS = [
    ("androstreamlivebs1",     "bein-sports-1-izle",  "Sports"),
    ("BeIN Sports 2",     "bein-sports-2-izle",  "Sports"),
    ("BeIN Sports 3",     "bein-sports-3-izle",  "Sports"),
    ("BeIN Sports 4",     "bein-sports-4-izle",  "Sports"),
    ("BeIN Sports 5",     "bein-sports-5-izle",  "Sports"),
    ("BeIN Max 1",        "bein-max-1-izle",     "Sports"),
    ("BeIN Max 2",        "bein-max-2-izle",     "Sports"),
    ("S Sport",           "s-sport-izle",        "Sports"),
    ("S Sport 2",         "s-sport-2-izle",      "Sports"),
    ("TRT Spor",          "trt-spor-izle",       "Sports"),
    ("TRT Spor 2",        "trt-spor-2-izle",     "Sports"),
    ("TRT 1",             "trt-1-izle",          "General"),
    ("A Spor",            "a-spor-izle",         "Sports"),
    ("ATV",               "atv-izle",            "General"),
    ("TV 8",              "tv8-izle",            "General"),
    ("Tivibu Spor 1",     "tivibu-spor-1-izle",  "Sports"),
    ("Tivibu Spor 2",     "tivibu-spor-2-izle",  "Sports"),
    ("Tivibu Spor 3",     "tivibu-spor-3-izle",  "Sports"),
    ("Smart Spor",        "smart-spor-izle",     "Sports"),
    ("Smart Spor 2",      "smart-spor-2-izle",   "Sports"),
    ("Euro Sport 1",      "euro-sport-1-izle",   "Sports"),
    ("Euro Sport 2",      "euro-sport-2-izle",   "Sports"),
    ("NBA TV",            "nba-tv-izle",         "Sports"),
]

# ─── Logger ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("scraper")


def _get_driver() -> webdriver.Chrome:
    """Headless Chrome driver döndürür."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
    except Exception:
        driver = webdriver.Chrome(options=opts)
    return driver


def _extract_m3u8_from_source(page_source: str, page_url: str) -> List[str]:
    """Sayfa kaynağından m3u8 URL'lerini regex ile çıkarır."""
    patterns = [
        r'https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*',
        r'source\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
        r"'url'\s*:\s*'([^']+\.m3u8[^']*)'",
    ]
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, page_source, re.IGNORECASE):
            url = m.group(1) if m.lastindex else m.group(0)
            url = url.strip().strip('"').strip("'")
            if url.startswith("http"):
                found.add(url)
    return list(found)


def _extract_m3u8_from_network(driver: webdriver.Chrome) -> List[str]:
    """Chrome Performance Log üzerinden ağ isteklerini tarar."""
    found = []
    try:
        logs = driver.get_log("performance")
        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") in (
                "Network.requestWillBeSent",
                "Network.responseReceived"
            ):
                url = (msg.get("params", {})
                          .get("request", {})
                          .get("url", ""))
                if ".m3u8" in url.lower():
                    found.append(url)
    except Exception as e:
        log.debug(f"Network log okunamadı: {e}")
    return found


def scrape_channel(name: str, slug: str, group: str) -> Dict | None:
    """
    Tek bir kanalın m3u8 linkini bulur.
    Önce requests ile dener, başaramazsa Selenium kullanır.
    """
    url = f"{BASE_URL}/{slug}"
    log.info(f"[{name}] ▶ {url}")

    # ── Yöntem 1: Hızlı requests denemesi ──
    try:
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"),
            "Referer": BASE_URL,
        }
        r = requests.get(url, headers=headers, timeout=15)
        links = _extract_m3u8_from_source(r.text, url)
        if links:
            log.info(f"  ✅ requests ile bulundu: {links[0][:60]}...")
            return {"name": name, "group": group, "url": links[0], "slug": slug}
    except Exception as e:
        log.debug(f"  requests hatası: {e}")

    # ── Yöntem 2: Selenium ──
    driver = None
    try:
        caps = webdriver.DesiredCapabilities.CHROME.copy()
        caps["goog:loggingPrefs"] = {"performance": "ALL"}
        driver = _get_driver()
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(url)
        time.sleep(6)  # JS yüklenmesi için bekle

        # Sayfa kaynağından bul
        links = _extract_m3u8_from_source(driver.page_source, url)
        if links:
            log.info(f"  ✅ Selenium (kaynak) ile bulundu")
            return {"name": name, "group": group, "url": links[0], "slug": slug}

        # Ağ loglarından bul
        net_links = _extract_m3u8_from_network(driver)
        if net_links:
            log.info(f"  ✅ Selenium (network) ile bulundu")
            return {"name": name, "group": group, "url": net_links[0], "slug": slug}

        # iframe kaynaklarını kontrol et
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            src = iframe.get_attribute("src") or ""
            if src:
                driver.get(src)
                time.sleep(4)
                links = _extract_m3u8_from_source(driver.page_source, src)
                net_links = _extract_m3u8_from_network(driver)
                all_links = links + net_links
                if all_links:
                    log.info(f"  ✅ iframe içinde bulundu")
                    return {"name": name, "group": group,
                            "url": all_links[0], "slug": slug}

        log.warning(f"  ⚠️ [{name}] için m3u8 bulunamadı")
        return None

    except Exception as e:
        log.error(f"  ❌ Selenium hatası: {e}")
        return None
    finally:
        if driver:
            driver.quit()


def scrape_all_channels() -> List[Dict]:
    """Tüm kanalların m3u8 linklerini döndürür."""
    results = []
    for name, slug, group in CHANNEL_SLUGS:
        result = scrape_channel(name, slug, group)
        if result:
            results.append(result)
        time.sleep(2)  # sunucuya yük bindirme
    log.info(f"Toplam {len(results)}/{len(CHANNEL_SLUGS)} kanal bulundu.")
    return results
