import asyncio
import json
import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from models import ScrapeRequest, BusinessLead, TaskStatus
from scraper import GoogleMapsScraper
from exporter import export_to_excel, export_to_csv
from database import (
    init_db,
    save_lead_to_db,
    get_all_saved_leads,
    get_total_saved_count,
    clear_all_leads,
    delete_single_lead,
    delete_selected_leads
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Aibis Lead Engine", lifespan=lifespan)

# Mount Static Files & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global In-Memory State
current_task: Optional[TaskStatus] = None
current_scraper: Optional[GoogleMapsScraper] = None
scraper_lock = asyncio.Lock()
subscribers: List[asyncio.Queue] = []
collected_leads: List[BusinessLead] = []

async def broadcast_event(event: dict):
    """Kirim event ke semua SSE subscriber yang aktif."""
    dead_queues = []
    for q in subscribers:
        try:
            q.put_nowait(event)
        except Exception:
            dead_queues.append(q)
    for q in dead_queues:
        if q in subscribers:
            subscribers.remove(q)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Menampilkan Dashboard Utama."""
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/scrape/status")
async def get_scrape_status():
    """Mengembalikan status task scraping yang sedang berjalan."""
    if current_task is None:
        return {"status": "idle", "current_count": 0, "target_limit": 0, "message": ""}
    return {
        "status": current_task.status,
        "current_count": current_task.current_count,
        "target_limit": current_task.target_limit,
        "message": current_task.message,
        "keyword": current_task.keyword,
        "location": current_task.location,
    }
@app.post("/api/scrape/start")
async def start_scraping(req: ScrapeRequest):
    """Memulai proses scraping di background dengan lock agar tidak bentrok."""
    global current_task, current_scraper, collected_leads
    
    async with scraper_lock:
        if current_scraper:
            current_scraper.stop()
            await asyncio.sleep(0.3)

        collected_leads.clear()
        
        current_task = TaskStatus(
            task_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            status="running",
            keyword=req.keyword,
            location=req.location,
            target_limit=req.limit,
            message="Memulai proses scraping..."
        )
        
        current_scraper = GoogleMapsScraper(headless=True)
        # Jalankan worker langsung sebagai async background task terisolasi
        asyncio.create_task(run_scraper_worker(current_scraper, req))
        
        return {"status": "ok", "message": "Scraping task dimulai"}

async def run_scraper_worker(scraper_instance: GoogleMapsScraper, req: ScrapeRequest):
    """Worker background yang mengeksekusi scraper dan broadcast event."""
    global current_task, collected_leads
    gen = scraper_instance.scrape(
        keyword=req.keyword,
        location=req.location,
        limit=req.limit,
        enrich_website=req.enrich_website
    )
    try:
        async for event in gen:
            # Jika scraper sudah distop, abaikan
            if not scraper_instance.is_running:
                break

            if event["type"] == "lead":
                lead_obj = BusinessLead(**event["lead"])
                # Simpan permanen ke database SQLite historis
                if save_lead_to_db(event["lead"], keyword=req.keyword, city=req.location):
                    collected_leads.append(lead_obj)
                if current_task:
                    current_task.current_count = len(collected_leads)
            
            await broadcast_event(event)

        if current_task and scraper_instance.is_running:
            current_task.status = "completed"
        await broadcast_event({"type": "done"})

    except Exception as e:
        if current_task:
            current_task.status = "error"
            current_task.message = str(e)
        await broadcast_event({"type": "error", "message": str(e)})
    finally:
        # Tutup generator (menjalankan finally: browser.close() di scraper)
        try:
            await gen.aclose()
        except Exception:
            pass

@app.post("/api/scrape/stop")
async def stop_scraping():
    """Menghentikan proses scraping."""
    global current_scraper, current_task
    async with scraper_lock:
        if current_scraper:
            current_scraper.stop()
        if current_task:
            current_task.status = "stopped"
        await broadcast_event({"type": "log", "message": "🛑 Scraping dihentikan atas permintaan pengguna."})
        await broadcast_event({"type": "done"})
        return {"status": "stopped"}

@app.get("/api/scrape/stream")
async def stream_events():
    """Server-Sent Events (SSE) Stream per client connection."""
    client_queue = asyncio.Queue()
    subscribers.append(client_queue)

    async def event_generator():
        try:
            while True:
                event = await client_queue.get()
                data = json.dumps(event)
                yield f"data: {data}\n\n"
                if event.get("type") in ["done", "error"]:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            if client_queue in subscribers:
                subscribers.remove(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/leads/saved")
async def get_saved_leads_endpoint():
    """Mengambil seluruh data riwayat leads yang tersimpan di database."""
    leads = get_all_saved_leads()
    return {"total": len(leads), "leads": leads}

@app.delete("/api/leads/{lead_id}")
async def delete_single_lead_endpoint(lead_id: str):
    """Menghapus 1 lead tertentu dari database & memory."""
    global collected_leads
    deleted = delete_single_lead(lead_id)
    collected_leads = [
        l for l in collected_leads 
        if (l.id != lead_id if hasattr(l, 'id') else l.get('id') != lead_id)
    ]
    return {"status": "ok", "deleted": deleted, "total_saved": get_total_saved_count()}

@app.post("/api/leads/delete-selected")
async def delete_selected_leads_endpoint(req: dict):
    """Menghapus beberapa leads terpilih."""
    global collected_leads
    ids = req.get("ids", [])
    deleted_count = delete_selected_leads(ids)
    return {"status": "ok", "deleted_count": deleted_count, "total_saved": get_total_saved_count()}

@app.post("/api/leads/clear")
async def clear_leads_endpoint():
    """Mengosongkan database riwayat leads."""
    global collected_leads
    clear_all_leads()
    collected_leads.clear()
    return {"status": "ok", "message": "Database riwayat telah dibersihkan", "total_saved": 0}

@app.get("/api/leads/count")
async def get_leads_count():
    """Mendapatkan jumlah data tersimpan di database."""
    return {"total_saved": get_total_saved_count()}
@app.get("/api/export/excel")
async def export_excel(scope: str = "current", background_tasks: BackgroundTasks = None):
    """Download hasil scraping dalam format .xlsx (scope: 'current' atau 'all')."""
    global collected_leads
    leads_to_export = collected_leads if scope == "current" else get_all_saved_leads()
    
    if not leads_to_export:
        raise HTTPException(status_code=404, detail="Tidak ada data leads")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join("output", f"leads_{scope}_{timestamp}.xlsx")
    export_to_excel(leads_to_export, filepath)
    
    if background_tasks is not None:
        background_tasks.add_task(os.remove, filepath)
    
    return FileResponse(
        filepath,
        filename=f"Aibis_Leads_{scope}_{timestamp}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/export/csv")
async def export_csv(scope: str = "current", background_tasks: BackgroundTasks = None):
    """Download hasil scraping dalam format .csv (scope: 'current' atau 'all')."""
    global collected_leads
    leads_to_export = collected_leads if scope == "current" else get_all_saved_leads()
    
    if not leads_to_export:
        raise HTTPException(status_code=404, detail="Tidak ada data leads")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join("output", f"leads_{scope}_{timestamp}.csv")
    export_to_csv(leads_to_export, filepath)
    
    if background_tasks is not None:
        background_tasks.add_task(os.remove, filepath)
    
    return FileResponse(
        filepath,
        filename=f"Aibis_Leads_{scope}_{timestamp}.csv",
        media_type="text/csv"
    )

if __name__ == "__main__":
    print("🚀 Menjalankan Aibis Lead Engine di http://localhost:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
