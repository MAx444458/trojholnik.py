import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()
app = FastAPI()

# SKLAD (Kompletná databáza produktov s integrovanými odkazmi na obrázky z Unsplash)
sklad = {
    "jablko": (0.5, "ovocie", 10, "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400"),
    "banan": (1.2, "ovocie", 5, "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400"),
    "hruska": (0.8, "ovocie", 7, "https://images.unsplash.com/photo-1514756331096-242fdeb70d4a?w=400"),
    "slivka": (0.3, "ovocie", 8, "https://images.unsplash.com/photo-1603186741832-73602d33486c?w=400"),
    "pomaranc": (0.6, "ovocie", 6, "https://images.unsplash.com/photo-1547514701-42782101795e?w=400"),
    "broskyna": (0.9, "ovocie", 5, "https://images.unsplash.com/photo-1595124256660-bf968b820c54?w=400"),
    "mrkva": (0.4, "zelenina", 10, "https://images.unsplash.com/photo-1598170845058-32b9d6a5da37?w=400"),
    "zemiak": (0.2, "zelenina", 20, "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400"),
    "petrzlen": (0.5, "zelenina", 5, "https://images.unsplash.com/photo-1587334206596-f947e90956f1?w=400"),
    "celer": (0.7, "zelenina", 3, "https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?w=400"),
    "cokolada": (1.5, "sladkost", 4, "https://images.unsplash.com/photo-1511381939415-e44015466834?w=400"),
    "cukor": (1.0, "sladkost", 6, "https://images.unsplash.com/photo-1581447101798-2fa5bbd33c8b?w=400"),
    "mlieko": (1.3, "ine", 5, "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400"),
    "chlieb": (2.0, "ine", 8, "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400")
}

kosik = []

# 🔒 Overenie prihlasovacieho mena "admin" a hesla "Maxpol04"
def over_admina(credentials: HTTPBasicCredentials = Depends(security)):
    spravne_meno = secrets.compare_digest(credentials.username, "admin")
    spravne_heslo = secrets.compare_digest(credentials.password, "Maxpol04")
    
    if not (spravne_meno and spravne_heslo):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nesprávne prístupové údaje!",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# 🛒 FRONTEND PRE ZÁKAZNÍKOV (Moderný, plne responzívny Grid dizajn s obrázkami)
@app.get("/", response_class=HTMLResponse)
def domov():
    return HTML_ZAKAZNIK

# API - SKLAD
@app.get("/api/sklad")
def api_sklad():
    vysledok = []
    for nazov, udaje in sklad.items():
        cena, kategoria, mnozstvo, obrazok = udaje
        vysledok.append({
            "nazov": nazov,
            "cena": cena,
            "kategoria": kategoria,
            "mnozstvo": mnozstvo,
            "obrazok": obrazok
        })
    return vysledok

# API - PRIDANIE DO KOŠÍKA
@app.post("/api/kosik/pridaj")
def pridaj_do_kosika(data: dict):
    nazov = data.get("nazov")
    if nazov not in sklad:
        return {"sprava": "Produkt neexistuje."}

    cena, kategoria, mnozstvo, obrazok = sklad[nazov]
    if mnozstvo <= 0:
        return {"sprava": "Produkt je vypredaný."}

    kosik.append(nazov)
    sklad[nazov] = (cena, kategoria, mnozstvo - 1, obrazok)
    return {"sprava": f"{nazov} bol pridaný do košíka."}

# API - KOŠÍK
@app.get("/api/kosik")
def api_kosik():
    produkty = []
    suma = 0
    for nazov in kosik:
        cena, kategoria, mnozstvo, obrazok = sklad[nazov]
        produkty.append({
            "nazov": nazov,
            "cena": cena
        })
        suma += cena
    return {
        "kosik": produkty,
        "suma": round(suma, 2)
    }

# API - KUPÓN (Podpora pre kupóny ZLAVA20 a ZLAVA10)
@app.post("/api/kosik/kupon")
def api_kupon(data: dict):
    kupon = data.get("kupon", "").strip().upper()
    suma = 0
    for nazov in kosik:
        if nazov in sklad:
            suma += sklad[nazov][0]
            
    if kupon == "ZLAVA20":
        return {"sprava": "Kupón -20% uplatnený! Nová suma:", "suma": round(suma * 0.8, 2)}
    elif kupon == "ZLAVA10":
        return {"sprava": "Kupón -10% uplatnený! Nová suma:", "suma": round(suma * 0.9, 2)}
    return {"sprava": "Celková suma:", "suma": round(suma, 2)}

