"""
Fusionne les données Wikidata (arbre.py) et Wikipédia (infobox.py) en un seul graphe
d'organisations, complète les dates et filtre le périmètre : la gauche en France.

Entrées  : data/noeuds.csv, data/aretes.csv          (arbre.py)
           data/wp_noeuds.csv, data/wp_aretes.csv    (infobox.py)
           data/corrections_noeuds.csv               (à la main, facultatif)
               action = inclure | exclure | vivant | disparu
           data/corrections_aretes.csv               (à la main, facultatif)
Sorties  : data/org_noeuds.csv, data/org_aretes.csv, data/org_exclus.csv

Les corrections manuelles ne sont jamais écrasées : elles sont relues à chaque exécution.

Usage : python fusion.py
        python fusion.py --refresh   (ré-interroge Wikidata)
"""

import csv
import json
import os
import re
import sys
import time

import requests

DATA = "data"
ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "arbre-gauche-fr/0.1 (https://github.com/srcchi/G-n-aGauche) python-requests",
    "Accept": "application/sparql-results+json",
}
CACHE = os.path.join(DATA, "cache_wikidata_orgs.json")
HUMAIN = "Q5"
# Types Wikidata d'organisations politiques : si l'un d'eux est présent, l'organisation est gardée
POLITIQUE = {"Q7278", "Q7210356", "Q2716508", "Q6138528", "Q2738074", "Q484652", "Q1393724",
             "Q24649", "Q2493450", "Q127603408", "Q233591", "Q40482169", "Q12909644",
             "Q61741927", "Q13243303", "Q3778417", "Q23702035", "Q17149090", "Q17127659"}
# Types non politiques : exclus s'ils n'ont aucun type de POLITIQUE
NON_POLITIQUE = {
    "Q200764", "Q155271", "Q2085381", "Q20860083", "Q3918", "Q1153191", "Q1110794", "Q11032",
    "Q1002697", "Q41298", "Q48204", "Q20873950", "Q1451906", "Q50922133", "Q18674739",
    "Q1400264", "Q101370382", "Q163740", "Q79913", "Q877998", "Q21528930",
}
# Types qui signalent une Internationale (organisation « parente » de partis nationaux)
INTERNATIONALE = {"Q2716508", "Q484652", "Q24649", "Q1194093"}
# Par le nom, quand le type Wikidata manque. Attention aux partis nationaux dont le nom
# contient le mot (SFIO, Parti communiste internationaliste...) : on ne les prend pas.
RX_INTERNATIONALE = re.compile(
    r"^(Internationale|Quatrième Internationale|Comité international|Comité pour une Internationale|"
    r"Ligue internationale|Entente internationale|Conférence internationale|Rencontre internationale|"
    r"Solidarité internationale|Union communiste internationaliste$)|– Quatrième Internationale$")
# Types qui signalent une organisation disparue
ANCIEN = {"Q40482169", "Q23702035"}
# Mots du nom qui signalent une organisation de gauche (quand l'idéologie n'est pas renseignée)
RX_NOM_GAUCHE = re.compile(r"gauche|sociali|communis|ouvri|travailleu|révolution|anarch|"
                           r"libertaire|trotsk|maoï|marxis|léninis|internationale|prolétar|"
                           r"syndical|insoumis|front populaire|spartak|bolch", re.I)

FRANCE = "Q142"
# Positionnement politique (P1387) considéré comme « de gauche »
RX_GAUCHE = re.compile(r"gauche|left", re.I)
# Positionnements explicitement hors périmètre
RX_DROITE = re.compile(r"droite|right|centre$|centre droit|center$|centrism", re.I)
# Catégories Wikipédia qui indiquent la France
RX_FRANCE_CAT = re.compile(r"en France|français|France\)|Parti communiste français|"
                           r"Section française|Parti socialiste \(France\)|"
                           r"La France insoumise|Nouveau Parti anticapitaliste|"
                           r"Union communiste internationaliste|Front de gauche \(France\)", re.I)
# Catégories qui indiquent un autre pays
RX_ETRANGER_CAT = re.compile(r" (au|en|aux) (?!France)[A-ZÉ]", re.U)

