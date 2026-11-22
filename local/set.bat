@echo off
title Veritabani Baslatma
color 0A

echo ========================================================
echo 1. setup...
echo ========================================================
pip install websockets truststore httpx

echo.
echo ========================================================
echo 2. Kurulum tamamlandi!.
echo ========================================================
python local_render.py

pause
