import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()
app = FastAPI()


# SKLAD
sklad = {
    "jablko": (0.5, "ovocie", 10),
    "banan": (1.2, "ovocie", 5),
    "hruska": (0.8, "ovocie", 7),
    "slivka": (0.3, "ovocie", 8),
    "pomaranc": (0.6, "ovocie", 6),
    "broskyna": (0.9, "ovocie", 5),

    "mrkva": (0.4, "zelenina", 10),
    "zemiak": (0.2, "zelenina", 20),
    "petrzlen": (0.5, "zelenina", 5),
    "celer": (0.7, "zelenina", 3),

    "cokolada": (1.5, "sladkost", 4),
    "cukor": (1.0, "sladkost", 6),

    "mlieko": (1.3, "ine", 5),
    "chlieb": (2.0, "ine", 8)
}

kosik = []


# FRONTEND
@app.get("/", response_class=HTMLResponse)
def domov():
    return """
<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<title>Nákupný systém</title>

<style>
body {
    font-family: Arial;
    background: #f2f2f2;
    margin: 0;
    padding: 30px;
}

h1 {
    text-align: center;
}

.container {
    max-width: 1000px;
    margin: auto;
}

.kategoria {
    background: white;
    padding: 20px;
    margin-bottom: 20px;
    border-radius: 12px;
}

.produkt {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    border-bottom: 1px solid #ddd;
}

button {
    padding: 8px 15px;
    border: none;
    border-radius: 7px;
    cursor: pointer;
    background: #222;
    color: white;
}

button:hover {
    background: #555;
}

#kosik {
    background: white;
    padding: 20px;
    border-radius: 12px;
}

.cena {
    font-weight: bold;
}
</style>
</head>

<body>

<div class="container">

<h1>🛒 NÁKUPNÝ SYSTÉM</h1>

<div id="produkty"></div>

<div id="kosik">
    <h2>🛍️ Nákupný košík</h2>
    <div id="obsahKosika">Košík je prázdny.</div>

    <h3 id="suma">Celková suma: 0.00 €</h3>

    <input id="kupon" placeholder="Zadaj kupon">
    <button onclick="pouzitKupon()">Použiť kupón</button>

    <h2 id="finalnaSuma"></h2>
</div>

</div>


<script>

let kuponPouzity = false;


// načítanie skladu
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

        html += `<div class="kategoria">
                    <h2>${kategorie[kat]}</h2>`;

        for (let produkt of sklad) {

            if (produkt.kategoria == kat) {

                html += `
                <div class="produkt">
                    <span>
                        ${produkt.nazov}
                        -
                        <span class="cena">${produkt.cena.toFixed(2)} €</span>
                        -
                        sklad: ${produkt.mnozstvo} ks
                    </span>

                    <button onclick="pridaj('${produkt.nazov}')">
                        Pridať
                    </button>
                </div>`;
            }
        }

        html += "</div>";
    }

    document.getElementById("produkty").innerHTML = html;
}


// pridanie produktu
async function pridaj(nazov) {

    const odpoved = await fetch("/api/kosik/pridaj", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            nazov: nazov
        })
    });

    const data = await odpoved.json();

    alert(data.sprava);

    nacitajSklad();
    nacitajKosik();
}


// načítanie košíka
async function nacitajKosik() {

    const odpoved = await fetch("/api/kosik");
    const data = await odpoved.json();

    let html = "";

    if (data.kosik.length == 0) {

        html = "Košík je prázdny.";

    } else {

        for (let produkt of data.kosik) {

            html += `
            <p>
                ${produkt.nazov}
                - ${produkt.cena.toFixed(2)} €
            </p>`;
        }
    }

    document.getElementById("obsahKosika").innerHTML = html;

    document.getElementById("suma").innerText =
        "Celková suma: " + data.suma.toFixed(2) + " €";

    if (!kuponPouzity) {
        document.getElementById("finalnaSuma").innerText = "";
    }
}


// kupón
async function pouzitKupon() {

    const kupon = document.getElementById("kupon").value;

    const odpoved = await fetch("/api/kosik/kupon", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            kupon: kupon
        })
    });

    const data = await odpoved.json();

    document.getElementById("finalnaSuma").innerText =
        data.sprava + " " + data.suma.toFixed(2) + " €";

    kuponPouzity = true;
}


// načítanie pri otvorení stránky
nacitajSklad();
nacitajKosik();

</script>

</body>
</html>
"""


