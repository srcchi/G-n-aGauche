"""
Arbre généalogique des organisations de gauche et d'extrême gauche en France : collecte Wikidata.

1. Organisations françaises de gauche (point de départ) : partis, mais aussi organisations
   politiques, organisations de jeunesse, tendances..., dont le pays (P17) ou le siège (P159)
   est en France, avec une idéologie, un positionnement ou un nom de gauche.
2. Leurs liens : précédé par, suivi par, remplace, remplacé par, scission de, membre de,
   dans les deux sens (ex. une scission d'un parti français est trouvée aussi).
3. Remontée des ancêtres, dans n'importe quel pays, sur PROFONDEUR générations : une
   organisation française issue d'une organisation étrangère (ou d'une Internationale issue
   d'une autre) garde sa lignée.
4. Normalise tous les liens dans le sens ancêtre -> descendant et écrit data/noeuds.csv et
   data/aretes.csv. Le tri gauche / France / Internationales est fait ensuite par nettoyage.py.

Dépendances : pip install requests   (networkx facultatif : export Gephi data/arbre_gauche.gexf)
Usage : python arbre.py
"""

import csv
import os
import re
import time

import requests

ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "arbre-gauche-fr/0.2 (https://github.com/srcchi/G-n-aGauche) python-requests",
    "Accept": "application/sparql-results+json",
}
DATA = "data"
PROFONDEUR = 3      # générations d'ancêtres remontées au-delà des organisations de départ
LOT = 150           # identifiants par requête

# Types de départ (et leurs sous-classes) : parti, organisation politique, organisation de jeunesse
TYPES = ["Q7278", "Q7210356", "Q1572070"]
RX_GAUCHE = re.compile(
    r"trotsk|marxis|léninis|stalinis|maoïs|anarch|communis|socialis|syndicalis|révolution|"
    r"luxemburg|conseillis|libertaire|anticapital|autogestion|antifascis|écosocialis|"
    r"altermondialis|gauche|left|ouvri|prolétar|internationalis|"
    r"écolog|vert|régionalis|autonomis|indépendantis|occitan|breton|basque|corse|kanak", re.I)

# Organisations françaises qui ont au moins un lien de lignée, quelle que soit leur idéologie
# (comme l'ancienne version de ce script) : le tri gauche / droite est fait par nettoyage.py.
QUERY_LIGNEE_FR = """
SELECT DISTINCT ?org WHERE {
  { ?org wdt:P17 wd:Q142 . } UNION { ?org wdt:P159/wdt:P17 wd:Q142 . }
  ?org wdt:P31/wdt:P279* wd:%s .
  { ?org wdt:P155 [] } UNION { ?org wdt:P156 [] } UNION { ?org wdt:P1365 [] } UNION
  { ?org wdt:P1366 [] } UNION { ?org wdt:P807 [] }
}
"""

QUERY_DEPART = """
SELECT ?org ?orgLabel
       (GROUP_CONCAT(DISTINCT ?ideoLabel; separator=" | ") AS ?ideologies)
       (GROUP_CONCAT(DISTINCT ?posLabel; separator=" | ") AS ?positions)
WHERE {
  { ?org wdt:P17 wd:Q142 . } UNION { ?org wdt:P159/wdt:P17 wd:Q142 . }
  ?org wdt:P31/wdt:P279* wd:%s .
  OPTIONAL { ?org wdt:P1142 ?ideo . ?ideo rdfs:label ?ideoLabel . FILTER(LANG(?ideoLabel) = "fr") }
  OPTIONAL { ?org wdt:P1387 ?pos . ?pos rdfs:label ?posLabel . FILTER(LANG(?posLabel) = "fr") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}
GROUP BY ?org ?orgLabel
"""

