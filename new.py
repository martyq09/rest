import asyncio
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse

app = FastAPI()

GIZLI_ANAHTAR = "CokGizliBaglantiAnahtari_2026!"

yerel_pc_baglantisi: WebSocket | None = None
bekleyen_istekler: dict[str, asyncio.Future] = {}


@app.websocket("/ws-kopru")
async def websocket_koprusu(websocket: WebSocket):
    global yerel_pc_baglantisi

    if websocket.headers.get("x-api-secret") != GIZLI_ANAHTAR:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    yerel_pc_baglantisi = websocket
    print("[+] Yerel PC tünel bağlantısı kuruldu.")

    try:
        while True:
            mesaj_str = await websocket.receive_text()
            veri = json.loads(mesaj_str)

            if veri.get("tip") == "ping":
                continue

            istek_id = veri.get("istek_id")
            if istek_id and istek_id in bekleyen_istekler:
                future = bekleyen_istekler.pop(istek_id)
                if not future.done():
                    future.set_result(veri)

    except WebSocketDisconnect:
        print("[-] Yerel PC bağlantısı koptu.")
        yerel_pc_baglantisi = None


# Ortak HTML Arayüz Oluşturucu (Sonuç kutusu dahil)
def sayfa_olustur(bildirim: str = "", basarili: bool = True) -> str:
    durum_renk = "green" if yerel_pc_baglantisi else "red"
    durum_yazi = "BAĞLI (Sorguya Hazır)" if yerel_pc_baglantisi else "ÇEVRİMDIŞI (Yerel PC Bekleniyor)"

    bildirim_html = ""
    if bildirim:
        kutu_bg = "#d4edda" if basarili else "#f8d7da"
        kutu_yazi = "#155724" if basarili else "#721c24"
        kutu_border = "#c3e6cb" if basarili else "#f5c6cb"
        bildirim_html = f"""
        <div style="background:{kutu_bg}; color:{kutu_yazi}; border:1px solid {kutu_border}; padding:12px; border-radius:6px; margin-bottom:16px; font-size:14px;">
            {bildirim}
        </div>
        """

    return f"""
    <html>
        <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Köprü Test Paneli</title></head>
        <body style="font-family:sans-serif; max-width:420px; margin:40px auto; padding:20px; border:1px solid #ddd; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
            <h2 style="margin-top:0;">Veritabanı Köprü Testi</h2>
            <p>Yerel PC Durumu: <strong style="color:{durum_renk};">{durum_yazi}</strong></p>
            {bildirim_html}
            <hr>
            <form action="/giris" method="post">
                <label>Kullanıcı Adı:</label><br>
                <input type="text" name="kullanici" placeholder="Örn: admin" required style="width:100%; padding:8px; margin:6px 0 12px 0; box-sizing:border-box;"><br>
                <label>Şifre:</label><br>
                <input type="password" name="sifre" placeholder="Örn: 12345" required style="width:100%; padding:8px; margin:6px 0 16px 0; box-sizing:border-box;"><br>
                <button type="submit" style="width:100%; padding:10px; background:#0066cc; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">Giriş Yap (Yerel DB'den Sor)</button>
            </form>
            <hr style="margin:20px 0;">
            <form action="/mesaj" method="post">
                <label>Yerel PC'ye Mesaj:</label><br>
                <input type="text" name="metin" placeholder="Mesajınızı yazın..." required style="width:100%; padding:8px; margin:6px 0 12px 0; box-sizing:border-box;"><br>
                <button type="submit" style="width:100%; padding:10px; background:#28a745; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:bold;">Mesaj Gönder</button>
            </form>
        </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
async def ana_sayfa():
    return sayfa_olustur()


@app.post("/giris", response_class=HTMLResponse)
async def giris_yap(kullanici: str = Form(...), sifre: str = Form(...)):
    if yerel_pc_baglantisi is None:
        return sayfa_olustur("Hata: Yerel veritabanı bilgisayarı şu an bağlı değil.", basarili=False)

    istek_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    bekleyen_istekler[istek_id] = future

    sorgu_paketi = {
        "istek_id": istek_id,
        "islem": "giris_kontrol",
        "kullanici": kullanici,
        "sifre": sifre
    }

    try:
        await yerel_pc_baglantisi.send_text(json.dumps(sorgu_paketi))
        yanit = await asyncio.wait_for(future, timeout=10.0)

        if yanit.get("basarili"):
            veri = yanit.get("veri", {})
            return sayfa_olustur(f"<strong>Giriş Başarılı!</strong> Hoş geldin {veri.get('kullanici')} (Rol: {veri.get('rol')})", basarili=True)
        else:
            return sayfa_olustur("Giriş Başarısız: Kullanıcı adı veya şifre hatalı.", basarili=False)

    except asyncio.TimeoutError:
        bekleyen_istekler.pop(istek_id, None)
        return sayfa_olustur("Hata: Yerel PC 10 saniye içinde yanıt vermedi.", basarili=False)


@app.post("/mesaj", response_class=HTMLResponse)
async def mesaj_gonder(metin: str = Form(...)):
    if yerel_pc_baglantisi is None:
        return sayfa_olustur("Hata: Yerel bilgisayar şu an bağlı değil.", basarili=False)

    istek_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    bekleyen_istekler[istek_id] = future

    paket = {
        "istek_id": istek_id,
        "islem": "mesaj_al",
        "metin": metin
    }

    try:
        await yerel_pc_baglantisi.send_text(json.dumps(paket))
        yanit = await asyncio.wait_for(future, timeout=10.0)
        return sayfa_olustur(f"<strong>Mesaj İletildi!</strong> Yerel PC Yanıtı: {yanit.get('cevap')}", basarili=True)

    except asyncio.TimeoutError:
        bekleyen_istekler.pop(istek_id, None)
        return sayfa_olustur("Hata: Yerel PC 10 saniye içinde yanıt vermedi.", basarili=False)
