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
