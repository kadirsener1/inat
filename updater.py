# -*- coding: utf-8 -*-
"""
updater.py
M3U dosyasını akıllıca güncelleyen modül.

Kurallar:
  - SOURCE_TAG (#SOURCE:inattv1289.xyz) ile işaretli girişler güncellenir.
  - Diğer kaynaktan gelen girişlere HİÇ dokunulmaz.
  - Yeni kanal varsa eklenir, bulunamayan eski kanal M3U'da kalır ama
    işaretlenerek uyarı verilir.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict

SOURCE_TAG = "#SOURCE:inattv1289.xyz"
M3U_FILE   = "playlist.m3u"

log = logging.getLogger("updater")


class M3UEntry:
    """Tek bir M3U kanal girişini temsil eder."""
    def __init__(self, extinf: str, url: str, source_tag: str = "",
                 extra_lines: List[str] = None):
        self.extinf     = extinf
        self.url        = url
        self.source_tag = source_tag
        self.extra      = extra_lines or []

    @property
    def is_from_inattv(self) -> bool:
        return SOURCE_TAG in self.source_tag

    @property
    def channel_name(self) -> str:
        m = re.search(r',(.+)$', self.extinf)
        return m.group(1).strip() if m else ""

    def to_text(self) -> str:
        lines = [self.extinf]
        if self.source_tag:
            lines.append(self.source_tag)
        lines.extend(self.extra)
        lines.append(self.url)
        return "\n".join(lines)


def parse_m3u(content: str) -> tuple[str, List[M3UEntry]]:
    """M3U metnini ayrıştırır. (header, [entry, ...]) döndürür."""
    lines = content.splitlines()
    header = lines[0] if lines else "#EXTM3U"
    entries: List[M3UEntry] = []
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = line
            source_tag = ""
            extra = []
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt.startswith(SOURCE_TAG):
                    source_tag = nxt
                    i += 1
                elif nxt.startswith("#") and not nxt.startswith("#EXTINF"):
                    extra.append(nxt)
                    i += 1
                elif nxt.startswith("http") or nxt.startswith("rtmp"):
                    entries.append(M3UEntry(extinf, nxt, source_tag, extra))
                    i += 1
                    break
                else:
                    i += 1
        else:
            i += 1
    return header, entries


def build_extinf(ch: Dict) -> str:
    """Yeni bir #EXTINF satırı oluşturur."""
    name  = ch["name"]
    group = ch.get("group", "Sports")
    slug  = ch.get("slug", "")
    logo  = ch.get("logo", "")
    logo_attr = f' tvg-logo="{logo}"' if logo else ""
    return (
        f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{name}"'
        f'{logo_attr} group-title="{group}",{name}'
    )


def update_m3u(channels: List[Dict], m3u_path: str = M3U_FILE) -> Dict:
    """
    M3U dosyasını günceller.
    - Dosya yoksa sıfırdan oluşturur.
    - Sadece SOURCE_TAG ile işaretli girişleri günceller.
    - Diğer girişlere dokunmaz.
    Geri döner: {added, updated, unchanged, not_found}
    """
    stats = {"added": 0, "updated": 0, "unchanged": 0, "not_found": 0}

    # ── Mevcut dosyayı oku ──
    if os.path.exists(m3u_path):
        with open(m3u_path, "r", encoding="utf-8") as f:
            content = f.read()
        header, entries = parse_m3u(content)
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        header = (
            f'#EXTM3U x-tvg-url="" '
            f'url-tvg="https://www.epgshares.com/epg_tr.xml.gz"\n'
            f'# Oluşturulma: {now}\n'
            f'# Bu dosya otomatik güncellenir - inattv1289.xyz kaynaklı\n'
            f'# bölüm dışındaki kanallar korunur.'
        )
        entries = []

    # ── Scraped kanalları isme göre indeksle ──
    scraped_map: Dict[str, Dict] = {ch["name"].lower(): ch for ch in channels}
    processed_names = set()

    # ── Mevcut girişleri güncelle ──
    for entry in entries:
        key = entry.channel_name.lower()
        if entry.is_from_inattv and key in scraped_map:
            ch = scraped_map[key]
            new_url = ch["url"]
            if entry.url != new_url:
                log.info(f"  🔄 Güncellendi: {entry.channel_name}")
                entry.url    = new_url
                entry.extinf = build_extinf(ch)
                entry.source_tag = SOURCE_TAG
                stats["updated"] += 1
            else:
                log.info(f"  ✅ Değişmedi: {entry.channel_name}")
                stats["unchanged"] += 1
            processed_names.add(key)
        elif entry.is_from_inattv and key not in scraped_map:
            log.warning(f"  ⚠️ Sitede bulunamadı (korunuyor): {entry.channel_name}")
            stats["not_found"] += 1

    # ── Yeni kanalları ekle ──
    for ch in channels:
        if ch["name"].lower() not in processed_names:
            log.info(f"  ➕ Eklendi: {ch['name']}")
            entries.append(M3UEntry(
                extinf=build_extinf(ch),
                url=ch["url"],
                source_tag=SOURCE_TAG
            ))
            stats["added"] += 1

    # ── Dosyayı yaz ──
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out_lines = [
        header,
        f"# Son güncelleme: {now_str}",
        ""
    ]
    for e in entries:
        out_lines.append(e.to_text())
        out_lines.append("")

    with open(m3u_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out_lines))

    log.info(f"📄 {m3u_path} yazıldı — "
             f"Eklenen:{stats['added']} Güncellenen:{stats['updated']} "
             f"Değişmez:{stats['unchanged']} Bulunamayan:{stats['not_found']}")
    return stats
