#!/usr/bin/env python3
"""
main.py — Tüm sistemi bir araya getiren orkestratör

Kullanım:
  python main.py                         # Tam çalıştırma
  python main.py --dry-run               # Dosyaya yazmadan test
  python main.py --m3u liste.m3u        # Özel dosya yolu
  python main.py --channel "BeIN Sports" # Tek kanal test
  python main.py --force-domain-check    # Domain kontrol zorla
  python main.py --domain 9123456.xyz    # Manuel domain belirt
"""

import argparse, json, logging, sys
from pathlib import Path

from domain_finder import DomainFinder
from scraper import scrape_all, scrape_channel, load_state, load_channels
import requests, updater

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("updater.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("Main")

DEFAULT_M3U = Path("playlist.m3u")


def parse_args():
    p = argparse.ArgumentParser(description="IPTV M3U Auto-Updater (8602741.xyz)")
    p.add_argument("--m3u",          default=str(DEFAULT_M3U), help="M3U dosya yolu")
    p.add_argument("--dry-run",       action="store_true",     help="Dosyaya yazma")
    p.add_argument("--channel",       default=None,           help="Tek kanal adı test et")
    p.add_argument("--domain",        default=None,           help="Domain'i manuel belirt")
    p.add_argument("--force-domain-check", action="store_true", help="Domain kontrolünü zorla")
    p.add_argument("--no-verify",     action="store_true",     help="m3u8 doğrulamasını atla")
    return p.parse_args()


def run_domain_check(args) -> dict:
    """Domain kontrolünü çalıştırır ve aktif state'i döndürür."""
    if args.domain:
        # Manuel domain verilmiş
        state = load_state()
        state["current_domain"] = args.domain
        state["current_base_url"] = f"https://{args.domain}/event.html?id="
        Path("state.json").write_text(json.dumps(state, indent=2))
        log.info(f"🔧 Manuel domain: {args.domain}")
        return state

    finder = DomainFinder()
    result = finder.find_active_domain()

    if result.get("error"):
        log.error("Domain bulunamadı! Son bilinen state ile devam ediliyor.")
    elif result.get("changed"):
        log.info(f"🔄 YENİ DOMAIN: {result['domain']}")
    else:
        log.info(f"✅ Domain aynı: {result['domain']}")

    return load_state()


def run_single_channel(channel_name: str, state: dict):
    """Tek bir kanalı test eder."""
    channels = load_channels()
    ch = next((c for c in channels if c["name"].lower() == channel_name.lower()), None)
    if not ch:
        log.error(f"Kanal bulunamadı: '{channel_name}'")
        log.info(f"Mevcut kanallar: {[c['name'] for c in channels]}")
        sys.exit(1)

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    from scraper import scrape_channel
    url = scrape_channel(ch, state, session)
    if url:
        log.info(f"✅ [{channel_name}] → {url}")
    else:
        log.warning(f"❌ [{channel_name}] Link bulunamadı")


def main():
    args    = parse_args()
    m3u_path = Path(args.m3u)

    log.info("=" * 60)
    log.info("🚀 IPTV Auto-Updater başlatıldı (8602741.xyz Domain Tracker)")
    log.info("=" * 60)

    # ── 1. Domain Kontrolü ──────────────────────────────────────
    state = run_domain_check(args)
    log.info(f"📡 Aktif domain   : {state['current_domain']}")
    log.info(f"📂 Checklist base : {state['checklist_base']}")
    log.info(f"📄 M3U dosyası    : {m3u_path}")

    # ── 2. Tek Kanal Testi ──────────────────────────────────────
    if args.channel:
        run_single_channel(args.channel, state)
        return

    # ── 3. Tüm Kanalları Tara ───────────────────────────────────
    log.info("🕷️  Kanallar taranıyor...")
    new_links = scrape_all(state)

    if not new_links:
        log.warning("Hiç link bulunamadı. İşlem durduruluyor.")
        sys.exit(1)

    log.info(f"🔗 Bulunan link sayısı: {len(new_links)}")
    for name, url in new_links.items():
        log.info(f"  {name:35s} → {url}")

    # ── 4. M3U Güncelle ─────────────────────────────────────────
    if args.dry_run:
        log.info("🔍 DRY-RUN: Dosyaya yazılmıyor")
        return

    u, a, s = updater.update_m3u(
        m3u_path,
        new_links,
        domain=state["current_domain"]
    )

    log.info("=" * 60)
    log.info(f"✅ Tamamlandı → Güncellenen: {u} | Eklenen: {a} | Değişmeyen: {s}")

    # ── 5. GitHub Actions için output yaz ───────────────────────
    output_file = Path("update_result.json")
    output_file.write_text(json.dumps({
        "domain": state["current_domain"],
        "updated": u, "added": a, "unchanged": s,
        "total_found": len(new_links),
        "has_changes": (u + a) > 0,
    }, indent=2))


if __name__ == "__main__":
    main()
