#!/usr/bin/env python3
"""
domain_finder.py — 8602741.xyz gibi değişen domain'leri otomatik bulan modül

Strateji:
  1) Bilinen kök domain kalıbını (*.xyz) DNS sorgusuyla test eder
  2) Wayback Machine CDX API ile arşivlenmiş URL'leri tarar
  3) Telegram kanallarındaki mesajlarda yeni domain'i arar
  4) DNS over HTTPS (Cloudflare/Google) ile subdomain keşfi yapar
  5) Bulunan domain'i state.json'a kaydeder, değişince bildirir
"""

import re, json, time, logging, requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("DomainFinder")

# ─── Sabit Ayarlar ────────────────────────────────────────────────────────────
STATE_FILE   = Path("state.json")
HEADERS      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT      = 10
SESSION      = requests.Session()
SESSION.headers.update(HEADERS)

# Bilinen kaynak domain yapısı — bu URL'lerin format kalıpları
BASE_URL_PATTERN = r"(?:https?://)?(\d+)\.xyz/event\.html"
CHECKLIST_HOSTS  = [
    "andro.evrenosoglu53.lat",
    "evrenosoglu53.lat",
]
# Kaynak bulma: bu endpointler eski domain'i yönlendirdiğinde yeni adresi verir
TRACKER_SOURCES = [
    "https://mahsunsportsx.blogspot.com",
    "https://t.me/s/mahsunsportsx",
    "https://t.me/s/kraloranlar",
    "https://web.archive.org/cdx/search/cdx?url=*.xyz/event.html&output=json&limit=10&fl=original&from=20240101",
]


