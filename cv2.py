#kategorie
ovocie = ["jablko" , "banan" , "hruska" , "slivka" , "pomaranc" , "broskyna"]
zelenina = ["mrkva" , "zemiak" , "petrzlen" , "celer"]
sladkosti = ["cokolada" , "cukor"]

#kosik
nakupny_kosik = ["jablko" , "mlieko" , "cokolada" , "chlieb" , "banan" , "cukor" , nova_polozka]


for i in range(0, 3):
    print ("co chcte pridat do kosika?")
    nova_polozka = input()
    nakupny_kosik.append(nova_polozka)

    while True:
        print("co chcete pridat do kodika?")
        vstup = input()
        if vstup == "un nic" or vstup == "koniec":
            break
        else:
            nakupny_kosik.append(vstup)
    for polozka in nakupny_kosik:
        print(polozka)

print("kolko veci mam kupit?")


for polozka in nakupny_kosik:
    if polozka in ovocie:
        print(f"{polozka} je ovocie")
    elif polozka in zelenina:
        print(f"{polozka} je zelenina")
    else:
        print(f"{polozka} je nieco ine")


















# 1. Kategórie
ovocie = ["jablko", "banan", "hruska", "slivka", "pomaranc", "broskyna"]
zelenina = ["mrkva", "zemiak", "petrzlen", "celer"]
sladkosti = ["cokolada", "cukor"]

# 2. Cenník
cennik = {
    "jablko": 0.5, "banan": 1.2, "hruska": 0.8, "slivka": 0.3, 
    "pomaranc": 0.6, "broskyna": 0.9, "mrkva": 0.4, "zemiak": 0.2, 
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
