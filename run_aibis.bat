@echo off
title Aibis - Google Maps Lead Engine
cd /d "%~dp0"

echo ========================================================
echo         Aibis - Google Maps B2B Lead Engine
echo ========================================================
echo.

:: Jalankan server FastAPI di background
start /b python app.py

:: Tunggu server siap lalu buka browser
timeout /t 3 /nobreak >nul
start "" http://localhost:8000

echo Server berjalan di http://localhost:8000
echo Tekan Ctrl+C untuk menghentikan.
pause