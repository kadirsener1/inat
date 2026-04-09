# -*- coding: utf-8 -*-
"""
main.py
Ana giriş noktası. Scraper + Updater'ı çalıştırır.
"""

import os
import sys
import logging
import argparse
from scraper import scrape_all_channels, CHANNEL_SLUGS
from updater import update_m3u, M3U_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("update.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("main")


def parse_args():
    p = argparse.ArgumentParser(description="iNat TV M3U Güncelleyici")
    p.add_argument("--m3u", default=M3U_FILE,
                   help="Güncellenecek M3U dosya yolu (varsayılan: playlist.m3u)")
    p.add_argument("--dry-run", action="store_true",
                   help="Dosyayı yazmadan sadece sonuçları göster")
    p.add_argument("--channel", metavar="NAME",
                   help="Tek bir kanalı güncelle (test için)")
    return p.parse_args()


def main():
    args = parse_args()
    log.info("=" * 55)
    log.info("  iNat TV M3U Güncelleyici başlatıldı")
    log.info("=" * 55)

    # ── Tek kanal modu ──
    if args.channel:
        from scraper import scrape_channel
        match = [
            (n, s, g) for n, s, g in CHANNEL_SLUGS
            if args.channel.lower() in n.lower()
        ]
        if not match:
            log.error(f"'{args.channel}' isimli kanal bulunamadı.")
            sys.exit(1)
        channels = [scrape_channel(*m) for m in match]
        channels = [c for c in channels if c]
    else:
        # ── Tüm kanallar ──
        channels = scrape_all_channels()

    if not channels:
        log.error("Hiç kanal bulunamadı! Çıkılıyor.")
        sys.exit(1)

    log.info(f"Bulunan kanal sayısı: {len(channels)}")
    for ch in channels:
        log.info(f"  📺 {ch['name']:25s}  {ch['url'][:55]}...")

    if args.dry_run:
        log.info("[DRY RUN] Dosya yazılmadı.")
        return

    # ── M3U'yu güncelle ──
    stats = update_m3u(channels, m3u_path=args.m3u)

    log.info("─" * 55)
    log.info(f"  ➕ Eklenen  : {stats['added']}")
    log.info(f"  🔄 Güncellenen: {stats['updated']}")
    log.info(f"  ✅ Değişmez : {stats['unchanged']}")
    log.info(f"  ⚠️ Bulunamayan: {stats['not_found']}")
    log.info("=" * 55)
    log.info("  Güncelleme tamamlandı ✅")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
