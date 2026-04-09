#!/usr/bin/env python3
# updater.py — v3.0
# Sadece SOURCE etiketli girişleri günceller, diğerlerine dokunmaz

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

M3U_FILE = Path("playlist.m3u")

SOURCES = {
    "8602741":   "#SOURCE:8602741.xyz",
    "tecostream": "#SOURCE:netspor.tecostream.xyz",
    "inattv":    "#SOURCE:inattv1289.xyz",
}

M3U_HEADER = """\
#EXTM3U url-epg="http://epg.streamstv.me/epg/guide-turkey.xml.gz" x-tvg-url="http://epg.streamstv.me/epg/guide-turkey.xml.gz"
#PLAYLIST:TR Sports Auto-Updated

"""

def _make_entry(name: str, group: str, logo: str, source_key: str,
                channel_id: str, url: str) -> str:
    """Tek bir M3U girişi oluştur."""
    source_tag = SOURCES.get(source_key, f"#SOURCE:{source_key}")
    return (
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" '
        f'tvg-logo="{logo}" group-title="{group}",{name}\n'
        f'{source_tag}\n'
        f'{url}\n'
    )


def load_m3u() -> str:
    """M3U dosyasını oku. Yoksa boş header döndür."""
    if M3U_FILE.exists():
        return M3U_FILE.read_text(encoding="utf-8")
    logger.info("playlist.m3u bulunamadı, sıfırdan oluşturuluyor.")
    return M3U_HEADER


def parse_entries(content: str) -> Dict[str, dict]:
    """
    M3U içeriğini parse et.
    
    Returns:
        dict: {channel_id: {extinf, source_tag, url, raw_block}}
    """
    entries = {}
    lines   = content.splitlines(keepends=True)
    i       = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("#EXTINF:"):
            block_start = i
            extinf_line = line.strip()

            # tvg-id çek
            id_match = re.search(r'tvg-id="([^"]*)"', extinf_line)
            cid      = id_match.group(1) if id_match else ""

            source_tag = ""
            url        = ""
            j          = i + 1

            while j < len(lines):
                nxt = lines[j].strip()
                if nxt.startswith("#SOURCE:"):
                    source_tag = nxt
                    j += 1
                elif nxt and not nxt.startswith("#"):
                    url = nxt
                    j += 1
                    break
                elif nxt.startswith("#EXTINF:"):
                    break
                else:
                    j += 1

            raw = "".join(lines[block_start:j])

            if cid:
                entries[cid] = {
                    "extinf":     extinf_line,
                    "source_tag": source_tag,
                    "url":        url,
                    "raw":        raw,
                    "line_start": block_start,
                }
            i = j
        else:
            i += 1

    return entries


def update_m3u(new_links: Dict[str, dict], dry_run: bool = False) -> dict:
    """
    M3U dosyasını akıllıca güncelle.
    
    Kurallar:
      - SOURCE etiketli kanallar → güncellenir
      - SOURCE etiketi olmayan   → kesinlikle dokunulmaz
      - Yeni kanal               → sona eklenir
      - Değişmeyen URL           → olduğu gibi bırakılır
    
    Returns:
        dict: {added, updated, unchanged, skipped}
    """
    content  = load_m3u()
    existing = parse_entries(content)

    stats = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    managed_sources = set(SOURCES.values())

    # Header'ı koru
    header_end = content.find("#EXTINF:")
    header     = content[:header_end] if header_end > 0 else M3U_HEADER

    # Yeni içerik oluştur
    new_content = header

    # 1. Mevcut girişleri işle
    processed_ids = set()
    for cid, entry in existing.items():
        is_managed = entry["source_tag"] in managed_sources

        if cid in new_links and is_managed:
            new_data = new_links[cid]
            new_url  = new_data["url"]

            if new_url == entry["url"]:
                new_content += entry["raw"]
                stats["unchanged"] += 1
                logger.debug(f"  = Değişmedi: {new_data['name']}")
            else:
                # URL güncelle, EXTINF satırını koru
                updated_block = (
                    entry["extinf"] + "\n"
                    + SOURCES.get(new_data["source"], entry["source_tag"]) + "\n"
                    + new_url + "\n"
                )
                new_content += updated_block
                stats["updated"] += 1
                logger.info(f"  ↻ Güncellendi: {new_data['name']}")
                logger.info(f"    Eski: {entry['url'][:60]}")
                logger.info(f"    Yeni: {new_url[:60]}")
        else:
            # Yönetilmeyen giriş → olduğu gibi bırak
            new_content += entry["raw"]
            if not is_managed:
                stats["skipped"] += 1

        processed_ids.add(cid)

    # 2. Yeni kanalları ekle
    for cid, data in new_links.items():
        if cid not in processed_ids:
            new_entry = _make_entry(
                name=data["name"],
                group=data["group"],
                logo=data["logo"],
                source_key=data["source"],
                channel_id=cid,
                url=data["url"],
            )
            new_content += new_entry
            stats["added"] += 1
            logger.info(f"  + Eklendi: {data['name']}")

    # 3. Timestamp güncelle
    ts_comment = f"# Son güncelleme: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    if "# Son güncelleme:" in new_content:
        new_content = re.sub(r"# Son güncelleme:.*\n", ts_comment, new_content)
    else:
        new_content = new_content.replace(M3U_HEADER.strip(), M3U_HEADER.strip() + "\n" + ts_comment)

    if not dry_run:
        M3U_FILE.write_text(new_content, encoding="utf-8")
        logger.info(f"playlist.m3u yazıldı ({M3U_FILE.stat().st_size / 1024:.1f} KB)")
    else:
        logger.info("DRY RUN — dosyaya yazılmadı")

    logger.info(
        f"Sonuç → Eklenen: {stats['added']} | "
        f"Güncellenen: {stats['updated']} | "
        f"Değişmeyen: {stats['unchanged']} | "
        f"Atlanılan: {stats['skipped']}"
    )
    return stats
