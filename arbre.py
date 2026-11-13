"""
Arbre généalogique des partis de gauche et d'extrême gauche en France.

1. Interroge Wikidata (SPARQL) : partis (nœuds) et liens (arêtes)
2. Normalise tous les liens dans le sens ancêtre -> descendant
3. Construit un graphe NetworkX
4. Exporte en GEXF (Gephi), DOT (Graphviz) et CSV

Dépendances : pip install requests networkx
Usage : python arbre_gauche.py
"""

import os
import csv
import re
import requests
import networkx as nx

ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "arbre-gauche-fr/0.1 (https://github.com/srcchi/G-n-aGauche) python-requests",
    "Accept": "application/sparql-results+json",
}

QUERY_NODES = """
SELECT ?parti ?partiLabel
       (MIN(?debut) AS ?fondation)
       (MIN(?fin) AS ?dissolution)
       (GROUP_CONCAT(DISTINCT ?ideoLabel; separator=" | ") AS ?ideologies)
WHERE {
  ?parti wdt:P31 wd:Q7278 ;
         wdt:P17 wd:Q142 ;
         wdt:P1142 ?ideo .
  ?ideo rdfs:label ?ideoLabel .
  FILTER(LANG(?ideoLabel) = "fr")
  FILTER(REGEX(?ideoLabel, "trotsk|marxis|léninis|stalinis|maoïs|anarch|communis|socialis|syndicalis|révolution|luxemburg|conseil", "i"))
  OPTIONAL { ?parti wdt:P571 ?debut. }
  OPTIONAL { ?parti wdt:P576 ?fin. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}
GROUP BY ?parti ?partiLabel
ORDER BY ?fondation
"""

QUERY_EDGES = """
SELECT ?source ?sourceLabel ?relation ?cible ?cibleLabel WHERE {
  ?source wdt:P31 wd:Q7278 ;
          wdt:P17 wd:Q142 .
  {
    ?source wdt:P155 ?cible . BIND("précédé par" AS ?relation)
  } UNION {
    ?source wdt:P156 ?cible . BIND("suivi par" AS ?relation)
  } UNION {
    ?source wdt:P1365 ?cible . BIND("remplace" AS ?relation)
  } UNION {
    ?source wdt:P1366 ?cible . BIND("remplacé par" AS ?relation)
  } UNION {
    ?source wdt:P807 ?cible . BIND("scission de" AS ?relation)
  } UNION {
    ?source wdt:P463 ?cible . BIND("membre de" AS ?relation)
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}
ORDER BY ?sourceLabel
LIMIT 5000
"""

# Pour chaque relation : (sens, type d'arête)
# "inverse" : la cible est l'ancêtre, donc cible -> source
# "direct"  : la source est l'ancêtre, donc source -> cible
RELATIONS = {
    "précédé par": ("inverse", "filiation"),
    "suivi par": ("direct", "filiation"),
    "remplace": ("inverse", "filiation"),
    "remplacé par": ("direct", "filiation"),
    "scission de": ("inverse", "scission"),
    "membre de": ("direct", "appartenance"),
}

# Courants : mots-clés cherchés dans les libellés d'idéologie.
# Un parti peut en avoir plusieurs (attribut multiple, comme conseillé).
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

COULEURS = {
    "trotskyste": "#c0392b",
    "stalinien": "#7f1d1d",
    "léniniste": "#e67e22",
    "maoïste": "#f1c40f",
    "anarchiste": "#111111",
    "luxemburgiste": "#8e44ad",
    "social-démocrate": "#e84393",
    "communiste": "#d35400",
    "syndicaliste révolutionnaire": "#27ae60",
}


def sparql(query):
    r = requests.get(ENDPOINT, params={"query": query, "format": "json"},
                     headers=HEADERS, timeout=90)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def qid(uri):
    return uri.rsplit("/", 1)[-1]


def val(row, key, default=""):
    return row.get(key, {}).get("value", default)


def annee(date_str):
    m = re.match(r"-?(\d{4})", date_str or "")
    return int(m.group(1)) if m else None


def courants_de(ideologies):
    trouves = [c for c, rx in COURANTS.items()
               if re.search(rx, ideologies, re.I)]
    return trouves


