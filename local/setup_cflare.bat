@echo off
title Veritabani Baslatma
color 0A

echo ========================================================
echo 1. setup...
echo ========================================================
pip install websockets truststore httpx

echo.
echo ========================================================
echo 2. Kurulum tamamlandi! baslatiliyor...
echo ========================================================
python local_cflare.py

pause
