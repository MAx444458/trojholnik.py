"""
E-SHOP (FastAPI)

Spustenie na počítači:
    pip install fastapi uvicorn
    uvicorn webrender:app --reload

Render – Start Command:
    uvicorn webrender:app --host 0.0.0.0 --port $PORT

Obchod: /        Admin: /admin   (meno: admin, heslo: Maxpol04)
"""

import json
import os
import re
import secrets
import threading
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()
app = FastAPI()

# 🔒 Prihlásenie do /admin
ADMIN_MENO = "admin"
ADMIN_HESLO = "Maxpol04"
DATA_SUBOR = Path(__file__).with_name("data.json")   # sem sa ukladá sklad, kupóny a objednávky
zamok = threading.RLock()

# SKLAD (názov: cena v €, kategória, počet kusov, obrázok)
sklad = {
    "jablko": {"cena": 0.5, "kategoria": "ovocie", "mnozstvo": 10, "obrazok": "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400"},
    "banan": {"cena": 1.2, "kategoria": "ovocie", "mnozstvo": 5, "obrazok": "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400"},
    "hruska": {"cena": 0.8, "kategoria": "ovocie", "mnozstvo": 7, "obrazok": "https://images.unsplash.com/photo-1514756331096-242fdeb70d4a?w=400"},
    "slivka": {"cena": 0.3, "kategoria": "ovocie", "mnozstvo": 8, "obrazok": "https://images.unsplash.com/photo-1603186741832-73602d33486c?w=400"},
    "pomaranc": {"cena": 0.6, "kategoria": "ovocie", "mnozstvo": 6, "obrazok": "https://images.unsplash.com/photo-1547514701-42782101795e?w=400"},
    "broskyna": {"cena": 0.9, "kategoria": "ovocie", "mnozstvo": 5, "obrazok": "https://images.unsplash.com/photo-1595124256660-bf968b820c54?w=400"},
    "mrkva": {"cena": 0.4, "kategoria": "zelenina", "mnozstvo": 10, "obrazok": "https://images.unsplash.com/photo-1598170845058-32b9d6a5da37?w=400"},
    "zemiak": {"cena": 0.2, "kategoria": "zelenina", "mnozstvo": 20, "obrazok": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400"},
    "petrzlen": {"cena": 0.5, "kategoria": "zelenina", "mnozstvo": 5, "obrazok": "https://images.unsplash.com/photo-1587334206596-f947e90956f1?w=400"},
    "celer": {"cena": 0.7, "kategoria": "zelenina", "mnozstvo": 3, "obrazok": "https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?w=400"},
    "cokolada": {"cena": 1.5, "kategoria": "sladkost", "mnozstvo": 4, "obrazok": "https://images.unsplash.com/photo-1511381939415-e44015466834?w=400"},
    "cukor": {"cena": 1.0, "kategoria": "sladkost", "mnozstvo": 6, "obrazok": "https://images.unsplash.com/photo-1581447101798-2fa5bbd33c8b?w=400"},
    "mlieko": {"cena": 1.3, "kategoria": "ine", "mnozstvo": 5, "obrazok": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400"},
    "chlieb": {"cena": 2.0, "kategoria": "ine", "mnozstvo": 8, "obrazok": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400"},
}

kupony = {"ZLAVA10": 10, "ZLAVA20": 20}   # kód: zľava v %
objednavky = []
kosiky = {}   # každý zákazník má vlastný košík: id -> {"polozky": {názov: kusy}, "kupon": kód}


# =====================================================================
# POMOCNÉ FUNKCIE
# =====================================================================

def uloz():
    """Uloží sklad, kupóny a objednávky do data.json (prežijú reštart servera)."""
    try:
        DATA_SUBOR.write_text(
            json.dumps({"sklad": sklad, "kupony": kupony, "objednavky": objednavky}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    except OSError:
        pass


def nacitaj():
    if not DATA_SUBOR.exists():
        return
    try:
        d = json.loads(DATA_SUBOR.read_text(encoding="utf-8"))
        sklad.clear(); sklad.update(d["sklad"])
        kupony.clear(); kupony.update(d["kupony"])
        objednavky[:] = d["objednavky"]
    except (OSError, ValueError, KeyError):
        pass


nacitaj()


def eura(x) -> Decimal:
    """Zaokrúhli sumu na 2 desatinné miesta (0,005 -> 0,01)."""
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def chyba(text, kod=400):
    raise HTTPException(status_code=kod, detail=text)


def cele_cislo(hodnota, nazov, minimum=0, maximum=100000):
    try:
        n = int(str(hodnota).strip())
    except (TypeError, ValueError):
        chyba(f"{nazov} musí byť celé číslo.")
    if not minimum <= n <= maximum:
        chyba(f"{nazov} musí byť od {minimum} do {maximum}.")
    return n


def cena_z_textu(hodnota):
    try:
        c = eura(str(hodnota).replace(",", ".").replace("€", "").strip())
    except InvalidOperation:
        chyba("Cena musí byť číslo, napr. 1,29.")
    if not c.is_finite() or c < 0 or c > 100000:
        chyba("Cena musí byť od 0 do 100 000 €.")
    return float(c)


def teraz():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Bratislava")).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return datetime.now().strftime("%d.%m.%Y %H:%M")


# 🔒 Overenie prihlasovacieho mena a hesla
def over_admina(credentials: HTTPBasicCredentials = Depends(security)):
    spravne_meno = secrets.compare_digest(credentials.username.encode(), ADMIN_MENO.encode())
    spravne_heslo = secrets.compare_digest(credentials.password.encode(), ADMIN_HESLO.encode())
    if not (spravne_meno and spravne_heslo):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nesprávne prístupové údaje!",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# 🛒 Košík zákazníka (podľa cookie, aby mal každý svoj)
def ziskaj_kosik(request: Request, response: Response):
    kid = request.cookies.get("kosik_id")
    with zamok:
        if not kid or kid not in kosiky:
            if len(kosiky) > 5000:   # upratanie prázdnych košíkov
                for k in [k for k, v in kosiky.items() if not v["polozky"]]:
                    del kosiky[k]
            kid = secrets.token_urlsafe(16)
            kosiky[kid] = {"polozky": {}, "kupon": None}
        kosik = kosiky[kid]
    response.set_cookie("kosik_id", kid, max_age=30 * 24 * 3600, httponly=True, samesite="lax")
    return kosik


def stav_kosika(kosik):
    polozky, suma, upozornenia = [], Decimal("0"), []
    for nazov, kusy in list(kosik["polozky"].items()):
        p = sklad.get(nazov)
        if not p or p["mnozstvo"] <= 0:
            del kosik["polozky"][nazov]
            upozornenia.append(f"{nazov} už nie je na sklade, odstránili sme ho z košíka.")
            continue
        if kusy > p["mnozstvo"]:
            kusy = kosik["polozky"][nazov] = p["mnozstvo"]
            upozornenia.append(f"{nazov}: na sklade je už len {kusy} ks, upravili sme počet.")
        spolu = eura(p["cena"]) * kusy
        suma += spolu
        polozky.append({"nazov": nazov, "cena": p["cena"], "kusy": kusy, "mnozstvo": p["mnozstvo"],
                        "obrazok": p["obrazok"], "spolu": float(spolu)})

    if kosik["kupon"] and kosik["kupon"] not in kupony:
        kosik["kupon"] = None
    percenta = kupony.get(kosik["kupon"], 0) if kosik["kupon"] else 0
    zlava = eura(suma * percenta / 100)
    return {
        "polozky": polozky,
        "pocet": sum(p["kusy"] for p in polozky),
        "suma": float(suma),
        "kupon": kosik["kupon"],
        "percenta": percenta,
        "zlava": float(zlava),
        "spolu": float(suma - zlava),
        "upozornenia": upozornenia,
    }


# =====================================================================
# OBCHOD PRE ZÁKAZNÍKOV
# =====================================================================

@app.get("/", response_class=HTMLResponse)
def domov():
    return HTML_ZAKAZNIK


# API - SKLAD
@app.get("/api/sklad")
def api_sklad():
    with zamok:
        return [{"nazov": nazov, **udaje} for nazov, udaje in sklad.items()]


# API - KOŠÍK
@app.get("/api/kosik")
def api_kosik(kosik: dict = Depends(ziskaj_kosik)):
    with zamok:
        return stav_kosika(kosik)


# API - PRIDANIE DO KOŠÍKA (aj viac kusov naraz)
@app.post("/api/kosik/pridaj")
def pridaj_do_kosika(data: dict, kosik: dict = Depends(ziskaj_kosik)):
    nazov = str(data.get("nazov", ""))
    kusy = cele_cislo(data.get("kusy", 1), "Počet kusov", 1, 999)
    with zamok:
        if nazov not in sklad:
            chyba("Produkt neexistuje.", 404)
        na_sklade = sklad[nazov]["mnozstvo"]
        v_kosiku = kosik["polozky"].get(nazov, 0)
        if na_sklade <= 0:
            chyba("Produkt je vypredaný.")
        if v_kosiku + kusy > na_sklade:
            chyba(f"Na sklade je len {na_sklade} ks (v košíku už máš {v_kosiku} ks).")
        kosik["polozky"][nazov] = v_kosiku + kusy
        vysledok = stav_kosika(kosik)
    vysledok["sprava"] = f"{nazov} ({kusy} ks) bol pridaný do košíka."
    return vysledok


# API - ZMENA POČTU KUSOV V KOŠÍKU (0 = odstrániť)
@app.post("/api/kosik/nastav")
def nastav_kusy(data: dict, kosik: dict = Depends(ziskaj_kosik)):
    nazov = str(data.get("nazov", ""))
    kusy = cele_cislo(data.get("kusy", 0), "Počet kusov", 0, 999)
    with zamok:
        if kusy == 0:
            kosik["polozky"].pop(nazov, None)
        else:
            if nazov not in sklad:
                chyba("Produkt neexistuje.", 404)
            if kusy > sklad[nazov]["mnozstvo"]:
                chyba(f"Na sklade je len {sklad[nazov]['mnozstvo']} ks.")
            kosik["polozky"][nazov] = kusy
        return stav_kosika(kosik)


# API - KUPÓN (prázdny kód = zrušiť kupón)
@app.post("/api/kosik/kupon")
def api_kupon(data: dict, kosik: dict = Depends(ziskaj_kosik)):
    kod = str(data.get("kupon", "")).strip().upper()
    with zamok:
        if kod and kod not in kupony:
            chyba("Neplatný zľavový kód.")
        kosik["kupon"] = kod or None
        vysledok = stav_kosika(kosik)
        vysledok["sprava"] = f"Kupón {kod} (-{kupony[kod]} %) uplatnený!" if kod else "Kupón bol zrušený."
    return vysledok


# API - OBJEDNÁVKA
@app.post("/api/objednat")
def objednat(data: dict, kosik: dict = Depends(ziskaj_kosik)):
    meno = str(data.get("meno", "")).strip()[:100]
    telefon = str(data.get("telefon", "")).strip()[:30]
    adresa = str(data.get("adresa", "")).strip()[:300]
    if len(meno) < 2:
        chyba("Zadaj meno a priezvisko.")
    if len(adresa) < 5:
        chyba("Zadaj adresu doručenia.")
    with zamok:
        stav = stav_kosika(kosik)
        if stav["upozornenia"]:
            chyba("Košík sa medzitým zmenil (sklad). Skontroluj ho a objednaj znova.", 409)
        if not stav["polozky"]:
            chyba("Košík je prázdny.")
        for p in stav["polozky"]:
            sklad[p["nazov"]]["mnozstvo"] -= p["kusy"]
        cislo = objednavky[-1]["cislo"] + 1 if objednavky else 1
        objednavky.append({
            "cislo": cislo, "cas": teraz(), "meno": meno, "telefon": telefon, "adresa": adresa,
            "polozky": [{"nazov": p["nazov"], "cena": p["cena"], "kusy": p["kusy"]} for p in stav["polozky"]],
            "suma": stav["suma"], "kupon": stav["kupon"], "zlava": stav["zlava"], "spolu": stav["spolu"],
        })
        kosik["polozky"].clear()
        kosik["kupon"] = None
        uloz()
    return {"cislo": cislo, "spolu": stav["spolu"]}


# =====================================================================
# 🔒 ADMIN (chránený menom a heslom)
# =====================================================================

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(prihlaseny_uzivatel: str = Depends(over_admina)):
    return HTML_ADMIN


@app.get("/api/admin/data")
def admin_data(u: str = Depends(over_admina)):
    with zamok:
        return {
            "sklad": [{"nazov": n, **p} for n, p in sklad.items()],
            "kupony": [{"kod": k, "percenta": v} for k, v in kupony.items()],
            "objednavky": list(reversed(objednavky)),
        }


# API - PRIDANIE / ÚPRAVA PRODUKTU
@app.post("/api/admin/produkt")
def admin_uloz_produkt(data: dict, u: str = Depends(over_admina)):
    nazov = str(data.get("nazov", "")).strip()
    povodny = str(data.get("povodny_nazov", "")).strip()
    if not 1 <= len(nazov) <= 60:
        chyba("Názov musí mať 1 až 60 znakov.")
    cena = cena_z_textu(data.get("cena"))
    kategoria = str(data.get("kategoria", "ine")).strip().lower()[:30] or "ine"
    mnozstvo = cele_cislo(data.get("mnozstvo", 0), "Počet kusov", 0, 100000)
    obrazok = str(data.get("obrazok", "")).strip()[:500]
    if obrazok and not obrazok.startswith(("http://", "https://")):
        chyba("Obrázok musí byť odkaz, ktorý začína https://")
    with zamok:
        if povodny and povodny not in sklad:
            chyba("Upravovaný produkt už neexistuje.", 404)
        if nazov != povodny and nazov in sklad:
            chyba("Produkt s takým názvom už existuje.")
        if povodny and povodny != nazov:   # premenovanie – presunie sa aj v košíkoch
            del sklad[povodny]
            for k in kosiky.values():
                if povodny in k["polozky"]:
                    k["polozky"][nazov] = k["polozky"].pop(povodny)
        sklad[nazov] = {"cena": cena, "kategoria": kategoria, "mnozstvo": mnozstvo, "obrazok": obrazok}
        uloz()
    return {"sprava": f"Produkt {nazov} bol {'upravený' if povodny else 'pridaný'}."}


# API - ODSTRÁNENIE PRODUKTU
@app.post("/api/admin/odstran")
def odstran_zo_skladu(data: dict, u: str = Depends(over_admina)):
    nazov = data.get("nazov")
    with zamok:
        if nazov in sklad:
            del sklad[nazov]
            uloz()
            return {"sprava": f"Produkt {nazov} bol odstránený zo skladu."}
    chyba("Produkt sa nenašiel.", 404)


# API - ZĽAVOVÉ KÓDY
@app.post("/api/admin/kupon")
def admin_pridaj_kupon(data: dict, u: str = Depends(over_admina)):
    kod = str(data.get("kod", "")).strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,20}", kod):
        chyba("Kód musí mať 3 až 20 znakov (písmená A–Z, čísla, - a _).")
    percenta = cele_cislo(data.get("percenta"), "Zľava v %", 1, 100)
    with zamok:
        kupony[kod] = percenta
        uloz()
    return {"sprava": f"Kód {kod} (-{percenta} %) bol uložený."}


@app.post("/api/admin/kupon/odstran")
def admin_odstran_kupon(data: dict, u: str = Depends(over_admina)):
    with zamok:
        kupony.pop(str(data.get("kod", "")), None)
        uloz()
    return {"sprava": "Kód bol odstránený."}


# =====================================================================
# HTML ŠABLÓNY (na spodku pre čistotu kódu)
# =====================================================================

HTML_ZAKAZNIK = r"""<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nákupný systém</title>
<style>
:root {
    --bg-main: #f1f5f9;
    --card-bg: #ffffff;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --text-dark: #1e293b;
    --text-light: #64748b;
    --cervena: #dc2626;
    --zelena: #16a34a;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
    font-family: 'Segoe UI', Roboto, Arial, sans-serif;
    background: var(--bg-main);
    color: var(--text-dark);
    margin: 0;
    padding: 30px 16px 90px;
}
h1 { text-align: center; font-size: clamp(1.8rem, 5vw, 2.5rem); font-weight: 800; margin-bottom: 40px; }
.container { max-width: 1200px; margin: auto; }
.kategoria { margin-bottom: 40px; }
.kategoria h2 { font-size: 1.5rem; border-left: 5px solid var(--primary); padding-left: 10px; margin-bottom: 20px; }
.produkty-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
.produkt {
    background: var(--card-bg); border-radius: 16px; overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); display: flex; flex-direction: column;
    transition: transform 0.2s, box-shadow 0.2s;
}
.produkt:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
.prod-img { width: 100%; height: 160px; object-fit: cover; background: #cbd5e1; display: block; }
.prod-info { padding: 15px; display: flex; flex-direction: column; flex-grow: 1; }
.prod-title { font-weight: 600; font-size: 1.1rem; margin-bottom: 10px; }
.prod-title::first-letter, .riadok-nazov strong::first-letter { text-transform: uppercase; }
.prod-meta { display: flex; justify-content: space-between; align-items: center; margin-top: auto; gap: 8px; }
.cena { color: var(--primary); font-size: 1.2rem; font-weight: 700; }
.prod-sklad { font-size: 0.85rem; color: var(--text-light); }
.prod-sklad.vypredane { color: var(--cervena); font-weight: 600; }
button {
    padding: 10px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;
    background: var(--primary); color: white; transition: background 0.2s; font: inherit; font-weight: 600;
}
button:hover:not(:disabled) { background: var(--primary-hover); }
button:disabled { background: #cbd5e1; color: var(--text-light); cursor: not-allowed; }
.pridat { display: flex; gap: 8px; margin-top: 12px; }
.pridat input { width: 64px; text-align: center; }
.pridat button { flex: 1; }
.prod-info > button { width: 100%; margin-top: 12px; }
input {
    padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; font: inherit; min-width: 0;
}
input:focus { outline: 2px solid var(--primary); border-color: transparent; }
#kosik {
    background: var(--card-bg); padding: 25px; border-radius: 16px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-top: 40px; scroll-margin-top: 20px;
}
#kosik h2 { margin-top: 0; }
.riadok {
    display: grid; grid-template-columns: 56px 1fr auto 90px 36px; gap: 12px; align-items: center;
    padding: 12px 0; border-bottom: 1px solid #e2e8f0;
}
.riadok img { width: 56px; height: 56px; object-fit: cover; border-radius: 10px; background: #cbd5e1; }
.riadok-nazov { display: flex; flex-direction: column; }
.riadok-nazov span { color: var(--text-light); font-size: 0.85rem; }
.riadok-suma { text-align: right; white-space: nowrap; }
.pocet { display: flex; align-items: center; gap: 8px; }
.pocet span { min-width: 24px; text-align: center; font-weight: 700; }
button.male { width: 32px; height: 32px; padding: 0; background: #e2e8f0; color: var(--text-dark); }
button.male:hover:not(:disabled) { background: #cbd5e1; }
button.odstranit { color: var(--cervena); background: #fee2e2; }
button.odstranit:hover:not(:disabled) { background: #fecaca; }
.upozornenie { background: #fef3c7; color: #92400e; padding: 10px 14px; border-radius: 8px; margin: 10px 0; }
.sumar { margin: 20px 0; }
.sumar p { margin: 6px 0; display: flex; justify-content: space-between; max-width: 360px; }
#zlava { color: var(--zelena); font-weight: 600; }
#finalnaSuma { font-size: 1.5rem; margin: 24px 0 20px; }
.kupon-riadok { display: flex; gap: 10px; flex-wrap: wrap; }
.kupon-riadok input { width: 200px; text-transform: uppercase; }
.btn-kupon { background: #1e293b; padding: 10px 20px; }
.btn-kupon:hover:not(:disabled) { background: #334155; }
#objednavka { margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 20px; }
#objednavka h3 { margin-top: 0; }
.formular { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 640px; }
.formular label { display: grid; gap: 6px; font-weight: 600; font-size: 0.9rem; }
.formular .siroke { grid-column: 1 / -1; }
.btn-objednat { grid-column: 1 / -1; background: var(--zelena); padding: 14px; font-size: 1.05rem; }
.btn-objednat:hover:not(:disabled) { background: #15803d; }
#potvrdenie { background: #dcfce7; color: #166534; padding: 16px; border-radius: 12px; font-weight: 600; }
#plavajuci {
    position: fixed; right: 20px; bottom: 20px; z-index: 10; text-decoration: none;
    background: var(--text-dark); color: #fff; padding: 14px 20px; border-radius: 999px;
    font-weight: 700; box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}
#plavajuci.bump { animation: bump .35s; }
@keyframes bump { 50% { transform: scale(1.12); } }
#sprava {
    position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 20;
    background: var(--text-dark); color: #fff; padding: 12px 20px; border-radius: 10px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2); max-width: calc(100% - 32px);
}
#sprava.chyba { background: var(--cervena); }
@media (max-width: 640px) {
    .produkty-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
    .pridat { flex-direction: column; }
    .pridat input { width: 100%; }
    .riadok { grid-template-columns: 48px 1fr 36px; }
    .riadok img { width: 48px; height: 48px; }
    .pocet { grid-column: 2; }
    .riadok-suma { grid-column: 3; grid-row: 2; }
    .riadok .odstranit { grid-column: 3; grid-row: 1; }
    .formular { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="container">
<h1>🛒 NÁKUPNÝ SYSTÉM</h1>
<div id="produkty">Načítavam katalóg produktov...</div>
<div id="kosik">
    <h2>🛍️ Nákupný košík</h2>
    <div id="upozornenia"></div>
    <div id="obsahKosika">Košík je prázdny.</div>
    <div class="sumar">
        <p><span>Celková suma:</span> <strong id="suma">0,00 €</strong></p>
        <p id="zlavaRiadok" hidden><span id="zlavaText"></span> <span id="zlava"></span></p>
    </div>
    <div class="kupon-riadok">
        <input id="kupon" placeholder="Zadaj kupón" maxlength="20">
        <button class="btn-kupon" id="btnKupon">Použiť kupón</button>
        <button class="btn-kupon" id="btnZrusKupon" hidden>Zrušiť kupón</button>
    </div>
    <h2 id="finalnaSuma">Na zaplatenie: 0,00 €</h2>
    <div id="objednavka" hidden>
        <h3>📦 Dokončiť objednávku</h3>
        <form id="formObjednavka" class="formular">
            <label>Meno a priezvisko<input name="meno" required minlength="2" maxlength="100" autocomplete="name"></label>
            <label>Telefón<input name="telefon" type="tel" maxlength="30" autocomplete="tel"></label>
            <label class="siroke">Adresa doručenia<input name="adresa" required minlength="5" maxlength="300" autocomplete="street-address"></label>
            <button class="btn-objednat">✅ Objednať (platba pri prevzatí)</button>
        </form>
    </div>
    <div id="potvrdenie" hidden></div>
</div>
</div>
<a id="plavajuci" href="#kosik">🛒 0 ks</a>
<div id="sprava" hidden></div>

<script>
const KATEGORIE = {"ovocie": "🍎 Ovocie", "zelenina": "🥕 Zelenina", "sladkost": "🍫 Sladkosti", "ine": "📦 Ostatné"};
const NAHRADNY = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="#e2e8f0"/><text x="200" y="175" font-size="72" text-anchor="middle">🛒</text></svg>');
const $ = id => document.getElementById(id);
const eur = x => Number(x).toFixed(2).replace('.', ',') + ' €';
const esc = s => String(s ?? '').replace(/[&<>"']/g, z => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[z]));
let kosik = {polozky: [], pocet: 0, suma: 0, zlava: 0, spolu: 0, kupon: null, upozornenia: []};
let casovac;

async function api(url, telo) {
    const moznosti = telo === undefined ? {} :
        {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(telo)};
    const odpoved = await fetch(url, moznosti);
    const data = await odpoved.json().catch(() => ({}));
    if (!odpoved.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Nastala chyba, skús to znova.");
    return data;
}

function sprava(text, jeChyba = false) {
    const el = $("sprava");
    el.textContent = text;
    el.className = jeChyba ? "chyba" : "";
    el.hidden = false;
    clearTimeout(casovac);
    casovac = setTimeout(() => el.hidden = true, 2800);
}

// obrázok sa nenačítal -> náhradný obrázok
document.addEventListener("error", e => {
    const t = e.target;
    if (t.tagName === "IMG" && !t.dataset.nahrada) { t.dataset.nahrada = "1"; t.src = NAHRADNY; }
}, true);

async function nacitajSklad() {
    const sklad = await api("/api/sklad");
    const kategorie = {...KATEGORIE};
    for (const p of sklad) if (!kategorie[p.kategoria]) kategorie[p.kategoria] = "📦 " + p.kategoria;
    let html = "";
    for (const kat in kategorie) {
        const produkty = sklad.filter(p => p.kategoria === kat);
        if (!produkty.length) continue;
        html += `<div class="kategoria"><h2>${esc(kategorie[kat])}</h2><div class="produkty-grid">`;
        for (const p of produkty) {
            const vKosiku = (kosik.polozky.find(x => x.nazov === p.nazov) || {kusy: 0}).kusy;
            const volne = p.mnozstvo - vKosiku;
            html += `
            <div class="produkt">
                <img src="${esc(p.obrazok || NAHRADNY)}" class="prod-img" alt="${esc(p.nazov)}" loading="lazy">
                <div class="prod-info">
                    <div class="prod-title">${esc(p.nazov)}</div>
                    <div class="prod-meta">
                        <span class="cena">${eur(p.cena)}</span>
                        <span class="prod-sklad ${volne > 0 ? "" : "vypredane"}">${p.mnozstvo <= 0 ? "Vypredané" : "Sklad: " + volne + " ks"}</span>
                    </div>
                    ${volne > 0
                        ? `<div class="pridat"><input type="number" min="1" max="${volne}" value="1" aria-label="Počet kusov"><button data-pridat="${esc(p.nazov)}">🛒 Pridať do košíka</button></div>`
                        : `<button disabled>${p.mnozstvo > 0 ? "Všetky kusy máš v košíku" : "Vypredané"}</button>`}
                </div>
            </div>`;
        }
        html += "</div></div>";
    }
    $("produkty").innerHTML = html || "<p>Sklad je prázdny.</p>";
}

function vykresliKosik(animuj = false) {
    const k = kosik;
    $("obsahKosika").innerHTML = k.polozky.length ? k.polozky.map(p => `
        <div class="riadok">
            <img src="${esc(p.obrazok || NAHRADNY)}" alt="">
            <div class="riadok-nazov"><strong>${esc(p.nazov)}</strong><span>${eur(p.cena)} / ks</span></div>
            <div class="pocet">
                <button class="male" data-zmen="${esc(p.nazov)}" data-o="-1" aria-label="Menej">−</button>
                <span>${p.kusy}</span>
                <button class="male" data-zmen="${esc(p.nazov)}" data-o="1" aria-label="Viac" ${p.kusy >= p.mnozstvo ? "disabled" : ""}>+</button>
            </div>
            <strong class="riadok-suma">${eur(p.spolu)}</strong>
            <button class="male odstranit" data-zmen="${esc(p.nazov)}" data-o="zmaz" title="Odstrániť">✕</button>
        </div>`).join("") : "Košík je prázdny.";
    $("upozornenia").innerHTML = k.upozornenia.map(u => `<div class="upozornenie">${esc(u)}</div>`).join("");
    $("suma").textContent = eur(k.suma);
    $("zlavaRiadok").hidden = !k.kupon;
    $("zlavaText").textContent = `Zľava ${k.kupon || ""} (-${k.percenta || 0} %):`;
    $("zlava").textContent = "-" + eur(k.zlava);
    $("finalnaSuma").textContent = "Na zaplatenie: " + eur(k.spolu);
    $("btnZrusKupon").hidden = !k.kupon;
    if (k.kupon) $("kupon").value = k.kupon;
    $("objednavka").hidden = !k.polozky.length;
    const pl = $("plavajuci");
    pl.textContent = k.pocet ? `🛒 ${k.pocet} ks · ${eur(k.spolu)}` : "🛒 Košík je prázdny";
    if (animuj) { pl.classList.remove("bump"); void pl.offsetWidth; pl.classList.add("bump"); }
}

async function nacitajVsetko() {
    try {
        kosik = await api("/api/kosik");
        vykresliKosik();
        await nacitajSklad();
    } catch (e) {
        $("produkty").textContent = e.message;
    }
}

// pridanie do košíka
$("produkty").addEventListener("click", async e => {
    const btn = e.target.closest("[data-pridat]");
    if (!btn) return;
    const kusy = Math.max(1, Math.floor(Number(btn.parentElement.querySelector("input").value)) || 1);
    btn.disabled = true;
    try {
        kosik = await api("/api/kosik/pridaj", {nazov: btn.dataset.pridat, kusy: kusy});
        sprava("✅ " + kosik.sprava);
        $("potvrdenie").hidden = true;
        vykresliKosik(true);
        await nacitajSklad();
    } catch (err) {
        sprava(err.message, true);
        btn.disabled = false;
    }
});

// +, −, ✕ v košíku
$("obsahKosika").addEventListener("click", async e => {
    const btn = e.target.closest("[data-zmen]");
    if (!btn) return;
    const p = kosik.polozky.find(x => x.nazov === btn.dataset.zmen);
    const kusy = btn.dataset.o === "zmaz" ? 0 : Math.max(0, p.kusy + Number(btn.dataset.o));
    try {
        kosik = await api("/api/kosik/nastav", {nazov: p.nazov, kusy: kusy});
    } catch (err) {
        sprava(err.message, true);
        kosik = await api("/api/kosik");
    }
    vykresliKosik();
    await nacitajSklad();
});

// kupón
async function pouzitKupon(kod) {
    try {
        kosik = await api("/api/kosik/kupon", {kupon: kod});
        sprava(kosik.sprava);
        if (!kod) $("kupon").value = "";
        vykresliKosik();
    } catch (err) {
        sprava(err.message, true);
    }
}
$("btnKupon").onclick = () => pouzitKupon($("kupon").value.trim());
$("kupon").addEventListener("keydown", e => { if (e.key === "Enter") pouzitKupon($("kupon").value.trim()); });
$("btnZrusKupon").onclick = () => pouzitKupon("");

// objednávka
$("formObjednavka").addEventListener("submit", async e => {
    e.preventDefault();
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    try {
        const d = await api("/api/objednat", Object.fromEntries(new FormData(e.target)));
        e.target.reset();
        $("potvrdenie").textContent = `🎉 Ďakujeme! Objednávka č. ${d.cislo} bola prijatá. Na zaplatenie pri prevzatí: ${eur(d.spolu)}`;
        $("potvrdenie").hidden = false;
        $("kupon").value = "";
    } catch (err) {
        sprava(err.message, true);
    }
    btn.disabled = false;
    await nacitajVsetko();
});

nacitajVsetko();
</script>
</body>
</html>"""


HTML_ADMIN = r"""<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Admin Panel - Správa skladu</title>
<style>
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { font-family: Arial, sans-serif; background: #f9f9f9; margin: 0; padding: 30px 16px; color: #1e293b; }
h1 { text-align: center; color: #333; }
.container { max-width: 1000px; margin: auto; }
.sklad-box { background: white; padding: 25px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
.sklad-box h2 { margin-top: 0; }
a { color: #3b82f6; }
button { padding: 8px 14px; border: none; border-radius: 6px; cursor: pointer; color: white; font-weight: bold; background: #d9534f; font: inherit; font-weight: bold; }
button:hover { background: #c9302c; }
button.zelene { background: #16a34a; } button.zelene:hover { background: #15803d; }
button.modre { background: #3b82f6; } button.modre:hover { background: #2563eb; }
button.sive { background: #94a3b8; } button.sive:hover { background: #64748b; }
button:disabled { opacity: .6; cursor: not-allowed; }
.admin-produkt { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #eee; }
.admin-produkt:last-child { border-bottom: none; }
.admin-produkt .info { display: flex; align-items: center; gap: 12px; min-width: 0; }
.admin-produkt img { width: 48px; height: 48px; object-fit: cover; border-radius: 8px; background: #e2e8f0; flex: none; }
.admin-produkt .akcie { display: flex; gap: 6px; flex: none; }
.vypredane { color: #dc2626; font-weight: bold; }
.malo { color: #d97706; font-weight: bold; }
.formular { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; align-items: end; }
.formular label { display: grid; gap: 6px; font-weight: bold; font-size: .9rem; }
.formular .siroke { grid-column: span 3; }
.formular input, .formular select { padding: 9px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font: inherit; width: 100%; background: #fff; }
.formular input:focus, .formular select:focus { outline: 2px solid #3b82f6; border-color: transparent; }
.tlacidla { grid-column: 1 / -1; display: flex; gap: 8px; }
#nahlad { width: 100%; height: 70px; object-fit: cover; border-radius: 8px; background: #e2e8f0; }
.tip { color: #64748b; font-size: .85rem; margin: 10px 0 0; }
.kupony-formular { grid-template-columns: 1fr 1fr auto; }
.kupon { display: inline-flex; align-items: center; gap: 10px; background: #f1f5f9; border-radius: 999px; padding: 6px 6px 6px 14px; margin: 10px 8px 0 0; }
.kupon button { padding: 4px 10px; border-radius: 999px; }
.objednavka { border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
.objednavka-hlava { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.objednavka ul { margin: 10px 0; padding-left: 20px; }
.ticho { color: #64748b; }
#sprava { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #1e293b; color: #fff; padding: 12px 20px; border-radius: 10px; z-index: 10; max-width: calc(100% - 32px); }
#sprava.chyba { background: #dc2626; }
@media (max-width: 700px) {
    .formular, .kupony-formular { grid-template-columns: 1fr; }
    .formular .siroke { grid-column: auto; }
    .admin-produkt { flex-direction: column; align-items: flex-start; }
}
</style>
</head>
<body>
<div class="container">
    <h1>🛠️ Administračný Panel Skladu</h1>
    <p style="text-align:center"><a href="/" target="_blank">🛒 Otvoriť obchod</a></p>

    <div class="sklad-box">
        <h2 id="nadpisFormulara">➕ Pridať nový produkt</h2>
        <form id="formProdukt" class="formular">
            <label>Názov<input name="nazov" required maxlength="60" placeholder="napr. kiwi"></label>
            <label>Cena (€)<input name="cena" required inputmode="decimal" placeholder="1,29"></label>
            <label>Kategória
                <select name="kategoria">
                    <option value="ovocie">🍎 Ovocie</option>
                    <option value="zelenina">🥕 Zelenina</option>
                    <option value="sladkost">🍫 Sladkosti</option>
                    <option value="ine">📦 Ostatné</option>
                </select>
            </label>
            <label>Počet kusov<input name="mnozstvo" type="number" min="0" value="10" required></label>
            <label class="siroke">Obrázok (odkaz)<input name="obrazok" placeholder="https://images.unsplash.com/..."></label>
            <img id="nahlad" alt="Náhľad">
            <div class="tlacidla">
                <button class="zelene">💾 Uložiť produkt</button>
                <button type="button" class="sive" id="zrusitUpravu" hidden>Zrušiť úpravu</button>
            </div>
        </form>
        <p class="tip">Tip na obrázok: na stránke s fotkou (napr. unsplash.com) klikni pravým tlačidlom na obrázok → „Kopírovať adresu obrázka“ a vlož ho sem.</p>
    </div>

    <div class="sklad-box">
        <h2>📦 Aktuálny stav skladu</h2>
        <div id="sklad-zoznam">Načítavam produkty zo skladu...</div>
    </div>

    <div class="sklad-box">
        <h2>🏷️ Zľavové kódy</h2>
        <form id="formKupon" class="formular kupony-formular">
            <label>Kód<input name="kod" required maxlength="20" placeholder="LETO15" style="text-transform:uppercase"></label>
            <label>Zľava (%)<input name="percenta" type="number" min="1" max="100" required placeholder="15"></label>
            <button class="zelene">➕ Pridať kód</button>
        </form>
        <div id="kupony-zoznam"></div>
    </div>

    <div class="sklad-box">
        <h2>🧾 Objednávky</h2>
        <div id="objednavky-zoznam">Zatiaľ žiadne objednávky.</div>
    </div>
</div>
<div id="sprava" hidden></div>

<script>
const KATEGORIE = {"ovocie": "Ovocie", "zelenina": "Zelenina", "sladkost": "Sladkosti", "ine": "Ostatné"};
const NAHRADNY = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#e2e8f0"/><text x="50" y="62" font-size="36" text-anchor="middle">🖼️</text></svg>');
const $ = id => document.getElementById(id);
const eur = x => Number(x).toFixed(2).replace('.', ',') + ' €';
const esc = s => String(s ?? '').replace(/[&<>"']/g, z => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[z]));
const form = $("formProdukt");
let data = {sklad: [], kupony: [], objednavky: []};
let upravovany = "";
let casovac;

async function api(url, telo) {
    const moznosti = telo === undefined ? {} :
        {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(telo)};
    const odpoved = await fetch(url, moznosti);
    if (odpoved.status === 401) { location.reload(); throw new Error("Prihlás sa znova."); }
    const d = await odpoved.json().catch(() => ({}));
    if (!odpoved.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Skontroluj vyplnené údaje.");
    return d;
}

function sprava(text, jeChyba = false) {
    const el = $("sprava");
    el.textContent = text; el.className = jeChyba ? "chyba" : ""; el.hidden = false;
    clearTimeout(casovac); casovac = setTimeout(() => el.hidden = true, 2800);
}

document.addEventListener("error", e => {
    const t = e.target;
    if (t.tagName === "IMG" && !t.dataset.nahrada) { t.dataset.nahrada = "1"; t.src = NAHRADNY; }
}, true);

async function nacitajAdminSklad() {
    data = await api("/api/admin/data");

    $("sklad-zoznam").innerHTML = data.sklad.map(p => {
        const trieda = p.mnozstvo === 0 ? "vypredane" : p.mnozstvo <= 3 ? "malo" : "";
        return `<div class="admin-produkt">
            <span class="info">
                <img src="${esc(p.obrazok || NAHRADNY)}" alt="">
                <span><strong>${esc(p.nazov)}</strong> (${esc(KATEGORIE[p.kategoria] || p.kategoria)}) - ${eur(p.cena)} -
                <span class="${trieda}">sklad: ${p.mnozstvo} ks</span></span>
            </span>
            <span class="akcie">
                <button class="modre" data-uprav="${esc(p.nazov)}">✏️ Upraviť</button>
                <button data-odstran="${esc(p.nazov)}">🗑️ Odstrániť</button>
            </span>
        </div>`;
    }).join("") || "<p>Sklad je prázdny.</p>";

    $("kupony-zoznam").innerHTML = data.kupony.map(k =>
        `<span class="kupon"><strong>${esc(k.kod)}</strong> -${k.percenta} % <button data-zmaz-kupon="${esc(k.kod)}">✕</button></span>`
    ).join("") || '<p class="ticho">Žiadne zľavové kódy.</p>';

    $("objednavky-zoznam").innerHTML = data.objednavky.map(o => `
        <div class="objednavka">
            <div class="objednavka-hlava">
                <strong>Objednávka č. ${o.cislo}</strong>
                <span class="ticho">${esc(o.cas)}</span>
            </div>
            <div>${esc(o.meno)}${o.telefon ? " · " + esc(o.telefon) : ""}<br>${esc(o.adresa)}</div>
            <ul>${o.polozky.map(p => `<li>${esc(p.nazov)} – ${p.kusy} ks × ${eur(p.cena)} = ${eur(p.cena * p.kusy)}</li>`).join("")}</ul>
            <div>Suma: ${eur(o.suma)}${o.zlava ? ` · Zľava ${esc(o.kupon)}: -${eur(o.zlava)}` : ""} · <strong>Spolu: ${eur(o.spolu)}</strong></div>
        </div>`).join("") || "Zatiaľ žiadne objednávky.";
}

// náhľad obrázka
form.obrazok.addEventListener("input", () => {
    const img = $("nahlad"); delete img.dataset.nahrada; img.src = form.obrazok.value.trim() || NAHRADNY;
});

function zrusUpravu() {
    upravovany = "";
    form.reset();
    $("nahlad").src = NAHRADNY;
    $("nadpisFormulara").textContent = "➕ Pridať nový produkt";
    $("zrusitUpravu").hidden = true;
}
$("zrusitUpravu").onclick = zrusUpravu;

// uloženie produktu (nový aj úprava)
form.addEventListener("submit", async e => {
    e.preventDefault();
    const btn = form.querySelector("button.zelene");
    btn.disabled = true;
    try {
        const d = await api("/api/admin/produkt", {...Object.fromEntries(new FormData(form)), povodny_nazov: upravovany});
        sprava("✅ " + d.sprava);
        zrusUpravu();
        await nacitajAdminSklad();
    } catch (err) { sprava(err.message, true); }
    btn.disabled = false;
});

// upraviť / odstrániť produkt
$("sklad-zoznam").addEventListener("click", async e => {
    const uprav = e.target.closest("[data-uprav]");
    if (uprav) {
        const p = data.sklad.find(x => x.nazov === uprav.dataset.uprav);
        upravovany = p.nazov;
        form.nazov.value = p.nazov;
        form.cena.value = p.cena.toFixed(2).replace(".", ",");
        if (![...form.kategoria.options].some(o => o.value === p.kategoria)) form.kategoria.add(new Option(p.kategoria, p.kategoria));
        form.kategoria.value = p.kategoria;
        form.mnozstvo.value = p.mnozstvo;
        form.obrazok.value = p.obrazok;
        const img = $("nahlad"); delete img.dataset.nahrada; img.src = p.obrazok || NAHRADNY;
        $("nadpisFormulara").textContent = "✏️ Upraviť produkt: " + p.nazov;
        $("zrusitUpravu").hidden = false;
        form.scrollIntoView({behavior: "smooth", block: "center"});
        return;
    }
    const odstran = e.target.closest("[data-odstran]");
    if (odstran && confirm("Naozaj chcete zmazať produkt " + odstran.dataset.odstran + "?")) {
        try {
            const d = await api("/api/admin/odstran", {nazov: odstran.dataset.odstran});
            sprava(d.sprava);
            if (upravovany === odstran.dataset.odstran) zrusUpravu();
            await nacitajAdminSklad();
        } catch (err) { sprava(err.message, true); }
    }
});

// zľavové kódy
$("formKupon").addEventListener("submit", async e => {
    e.preventDefault();
    try {
        const d = await api("/api/admin/kupon", Object.fromEntries(new FormData(e.target)));
        sprava("✅ " + d.sprava);
        e.target.reset();
        await nacitajAdminSklad();
    } catch (err) { sprava(err.message, true); }
});
$("kupony-zoznam").addEventListener("click", async e => {
    const b = e.target.closest("[data-zmaz-kupon]");
    if (!b || !confirm("Zmazať kód " + b.dataset.zmazKupon + "?")) return;
    try { await api("/api/admin/kupon/odstran", {kod: b.dataset.zmazKupon}); await nacitajAdminSklad(); }
    catch (err) { sprava(err.message, true); }
});

$("nahlad").src = NAHRADNY;
nacitajAdminSklad().catch(err => sprava(err.message, true));
</script>
</body>
</html>"""
