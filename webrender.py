import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

"""
E-SHOP – FastAPI + SQLite
=========================
 
Inštalácia:
    pip install -r requirements.txt
 
Spustenie:
    uvicorn main:app --reload
 
Obchod:  http://127.0.0.1:8000/
Admin:   http://127.0.0.1:8000/admin
 
Nastavenia (nepovinné, cez premenné prostredia):
    ESHOP_NAZOV        názov obchodu               (predvolené: Čerstvý trh)
    ESHOP_ADMIN_MENO   meno do administrácie       (predvolené: admin)
    ESHOP_ADMIN_HESLO  heslo do administrácie      (predvolené: Maxpol04 – ZMEŇ HO!)
    ESHOP_HTTPS        1 = web beží na https (bezpečné cookies)
 
Dáta sa ukladajú do súboru eshop.db, nahrané obrázky do priečinka uploads/.
Všetky ceny sa interne počítajú v centoch (celé čísla), takže nevznikajú
chyby zaokrúhľovania typu 0.1 + 0.2 = 0.30000000000000004.
"""
 
import hashlib
import html
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, Optional
 
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
 
# =====================================================================
# NASTAVENIA
# =====================================================================
 
ZAKLAD = Path(__file__).resolve().parent
DB_SUBOR = ZAKLAD / "eshop.db"
UPLOAD_DIR = ZAKLAD / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
 
NAZOV_OBCHODU = os.getenv("ESHOP_NAZOV", "Čerstvý trh")
ADMIN_MENO = os.getenv("ESHOP_ADMIN_MENO", "admin")
ADMIN_HESLO = os.getenv("ESHOP_ADMIN_HESLO", "Maxpol04")
HTTPS = os.getenv("ESHOP_HTTPS", "0") == "1"
 
ADMIN_RELACIA_SEKUNDY = 8 * 3600          # prihlásenie do adminu platí 8 hodín
KOSIK_PLATNOST_SEKUNDY = 30 * 24 * 3600   # košík si obchod pamätá 30 dní
MAX_OBRAZOK_BAJTY = 5 * 1024 * 1024       # max. 5 MB na obrázok
POVOLENE_PRIPONY = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
 
app = FastAPI(title=NAZOV_OBCHODU, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
 
 
@app.middleware("http")
async def bezpecnostne_hlavicky(request: Request, call_next):
    odpoved = await call_next(request)
    odpoved.headers.setdefault("X-Content-Type-Options", "nosniff")
    odpoved.headers.setdefault("X-Frame-Options", "DENY")
    odpoved.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith(("/admin", "/api/")):
        odpoved.headers["Cache-Control"] = "no-store"
    return odpoved
 
 
# =====================================================================
# DATABÁZA
# =====================================================================
 
SCHEMA = """
CREATE TABLE IF NOT EXISTS produkty (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nazov      TEXT    NOT NULL,
    popis      TEXT    NOT NULL DEFAULT '',
    cena       INTEGER NOT NULL CHECK (cena >= 0),          -- v centoch
    kategoria  TEXT    NOT NULL DEFAULT 'Ostatné',
    sklad      INTEGER NOT NULL DEFAULT 0 CHECK (sklad >= 0),
    obrazok    TEXT    NOT NULL DEFAULT '',
    aktivny    INTEGER NOT NULL DEFAULT 1,
    vytvorene  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kosiky (
    id        TEXT PRIMARY KEY,
    kupon     TEXT,
    upravene  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kosik_polozky (
    kosik_id    TEXT    NOT NULL REFERENCES kosiky(id)   ON DELETE CASCADE,
    produkt_id  INTEGER NOT NULL REFERENCES produkty(id) ON DELETE CASCADE,
    mnozstvo    INTEGER NOT NULL CHECK (mnozstvo > 0),
    PRIMARY KEY (kosik_id, produkt_id)
);
CREATE TABLE IF NOT EXISTS kupony (
    kod       TEXT    PRIMARY KEY,
    typ       TEXT    NOT NULL CHECK (typ IN ('percent', 'suma')),
    hodnota   INTEGER NOT NULL CHECK (hodnota > 0),   -- percentá alebo centy
    min_suma  INTEGER NOT NULL DEFAULT 0,             -- v centoch
    aktivny   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS objednavky (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vytvorene   INTEGER NOT NULL,
    meno        TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    telefon     TEXT    NOT NULL DEFAULT '',
    adresa      TEXT    NOT NULL,
    poznamka    TEXT    NOT NULL DEFAULT '',
    medzisucet  INTEGER NOT NULL,
    zlava       INTEGER NOT NULL,
    spolu       INTEGER NOT NULL,
    kupon       TEXT,
    stav        TEXT    NOT NULL DEFAULT 'nová'
);
CREATE TABLE IF NOT EXISTS objednavka_polozky (
    objednavka_id  INTEGER NOT NULL REFERENCES objednavky(id) ON DELETE CASCADE,
    produkt_id     INTEGER,
    nazov          TEXT    NOT NULL,
    cena           INTEGER NOT NULL,
    mnozstvo       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_relacie (
    token_hash  TEXT    PRIMARY KEY,
    expiruje    INTEGER NOT NULL
);
"""
 
U = "https://images.unsplash.com/"
POCIATOCNE_PRODUKTY = [
    # názov, popis, cena €, kategória, sklad, obrázok
    ("Jablko", "Chrumkavé a šťavnaté, cena za kus.", "0.50", "Ovocie", 10, U + "photo-1560806887-1e4cd0b6cbd6?w=600"),
    ("Banán", "Zrelý a sladký, cena za kus.", "1.20", "Ovocie", 5, U + "photo-1571771894821-ce9b6c11b08e?w=600"),
    ("Hruška", "Mäkká a voňavá, cena za kus.", "0.80", "Ovocie", 7, U + "photo-1514756331096-242fdeb70d4a?w=600"),
    ("Slivka", "Sladké slivky, cena za kus.", "0.30", "Ovocie", 8, U + "photo-1603186741832-73602d33486c?w=600"),
    ("Pomaranč", "Plný vitamínu C, cena za kus.", "0.60", "Ovocie", 6, U + "photo-1547514701-42782101795e?w=600"),
    ("Broskyňa", "Šťavnatá broskyňa, cena za kus.", "0.90", "Ovocie", 5, U + "photo-1595124256660-bf968b820c54?w=600"),
    ("Mrkva", "Čerstvá mrkva, cena za kus.", "0.40", "Zelenina", 10, U + "photo-1598170845058-32b9d6a5da37?w=600"),
    ("Zemiak", "Varné zemiaky, cena za kus.", "0.20", "Zelenina", 20, U + "photo-1518977676601-b53f82aba655?w=600"),
    ("Petržlen", "Koreňová petržlen, cena za kus.", "0.50", "Zelenina", 5, U + "photo-1587334206596-f947e90956f1?w=600"),
    ("Zeler", "Bulvový zeler, cena za kus.", "0.70", "Zelenina", 3, U + "photo-1628155930542-3c7a64e2c833?w=600"),
    ("Čokoláda", "Horká čokoláda 100 g.", "1.50", "Sladkosti", 4, U + "photo-1511381939415-e44015466834?w=600"),
    ("Cukor", "Kryštálový cukor 1 kg.", "1.00", "Sladkosti", 6, U + "photo-1581447101798-2fa5bbd33c8b?w=600"),
    ("Mlieko", "Polotučné mlieko 1 l.", "1.30", "Ostatné", 5, U + "photo-1550583724-b2692b85b150?w=600"),
    ("Chlieb", "Kváskový chlieb 1 kg.", "2.00", "Ostatné", 8, U + "photo-1509440159596-0249088772ff?w=600"),
]
 
 
@contextmanager
def databaza():
    """Otvorí spojenie s DB. Pri chybe (aj HTTPException) sa všetko vráti späť."""
    con = sqlite3.connect(DB_SUBOR, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
 
 
def inicializuj_db():
    with databaza() as con:
        con.executescript(SCHEMA)
        teraz = int(time.time())
        if con.execute("SELECT COUNT(*) FROM produkty").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO produkty (nazov, popis, cena, kategoria, sklad, obrazok, vytvorene) VALUES (?,?,?,?,?,?,?)",
                [(n, p, na_centy(c), k, s, o, teraz) for n, p, c, k, s, o in POCIATOCNE_PRODUKTY],
            )
        if con.execute("SELECT COUNT(*) FROM kupony").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO kupony (kod, typ, hodnota) VALUES (?,?,?)",
                [("ZLAVA10", "percent", 10), ("ZLAVA20", "percent", 20)],
            )
        # upratanie starých košíkov a prihlásení
        con.execute("DELETE FROM kosiky WHERE upravene < ?", (teraz - KOSIK_PLATNOST_SEKUNDY,))
        con.execute("DELETE FROM admin_relacie WHERE expiruje < ?", (teraz,))
 
 
# =====================================================================
# PENIAZE (všetko v centoch, zaokrúhľovanie matematicky na 2 desatinné miesta)
# =====================================================================
 
def na_centy(hodnota) -> int:
    """'1,29' / '1.29' / 1.29 -> 129 (zaokrúhli na celé centy)."""
    text = str(hodnota).replace("€", "").replace(" ", "").replace(",", ".").strip()
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise HTTPException(400, f"Neplatná suma: „{hodnota}“.")
    if not d.is_finite() or d < 0 or d > 1_000_000:
        raise HTTPException(400, "Suma musí byť medzi 0 a 1 000 000 €.")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
 
 
