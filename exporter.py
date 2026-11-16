import re
from typing import Optional, Tuple
import pandas as pd
from datetime import datetime
import os

def clean_phone_number(raw_phone: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Membersihkan nomor telepon dan membuat link WhatsApp (wa.me).
    Format Indonesia: 0812... -> 62812...
    """
    if not raw_phone:
        return None, None
    
    cleaned = re.sub(r"[^\d+]", "", raw_phone)
    if not cleaned:
        return None, None
    
    digits = re.sub(r"\D", "", cleaned)
    if digits.startswith("0"):
        wa_number = "62" + digits[1:]
    else:
        wa_number = digits
    
    wa_url = f"https://wa.me/{wa_number}" if len(wa_number) >= 9 else None
    return raw_phone.strip(), wa_url

def _build_rows(leads: list) -> list:
    """Satu sumber kebenaran pemetaan kolom ekspor."""
    data = []
    for lead in leads:
        d = lead.model_dump() if hasattr(lead, "model_dump") else dict(lead)
        data.append({
            "Nama Bisnis": d.get("name"),
            "Kategori": d.get("category"),
            "Nomor Telepon": d.get("phone"),
            "WhatsApp Link": d.get("whatsapp_url"),
            "Website Resmi": d.get("website"),
            "Email": d.get("email"),
            "Instagram": d.get("instagram"),
            "Facebook": d.get("facebook"),
            "Rating": d.get("rating"),
            "Jumlah Ulasan": d.get("reviews_count"),
            "Status Operasional": d.get("operational_status"),
            "Alamat Lengkap": d.get("address"),
            "Kota / Area": d.get("city"),
            "Google Maps URL": d.get("google_maps_url"),
            "Waktu Scraping": d.get("created_at")
        })
    return data

def export_to_excel(leads: list, filepath: str) -> str:
    """Ekspor list BusinessLead ke file Excel (.xlsx) rapi dengan formatting."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    df = pd.DataFrame(_build_rows(leads))
    df = df.drop_duplicates(subset=["Nama Bisnis", "Alamat Lengkap"], keep="first")
    
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads B2B")
    
    return filepath

def export_to_csv(leads: list, filepath: str) -> str:
    """Ekspor list BusinessLead ke file CSV."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    df = pd.DataFrame(_build_rows(leads))
    df = df.drop_duplicates(subset=["Nama Bisnis", "Alamat Lengkap"], keep="first")
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath