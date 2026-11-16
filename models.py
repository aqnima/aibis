from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ScrapeRequest(BaseModel):
    keyword: str = Field(..., description="Kata kunci pencarian, misal: Coffee Shop, Dokter Gigi")
    location: str = Field(..., description="Kota atau area spesifik, misal: Bandung, Wonosobo")
    limit: int = Field(default=20, ge=1, le=200, description="Jumlah target leads yang ingin diambil")
    enrich_website: bool = Field(default=True, description="Apakah ingin mengekstrak email dan sosmed dari website bisnis")

class BusinessLead(BaseModel):
    id: str
    name: str
    category: Optional[str] = "Bisnis"
    phone: Optional[str] = None
    whatsapp_url: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = 0
    price_level: Optional[str] = None  # misal: Rp, Rp Rp, $
    operational_status: Optional[str] = None  # misal: Buka sekarang, Tutup
    address: Optional[str] = "N/A"
    city: Optional[str] = None
    google_maps_url: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

class TaskStatus(BaseModel):
    task_id: str
    status: str  # idle, running, completed, error, stopped
    keyword: str
    location: str
    target_limit: int
    current_count: int = 0
    message: str = ""
    leads: List[BusinessLead] = []