def construire_graphe():
    g = nx.DiGraph()

    print("Récupération des partis...")
    for row in sparql(QUERY_NODES):
        ideo = val(row, "ideologies")
        courants = courants_de(ideo)
        g.add_node(
            qid(val(row, "parti")),
            label=val(row, "partiLabel"),
            fondation=annee(val(row, "fondation")) or 0,
            dissolution=annee(val(row, "dissolution")) or 0,
            ideologies=ideo,
            courants=" | ".join(courants),
            principal=courants[0] if courants else "",
        )
    nb_noeuds_ideo = g.number_of_nodes()

    print("Récupération des liens...")
    for row in sparql(QUERY_EDGES):
        rel = val(row, "relation")
        if rel not in RELATIONS:
            continue
        sens, type_arete = RELATIONS[rel]
        s, c = qid(val(row, "source")), qid(val(row, "cible"))
        ancetre, descendant = (c, s) if sens == "inverse" else (s, c)

        # Nœuds absents de la requête 1 (pas d'idéologie renseignée)
        for n, lab in ((s, val(row, "sourceLabel")), (c, val(row, "cibleLabel"))):
            if n not in g:
                g.add_node(n, label=lab, fondation=0, dissolution=0,
                           ideologies="", courants="", principal="")

        # DiGraph dédoublonne déjà (ancêtre, descendant) ; on garde le type
        # le plus informatif si une arête existe déjà.
        if g.has_edge(ancetre, descendant):
            if g[ancetre][descendant]["type"] == "filiation" and type_arete == "scission":
                g[ancetre][descendant]["type"] = "scission"
        else:
            g.add_edge(ancetre, descendant, type=type_arete, relation=rel)

    print(f"{nb_noeuds_ideo} partis avec idéologie, "
          f"{g.number_of_nodes() - nb_noeuds_ideo} ajoutés via les liens, "
          f"{g.number_of_edges()} arêtes.")
    return g


def exporter(g):
    os.makedirs("data", exist_ok=True)
    os.chdir("data")
    nx.write_gexf(g, "arbre_gauche.gexf")

    # Noms lisibles pour les nœuds sans libellé (Wikidata renvoie parfois le Q-id)
    nx.write_gexf(g, "arbre_gauche.gexf")

    with open("noeuds.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "fondation", "dissolution",
                    "courants", "ideologies_wikidata"])
        for n, d in g.nodes(data=True):
            w.writerow([n, d["label"], d["fondation"] or "",
                        d["dissolution"] or "", d["courants"], d["ideologies"]])

    with open("aretes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ancetre", "descendant", "type", "relation_wikidata"])
        for a, b, d in g.edges(data=True):
            w.writerow([a, b, d["type"], d["relation"]])

    # DOT : on n'affiche que les composantes connexes de plus d'un nœud
    connexes = [c for c in nx.weakly_connected_components(g) if len(c) > 1]
    gardes = set().union(*connexes) if connexes else set()
    with open("arbre_gauche.dot", "w", encoding="utf-8") as f:
        f.write('digraph G {\n  rankdir=LR;\n  node [shape=box, style="filled,rounded", '
                'fontname="Helvetica", fontcolor="white"];\n')
        for n in gardes:
            d = g.nodes[n]
            couleur = COULEURS.get(d["principal"], "#7f8c8d")
            lab = d["label"].replace('"', "'")
            if d["fondation"]:
                lab += f"\\n({d['fondation']}"
                lab += f"-{d['dissolution']})" if d["dissolution"] else "-)"
            f.write(f'  "{n}" [label="{lab}", fillcolor="{couleur}"];\n')
        for a, b, d in g.edges(data=True):
            if a in gardes and b in gardes:
                style = {"scission": 'color="red", style="dashed"',
                         "appartenance": 'color="gray", style="dotted"'}.get(d["type"], "")
                f.write(f'  "{a}" -> "{b}" [{style}];\n')
        f.write("}\n")

    print("Fichiers écrits : arbre_gauche.gexf, arbre_gauche.dot, noeuds.csv, aretes.csv")
    print("Rendu : dot -Tsvg arbre_gauche.dot -o arbre_gauche.svg")


if __name__ == "__main__":
    graphe = construire_graphe()
    exporter(graphe)