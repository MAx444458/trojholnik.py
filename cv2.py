


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


