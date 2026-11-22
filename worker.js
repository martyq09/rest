import { DurableObject } from "cloudflare:workers";

const GIZLI_ANAHTAR = "Baglantikey_12026!";

export class KopruOdasi extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.bekleyenIstekler = new Map();
  }

  async fetch(request) {
    const url = new URL(request.url);

    // 1. Yerel PC'nin WebSocket bağlantısı
    if (url.pathname === "/ws-kopru") {
      if (request.headers.get("x-api-secret") !== GIZLI_ANAHTAR) {
        return new Response("Yetkisiz", { status: 401 });
      }
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);

      // Varsa eski bağlantıyı kapat, yenisini kabul et
      this.ctx.getWebSockets().forEach(ws => ws.close(1000, "Yeni baglanti"));
      this.ctx.acceptWebSocket(server);

      return new Response(null, { status: 101, webSocket: client });
    }

    // 2. Yerel PC durum kontrolü
    if (url.pathname === "/api/durum") {
      const bagli = this.ctx.getWebSockets().length > 0;
      return Response.json({ bagli });
    }

    // 3. Giriş ve Mesaj API istekleri
    if (url.pathname === "/api/giris" || url.pathname === "/api/mesaj") {
      const soketler = this.ctx.getWebSockets();
      if (soketler.length === 0) {
        return Response.json({ detail: "Yerel bilgisayar şu an çevrimdışı." }, { status: 503 });
      }

      const govde = await request.json();
      const istekId = crypto.randomUUID();
      const paket = url.pathname === "/api/giris"
        ? { istek_id: istekId, islem: "giris_kontrol", kullanici: govde.kullanici, sifre: govde.sifre }
        : { istek_id: istekId, islem: "mesaj_al", metin: govde.metin };

      return new Promise((resolve) => {
        const zamanAsimi = setTimeout(() => {
          this.bekleyenIstekler.delete(istekId);
          resolve(Response.json({ detail: "Yerel PC 10 saniye içinde yanıt vermedi." }, { status: 504 }));
        }, 10000);

        this.bekleyenIstekler.set(istekId, (yanit) => {
          clearTimeout(zamanAsimi);
          if (url.pathname === "/api/giris") {
            if (yanit.basarili) {
              resolve(Response.json({ mesaj: `Hoş geldin ${yanit.veri.kullanici} (${yanit.veri.rol})` }));
            } else {
              resolve(Response.json({ detail: "Kullanıcı adı veya şifre hatalı." }, { status: 401 }));
            }
          } else {
            resolve(Response.json({ mesaj: yanit.cevap }));
          }
        });

        soketler[0].send(JSON.stringify(paket));
      });
    }

    return new Response("Bulunamadı", { status: 404 });
  }

  // Yerel PC'den gelen WebSocket mesajlarını yakala
  async webSocketMessage(ws, message) {
    const veri = JSON.parse(message);
    if (veri.tip === "ping") return;
    const cozucu = this.bekleyenIstekler.get(veri.istek_id);
    if (cozucu) {
      this.bekleyenIstekler.delete(veri.istek_id);
      cozucu(veri);
    }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/ws-kopru" || url.pathname.startsWith("/api/")) {
      const id = env.KOPRU.idFromName("tek-kopru");
      return env.KOPRU.get(id).fetch(request);
    }
    // Diğer tüm isteklerde static/ klasöründeki index.html, style.css, app.js dosyalarını sun
    return env.ASSETS.fetch(request);
  }
};
