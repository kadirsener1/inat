#!/usr/bin/env python3
# main.py — v3.0
# Kullanım: python main.py [--channel "BeIN Sports 1 HD"] [--dry-run] [--source 8602741]

import argparse
import logging
import sys
from pathlib import Path

# Logging ayarı
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("updater.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="IPTV M3U Auto-Updater v3.0")
    parser.add_argument("--channel",    help="Tek kanal adı ile test et")
    parser.add_argument("--source",     help="Kaynak filtrele: 8602741 | tecostream | inattv")
    parser.add_argument("--dry-run",    action="store_true", help="Dosyaya yazma, sadece göster")
    parser.add_argument("--no-domain-check", action="store_true", help="Domain kontrolünü atla")
    parser.add_argument("--m3u",        default="playlist.m3u", help="M3U dosya yolu")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("IPTV Auto-Updater v3.0 başlıyor...")
    logger.info("=" * 60)

    # M3U dosya yolunu güncelle
    from updater import M3U_FILE
    import updater
    updater.M3U_FILE = Path(args.m3u)

    # 1. Domain kontrolü
    state = {}
    if not args.no_domain_check:
        logger.info("[1/3] Domain kontrolü...")
        try:
            from domain_finder import find_current_domain
            state = find_current_domain()
            logger.info(f"  Domain: {state.get('domain_8602741', '?')}")
        except Exception as e:
            logger.error(f"Domain kontrolü hatası: {e}")
            from domain_finder import load_state
            state = load_state()
    else:
        from domain_finder import load_state
        state = load_state()
        logger.info("[1/3] Domain kontrolü atlandı.")

    # 2. Kanal tarama
    logger.info("[2/3] Kanallar taranıyor...")
    try:
        from scraper import scrape_all, load_channels, scrape_channel

        if args.channel or args.source:
            # Tek kanal veya kaynak filtresi
            all_channels = load_channels()
            filtered     = []

            for ch in all_channels:
                if args.channel and args.channel.lower() not in ch.get("name", "").lower():
                    continue
                if args.source and ch.get("source", "") != args.source:
                    continue
                filtered.append(ch)

            logger.info(f"Filtre sonucu: {len(filtered)} kanal")
            new_links = {}
            for ch in filtered:
                result = scrape_channel(ch, state)
                if result:
                    cid = ch.get("id", ch["name"])
                    new_links[cid] = {
                        "url":    result,
                        "name":   ch["name"],
                        "group":  ch.get("group", "Spor"),
                        "logo":   ch.get("logo", ""),
                        "source": ch.get("source", ""),
                    }
        else:
            new_links = scrape_all(state)

    except Exception as e:
        logger.error(f"Tarama hatası: {e}", exc_info=True)
        sys.exit(1)

    logger.info(f"Bulunan linkler: {len(new_links)}")

    # 3. M3U güncelleme
    logger.info("[3/3] M3U dosyası güncelleniyor...")
    try:
        from updater import update_m3u
        stats = update_m3u(new_links, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Güncelleme hatası: {e}", exc_info=True)
        sys.exit(1)

    # Özet
    logger.info("=" * 60)
    logger.info(f"✅ Tamamlandı!")
    logger.info(f"   Eklenen   : {stats['added']}")
    logger.info(f"   Güncellenen: {stats['updated']}")
    logger.info(f"   Değişmeyen: {stats['unchanged']}")
    logger.info(f"   Atlanılan : {stats['skipped']}")
    if not args.dry_run and stats["added"] + stats["updated"] > 0:
        logger.info(f"   📁 Dosya   : {args.m3u}")
    logger.info("=" * 60)

    # GitHub Actions için çıkış kodu
    # 0 = değişiklik var veya başarılı, 0 döner
    changed = stats["added"] + stats["updated"]
    if changed > 0:
        logger.info(f"GitHub Actions: {changed} değişiklik → commit atılacak")
    else:
        logger.info("GitHub Actions: Değişiklik yok → commit atlanacak")

    sys.exit(0)


if __name__ == "__main__":
    main()