# API - ODSTRÁNENIE PRODUKTU (Pre admina)
@app.post("/api/admin/odstran")
def odstran_zo_skladu(data: dict, u: str = Depends(over_admina)):
    nazov = data.get("nazov")
    if nazov in sklad:
        del sklad[nazov]
        return {"sprava": f"Produkt {nazov} bol odstránený zo skladu."}
    return {"sprava": "Produkt sa nenašiel."}

# 🔒 ZABEZPEČENÝ ADMIN PANEL (Kompletný grafický panel chránený heslom)
@app.get("/admin", response_class=HTMLResponse)
def admin_panel(prihlaseny_uzivatel: str = Depends(over_admina)):
    return HTML_ADMIN


# =====================================================================
# VEĽKÉ HTML ŠABLÓNY S DIZAJNOM (Presunuté na spodok pre čistotu kódu)
# =====================================================================

HTML_ZAKAZNIK = """<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<title>Nákupný systém</title>
<style>
:root {
    --bg-main: #f1f5f9;
    --card-bg: #ffffff;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --text-dark: #1e293b;
    --text-light: #64748b;
}
body {
    font-family: 'Segoe UI', Roboto, Arial, sans-serif;
    background: var(--bg-main);
    color: var(--text-dark);
    margin: 0;
    padding: 30px;
}
h1 {
    text-align: center;
    font-size: 2.5rem;
    font-weight: 800;
    margin-bottom: 40px;
}
.container {
    max-width: 1200px;
    margin: auto;
}
.kategoria {
    background: transparent;
    padding: 0;
    margin-bottom: 40px;
}
.kategoria h2 {
    font-size: 1.5rem;
    border-left: 5px solid var(--primary);
    padding-left: 10px;
    margin-bottom: 20px;
}
.produkty-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}
.produkt {
    background: var(--card-bg);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    padding: 0;
    border: none;
    transition: transform 0.2s, box-shadow 0.2s;
}
.produkt:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
}
.prod-img {
    width: 100%;
    height: 150px;
    object-fit: cover;
    background: #cbd5e1;
}
.prod-info {
    padding: 15px;
    display: flex;
    flex-direction: column;
    flex-grow: 1;
}
.prod-title {
    font-weight: 600;
    font-size: 1.1rem;
    margin-bottom: 10px;
    text-transform: capitalize;
}
.prod-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
}
.cena {
    color: var(--primary);
    font-size: 1.2rem;
    font-weight: 700;
}
.prod-sklad {
    font-size: 0.85rem;
    color: var(--text-light);
}
button {
    width: 100%;
    margin-top: 12px;
    padding: 10px;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    background: var(--primary);
    color: white;
    transition: background 0.2s;
}
button:hover {
    background: var(--primary-hover);
}
#kosik {
    background: var(--card-bg);
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    margin-top: 40px;
}
#kosik h2 {
    margin-top: 0;
}
input {
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    width: 200px;
    margin-right: 10px;
}
.btn-kupon {
    width: auto;
    display: inline-block;
    margin-top: 0;
    padding: 10px 20px;
    background: #1e293b;
}
.btn-kupon:hover {
    background: #334155;
}
</style>
</head>
<body>
<div class="container">
<h1>🛒 NÁKUPNÝ SYSTÉM</h1>
<div id="produkty">Načítavam katalóg produktov...</div>
<div id="kosik">
    <h2>🛍️ Nákupný košík</h2>
    <div id="obsahKosika">Košík je prázdny.</div>
    <h3 id="suma">Celková suma: 0.00 €</h3>
    <input id="kupon" placeholder="Zadaj kupon">
    <button class="btn-kupon" onclick="pouzitKupon()">Použiť kupón</button>
    <h2 id="finalnaSuma"></h2>
</div>
</div>
<script>
let kuponPouzity = false;

async function nacitajSklad() {
    const odpoved = await fetch("/api/sklad");
    const sklad = await odpoved.json();
    let html = "";
    const kategorie = {
        "ovocie": "🍎 Ovocie",
        "zelenina": "🥕 Zelenina",
        "sladkost": "🍫 Sladkosti",
        "ine": "📦 Ostatné"
    };
    for (let kat in kategorie) {
        html += `<div class="kategoria"><h2>${kategorie[kat]}</h2><div class="produkty-grid">`;
        for (let produkt of sklad) {
            if (produkt.kategoria == kat) {
                html += `
                <div class="produkt">
                    <img src="${produkt.obrazok}" class="prod-img" alt="${produkt.nazov}">
                    <div class="prod-info">
                        <div class="prod-title">${produkt.nazov}</div>
                        <div class="prod-meta">
                            <span class="cena">${produkt.cena.toFixed(2)} €</span>
                            <span class="prod-sklad">Sklad: ${produkt.mnozstvo} ks</span>
                        </div>
                        <button onclick="pridaj('${produkt.nazov}')">🛒 Pridať do košíka</button>
                    </div>
                </div>`;
            }
        }
        html += "</div></div>";
    }
    document.getElementById("produkty").innerHTML = html;
}

async function pridaj(nazov) {
    const odpoved = await fetch("/api/kosik/pridaj", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({nazov: nazov})
    });
    const data = await odpoved.json();
    alert(data.sprava);
    nacitajSklad();
    nacitajKosik();
}

async function nacitajKosik() {
    const odpoved = await fetch("/api/kosik");
    const data = await odpoved.json();
    let html = "";
    if (data.kosik.length == 0) {
        html = "Košík je prázdny.";
    } else {
        for (let produkt of data.kosik) {
            html += `<p>✅ ${produkt.nazov} - ${produkt.cena.toFixed(2)} €</p>`;
        }
    }
    document.getElementById("obsahKosika").innerHTML = html;
    document.getElementById("suma").innerText = "Celková suma: " + data.suma.toFixed(2) + " €";
    if (!kuponPouzity) {
        document.getElementById("finalnaSuma").innerText = "";
    }
}

async function pouzitKupon() {
    const kupon = document.getElementById("kupon").value;
    const odpoved = await fetch("/api/kosik/kupon", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({kupon: kupon})
    });
    const data = await odpoved.json();
    document.getElementById("finalnaSuma").innerText = data.sprava + " " + data.suma.toFixed(2) + " €";
    kuponPouzity = true;
}

nacitajSklad();
nacitajKosik();
</script>
</body>
</html>"""

