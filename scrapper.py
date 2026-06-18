from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import csv
import time
import pandas as pd
import os
import re

# ==========================================
# CONFIGURATION GLOBALE
# ==========================================
HEADLESS = False
MAX_SCROLL = 15
MAX_RETRIES = 3
RETRY_DELAY = 5

SELECTORS_VOIR_PLUS = {
    "decathlon":   "",
    "intersport":  "button.btn--load-more, button[class*='loadMore'], a[class*='load-more']",
    "jdsports":    "button#loadMore, button[data-e2e='loadmore']",
    "sport2000":   "button[data-action*='show-more'], a[data-action*='show-more'], button.more",
    "alltricks":   "button[class*='showMore'], button[class*='ShowMore'], a[class*='showMore']",
    "zalando":     "",
    "irun":        "a.c-pagination__link--next, a[rel='next']",
}

MARQUES_CONNUES = {
    "ADIDAS", "NIKE", "PUMA", "REEBOK", "ASICS", "NEW BALANCE", "UNDER ARMOUR",
    "LACOSTE", "FRED PERRY", "FILA", "ELLESSE", "CHAMPION", "UMBRO", "LOTTO",
    "HUMMEL", "KAPPA", "JOMA", "ERIMA", "MIZUNO", "BROOKS", "SAUCONY", "HOKA",
    "COLUMBIA", "THE NORTH FACE", "SALOMON", "SCOTT", "CRAFT", "ODLO", "VAUDE",
    "MAMMUT", "MILLET", "ORTOVOX", "PATAGONIA", "ARC'TERYX", "GORE",
    "JACK WOLFSKIN", "CMP", "ICEPEAK", "KILLTEC", "REGATTA", "BERGHAUS",
    "DARE2B", "TRESPASS", "PEAK PERFORMANCE", "LÖFFLER",
    "KIPSTA", "KALENJI", "QUECHUA", "DOMYOS", "NABAIJI", "TRIBORD", "BTWIN",
    "KIPRUN", "FORCLAZ", "TARMAK", "WEDZE", "SOLOGNAC", "ARTENGO", "INESIS", "FOUGANZA",
    "OLAIAN", "SIMOND", "CAPERLAN", "GEOLOGIC", "SUBEA", "NYAMBA", "ROCKRIDER",
    "CASTELLI", "RAPHA", "POC", "MAVIC", "PEARL IZUMI", "SUGOI", "BIORACER",
    "SANTINI", "ENDURA", "SPORTFUL", "SHIMANO", "NALINI",
    "ORCA", "TYR", "SPEEDO", "ARENA", "ZOGGS", "2XU", "COMPRESSPORT", "SKINS",
    "X-BIONIC", "FALKE", "CEP",
    "JORDAN", "CONVERSE", "VANS", "TIMBERLAND", "QUIKSILVER", "BILLABONG",
    "ROXY", "VOLCOM", "ELEMENT", "CARHARTT", "DICKIES", "LEVIS", "LEVI'S",
    "SUPERDRY", "PROTEST", "O'NEILL", "RIP CURL", "BRUNOTTI",
    "PEGADOR", "KARL KANI", "VON DUTCH", "WASTED PARIS", "WAX LONDON",
    "WOOD WOOD", "OBEY", "HUF", "FUBU", "KANGOL", "PRIMITIVE", "SEAN JOHN",
    "WRSTBHVR", "PEQUS", "STAPLE", "MARKET", "AAPE", "HEAD",
}

CHAMPS = ["Marque", "Titre", "Prix Actuel", "Note", "Coloris", "Source"]


# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def extraire_marque_du_titre(titre):
    titre_upper = titre.upper()
    mots = titre_upper.split()
    if len(mots) >= 2:
        candidate = f"{mots[0]} {mots[1]}"
        if candidate in MARQUES_CONNUES:
            titre_propre = titre[len(candidate):].strip().strip(',').strip()
            return candidate.title(), titre_propre
    if mots and mots[0] in MARQUES_CONNUES:
        marque = mots[0]
        titre_propre = titre[len(marque):].strip().strip(',').strip()
        return marque.title(), titre_propre
    return "Inconnu", titre


