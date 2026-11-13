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
Dépendance : Graphviz (commande dot)
"""

import csv
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

STYLE_ARETE = {
    "filiation": 'color="#555555"',
    "scission": 'color="#c0392b", style="dashed", penwidth=1.2',
    "passage": 'color="#2471a3", style="dotted", penwidth=1.8',
    "appartenance": 'color="#7f7f7f", style="dotted", penwidth=1.3, arrowhead=none, constraint=false',
}


def lire(nom):
    with open(os.path.join(DATA, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def courant(d):
    # Le libellé d'abord, puis les courants déjà détectés, puis les idéologies :
    # le nom d'une organisation est l'indice le plus fiable.
    for texte in (d["label"], d["courants"], d["ideologies"]):
        for nom, rx, fond, police in COURANTS:
            if re.search(rx, texte, re.I):
                return nom, fond, police
    return INCONNU


def etiquette(d):
    lab = re.sub(r" \((parti politique|organisation politique|France|parti français)\)$", "",
                 d["label"]).replace('"', "'")
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

    # Seules les organisations reliées par au moins une arête sont dessinées
    dans = {x for a, b, _ in aretes for x in (a, b)}
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
    dans = {x for a, b, _ in aretes for x in (a, b)}

    # Colonnes de la frise : seulement les périodes qui contiennent des organisations
    colonne = {q: annees[q] // PAS * PAS for q in dans}
    colonnes = sorted(set(colonne.values()))
    par_colonne = defaultdict(list)
    for q in dans:
        par_colonne[colonne[q]].append(q)

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

    for c in colonnes:
        membres = sorted(par_colonne[c], key=lambda q: annees[q])
        for q in membres:
            d = noeuds[q]
            nom_c, fond, police = courant(d)
            legende[nom_c] = (fond, police)
            bord = ""
            if d["internationale"]:   # organisation parente : double bordure
                bord = ', peripheries=2, penwidth=1.5, color="#333333"'
            elif d["etranger"]:
                bord = ', penwidth=2, color="#000000", style="filled,rounded,dashed"'
            lignes.append(f'  "{q}" [label="{etiquette(d)}", fillcolor="{fond}", '
                          f'fontcolor="{police}"{bord}, tooltip="{nom_c}"];')
        lignes.append("  { rank=same; " + f'"an{c}"; ' + " ".join(f'"{q}";' for q in membres) + " }")

    for a, b, t in sorted(aretes):
        style = STYLE_ARETE[t]
        if colonne[b] < colonne[a] and "constraint" not in style:
            style += ", constraint=false"  # date incohérente : on ne contraint pas la mise en page
        lignes.append(f'  "{a}" -> "{b}" [{style}];')

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
                     ("passage", "passage de militants"), ("appartenance", "membre de")):
        lignes.append(f'    "leg_{t}_a" [label="{texte}"]; "leg_{t}_b" [label=""];')
        lignes.append(f'    "leg_{t}_a" -> "leg_{t}_b" [{STYLE_ARETE[t]}];')
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
