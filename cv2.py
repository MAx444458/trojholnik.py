#kategorie 
    ovocie: = ["jablko" , "banan" , "hruska" , "slivka" , "pomaranc" , "broskyna"],
    zelenina = ["mrkva" , "zemiak" , "petrzlen" , "celer"],
    sladkosti = ["cokolada" , "cukor"]

sklad = {
    "jablko": (1.0, "ovocie", 1000),
    "banan": (2.0, "ovocie", 20),
    "mlieko": (1.2, "ovocie", 1)
    }
             
#kosik
nakupny_kosik = ["jablko" , "mlieko" , "cokolada" , "chlieb" , "banan" , "cukor"]

pocet = int(input("kolko veci chcete pridat do kosika?\n"))
while pocet:
        print("co chcete pridat?")
        nazov = input().strip().lower()

while True:
    print("vloz polozku do kosika")
    polozka = input()

    if nazov in produkty:
        nakupny_kosik.append(nazov)
        pocet -=1
        else:
        print("takato polozka nie je v zozname.") 


    for polozka in nakupny_kosik:
        cena, kategoria = produkty[polozka]
        print(f"{polozka} - {cena} EUR, {kategoria}, - {mnozstvo} ks")
        print(polozka)


    for i in range(0, 3):
        print ("co chcte pridat do kosika?")
        nova_polozka = input()
        nakupny_kosik.append(nova_polozka)


    for polozka in nakupny_kosik:
        if polozka in ovocie:
            print(f"{polozka} je ovocie")
        elif polozka in zelenina:
            print(f"{polozka} je zelenina")
        else:
            print(f"{polozka} je nieco ine")





.........................................................................................................................................................................................




    # 1. Kategórie
    ovocie = ["jablko", "banan", "hruska", "slivka", "pomaranc", "broskyna"]
    zelenina = ["mrkva", "zemiak", "petrzlen", "celer"]
    sladkosti = ["cokolada", "cukor"]

    # 2. Cenník
    cennik = {
        "jablko": (0.5, "ovocie"), "banan": (1.2, "ovocie"), "hruska": (0.8, "ovocie"), "slivka": (0.3, "ovocie"),
        "pomaranc": (0.6, "ovocie"), "broskyna": (0.9, "ovocie"), "mrkva": 0.4, "zemiak": 0.2, 
        "petrzlen": 0.5, "celer": 0.7, "cokolada": 1.5, "cukor": 1.0, 
        "mlieko": 1.3, "chlieb": 2.0
    }

    # 3. Základný nákupný košík
    nakupny_kosik = ["jablko", "mlieko", "cokolada", "chlieb", "banan", "cukor"]

    # 4. Prvé 3 položky
    for i in range(0, 3):
        print("Co chcete pridat do kosika?")
        nova_polozka = input()
        nakupny_kosik.append(nova_polozka)

    # 5. Pridávanie položiek, kým nenapíšete 'nic' alebo 'koniec'
    while True:
        print("Co chcete pridat do kosika?")
        vstup = input()
        if vstup == "nic" or vstup == "koniec":
            break
        else:
            nakupny_kosik.append(vstup)

    # 6. VÝPIS CIEN A SPOČÍTANIE DOKOPY
    print("\n--- UCET ZA NAKUP ---")
    celkova_suma = 0

    for polozka in nakupny_kosik:
        cena = cennik.get(polozka, 0.0) 
        celkova_suma += cena
        print(f"{polozka} - cena: {cena} €")

    print(f"Celkovo dokopy: {celkova_suma} €\n")

    # 7. ROZTRIEDENIE DO KATEGÓRIÍ
    print("--- ROZDELENIE POTRAVIN ---")
    for polozka in nakupny_kosik:
        if polozka in ovocie:
            print(f"{polozka} je ovocie")
        elif polozka in zelenina:
            print(f"{polozka} je zelenina")
        elif polozka in sladkosti:
            print(f"{polozka} je sladkost")
        else:
            print(f"{polozka} je nieco ine")







.........................................................................................................................................................................................








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
```
