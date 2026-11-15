"""
Arbre des organisations : scissions, fusions et filiations, sur une frise chronologique.

Par défaut, l'arbre part des organisations françaises qui existent encore et remonte
tous leurs ancêtres (filiation, scission, passage de militants). Les branches mortes
sans descendant actuel ne sont pas dessinées.

Entrées : data/org_noeuds.csv, data/org_aretes.csv   (produits par fusion.py)
Sorties : data/arbre_orgs.dot, data/arbre_orgs.svg

Usage : python arbre_orgs.py
        python arbre_orgs.py --tout              (toutes les organisations, même disparues sans descendance)
        python arbre_orgs.py --sans-internationales   (n'affiche pas les Internationales)
        python arbre_orgs.py --depuis 1900       (ne garde que les organisations fondées après)
        python arbre_orgs.py --min-taille 20000  (seulement les « grandes » organisations : article
                                                  Wikipédia d'au moins 20 000 caractères ; la lignée
                                                  passe par les petites sans les dessiner)
        python arbre_orgs.py --sans-zones        (pas de bandes de couleur par famille politique)
        python arbre_orgs.py --sans-durees       (pas de barres de durée de vie)
Dépendance : Graphviz (commande dot)
"""

import csv
import datetime
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

DATA = "data"
PAS = 5  # largeur d'une colonne de la frise, en années
LIGNEE = {"filiation", "scission", "passage"}

# Ordre de priorité : le premier courant trouvé donne la couleur.
# (nom, regex, couleur de fond, couleur du texte)
# Noir et nuances : anarchisme. Rouge et nuances : communisme. Rose : social-démocratie.
# Vert : écologie. Gris clair : inconnu.
COURANTS = [
    ("trotskyste", r"trotsk|quatrième internationale|lambert|pabl", "#ff6b5e", "black"),
    ("maoïste", r"maoï|marxiste-léniniste|marxistes-léninistes|hoxha", "#7b0d0d", "white"),
    ("anarcho-syndicaliste", r"anarcho-syndical|syndicalis", "#4d4d4d", "white"),
    ("communiste libertaire", r"communis\w* libertaire|plateform", "#2e2e2e", "white"),
    ("anarchiste", r"anarch|libertaire", "#111111", "white"),
    ("luxemburgiste / conseilliste", r"luxemburg|conseillis", "#b85450", "white"),
    ("communiste", r"communis|léninis|stalinis|bolch", "#d62828", "white"),
    ("écosocialiste", r"écosocialis", "#1e8449", "white"),
    ("radical / républicain", r"radical|républicain", "#f5b7d2", "black"),
    ("social-démocrate", r"social-d[ée]mocr|socialis", "#e84393", "white"),
    ("écologiste", r"écolog|\bverts?\b", "#58d68d", "black"),
]
INCONNU = ("autre / inconnu", "#d5d8dc", "black")

# Zones de fond : chaque courant appartient à une grande famille, dessinée comme une bande colorée.
# Ordre du dictionnaire = ordre des bandes, de haut en bas.
FAMILLE = {
    "anarchiste": "anarchisme", "anarcho-syndicaliste": "anarchisme",
    "communiste libertaire": "anarchisme",
    "trotskyste": "communisme", "maoïste": "communisme", "communiste": "communisme",
    "luxemburgiste / conseilliste": "communisme",
    "social-démocrate": "social-démocratie", "radical / républicain": "social-démocratie",
    "écosocialiste": "écologie", "écologiste": "écologie",
}
ZONES = {   # famille : (couleur de fond, titre)
    "anarchisme": ("#ececec", "Anarchisme"),
    "communisme": ("#fde8e6", "Communisme"),
    "social-démocratie": ("#fdeaf3", "Social-démocratie"),
    "écologie": ("#e6f6ec", "Écologie"),
    "autre": ("#f5f6f7", "Autre / inconnu"),
}
ANNEE_COURANTE = datetime.date.today().year

STYLE_ARETE = {
    "filiation": 'color="#555555"',
    "scission": 'color="#c0392b", style="dashed", penwidth=1.2',
    "passage": 'color="#2471a3", style="dotted", penwidth=1.8',
    "appartenance": 'color="#7f7f7f", style="dotted", penwidth=1.3, arrowhead=none, constraint=false',
    # Lignée qui passe par des organisations non dessinées (option --min-taille)
    "indirect": 'color="#aaaaaa", style="dashed", penwidth=1.0',
}


def tailles_articles():
    """Longueur de l'article Wikipédia de chaque organisation (même identifiant que fusion.py)."""
    chemin = os.path.join(DATA, "cache_wikitext.json")
    if not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        cache = json.load(f)
    return {(d["qid"] or f"fr:{t}"): len(d["text"]) for t, d in cache.items()}


