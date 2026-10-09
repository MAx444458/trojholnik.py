
• 🛒 Stránka obchodu (pre zákazníkov): http://127.0.0.1:8000
• 🛠️ Administračný panel (pre správu skladu): 127.0.0



# 1. KATEGÓRIE
ovocie = ["jablko", "banan", "hruska", "slivka", "pomaranc", "broskyna"]
zelenina = ["mrkva", "zemiak", "petrzlen", "celer"]
sladkosti = ["cokolada", "cukor"]


# 2. SKLAD
# nazov: (cena, kategoria, mnozstvo)

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


# 3. NAKUPNY KOSIK

nakupny_kosik = []


# 4. PRIDAVANIE POLOZIEK DO KOSIKA

while True:

    print("Co chcete pridat do kosika?")
    polozka = input().strip().lower()

    if polozka == "koniec":
        break

    if polozka in sklad:

        cena, kategoria, mnozstvo = sklad[polozka]

        if mnozstvo > 0:

            nakupny_kosik.append(polozka)

            # uberieme 1 kus zo skladu
            mnozstvo = mnozstvo - 1

            sklad[polozka] = (cena, kategoria, mnozstvo)

            print("Polozka bola pridana do kosika.")
            print("Zostava v sklade:", mnozstvo, "ks")

        else:

            print("Tato polozka je vypredana.")

    else:

        print("Takato polozka nie je v sklade.")


# 5. VYPIS NAKUPU A SPOCITANIE CENY

print("\n--- UCET ZA NAKUP ---")

celkova_suma = 0

for polozka in nakupny_kosik:

    cena, kategoria, mnozstvo = sklad[polozka]

    print(f"{polozka} - {cena} EUR, {kategoria}")

    celkova_suma = celkova_suma + cena


print("----------------------")
print(f"Celkovo dokopy: {celkova_suma} EUR")
print(f"Pocet poloziek: {len(nakupny_kosik)}")


# 6. ROZDELENIE POTRAVIN

print("\n--- ROZDELENIE POTRAVIN ---")

for polozka in nakupny_kosik:

    if polozka in ovocie:
        print(f"{polozka} je ovocie")

    elif polozka in zelenina:
        print(f"{polozka} je zelenina")

    elif polozka in sladkosti:
        print(f"{polozka} je sladkost")

    else:
        print(f"{polozka} je nieco ine")


# 7. ZOSTATOK V SKLADE

print("\n--- ZOSTATOK V SKLADE ---")

for polozka in sklad:

    cena, kategoria, mnozstvo = sklad[polozka]

    if mnozstvo > 0:
        print(f"{polozka} - {cena} EUR - {kategoria} - {mnozstvo} ks")

    else:
        print(f"{polozka} - VYPREDANE")


kupon = input("Mas kupon? (ano/nie): ").strip().lower()
if kupon == "ano":
    celkova_suma = celkova_suma * 0.8  # Aplikuj 20% zľavu
    print("Kupon bol pouzity. Celkova suma po zlave:", celkova_suma, "EUR")

print("celkova suma:", round(celkova_suma, 2), "EUR")


............................................................................................................................................................................


# 1. KATEGÓRIE
ovocie = ["jablko", "banan", "hruska", "slivka", "pomaranc", "broskyna"]
zelenina = ["mrkva", "zemiak", "petrzlen", "celer"]
sladkosti = ["cokolada", "cukor"]


# 2. SKLAD
# nazov: (cena, kategoria, mnozstvo)
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


# --- NOVE FUNKCIE ---

def vypis_ucet_a_kategorie(kosik, sklad_dat):
    """Vytlačí detailný účet a rozdelí nakúpené potraviny do kategórií."""
    print("\n--- UCET ZA NAKUP ---")
    suma = 0
    for polozka in kosik:
        cena, kategoria, mnozstvo = sklad_dat[polozka]
        print(f"{polozka} - {cena} EUR, {kategoria}")
        suma = suma + cena

    print("----------------------")
    print(f"Celkovo dokopy: {suma} EUR")
    print(f"Pocet poloziek: {len(kosik)}")

    print("\n--- ROZDELENIE POTRAVIN ---")
    for polozka in kosik:
        if polozka in ovocie:
            print(f"{polozka} je ovocie")
        elif polozka in zelenina:
            print(f"{polozka} je zelenina")
        elif polozka in sladkosti:
            print(f"{polozka} je sladkost")
        else:
            print(f"{polozka} je nieco ine")
            
    return suma


def vypocitaj_konecnu_sumu(zakladna_suma):
    """Opýta sa na kupón, aplikuje zľavu a vráti zaokrúhlenú konečnú sumu."""
    kupon = input("Mas kupon? (ano/nie): ").strip().lower()
    if kupon == "ano":
        zakladna_suma = zakladna_suma * 0.8  # Aplikuj 20% zľavu
        print("Kupon bol pouzity. Celkova suma po zlave:", zakladna_suma, "EUR")
    
    return round(zakladna_suma, 2)


# 3. NAKUPNY KOSIK
nakupny_kosik = []


# 4. PRIDAVANIE POLOZIEK DO KOSIKA
while True:
    print("Co chcete pridat do kosika?")
    polozka = input().strip().lower()

    if polozka == "koniec":
        break

    if polozka in sklad:
        cena, kategoria, mnozstvo = sklad[polozka]

        if mnozstvo > 0:
            nakupny_kosik.append(polozka)

            # uberieme 1 kus zo skladu
            mnozstvo = mnozstvo - 1
            sklad[polozka] = (cena, kategoria, mnozstvo)

            print("Polozka bola pridana do kosika.")
            print("Zostava v sklade:", mnozstvo, "ks")
        else:
            print("Tato polozka je vypredana.")
    else:
        print("Takato polozka nie je v sklade.")


# 5. a 6. (Cez funkciu)
celkova_suma = vypis_ucet_a_kategorie(nakupny_kosik, sklad)


# KUPÓN A ZAOKRÚHLENIE (Cez funkciu)
konecna_suma = vypocitaj_konecnu_sumu(celkova_suma)
print("celkova suma:", konecna_suma, "EUR")


# 7. ZOSTATOK V SKLADE
print("\n--- ZOSTATOK V SKLADE ---")
for polozka in sklad:
    cena, kategoria, mnozstvo = sklad[polozka]

    if mnozstvo > 0:
        print(f"{polozka} - {cena} EUR - {kategoria} - {mnemis_obsah} - {mnozstvo} ks")
    else:
        print(f"{polozka} - VYPREDANE")


............................................................................................................................................................................................................




from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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
            "kategoria": kategoria,
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