class DomainFinder:
    def __init__(self):
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text())
            except:
                pass
        return {
            "current_domain": "8602741.xyz",
            "current_base_url": "https://8602741.xyz/event.html?id=",
            "checklist_base": "https://andro.evrenosoglu53.lat/checklist/",
            "last_seen": None,
            "history": [],
            "last_check": None,
        }

    def _save_state(self):
        self.state["last_check"] = datetime.now(timezone.utc).isoformat()
        STATE_FILE.write_text(json.dumps(self.state, indent=2, ensure_ascii=False))

    def _test_domain(self, domain: str) -> bool:
        """Domain'in event.html sayfasını sunup sunmadığını kontrol eder."""
        for scheme in ["https", "http"]:
            url = f"{scheme}://{domain}/event.html?id=test"
            try:
                r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code == 200 and "clappr" in r.text.lower():
                    log.info(f"✅ Aktif domain bulundu: {domain}")
                    return True
            except:
                continue
        return False

    def _extract_domains_from_text(self, text: str) -> List[str]:
        """Metin içinden sayısal .xyz domain'lerini çıkarır."""
        matches = re.findall(r"\b(\d{5,10})\.xyz\b", text)
        return list({f"{m}.xyz" for m in matches})

    def _check_current_domain(self) -> bool:
        """Mevcut kayıtlı domain hâlâ çalışıyor mu?"""
        domain = self.state.get("current_domain", "")
        return self._test_domain(domain) if domain else False

    def _search_wayback(self) -> List[str]:
        """Wayback Machine CDX API ile arşivlenmiş domain'leri bulur."""
        candidates = []
        url = ("https://web.archive.org/cdx/search/cdx"
               "?url=*.xyz/event.html*&output=json&limit=50"
               "&fl=original&from=20240101&collapse=urlkey")
        try:
            r = SESSION.get(url, timeout=20)
            if r.ok:
                data = r.json()
                for row in data[1:]:      # İlk satır başlık
                    found = self._extract_domains_from_text(row[0])
                    candidates.extend(found)
        except Exception as e:
            log.warning(f"Wayback hatası: {e}")
        return list(set(candidates))

    def _search_tracker_pages(self) -> List[str]:
        """Telegram kanalları ve blog sayfalarından yeni domain arar."""
        candidates = []
        for src_url in TRACKER_SOURCES:
            try:
                r = SESSION.get(src_url, timeout=TIMEOUT)
                if r.ok:
                    found = self._extract_domains_from_text(r.text)
                    candidates.extend(found)
                    log.info(f"Tracker {src_url[:50]}... → {len(found)} aday")
            except Exception as e:
                log.warning(f"Tracker hatası ({src_url[:40]}): {e}")
        return list(set(candidates))

    def _search_redirect_chain(self) -> Optional[str]:
        """Eski domain yenisine yönlendiriyor olabilir — takip et."""
        old_domain = self.state.get("current_domain", "8602741.xyz")
        test_url = f"https://{old_domain}/event.html?id=test"
        try:
            r = SESSION.get(test_url, timeout=TIMEOUT, allow_redirects=True)
            final = urlparse(r.url)
            new_domain = final.netloc
            if new_domain and new_domain != old_domain:
                log.info(f"🔀 Redirect zinciri: {old_domain} → {new_domain}")
                return new_domain
        except:
            pass
        return None

    def _search_dns_bruteforce(self) -> List[str]:
        """
        Bilinen numaranın +/-500 aralığını hızlıca test eder.
        Mevcut domain numarasına yakın domainleri kontrol eder.
        """
        candidates = []
        current = self.state.get("current_domain", "8602741.xyz")
        m = re.match(r"(\d+)\.xyz", current)
        if not m:
            return []
        base_num = int(m.group(1))
        # Sadece Cloudflare DoH ile DNS A kaydı varlığını kontrol et (HTTP yapmaz)
        doh_url = "https://cloudflare-dns.com/dns-query"
        for offset in range(-100, 500, 10):
            num = base_num + offset
            if num <= 0:
                continue
            domain = f"{num}.xyz"
            try:
                r = SESSION.get(
                    doh_url,
                    params={"name": domain, "type": "A"},
                    headers={"accept": "application/dns-json"},
                    timeout=5
                )
                data = r.json()
                if data.get("Answer"):
                    candidates.append(domain)
                    log.debug(f"DNS hit: {domain}")
            except:
                pass
        return candidates

    def _update_checklist_base(self, domain: str):
        """
        Yeni domain'in kaynak kodundan checklist URL'ini çıkarır.
        8602741.xyz → evrenosoglu53.lat/checklist/ gibi değişebilir.
        """
        test_url = f"https://{domain}/event.html?id=androstreamlivebs1"
        try:
            r = SESSION.get(test_url, timeout=TIMEOUT)
            # Kaynak koddan checklist URL'ini bul
            patterns = [
                r'"(https://[^"]+/checklist/)"',
                r"'(https://[^']+/checklist/)'",
                r"(https://\S+/checklist/)(?:[a-z])",
            ]
            for pat in patterns:
                m = re.search(pat, r.text)
                if m:
                    new_base = m.group(1)
                    old_base = self.state.get("checklist_base")
                    if new_base != old_base:
                        log.info(f"📦 Checklist base değişti: {old_base} → {new_base}")
                        self.state["checklist_base"] = new_base
                    return
        except Exception as e:
            log.warning(f"Checklist base güncellenemedi: {e}")

    def find_active_domain(self) -> dict:
        """
        Ana metot: aktif domain'i bulur ve state'i günceller.
        Returns: {"domain": str, "base_url": str, "checklist_base": str, "changed": bool}
        """
        log.info("🔍 Domain kontrolü başlatılıyor...")
        old_domain = self.state.get("current_domain")

        # 1. Mevcut domain hâlâ çalışıyor mu?
        if self._check_current_domain():
            log.info(f"✅ Mevcut domain aktif: {old_domain}")
            self._update_checklist_base(old_domain)
            self._save_state()
            return {"domain": old_domain, "changed": False, **self._get_urls()}

        log.warning(f"⚠️  Mevcut domain yanıt vermiyor: {old_domain} — Yeni domain aranıyor...")

        # 2. Redirect zinciri
        redirected = self._search_redirect_chain()
        if redirected and self._test_domain(redirected):
            return self._set_new_domain(redirected, old_domain)

        # 3. Tracker sayfaları (Telegram, Blog)
        all_candidates = self._search_tracker_pages()

        # 4. Wayback Machine
        all_candidates.extend(self._search_wayback())

        # 5. DNS brute-force (yakın numara aralığı)
        dns_candidates = self._search_dns_bruteforce()
        all_candidates.extend(dns_candidates)

        # En yüksek numaralı (en yeni) domain'i önce test et
        all_candidates = sorted(
            set(all_candidates),
            key=lambda d: int(re.match(r"(\d+)", d).group()) if re.match(r"(\d+)", d) else 0,
            reverse=True
        )
        log.info(f"🔎 Toplam {len(all_candidates)} aday domain test edilecek")

        for candidate in all_candidates:
            if self._test_domain(candidate):
                return self._set_new_domain(candidate, old_domain)

        log.error("❌ Aktif domain bulunamadı! Eski state korunuyor.")
        return {"domain": old_domain, "changed": False, "error": "not_found", **self._get_urls()}

    def _set_new_domain(self, new_domain: str, old_domain: str) -> dict:
        self.state["history"].append({
            "from": old_domain,
            "to": new_domain,
            "at": datetime.now(timezone.utc).isoformat()
        })
        self.state["current_domain"] = new_domain
        self.state["current_base_url"] = f"https://{new_domain}/event.html?id="
        self.state["last_seen"] = datetime.now(timezone.utc).isoformat()
        self._update_checklist_base(new_domain)
        self._save_state()
        log.info(f"🔄 Domain güncellendi: {old_domain} → {new_domain}")
        return {"domain": new_domain, "changed": True, **self._get_urls()}

    def _get_urls(self) -> dict:
        return {
            "base_url": self.state["current_base_url"],
            "checklist_base": self.state["checklist_base"],
        }


if __name__ == "__main__":
    finder = DomainFinder()
    result = finder.find_active_domain()
    print(json.dumps(result, indent=2, ensure_ascii=False))
