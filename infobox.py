"""
Extraction des infobox de Wikipédia FR pour compléter l'arbre des partis de gauche.

1. Liste les pages de catégories données (avec sous-catégories, jusqu'à PROFONDEUR)
2. Récupère le wikitext de chaque page (avec cache dans data/)
3. Lit l'infobox de parti (prédécesseur, successeur, scission, international, idéologie...)
4. Résout les redirections et récupère l'identifiant Wikidata de chaque page
5. Écrit data/wp_noeuds.csv et data/wp_aretes.csv, au même format que le script Wikidata,
   avec les mêmes identifiants (Q...) quand ils existent, pour pouvoir fusionner ensuite.

Dépendances : pip install requests mwparserfromhell
Usage : python infobox_wikipedia.py
        python infobox_wikipedia.py "Catégorie:Mon autre catégorie" ...   (remplace la liste par défaut)
        python infobox_wikipedia.py --refresh   (supprime les caches de data/ et refait tout)
"""

import csv
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict

import mwparserfromhell
import requests

API = "https://fr.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "arbre-gauche-fr/0.1 (https://github.com/srcchi/G-n-aGauche) python-requests"}
DATA = "data"
PROFONDEUR = 2

# Noms de catégories écrits de mémoire : le script signale celles qui sont vides ou inexistantes.
CATEGORIES = [
    "Catégorie:Extrême gauche en France",
    "Catégorie:Parti politique communiste en France",
    "Catégorie:Trotskisme en France",
    "Catégorie:Organisation trotskiste",
    "Catégorie:Organisation maoïste",
    "Catégorie:Organisation anarchiste en France",
    "Catégorie:Parti politique socialiste en France",
]

# Préfixes de nom de modèle considérés comme une infobox de parti
INFOBOX_PREFIXES = ("infobox parti", "infobox organisation")

# Paramètres de l'infobox -> rôle. Clés normalisées (minuscules, sans accents, espaces simples).
# Les noms viennent de ma mémoire du modèle : la fin du script affiche les paramètres
# réellement rencontrés, pour que tu puisses corriger cette table.
CHAMPS = {
    "predecesseur": "pred", "precede par": "pred", "fusion de": "pred", "issu de": "pred",
    "precedent": "pred", "remplace": "pred",
    "successeur": "succ", "suivi par": "succ", "fusionne dans": "succ", "devenu": "succ",
    "suivant": "succ", "remplace par": "succ",
    "scission de": "scission_de",
    "scission": "scission_vers", "scissions": "scission_vers", "scission vers": "scission_vers",
    "scission dans": "scission_vers",
    "international": "international", "internationale": "international",
    "affiliation internationale": "international", "affi internationale": "international",
    "ideologie": "ideologie", "ideologies": "ideologie",
    "fondation": "fondation", "creation": "fondation",
    "date de fondation": "fondation", "date fondation": "fondation",
    "disparition": "disparition", "dissolution": "disparition",
    "positionnement": "positionnement",
    # Appartenance à une fédération européenne / nationale ou à une coalition
    "affi europeenne": "affiliation", "affiliation europeenne": "affiliation",
    "affi nationale": "affiliation", "affi francaise": "affiliation",
    "coalition": "affiliation", "affiliation": "affiliation",
    "coalition de": "membres",  # sur la page de la coalition : liste de ses membres
}

COURANTS = {
    "trotskyste": r"trotsk",
    "stalinien": r"stalinis",
    "léniniste": r"léninis",
    "maoïste": r"maoïs",
    "anarchiste": r"anarch|libertaire",
    "luxemburgiste": r"luxemburg|conseil",
    "social-démocrate": r"social-d[ée]mocr|socialis",
    "communiste": r"communis",
    "syndicaliste révolutionnaire": r"syndicalis",
}

PREFIXES_IGNORES = ("fichier:", "file:", "image:", "catégorie:", "category:")

# Sous-catégories à ne pas explorer (personnes, élections, presse...) : elles ne contiennent pas de partis
EXCLUS = re.compile(
    r"personnalit|militant|député|sénateur|maire|élu|conseiller|ministre|candidat|"
    r"dirigeant|membre|secrétaire|presse|journal|revue|élection|biographie",
    re.I,
)


def api(**params):
    params.update(action="query", format="json", formatversion=2)
    for essai in range(6):
        r = requests.get(API, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 429:
            try:
                attente = int(r.headers.get("Retry-After", 5 * (essai + 1)))
            except ValueError:
                attente = 5 * (essai + 1)
            attente = min(attente, 60)
            print(f"  429 (trop de requêtes), pause de {attente}s...")
            time.sleep(attente)
            continue
        r.raise_for_status()
        time.sleep(0.5)  # politesse envers l'API
        return r.json()
    raise RuntimeError("Trop de réponses 429 consécutives, réessaie plus tard.")


def normaliser(nom):
    s = unicodedata.normalize("NFD", str(nom).strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s_\-]+", " ", s).strip()


# ---------- Caches (data/cache_*.json) ----------

def cache_lire(nom):
    chemin = os.path.join(DATA, nom)
    if not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def cache_ecrire(nom, contenu):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, nom), "w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False)


# ---------- 1. Catégories ----------

def membres_categorie(cat):
    """Renvoie (pages, sous-catégories) d'une catégorie."""
    pages, sous = [], []
    suite = {}
    while True:
        data = api(list="categorymembers", cmtitle=cat, cmlimit=500,
                   cmtype="page|subcat", **suite)
        for m in data["query"]["categorymembers"]:
            (sous if m["ns"] == 14 else pages).append(m["title"])
        if "continue" not in data:
            break
        suite = data["continue"]
    return pages, sous


def explorer(cat_racine):
    """Parcourt la catégorie et ses sous-catégories. Renvoie {titre de page: {catégories}}."""
    cache = cache_lire("cache_categories.json")
    cle = f"{cat_racine}|{PROFONDEUR}"
    if cle in cache:
        print("  (en cache)")
        return {t: set(cs) for t, cs in cache[cle].items()}
    trouvees = defaultdict(set)
    vues = set()
    a_voir = [(cat_racine, 0)]
    total_racine = 0
    while a_voir:
        cat, prof = a_voir.pop()
        if cat in vues:
            continue
        vues.add(cat)
        pages, sous = membres_categorie(cat)
        if cat == cat_racine:
            total_racine = len(pages) + len(sous)
        for p in pages:
            trouvees[p].add(cat)
        if prof < PROFONDEUR:
            a_voir.extend((s, prof + 1) for s in sous if not EXCLUS.search(s))
    if total_racine == 0:
        print(f"  ATTENTION : catégorie vide ou inexistante : {cat_racine}")
    else:
        cache[cle] = {t: sorted(cs) for t, cs in trouvees.items()}
        cache_ecrire("cache_categories.json", cache)
    return trouvees


# ---------- 2. Wikitext (avec cache) ----------

def charger_wikitext(titres):
    chemin = os.path.join(DATA, "cache_wikitext.json")
    cache = {}
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            cache = json.load(f)
    manquants = [t for t in titres if t not in cache]
    for i in range(0, len(manquants), 20):
        lot = manquants[i:i + 20]
        print(f"  wikitext {i + len(lot)}/{len(manquants)}")
        data = api(prop="revisions|pageprops", rvprop="content", rvslots="main",
                   ppprop="wikibase_item", titles="|".join(lot))
        for p in data["query"]["pages"]:
            texte, qid = "", None
            if p.get("revisions"):
                texte = p["revisions"][0]["slots"]["main"]["content"]
            qid = p.get("pageprops", {}).get("wikibase_item")
            cache[p["title"]] = {"text": texte, "qid": qid}
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return {t: cache[t] for t in titres if t in cache}


# ---------- 3. Infobox ----------

def liens(valeur):
    """Titres des liens internes d'une valeur de paramètre."""
    code = mwparserfromhell.parse(str(valeur))
    res = []
    for l in code.filter_wikilinks():
        t = str(l.title).split("#")[0].strip()
        if t and not t.lower().startswith(PREFIXES_IGNORES):
            res.append(t)
    return res


def annee(valeur):
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", str(valeur))
    return int(m.group(1)) if m else None


def lire_infobox(texte, compteur_modeles, compteur_params):
    code = mwparserfromhell.parse(texte)
    for tpl in code.filter_templates(recursive=False):
        nom = str(tpl.name).strip().lower()
        if nom.startswith("infobox"):
            compteur_modeles[nom] += 1
        if nom.startswith(INFOBOX_PREFIXES):
            champs = defaultdict(list)
            for p in tpl.params:
                cle = normaliser(p.name)
                compteur_params[(nom, cle)] += 1
                role = CHAMPS.get(cle)
                if role and str(p.value).strip():
                    champs[role].append(p.value)
            return champs
    return None


# ---------- 4. Résolution des redirections et des identifiants Wikidata ----------

def resoudre(titres):
    cache = cache_lire("cache_resolution.json")
    res = {t: tuple(cache[t]) for t in titres if t in cache}
    titres = sorted(set(t for t in titres if t not in cache))
    for i in range(0, len(titres), 50):
        lot = titres[i:i + 50]
        data = api(titles="|".join(lot), redirects=1, prop="pageprops",
                   ppprop="wikibase_item")["query"]
        norm = {n["from"]: n["to"] for n in data.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in data.get("redirects", [])}
        pages = {p["title"]: p for p in data.get("pages", [])}
        for t in lot:
            t2 = redir.get(norm.get(t, t), norm.get(t, t))
            p = pages.get(t2, {})
            res[t] = (t2, p.get("pageprops", {}).get("wikibase_item"))
            cache[t] = list(res[t])
    cache_ecrire("cache_resolution.json", cache)
    return res


# ---------- 5. Assemblage ----------

def courants_de(texte):
    return [c for c, rx in COURANTS.items() if re.search(rx, texte, re.I)]


def main():
    os.makedirs(DATA, exist_ok=True)
    if "--refresh" in sys.argv[1:]:
        for nom in ("cache_wikitext.json", "cache_categories.json", "cache_resolution.json"):
            chemin = os.path.join(DATA, nom)
            if os.path.exists(chemin):
                os.remove(chemin)
        print("Caches supprimés, tout sera refait.")
    cats = [a for a in sys.argv[1:] if not a.startswith("--")] or CATEGORIES

    print("Exploration des catégories...")
    pages = defaultdict(set)
    for c in cats:
        print(f" {c}")
        for titre, cs in explorer(c).items():
            pages[titre] |= cs
    print(f"{len(pages)} pages candidates.")

    print("Récupération du wikitext...")
    textes = charger_wikitext(sorted(pages))

    modeles, params = Counter(), Counter()
    infos, sans_infobox = {}, 0
    for titre, d in textes.items():
        champs = lire_infobox(d["text"], modeles, params)
        if champs is None:
            sans_infobox += 1
        else:
            infos[titre] = (d["qid"], champs)
    print(f"{len(infos)} pages avec infobox de parti, {sans_infobox} sans.")

    # Cibles des liens à résoudre
    cibles = set()
    for _, champs in infos.values():
        for role in ("pred", "succ", "scission_de", "scission_vers", "international",
                     "affiliation", "membres"):
            for v in champs.get(role, []):
                cibles.update(liens(v))
    print(f"Résolution de {len(cibles)} cibles de liens...")
    resolues = resoudre(cibles)

    # Identifiants : Q... si connu, sinon "fr:Titre"
    ident = {}
    for titre, (qid, _) in infos.items():
        ident[titre] = qid or f"fr:{titre}"
    for titre_resolu, qid in resolues.values():
        ident.setdefault(titre_resolu, qid or f"fr:{titre_resolu}")

    noeuds, aretes, sans_lien = {}, set(), []

    def noeud(titre):
        i = ident[titre]
        if i not in noeuds:
            noeuds[i] = dict(label=titre, fondation="", dissolution="", courants="",
                             ideologies="", positionnement="", categories="")
        return i

    for titre, (qid, champs) in infos.items():
        n = noeud(titre)
        d = noeuds[n]
        d["fondation"] = next((annee(v) for v in champs.get("fondation", []) if annee(v)), "") or ""
        d["dissolution"] = next((annee(v) for v in champs.get("disparition", []) if annee(v)), "") or ""
        ideo = []
        for v in champs.get("ideologie", []):
            ideo += liens(v) or [mwparserfromhell.parse(str(v)).strip_code().strip()]
        d["ideologies"] = " | ".join(x for x in ideo if x)
        pos = []
        for v in champs.get("positionnement", []):
            pos += liens(v) or [mwparserfromhell.parse(str(v)).strip_code().strip()]
        d["positionnement"] = " | ".join(x for x in pos if x)
        cats = " | ".join(sorted(pages[titre]))
        d["categories"] = cats
        d["courants"] = " | ".join(courants_de(d["ideologies"] + " " + cats))

        for role, sens, type_arete in (
            ("pred", "inverse", "filiation"),
            ("succ", "direct", "filiation"),
            ("scission_de", "inverse", "scission"),
            ("scission_vers", "direct", "scission"),
            ("international", "direct", "appartenance"),
            ("affiliation", "direct", "appartenance"),
            ("membres", "inverse", "appartenance"),
        ):
            for v in champs.get(role, []):
                cs = liens(v)
                if not cs:
                    texte = mwparserfromhell.parse(str(v)).strip_code().strip()
                    if texte:
                        sans_lien.append((titre, role, texte))
                    continue
                for c in cs:
                    cible = resolues.get(c, (c, None))[0]
                    if cible not in ident:
                        ident[cible] = f"fr:{cible}"
                    m = noeud(cible)
                    anc, desc = (m, n) if sens == "inverse" else (n, m)
                    aretes.add((anc, desc, type_arete, f"wikipedia:{role}"))

    with open(os.path.join(DATA, "wp_noeuds.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "fondation", "dissolution", "courants",
                    "ideologies_wikipedia", "positionnement_wikipedia",
                    "categories_wikipedia"])
        for i, d in noeuds.items():
            w.writerow([i, d["label"], d["fondation"], d["dissolution"],
                        d["courants"], d["ideologies"], d["positionnement"],
                        d["categories"]])

    with open(os.path.join(DATA, "wp_aretes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ancetre", "descendant", "type", "relation_wikipedia"])
        w.writerows(sorted(aretes))

    with open(os.path.join(DATA, "wp_valeurs_sans_lien.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["page", "champ", "texte"])
        w.writerows(sans_lien)

    print(f"\n{len(noeuds)} nœuds, {len(aretes)} arêtes, "
          f"{len(sans_lien)} valeurs sans lien à revoir à la main.")
    print("Fichiers : data/wp_noeuds.csv, data/wp_aretes.csv, data/wp_valeurs_sans_lien.csv")

    print("\nModèles d'infobox rencontrés (pour ajuster INFOBOX_PREFIXES) :")
    for nom, n in modeles.most_common(10):
        print(f"  {n:4d}  {nom}")
    print("\nParamètres d'infobox de parti les plus fréquents (pour ajuster CHAMPS) :")
    bruit = re.compile(r"(option|valeur) \d+$|logo|couleurs|site web|siege|adherents")
    for (modele, cle), n in params.most_common(200):
        if bruit.match(cle):
            continue
        marque = "" if cle in CHAMPS else "   <- non utilisé"
        print(f"  {n:4d}  {modele} : {cle}{marque}")


if __name__ == "__main__":
    main()