def contracter(aretes, grands):
    """Ne garde que les organisations de `grands`. Une lignée qui passe par des organisations
    retirées devient une arête « indirect » entre les grandes organisations qu'elle relie."""
    enfants = defaultdict(list)
    for a, b, t in aretes:
        if t in LIGNEE:
            enfants[a].append((b, t))
    res = {(a, b): t for a, b, t in aretes if a in grands and b in grands}
    for a in grands:
        # Parcours des descendants à travers les organisations retirées uniquement
        vus, pile = set(), [b for b, _ in enfants[a] if b not in grands]
        while pile:
            x = pile.pop()
            if x in vus:
                continue
            vus.add(x)
            for y, _ in enfants[x]:
                if y in grands:
                    if y != a:
                        res.setdefault((a, y), "indirect")
                elif y not in vus:
                    pile.append(y)
    return [(a, b, t) for (a, b), t in res.items()]


def lire(nom):
    with open(os.path.join(DATA, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def courant(d):
    # Le libellé d'abord, puis les courants déjà détectés, puis les idéologies :
    # le nom d'une organisation est l'indice le plus fiable.
    textes = (d["label"], d["courants"], d["ideologies"])
    if "correction" in d["sources"] and d["courants"]:   # un courant saisi à la main l'emporte
        textes = (d["courants"], d["label"], d["ideologies"])
    for texte in textes:
        for nom, rx, fond, police in COURANTS:
            if re.search(rx, texte, re.I):
                return nom, fond, police
    return INCONNU


def nom_court(d):
    return re.sub(r" \((parti politique|organisation politique|France|parti français)\)$", "",
                  d["label"]).replace('"', "'")


def etiquette(d):
    lab = nom_court(d)
    if len(lab) > 32:  # coupe les noms longs sur deux lignes
        coupe = lab.rfind(" ", 0, len(lab) // 2 + 8)
        lab = lab[:coupe] + "\\n" + lab[coupe + 1:] if coupe > 0 else lab
    lab += f"\\n{d['fondation'] or '?'}–{d['dissolution'] or ''}"
    if d.get("journaux"):
        lab += "\\n« " + d["journaux"].split(" | ")[0].replace('"', "'") + " »"
    return lab


def main():
    depuis = 0
    if "--depuis" in sys.argv:
        depuis = int(sys.argv[sys.argv.index("--depuis") + 1])
    types = set(LIGNEE)
    avec_inter = "--sans-internationales" not in sys.argv
    if avec_inter:
        types.add("appartenance")

    noeuds = {r["id"]: r for r in lire("org_noeuds.csv")}
    aretes = [(r["ancetre"], r["descendant"], r["type"]) for r in lire("org_aretes.csv")
              if r["type"] in types]
    # Appartenance : seulement vers une Internationale (pas les coalitions électorales)
    aretes = [(a, b, t) for a, b, t in aretes
              if t != "appartenance" or noeuds[b]["internationale"]]

    # ---------- Organisations vivantes + tous leurs ancêtres ----------
    gardes = set(noeuds)
    if "--tout" not in sys.argv:
        parents = defaultdict(set)
        for a, b, t in aretes:
            if t in LIGNEE:
                parents[b].add(a)
        def avec_ancetres(depart):
            vus, pile = set(), list(depart)
            while pile:
                q = pile.pop()
                if q not in vus:
                    vus.add(q)
                    pile.extend(parents[q])
            return vus

        racines = [q for q, d in noeuds.items() if d["vivant"] and not d["etranger"]]
        gardes = avec_ancetres(racines)
        # Les Internationales dont un membre est dessiné, et leurs propres ancêtres
        inter = {b for a, b, t in aretes if t == "appartenance" and a in gardes}
        gardes |= avec_ancetres(inter)
        aretes = [(a, b, t) for a, b, t in aretes if a in gardes and b in gardes]

    # ---------- Seulement les « grandes » organisations ----------
    min_taille = 0
    if "--min-taille" in sys.argv:
        min_taille = int(sys.argv[sys.argv.index("--min-taille") + 1])
    if min_taille:
        tailles = tailles_articles()
        # Grande = article assez long, ou ajoutée / corrigée à la main
        grands = {q for q, d in noeuds.items()
                  if tailles.get(q, 0) >= min_taille or "correction" in d["sources"]}
        lignee = contracter([e for e in aretes if e[2] != "appartenance"], grands)
        membres = {x for a, b, _ in lignee for x in (a, b)}
        # Internationales : gardées seulement si une grande organisation dessinée en est membre
        inter = [(a, b, t) for a, b, t in aretes
                 if t == "appartenance" and a in membres and (b in grands or b in membres)]
        aretes = lignee + inter
        # Une grande organisation est dessinée même si toute sa parenté est petite
        seules = {q for q in grands & gardes if not noeuds[q]["internationale"]}
    else:
        seules = set()

    # Seules les organisations reliées par au moins une arête sont dessinées
    # (et, avec --min-taille, les grandes organisations isolées)
    dans = {x for a, b, _ in aretes for x in (a, b)} | seules
    annees = {q: int(noeuds[q]["fondation"]) for q in dans if noeuds[q]["fondation"]}

    # Organisations sans date : placées juste après leur ancêtre, ou juste avant leur descendant
    for _ in range(3):
        for a, b, _ in aretes:
            if b not in annees and a in annees:
                annees[b] = annees[a] + 1
            elif a not in annees and b in annees:
                annees[a] = annees[b] - 1
    sans_date = dans - set(annees)
    dans = {q for q in dans if q in annees and annees[q] >= depuis}
    aretes = [(a, b, t) for a, b, t in aretes if a in dans and b in dans]
    dans = {x for a, b, _ in aretes for x in (a, b)} | (seules & dans)

    col = lambda annee: annee // PAS * PAS
    colonne = {q: col(annees[q]) for q in dans}

    # ---------- Durée de vie de chaque organisation ----------
    # Fin = dissolution ; sinon aujourd'hui si elle existe encore ; sinon la fondation de son
    # premier successeur (fusion, changement de nom) ; sinon pas de barre.
    avec_durees = "--sans-durees" not in sys.argv
    succ = defaultdict(list)
    for a, b, t in aretes:
        if t == "filiation":
            succ[a].append(annees[b])
    fin = {}
    for q in dans:
        d = noeuds[q]
        if d["dissolution"]:
            f = int(d["dissolution"])
        elif d["vivant"]:
            f = ANNEE_COURANTE
        else:
            f = min(succ[q], default=annees[q])
        fin[q] = max(f, annees[q])

    # Colonnes de la frise : les périodes qui contiennent une fondation (et une fin de barre)
    colonnes = set(colonne.values())
    if avec_durees:
        colonnes |= {col(f) for f in fin.values()}
    colonnes = sorted(colonnes)
    # Points de la barre de vie : un par colonne traversée après la fondation
    vie = {q: [c for c in colonnes if colonne[q] < c <= col(fin[q])] if avec_durees else []
           for q in dans}
    par_colonne = defaultdict(list)
    for q in dans:
        par_colonne[colonne[q]].append(q)
        for c in vie[q]:
            par_colonne[c].append(f"{q}@{c}")

    legende = {}
    lignes = [
        "digraph G {",
        '  rankdir=LR; newrank=true; nodesep=0.12; ranksep=0.35; splines=true;',
        '  edge [arrowsize=0.5, penwidth=0.8];',
        "  // Frise",
        '  node [shape=plaintext, style="", fontname="Helvetica", fontcolor="#333333", fontsize=14];',
    ]
    for c in colonnes:
        lignes.append(f'  "an{c}" [label="{c}"];')
    if len(colonnes) > 1:
        lignes.append("  " + " -> ".join(f'"an{c}"' for c in colonnes) + ' [style=invis, weight=100];')
    lignes.append('  node [shape=box, style="filled,rounded", fontsize=10, penwidth=0];')

    # ---------- Nœuds, regroupés par famille politique (zones de fond) ----------
    avec_zones = "--sans-zones" not in sys.argv
    par_famille = defaultdict(list)
    for q in dans:
        par_famille[FAMILLE.get(courant(noeuds[q])[0], "autre")].append(q)
    barres = []
    for i, (fam, (fond_zone, titre)) in enumerate(ZONES.items()):
        if not par_famille[fam]:
            continue
        retrait = "  "
        if avec_zones:
            lignes.append(f'  subgraph cluster_zone{i} {{ label="{titre}"; labeljust=l; '
                          f'fontname="Helvetica-Bold"; fontsize=22; fontcolor="#00000055"; '
                          f'style="filled,rounded"; fillcolor="{fond_zone}"; color="{fond_zone}";')
            retrait = "    "
        for q in sorted(par_famille[fam], key=lambda q: annees[q]):
            d = noeuds[q]
            nom_c, fond, police = courant(d)
            legende[nom_c] = (fond, police)
            bord = ""
            if d["internationale"]:   # organisation parente : double bordure
                bord = ', peripheries=2, penwidth=1.5, color="#333333"'
            elif d["etranger"]:
                bord = ', penwidth=2, color="#000000", style="filled,rounded,dashed"'
            lignes.append(f'{retrait}"{q}" [label="{etiquette(d)}", fillcolor="{fond}", '
                          f'fontcolor="{police}"{bord}, tooltip="{nom_c}"];')
            # Barre de vie : points invisibles reliés par un trait épais de la couleur du courant.
            # Le dernier point d'une organisation encore existante porte son nom.
            for c in vie[q]:
                if c == vie[q][-1] and fin[q] == ANNEE_COURANTE:
                    lignes.append(f'{retrait}"{q}@{c}" [label="{nom_court(d)}", fillcolor="{fond}", '
                                  f'fontcolor="{police}", fontsize=9, tooltip="{nom_c}"];')
                else:
                    lignes.append(f'{retrait}"{q}@{c}" [shape=point, width=0.02, label="", '
                                  f'color="{fond}", fillcolor="{fond}"];')
            points = [q] + [f"{q}@{c}" for c in vie[q]]
            for p1, p2 in zip(points, points[1:]):
                barres.append(f'  "{p1}" -> "{p2}" [color="{fond}aa", penwidth=6, '
                              f'arrowhead=none, weight=20, tooltip="{nom_court(d)}"];')
        if avec_zones:
            lignes.append("  }")

    for c in colonnes:
        membres = par_colonne[c]
        lignes.append("  { rank=same; " + f'"an{c}"; ' + " ".join(f'"{q}";' for q in membres) + " }")
    lignes += barres

    for a, b, t in sorted(aretes):
        style = STYLE_ARETE[t]
        if colonne[b] < colonne[a] and "constraint" not in style:
            style += ", constraint=false"  # date incohérente : on ne contraint pas la mise en page
        # Une scission ou une filiation part de la barre de vie de l'ancêtre, à la date de
        # fondation du descendant (le dernier point avant cette date).
        source = a
        if t != "appartenance":
            avant = [c for c in vie[a] if c < colonne[b]]
            if avant:
                source = f"{a}@{avant[-1]}"
        lignes.append(f'  "{source}" -> "{b}" [{style}];')

    # Légende, dans l'ordre de COURANTS
    lignes.append('  subgraph cluster_legende { label="Légende"; fontname="Helvetica"; '
                  'style="rounded"; color="#cccccc";')
    ordre = [c[0] for c in COURANTS] + [INCONNU[0]]
    for i, nom in enumerate(n for n in ordre if n in legende):
        fond, police = legende[nom]
        lignes.append(f'    "leg{i}" [label="{nom}", fillcolor="{fond}", fontcolor="{police}"];')
    lignes.append('    "leg_e" [label="organisation étrangère", fillcolor="#ffffff", '
                  'fontcolor="#000000", style="filled,rounded,dashed", penwidth=2, color="#000000"];')
    lignes.append('    "leg_i" [label="Internationale (organisation parente)", fillcolor="#ffffff", '
                  'fontcolor="#000000", peripheries=2, penwidth=1.5, color="#333333"];')
    lignes.append('    node [shape=plaintext, style="", fontcolor="#333333"];')
    for t, texte in (("filiation", "filiation / fusion"), ("scission", "scission"),
                     ("passage", "passage de militants"), ("appartenance", "membre de"),
                     ("indirect", "lignée via des organisations\\nnon dessinées")):
        if t == "indirect" and not min_taille:
            continue
        lignes.append(f'    "leg_{t}_a" [label="{texte}"]; "leg_{t}_b" [label=""];')
        lignes.append(f'    "leg_{t}_a" -> "leg_{t}_b" [{STYLE_ARETE[t]}];')
    if avec_durees:
        lignes.append('    "leg_vie_a" [label="durée de vie\\n(jusqu\'à aujourd\'hui : nom répété)"]; '
                      '"leg_vie_b" [label=""];')
        lignes.append('    "leg_vie_a" -> "leg_vie_b" [color="#888888aa", penwidth=6, arrowhead=none];')
    lignes.append("  }")
    lignes.append("}")

    dot = os.path.join(DATA, "arbre_orgs.dot")
    with open(dot, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    svg = os.path.join(DATA, "arbre_orgs.svg")
    subprocess.run(["dot", "-Tsvg", dot, "-o", svg], check=True)

    print(f"{len(dans)} organisations, {len(aretes)} liens, {len(colonnes)} colonnes de {PAS} ans.")
    if sans_date:
        print(f"{len(sans_date)} organisations sans date non placées : "
              + " ; ".join(noeuds[q]["label"] for q in sorted(sans_date)))
    print(f"Fichiers : {dot}, {svg}")


if __name__ == "__main__":
    main()