# Liens partant des organisations données (?s dans VALUES)
QUERY_LIENS_SORTANTS = """
SELECT ?s ?rel ?c WHERE {
  VALUES ?s { %s }
  { ?s wdt:P155 ?c . BIND("précédé par" AS ?rel) } UNION
  { ?s wdt:P156 ?c . BIND("suivi par" AS ?rel) } UNION
  { ?s wdt:P1365 ?c . BIND("remplace" AS ?rel) } UNION
  { ?s wdt:P1366 ?c . BIND("remplacé par" AS ?rel) } UNION
  { ?s wdt:P807 ?c . BIND("scission de" AS ?rel) } UNION
  { ?s wdt:P463 ?c . BIND("membre de" AS ?rel) }
}
"""
# Liens arrivant sur les organisations données (?c dans VALUES) : leurs descendants
QUERY_LIENS_ENTRANTS = """
SELECT ?s ?rel ?c WHERE {
  VALUES ?c { %s }
  { ?s wdt:P155 ?c . BIND("précédé par" AS ?rel) } UNION
  { ?s wdt:P1365 ?c . BIND("remplace" AS ?rel) } UNION
  { ?s wdt:P807 ?c . BIND("scission de" AS ?rel) }
}
"""
# Détails de chaque organisation
QUERY_DETAILS = """
SELECT ?org ?orgLabel (MIN(?debut) AS ?fondation) (MIN(?fin) AS ?dissolution)
       (GROUP_CONCAT(DISTINCT ?ideoLabel; separator=" | ") AS ?ideologies)
WHERE {
  VALUES ?org { %s }
  OPTIONAL { ?org wdt:P571 ?debut. }
  OPTIONAL { ?org wdt:P576 ?fin. }
  OPTIONAL { ?org wdt:P1142 ?ideo . ?ideo rdfs:label ?ideoLabel . FILTER(LANG(?ideoLabel) = "fr") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}
GROUP BY ?org ?orgLabel
"""

