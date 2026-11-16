"""
Launcher Desktop Native menggunakan PyWebView.
Aplikasi akan terbuka di jendela desktop mandiri (.exe ready) tanpa URL bar browser!
"""
import threading
import time
import webview
import uvicorn
from app import app

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    # Jalankan server backend di background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    # Beri jeda 1 detik agar server siap
    time.sleep(1)
    
    # Buka GUI Native Desktop Window
    window = webview.create_window(
        title="Aibis - Google Maps Lead Engine",
        url="http://127.0.0.1:8000",
        width=1280,
        height=850,
        resizable=True,
        min_size=(900, 600)
    )
    webview.start()
