import asyncio
import json
import sqlite3
import ssl
import httpx
import truststore
import websockets

# Windows sertifika deposunu aktif et (Kurumsal SSL Proxy engeline takılmamak için)
truststore.inject_into_ssl()

SUNUCU_DOMAIN = "rest-zq4l.onrender.com"

SUNUCU_WSS_ADRESI = f"wss://{SUNUCU_DOMAIN}/ws-kopru"
SUNUCU_HTTPS_ADRESI = f"https://{SUNUCU_DOMAIN}/"
GIZLI_ANAHTAR = "Baglantikey_12026!"

TARAYICI_BASLIKLARI = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


# Test için yerel SQLite veritabanı ve örnek kullanıcı (admin / 12345) oluşturur
def yerel_db_hazirla():
    conn = sqlite3.connect("yerel_gizli_db.sqlite")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS kullanicilar (id INTEGER PRIMARY KEY, kadi TEXT, sifre TEXT, rol TEXT)")
    cursor.execute("INSERT OR IGNORE INTO kullanicilar (id, kadi, sifre, rol) VALUES (1, 'admin', '12345', 'Yönetici')")
    conn.commit()
    conn.close()


# Gelen giriş bilgisini yerel veritabanında sorgular
def db_giris_sorgula(kullanici: str, sifre: str) -> dict:
    conn = sqlite3.connect("yerel_gizli_db.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT id, kadi, rol FROM kullanicilar WHERE kadi = ? AND sifre = ?", (kullanici, sifre))
    kayit = cursor.fetchone()
    conn.close()

    if kayit:
        return {
            "basarili": True,
            "veri": {
                "id": kayit[0],
                "kullanici": kayit[1],
                "rol": kayit[2]
            }
        }
    return {"basarili": False}


# 1. Görev: WebSocket bağlantısını canlı tut (20 saniyede bir ping)
async def ws_canli_tut(ws):
    while True:
        await asyncio.sleep(20)
        await ws.send(json.dumps({"tip": "ping"}))


# 2. Görev: Hotspot oturumunun düşmesini engelle (3 dakikada bir normal HTTPS isteği)
async def hotspot_oturum_koru():
    async with httpx.AsyncClient(headers=TARAYICI_BASLIKLARI, timeout=10.0) as client:
        while True:
            await asyncio.sleep(180)
            try:
                yanit = await client.get(SUNUCU_HTTPS_ADRESI, follow_redirects=False)
                if yanit.status_code in (301, 302, 307):
                    print("[UYARI] Wi-Fi Hotspot oturumu düşmüş! Tarayıcıdan giriş yapın.")
                else:
                    print("[*] Web aktivitesi yenilendi (Hotspot oturumu aktif).")
            except Exception as e:
                print(f"[!] Periyodik web kontrolü hatası: {e}")


# Ana Sunucuya Bağlanan İstemci Döngüsü
async def sunucuya_baglan():
    yerel_db_hazirla()

    ws_basliklari = {
        **TARAYICI_BASLIKLARI,
        "Origin": SUNUCU_HTTPS_ADRESI.rstrip("/"),
        "X-API-Secret": GIZLI_ANAHTAR
    }
    ssl_context = ssl.create_default_context()

    # Arka planda Hotspot koruma görevini başlat
    asyncio.create_task(hotspot_oturum_koru())

    while True:
        try:
            print(f"[*] {SUNUCU_WSS_ADRESI} adresine bağlanılıyor...")
            async with websockets.connect(
                SUNUCU_WSS_ADRESI,
                additional_headers=ws_basliklari,
                ssl=ssl_context
            ) as ws:
                print("[+] BAĞLANTI BAŞARILI! Sunucudan gelecek sorgular bekleniyor...")
                ping_gorevi = asyncio.create_task(ws_canli_tut(ws))

                try:
                    async for mesaj_str in ws:
                        istek = json.loads(mesaj_str)
                        if istek.get("islem") == "giris_kontrol":
                            print(f"[>] Sorgu geldi: Kullanıcı = {istek.get('kullanici')}")
                            sonuc = db_giris_sorgula(istek.get("kullanici"), istek.get("sifre"))
                            yanit = {
                                "istek_id": istek.get("istek_id"),
                                **sonuc
                            }
                            await ws.send(json.dumps(yanit))
                            print(f"[<] Yanıt gönderildi: {sonuc}")

                        elif istek.get("islem") == "mesaj_al":
                            gelen = istek.get("metin")
                            print(f"[MESAJ GELDİ]: {gelen}")
                            await ws.send(json.dumps({
                                "istek_id": istek.get("istek_id"),
                                "cevap": f"Alındı: {gelen}"
                            }))
                finally:
                    ping_gorevi.cancel()

        except Exception as hata:
            print(f"[!] Bağlantı kesildi veya kurulamadı: {hata}")
            print("[*] 5 saniye içinde yeniden denenecek...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(sunucuya_baglan())
