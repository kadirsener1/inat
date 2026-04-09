#!/usr/bin/env python3
"""
updater.py — M3U dosyasını akıllıca güncelleyen modül

Kurallar:
  ✅ #SOURCE:8602741.xyz etiketli girişleri günceller
  ✅ Link değiştiyse → yeni linki yazar
  ✅ Link aynıysa    → hiç dokunmaz
  ✅ Yeni kanal varsa → ekler
  ❌ Başka kaynaklı kanalları (inattv1289, netspor...) kesinlikle değiştirmez
  ❌ El ile eklenen kanalları silmez
"""

import re, json, logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Updater")

SOURCE_TAG      = "8602741.xyz"
SOURCE_MARKER   = f"#SOURCE:{SOURCE_TAG}"
CHANNELS_FILE   = Path("channels.json")
STATE_FILE      = Path("state.json")

EPG_URL = "https://epg.pw/xmltv.xml.gz"
EPG_BACKUP = "http://195.154.221.171/epg/guidecombo.xml"


def load_channels_meta() -> Dict[str, dict]:
    """channels.json'dan kanal metadata'sını yükler."""
    if not CHANNELS_FILE.exists():
        return {}
    data = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
    return {ch["name"]: ch for ch in data}


def parse_m3u(content: str) -> Tuple[str, List[dict]]:
    """
    M3U içeriğini ayrıştırır.
    Returns: (header_line, entries_list)
    entries: [{"extinf": str, "source": str|None, "url": str, "raw_lines": list}]
    """
    lines  = content.splitlines()
    header = lines[0] if lines and lines[0].startswith("#EXTM3U") else "#EXTM3U"
    entries = []
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            entry = {"extinf": line, "source": None, "url": "", "extra": []}
            i += 1
            # #EXTVLCOPT veya #SOURCE satırlarını topla
            while i < len(lines) and lines[i].startswith("#") and not lines[i].startswith("#EXTINF"):
                meta = lines[i].strip()
                if meta.startswith("#SOURCE:"):
                    entry["source"] = meta.split(":", 1)[1].strip()
                else:
                    entry["extra"].append(meta)
                i += 1
            # URL satırı
            if i < len(lines) and not lines[i].startswith("#"):
                entry["url"] = lines[i].strip()
                i += 1
            entries.append(entry)
        else:
            i += 1
    return header, entries


def extract_channel_name(extinf: str) -> str:
    """#EXTINF satırından kanal adını çıkarır."""
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else ""


def build_extinf(ch_meta: dict, domain: str) -> str:
    """channels.json metadata'sından #EXTINF satırı üretir."""
    name      = ch_meta.get("name", "Kanal")
    tvg_id    = ch_meta.get("tvg_id", "")
    tvg_name  = ch_meta.get("tvg_name", name)
    logo      = ch_meta.get("logo", "")
    group     = ch_meta.get("group", "Spor")

    parts = ['-1']
    if tvg_id:    parts.append(f'tvg-id="{tvg_id}"')
    if tvg_name:  parts.append(f'tvg-name="{tvg_name}"')
    if logo:      parts.append(f'tvg-logo="{logo}"')
    if group:     parts.append(f'group-title="{group}"')

    attrs = " ".join(parts)
    return f"#EXTINF:{attrs},{name}"


def update_m3u(
    m3u_path: Path,
    new_links: Dict[str, str],
    domain: str = SOURCE_TAG
) -> Tuple[int, int, int]:
    """
    M3U dosyasını akıllıca günceller.
    
    Args:
        m3u_path: Güncellenecek .m3u dosyası
        new_links: {kanal_adı: yeni_m3u8_url}
        domain: Kaynak etiketi (8602741.xyz)
    
    Returns: (güncellenen, eklenen, değişmeyen) sayıları
    """
    channels_meta = load_channels_meta()
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

    # Dosya yoksa oluştur
    if not m3u_path.exists():
        log.info(f"M3U dosyası yok, oluşturuluyor: {m3u_path}")
        _create_fresh_m3u(m3u_path, new_links, channels_meta, domain)
        return 0, len(new_links), 0

    content = m3u_path.read_text(encoding="utf-8")
    header, entries = parse_m3u(content)

    updated  = 0
    added    = 0
    same     = 0
    processed_names = set()

    # Mevcut girişleri güncelle
    for entry in entries:
        ch_name = extract_channel_name(entry["extinf"])
        src     = entry.get("source")

        # Bu siteden değilse DOKUNMA
        if src != domain:
            processed_names.add(ch_name)
            continue

        # Bu siteden ama yeni link yoksa (taramada bulunamadı) — olduğu gibi bırak
        if ch_name not in new_links:
            processed_names.add(ch_name)
            same += 1
            log.debug(f"[{ch_name}] Taramada bulunamadı, mevcut link korunuyor")
            continue

        new_url = new_links[ch_name]
        if entry["url"] == new_url:
            same += 1
            log.debug(f"[{ch_name}] Değişmedi ✓")
        else:
            old_url = entry["url"]
            entry["url"] = new_url
            # EXTINF'i de güncelle (metadata değişmiş olabilir)
            if ch_name in channels_meta:
                entry["extinf"] = build_extinf(channels_meta[ch_name], domain)
            updated += 1
            log.info(f"[{ch_name}] 🔄 Güncellendi:\n    ESKİ: {old_url}\n    YENİ: {new_url}")

        processed_names.add(ch_name)

    # Yeni kanalları ekle (M3U'da olmayan ama taramada bulunanlar)
    for ch_name, new_url in new_links.items():
        if ch_name in processed_names:
            continue
        meta    = channels_meta.get(ch_name, {"name": ch_name, "group": "Spor"})
        extinf  = build_extinf(meta, domain)
        entries.append({
            "extinf": extinf,
            "source": domain,
            "url": new_url,
            "extra": [],
        })
        added += 1
        log.info(f"[{ch_name}] ➕ Yeni kanal eklendi: {new_url}")

    # Dosyayı yeniden yaz
    _write_m3u(m3u_path, header, entries, domain, state)

    log.info(f"📊 Sonuç → Güncellenen: {updated} | Eklenen: {added} | Değişmeyen: {same}")
    return updated, added, same


def _write_m3u(path: Path, header: str, entries: List[dict], domain: str, state: dict):
    """M3U dosyasını yazar."""
    now     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cur_dom = state.get("current_domain", domain)
    lines   = [
        header,
        f"# Güncellenme: {now}",
        f"# Aktif Domain: {cur_dom}",
        f"# Kaynak: https://{cur_dom}/event.html?id=",
        "",
    ]
    for entry in entries:
        lines.append(entry["extinf"])
        for ex in entry.get("extra", []):
            lines.append(ex)
        if entry.get("source"):
            lines.append(f"#SOURCE:{entry['source']}")
        lines.append(entry["url"])
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"💾 M3U yazıldı: {path} ({len(entries)} kanal)")


def _create_fresh_m3u(path: Path, links: Dict[str, str], meta: dict, domain: str):
    """Sıfırdan M3U dosyası oluşturur."""
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    entries = []
    for name, url in links.items():
        ch_meta = meta.get(name, {"name": name, "group": "Spor"})
        entries.append({
            "extinf": build_extinf(ch_meta, domain),
            "source": domain,
            "url": url,
            "extra": [],
        })
    header = ('#EXTM3U x-tvg-url="' + EPG_URL + '" x-tvg-url-backup="' + EPG_BACKUP + '"')
    _write_m3u(path, header, entries, domain, state)