HTML_ADMIN = """<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<title>Admin Panel - Správa skladu</title>
<style>
body { font-family: Arial, sans-serif; background: #f9f9f9; margin: 0; padding: 30px; }
h1 { text-align: center; color: #333; }
.container { max-width: 900px; margin: auto; }
.sklad-box { background: white; padding: 25px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
button { padding: 6px 12px; border: none; border-radius: 6px; cursor: pointer; color: white; font-weight: bold; background: #d9534f; }
button:hover { background: #c9302c; }
.admin-produkt { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #eee; }
</style>
</head>
<body>
<div class="container">
    <h1>🛠️ Administračný Panel Skladu (Chránené verziou 2026)</h1>
    <div class="sklad-box">
        <h2>📦 Aktuálny stav skladu</h2>
        <div id="sklad-zoznam">Načítavam produkty zo skladu...</div>
    </div>
</div>
<script>
async function nacitajAdminSklad() {
    const odpoved = await fetch("/api/sklad");
    const sklad = await odpoved.json();
    let html = "";
    for (let p of sklad) {
        html += `<div class="admin-produkt"><span><strong>${p.nazov}</strong> (${p.kategoria}) - ${p.cena.toFixed(2)} € - sklad: ${p.mnozstvo} ks</span><button onclick="odstranProdukt('${p.nazov}')">🗑️ Odstrániť</button></div>`;
    }
    document.getElementById("sklad-zoznam").innerHTML = html || "<p>Sklad je prázdny.</p>";
}
async function odstranProdukt(nazov) {
    if(confirm("Naozaj chcete zmazať produkt " + nazov + "?")) {
        const o = await fetch("/api/admin/odstran", {
            method: "POST", 
            headers: {"Content-Type": "application/json"}, 
            body: JSON.stringify({nazov: nazov})
        });
        const d = await o.json();
        alert(d.sprava);
        nacitajAdminSklad();
    }
}
nacitajAdminSklad();
</script>
</body>
</html>"""
