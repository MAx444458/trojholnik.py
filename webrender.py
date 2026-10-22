import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()
app = FastAPI()

# SKLAD (Dáta, z ktorých čerpá zákazník aj admin)
sklad = {
    "jablko": (0.5, "ovocie", 10), "banan": (1.2, "ovocie", 5), "hruska": (0.8, "ovocie", 7),
    "slivka": (0.3, "ovocie", 8), "pomaranc": (0.6, "ovocie", 6), "broskyna": (0.9, "ovocie", 5),
    "mrkva": (0.4, "zelenina", 10), "zemiak": (0.2, "zelenina", 20), "petrzlen": (0.5, "zelenina", 5),
    "celer": (0.7, "zelenina", 3), "cokolada": (1.5, "sladkost", 4), "cukor": (1.0, "sladkost", 6),
    "mlieko": (1.3, "ine", 5), "chlieb": (2.0, "ine", 8)
}
kosik = []

# 🔒 Overenie prístupu
def over_admina(credentials: HTTPBasicCredentials = Depends(security)):
    if not (secrets.compare_digest(credentials.username, "admin") and secrets.compare_digest(credentials.password, "Maxpol04")):
        raise HTTPException(status_code=401, detail="Zle udaje", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

# API PRE STRÁNKY
@app.get("/", response_class=HTMLResponse)
def domov(): return HTML_SHOP

@app.get("/api/sklad")
def api_sklad(): return [{"nazov": k, "cena": v[0], "kategoria": v[1], "mnozstvo": v[2]} for k, v in sklad.items()]

@app.post("/api/kosik/pridaj")
def pridaj_do_kosika(data: dict):
    n = data.get("nazov")
    if n not in sklad or sklad[n][2] <= 0: return {"sprava": "Vypredané!"}
    kosik.append(n)
    sklad[n] = (sklad[n][0], sklad[n][1], sklad[n][2] - 1)
    return {"sprava": f"{n} bol pridaný do košíka."}

@app.get("/api/kosik")
def api_kosik(): return {"kosik": [{"nazov": x, "cena": sklad[x][0]} for x in kosik], "suma": round(sum(sklad[x][0] for x in kosik), 2)}

@app.post("/api/kosik/kupon")
def api_kupon(data: dict):
    c = data.get("kupon", "").strip().upper()
    s = sum(sklad[x][0] for x in kosik if x in sklad)
    m = 0.8 if c == "ZLAVA20" else (0.9 if c == "ZLAVA10" else 1.0)
    return {"sprava": "Kupón uplatnený! Nová suma:" if m < 1.0 else "Celková suma:", "suma": round(s * m, 2)}

# API - ODSTRÁNENIE PRODUKTU ZO SKLADU (Pre admin tlačidlo 🗑️)
@app.post("/api/admin/odstran")
def odstran_zo_skladu(data: dict, u: str = Depends(over_admina)):
    n = data.get("nazov")
    if n in sklad:
        del sklad[n]
        return {"sprava": f"Produkt {n} bol odstránený zo skladu."}
    return {"sprava": "Produkt sa nenašiel."}

# 🔒 ZABEZPEČENÝ ADMIN PANEL (Teraz s kompletným načítaním všetkých produktov)
@app.get("/admin", response_class=HTMLResponse)
def admin_panel(u: str = Depends(over_admina)): return HTML_ADMIN

HTML_SHOP = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Obchod</title></head><body style="font-family:Arial; padding:20px;"><h1>🛒 Obchod pre zákazníkov</h1><div id="p">Načítavam produkty...</div><script>async function n(){const o=await fetch("/api/sklad");const s=await o.json();let h="";for(let p of s){h+=`<p><strong>${p.nazov}</strong> - ${p.cena.toFixed(2)} EUR (Sklad: ${p.mnozstvo} ks) <button onclick="add('${p.nazov}')">Pridat</button></p>`;}document.getElementById("p").innerHTML=h;}async function add(n_prod){const o=await fetch("/api/kosik/pridaj",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nazov:n_prod})});const d=await o.json();alert(d.sprava);n();}n();</script></body></html>"""

HTML_ADMIN = """
<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<title>Admin Panel - Správa skladu</title>
<style>
body { font-family: Arial; background: #f9f9f9; margin: 0; padding: 30px; }
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
    <h1>🛠️ Administračný Panel Skladu</h1>
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
    if(confirm("Naozaj chcete zmazať " + nazov + "?")) {
        const o = await fetch("/api/admin/odstran", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({nazov: nazov})});
        const d = await o.json();
        alert(d.sprava);
        nacitajAdminSklad();
    }
}
nacitajAdminSklad();
</script>
</body>
</html>
"""
