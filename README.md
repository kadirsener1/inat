# 📡 iNat TV M3U Otomatik Güncelleyici

inattv1289.xyz sitesinden m3u8 linklerini otomatik bulur ve
playlist.m3u dosyasını akıllıca günceller.

## 📁 Dosya Yapısı

```
inat-tv-m3u/
├── .github/
│   └── workflows/
│       └── update-playlist.yml   ← GitHub Actions iş akışı
├── scraper.py                    ← m3u8 link bulucu
├── updater.py                    ← M3U akıllı güncelleyici
├── main.py                       ← Ana giriş noktası
├── requirements.txt              ← Bağımlılıklar
├── playlist.m3u                  ← 📺 IPTV listesi (otomatik güncellenir)
└── update.log                    ← Son çalışma logu
```

## 🚀 Kurulum (Yerel)

```bash
# 1. Repoyu klonla
git clone https://github.com/KULLANICI_ADIN/inat-tv-m3u.git
cd inat-tv-m3u

# 2. Sanal ortam oluştur (önerilir)
python -m venv venv
source venv/bin/activate          # Linux/Mac
venv\Scripts\activate             # Windows

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. Çalıştır
python main.py

# Tek kanal test
python main.py --channel "BeIN Sports 1"

# Dosyaya yazmadan test
python main.py --dry-run
```

## ⚙️ GitHub Actions Kurulumu

1. Bu repoyu GitHub'a push et.
2. Actions sekmesine gir → "Update iNat TV Playlist" iş akışını etkinleştir.
3. Otomatik: her gün 06:00 ve 18:00 UTC'de çalışır.
4. Manuel: Actions → Run workflow → isteğe bağlı kanal adı gir.

## 📺 IPTV Player'da Kullanım

playlist.m3u dosyasının ham GitHub bağlantısını kopyala:

```
https://raw.githubusercontent.com/KULLANICI/REPO/main/playlist.m3u
```

| Player          | Nasıl Eklenir?                              |
|-----------------|---------------------------------------------|
| VLC             | Medya → Ağ Akışını Aç → URL yapıştır       |
| TiviMate        | Ayarlar → Playlist → + → URL               |
| IPTV Smarters   | Playlist → M3U URL → yapıştır              |
| OTT Navigator   | Genel → M3U Playlist → URL gir             |
| Kodi (IPTV PVR) | PVR IPTV Simple Client → M3U URL           |

## 🔒 Kurallar

- Yalnızca `#SOURCE:inattv1289.xyz` etiketli girişler güncellenir.
- Kendi eklediğin kanallar (etiket olmadan) asla değiştirilmez.
- Sitede artık olmayan kanal M3U'da "uyarı" ile korunur.

## ⚠️ Yasal Uyarı

Bu araç yalnızca eğitim amaçlıdır. Yayın içeriklerinin
telif hakkı sahiplerine aittir. Kendi sorumluluğunuzda kullanınız.
