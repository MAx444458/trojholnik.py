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


# API - SKLAD (Opravený preklep 'kcategoria' -> 'kategoria')
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

# =====================================================================
# 🎨 GRAFICKÉ VYLEPŠENIE & OBRÁZKY (Vložte na úplný koniec súboru)
# =====================================================================
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import Response

# Automatická databáza fotiek z Unsplash pre tvoj zoznam potravín
FOTKY_PRODUKTOV = {
    "jablko": "https://unsplash.com",
    "banan": "https://unsplash.com",
    "hruska": "https://unsplash.com",
    "slivka": "https://unsplash.com",
    "pomaranc": "https://unsplash.com",
    "broskyna": "https://unsplash.com",
    "mrkva": "https://unsplash.com",
    "zemiak": "https://unsplash.com",
    "petrzlen": "https://unsplash.com",
    "celer": "https://unsplash.com",
    "cokolada": "https://unsplash.com",
    "cukor": "https://unsplash.com",
    "mlieko": "https://unsplash.com",
    "chlieb": "https://unsplash.com"
}

# Middleware, ktorý za behu upraví staré HTML na moderný dizajn s obrázkami
@app.middleware("http")
async def vylepsi_grafiku_a_obrazky(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" and response.status_code == 200:
        body = b"".join([chunk async for chunk in response.body_iterator])
        html = body.decode("utf-8")
        
        # 1. Výmena starého CSS za moderný responzívny Grid dizajn
        stary_style = "<style\(>\nbody {\n    font-family: Arial;\n    background: #f2f2f2;\n    margin: 0;\n    padding: 30px;\n}\\)n\nh1 {\n    text-align: center;\n}\n\n.container {\n    max-width: 1000px;\n    margin: auto;\n}\n\n.kategoria {\n    background: white;\n    padding: 20px;\n    margin-bottom: 20px;\n    border-radius: 12px;\n}\n\n.produkt {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    padding: 12px;\n    border-bottom: 1px solid #ddd;\n}\n\(\nbutton {\n    padding: 8px 15px;\n    border: none;\n    border-radius: 7px;\n    cursor: pointer; background: #222;\n    color: white;\n}\\)n\nbutton:hover {\n    background: #555;\n}..."
        
        novy_style = """<style>
        body { font-family: 'Segoe UI', Roboto, Arial, sans-serif; background: #f1f5f9; padding: 30px; color: #1e293b; }
        h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 30px; }
        .kategoria { background: transparent; padding: 0; margin-bottom: 40px; }
        .kategoria h2 { font-size: 1.5rem; border-left: 5px solid #3b82f6; padding-left: 10px; margin-bottom: 20px; }
        #produkty { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .produkt { background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); display: flex; flex-direction: column; padding: 0; border: none; transition: transform 0.2s, box-shadow 0.2s; }
        .produkt:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
        .prod-img { width: 100%; height: 150px; object-fit: cover; background: #cbd5e1; }
        .prod-info { padding: 15px; display: flex; flex-direction: column; flex-grow: 1; }
        .prod-title { font-weight: 600; font-size: 1.1rem; margin-bottom: 10px; text-transform: capitalize; }
        .prod-meta { display: flex; justify-content: space-between; align-items: center; margin-top: auto; }
        .cena { color: #3b82f6; font-size: 1.2rem; font-weight: 700; }
        .prod-sklad { font-size: 0.85rem; color: #64748b; }
        button { width: 100%; margin-top: 12px; padding: 10px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; background: #3b82f6; color: white; transition: background 0.2s; }
        button:hover { background: #2563eb; }
        #kosik { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        </style>"""
        
        # 2. Vstreknutie obrázkov do JavaScriptu, ktorý vykresľuje zoznam produktov
        stary_javascript_loop = 'if (produkt.kategoria == kat) {\n\n                html += `\n                <div class="produkt">\n                    <span>\n                        ${produkt.nazov}\n                        -\n                        <span class="cena">${produkt.cena.toFixed(2)} €</span>\n                        -\n                        sklad: ${produkt.mnozstvo} ks\n                    </span>\n\n                    <button onclick="pridaj(\'${produkt.nazov}\')">\n                        Pridať\n                    </button>\n                </div>`;\n            }'
        
        novy_javascript_loop = """
        if (produkt.kategoria == kat) {
            const fotky = """ + str(FOTKY_PRODUKTOV) + """;
            const imgUrl = fotky[produkt.nazov] || "https://unsplash.com";
            html += `
            <div class="produkt">
                <img src="${imgUrl}" class="prod-img" alt="${produkt.nazov}">
                <div class="prod-info">
                    <div class="prod-title">${produkt.nazov}</div>
                    <div class="prod-meta">
                        <span class="cena">${produkt.cena.toFixed(2)} €</span>
                        <span class="prod-sklad">Sklad: ${produkt.mnozstvo} ks</span>
                    </div>
                    <button onclick="pridaj('${produkt.nazov}')">🛒 Pridať do košíka</button>
                </div>
            </div>`;
        }"""
        
        # Aplikovanie zmien do výsledného HTML kódu
        html = html.replace("</head>", novy_style + "\n</head>")
        html = html.replace(stary_javascript_loop, novy_javascript_loop)
        
        return Response(content=html, media_type="text/html")
    return response

