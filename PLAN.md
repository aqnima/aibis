# Implementation Plan: Fullstack Python Lead Generator (FastAPI + Playwright + Tailwind UI)

Aplikasi Web-based All-in-One untuk scraping lead Google Maps. Ringan, cepat, zero node_modules, dan jalan dalam 1 perintah tunggal.

---

## 🎯 Ringkasan Arsitektur Fullstack (Opsi A)

```
[ Browser Client ]
  │  ▲
  │  │  1. HTTP POST: Mulai Scraping (Keyword, Kota, Limit, Enrich toggle)
  │  │  2. HTTP GET /events: Server-Sent Events (SSE) Stream data lead live
  │  │  3. HTTP GET /export/excel: Download .xlsx instan
  ▼  │
[ FastAPI Async Server (app.py) ]
  ├── Static & Jinja2 Templates (Dashboard UI dengan Tailwind CSS & Alpine.js)
  ├── Task Manager (Mengelola background tasks & cancel request)
  ├── Data Store (In-Memory cache & auto-save backup SQLite)
  └── [ Playwright Async Engine (scraper.py) ]
        ├── Chromium Headless Stealth Instance
        ├── Google Maps Feed Scroller (`div[role="feed"]`)
        ├── Detail Extractor (Nama, Telepon, Web, Rating, Alamat)
        └── (Opsional) Web Crawler (Ambil email & sosmed dari domain bisnis)
```

---

## 🗂️ Rincian File yang Akan Dibuat

### 1. `requirements.txt` [NEW]
Daftar dependency Python yang ramping dan cepat:
```txt
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
playwright>=1.48.0
playwright-stealth>=1.0.6
pandas>=2.2.0
openpyxl>=3.1.0
pydantic>=2.9.0
jinja2>=3.1.0
requests>=2.32.0
```

### 2. `models.py` [NEW]
Schema data request dan lead output:
```python
from pydantic import BaseModel
from typing import Optional, List

class ScrapeRequest(BaseModel):
    keyword: str
    location: str
    limit: int = 20
    enrich_website: bool = False

class BusinessLead(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_url: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    address: Optional[str] = None
    google_maps_url: Optional[str] = None
```

### 3. `scraper.py` [NEW]
Async engine Playwright yang terhubung dengan event emitter / callback async:
- Buka Chromium Stealth
- Akses URL Google Maps dengan query `keyword + location`
- Loop scroll container `div[role="feed"]`
- Parse link unik bisnis
- Buka detail dan ekstraksi data esensial
- Emit hasil lead satu per satu secara realtime (generator async)

### 4. `app.py` [NEW]
Backend utama FastAPI:
- `GET /`: Render dashboard HTML
- `POST /api/scrape/start`: Mulai task scraping baru
- `POST /api/scrape/stop`: Hentikan task yang sedang jalan
- `GET /api/scrape/stream`: Stream SSE yang mengirim log & lead baru ke browser secara live
- `GET /api/export/excel`: Download file `.xlsx` dengan format cantik
- `GET /api/export/csv`: Download file `.csv`

### 5. `templates/index.html` [NEW]
Dashboard modern bergaya SaaS:
- Responsive layout (mobile & desktop)
- Metric cards (Total leads, % Ada No HP, % Ada Website, Rata-rata Rating)
- Form input interaktif dengan status indikator
- Progress bar animasi realtime
- Live data table dengan fitur search & filter (All / Punya WA / Punya Web)
- Tombol aksi: "Chat WhatsApp", "Buka Maps", "Buka Web"
- Tombol export: "Download Excel" & "Download CSV"

### 6. `static/js/dashboard.js` [NEW] & `static/css/custom.css` [NEW]
Logika SSE client, state management Alpine/Vanilla JS, dan custom styling.

---

## 🚀 Cara Menjalankan (Pengalaman Pengguna)

King cuma butuh 1 perintah di terminal:
```powershell
python app.py
```
Lalu browser otomatis membuka `http://localhost:8000`. Siap dipakai!

---

## 🧪 Verification Plan

1. **Setup Test:** Install dependencies dan browser Playwright.
2. **Backend & UI Test:** Jalankan `python app.py` dan pastikan server jalan di port 8000.
3. **Smoke Test Scraping:** Masukkan query uji coba (contoh: *"Kopi susu Tebet"*, limit 5) langsung via web UI.
4. **Verifikasi Streaming:** Pastikan baris data muncul satu per satu di tabel secara real-time.
5. **Verifikasi Export:** Download file Excel dan buka untuk memastikan data bersih dan lengkap.
