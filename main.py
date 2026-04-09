#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — IPTV M3U8 Scraper & Updater
Kullanım:
  python main.py                              # tüm kanallar
  python main.py --channel "BeIN Sports 1 HD" # tek kanal
  python main.py --dry-run                    # yazmadan göster
  python main.py --no-selenium                # sadece requests
  python main.py --m3u /path/to/list.m3u      # özel dosya
"""

import sys
import argparse
import logging
from scraper import scrape_all, scrape_channel, CHANNELS, make_session, make_driver, SELENIUM_OK
from updater import update_playlist, DEFAULT_M3U_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ]
)

def parse_args():
    p = argparse.ArgumentParser(description="IPTV M3U8 Scraper — netspor.tecostream.xyz")
    p.add_argument("--channel",     default=None,
                   help="Tek kanal adı (örn: 'BeIN Sports 1 HD')")
    p.add_argument("--m3u",        default=DEFAULT_M3U_FILE,
                   help=f"M3U dosya yolu (varsayılan: {DEFAULT_M3U_FILE})")
    p.add_argument("--dry-run",    action="store_true",
                   help="Dosyaya yazmadan sadece önizle")
    p.add_argument("--no-selenium",action="store_true",
                   help="Selenium kullanma (sadece requests)")
    return p.parse_args()

def main():
    args = parse_args()
    use_sel = (not args.no_selenium) and SELENIUM_OK

    if args.channel:
        # Tek kanal modu
        target = None
        for ch in CHANNELS:
            if ch.name.lower() == args.channel.lower():
                target = ch; break
        if not target:
            print(f"Hata: '{args.channel}' kanalı bulunamadı.")
            print("Geçerli kanallar:")
            for c in CHANNELS:
                print(f"  - {c.name}")
            sys.exit(1)

        session = make_session()
        driver  = make_driver() if use_sel else None
        try:
            link = scrape_channel(target, session, driver)
            if link:
                print(f"✓ {target.name}: {link}")
                new_links = {target.name: link}
                update_playlist(new_links, args.m3u, args.dry_run)
            else:
                print(f"✗ {target.name}: link bulunamadı")
        finally:
            if driver: driver.quit()
            session.close()
    else:
        # Tüm kanallar
        new_links = scrape_all(use_selenium=use_sel)
        if new_links:
            update_playlist(new_links, args.m3u, args.dry_run)
        else:
            print("Hiç m3u8 linki bulunamadı! Site erişilemez olabilir.")
            sys.exit(1)

if __name__ == "__main__":
    main()
