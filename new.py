import asyncio
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Form
from fastapi.responses import HTMLResponse

app = FastAPI()

# Yerel PC'deki ajan koduyla birebir aynı olmalıdır
GIZLI_ANAHTAR = "CokGizliBaglantiAnahtari_2026!"

yerel_pc_baglantisi: WebSocket | None = None
bekleyen_istekler: dict[str, asyncio.Future] = {}


# 1. Yerel PC'nin bağlanacağı WebSocket Köprüsü
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


# 2. Ana Sayfa ve Test Giriş Formu (Bağlantı durumunu da gösterir)
@app.get("/", response_class=HTMLResponse)
async def ana_sayfa():
    durum_renk = "green" if yerel_pc_baglantisi else "red"
    durum_yazi = "BAĞLI (Sorguya Hazır)" if yerel_pc_baglantisi else "ÇEVRİMDIŞI (Yerel PC Bekleniyor)"

    return f"""
    <html>
        <head><meta charset="utf-8"><title>Köprü Test Paneli</title></head>
        <body style="font-family:sans-serif; max-width:420px; margin:50px auto; padding:20px; border:1px solid #ddd; border-radius:8px;">
            <h2>Veritabanı Köprü Testi</h2>
            <p>Yerel PC Durumu: <strong style="color:{durum_renk};">{durum_yazi}</strong></p>
            <hr>
            <form action="/giris" method="post">
                <label>Kullanıcı Adı:</label><br>
                <input type="text" name="kullanici" placeholder="Örn: admin" required style="width:100%; padding:8px; margin:6px 0 12px 0;"><br>
                <label>Şifre:</label><br>
                <input type="password" name="sifre" placeholder="Örn: 12345" required style="width:100%; padding:8px; margin:6px 0 16px 0;"><br>
                <button type="submit" style="width:100%; padding:10px; background:#0066cc; color:white; border:none; border-radius:4px; cursor:pointer;">Giriş Yap (Yerel DB'den Sor)</button>
            </form>
        </body>
    </html>
    """


# 3. Giriş İsteğini Yerel PC'ye İleten Uç Nokta
@app.post("/giris")
async def giris_yap(kullanici: str = Form(...), sifre: str = Form(...)):
    if yerel_pc_baglantisi is None:
        raise HTTPException(status_code=503, detail="Yerel veritabanı bilgisayarı şu an bağlı değil.")

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
            return {"durum": "Giriş Başarılı!", "yerel_db_yaniti": yanit.get("veri")}
        else:
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı.")

    except asyncio.TimeoutError:
        bekleyen_istekler.pop(istek_id, None)
        raise HTTPException(status_code=504, detail="Yerel PC 10 saniye içinde yanıt vermedi.")
