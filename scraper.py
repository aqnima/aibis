import asyncio
import re
import uuid
import urllib.parse
from typing import AsyncGenerator, Dict, Any, Optional, Tuple
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from models import BusinessLead
from exporter import clean_phone_number
from database import get_existing_lead_keys, normalize_text

import requests
from bs4 import BeautifulSoup

def enrich_from_website(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Mengunjungi website bisnis untuk mencari Email, Instagram, dan Facebook publik.
    Returns: (email, instagram_url, facebook_url)
    """
    if not url:
        return None, None, None
    try:
        if not url.startswith("http"):
            url = "http://" + url
        import ipaddress, socket
        host = urllib.parse.urlparse(url).hostname
        if host:
            try:
                ip = socket.gethostbyname(host)
                if ipaddress.ip_address(ip).is_private:
                    return None, None, None
            except (socket.gaierror, ValueError):
                pass
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=5, stream=True)
        if res.status_code == 200:
            text = ""
            for chunk in res.iter_content(chunk_size=8192):
                text += chunk.decode("utf-8", errors="ignore")
                if len(text) > 2_000_000:
                    break
            soup = BeautifulSoup(text, "html.parser")

            # 1. Cari Email
            email = None
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
            valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css'))]
            if valid_emails:
                email = valid_emails[0]

            # 2. Cari Instagram Link
            instagram = None
            ig_links = soup.find_all("a", href=re.compile(r"instagram\.com/[a-zA-Z0-9_.-]+", re.I))
            for ig in ig_links:
                href = ig.get("href")
                if href and not any(k in href for k in ["/p/", "/reel/", "/explore/"]):
                    instagram = href
                    break

            # 3. Cari Facebook Link
            facebook = None
            fb_links = soup.find_all("a", href=re.compile(r"facebook\.com/[a-zA-Z0-9_.-]+", re.I))
            for fb in fb_links:
                href = fb.get("href")
                if href and not any(k in href for k in ["/sharer/", "/share.php"]):
                    facebook = href
                    break

            return email, instagram, facebook
    except Exception:
        pass
    return None, None, None

class GoogleMapsScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.is_running = True

    def stop(self):
        self.is_running = False

    async def scrape(
        self, keyword: str, location: str, limit: int = 20, enrich_website: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self.is_running = True
        full_query = f"{keyword} di {location}" if location else keyword
        search_url = f"https://www.google.com/maps/search/{urllib.parse.quote(full_query)}"

        yield {"type": "log", "message": f"🚀 Memulai browser engine untuk query: '{full_query}'..."}

        async with async_playwright() as p:
            # Gunakan browser Chromium bawaan sistem (Microsoft Edge / Chrome) atau default Playwright
            try:
                browser = await p.chromium.launch(
                    channel="msedge",
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
            except Exception:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="id-ID",
            )
            page = await context.new_page()
            stealth_sync_obj = Stealth()
            await stealth_sync_obj.apply_stealth_async(page)

            try:
                yield {"type": "log", "message": f"🌐 Mengakses Google Maps..."}
                await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(3)

                feed_selector = 'div[role="feed"]'
                try:
                    await page.wait_for_selector(feed_selector, timeout=12000)
                except Exception:
                    yield {"type": "log", "message": "⚠️ Panel feed list tidak terdeteksi langsung..."}

                # Ambil daftar nama yang sudah pernah tersimpan di database
                existing_names = get_existing_lead_keys(city=location, keyword=keyword)
                if existing_names:
                    yield {"type": "log", "message": f"💾 Ditemukan {len(existing_names)} bisnis yang sudah tersimpan sebelumnya. Sistem akan otomatis melewati (skip) data tersebut."}

                collected_leads = 0
                seen_names = set(existing_names)  # Gabungkan dengan data historis
                scroll_attempts = 0
                max_scroll_attempts = 60

                yield {"type": "log", "message": f"📜 Mulai mengumpulkan target {limit} leads BARU..."}

                while self.is_running and collected_leads < limit and scroll_attempts < max_scroll_attempts:
                    # Ambil semua card artikel dalam feed
                    articles = await page.query_selector_all('div[role="article"]')

                    for art in articles:
                        if not self.is_running or collected_leads >= limit:
                            break

                        # Ambil link place
                        link_elem = await art.query_selector('a[href*="/maps/place/"]')
                        if not link_elem:
                            continue
                        
                        place_url = await link_elem.get_attribute("href")
                        
                        # Parsing data dari teks card feed
                        raw_text = await art.inner_text()
                        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                        if not lines:
                            continue

                        name = lines[0]
                        norm_name = normalize_text(name)
                        if not norm_name or norm_name in seen_names:
                            continue

                        seen_names.add(norm_name)

                        # Inisialisasi atribut lead
                        category = "Bisnis / Toko"
                        rating = None
                        reviews_count = 0
                        address = None
                        phone = None
                        whatsapp_url = None
                        website = None
                        operational_status = None

                        for line in lines[1:]:
                            # Status Operasional (Buka / Tutup)
                            if any(k in line.lower() for k in ["buka", "tutup"]) and not operational_status:
                                operational_status = line.split("·")[0].strip()

                            # Rating & reviews regex: 4,9(1.779) atau 4.8(556)
                            rating_match = re.search(r"(\d+[\.,]\d+)\((\d+[\.,]?\d*)\)", line)
                            if rating_match and not rating:
                                rating = float(rating_match.group(1).replace(",", "."))
                                rev_str = rating_match.group(2).replace(".", "").replace(",", "")
                                reviews_count = int(rev_str)
                                continue

                            # Kategori dan Alamat biasanya ada di baris "Kedai Kopi · Jl. ..."
                            if "·" in line:
                                parts = [p.strip() for p in line.split("·") if p.strip()]
                                if parts:
                                    category = parts[0]
                                    for part in parts[1:]:
                                        phone_match = re.search(r"(\+?62[\d\s-]{8,}|08[\d\s-]{8,})", part)
                                        if phone_match and not phone:
                                            phone, whatsapp_url = clean_phone_number(phone_match.group(1))
                                        elif not address and len(part) > 3 and not any(k in part.lower() for k in ["buka", "tutup"]):
                                            address = part

                            # Deteksi no telp di baris mana pun
                            if not phone:
                                phone_match = re.search(r"(\+?62[\d\s-]{8,}|08[\d\s-]{8,})", line)
                                if phone_match:
                                    phone, whatsapp_url = clean_phone_number(phone_match.group(1))

                        # Buka detail modal/side panel jika nomor telepon atau website belum didapat
                        if not phone or not website:
                            try:
                                await link_elem.scroll_into_view_if_needed()
                                await link_elem.click()
                                await asyncio.sleep(1.2)
                                
                                # Ambil nomor telepon dari tombol panel jika ada
                                phone_btn = await page.query_selector('button[data-tooltip*="Salin nomor telepon"], button[aria-label*="Telepon"]')
                                if phone_btn:
                                    aria_p = await phone_btn.get_attribute("aria-label")
                                    if aria_p:
                                        raw_p = aria_p.replace("Telepon:", "").strip()
                                        phone, whatsapp_url = clean_phone_number(raw_p)

                                # Ambil website jika ada
                                web_btn = await page.query_selector('a[data-tooltip*="Buka situs web"], a[aria-label*="Situs Web"]')
                                if web_btn:
                                    website = await web_btn.get_attribute("href")

                                # Ambil alamat lengkap jika ada
                                addr_btn = await page.query_selector('button[data-tooltip*="Salin alamat"], button[aria-label*="Alamat"]')
                                if addr_btn:
                                    aria_addr = await addr_btn.get_attribute("aria-label")
                                    if aria_addr:
                                        address = aria_addr.replace("Alamat:", "").strip()
                            except Exception:
                                pass
                            finally:
                                # Kembali ke panel feed (kembali ke daftar) agar scraping lanjut
                                try:
                                    back_btn = await page.query_selector('button[aria-label*="Kembali"], button[aria-label*="Back"]')
                                    if back_btn:
                                        await back_btn.click()
                                        await asyncio.sleep(0.5)
                                except Exception:
                                    pass

                        # Auto-enrichment Email, Instagram, Facebook dari Website
                        email, instagram, facebook = None, None, None
                        if enrich_website and website:
                            email, instagram, facebook = await asyncio.to_thread(enrich_from_website, website)

                        lead_data = BusinessLead(
                            id=str(uuid.uuid4())[:8],
                            name=name,
                            category=category,
                            phone=phone,
                            whatsapp_url=whatsapp_url,
                            website=website,
                            email=email,
                            instagram=instagram,
                            facebook=facebook,
                            rating=rating,
                            reviews_count=reviews_count,
                            operational_status=operational_status,
                            address=address or f"{location or 'Indonesia'}",
                            city=location,
                            google_maps_url=place_url,
                        )

                        collected_leads += 1
                        yield {
                            "type": "lead",
                            "lead": lead_data.model_dump(),
                            "current": collected_leads,
                            "target": limit
                        }
                        
                        enrich_info = []
                        if lead_data.phone: enrich_info.append("📞 WA")
                        if lead_data.website: enrich_info.append("🌐 Web")
                        if lead_data.email: enrich_info.append("✉️ Email")
                        if lead_data.instagram: enrich_info.append("📸 IG")
                        tag_str = " | ".join(enrich_info) if enrich_info else "Data Dasar"

                        yield {
                            "type": "log",
                            "message": f"✅ [{collected_leads}/{limit}] Terkumpul: {lead_data.name} ({tag_str})"
                        }

                    # Scroll feed panel ke bawah untuk muat item berikutnya
                    try:
                        feed_panel = await page.query_selector(feed_selector)
                        if feed_panel:
                            await feed_panel.evaluate("el => el.scrollBy(0, 3000)")
                        else:
                            await page.keyboard.press("PageDown")
                    except Exception:
                        await page.keyboard.press("PageDown")

                    scroll_attempts += 1
                    await asyncio.sleep(1.8)

                    # Cek akhir daftar
                    try:
                        feed_text = await feed_panel.inner_text() if feed_panel else ""
                    except Exception:
                        feed_text = ""
                    if "You've reached the end of the list" in feed_text or "Anda telah mencapai akhir daftar" in feed_text:
                        yield {"type": "log", "message": "🏁 Google Maps menandai akhir daftar hasil pencarian."}
                        break

                if not self.is_running:
                    yield {"type": "log", "message": "🛑 Scraping dihentikan."}
                else:
                    yield {"type": "log", "message": f"🎉 Scraping selesai! Berhasil mengumpulkan {collected_leads} leads lengkap."}

            except Exception as e:
                yield {"type": "log", "message": f"❌ Terjadi kesalahan: {str(e)}"}
            finally:
                await browser.close()