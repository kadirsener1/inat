#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
updater.py — M3U Akıllı Güncelleyici
Yalnızca netspor.tecostream.xyz kaynaklı linkleri değiştirir.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from scraper import CHANNELS, SOURCE_TAG, Channel

log = logging.getLogger("updater")

SOURCE_MARKER    = f"#SOURCE:{SOURCE_TAG}"
DEFAULT_M3U_FILE = "playlist.m3u"

EPG_URL = "https://epg.pw/xmltv.xml.gz"  # genel Türk EPG

# ── M3U Header ──────────────────────────────────────────────
def m3u_header() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f'#EXTM3U url-tvg="{EPG_URL}" tvg-shift="+3" '
        f'x-tvg-url="{EPG_URL}" '
        f'refresh="3600"\n'
        f'# Otomatik güncellendi: {ts}\n'
        f'# Kaynak: {SOURCE_TAG}\n'
    )

# ── Kanal için EXTINF satırı ─────────────────────────────────
def build_extinf(ch: Channel, url: str) -> str:
    return (
        f'{SOURCE_MARKER}\n'
        f'#EXTINF:-1 tvg-id="{ch.tvg_id or ch.name}" '
        f'tvg-name="{ch.name}" '
        f'tvg-logo="{ch.logo}" '
        f'group-title="{ch.group}",'
        f'{ch.name}\n'
        f'{url}\n'
    )

# ── M3U dosyasını parse et ──────────────────────────────────
class M3UEntry:
    def __init__(self, raw_lines: List[str], is_source: bool = False):
        self.raw_lines  = raw_lines
        self.is_source  = is_source   # bu site'den mi?
        self.channel_name = ""
        self._parse()

    def _parse(self):
        for line in self.raw_lines:
            m = re.search(r'tvg-name="([^"]+)"', line)
            if m:
                self.channel_name = m.group(1)
                break
            m2 = re.match(r'#EXTINF.*,(.+)$', line)
            if m2:
                self.channel_name = m2.group(1).strip()

    def render(self) -> str:
        return "\n".join(self.raw_lines) + "\n"

def parse_m3u(path: str) -> Tuple[str, List[M3UEntry]]:
    if not os.path.exists(path):
        return m3u_header(), []

    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    header_lines = []
    entries: List[M3UEntry] = []
    i = 0

    # header topla
    while i < len(lines) and not lines[i].startswith("#EXTINF") and not lines[i].startswith(SOURCE_MARKER):
        header_lines.append(lines[i])
        i += 1

    while i < len(lines):
        chunk = []
        is_src = False

        if lines[i].startswith(SOURCE_MARKER):
            is_src = True
            chunk.append(lines[i])
            i += 1

        while i < len(lines) and lines[i].startswith("#"):
            chunk.append(lines[i]); i += 1

        if i < len(lines) and not lines[i].startswith("#") and lines[i].strip():
            chunk.append(lines[i]); i += 1

        if chunk:
            entries.append(M3UEntry(chunk, is_src))

    header = "\n".join(header_lines)
    if not header.startswith("#EXTM3U"):
        header = m3u_header()
    return header, entries

# ── Kanal adı normalize ─────────────────────────────────────
def normalize(name: str) -> str:
    return re.sub(r'\s+', ' ', name.lower().strip()
               .replace("ı","i").replace("ğ","g").replace("ş","s")
               .replace("ç","c").replace("ö","o").replace("ü","u"))

# ── Ana güncelleme fonksiyonu ────────────────────────────────
def update_playlist(
    new_links: Dict[str, str],
    m3u_path: str = DEFAULT_M3U_FILE,
    dry_run: bool = False
) -> Dict[str, int]:
    if not new_links:
        log.warning("Yeni link bulunamadı, güncelleme atlandı.")
        return {"added":0, "updated":0, "unchanged":0, "kept":0}

    header, entries = parse_m3u(m3u_path)

    # Bu siteden olmayan girişleri koru
    other_entries = [e for e in entries if not e.is_source]
    source_entries= [e for e in entries if     e.is_source]

    # Mevcut kaynak girişlerini ada göre map et
    existing_map: Dict[str, M3UEntry] = {}
    for e in source_entries:
        existing_map[normalize(e.channel_name)] = e

    # Kanal kataloğunu ada göre map et
    ch_map: Dict[str, Channel] = {normalize(c.name): c for c in CHANNELS}

    stats = {"added":0, "updated":0, "unchanged":0, "kept": len(other_entries)}
    new_source_blocks: List[str] = []

    for ch in CHANNELS:
        key    = normalize(ch.name)
        new_url= new_links.get(ch.name)

        if not new_url:
            # Yeni link yoksa var olanı koru
            if key in existing_map:
                new_source_blocks.append(existing_map[key].render())
                log.info(f"  KORUNDU  | {ch.name}")
            else:
                log.warning(f"  ATLANDI  | {ch.name} (link yok)")
            continue

        if key in existing_map:
            old_lines = existing_map[key].raw_lines
            old_url   = old_lines[-1].strip()
            if old_url == new_url:
                new_source_blocks.append(existing_map[key].render())
                stats["unchanged"] += 1
                log.info(f"  AYNI     | {ch.name}")
            else:
                new_source_blocks.append(build_extinf(ch, new_url))
                stats["updated"] += 1
                log.info(f"  GÜNCELLENDİ | {ch.name}")
                log.info(f"    ESKİ: {old_url}")
                log.info(f"    YENİ: {new_url}")
        else:
            new_source_blocks.append(build_extinf(ch, new_url))
            stats["added"] += 1
            log.info(f"  EKLENDİ  | {ch.name} → {new_url}")

    # Dosya oluştur
    output_parts = [header.rstrip("\n") + "\n"]
    output_parts += ["# ── Diğer kaynaklar ──────────────────────────────\n"]
    output_parts += [e.render() for e in other_entries]
    output_parts += [f"\n# ── {SOURCE_TAG} (otomatik) ─────────────────\n"]
    output_parts += new_source_blocks

    content = "".join(output_parts)

    if not dry_run:
        with open(m3u_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        log.info(f"Yazıldı → {m3u_path}")
    else:
        log.info("[DRY-RUN] — Dosyaya yazılmadı.")
        print(content)

    log.info(
        f"Özet: +{stats['added']} eklendi | "
        f"~{stats['updated']} güncellendi | "
        f"={stats['unchanged']} değişmedi | "
        f"{stats['kept']} başka kaynak korundu"
    )
    return stats