QUERY = """
SELECT ?item
       (GROUP_CONCAT(DISTINCT ?p17; separator="|") AS ?pays)
       (GROUP_CONCAT(DISTINCT ?posLabel; separator="|") AS ?pos)
       (GROUP_CONCAT(DISTINCT ?p31; separator="|") AS ?types)
       (GROUP_CONCAT(DISTINCT ?jLabel; separator="|") AS ?journaux)
       (MIN(?d) AS ?debut) (MIN(?f) AS ?fin)
WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P17 ?p17. }
  OPTIONAL { ?item wdt:P31 ?p31. }
  OPTIONAL { { ?item wdt:P2813 ?j. } UNION { ?j wdt:P123 ?item. ?j wdt:P31/wdt:P279* wd:Q1002697. }
             ?j rdfs:label ?jLabel. FILTER(LANG(?jLabel) = "fr") }
  OPTIONAL { ?item wdt:P1387 ?p. ?p rdfs:label ?posLabel. FILTER(LANG(?posLabel) = "fr") }
  OPTIONAL { ?item wdt:P571 ?d. }
  OPTIONAL { ?item wdt:P576 ?f. }
}
GROUP BY ?item
"""


def lire_csv(nom):
    chemin = os.path.join(DATA, nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def annee(s):
    m = re.match(r"-?(\d{4})", str(s or ""))
    return int(m.group(1)) if m else None


def wikidata(qids):
    """Pays, positionnement et dates de chaque QID, avec cache."""
    cache = {}
    if os.path.exists(CACHE) and "--refresh" not in sys.argv:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    manquants = sorted(q for q in qids if q not in cache)
    for i in range(0, len(manquants), 100):
        lot = manquants[i:i + 100]
        print(f"  Wikidata {i + len(lot)}/{len(manquants)}")
        for essai in range(4):
            r = requests.post(ENDPOINT, headers=HEADERS, timeout=120, data={
                "query": QUERY % " ".join(f"wd:{q}" for q in lot), "format": "json"})
            if r.status_code in (429, 500, 502, 503, 504):
                attente = min(int(r.headers.get("Retry-After", 10 * (essai + 1))), 60)
                print(f"  {r.status_code}, pause de {attente}s...")
                time.sleep(attente)
                continue
            break
        r.raise_for_status()
        for q in lot:
            cache[q] = {}
        for row in r.json()["results"]["bindings"]:
            v = lambda k: row.get(k, {}).get("value", "")
            q = v("item").rsplit("/", 1)[-1]
            cache[q] = {
                "pays": [p.rsplit("/", 1)[-1] for p in v("pays").split("|") if p],
                "pos": [p for p in v("pos").split("|") if p],
                "types": [p.rsplit("/", 1)[-1] for p in v("types").split("|") if p],
                "journaux": [p for p in v("journaux").split("|") if p],
                "debut": annee(v("debut")),
                "fin": annee(v("fin")),
            }
        time.sleep(1)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return cache


def main():
    # ---------- Nœuds : fusion des deux sources ----------
    noeuds = {}
    for source, lignes in (("wikidata", lire_csv("noeuds.csv")),
                           ("wikipedia", lire_csv("wp_noeuds.csv"))):
        for r in lignes:
            d = noeuds.setdefault(r["id"], dict(id=r["id"], label=r["label"], fondation=None,
                                                dissolution=None, courants=set(),
                                                ideologies=set(), positionnement="",
                                                categories="", sources=set()))
            d["sources"].add(source)
            d["fondation"] = d["fondation"] or annee(r["fondation"])
            d["dissolution"] = d["dissolution"] or annee(r["dissolution"])
            d["courants"] |= {c for c in r["courants"].split(" | ") if c}
            ideo = r.get("ideologies_wikidata") or r.get("ideologies_wikipedia") or ""
            d["ideologies"] |= {c for c in ideo.split(" | ") if c}
            d["positionnement"] = d["positionnement"] or r.get("positionnement_wikipedia", "")
            d["categories"] = d["categories"] or r.get("categories_wikipedia", "")
            if source == "wikipedia":   # libellés Wikipédia plus lisibles que Wikidata
                d["label"] = r["label"]

    # ---------- Arêtes : fusion, dédoublonnage ----------
    aretes = {}
    for source, lignes in (("wikidata", lire_csv("aretes.csv")),
                           ("wikipedia", lire_csv("wp_aretes.csv"))):
        for r in lignes:
            cle = (r["ancetre"], r["descendant"])
            if r["ancetre"] == r["descendant"]:
                continue
            e = aretes.setdefault(cle, dict(type=r["type"], sources=set()))
            e["sources"].add(source)
            # Le type le plus informatif l'emporte : scission > filiation > appartenance
            ordre = ["appartenance", "filiation", "scission"]
            if ordre.index(r["type"]) > ordre.index(e["type"]):
                e["type"] = r["type"]

    # ---------- Compléments Wikidata ----------
    print("Compléments Wikidata (pays, positionnement, dates)...")
    infos = wikidata([q for q in noeuds if re.fullmatch(r"Q\d+", q)])
    for q, d in noeuds.items():
        w = infos.get(q, {})
        d["pays"] = w.get("pays", [])
        d["pos_wd"] = w.get("pos", [])
        d["types"] = w.get("types", [])
        d["journaux"] = w.get("journaux", [])
        # Dates Wikidata en priorité : l'infobox mélange parfois plusieurs dates
        # (ex. le PS affiche 1905, la date de la SFIO, avant 1969).
        d["fondation"] = w.get("debut") or d["fondation"]
        d["dissolution"] = w.get("fin") or d["dissolution"]

    # ---------- Corrections manuelles ----------
    forcer = {}
    for r in lire_csv("corrections_noeuds.csv"):
        forcer[r["id"]] = r["action"].strip().lower()
        d = noeuds.setdefault(r["id"], dict(id=r["id"], label=r["id"], fondation=None,
                                            dissolution=None, courants=set(), ideologies=set(),
                                            positionnement="", categories="", sources=set(),
                                            pays=[], pos_wd=[], types=[], journaux=[]))
        d["sources"].add("correction")
        for champ in ("label", "fondation", "dissolution"):
            if r.get(champ):
                d[champ] = annee(r[champ]) if champ != "label" else r[champ]
        if r.get("courants"):
            d["courants"] = {c.strip() for c in r["courants"].split("|") if c.strip()}
    for r in lire_csv("corrections_aretes.csv"):
        cle = (r["ancetre"], r["descendant"])
        if r.get("action", "").strip().lower() == "supprimer":
            aretes.pop(cle, None)
        else:
            aretes[cle] = dict(type=r["type"], sources={"correction"})

    # ---------- Périmètre : gauche + France ----------
    def de_gauche(d):
        """None si de gauche, sinon la raison."""
        positions = " ".join(d["pos_wd"]) + " " + d["positionnement"]
        if RX_GAUCHE.search(positions):
            return None
        if RX_DROITE.search(positions):
            return f"positionnement : {positions.strip()}"
        if d["courants"] or RX_NOM_GAUCHE.search(d["label"]):
            return None
        return "ni positionnement de gauche ni courant reconnu"

    def francais(d):
        if d["pays"]:
            return FRANCE in d["pays"]
        if RX_FRANCE_CAT.search(d["categories"]):
            return True
        return not RX_ETRANGER_CAT.search(d["categories"])

    raisons = {}
    for q, d in noeuds.items():
        if forcer.get(q) in ("inclure", "vivant", "disparu"):
            raisons[q] = None
        elif forcer.get(q) == "exclure":
            raisons[q] = "exclu à la main"
        elif HUMAIN in d["types"]:
            raisons[q] = "personne, pas organisation"
        elif set(d["types"]) & NON_POLITIQUE and not set(d["types"]) & POLITIQUE:
            raisons[q] = "pas une organisation politique (journal, librairie, think tank...)"
        else:
            raisons[q] = de_gauche(d) or (None if francais(d) else "hors de France")

    # Une organisation de gauche étrangère est gardée si une organisation française gardée
    # en est membre (une Internationale) ou si elles ont un lien de lignée direct.
    # Les simples sections étrangères d'une Internationale française ne sont pas gardées.
    def fr_garde(y):
        return y in noeuds and raisons.get(y) is None and francais(noeuds[y])
    for (a, b), e in aretes.items():
        candidats = [b] if e["type"] == "appartenance" else [a, b]
        for x in candidats:
            y = a if x == b else b
            if raisons.get(x) == "hors de France" and fr_garde(y):
                raisons[x] = None
                noeuds[x]["etranger"] = True

    gardes = {q: d for q, d in noeuds.items() if raisons[q] is None}
    exclus = [(q, d["label"], raisons[q]) for q, d in noeuds.items() if raisons[q]]
    aretes = {k: e for k, e in aretes.items() if k[0] in gardes and k[1] in gardes}

    # ---------- Organisations encore existantes ----------
    # Vivante = pas de date de dissolution, pas de catégorie « Ancien(ne) ... », pas de type
    # « ancien parti », et pas de successeur (une organisation qui a fusionné ou changé de nom
    # n'existe plus). Les liens qui remontent le temps (données incohérentes) sont ignorés.
    a_successeur = set()
    for (a, b), e in aretes.items():
        fa, fb = gardes[a]["fondation"], gardes[b]["fondation"]
        if e["type"] == "filiation" and not (fa and fb and fb < fa):
            a_successeur.add(a)
    for q, d in gardes.items():
        d["vivant"] = (not d["dissolution"] and q not in a_successeur
                       and not set(d["types"]) & ANCIEN
                       and not re.search(r"Catégorie:Ancien", d["categories"]))
        if forcer.get(q) in ("vivant", "disparu"):
            d["vivant"] = forcer[q] == "vivant"

    # ---------- Écriture ----------
    with open(os.path.join(DATA, "org_noeuds.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "fondation", "dissolution", "courants", "ideologies",
                    "positionnement", "etranger", "vivant", "internationale", "journaux",
                    "sources"])
        for q, d in sorted(gardes.items(), key=lambda x: (x[1]["fondation"] or 9999, x[1]["label"])):
            w.writerow([q, d["label"], d["fondation"] or "", d["dissolution"] or "",
                        " | ".join(sorted(d["courants"])), " | ".join(sorted(d["ideologies"])),
                        d["positionnement"] or " | ".join(d["pos_wd"]),
                        "oui" if d.get("etranger") else "",
                        "oui" if d["vivant"] else "",
                        "oui" if (set(d["types"]) & INTERNATIONALE
                                  or RX_INTERNATIONALE.search(d["label"])) else "",
                        " | ".join(d["journaux"]),
                        " | ".join(sorted(d["sources"]))])

    with open(os.path.join(DATA, "org_aretes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ancetre", "descendant", "type", "sources"])
        for (a, b), e in sorted(aretes.items()):
            w.writerow([a, b, e["type"], " | ".join(sorted(e["sources"]))])

    with open(os.path.join(DATA, "org_exclus.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "raison"])
        w.writerows(sorted(exclus, key=lambda x: x[2]))

    lignee = [e for e in aretes.values() if e["type"] != "appartenance"]
    dans_lignee = {x for k, e in aretes.items() if e["type"] != "appartenance" for x in k}
    sans_date = [q for q in dans_lignee if not gardes[q]["fondation"]]
    print(f"{len(gardes)} organisations gardées, {len(exclus)} exclues (voir org_exclus.csv).")
    print(f"{len(aretes)} arêtes, dont {len(lignee)} de lignée (filiation / scission).")
    print(f"{len(dans_lignee)} organisations dans la lignée, dont {len(sans_date)} sans date de fondation.")
    if not os.path.exists(os.path.join(DATA, "corrections_noeuds.csv")):
        with open(os.path.join(DATA, "corrections_noeuds.csv"), "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["id", "action", "label", "fondation", "dissolution", "courants"])
    if not os.path.exists(os.path.join(DATA, "corrections_aretes.csv")):
        with open(os.path.join(DATA, "corrections_aretes.csv"), "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["ancetre", "descendant", "type", "action"])


if __name__ == "__main__":
    main()
