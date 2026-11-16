import sqlite3
import os
import json
from typing import List, Set, Optional
from datetime import datetime

DB_PATH = os.environ.get("AIBIS_DB_PATH") or os.path.join(os.path.dirname(__file__), "leads_history.db")

def init_db():
    """Inisialisasi tabel SQLite untuk menyimpan leads historis."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraped_leads (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            category TEXT,
            phone TEXT,
            whatsapp_url TEXT,
            website TEXT,
            email TEXT,
            instagram TEXT,
            facebook TEXT,
            rating REAL,
            reviews_count INTEGER,
            operational_status TEXT,
            address TEXT,
            city TEXT,
            keyword TEXT,
            google_maps_url TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_normalized_name ON scraped_leads(normalized_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_city_keyword ON scraped_leads(city, keyword)")
    conn.commit()
    conn.close()

def normalize_text(text: str) -> str:
    """Normalisasi string nama/alamat agar perbandingan duplikasi akurat."""
    if not text:
        return ""
    import re
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return " ".join(cleaned.split())

def get_existing_lead_keys(city: Optional[str] = None, keyword: Optional[str] = None) -> Set[str]:
    """Mengambil daftar nama bisnis unik yang sudah pernah disimpan di database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if city:
        cursor.execute("SELECT normalized_name FROM scraped_leads WHERE city = ?", (city,))
    else:
        cursor.execute("SELECT normalized_name FROM scraped_leads")
    rows = cursor.fetchall()
    conn.close()
    return {row[0] for row in rows if row[0]}

def save_lead_to_db(lead_dict: dict, keyword: str = "", city: str = "") -> bool:
    """Menyimpan 1 lead ke SQLite. Return True jika baru, False jika duplikat."""
    norm_name = normalize_text(lead_dict.get("name", ""))
    if not norm_name:
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if city:
        cursor.execute("SELECT id FROM scraped_leads WHERE normalized_name = ? AND city = ?", (norm_name, city))
    else:
        cursor.execute("SELECT id FROM scraped_leads WHERE normalized_name = ?", (norm_name,))
    exists = cursor.fetchone()
    if exists:
        conn.close()
        return False
        
    cursor.execute("""
        INSERT INTO scraped_leads (
            id, name, normalized_name, category, phone, whatsapp_url,
            website, email, instagram, facebook, rating, reviews_count,
            operational_status, address, city, keyword, google_maps_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead_dict.get("id"),
        lead_dict.get("name"),
        norm_name,
        lead_dict.get("category"),
        lead_dict.get("phone"),
        lead_dict.get("whatsapp_url"),
        lead_dict.get("website"),
        lead_dict.get("email"),
        lead_dict.get("instagram"),
        lead_dict.get("facebook"),
        lead_dict.get("rating"),
        lead_dict.get("reviews_count"),
        lead_dict.get("operational_status"),
        lead_dict.get("address"),
        city,
        keyword,
        lead_dict.get("google_maps_url"),
        lead_dict.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()
    return True

def get_all_saved_leads() -> List[dict]:
    """Mengambil semua leads yang tersimpan di database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_leads ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_total_saved_count() -> int:
    """Menghitung total data unik di database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM scraped_leads")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def delete_single_lead(lead_id: str) -> bool:
    """Menghapus 1 lead tertentu berdasarkan ID dari database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scraped_leads WHERE id = ?", (lead_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def delete_selected_leads(lead_ids: List[str]) -> int:
    """Menghapus sekumpulan leads terpilih berdasarkan list ID."""
    if not lead_ids:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in lead_ids)
    cursor.execute(f"DELETE FROM scraped_leads WHERE id IN ({placeholders})", lead_ids)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def clear_all_leads():
    """Mengosongkan seluruh database riwayat leads."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scraped_leads")
    conn.commit()
    conn.close()