def scroller_page(page, nb_scrolls=MAX_SCROLL, delai=1.5):
    """Scroll robuste : absorbe les navigations inattendues (context destroyed)."""
    try:
        derniere_hauteur = page.evaluate("document.body.scrollHeight")
    except Exception:
        return
    for i in range(nb_scrolls):
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(delai)
            nouvelle_hauteur = page.evaluate("document.body.scrollHeight")
            if nouvelle_hauteur == derniere_hauteur and i > 2:
                break
            derniere_hauteur = nouvelle_hauteur
        except Exception:
            break  # Contexte détruit → on sort proprement


def cliquer_voir_plus(page, selecteurs, site="", max_clics=15):
    if not selecteurs.strip():
        return 0
    clics = 0
    while clics < max_clics:
        clique = False
        for sel in selecteurs.split(','):
            sel = sel.strip()
            try:
                bouton = page.locator(sel).first
                if bouton.is_visible(timeout=3500):
                    bouton.scroll_into_view_if_needed()
                    bouton.click()
                    time.sleep(2)
                    clics += 1
                    clique = True
                    break
            except Exception:
                continue
        if not clique:
            break
    if clics == 0 and selecteurs.strip():
        print(f"  ⚠️ [{site}] Bouton 'Voir plus' introuvable — seule la 1ère page a été chargée.")
    return clics


def _goto_avec_retry(page, url, wait_until="domcontentloaded", site="", timeout=45000):
    for tentative in range(1, MAX_RETRIES + 1):
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout)
            return True
        except Exception as e:
            if tentative < MAX_RETRIES:
                print(f"  ⚠️ [{site}] Tentative {tentative}/{MAX_RETRIES} échouée ({e}). "
                      f"Nouvelle tentative dans {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  ❌ [{site}] {url} — abandon après {MAX_RETRIES} tentatives : {e}")
    return False


def _ecrire_csv(chemin, donnees):
    with open(chemin, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=CHAMPS, delimiter=';')
        writer.writeheader()
        writer.writerows(donnees)


def _nettoyer_prix(texte):
    return "".join(
        c for c in texte.replace('€', '').replace(',', '.').replace('\xa0', '').strip()
        if c.isdigit() or c == '.'
    )