def vypocitaj_zlavu(medzisucet: int, kupon) -> int:
    if kupon is None or medzisucet <= 0 or medzisucet < kupon["min_suma"]:
        return 0
    if kupon["typ"] == "percent":
        zlava = (Decimal(medzisucet) * kupon["hodnota"] / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    else:
        zlava = Decimal(kupon["hodnota"])
    return int(min(zlava, medzisucet))  # zľava nikdy nie je vyššia ako nákup
 
 
# =====================================================================
# KOŠÍK (každý zákazník má vlastný, podľa cookie)
# =====================================================================
 
def ziskaj_kosik(request: Request, response: Response) -> str:
    kid = request.cookies.get("kosik", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", kid):
        kid = secrets.token_urlsafe(24)
    response.set_cookie("kosik", kid, max_age=KOSIK_PLATNOST_SEKUNDY, httponly=True, samesite="lax", secure=HTTPS)
    with databaza() as con:
        con.execute(
            "INSERT INTO kosiky (id, upravene) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET upravene = excluded.upravene",
            (kid, int(time.time())),
        )
    return kid
 
 
def aktivny_kupon(con, kod):
    if not kod:
        return None
    return con.execute("SELECT * FROM kupony WHERE kod = ? AND aktivny = 1", (kod,)).fetchone()
 
 
def stav_kosika(con, kid: str) -> dict:
    riadky = con.execute(
        """SELECT p.id, p.nazov, p.cena, p.obrazok, p.sklad, p.aktivny, k.mnozstvo
           FROM kosik_polozky k JOIN produkty p ON p.id = k.produkt_id
           WHERE k.kosik_id = ? ORDER BY p.nazov""",
        (kid,),
    ).fetchall()
 
    polozky, upozornenia, medzisucet, upravene = [], [], 0, False
    for r in riadky:
        mnozstvo = r["mnozstvo"]
        if not r["aktivny"] or r["sklad"] <= 0:
            con.execute("DELETE FROM kosik_polozky WHERE kosik_id = ? AND produkt_id = ?", (kid, r["id"]))
            upozornenia.append(f"{r['nazov']} už nie je dostupný, odstránili sme ho z košíka.")
            upravene = True
            continue
        if mnozstvo > r["sklad"]:
            mnozstvo = r["sklad"]
            con.execute("UPDATE kosik_polozky SET mnozstvo = ? WHERE kosik_id = ? AND produkt_id = ?", (mnozstvo, kid, r["id"]))
            upozornenia.append(f"{r['nazov']}: na sklade je už len {mnozstvo} ks, množstvo sme upravili.")
            upravene = True
        spolu = r["cena"] * mnozstvo
        medzisucet += spolu
        polozky.append({
            "id": r["id"], "nazov": r["nazov"], "cena": r["cena"], "obrazok": r["obrazok"],
            "sklad": r["sklad"], "mnozstvo": mnozstvo, "spolu": spolu,
        })
 
    kod = con.execute("SELECT kupon FROM kosiky WHERE id = ?", (kid,)).fetchone()["kupon"]
    kupon = aktivny_kupon(con, kod)
    if kod and kupon is None:
        con.execute("UPDATE kosiky SET kupon = NULL WHERE id = ?", (kid,))
        upozornenia.append(f"Kupón {kod} už nie je platný.")
 
    zlava = vypocitaj_zlavu(medzisucet, kupon)
    return {
        "polozky": polozky,
        "pocet": sum(p["mnozstvo"] for p in polozky),
        "medzisucet": medzisucet,
        "zlava": zlava,
        "spolu": medzisucet - zlava,
        "kupon": None if kupon is None else {
            "kod": kupon["kod"], "typ": kupon["typ"], "hodnota": kupon["hodnota"],
            "min_suma": kupon["min_suma"], "plati": medzisucet >= kupon["min_suma"],
        },
        "upozornenia": upozornenia,
        "upravene": upravene,
    }
 
 
# =====================================================================
# OBCHOD – STRÁNKA A API PRE ZÁKAZNÍKOV
# =====================================================================
 
def stranka(sablona: str) -> HTMLResponse:
    return HTMLResponse(sablona.replace("{{NAZOV}}", html.escape(NAZOV_OBCHODU)))
 
 
@app.get("/", response_class=HTMLResponse)
def obchod():
    return stranka(HTML_OBCHOD)
 
 
@app.get("/api/produkty")
def api_produkty():
    with databaza() as con:
        riadky = con.execute(
            "SELECT id, nazov, popis, cena, kategoria, sklad, obrazok FROM produkty WHERE aktivny = 1 "
            "ORDER BY kategoria = 'Ostatné', kategoria, nazov"   # „Ostatné“ vždy na konci
        ).fetchall()
    return [dict(r) for r in riadky]
 
 
@app.get("/api/kosik")
def api_kosik(kid: str = Depends(ziskaj_kosik)):
    with databaza() as con:
        return stav_kosika(con, kid)
 
 
class PridajVstup(BaseModel):
    produkt_id: int
    mnozstvo: int = Field(1, ge=1, le=999)
 
 
@app.post("/api/kosik/pridaj")
def kosik_pridaj(data: PridajVstup, kid: str = Depends(ziskaj_kosik)):
    with databaza() as con:
        p = con.execute("SELECT nazov, sklad FROM produkty WHERE id = ? AND aktivny = 1", (data.produkt_id,)).fetchone()
        if not p:
            raise HTTPException(404, "Produkt neexistuje.")
        r = con.execute(
            "SELECT mnozstvo FROM kosik_polozky WHERE kosik_id = ? AND produkt_id = ?", (kid, data.produkt_id)
        ).fetchone()
        v_kosiku = r["mnozstvo"] if r else 0
        nove = v_kosiku + data.mnozstvo
        if p["sklad"] <= 0:
            raise HTTPException(409, f"{p['nazov']} je vypredaný.")
        if nove > p["sklad"]:
            zostava = p["sklad"] - v_kosiku
            if zostava <= 0:
                raise HTTPException(409, f"V košíku už máte všetky dostupné kusy ({p['sklad']} ks).")
            raise HTTPException(409, f"Na sklade je len {p['sklad']} ks. Pridať môžete ešte {zostava} ks.")
        con.execute(
            """INSERT INTO kosik_polozky (kosik_id, produkt_id, mnozstvo) VALUES (?, ?, ?)
               ON CONFLICT(kosik_id, produkt_id) DO UPDATE SET mnozstvo = excluded.mnozstvo""",
            (kid, data.produkt_id, nove),
        )
        stav = stav_kosika(con, kid)
    stav["sprava"] = f"{p['nazov']} ({data.mnozstvo} ks) pridané do košíka."
    return stav
 
 
class NastavVstup(BaseModel):
    produkt_id: int
    mnozstvo: int = Field(ge=0, le=999)
 
 
@app.post("/api/kosik/nastav")
def kosik_nastav(data: NastavVstup, kid: str = Depends(ziskaj_kosik)):
    with databaza() as con:
        if data.mnozstvo == 0:
            con.execute("DELETE FROM kosik_polozky WHERE kosik_id = ? AND produkt_id = ?", (kid, data.produkt_id))
        else:
            p = con.execute("SELECT nazov, sklad FROM produkty WHERE id = ? AND aktivny = 1", (data.produkt_id,)).fetchone()
            if not p:
                raise HTTPException(404, "Produkt neexistuje.")
            if data.mnozstvo > p["sklad"]:
                raise HTTPException(409, f"{p['nazov']}: na sklade je len {p['sklad']} ks.")
            con.execute(
                """INSERT INTO kosik_polozky (kosik_id, produkt_id, mnozstvo) VALUES (?, ?, ?)
                   ON CONFLICT(kosik_id, produkt_id) DO UPDATE SET mnozstvo = excluded.mnozstvo""",
                (kid, data.produkt_id, data.mnozstvo),
            )
        return stav_kosika(con, kid)
 
 
class KuponVstup(BaseModel):
    kod: str = Field(max_length=40)
 
 
@app.post("/api/kosik/kupon")
def kosik_kupon(data: KuponVstup, kid: str = Depends(ziskaj_kosik)):
    kod = data.kod.strip().upper()
    with databaza() as con:
        if not aktivny_kupon(con, kod):
            raise HTTPException(404, "Tento zľavový kód neexistuje alebo už neplatí.")
        con.execute("UPDATE kosiky SET kupon = ? WHERE id = ?", (kod, kid))
        stav = stav_kosika(con, kid)
    stav["sprava"] = f"Kupón {kod} bol uplatnený."
    return stav
 
 
@app.delete("/api/kosik/kupon")
def kosik_zrus_kupon(kid: str = Depends(ziskaj_kosik)):
    with databaza() as con:
        con.execute("UPDATE kosiky SET kupon = NULL WHERE id = ?", (kid,))
        return stav_kosika(con, kid)
 
 
class ObjednavkaVstup(BaseModel):
    meno: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=120)
    telefon: str = Field("", max_length=30)
    adresa: str = Field(min_length=5, max_length=300)
    poznamka: str = Field("", max_length=1000)
 
 
@app.post("/api/objednavka")
def vytvor_objednavku(data: ObjednavkaVstup, kid: str = Depends(ziskaj_kosik)):
    email = data.email.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Zadajte platný e-mail.")
    with databaza() as con:
        stav = stav_kosika(con, kid)
        if stav["upravene"]:
            raise HTTPException(409, "Košík sa medzitým zmenil (sklad). Skontrolujte ho prosím a objednajte znova.")
        if not stav["polozky"]:
            raise HTTPException(400, "Košík je prázdny.")
        kupon = stav["kupon"]["kod"] if stav["kupon"] and stav["zlava"] else None
        cur = con.execute(
            """INSERT INTO objednavky (vytvorene, meno, email, telefon, adresa, poznamka, medzisucet, zlava, spolu, kupon)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (int(time.time()), data.meno.strip(), email, data.telefon.strip(), data.adresa.strip(),
             data.poznamka.strip(), stav["medzisucet"], stav["zlava"], stav["spolu"], kupon),
        )
        oid = cur.lastrowid
        for p in stav["polozky"]:
            # odpočet zo skladu – podmienka zaručí, že sklad nikdy nepôjde do mínusu
            u = con.execute(
                "UPDATE produkty SET sklad = sklad - ? WHERE id = ? AND sklad >= ?",
                (p["mnozstvo"], p["id"], p["mnozstvo"]),
            )
            if u.rowcount != 1:
                raise HTTPException(409, f"{p['nazov']} sa medzitým vypredal. Skontrolujte košík.")
            con.execute(
                "INSERT INTO objednavka_polozky (objednavka_id, produkt_id, nazov, cena, mnozstvo) VALUES (?,?,?,?,?)",
                (oid, p["id"], p["nazov"], p["cena"], p["mnozstvo"]),
            )
        con.execute("DELETE FROM kosik_polozky WHERE kosik_id = ?", (kid,))
        con.execute("UPDATE kosiky SET kupon = NULL WHERE id = ?", (kid,))
    return {"cislo": oid, "spolu": stav["spolu"]}
 
 
# =====================================================================
# ADMIN – PRIHLÁSENIE (heslo, relácia v cookie, ochrana proti hádaniu hesla)
# =====================================================================
 
_neuspesne_pokusy: dict[str, list[float]] = {}
 
 
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
 
 
def je_admin(request: Request) -> bool:
    token = request.cookies.get("admin")
    if not token:
        return False
    with databaza() as con:
        r = con.execute("SELECT expiruje FROM admin_relacie WHERE token_hash = ?", (_hash(token),)).fetchone()
    return bool(r and r["expiruje"] > time.time())
 
 
def over_admina(request: Request):
    if not je_admin(request):
        raise HTTPException(401, "Nie ste prihlásený.")
 
 
class PrihlasenieVstup(BaseModel):
    meno: str = Field(max_length=100)
    heslo: str = Field(max_length=200)
 
 
@app.post("/admin/prihlasenie")
def admin_prihlasenie(data: PrihlasenieVstup, request: Request, response: Response):
    ip = request.client.host if request.client else "?"
    teraz = time.time()
    pokusy = [t for t in _neuspesne_pokusy.get(ip, []) if teraz - t < 300]
    _neuspesne_pokusy[ip] = pokusy
    if len(pokusy) >= 5:
        raise HTTPException(429, "Príliš veľa neúspešných pokusov. Skúste to znova o 5 minút.")
 
    ok_meno = secrets.compare_digest(data.meno.encode(), ADMIN_MENO.encode())
    ok_heslo = secrets.compare_digest(data.heslo.encode(), ADMIN_HESLO.encode())
    if not (ok_meno and ok_heslo):
        pokusy.append(teraz)
        raise HTTPException(401, "Nesprávne meno alebo heslo.")
 
    _neuspesne_pokusy.pop(ip, None)
    token = secrets.token_urlsafe(32)
    with databaza() as con:
        con.execute("DELETE FROM admin_relacie WHERE expiruje < ?", (int(teraz),))
        con.execute("INSERT INTO admin_relacie (token_hash, expiruje) VALUES (?, ?)",
                    (_hash(token), int(teraz) + ADMIN_RELACIA_SEKUNDY))
    response.set_cookie("admin", token, max_age=ADMIN_RELACIA_SEKUNDY, httponly=True, samesite="strict", secure=HTTPS)
    return {"ok": True}
 
 
@app.post("/admin/odhlasenie")
def admin_odhlasenie(request: Request, response: Response):
    token = request.cookies.get("admin")
    if token:
        with databaza() as con:
            con.execute("DELETE FROM admin_relacie WHERE token_hash = ?", (_hash(token),))
    response.delete_cookie("admin")
    return {"ok": True}
 
 
@app.get("/admin", response_class=HTMLResponse)
def admin_stranka(request: Request):
    return stranka(HTML_ADMIN if je_admin(request) else HTML_PRIHLASENIE)
 
 
# =====================================================================
# ADMIN – PRODUKTY
# =====================================================================
 
def _je_obrazok(b: bytes) -> bool:
    return (
        b.startswith(b"\xff\xd8\xff")                      # JPG
        or b.startswith(b"\x89PNG\r\n\x1a\n")              # PNG
        or b[:6] in (b"GIF87a", b"GIF89a")                 # GIF
        or (b[:4] == b"RIFF" and b[8:12] == b"WEBP")       # WEBP
    )
 
 
def uloz_obrazok(subor: UploadFile) -> str:
    pripona = Path(subor.filename or "").suffix.lower()
    if pripona not in POVOLENE_PRIPONY:
        raise HTTPException(400, "Obrázok musí byť JPG, PNG, WEBP alebo GIF.")
    obsah = subor.file.read(MAX_OBRAZOK_BAJTY + 1)
    if len(obsah) > MAX_OBRAZOK_BAJTY:
        raise HTTPException(400, "Obrázok je väčší ako 5 MB.")
    if not _je_obrazok(obsah):
        raise HTTPException(400, "Súbor nie je platný obrázok.")
    nazov = f"{uuid.uuid4().hex}{'.jpg' if pripona == '.jpeg' else pripona}"
    (UPLOAD_DIR / nazov).write_bytes(obsah)
    return f"/uploads/{nazov}"
 
 
def zmaz_lokalny_obrazok(cesta: str):
    if cesta and cesta.startswith("/uploads/"):
        (UPLOAD_DIR / Path(cesta).name).unlink(missing_ok=True)
 
 
def vyber_obrazok(subor: Optional[UploadFile], url: str, sucasny: str = "") -> str:
    if subor is not None and subor.filename:
        return uloz_obrazok(subor)
    url = (url or "").strip()
    if url == sucasny:
        return sucasny
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(400, "Odkaz na obrázok musí začínať http:// alebo https://")
    return url[:500]
 
 
def over_udaje_produktu(nazov, popis, cena, kategoria, sklad, aktivny):
    nazov = nazov.strip()
    kategoria = kategoria.strip() or "Ostatné"
    if not 1 <= len(nazov) <= 100:
        raise HTTPException(400, "Názov musí mať 1 až 100 znakov.")
    if len(kategoria) > 50:
        raise HTTPException(400, "Kategória môže mať najviac 50 znakov.")
    if not 0 <= sklad <= 1_000_000:
        raise HTTPException(400, "Počet na sklade musí byť 0 alebo viac.")
    return nazov, popis.strip()[:1000], na_centy(cena), kategoria, sklad, 1 if aktivny else 0
 
 
@app.get("/api/admin/produkty", dependencies=[Depends(over_admina)])
def admin_produkty():
    with databaza() as con:
        return [dict(r) for r in con.execute("SELECT * FROM produkty ORDER BY kategoria, nazov").fetchall()]
 
 
@app.post("/api/admin/produkty", dependencies=[Depends(over_admina)])
def admin_novy_produkt(
    nazov: str = Form(...), cena: str = Form(...), kategoria: str = Form(""), sklad: int = Form(0),
    popis: str = Form(""), aktivny: bool = Form(True), obrazok_url: str = Form(""),
    obrazok: Optional[UploadFile] = File(None),
):
    udaje = over_udaje_produktu(nazov, popis, cena, kategoria, sklad, aktivny)
    cesta = vyber_obrazok(obrazok, obrazok_url)
    with databaza() as con:
        cur = con.execute(
            "INSERT INTO produkty (nazov, popis, cena, kategoria, sklad, aktivny, obrazok, vytvorene) VALUES (?,?,?,?,?,?,?,?)",
            (*udaje, cesta, int(time.time())),
        )
    return {"id": cur.lastrowid}
 
 
@app.post("/api/admin/produkty/{pid}", dependencies=[Depends(over_admina)])
def admin_uprav_produkt(
    pid: int,
    nazov: str = Form(...), cena: str = Form(...), kategoria: str = Form(""), sklad: int = Form(0),
    popis: str = Form(""), aktivny: bool = Form(True), obrazok_url: str = Form(""),
    obrazok: Optional[UploadFile] = File(None),
):
    udaje = over_udaje_produktu(nazov, popis, cena, kategoria, sklad, aktivny)
    with databaza() as con:
        p = con.execute("SELECT obrazok FROM produkty WHERE id = ?", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, "Produkt neexistuje.")
        cesta = vyber_obrazok(obrazok, obrazok_url, p["obrazok"])
        con.execute(
            "UPDATE produkty SET nazov=?, popis=?, cena=?, kategoria=?, sklad=?, aktivny=?, obrazok=? WHERE id=?",
            (*udaje, cesta, pid),
        )
    if cesta != p["obrazok"]:
        zmaz_lokalny_obrazok(p["obrazok"])
    return {"ok": True}
 
 
@app.delete("/api/admin/produkty/{pid}", dependencies=[Depends(over_admina)])
def admin_zmaz_produkt(pid: int):
    with databaza() as con:
        p = con.execute("SELECT obrazok FROM produkty WHERE id = ?", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, "Produkt neexistuje.")
        con.execute("DELETE FROM produkty WHERE id = ?", (pid,))
    zmaz_lokalny_obrazok(p["obrazok"])
    return {"ok": True}
 
 
# =====================================================================
# ADMIN – ZĽAVOVÉ KÓDY
# =====================================================================
 
class KuponAdmin(BaseModel):
    kod: str = Field(max_length=40)
    typ: Literal["percent", "suma"]
    hodnota: str = Field(max_length=20)
    min_suma: str = Field("0", max_length=20)
    aktivny: bool = True
 
 
@app.get("/api/admin/kupony", dependencies=[Depends(over_admina)])
def admin_kupony():
    with databaza() as con:
        return [dict(r) for r in con.execute("SELECT * FROM kupony ORDER BY kod").fetchall()]
 
 
@app.post("/api/admin/kupony", dependencies=[Depends(over_admina)])
def admin_uloz_kupon(data: KuponAdmin):
    kod = data.kod.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,40}", kod):
        raise HTTPException(400, "Kód môže obsahovať len písmená A–Z, číslice, - a _ (3 až 40 znakov).")
    if data.typ == "percent":
        try:
            d = Decimal(data.hodnota.replace(",", ".").strip())
        except InvalidOperation:
            raise HTTPException(400, "Zadajte percentá ako celé číslo.")
        if not d.is_finite() or d != d.to_integral_value() or not 1 <= d <= 100:
            raise HTTPException(400, "Percentuálna zľava musí byť celé číslo od 1 do 100.")
        hodnota = int(d)
    else:
        hodnota = na_centy(data.hodnota)
        if hodnota <= 0:
            raise HTTPException(400, "Zľava musí byť väčšia ako 0 €.")
    min_suma = na_centy(data.min_suma or "0")
    with databaza() as con:
        con.execute(
            """INSERT INTO kupony (kod, typ, hodnota, min_suma, aktivny) VALUES (?,?,?,?,?)
               ON CONFLICT(kod) DO UPDATE SET typ=excluded.typ, hodnota=excluded.hodnota,
               min_suma=excluded.min_suma, aktivny=excluded.aktivny""",
            (kod, data.typ, hodnota, min_suma, 1 if data.aktivny else 0),
        )
    return {"ok": True}
 
 
@app.delete("/api/admin/kupony/{kod}", dependencies=[Depends(over_admina)])
def admin_zmaz_kupon(kod: str):
    with databaza() as con:
        con.execute("DELETE FROM kupony WHERE kod = ?", (kod.upper(),))
    return {"ok": True}
 
 
# =====================================================================
# ADMIN – OBJEDNÁVKY
# =====================================================================
 
@app.get("/api/admin/objednavky", dependencies=[Depends(over_admina)])
def admin_objednavky():
    with databaza() as con:
        objednavky = [dict(r) for r in con.execute("SELECT * FROM objednavky ORDER BY id DESC LIMIT 500").fetchall()]
        if objednavky:
            ids = [o["id"] for o in objednavky]
            polozky: dict[int, list] = {}
            for r in con.execute(
                f"SELECT * FROM objednavka_polozky WHERE objednavka_id IN ({','.join('?' * len(ids))})", ids
            ).fetchall():
                polozky.setdefault(r["objednavka_id"], []).append(dict(r))
            for o in objednavky:
                o["polozky"] = polozky.get(o["id"], [])
    return objednavky
 
 
class StavVstup(BaseModel):
    stav: Literal["nová", "vybavuje sa", "odoslaná", "zrušená"]
 
 
@app.post("/api/admin/objednavky/{oid}/stav", dependencies=[Depends(over_admina)])
def admin_stav_objednavky(oid: int, data: StavVstup):
    with databaza() as con:
        o = con.execute("SELECT stav FROM objednavky WHERE id = ?", (oid,)).fetchone()
        if not o:
            raise HTTPException(404, "Objednávka neexistuje.")
        if o["stav"] == "zrušená" and data.stav != "zrušená":
            raise HTTPException(400, "Zrušenú objednávku už nemožno obnoviť.")
        if data.stav == "zrušená" and o["stav"] != "zrušená":
            # tovar zo zrušenej objednávky sa vráti na sklad
            for p in con.execute("SELECT produkt_id, mnozstvo FROM objednavka_polozky WHERE objednavka_id = ?", (oid,)):
                con.execute("UPDATE produkty SET sklad = sklad + ? WHERE id = ?", (p["mnozstvo"], p["produkt_id"]))
        con.execute("UPDATE objednavky SET stav = ? WHERE id = ?", (data.stav, oid))
    return {"ok": True}
 
 
# =====================================================================
# HTML ŠABLÓNY
# =====================================================================
 
HTML_OBCHOD = r"""<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{NAZOV}}</title>
<style>
:root{--brand:#15803d;--brand-tmava:#166534;--brand-svetla:#dcfce7;--text:#0f172a;--text-2:#475569;--text-3:#94a3b8;
--pozadie:#f8fafc;--okraj:#e2e8f0;--cervena:#dc2626;--oranzova:#d97706;--tien:0 1px 2px rgba(15,23,42,.06),0 4px 16px rgba(15,23,42,.06)}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:var(--pozadie);color:var(--text);line-height:1.5}
button,input,textarea,select{font:inherit;color:inherit}
.obal{max-width:1200px;margin:0 auto;padding:0 16px}
.hlavicka{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--okraj)}
.hlavicka-obsah{display:flex;align-items:center;gap:16px;min-height:68px}
.logo{font-weight:800;font-size:1.25rem;color:var(--text);text-decoration:none;white-space:nowrap}
#hladat{flex:1;max-width:420px;margin-left:auto;padding:10px 16px;border:1px solid var(--okraj);border-radius:999px;background:var(--pozadie)}
#hladat:focus{outline:2px solid var(--brand);outline-offset:1px;background:#fff}
.kosik-btn{display:flex;align-items:center;gap:8px;padding:10px 16px;border:0;border-radius:999px;background:var(--text);color:#fff;font-weight:600;cursor:pointer}
.odznak{min-width:22px;height:22px;padding:0 6px;border-radius:999px;background:var(--brand);font-size:.8rem;display:inline-grid;place-items:center}
.odznak.bump{animation:bump .35s}
@keyframes bump{50%{transform:scale(1.4)}}
.hero{padding:40px 0 4px}
.hero h1{margin:0 0 6px;font-size:clamp(1.6rem,4vw,2.4rem);letter-spacing:-.02em}
.hero p{margin:0;color:var(--text-2)}
.cipy{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0}
.cip{padding:8px 16px;border-radius:999px;border:1px solid var(--okraj);background:#fff;cursor:pointer;color:var(--text-2);font-weight:500}
.cip:hover{border-color:var(--brand);color:var(--brand)}
.cip.aktivny{background:var(--brand);border-color:var(--brand);color:#fff}
.sekcia h2{font-size:1.25rem;margin:8px 0 14px}
.mriezka{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px;margin-bottom:36px}
.karta{background:#fff;border-radius:14px;box-shadow:var(--tien);overflow:hidden;display:flex;flex-direction:column;transition:transform .2s,box-shadow .2s}
.karta:hover{transform:translateY(-3px);box-shadow:0 10px 30px rgba(15,23,42,.12)}
.karta-obr{aspect-ratio:4/3;background:#e2e8f0;overflow:hidden}
.karta-obr img{width:100%;height:100%;object-fit:cover;display:block}
.karta-telo{padding:14px 16px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
.karta-kat{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-3);font-weight:700}
.karta h3{margin:0;font-size:1.05rem}
.popis{margin:0;color:var(--text-2);font-size:.9rem}
.karta-cena{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:2px 8px;margin-top:auto;padding-top:8px}
.karta-cena strong{font-size:1.25rem;color:var(--brand-tmava)}
.sklad{font-size:.8rem;font-weight:600}
.sklad.ok{color:var(--brand)}.sklad.malo{color:var(--oranzova)}.sklad.nie{color:var(--cervena)}
.pridat{display:flex;gap:8px;margin-top:8px}
.stepper{display:flex;align-items:center;border:1px solid var(--okraj);border-radius:10px;overflow:hidden;background:#fff}
.stepper button{width:34px;height:40px;border:0;background:transparent;font-size:1.1rem;cursor:pointer}
.stepper button:hover:not(:disabled){background:var(--pozadie)}
.stepper button:disabled{color:var(--text-3);cursor:not-allowed}
.stepper input{width:40px;height:40px;border:0;text-align:center;-moz-appearance:textfield;background:transparent}
.stepper input::-webkit-outer-spin-button,.stepper input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
.stepper.male button{width:28px;height:32px}.stepper.male input{width:34px;height:32px}
.btn-hlavne{flex:1;padding:10px 14px;border:0;border-radius:10px;background:var(--brand);color:#fff;font-weight:600;cursor:pointer;transition:background .15s}
.btn-hlavne:hover:not(:disabled){background:var(--brand-tmava)}
.btn-hlavne:disabled{opacity:.5;cursor:not-allowed}
.btn-vypredane{margin-top:8px;padding:10px;border:0;border-radius:10px;background:var(--pozadie);color:var(--text-3);font-weight:600}
.nacitavam,.prazdne{padding:60px 0;text-align:center;color:var(--text-2)}
footer{text-align:center;color:var(--text-3);padding:40px 16px;font-size:.9rem}
.zaves{position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:30}
.kosik{position:fixed;top:0;right:0;height:100%;width:min(420px,100%);background:#fff;z-index:40;display:flex;flex-direction:column;
transform:translateX(100%);transition:transform .25s ease,visibility .25s;visibility:hidden}
.kosik.otvoreny{transform:none;visibility:visible;box-shadow:-10px 0 30px rgba(15,23,42,.15)}
.kosik-hlava{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;border-bottom:1px solid var(--okraj)}
.kosik-hlava h2{margin:0;font-size:1.2rem}
.zavriet{border:0;background:var(--pozadie);width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:1rem}
.kosik-polozky{flex:1;overflow-y:auto;padding:4px 20px}
.polozka{display:grid;grid-template-columns:64px 1fr auto;gap:12px;padding:14px 0;border-bottom:1px solid var(--okraj);align-items:center}
.polozka img{width:64px;height:64px;object-fit:cover;border-radius:10px;background:#e2e8f0}
.polozka-info{display:flex;flex-direction:column;gap:4px;min-width:0;align-items:flex-start}
.polozka-info span{color:var(--text-2);font-size:.85rem}
.polozka-spolu{display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.odstranit{border:0;background:none;color:var(--cervena);font-size:.8rem;cursor:pointer;padding:0}
.prazdny-kosik{text-align:center;padding:60px 0;color:var(--text-2);font-size:2.5rem}
.prazdny-kosik p{font-size:1rem}
.kosik-pata{padding:16px 20px 20px;border-top:1px solid var(--okraj);background:var(--pozadie)}
.kupon{display:flex;gap:8px}
.kupon input{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--okraj);border-radius:10px;text-transform:uppercase;background:#fff}
.kupon button{padding:10px 14px;border:0;border-radius:10px;background:var(--text);color:#fff;font-weight:600;cursor:pointer}
.kupon-info{font-size:.9rem;display:flex;justify-content:space-between;align-items:center;gap:8px;background:var(--brand-svetla);color:var(--brand-tmava);padding:8px 12px;border-radius:10px}
.kupon-info.neplatny{background:#fef3c7;color:#92400e}
.kupon-info button{border:0;background:none;color:inherit;text-decoration:underline;cursor:pointer;padding:0}
.suhrn{margin:14px 0}
.suhrn div{display:flex;justify-content:space-between;padding:3px 0}
.suhrn dt{color:var(--text-2)}.suhrn dd{margin:0;font-weight:600}
.suhrn .zlava dd{color:var(--brand)}
.suhrn .spolu{font-size:1.2rem;border-top:1px solid var(--okraj);margin-top:6px;padding-top:10px}
.suhrn .spolu dt{color:var(--text);font-weight:700}
.upozornenie{background:#fef3c7;color:#92400e;padding:8px 12px;border-radius:10px;font-size:.85rem;margin-bottom:10px}
.kosik-pata .btn-hlavne{width:100%;padding:14px}
.modal{position:fixed;inset:0;z-index:50;background:rgba(15,23,42,.5);display:grid;place-items:center;padding:16px}
.modal-okno{background:#fff;border-radius:18px;width:min(520px,100%);max-height:calc(100vh - 32px);overflow-y:auto;padding:28px;position:relative}
.modal-okno>.zavriet{position:absolute;top:16px;right:16px}
.modal h2{margin:0 0 4px;padding-right:40px}
.pod{color:var(--text-2);margin:0}
.form{display:grid;gap:14px;margin-top:18px}
.form label{display:grid;gap:6px;font-weight:600;font-size:.9rem}
.form input,.form textarea{padding:11px 12px;border:1px solid var(--okraj);border-radius:10px;font-weight:400;width:100%}
.form input:focus,.form textarea:focus{outline:2px solid var(--brand);outline-offset:0;border-color:transparent}
.form .dva{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.nepovinne{font-weight:400;color:var(--text-3)}
.dakujeme{text-align:center;padding:12px 0}
.dakujeme .ikona{font-size:3rem}
.dakujeme h2{padding:0}
.dakujeme .btn-hlavne{flex:none;padding:12px 24px;margin-top:12px}
.toasty{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:60;display:grid;gap:8px;width:min(420px,calc(100% - 32px))}
.toast{background:var(--text);color:#fff;padding:12px 16px;border-radius:12px;box-shadow:var(--tien);transition:opacity .3s,transform .3s}
.toast.chyba{background:var(--cervena)}
.toast.von{opacity:0;transform:translateY(8px)}
@media(max-width:640px){
.hlavicka-obsah{flex-wrap:wrap;padding-top:12px;padding-bottom:12px;gap:10px}
#hladat{order:3;max-width:none;flex-basis:100%}
.kosik-btn{margin-left:auto}
.form .dva{grid-template-columns:1fr}
.mriezka{grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
.pridat{flex-direction:column}
.pridat .stepper{justify-content:space-between}
.pridat .stepper input{flex:1}
}
</style>
</head>
<body>
<header class="hlavicka">
  <div class="obal hlavicka-obsah">
    <a class="logo" href="/">🥬 {{NAZOV}}</a>
    <input id="hladat" type="search" placeholder="Hľadať produkty…" aria-label="Hľadať produkty">
    <button class="kosik-btn" id="otvorKosik" aria-label="Otvoriť košík">🛒 Košík <span id="pocet" class="odznak">0</span></button>
  </div>
</header>
 
<main class="obal">
  <section class="hero">
    <h1>Čerstvé potraviny až k vám domov</h1>
    <p>Vyberte si z ponuky, nastavte počet kusov a objednajte pár kliknutiami.</p>
  </section>
  <nav id="kategorie" class="cipy" aria-label="Kategórie"></nav>
  <div id="katalog"><div class="nacitavam">Načítavam produkty…</div></div>
</main>
<footer>© <span id="rok"></span> {{NAZOV}} · Platba pri prevzatí</footer>
 
<div id="zaves" class="zaves" hidden></div>
<aside id="kosik" class="kosik" aria-hidden="true" aria-label="Košík">
  <div class="kosik-hlava"><h2>Váš košík</h2><button class="zavriet" id="zavrietKosik" aria-label="Zavrieť">✕</button></div>
  <div id="kosikPolozky" class="kosik-polozky"></div>
  <div class="kosik-pata">
    <div id="upozornenia"></div>
    <form id="kuponForm" class="kupon"><input id="kuponKod" placeholder="Zľavový kód" maxlength="40" aria-label="Zľavový kód"><button>Uplatniť</button></form>
    <div id="kuponInfo"></div>
    <dl class="suhrn">
      <div><dt>Medzisúčet</dt><dd id="medzisucet">0,00 €</dd></div>
      <div id="zlavaRiadok" class="zlava" hidden><dt>Zľava</dt><dd id="zlava"></dd></div>
      <div class="spolu"><dt>Spolu</dt><dd id="spolu">0,00 €</dd></div>
    </dl>
    <button id="kObjednavke" class="btn-hlavne" disabled>Pokračovať k objednávke</button>
  </div>
</aside>
 
<div id="modal" class="modal" hidden><div class="modal-okno" role="dialog" aria-modal="true">
  <button class="zavriet" data-zavriet-modal aria-label="Zavrieť">✕</button>
  <div id="modalObsah"></div>
</div></div>
<div id="toasty" class="toasty" aria-live="polite"></div>
 
<script>
const fmt = new Intl.NumberFormat('sk-SK', {style: 'currency', currency: 'EUR'});
const cena = c => fmt.format(c / 100);
const esc = s => String(s ?? '').replace(/[&<>"']/g, z => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[z]));
const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const $ = id => document.getElementById(id);
const PLACEHOLDER = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="#e2e8f0"/><text x="200" y="175" font-size="72" text-anchor="middle">🛒</text></svg>');
const POLIA = {meno: 'Meno a priezvisko', email: 'E-mail', telefon: 'Telefón', adresa: 'Adresa', poznamka: 'Poznámka', mnozstvo: 'Počet kusov', kod: 'Zľavový kód'};
 
let produkty = [];
let kosik = {polozky: [], pocet: 0, medzisucet: 0, zlava: 0, spolu: 0, kupon: null, upozornenia: []};
let aktivnaKat = 'Všetko';
 
async function api(url, moznosti = {}) {
  const o = {...moznosti};
  if (o.body !== undefined) { o.body = JSON.stringify(o.body); o.headers = {'Content-Type': 'application/json'}; }
  const r = await fetch(url, o);
  let d = null;
  try { d = await r.json(); } catch (e) {}
  if (!r.ok) {
    if (d && typeof d.detail === 'string') throw new Error(d.detail);
    if (d && Array.isArray(d.detail) && d.detail.length) {
      const pole = d.detail[0].loc ? d.detail[0].loc[d.detail[0].loc.length - 1] : '';
      throw new Error('Skontrolujte pole: ' + (POLIA[pole] || pole));
    }
    throw new Error('Nastala chyba. Skúste to prosím znova.');
  }
  return d;
}
 
function toast(text, typ = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + typ;
  el.textContent = text;
  $('toasty').append(el);
  setTimeout(() => el.classList.add('von'), 2700);
  setTimeout(() => el.remove(), 3100);
}
 
// nefunkčný obrázok -> náhradný obrázok
document.addEventListener('error', e => {
  const t = e.target;
  if (t.tagName === 'IMG' && !t.dataset.nahrada) { t.dataset.nahrada = '1'; t.src = PLACEHOLDER; }
}, true);
const obr = url => esc(url || PLACEHOLDER);
 
const vKosiku = id => (kosik.polozky.find(x => x.id === id) || {mnozstvo: 0}).mnozstvo;
 
function stavSkladu(p) {
  if (p.sklad <= 0) return '<span class="sklad nie">Vypredané</span>';
  if (p.sklad <= 5) return `<span class="sklad malo">Posledné ${p.sklad} ks</span>`;
  return `<span class="sklad ok">Skladom ${p.sklad} ks</span>`;
}
 
function kartaProduktu(p) {
  const zostava = p.sklad - vKosiku(p.id);
  const akcia = zostava > 0
    ? `<div class="pridat">
         <div class="stepper" data-max="${zostava}">
           <button type="button" data-krok="-1" aria-label="Menej">−</button>
           <input type="number" min="1" max="${zostava}" value="1" aria-label="Počet kusov">
           <button type="button" data-krok="1" aria-label="Viac">+</button>
         </div>
         <button class="btn-hlavne" data-pridat="${p.id}">Do košíka</button>
       </div>`
    : `<button class="btn-vypredane" disabled>${p.sklad > 0 ? 'Všetky kusy máte v košíku' : 'Vypredané'}</button>`;
  return `<article class="karta">
    <div class="karta-obr"><img src="${obr(p.obrazok)}" alt="${esc(p.nazov)}" loading="lazy"></div>
    <div class="karta-telo">
      <span class="karta-kat">${esc(p.kategoria)}</span>
      <h3>${esc(p.nazov)}</h3>
      ${p.popis ? `<p class="popis">${esc(p.popis)}</p>` : ''}
      <div class="karta-cena"><strong>${cena(p.cena)}</strong>${stavSkladu(p)}</div>
      ${akcia}
    </div>
  </article>`;
}
 
function vykresliKatalog() {
  const kategorie = [...new Set(produkty.map(p => p.kategoria))];
  if (aktivnaKat !== 'Všetko' && !kategorie.includes(aktivnaKat)) aktivnaKat = 'Všetko';
  $('kategorie').innerHTML = ['Všetko', ...kategorie]
    .map(k => `<button class="cip${k === aktivnaKat ? ' aktivny' : ''}" data-kat="${esc(k)}">${esc(k)}</button>`).join('');
 
  const q = norm($('hladat').value.trim());
  const zobraz = produkty.filter(p =>
    (aktivnaKat === 'Všetko' || p.kategoria === aktivnaKat) &&
    (!q || norm(p.nazov + ' ' + p.popis + ' ' + p.kategoria).includes(q)));
  if (!zobraz.length) { $('katalog').innerHTML = '<p class="prazdne">Nenašli sa žiadne produkty.</p>'; return; }
 
  const skupiny = {};
  for (const p of zobraz) (skupiny[p.kategoria] = skupiny[p.kategoria] || []).push(p);
  $('katalog').innerHTML = Object.entries(skupiny).map(([k, zoz]) =>
    `<section class="sekcia"><h2>${esc(k)}</h2><div class="mriezka">${zoz.map(kartaProduktu).join('')}</div></section>`).join('');
}
 
function vykresliKosik(animuj = false) {
  const odz = $('pocet');
  odz.textContent = kosik.pocet;
  if (animuj) { odz.classList.remove('bump'); void odz.offsetWidth; odz.classList.add('bump'); }
 
  $('kosikPolozky').innerHTML = kosik.polozky.length ? kosik.polozky.map(p => `
    <div class="polozka">
      <img src="${obr(p.obrazok)}" alt="">
      <div class="polozka-info">
        <strong>${esc(p.nazov)}</strong>
        <span>${cena(p.cena)} / ks</span>
        <div class="stepper male" data-kosik="${p.id}">
          <button type="button" data-zmena="-1" aria-label="Menej">−</button>
          <input type="number" min="0" max="${p.sklad}" value="${p.mnozstvo}" aria-label="Počet kusov">
          <button type="button" data-zmena="1" aria-label="Viac" ${p.mnozstvo >= p.sklad ? 'disabled' : ''}>+</button>
        </div>
      </div>
      <div class="polozka-spolu"><strong>${cena(p.spolu)}</strong><button class="odstranit" data-odstranit="${p.id}">Odstrániť</button></div>
    </div>`).join('')
    : '<div class="prazdny-kosik">🧺<p>Košík je zatiaľ prázdny.</p></div>';
 
  $('upozornenia').innerHTML = kosik.upozornenia.map(u => `<div class="upozornenie">${esc(u)}</div>`).join('');
 
  const k = kosik.kupon;
  $('kuponInfo').innerHTML = k ? `<div class="kupon-info${k.plati ? '' : ' neplatny'}">
      <span>Kupón <b>${esc(k.kod)}</b> (${k.typ === 'percent' ? '−' + k.hodnota + ' %' : '−' + cena(k.hodnota)})${k.plati ? '' : ' · platí od nákupu ' + cena(k.min_suma)}</span>
      <button type="button" data-zrus-kupon>Zrušiť</button></div>` : '';
  $('kuponForm').hidden = !!k;
 
  $('medzisucet').textContent = cena(kosik.medzisucet);
  $('zlavaRiadok').hidden = !kosik.zlava;
  $('zlava').textContent = '−' + cena(kosik.zlava);
  $('spolu').textContent = cena(kosik.spolu);
  $('kObjednavke').disabled = !kosik.polozky.length;
}
 
async function nacitajVsetko() {
  try {
    [produkty, kosik] = await Promise.all([api('/api/produkty'), api('/api/kosik')]);
    vykresliKatalog();
    vykresliKosik();
  } catch (err) {
    $('katalog').innerHTML = `<p class="prazdne">${esc(err.message)}</p>`;
  }
}
 
// ---- katalóg ----
$('kategorie').addEventListener('click', e => {
  const b = e.target.closest('[data-kat]');
  if (b) { aktivnaKat = b.dataset.kat; vykresliKatalog(); }
});
$('hladat').addEventListener('input', vykresliKatalog);
 
$('katalog').addEventListener('click', async e => {
  const krok = e.target.closest('[data-krok]');
  if (krok) {
    const st = krok.closest('.stepper'), inp = st.querySelector('input');
    inp.value = Math.min(+st.dataset.max, Math.max(1, (Math.floor(+inp.value) || 1) + +krok.dataset.krok));
    return;
  }
  const pridat = e.target.closest('[data-pridat]');
  if (!pridat) return;
  const mnozstvo = Math.max(1, Math.floor(+pridat.parentElement.querySelector('input').value) || 1);
  pridat.disabled = true;
  try {
    kosik = await api('/api/kosik/pridaj', {method: 'POST', body: {produkt_id: +pridat.dataset.pridat, mnozstvo}});
    toast('✓ ' + kosik.sprava);
    vykresliKosik(true);
    vykresliKatalog();
  } catch (err) {
    toast(err.message, 'chyba');
    await nacitajVsetko();
  } finally {
    pridat.disabled = false;
  }
});
$('katalog').addEventListener('change', e => {
  const st = e.target.closest('.stepper');
  if (st) e.target.value = Math.min(+st.dataset.max, Math.max(1, Math.floor(+e.target.value) || 1));
});
 
// ---- košík ----
function otvorKosik() {
  $('kosik').classList.add('otvoreny'); $('kosik').setAttribute('aria-hidden', 'false');
  $('zaves').hidden = false; document.body.style.overflow = 'hidden';
}
function zavriKosik() {
  $('kosik').classList.remove('otvoreny'); $('kosik').setAttribute('aria-hidden', 'true');
  $('zaves').hidden = true; document.body.style.overflow = '';
}
$('otvorKosik').onclick = otvorKosik;
$('zavrietKosik').onclick = zavriKosik;
$('zaves').onclick = zavriKosik;
 
async function nastav(id, mnozstvo) {
  try {
    kosik = await api('/api/kosik/nastav', {method: 'POST', body: {produkt_id: id, mnozstvo}});
  } catch (err) {
    toast(err.message, 'chyba');
    kosik = await api('/api/kosik');
  }
  vykresliKosik();
  vykresliKatalog();
}
$('kosikPolozky').addEventListener('click', e => {
  const z = e.target.closest('[data-zmena]');
  if (z) {
    const st = z.closest('[data-kosik]');
    return nastav(+st.dataset.kosik, Math.max(0, (Math.floor(+st.querySelector('input').value) || 0) + +z.dataset.zmena));
  }
  const o = e.target.closest('[data-odstranit]');
  if (o) nastav(+o.dataset.odstranit, 0);
});
$('kosikPolozky').addEventListener('change', e => {
  const st = e.target.closest('[data-kosik]');
  if (st) nastav(+st.dataset.kosik, Math.max(0, Math.floor(+e.target.value) || 0));
});
 
$('kuponForm').addEventListener('submit', async e => {
  e.preventDefault();
  const kod = $('kuponKod').value.trim();
  if (!kod) return;
  try {
    kosik = await api('/api/kosik/kupon', {method: 'POST', body: {kod}});
    toast('✓ ' + kosik.sprava);
    $('kuponKod').value = '';
    vykresliKosik();
  } catch (err) { toast(err.message, 'chyba'); }
});
$('kuponInfo').addEventListener('click', async e => {
  if (!e.target.closest('[data-zrus-kupon]')) return;
  kosik = await api('/api/kosik/kupon', {method: 'DELETE'});
  vykresliKosik();
});
 
// ---- objednávka ----
function otvorModal(obsah) {
  $('modalObsah').innerHTML = obsah;
  $('modal').hidden = false;
  document.body.style.overflow = 'hidden';
}
function zavriModal() {
  $('modal').hidden = true;
  document.body.style.overflow = $('kosik').classList.contains('otvoreny') ? 'hidden' : '';
}
$('modal').addEventListener('click', e => {
  if (e.target.id === 'modal' || e.target.closest('[data-zavriet-modal]')) zavriModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') { zavriModal(); zavriKosik(); } });
 
$('kObjednavke').onclick = () => {
  zavriKosik();
  otvorModal(`
    <h2>Dokončenie objednávky</h2>
    <p class="pod">Na zaplatenie: <b>${cena(kosik.spolu)}</b> · platba pri prevzatí</p>
    <form id="objForm" class="form">
      <label>Meno a priezvisko<input name="meno" required minlength="2" maxlength="100" autocomplete="name"></label>
      <div class="dva">
        <label>E-mail<input name="email" type="email" required maxlength="120" autocomplete="email"></label>
        <label>Telefón <span class="nepovinne">(nepovinné)</span><input name="telefon" type="tel" maxlength="30" autocomplete="tel"></label>
      </div>
      <label>Doručovacia adresa<textarea name="adresa" rows="2" required minlength="5" maxlength="300" autocomplete="street-address"></textarea></label>
      <label>Poznámka <span class="nepovinne">(nepovinné)</span><textarea name="poznamka" rows="2" maxlength="1000"></textarea></label>
      <button class="btn-hlavne" style="padding:14px">Záväzne objednať</button>
    </form>`);
};
 
$('modalObsah').addEventListener('submit', async e => {
  if (e.target.id !== 'objForm') return;
  e.preventDefault();
  const btn = e.target.querySelector('button');
  btn.disabled = true; btn.textContent = 'Odosielam…';
  try {
    const d = await api('/api/objednavka', {method: 'POST', body: Object.fromEntries(new FormData(e.target))});
    otvorModal(`<div class="dakujeme">
      <div class="ikona">✅</div>
      <h2>Ďakujeme za objednávku!</h2>
      <p>Číslo objednávky: <b>#${d.cislo}</b><br>Suma na zaplatenie: <b>${cena(d.spolu)}</b></p>
      <p class="pod">Budeme vás kontaktovať ohľadom doručenia.</p>
      <button class="btn-hlavne" data-zavriet-modal>Pokračovať v nákupe</button>
    </div>`);
    await nacitajVsetko();
  } catch (err) {
    toast(err.message, 'chyba');
    btn.disabled = false; btn.textContent = 'Záväzne objednať';
    await nacitajVsetko();
  }
});
 
$('rok').textContent = new Date().getFullYear();
nacitajVsetko();
</script>
</body>
</html>"""
 
 
HTML_PRIHLASENIE = r"""<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Prihlásenie · {{NAZOV}}</title>
<style>
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;background:linear-gradient(135deg,#0f172a,#1e3a2b);
font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#0f172a}
.box{background:#fff;border-radius:18px;padding:32px;width:min(380px,100%);box-shadow:0 20px 50px rgba(0,0,0,.35);display:grid;gap:14px}
.ikona{font-size:2.2rem}
h1{margin:0;font-size:1.5rem}
p{margin:-8px 0 6px;color:#64748b}
label{display:grid;gap:6px;font-weight:600;font-size:.9rem}
input{font:inherit;padding:11px 12px;border:1px solid #e2e8f0;border-radius:10px}
input:focus{outline:2px solid #15803d;border-color:transparent}
button{font:inherit;padding:12px;border:0;border-radius:10px;background:#15803d;color:#fff;font-weight:700;cursor:pointer;margin-top:4px}
button:hover{background:#166534}button:disabled{opacity:.6}
.chyba{background:#fee2e2;color:#991b1b;padding:10px 12px;border-radius:10px;font-size:.9rem}
a{color:#64748b;text-align:center;font-size:.9rem;text-decoration:none}
</style>
</head>
<body>
<form class="box" id="f">
  <div class="ikona">🔒</div>
  <h1>Administrácia</h1>
  <p>{{NAZOV}}</p>
  <label>Používateľské meno<input name="meno" autocomplete="username" required autofocus></label>
  <label>Heslo<input name="heslo" type="password" autocomplete="current-password" required></label>
  <div id="chyba" class="chyba" hidden></div>
  <button id="btn">Prihlásiť sa</button>
  <a href="/">← Späť do obchodu</a>
</form>
<script>
document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('btn'), ch = document.getElementById('chyba');
  btn.disabled = true; ch.hidden = true;
  try {
    const r = await fetch('/admin/prihlasenie', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(Object.fromEntries(new FormData(e.target)))});
    if (r.ok) { location.reload(); return; }
    let d = {}; try { d = await r.json(); } catch (x) {}
    ch.textContent = typeof d.detail === 'string' ? d.detail : 'Prihlásenie zlyhalo.';
  } catch (x) { ch.textContent = 'Server je nedostupný.'; }
  ch.hidden = false; btn.disabled = false;
});
</script>
</body>
</html>"""
 
 
HTML_ADMIN = r"""<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Administrácia · {{NAZOV}}</title>
<style>
:root{--brand:#15803d;--brand-tmava:#166534;--text:#0f172a;--text-2:#475569;--text-3:#94a3b8;--pozadie:#f1f5f9;--okraj:#e2e8f0;--cervena:#dc2626}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:var(--pozadie);color:var(--text);line-height:1.5}
button,input,select,textarea{font:inherit;color:inherit}
.obal{max-width:1200px;margin:0 auto;padding:0 16px}
.lista{background:var(--text);color:#fff;position:sticky;top:0;z-index:20}
.lista-obsah{display:flex;align-items:center;gap:20px;min-height:64px;flex-wrap:wrap;padding-top:8px;padding-bottom:8px}
.logo{font-weight:800;white-space:nowrap}.logo span{font-weight:400;color:var(--text-3);margin-left:6px}
.taby{display:flex;gap:4px;overflow-x:auto}
.taby button{background:none;border:0;color:#cbd5e1;padding:8px 14px;border-radius:10px;cursor:pointer;font-weight:600;white-space:nowrap;display:flex;align-items:center;gap:6px}
.taby button:hover{color:#fff;background:rgba(255,255,255,.08)}
.taby button.aktivny{background:#fff;color:var(--text)}
.odznak{min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:#ef4444;color:#fff;font-size:.75rem;display:inline-grid;place-items:center}
.lista-akcie{margin-left:auto;display:flex;gap:12px;align-items:center}
.lista-akcie a{color:#cbd5e1;text-decoration:none}.lista-akcie a:hover{color:#fff}
.lista-akcie button{background:rgba(255,255,255,.12);color:#fff;border:0;padding:8px 14px;border-radius:10px;cursor:pointer}
main.obal{padding-top:24px;padding-bottom:60px}
a{color:var(--brand)}
.panel{background:#fff;border-radius:14px;padding:20px;box-shadow:0 1px 3px rgba(15,23,42,.06);margin-bottom:20px}
.panel h2{margin:0 0 14px;font-size:1.1rem}
.panel-hlava{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.panel-hlava h2{margin:0}
.nastroje{display:flex;gap:8px;flex-wrap:wrap}
.nastroje input,.panel-hlava select{padding:9px 12px;border:1px solid var(--okraj);border-radius:10px;background:#fff}
.statistiky{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:20px}
.stat{background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 1px 3px rgba(15,23,42,.06)}
.stat span{color:var(--text-2);font-size:.9rem}.stat strong{display:block;font-size:1.8rem;margin-top:2px}
.dva-stlpce{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.riadok-zoznam{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--okraj);gap:12px}
.riadok-zoznam:last-child{border-bottom:0}
.ticho{color:var(--text-3)}.mensie{font-size:.85rem}
.tabulka-obal{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-3);padding:8px 10px;border-bottom:1px solid var(--okraj);white-space:nowrap}
td{padding:10px;border-bottom:1px solid var(--okraj);vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
.vpravo{text-align:right}
.miniatura{width:48px;height:48px;object-fit:cover;border-radius:8px;background:#e2e8f0;display:block}
.akcie{white-space:nowrap;text-align:right}.akcie .btn{margin-left:6px}
code{background:var(--pozadie);padding:2px 8px;border-radius:6px;font-weight:600}
.stitok{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:600;background:#e2e8f0;color:var(--text-2);white-space:nowrap}
.stitok.zeleny,.stitok.stav-2{background:#dcfce7;color:#166534}
.stitok.oranzovy,.stitok.stav-1{background:#fef3c7;color:#92400e}
.stitok.cerveny,.stitok.stav-3{background:#fee2e2;color:#991b1b}
.stitok.stav-0{background:#dbeafe;color:#1e40af}
.btn{padding:10px 16px;border:0;border-radius:10px;background:var(--brand);color:#fff;font-weight:600;cursor:pointer}
.btn:hover{background:var(--brand-tmava)}.btn:disabled{opacity:.5;cursor:not-allowed}
.btn.sekundarne{background:#e2e8f0;color:var(--text)}.btn.sekundarne:hover{background:#cbd5e1}
.btn.nebezpecne{background:#fee2e2;color:#991b1b}.btn.nebezpecne:hover{background:#fecaca}
.btn.male{padding:6px 12px;font-size:.85rem}
.form{display:grid;gap:14px}
.form label{display:grid;gap:6px;font-weight:600;font-size:.88rem}
.form input:not([type=checkbox]):not([type=file]),.form select,.form textarea{padding:10px 12px;border:1px solid var(--okraj);border-radius:10px;font-weight:400;width:100%;background:#fff}
.form input:focus,.form select:focus,.form textarea:focus{outline:2px solid var(--brand);outline-offset:0}
.form label.check{display:flex;align-items:center;gap:8px;align-self:end;padding-bottom:10px;cursor:pointer}
.form label.check input{width:18px;height:18px;accent-color:var(--brand)}
.form .dva{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form.riadok{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));align-items:end}
.tlacidla{display:flex;gap:8px;flex-wrap:wrap}
.obrazok-blok{display:grid;grid-template-columns:120px 1fr;gap:14px;align-items:start}
.obrazok-blok img{width:120px;height:120px;object-fit:cover;border-radius:12px;background:#e2e8f0}
.obrazok-blok>div{display:grid;gap:10px}
.obrazok-blok input[type=file]{font-weight:400;font-size:.88rem}
small{color:var(--text-3);font-weight:400}
.modal{position:fixed;inset:0;z-index:50;background:rgba(15,23,42,.5);display:grid;place-items:center;padding:16px}
.modal-okno{background:#fff;border-radius:18px;width:min(600px,100%);max-height:calc(100vh - 32px);overflow-y:auto;padding:28px;position:relative}
.modal-okno h2{margin:0 0 18px}
.zavriet{position:absolute;top:16px;right:16px;border:0;background:var(--pozadie);width:36px;height:36px;border-radius:50%;cursor:pointer}
.objednavka{border:1px solid var(--okraj);border-radius:12px;margin-bottom:10px;overflow:hidden}
.objednavka summary{display:grid;grid-template-columns:70px 1fr auto 120px;gap:16px;align-items:center;padding:14px 16px;cursor:pointer;list-style:none}
.objednavka summary::-webkit-details-marker{display:none}
.objednavka summary:hover,.objednavka[open] summary{background:var(--pozadie)}
.objednavka summary .stitok{justify-self:end}
.obj-cislo{font-weight:700;color:var(--text-2)}
.obj-meno{display:flex;flex-direction:column}.obj-meno small{font-size:.8rem}
.obj-detail{padding:16px;display:grid;gap:16px;border-top:1px solid var(--okraj)}
.obj-stlpce{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.obj-stlpce h4{margin:0 0 4px;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--text-3)}
.obj-stlpce p{margin:0;overflow-wrap:anywhere}
.obj-suhrn{display:flex;gap:20px;justify-content:flex-end;flex-wrap:wrap;color:var(--text-2)}
.obj-suhrn strong{color:var(--text)}
.obj-stav{display:flex;align-items:center;gap:10px;font-weight:600}
.obj-stav select{padding:8px 12px;border:1px solid var(--okraj);border-radius:10px;background:#fff}
.toasty{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:60;display:grid;gap:8px;width:min(420px,calc(100% - 32px))}
.toast{background:var(--text);color:#fff;padding:12px 16px;border-radius:12px;transition:opacity .3s,transform .3s}
.toast.chyba{background:var(--cervena)}.toast.von{opacity:0;transform:translateY(8px)}
@media(max-width:760px){
.dva-stlpce,.form .dva{grid-template-columns:1fr}
.obrazok-blok{grid-template-columns:1fr}
.objednavka summary{grid-template-columns:1fr auto}
.obj-cislo{display:none}
.lista-akcie{margin-left:0}
}
</style>
</head>
<body>
<header class="lista">
  <div class="obal lista-obsah">
    <div class="logo">🛠️ Administrácia<span>{{NAZOV}}</span></div>
    <nav class="taby" id="taby">
      <button data-tab="prehlad">Prehľad</button>
      <button data-tab="produkty">Produkty</button>
      <button data-tab="kupony">Zľavové kódy</button>
      <button data-tab="objednavky">Objednávky <span id="noveOdznak" class="odznak" hidden></span></button>
    </nav>
    <div class="lista-akcie"><a href="/" target="_blank" rel="noopener">Zobraziť obchod ↗</a><button id="odhlasit">Odhlásiť</button></div>
  </div>
</header>
 
<main class="obal">
  <section id="tab-prehlad" class="tab">
    <div class="statistiky" id="statistiky"></div>
    <div class="dva-stlpce">
      <div class="panel"><h2>Dochádza na sklade (3 ks a menej)</h2><div id="nizkySklad"></div></div>
      <div class="panel"><h2>Posledné objednávky</h2><div id="posledne"></div></div>
    </div>
  </section>
 
  <section id="tab-produkty" class="tab" hidden>
    <div class="panel">
      <div class="panel-hlava">
        <h2>Produkty</h2>
        <div class="nastroje"><input id="hladatProdukt" type="search" placeholder="Hľadať produkt…"><button class="btn" id="novyProdukt">+ Nový produkt</button></div>
      </div>
      <div class="tabulka-obal"><table>
        <thead><tr><th></th><th>Názov</th><th>Kategória</th><th class="vpravo">Cena</th><th class="vpravo">Sklad</th><th>Stav</th><th></th></tr></thead>
        <tbody id="produktyTelo"></tbody>
      </table></div>
    </div>
  </section>
 
  <section id="tab-kupony" class="tab" hidden>
    <div class="panel">
      <h2 id="kuponNadpis">Nový zľavový kód</h2>
      <form id="kuponForm" class="form riadok">
        <label>Kód<input name="kod" required maxlength="40" placeholder="LETO15" style="text-transform:uppercase"></label>
        <label>Typ zľavy<select name="typ"><option value="percent">Percentá (%)</option><option value="suma">Pevná suma (€)</option></select></label>
        <label>Hodnota<input name="hodnota" required placeholder="15" inputmode="decimal"></label>
        <label>Min. nákup (€)<input name="min_suma" value="0" inputmode="decimal"></label>
        <label class="check"><input type="checkbox" name="aktivny" checked> Aktívny</label>
        <div class="tlacidla"><button class="btn">Uložiť kód</button><button type="button" class="btn sekundarne" id="kuponZrus" hidden>Zrušiť úpravu</button></div>
      </form>
    </div>
    <div class="panel">
      <h2>Zľavové kódy</h2>
      <div class="tabulka-obal"><table>
        <thead><tr><th>Kód</th><th>Zľava</th><th>Min. nákup</th><th>Stav</th><th></th></tr></thead>
        <tbody id="kuponyTelo"></tbody>
      </table></div>
    </div>
  </section>
 
  <section id="tab-objednavky" class="tab" hidden>
    <div class="panel">
      <div class="panel-hlava">
        <h2>Objednávky</h2>
        <select id="filterStav" aria-label="Filtrovať podľa stavu">
          <option value="">Všetky stavy</option><option>nová</option><option>vybavuje sa</option><option>odoslaná</option><option>zrušená</option>
        </select>
      </div>
      <div id="objednavkyZoznam"></div>
    </div>
  </section>
</main>
 
<div id="modal" class="modal" hidden><div class="modal-okno" role="dialog" aria-modal="true">
  <button class="zavriet" data-zavriet-modal aria-label="Zavrieť">✕</button>
  <h2 id="modalNadpis">Nový produkt</h2>
  <form id="produktForm" class="form">
    <label>Názov<input name="nazov" required maxlength="100"></label>
    <div class="dva">
      <label>Kategória<input name="kategoria" list="zoznamKategorii" required maxlength="50" placeholder="napr. Ovocie"></label>
      <label>Cena (€)<input name="cena" required inputmode="decimal" placeholder="1,29"></label>
    </div>
    <div class="dva">
      <label>Počet kusov na sklade<input name="sklad" type="number" min="0" step="1" required></label>
      <label class="check"><input type="checkbox" name="aktivny"> Zobraziť v obchode</label>
    </div>
    <label>Popis <small>(nepovinné)</small><textarea name="popis" rows="3" maxlength="1000"></textarea></label>
    <div class="obrazok-blok">
      <img id="nahlad" alt="Náhľad obrázka">
      <div>
        <label>Nahrať obrázok z počítača<input type="file" name="subor" accept="image/jpeg,image/png,image/webp,image/gif"></label>
        <label>alebo odkaz na obrázok<input name="obrazok_url" placeholder="https://…"></label>
        <small>JPG, PNG, WEBP alebo GIF, najviac 5 MB. Ak pole s odkazom vymažete, obrázok sa odstráni.</small>
      </div>
    </div>
    <div class="tlacidla"><button class="btn" id="ulozitProdukt">Uložiť produkt</button><button type="button" class="btn sekundarne" data-zavriet-modal>Zrušiť</button></div>
  </form>
</div></div>
<datalist id="zoznamKategorii"></datalist>
<div id="toasty" class="toasty" aria-live="polite"></div>
 
<script>
const fmt = new Intl.NumberFormat('sk-SK', {style: 'currency', currency: 'EUR'});
const cena = c => fmt.format(c / 100);
const naEura = c => (c / 100).toFixed(2).replace('.', ',');
const esc = s => String(s ?? '').replace(/[&<>"']/g, z => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[z]));
const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const datum = t => new Date(t * 1000).toLocaleString('sk-SK', {dateStyle: 'medium', timeStyle: 'short'});
const $ = id => document.getElementById(id);
const PLACEHOLDER = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#e2e8f0"/><text x="50" y="62" font-size="36" text-anchor="middle">🖼️</text></svg>');
const STAVY = ['nová', 'vybavuje sa', 'odoslaná', 'zrušená'];
const TABY = ['prehlad', 'produkty', 'kupony', 'objednavky'];
 
let produkty = [], kupony = [], objednavky = [], upravovanyId = null;
 
async function api(url, moznosti = {}) {
  const o = {...moznosti};
  if (o.body !== undefined && !(o.body instanceof FormData)) {
    o.body = JSON.stringify(o.body); o.headers = {'Content-Type': 'application/json'};
  }
  const r = await fetch(url, o);
  if (r.status === 401) { location.reload(); throw new Error('Prihlásenie vypršalo.'); }
  let d = null;
  try { d = await r.json(); } catch (e) {}
  if (!r.ok) {
    if (d && typeof d.detail === 'string') throw new Error(d.detail);
    if (d && Array.isArray(d.detail) && d.detail.length) {
      const loc = d.detail[0].loc || [];
      throw new Error('Skontrolujte pole: ' + (loc[loc.length - 1] || '?'));
    }
    throw new Error('Nastala chyba. Skúste to znova.');
  }
  return d;
}
 
function toast(text, typ = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + typ; el.textContent = text;
  $('toasty').append(el);
  setTimeout(() => el.classList.add('von'), 2700);
  setTimeout(() => el.remove(), 3100);
}
 
document.addEventListener('error', e => {
  const t = e.target;
  if (t.tagName === 'IMG' && !t.dataset.nahrada) { t.dataset.nahrada = '1'; t.src = PLACEHOLDER; }
}, true);
 
// ---- taby ----
function prepniTab(t) {
  if (!TABY.includes(t)) t = 'prehlad';
  document.querySelectorAll('#taby [data-tab]').forEach(b => b.classList.toggle('aktivny', b.dataset.tab === t));
  document.querySelectorAll('.tab').forEach(s => s.hidden = s.id !== 'tab-' + t);
  history.replaceState(null, '', '#' + t);
}
$('taby').addEventListener('click', e => { const b = e.target.closest('[data-tab]'); if (b) prepniTab(b.dataset.tab); });
 
// ---- prehľad ----
function vykresliPrehlad() {
  const nizky = produkty.filter(p => p.aktivny && p.sklad <= 3).sort((a, b) => a.sklad - b.sklad);
  const nove = objednavky.filter(o => o.stav === 'nová').length;
  const trzby = objednavky.filter(o => o.stav !== 'zrušená').reduce((s, o) => s + o.spolu, 0);
  $('statistiky').innerHTML = [
    ['Produkty v obchode', produkty.filter(p => p.aktivny).length],
    ['Nové objednávky', nove],
    ['Objednávky spolu', objednavky.length],
    ['Tržby (bez zrušených)', cena(trzby)],
  ].map(([n, v]) => `<div class="stat"><span>${n}</span><strong>${v}</strong></div>`).join('');
  $('noveOdznak').textContent = nove;
  $('noveOdznak').hidden = !nove;
  $('nizkySklad').innerHTML = nizky.map(p =>
    `<div class="riadok-zoznam"><span>${esc(p.nazov)}</span><span class="stitok ${p.sklad ? 'oranzovy' : 'cerveny'}">${p.sklad} ks</span></div>`).join('')
    || '<p class="ticho">Všetky produkty sú dostatočne naskladnené.</p>';
  $('posledne').innerHTML = objednavky.slice(0, 6).map(o =>
    `<div class="riadok-zoznam"><span>#${o.id} · ${esc(o.meno)}</span><span>${cena(o.spolu)} <span class="stitok stav-${STAVY.indexOf(o.stav)}">${esc(o.stav)}</span></span></div>`).join('')
    || '<p class="ticho">Zatiaľ žiadne objednávky.</p>';
}
 
// ---- produkty ----
function vykresliProdukty() {
  const q = norm($('hladatProdukt').value.trim());
  const zoz = produkty.filter(p => !q || norm(p.nazov + ' ' + p.kategoria).includes(q));
  $('produktyTelo').innerHTML = zoz.map(p => `<tr>
    <td><img class="miniatura" src="${esc(p.obrazok || PLACEHOLDER)}" alt=""></td>
    <td><strong>${esc(p.nazov)}</strong>${p.popis ? `<div class="ticho mensie">${esc(p.popis.length > 60 ? p.popis.slice(0, 60) + '…' : p.popis)}</div>` : ''}</td>
    <td>${esc(p.kategoria)}</td>
    <td class="vpravo">${cena(p.cena)}</td>
    <td class="vpravo"><span class="stitok ${p.sklad === 0 ? 'cerveny' : p.sklad <= 3 ? 'oranzovy' : 'zeleny'}">${p.sklad} ks</span></td>
    <td>${p.aktivny ? '<span class="stitok zeleny">V obchode</span>' : '<span class="stitok">Skrytý</span>'}</td>
    <td class="akcie"><button class="btn male sekundarne" data-upravit="${p.id}">Upraviť</button><button class="btn male nebezpecne" data-zmazat="${p.id}">Zmazať</button></td>
  </tr>`).join('') || '<tr><td colspan="7" class="ticho">Žiadne produkty.</td></tr>';
  $('zoznamKategorii').innerHTML = [...new Set(produkty.map(p => p.kategoria))].map(k => `<option value="${esc(k)}">`).join('');
}
 
const pf = $('produktForm'), el = pf.elements;
function nahlad(src) { const i = $('nahlad'); delete i.dataset.nahrada; i.src = src || PLACEHOLDER; }
 
function otvorProdukt(p = null) {
  upravovanyId = p ? p.id : null;
  $('modalNadpis').textContent = p ? 'Upraviť produkt' : 'Nový produkt';
  pf.reset();
  el.nazov.value = p ? p.nazov : '';
  el.kategoria.value = p ? p.kategoria : '';
  el.cena.value = p ? naEura(p.cena) : '';
  el.sklad.value = p ? p.sklad : 0;
  el.aktivny.checked = p ? !!p.aktivny : true;
  el.popis.value = p ? p.popis : '';
  el.obrazok_url.value = p ? p.obrazok : '';
  nahlad(el.obrazok_url.value);
  $('modal').hidden = false;
  el.nazov.focus();
}
function zavriModal() { $('modal').hidden = true; }
 
el.subor.addEventListener('change', () => { const f = el.subor.files[0]; if (f) nahlad(URL.createObjectURL(f)); });
el.obrazok_url.addEventListener('input', () => { if (!el.subor.files.length) nahlad(el.obrazok_url.value.trim()); });
 
pf.addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData();
  for (const n of ['nazov', 'kategoria', 'cena', 'sklad', 'popis', 'obrazok_url']) fd.append(n, el[n].value);
  fd.append('aktivny', el.aktivny.checked ? 'true' : 'false');
  if (el.subor.files[0]) fd.append('obrazok', el.subor.files[0]);
  const btn = $('ulozitProdukt'), bolUpraveny = !!upravovanyId;
  btn.disabled = true;
  try {
    await api(bolUpraveny ? '/api/admin/produkty/' + upravovanyId : '/api/admin/produkty', {method: 'POST', body: fd});
    zavriModal();
    toast(bolUpraveny ? '✓ Produkt bol upravený.' : '✓ Produkt bol pridaný.');
    await nacitaj();
  } catch (err) { toast(err.message, 'chyba'); }
  finally { btn.disabled = false; }
});
 
$('produktyTelo').addEventListener('click', async e => {
  const u = e.target.closest('[data-upravit]');
  if (u) return otvorProdukt(produkty.find(p => p.id === +u.dataset.upravit));
  const z = e.target.closest('[data-zmazat]');
  if (!z) return;
  const p = produkty.find(x => x.id === +z.dataset.zmazat);
  if (!confirm(`Naozaj zmazať produkt „${p.nazov}“?\n\nTip: ak ho chcete len dočasne skryť, upravte ho a odškrtnite „Zobraziť v obchode“.`)) return;
  try { await api('/api/admin/produkty/' + p.id, {method: 'DELETE'}); toast('Produkt bol zmazaný.'); await nacitaj(); }
  catch (err) { toast(err.message, 'chyba'); }
});
$('novyProdukt').onclick = () => otvorProdukt();
$('hladatProdukt').addEventListener('input', vykresliProdukty);
$('modal').addEventListener('click', e => { if (e.target.id === 'modal' || e.target.closest('[data-zavriet-modal]')) zavriModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') zavriModal(); });
 
// ---- zľavové kódy ----
const kf = $('kuponForm'), kel = kf.elements;
function vykresliKupony() {
  $('kuponyTelo').innerHTML = kupony.map(k => `<tr>
    <td><code>${esc(k.kod)}</code></td>
    <td>${k.typ === 'percent' ? k.hodnota + ' %' : cena(k.hodnota)}</td>
    <td>${k.min_suma ? cena(k.min_suma) : '—'}</td>
    <td>${k.aktivny ? '<span class="stitok zeleny">Aktívny</span>' : '<span class="stitok">Neaktívny</span>'}</td>
    <td class="akcie"><button class="btn male sekundarne" data-upravit-kupon="${esc(k.kod)}">Upraviť</button><button class="btn male nebezpecne" data-zmazat-kupon="${esc(k.kod)}">Zmazať</button></td>
  </tr>`).join('') || '<tr><td colspan="5" class="ticho">Žiadne zľavové kódy.</td></tr>';
}
function resetKupon() {
  kf.reset(); kel.kod.readOnly = false;
  $('kuponNadpis').textContent = 'Nový zľavový kód'; $('kuponZrus').hidden = true;
}
$('kuponyTelo').addEventListener('click', async e => {
  const u = e.target.closest('[data-upravit-kupon]');
  if (u) {
    const k = kupony.find(x => x.kod === u.dataset.upravitKupon);
    kel.kod.value = k.kod; kel.kod.readOnly = true; kel.typ.value = k.typ;
    kel.hodnota.value = k.typ === 'percent' ? k.hodnota : naEura(k.hodnota);
    kel.min_suma.value = naEura(k.min_suma); kel.aktivny.checked = !!k.aktivny;
    $('kuponNadpis').textContent = 'Upraviť kód ' + k.kod; $('kuponZrus').hidden = false;
    kf.scrollIntoView({behavior: 'smooth', block: 'center'});
    return;
  }
  const z = e.target.closest('[data-zmazat-kupon]');
  if (!z || !confirm('Zmazať zľavový kód ' + z.dataset.zmazatKupon + '?')) return;
  try { await api('/api/admin/kupony/' + encodeURIComponent(z.dataset.zmazatKupon), {method: 'DELETE'}); toast('Kód bol zmazaný.'); resetKupon(); await nacitaj(); }
  catch (err) { toast(err.message, 'chyba'); }
});
kf.addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('/api/admin/kupony', {method: 'POST', body: {
      kod: kel.kod.value, typ: kel.typ.value, hodnota: kel.hodnota.value,
      min_suma: kel.min_suma.value || '0', aktivny: kel.aktivny.checked}});
    toast('✓ Zľavový kód bol uložený.');
    resetKupon();
    await nacitaj();
  } catch (err) { toast(err.message, 'chyba'); }
});
$('kuponZrus').onclick = resetKupon;
 
// ---- objednávky ----
function vykresliObjednavky() {
  const otvorene = new Set([...document.querySelectorAll('details.objednavka[open]')].map(d => +d.dataset.id));
  const f = $('filterStav').value;
  const zoz = objednavky.filter(o => !f || o.stav === f);
  $('objednavkyZoznam').innerHTML = zoz.map(o => `<details class="objednavka" data-id="${o.id}" ${otvorene.has(o.id) ? 'open' : ''}>
    <summary>
      <span class="obj-cislo">#${o.id}</span>
      <span class="obj-meno">${esc(o.meno)}<small class="ticho">${datum(o.vytvorene)}</small></span>
      <strong>${cena(o.spolu)}</strong>
      <span class="stitok stav-${STAVY.indexOf(o.stav)}">${esc(o.stav)}</span>
    </summary>
    <div class="obj-detail">
      <div class="obj-stlpce">
        <div><h4>Zákazník</h4><p>${esc(o.meno)}<br><a href="mailto:${esc(o.email)}">${esc(o.email)}</a>${o.telefon ? '<br>' + esc(o.telefon) : ''}</p></div>
        <div><h4>Doručenie</h4><p>${esc(o.adresa).replace(/\n/g, '<br>')}</p></div>
        ${o.poznamka ? `<div><h4>Poznámka</h4><p>${esc(o.poznamka)}</p></div>` : ''}
      </div>
      <div class="tabulka-obal"><table>
        <thead><tr><th>Produkt</th><th class="vpravo">Cena/ks</th><th class="vpravo">Ks</th><th class="vpravo">Spolu</th></tr></thead>
        <tbody>${o.polozky.map(p => `<tr><td>${esc(p.nazov)}</td><td class="vpravo">${cena(p.cena)}</td><td class="vpravo">${p.mnozstvo}</td><td class="vpravo">${cena(p.cena * p.mnozstvo)}</td></tr>`).join('')}</tbody>
      </table></div>
      <div class="obj-suhrn">
        <span>Medzisúčet: ${cena(o.medzisucet)}</span>
        ${o.zlava ? `<span>Zľava${o.kupon ? ' (' + esc(o.kupon) + ')' : ''}: −${cena(o.zlava)}</span>` : ''}
        <strong>Spolu: ${cena(o.spolu)}</strong>
      </div>
      <label class="obj-stav">Stav objednávky:
        <select data-stav="${o.id}" ${o.stav === 'zrušená' ? 'disabled' : ''}>${STAVY.map(s => `<option ${s === o.stav ? 'selected' : ''}>${s}</option>`).join('')}</select>
      </label>
    </div>
  </details>`).join('') || '<p class="ticho">Žiadne objednávky.</p>';
}
$('filterStav').addEventListener('change', vykresliObjednavky);
$('objednavkyZoznam').addEventListener('change', async e => {
  const s = e.target.closest('[data-stav]');
  if (!s) return;
  const o = objednavky.find(x => x.id === +s.dataset.stav);
  if (s.value === 'zrušená' && !confirm('Zrušiť objednávku #' + o.id + '?\nTovar sa vráti na sklad a zrušenie už nemožno vrátiť.')) { s.value = o.stav; return; }
  try { await api(`/api/admin/objednavky/${o.id}/stav`, {method: 'POST', body: {stav: s.value}}); toast('✓ Stav objednávky bol zmenený.'); await nacitaj(); }
  catch (err) { toast(err.message, 'chyba'); s.value = o.stav; }
});
 
// ---- načítanie ----
async function nacitaj() {
  [produkty, kupony, objednavky] = await Promise.all([
    api('/api/admin/produkty'), api('/api/admin/kupony'), api('/api/admin/objednavky')]);
  vykresliPrehlad(); vykresliProdukty(); vykresliKupony(); vykresliObjednavky();
}
$('odhlasit').onclick = async () => { await fetch('/admin/odhlasenie', {method: 'POST'}); location.reload(); };
 
prepniTab(location.hash.slice(1));
nacitaj().catch(err => toast(err.message, 'chyba'));
</script>
</body>
</html>"""
 
 
# Databáza sa pripraví hneď pri spustení
inicializuj_db()
 