# API - SKLAD
@app.get("/api/sklad")
def api_sklad():

    vysledok = []

    for nazov, udaje in sklad.items():

        cena, kategoria, mnozstvo = udaje

        vysledok.append({
            "nazov": nazov,
            "cena": cena,
            "kategoria": kcategoria,
            "mnozstvo": mnozstvo
        })

    return vysledok


# API - PRIDANIE DO KOŠÍKA
@app.post("/api/kosik/pridaj")
def pridaj_do_kosika(data: dict):

    nazov = data["nazov"]

    if nazov not in sklad:
        return {"sprava": "Produkt neexistuje."}

    cena, kategoria, mnozstvo = sklad[nazov]

    if mnozstvo <= 0:
        return {"sprava": "Produkt je vypredaný."}

    kosik.append(nazov)

    sklad[nazov] = (
        cena,
        kategoria,
        mnozstvo - 1
    )

    return {
        "sprava": f"{nazov} bol pridaný do košíka."
    }


# API - KOŠÍK
@app.get("/api/kosik")
def api_kosik():

    produkty = []
    suma = 0

    for nazov in kosik:

        cena, kategoria, mnozstvo = sklad[nazov]

        produkty.append({
            "nazov": nazov,
            "cena": cena
        })

        suma += cena

    return {
        "kosik": produkty,
        "suma": round(suma, 2)
    }


# API - KUPÓN
@app.post("/api/kosik/kupon")
def api_kupon(data: dict):

    kupon = data.get("kupon", "").strip().upper()
    suma = 0
    for nazov in kosik:
        if nazov in sklad:
            suma += sklad[nazov][0]
            
    if kupon == "ZLAVA20":
        return {"sprava": "Kupón uplatnený! Nová suma:", "suma": round(suma * 0.8, 2)}
    elif kupon == "ZLAVA10":
        return {"sprava": "Kupón uplatnený! Nová suma:", "suma": round(suma * 0.9, 2)}
    return {"sprava": "Celková suma:", "suma": round(suma, 2)}


# =====================================================================
# 🔒 ZABEZPEČENÝ ADMIN PANEL
# =====================================================================

# Funkcia, ktorá skontroluje, či si zadal správne meno a heslo Maxpol04
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

# Stránka /admin, ktorá sa otvorí až po správnom zadaní hesla
@app.get("/admin", response_class=HTMLResponse)
def admin_panel(prihlaseny_uzivatel: str = Depends(over_admina)):
    return """
<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<title>Admin Panel - Správa skladu</title>
<style>
body { font-family: Arial; background: #f9f9f9; margin: 0; padding: 30px; }
h1 { text-align: center; color: #333; }
.container { max-width: 900px; margin: auto; }
.admin-box { background: white; padding: 25px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #d9534f; }
.form-skupina { margin-bottom: 15px; }
.form-skupina label { display: inline-block; width: 150px; font-weight: bold; }
.form-skupina input { padding: 8px; width: 250px; border-radius: 6px; border: 1px solid #ccc; }
button { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; color: white; font-weight: bold; background: #5cb85c; }
button:hover { background: #4cae4c; }
</style>
</head>
<body>
<div class="container">
    <h1>🛠️ Administračný Panel Skladu</h1>
    <div class="admin-box">
        <h2>➕ Pridať / Upraviť produkt (Prihlásený admin)</h2>
        <div class="form-skupina"><label>Názov:</label><input type="text" id="nazov"></div>
        <div class="form-skupina"><label>Cena (€):</label><input type="number" step="0.01" id="cena"></div>
        <button onclick="alert('Produkt pripravený na uloženie!')">Uložiť produkt</button>
    </div>
</div>
</body>
</html>
"""