# ==========================================
# [1/7] ZALANDO
# ==========================================
def scrape_zalando():
    URLS = [
        "https://www.zalando.fr/mode-homme/",
        "https://www.zalando.fr/mode-femme/",
        "https://www.zalando.fr/mode-enfant/?gender=4",
        "https://www.zalando.fr/mode-enfant/?gender=2",
        "https://www.zalando.fr/mode-enfant/?gender=1",
        "https://www.zalando.fr/mode-enfant/?gender=3",
        "https://www.zalando.fr/vetements-enfant/",
        (
            "https://www.zalando.fr/mode-enfant/032c.aape.adererror.adidas-originals.barbour-beacon."
            "barbour-international.carhartt.champion-reverse-weave.champion-rochester.cleptomanicx."
            "columbia.converse-online-shop.cp-company.dickies.edwin.element.etudes.filling-pieces."
            "fubu.han-kjobenhavn.huf.jordan.kangol.karl-kani.kavu.koche.lacoste-live.levis."
            "levis-made-crafted.levis-plus.levisr-skateboarding.levisr-workwear.libertine-libertine."
            "market.martin-asbjorn.new-balance.nike-sb.nike-sportswear.nikolaj-storm.nm-sense.nudie."
            "obey-clothing.oftt.on-vacation.pegador.pequs.primitive.puma.quiksilver.santa-cruz."
            "sean-john-1.staple-pigeon.the-north-face.vans.volcom.von-dutch.wasted-paris.wax-london."
            "wood-wood.wrstbhvr.you-must-create/?order=activation_date"
        ),
        "https://www.zalando.fr/vetements-enfant-luxe/",
        # URL seconde main supprimee (titres inexploitables)
        # "https://www.zalando.fr/vetements-seconde-main-enfant/",
    ]
    OUTPUT_FILE = "zalando_vetements_clean.csv"
    SITE = "Zalando"
    print(f"\n[1/7] Démarrage {SITE} (jamais testé — en premier)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_zalando_profile",
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for url in URLS:
            print(f"  -> {url}")
            if not _goto_avec_retry(page, url, wait_until="domcontentloaded", site=SITE):
                continue
            time.sleep(3)
            scroller_page(page, delai=2.0)

            try:
                soup = BeautifulSoup(page.content(), 'html.parser')
                articles = soup.find_all('article')
                for art in articles:
                    header = art.find('header')
                    if not header:
                        continue
                    h3 = header.find('h3')
                    spans = h3.find_all('span') if h3 else []
                    if len(spans) < 2:
                        continue
                    brand = spans[0].text.strip()
                    title = spans[1].text.strip()

                    # Fix : ignorer les articles sans vrai titre
                    if title.lower() in ("seconde main", ""):
                        continue

                    cle = (brand.upper(), title.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    current_price = ""
                    price_section = header.find('section')
                    if price_section:
                        prices = re.findall(r'(\d+[\.,]\d+)', price_section.text)
                        if prices:
                            current_price = prices[0].replace(',', '.')

                    products_data.append({
                        "Marque": brand, "Titre": title,
                        "Prix Actuel": current_price, "Note": "",
                        "Coloris": "1 couleur", "Source": SITE,
                    })
            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
        ctx.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# [2/7] I-RUN
# ==========================================
def scrape_irun():
    URLS = [
        "https://www.i-run.fr/vetement_sport_homme/",
        "https://www.i-run.fr/vetement_sport_femme/",
    ]
    OUTPUT_FILE = "irun_vetements_clean.csv"
    SITE = "i-Run"
    print(f"\n[2/7] Démarrage {SITE} (jamais testé — en deuxième)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_irun_profile",
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for url in URLS:
            print(f"  -> {url}")
            if not _goto_avec_retry(page, url, wait_until="domcontentloaded", site=SITE):
                continue
            time.sleep(3)

            scroller_page(page, nb_scrolls=5, delai=1.8)
            cliquer_voir_plus(page, SELECTORS_VOIR_PLUS["irun"], site=SITE, max_clics=15)
            scroller_page(page)

            try:
                soup = BeautifulSoup(page.content(), 'html.parser')
                articles = soup.find_all('article', class_=lambda x: x and 'c-productCard' in x)

                for art in articles:
                    brand_elem = art.find('div', class_='c-productCard__brandName')
                    brand = brand_elem.text.strip() if brand_elem else "i-Run"

                    title_elem = art.find('div', class_='c-productCard__productName')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()

                    cle = (brand.upper(), title.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    current_price = ""
                    price_elem = art.find('span', class_='c-productCard__currentPrice')
                    if price_elem:
                        current_price = _nettoyer_prix(price_elem.text)

                    rating = ""
                    rating_elem = art.find('span', class_='c-ranking')
                    if rating_elem:
                        span_val = rating_elem.find('span')
                        if span_val:
                            rating = "".join(
                                c for c in span_val.text.replace(',', '.').strip()
                                if c.isdigit() or c == '.'
                            )

                    products_data.append({
                        "Marque": brand, "Titre": title,
                        "Prix Actuel": current_price, "Note": rating,
                        "Coloris": "1 couleur", "Source": SITE,
                    })
            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
        ctx.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# [3/7] INTERSPORT
# ==========================================
def scraper_intersport():
    URLS = [
        "https://www.intersport.fr/sportswear/homme/survetements/",
        "https://www.intersport.fr/sportswear/homme/hauts/",
        "https://www.intersport.fr/sportswear/homme/bas/",
        "https://www.intersport.fr/sportswear/femme/hauts/",
        "https://www.intersport.fr/sportswear/femme/bas/",
        "https://www.intersport.fr/sportswear/garcon/hauts/",
        "https://www.intersport.fr/sportswear/garcon/bas/",
        "https://www.intersport.fr/sportswear/garcon/survetements/",
        "https://www.intersport.fr/sportswear/fille/hauts/",
        "https://www.intersport.fr/sportswear/fille/bas/",
        "https://www.intersport.fr/sportswear/fille/survetements/",
        "https://www.intersport.fr/sportswear/bebe/bebe-fille/vetements/",
        "https://www.intersport.fr/sportswear/bebe/bebe-garcon/vetements/",
    ]
    OUTPUT_FILE = "intersport_vetements.csv"
    SITE = "Intersport"
    print(f"\n[3/7] Démarrage {SITE} (corrigé : ChromeDriver → Playwright)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_intersport_data",
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-gpu",
            ],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for url in URLS:
            print(f"  -> {url}")
            if not _goto_avec_retry(page, url, wait_until="domcontentloaded", site=SITE):
                continue
            time.sleep(4)

            scroller_page(page, nb_scrolls=8, delai=1.5)
            cliquer_voir_plus(page, SELECTORS_VOIR_PLUS["intersport"], site=SITE)
            scroller_page(page, nb_scrolls=5, delai=1.5)

            try:
                soup = BeautifulSoup(page.content(), "html.parser")
                for produit in soup.find_all("div", class_="product-box"):
                    titre_tag = produit.find("div", class_="product-box__name")
                    marque_tag = produit.find("div", class_="product-box__brand")
                    if not titre_tag or not marque_tag:
                        continue

                    titre = titre_tag.text.strip()
                    marque = marque_tag.text.strip()
                    cle = (marque.upper(), titre.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    prix_actuel = ""
                    prix_container = produit.find("div", class_="product-box__price")
                    if prix_container:
                        px = (prix_container.find("span", class_="product-box__price--alert")
                              or prix_container.find("span"))
                        if px:
                            prix_actuel = _nettoyer_prix(px.text)

                    # Fix : 0 etoile = pas de note (pas "note 0/5")
                    nb_etoiles = len(produit.find_all("span", class_="circle --completed"))
                    note = nb_etoiles if nb_etoiles > 0 else ""
                    couleurs_tag = produit.find("div", class_="product-box__various-colors")
                    couleurs = couleurs_tag.text.strip() if couleurs_tag else "1 couleur"

                    products_data.append({
                        "Marque": marque, "Titre": titre,
                        "Prix Actuel": prix_actuel, "Note": note,
                        "Coloris": couleurs, "Source": SITE,
                    })
            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
        ctx.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# [4/7] SPORT 2000
# ==========================================
def scrape_sport2000():
    URLS = [
        "https://www.sport2000.fr/landing-page/selection-vetements-homme",
        "https://www.sport2000.fr/landing-page/selection-vetements-de-sport-femme",
        "https://www.sport2000.fr/landing-page/selection-vetements-garcon",
        "https://www.sport2000.fr/taxons/sport-2000/selection-enfant-sport-2000/selection-filles/vetements-filles",
    ]
    OUTPUT_FILE = "sport2000_vetements_clean.csv"
    SITE = "Sport 2000"
    print(f"\n[4/7] Démarrage {SITE} (corrigé : networkidle → commit, timeout 60s)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_sport2000_data",
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
            ],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for url in URLS:
            print(f"  -> {url}")
            ok = _goto_avec_retry(
                page, url,
                wait_until="commit",   # ← CORRIGÉ (était "networkidle")
                site=SITE,
                timeout=60000,         # ← 60s au lieu de 30s
            )
            if not ok:
                continue

            time.sleep(6)  # Laisser le JS charger les produits
            scroller_page(page, nb_scrolls=8, delai=1.5)
            cliquer_voir_plus(page, SELECTORS_VOIR_PLUS["sport2000"], site=SITE)
            scroller_page(page, nb_scrolls=5, delai=1.2)

            try:
                soup = BeautifulSoup(page.content(), 'html.parser')
                articles = soup.find_all('div', class_=lambda x: x and 'mini-product' in x)
                articles = [a for a in articles if a.find('div', class_='mini-product__inner')]

                for art in articles:
                    brand_elem = art.find('p', class_='mini-product__brand')
                    brand = brand_elem.text.strip() if brand_elem else "Sport 2000"

                    title_elem = art.find('a', class_='mini-product__name')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()

                    cle = (brand.upper(), title.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    current_price = ""
                    price_elem = art.find('span', class_=lambda x: x and 'mini-product__price-current' in x)
                    if price_elem:
                        current_price = _nettoyer_prix(price_elem.text)

                    products_data.append({
                        "Marque": brand, "Titre": title,
                        "Prix Actuel": current_price, "Note": "",
                        "Coloris": "1 couleur", "Source": SITE,
                    })
            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
        ctx.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# [5/7] ALLTRICKS
# ==========================================
def scrape_alltricks():
    URLS = [
        "https://www.alltricks.fr/C-40759-vetements-vtt",
        "https://www.alltricks.fr/C-102720-vetements-route",
        "https://www.alltricks.fr/C-1375904-textile-gravel",
        "https://www.alltricks.fr/C-41003-textile--ville",
        "https://www.alltricks.fr/C-2128307-vetements-chaussures-enfant-ville",
        "https://www.alltricks.fr/C-41167-textile-bmx",
        "https://www.alltricks.fr/C-153691-vetements-homme",
        "https://www.alltricks.fr/C-153694-vetements-femme",
        "https://www.alltricks.fr/C-3142941-vetements-running-enfants",
        "https://www.alltricks.fr/C-223834-vetements-randonnee-homme",
        (
            "https://www.alltricks.fr/C-41314-combinaisons-neoprenes-trifonctions/"
            "NW-7509-type-de-produit~combinaison-neoprene/NW-7509-type-de-produit~combinaison-trifonction/"
            "NW-7509-type-de-produit~combinaison-swimrun/NW-7509-type-de-produit~combinaison-aero/"
            "NW-7509-type-de-produit~combinaison-de-sport/NW-7509-type-de-produit~haut-neoprene/"
            "NW-7509-type-de-produit~bas-neoprene/NW-7509-type-de-produit~combinaison-eau-libre/"
            "NW-7509-type-de-produit~combinaison-non-neoprene/NW-7509-type-de-produit~t-shirt-de-bain"
        ),
        "https://www.alltricks.fr/C-1583629-vetements-natation",
        "https://www.alltricks.fr/C-1955202-vetements-alpinisme",
        "https://www.alltricks.fr/C-1645911-t_shirt-veste-doudoune-escalade",
        (
            "https://www.alltricks.fr/C-2284276-textile-cycliste-triathlon/"
            "NW-7509-type-de-produit~maillot-de-sport/NW-7509-type-de-produit~cuissard-court-(velo)/"
            "NW-7509-type-de-produit~veste-de-sport/NW-7509-type-de-produit~cuissard-long-(velo)/"
            "NW-7509-type-de-produit~combinaison-trifonction/NW-7509-type-de-produit~brassiere/"
            "NW-7509-type-de-produit~cuissard-3-4-(velo)/NW-7509-type-de-produit~debardeur/"
            "NW-7509-type-de-produit~combinaison-aero/NW-7509-type-de-produit~combinaison-de-sport/"
            "NW-7509-type-de-produit~combinaison-neoprene/NW-7509-type-de-produit~combinaison-swimrun/"
            "NW-7509-type-de-produit~collant-long/NW-7509-type-de-produit~pantalon-(sport)"
        ),
        "https://www.alltricks.fr/C-2796097-ironman/NW-16498-genre~homme",
        "https://www.alltricks.fr/C-2796097-ironman/NW-16498-genre~femme",
        "https://www.alltricks.fr/C-2184856-textile-bas-velo-reconditionne",
        "https://www.alltricks.fr/C-2184855-textile-haut-velo-reconditionne",
        "https://www.alltricks.fr/C-2184869-vetements-running-seconde-vie",
        "https://www.alltricks.fr/C-2184872-textile-outdoor-seconde-vie",
    ]
    OUTPUT_FILE = "alltricks_vetements_clean.csv"
    SITE = "Alltricks"
    print(f"\n[5/7] Démarrage {SITE} (corrigé : page isolée par URL)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-gpu"],
        )

        for url in URLS:
            print(f"  -> {url}")
            # Clé du fix : nouvelle page par URL → jamais de context destroyed
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
            )
            try:
                if not _goto_avec_retry(page, url, wait_until="domcontentloaded", site=SITE):
                    page.close()
                    continue
                time.sleep(3)

                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                scroller_page(page, nb_scrolls=5, delai=1.5)
                cliquer_voir_plus(page, SELECTORS_VOIR_PLUS["alltricks"], site=SITE, max_clics=20)
                scroller_page(page, nb_scrolls=5, delai=1.5)

                soup = BeautifulSoup(page.content(), 'html.parser')
                articles = soup.find_all('div', class_=lambda x: x and 'productCard' in x)

                for art in articles:
                    brand_elem = art.find('strong', class_='productCard_brandLabel')
                    brand = brand_elem.text.strip() if brand_elem else "Alltricks"

                    title_elem = art.find('a', class_='productCard_description')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()

                    cle = (brand.upper(), title.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    current_price = ""
                    price_elem = art.find('span', class_=lambda x: x and 'productCard_actualPrice' in x)
                    if price_elem:
                        current_price = _nettoyer_prix(price_elem.text)

                    rating = ""
                    rating_elem = art.find('span', class_='productCard_review_score')
                    if rating_elem:
                        rating = rating_elem.text.split('/')[0].replace(',', '.').strip()

                    products_data.append({
                        "Marque": brand, "Titre": title,
                        "Prix Actuel": current_price, "Note": rating,
                        "Coloris": "1 couleur", "Source": SITE,
                    })

            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
            finally:
                page.close()  # Fermeture propre systématique

        browser.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# [6/7] JD SPORTS
# ==========================================
def scrape_jdsports():
    URLS = [
        "https://www.jdsports.fr/homme/vetements-homme/",
        "https://www.jdsports.fr/femme/vetements-femme/",
        "https://www.jdsports.fr/enfant/gender/garons/c/vtements/",
        "https://www.jdsports.fr/enfant/gender/filles/c/vtements/",
        "https://www.jdsports.fr/enfant/vetements-junior-(8-15-ans)/",
        "https://www.jdsports.fr/enfant/vetements-enfant-(3-7-ans)/",
        "https://www.jdsports.fr/enfant/vetements-bebe-(0-3-ans)/",
    ]
    OUTPUT_FILE = "jdsports_vetements_clean.csv"
    SITE = "JD Sports"
    print(f"\n[6/7] Démarrage {SITE} (✅ confirmé OK — en avant-dernier)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0")

        for url in URLS:
            print(f"  -> {url}")
            if not _goto_avec_retry(page, url, wait_until="domcontentloaded", site=SITE):
                continue
            time.sleep(3)

            scroller_page(page, nb_scrolls=5, delai=1.5)
            cliquer_voir_plus(page, SELECTORS_VOIR_PLUS["jdsports"], site=SITE)
            scroller_page(page)

            try:
                soup = BeautifulSoup(page.content(), 'html.parser')
                articles = soup.find_all('li', class_=lambda x: x and 'productListItem' in x)

                for art in articles:
                    title_elem = art.find('span', class_='itemTitle')
                    if not title_elem:
                        continue
                    brand, title = extraire_marque_du_titre(title_elem.text.strip())

                    cle = (brand.upper(), title.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    current_price = ""
                    price_elem = art.find('span', class_='pri')
                    if price_elem:
                        current_price = _nettoyer_prix(price_elem.text)

                    products_data.append({
                        "Marque": brand, "Titre": title,
                        "Prix Actuel": current_price, "Note": "",
                        "Coloris": "1 couleur", "Source": SITE,
                    })
            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
        browser.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# [7/7] DECATHLON
# ==========================================
def scrape_decathlon():
    URLS = [
        "https://www.decathlon.fr/homme/vetements",
        "https://www.decathlon.fr/femme/vetements",
        "https://www.decathlon.fr/enfant-bebe/vetements-garcon-s",
        "https://www.decathlon.fr/enfant-bebe/vetements-fille",
        "https://www.decathlon.fr/enfant-bebe/vetements-bebe",
        "https://www.decathlon.fr/femme/vetements-sportswear",
        "https://www.decathlon.fr/homme/vetements-sportswear",
    ]
    OUTPUT_FILE = "decathlon_vetements_clean.csv"
    SITE = "Decathlon"
    print(f"\n[7/7] Démarrage {SITE} (✅ confirmé OK — en dernier)...")
    products_data = []
    vus = set()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_user_data",
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for url in URLS:
            print(f"  -> {url}")
            if not _goto_avec_retry(page, url, wait_until="commit", site=SITE):
                continue
            time.sleep(3)
            scroller_page(page)

            try:
                soup = BeautifulSoup(page.content(), 'html.parser')
                articles = soup.find_all('article', class_=lambda x: x and 'product-card' in x)

                for art in articles:
                    title_elem = art.find('div', class_=lambda x: x and 'product-card-details__item__title' in x)
                    if not title_elem:
                        continue
                    brand, title = extraire_marque_du_titre(title_elem.text.strip())

                    cle = (brand.upper(), title.upper())
                    if cle in vus:
                        continue
                    vus.add(cle)

                    current_price = ""
                    price_elem = art.find('span', class_=lambda x: x and 'vp-price-amount' in x)
                    if price_elem:
                        current_price = _nettoyer_prix(price_elem.text)

                    rating = ""
                    rating_elem = art.find('div', class_=lambda x: x and 'vp-star-rating' in x)
                    if rating_elem and rating_elem.has_attr('aria-label'):
                        m = re.search(r'([\d,]+)', rating_elem['aria-label'])
                        if m:
                            rating = m.group(1).replace(',', '.')

                    products_data.append({
                        "Marque": brand, "Titre": title,
                        "Prix Actuel": current_price, "Note": rating,
                        "Coloris": "1 couleur", "Source": SITE,
                    })
            except Exception as e:
                print(f"  ⚠️ Erreur parsing {url}: {e}")
        ctx.close()

    _ecrire_csv(OUTPUT_FILE, products_data)
    print(f"  ✅ {len(products_data)} produits {SITE} exportés.")


# ==========================================
# FUSION DES DONNÉES
# ==========================================
def fusionner_donnees():
    print("\n" + "=" * 50)
    print("  FUSION DE TOUS LES FICHIERS CSV")
    print("=" * 50)

    fichiers_csv = [
        "zalando_vetements_clean.csv",
        "irun_vetements_clean.csv",
        "intersport_vetements.csv",
        "sport2000_vetements_clean.csv",
        "alltricks_vetements_clean.csv",
        "jdsports_vetements_clean.csv",
        "decathlon_vetements_clean.csv",
    ]

    dataframes = []
    for fichier in fichiers_csv:
        if os.path.exists(fichier):
            try:
                df = pd.read_csv(fichier, sep=';', on_bad_lines='skip', dtype=str)
                dataframes.append(df)
                print(f"  ✅ {fichier} — {len(df)} lignes")
            except Exception as e:
                print(f"  ⚠️ Erreur lecture {fichier} : {e}")
        else:
            print(f"  ⚠️ Fichier introuvable : {fichier}")

    if not dataframes:
        print("❌ Aucun fichier à fusionner. Abandon.")
        return

    df_final = pd.concat(dataframes, ignore_index=True)
    print(f"\n  Total brut : {len(df_final)} lignes")

    df_final['Prix Actuel'] = pd.to_numeric(df_final['Prix Actuel'], errors='coerce')
    avant_filtre = len(df_final)
    df_final = df_final[df_final['Prix Actuel'] > 0].dropna(subset=['Prix Actuel'])
    print(f"  Prix invalides supprimés : {avant_filtre - len(df_final)} lignes")

    avant_dedup = len(df_final)
    df_final = df_final.drop_duplicates(subset=['Marque', 'Titre', 'Source'], keep='first')
    print(f"  Doublons supprimés : {avant_dedup - len(df_final)} lignes")

    df_final = df_final.reset_index(drop=True)
    fichier_final = "donnees_brutes_total.csv"
    df_final.to_csv(fichier_final, index=False, sep=';', encoding='utf-8-sig')
    print(f"\n🎉 Export réussi : '{fichier_final}' — {len(df_final)} produits uniques.")


# ==========================================
# EXECUTION PRINCIPALE
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("SCRAPING VÊTEMENTS SPORT")
    print("=" * 50)
    print()
    print("Ordre d'exécution :")
    print("  [1] Zalando")
    print("  [2] i-Run")
    print("  [3] Intersport")
    print("  [4] Sport 2000")
    print("  [5] Alltricks")
    print("  [6] JD Sports")
    print("  [7] Decathlon")
    print()

    scrape_zalando()
    scrape_irun()
    scraper_intersport()
    scrape_sport2000()
    scrape_alltricks()
    scrape_jdsports()
    scrape_decathlon()

    fusionner_donnees()