# Pour chaque relation : (sens, type d'arête)
# "inverse" : la cible est l'ancêtre ; "direct" : la source est l'ancêtre
RELATIONS = {
    "précédé par": ("inverse", "filiation"),
    "suivi par": ("direct", "filiation"),
    "remplace": ("inverse", "filiation"),
    "remplacé par": ("direct", "filiation"),
    "scission de": ("inverse", "scission"),
    "membre de": ("direct", "appartenance"),
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


def sparql(query):
    for essai in range(5):
        r = requests.post(ENDPOINT, data={"query": query, "format": "json"},
                          headers=HEADERS, timeout=180)
        if r.status_code in (429, 500, 502, 503, 504):
            attente = min(int(r.headers.get("Retry-After", 10 * (essai + 1)) or 10), 60)
            print(f"  {r.status_code}, pause de {attente}s...")
            time.sleep(attente)
            continue
        r.raise_for_status()
        time.sleep(1)    # politesse envers le service
        return r.json()["results"]["bindings"]
    raise RuntimeError("Wikidata ne répond pas, réessaie plus tard.")


def qid(uri):
    return uri.rsplit("/", 1)[-1]


def val(row, key, default=""):
    return row.get(key, {}).get("value", default)


def annee(date_str):
    m = re.match(r"-?(\d{4})", date_str or "")
    return int(m.group(1)) if m else None


def courants_de(ideologies):
    return [c for c, rx in COURANTS.items() if re.search(rx, ideologies, re.I)]


def par_lots(ids):
    ids = sorted(ids)
    for i in range(0, len(ids), LOT):
        yield " ".join(f"wd:{q}" for q in ids[i:i + LOT])


def collecter():
    # ---------- 1. Organisations de départ ----------
    depart = set()
    for t in TYPES:
        print(f"Organisations françaises de type {t}...")
        for row in sparql(QUERY_DEPART % t):
            texte = " ".join((val(row, "orgLabel"), val(row, "ideologies"), val(row, "positions")))
            if RX_GAUCHE.search(texte) and not re.search(r"droite|right", val(row, "positions"), re.I):
                depart.add(qid(val(row, "org")))
    n_gauche = len(depart)
    for t in TYPES:
        for row in sparql(QUERY_LIGNEE_FR % t):
            depart.add(qid(val(row, "org")))
    print(f"{len(depart)} organisations françaises au départ ({n_gauche} de gauche, "
          f"{len(depart) - n_gauche} autres ayant un lien de lignée).")

    # ---------- 2. Liens des organisations de départ, dans les deux sens ----------
    liens = set()

    def ajouter(rows):
        nouveaux = set()
        for row in rows:
            rel = val(row, "rel")
            s, c = qid(val(row, "s")), qid(val(row, "c"))
            if not re.fullmatch(r"Q\d+", s) or not re.fullmatch(r"Q\d+", c) or s == c:
                continue
            liens.add((s, rel, c))
            nouveaux |= {s, c}
        return nouveaux

    print("Liens des organisations de départ...")
    connus = set(depart)
    for lot in par_lots(depart):
        connus |= ajouter(sparql(QUERY_LIENS_SORTANTS % lot))
        connus |= ajouter(sparql(QUERY_LIENS_ENTRANTS % lot))

    # ---------- 3. Remontée des ancêtres, tous pays ----------
    a_remonter = connus - depart
    for g in range(1, PROFONDEUR + 1):
        if not a_remonter:
            break
        print(f"Ancêtres, génération {g} : {len(a_remonter)} organisations à examiner...")
        trouves = set()
        for lot in par_lots(a_remonter):
            rows = [r for r in sparql(QUERY_LIENS_SORTANTS % lot)
                    if val(r, "rel") in ("précédé par", "remplace", "scission de", "membre de")]
            trouves |= ajouter(rows)
        a_remonter = trouves - connus
        connus |= trouves
    print(f"{len(connus)} organisations au total, {len(liens)} liens bruts.")

    # ---------- 4. Détails ----------
    print("Détails (libellés, dates, idéologies)...")
    noeuds = {}
    for lot in par_lots(connus):
        for row in sparql(QUERY_DETAILS % lot):
            q = qid(val(row, "org"))
            ideo = val(row, "ideologies")
            noeuds[q] = dict(label=val(row, "orgLabel"), fondation=annee(val(row, "fondation")),
                             dissolution=annee(val(row, "dissolution")), ideologies=ideo,
                             courants=" | ".join(courants_de(ideo)))

    # ---------- 5. Arêtes ancêtre -> descendant ----------
    aretes = {}
    for s, rel, c in liens:
        sens, type_arete = RELATIONS[rel]
        ancetre, descendant = (c, s) if sens == "inverse" else (s, c)
        cle = (ancetre, descendant)
        if cle not in aretes or (aretes[cle][0] == "filiation" and type_arete == "scission"):
            aretes[cle] = (type_arete, rel)
    return noeuds, aretes, depart


def exporter(noeuds, aretes):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "noeuds.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "fondation", "dissolution", "courants", "ideologies_wikidata"])
        for q, d in sorted(noeuds.items(), key=lambda x: (x[1]["fondation"] or 9999, x[0])):
            w.writerow([q, d["label"], d["fondation"] or "", d["dissolution"] or "",
                        d["courants"], d["ideologies"]])
    with open(os.path.join(DATA, "aretes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ancetre", "descendant", "type", "relation_wikidata"])
        for (a, b), (t, rel) in sorted(aretes.items()):
            w.writerow([a, b, t, rel])
    try:
        import networkx as nx
    except ImportError:
        print("networkx absent : pas d'export Gephi (data/arbre_gauche.gexf), ce n'est pas nécessaire.")
        return
    g = nx.DiGraph()
    for q, d in noeuds.items():
        g.add_node(q, label=d["label"], fondation=d["fondation"] or 0,
                   dissolution=d["dissolution"] or 0, courants=d["courants"])
    for (a, b), (t, rel) in aretes.items():
        g.add_edge(a, b, type=t, relation=rel)
    nx.write_gexf(g, os.path.join(DATA, "arbre_gauche.gexf"))


if __name__ == "__main__":
    noeuds, aretes, depart = collecter()
    exporter(noeuds, aretes)
    print(f"Fichiers écrits : data/noeuds.csv ({len(noeuds)} organisations), "
          f"data/aretes.csv ({len(aretes)} liens).")
