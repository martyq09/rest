const durumEtiketi = document.getElementById("durum-etiketi");
const bildirimKutusu = document.getElementById("bildirim-kutusu");

function bildirimGoster(mesaj, basariliMi) {
    bildirimKutusu.textContent = mesaj;
    bildirimKutusu.className = basariliMi ? "basarili" : "hata";
}

// Yerel PC'nin bağlı olup olmadığını periyodik kontrol et
async function durumGuncelle() {
    try {
        const res = await fetch("/api/durum");
        const data = await res.json();
        if (data.bagli) {
            durumEtiketi.textContent = "BAĞLI (Sorguya Hazır)";
            durumEtiketi.className = "acik";
        } else {
            durumEtiketi.textContent = "ÇEVRİMDIŞI (Yerel PC Bekleniyor)";
            durumEtiketi.className = "kapali";
        }
    } catch {
        durumEtiketi.textContent = "Sunucuya Ulaşılamıyor";
        durumEtiketi.className = "kapali";
    }
}

// Giriş Formu Gönderimi
document.getElementById("giris-formu").addEventListener("submit", async (e) => {
    e.preventDefault();
    const kullanici = document.getElementById("kullanici").value;
    const sifre = document.getElementById("sifre").value;

    const res = await fetch("/api/giris", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kullanici, sifre })
    });

    const data = await res.json();
    bildirimGoster(res.ok ? data.mesaj : data.detail, res.ok);
});

// Mesaj Formu Gönderimi
document.getElementById("mesaj-formu").addEventListener("submit", async (e) => {
    e.preventDefault();
    const metinInput = document.getElementById("metin");

    const res = await fetch("/api/mesaj", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metin: metinInput.value })
    });

    const data = await res.json();
    bildirimGoster(res.ok ? data.mesaj : data.detail, res.ok);
    if (res.ok) metinInput.value = "";
});

// Sayfa açıldığında ve her 5 saniyede bir durumu kontrol et
durumGuncelle();
setInterval(durumGuncelle, 5000);
