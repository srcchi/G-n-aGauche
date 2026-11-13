"""
Phase 2 : mise en page et rendu de l'arbre, sans Graphviz.

Dessine les organisations gardées par l'élagage strict (colonne garde de organisations.csv) :
organisations actives reliées et leurs ancêtres. Mise en page calculée ici, SVG écrit directement.

Règles (vérifiées par verifier.py) :
R1 liens orthogonaux vers la droite ; R2 Internationales jamais en boîte ; R3 dates exactes ;
R4 chaque nom dans son étiquette, aucun texte flottant ; R5 lignée stricte ; R6 ni coalition
ni satellite.

Entrées : data/sortie/organisations.csv, sans_date.csv, liens.csv, internationales.csv,
          affiliations.csv (nettoyage.py) ; data/manuel/sigles.csv
Sorties : data/sortie/arbre.svg (+ copie arbre.svg à la racine), arbre.html,
          arbre_<famille>.svg, arbre_apercu.svg (si l'arbre est très grand),
          vue_internationales.svg et .html, anomalies_rendu.csv (s'il y en a)

Usage : python rendu.py      puis      python verifier.py
"""

import csv
import datetime
import html
import json
import math
import os
import re
import shutil
import unicodedata
from collections import Counter, defaultdict

SORTIE = os.path.join("data", "sortie")
MANUEL = os.path.join("data", "manuel")

# ---------- Géométrie (px, unités SVG) ----------
PPA = 13.0                  # pixels par année
COL_VOIES = 210             # colonne des titres de voies
X0 = COL_VOIES + 30
BAR_H = 16
GAP = 12                    # écart horizontal minimal entre deux éléments d'une rangée
ROW_GAP = 10
GOUTTIERE = 10              # un lien part de la source à x(t) - GOUTTIERE
FLECHE_L, FLECHE_DEMI = 10, 5   # flèches d'au moins 9 px
MIN_W = 6                   # largeur minimale d'une barre
DEGRADE = 28                # fin ouverte d'une organisation active
QUEUE = 40                  # queue hachurée « fin inconnue »
TAG_PAD, TAG_NOM_MAX = 6, 240
LIGNE = 14
FRAME_W, FRAME_PAS = 2.4, 5     # épaisseur et écart des cadres d'affiliation emboîtés
TAB_H = 15
SEUIL_ANNEES, SEUIL_VOIES, SEUIL_RANGS = 40, 2, 6
CASSURE_ANS, CASSURE_PX = 60, 44
VOIE_PAD = 8
FS, FS_SIGLE = 11, 13
POLICE = "Arial, Helvetica, sans-serif"

VOIES = [
    ("socialistes", "Socialistes", "#CC79A7"),
    ("radicaux", "Radicaux", "#F0E442"),
    ("écologistes", "Écologistes", "#009E73"),
    ("communistes", "Communistes", "#C1272D"),
    ("trotskystes", "Trotskystes", "#E69F00"),
    ("maoïstes", "Maoïstes", "#8C510A"),
    ("anarchistes et libertaires", "Anarchistes et libertaires", "#222222"),
    ("outre-mer", "Outre-mer", "#7B3294"),
    ("à classer", "À classer", "#8C8C8C"),
]
SANS_DATE = ("sans date", "Dates inconnues (hors échelle)", "#A6A6A6")
TEINTE = {k: c for k, _, c in VOIES + [SANS_DATE]}
TITRES = {k: t for k, t, _ in VOIES + [SANS_DATE]}
NUANCES = {"communiste libertaire": 0.30, "anarcho-syndicaliste": 0.45,
           "luxemburgiste / conseilliste": 0.35, "écosocialiste": -0.30}
COULEURS_INTER = {
    "socialiste": "#2F5D9E", "communiste": "#16365C", "trotskyste": "#1F7A7A",
    "anarchiste": "#4A5560", "écologiste": "#4C9BC9", "régionaliste": "#7A8894",
    "gauche radicale": "#1593A8", "autre": "#8A9AA8",
}
MOTS_VIDES = {"de", "la", "le", "les", "des", "du", "pour", "l", "d", "et", "à", "en", "contre",
              "sur", "au", "aux"}
STYLE_LIEN = {
    "renommage": dict(couleur="#3D3D3D", dash="", w=(2.6, 1.5)),
    "filiation": dict(couleur="#3D3D3D", dash="", w=(2.6, 1.5)),
    "fusion": dict(couleur="#3D3D3D", dash="", w=(2.2, 1.5)),
    "scission": dict(couleur="#C0392B", dash="6 3", w=(1.6, 1.6)),
    "passage": dict(couleur="#2471A3", dash="1.5 3", w=(1.2, 1.2)),
}
NOMS_LIENS = {"renommage": "renommage", "filiation": "filiation", "fusion": "fusion",
              "scission": "scission", "passage": "passage de militants"}
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


# ======================================================================
# Outils
# ======================================================================

def lire(nom, dossier=SORTIE):
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def esc(s):
    return html.escape(str(s), quote=True)


def t_de(annee, mois=""):
    return int(annee) + ((int(mois) - 1) / 12 if mois else 0)


def aujourdhui():
    d = datetime.date.today()
    return d.year + (d.month - 1) / 12 + (d.day - 1) / 365


def larg(s, fs, gras=False):
    """Largeur estimée d'un texte en Arial, un peu généreuse."""
    w = 0
    for c in s:
        if c in "il.,:;'|!()[]jfrtI ’":
            w += 0.32
        elif c.isupper() or c in "mwMW@%":
            w += 0.74 if gras else 0.70
        elif c.isdigit():
            w += 0.58
        else:
            w += 0.60 if gras else 0.56
    return w * fs + 2


def hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_hex(r, g, b):
    return "#" + "".join(f"{round(max(0, min(1, x)) * 255):02X}" for x in (r, g, b))


def melange(c, cible, f):
    return rgb_hex(*(x + (y - x) * f for x, y in zip(hex_rgb(c), hex_rgb(cible))))


def nuance(c, f):
    return melange(c, "#FFFFFF", f) if f >= 0 else melange(c, "#000000", -f)


def luminance(c):
    def lin(x):
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in hex_rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(c1, c2):
    l1, l2 = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def texte_sur(fond):
    return "#000000" if contraste(fond, "#000000") >= contraste(fond, "#FFFFFF") else "#FFFFFF"


def gris_sur(fond):
    """Gris des dates, contraste d'au moins 4,5:1."""
    noir = texte_sur(fond) == "#000000"
    for g in (["#333333", "#222222"] if noir else ["#E8E8E8", "#F4F4F4"]):
        if contraste(g, fond) >= 4.5:
            return g
    return texte_sur(fond)


def sans_accents(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", sans_accents(s)).strip("-")


def acronyme(nom):
    base = re.sub(r"\s*\([^)]*\)", "", nom)
    res = "-".join("".join(w[0].upper() for w in re.findall(r"[^\W\d_]+", p) if w.lower() not in MOTS_VIDES)
                   for p in re.split(r"\s+[-–]\s+", base))
    m = re.search(r"\(([^)]*)\)", nom)
    return res + ("-" + m.group(1)[:5].rstrip() if m else "")


def couper(s, w, fs, gras=False, max_lignes=2):
    """Coupe un texte en lignes d'au plus w px ; la dernière ligne finit par « … » si besoin."""
    lignes, cour = [], ""
    for mot in s.split():
        essai = (cour + " " + mot).strip()
        if larg(essai, fs, gras) > w and cour:
            lignes.append(cour)
            cour = mot
        else:
            cour = essai
    if cour:
        lignes.append(cour)
    if len(lignes) > max_lignes:
        der = " ".join(lignes[max_lignes - 1:])
        while larg(der + "…", fs, gras) > w and " " in der:
            der = der.rsplit(" ", 1)[0]
        lignes = lignes[:max_lignes - 1] + [der + "…"]
    return lignes


def texte(x, y, s, fs=FS, gras=False, couleur="#1A1A1A", ancre="start", cls="", extra="", italique=False):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" font-family="{POLICE}"'
            f'{" font-weight=\"bold\"" if gras else ""}{" font-style=\"italic\"" if italique else ""}'
            f' fill="{couleur}" text-anchor="{ancre}" class="{cls}"{extra}>{esc(s)}</text>')


# ======================================================================
# Données
# ======================================================================

def charger():
    T_AUJ = aujourdhui()
    sigles = {r["id"]: r for r in lire("sigles.csv", MANUEL)}
    inter = {}
    vus_cle = Counter()
    for r in lire("internationales.csv"):
        cle = r["color_key"] or "autre"
        vus_cle[cle] += 1
        base = COULEURS_INTER.get(cle, COULEURS_INTER["autre"])
        # Plusieurs Internationales d'une même famille : même teinte, clarté différente
        couleur = nuance(base, [0, 0.25, -0.25, 0.45][(vus_cle[cle] - 1) % 4])
        inter[r["id"]] = dict(id=r["id"], nom=r["name"], sigle=r["sigle"] or acronyme(r["name"]),
                              debut=r["start"], fin=r["end"], couleur=couleur,
                              pred=[p for p in r["predecessor_id"].split(" | ") if p], membres=[])
    orgs = {}
    for r in lire("organisations.csv"):
        if r.get("garde") != "oui":
            continue
        s = sigles.get(r["id"], {})
        sigle = (s.get("sigle") or "").strip()
        nom_court = (s.get("short_name") or r["nom_court"] or r["label"]).strip()
        statut = r["statut_fin"]
        t0 = t_de(r["fondation"], r["fondation_mois"])
        if statut.startswith("actif"):
            t1, fin_txt = None, ""
        elif r["dissolution"]:
            t1, fin_txt = t_de(r["dissolution"], r["dissolution_mois"]), r["dissolution"]
        elif r["fin_deduite"]:
            t1, fin_txt = t_de(r["fin_deduite"]), r["fin_deduite"]
        else:
            t1, fin_txt = None, "fin inconnue"
        fam_c = r["famille_courant"] or r["famille"]
        couleur = nuance(TEINTE.get(fam_c, TEINTE["à classer"]), NUANCES.get(r["courant_principal"], 0))

        def date_longue(a, m):
            return f"{MOIS[int(m) - 1]} {a}" if m else str(a)
        fin_detail = ("toujours active" + (" (provisoire : à valider dans actifs.csv)"
                                           if statut == "actif_provisoire" else "")
                      if statut.startswith("actif") else
                      f"fin : {date_longue(r['dissolution'], r['dissolution_mois'])} ({r['dissolution_source']})"
                      if r["dissolution"] else
                      f"fin : {r['fin_deduite']} ({r['fin_deduite_source']})" if r["fin_deduite"] else
                      "fin inconnue")
        details = [r["label"], f"fondation : {date_longue(r['fondation'], r['fondation_mois'])} "
                               f"({r['fondation_source']})", fin_detail,
                   f"famille : {r['famille']}", f"courants : {r['courants_sources'] or 'aucun reconnu'}"]
        if r.get("organisations_liees"):
            details.append(f"organisations liées : {r['organisations_liees']}")
        if r["journaux"]:
            details.append(f"journaux : {r['journaux']}")
        if r["perimetre_douteux"]:
            details.append(f"à vérifier : {r['perimetre_douteux']}")
        details.append(f"sources : {r['sources']}")
        orgs[r["id"]] = dict(id=r["id"], label=r["label"], sigle=sigle, nom_court=nom_court,
                             voie=r["famille"], couleur=couleur, t0=t0, t1=t1, statut=statut,
                             an0=r["fondation"], fin_txt=fin_txt, details=details, affil=[],
                             sans_date=False)
    for r in lire("sans_date.csv"):
        if r.get("garde") != "oui":
            continue
        s = sigles.get(r["id"], {})
        orgs[r["id"]] = dict(id=r["id"], label=r["label"], sigle=(s.get("sigle") or "").strip(),
                             nom_court=(s.get("short_name") or r["label"]).strip(), voie="sans date",
                             couleur=TEINTE.get(r["famille"], "#8C8C8C"), t0=None, t1=None,
                             statut="sans date", an0="?", fin_txt="?", affil=[], sans_date=True,
                             details=[r["label"], "date de fondation inconnue : hors échelle, sans lien",
                                      f"famille : {r['famille']}", f"sources : {r['sources']}"])
    for r in lire("affiliations.csv"):
        if r["party_id"] in orgs and r["international_id"] in inter and not orgs[r["party_id"]]["sans_date"]:
            orgs[r["party_id"]]["affil"].append(r)
            inter[r["international_id"]]["membres"].append(r["party_id"])
    liens = [dict(a=r["source"], b=r["cible"], rel=r["relation"],
                  t=t_de(r["date_evenement"], r["date_evenement_mois"]))
             for r in lire("liens.csv") if r["source"] in orgs and r["cible"] in orgs]
    return orgs, liens, inter, T_AUJ


# ======================================================================
# Échelle de temps (linéaire, avec cassure explicite si un trou de plus de 60 ans)
# ======================================================================

class Echelle:
    def __init__(self, debuts, T_AUJ):
        d = sorted(debuts)
        self.T0 = math.floor(d[0] / 10) * 10 if d else 1900
        self.T1 = math.ceil(T_AUJ / 10) * 10
        self.cassure = None
        for a, b in zip(d, d[1:]):
            if b - a > CASSURE_ANS:
                # Le premier groupe garde son échelle, l'axe reprend à la décennie du groupe suivant
                self.cassure = (math.ceil((a + 5) / 10) * 10, math.floor(b / 10) * 10)
                break

    def X(self, t):
        if not self.cassure:
            return X0 + (t - self.T0) * PPA
        a1, b0 = self.cassure
        if t <= a1:
            return X0 + (t - self.T0) * PPA
        if t >= b0:
            return X0 + (a1 - self.T0) * PPA + CASSURE_PX + (t - b0) * PPA
        return X0 + (a1 - self.T0) * PPA + (t - a1) / (b0 - a1) * CASSURE_PX

    def graduations(self):
        for a in range(self.T0, self.T1 + 1, 10):
            if self.cassure and self.cassure[0] < a < self.cassure[1]:
                continue
            yield a


# ======================================================================
# Mise en page
# ======================================================================

def preparer_items(orgs, inter, ech, T_AUJ):
    """Barre, étiquette, cadres d'affiliation et onglets de chaque organisation (positions x)."""
    for o in orgs.values():
        # --- Étiquette : sigle en gras (ou nom court), nom complet en petit (2 lignes au plus), dates ---
        dates = f"{o['an0']}–{o['fin_txt']}" if o["fin_txt"] != "fin inconnue" else f"{o['an0']} – fin inconnue"
        lignes = []
        if o["sans_date"]:
            dates = ""
        if o["sigle"]:
            lignes.append([(o["sigle"], FS_SIGLE, True, "sigle"), (dates, FS, False, "dates")])
            for l in couper(o["label"], TAG_NOM_MAX, FS):
                lignes.append([(l, FS, False, "nom")])
        else:
            noms = couper(o["nom_court"], TAG_NOM_MAX, 12, True)
            for l in noms[:-1]:
                lignes.append([(l, 12, True, "sigle")])
            der = noms[-1]
            if dates and larg(der, 12, True) + 6 + larg(dates, FS) <= TAG_NOM_MAX:
                lignes.append([(der, 12, True, "sigle"), (dates, FS, False, "dates")])
            else:
                lignes.append([(der, 12, True, "sigle")])
                if dates:
                    lignes.append([(dates, FS, False, "dates")])
        lignes = [[m for m in l if m[0]] for l in lignes]
        o["tag_lignes"] = lignes
        o["tag_w"] = max(sum(larg(t, fs, g) + (6 if i else 0) for i, (t, fs, g, _) in enumerate(l))
                         for l in lignes) + 2 * TAG_PAD
        o["tag_h"] = 6 + LIGNE * len(lignes)
        o["tag_cote"] = "droite"
        o["renv_in"], o["renv_out"] = [], []
        o["cadres"], o["n_niv"] = [], 0
        if o["sans_date"]:
            continue
        o["x0"] = ech.X(o["t0"])
        if o["t1"] is not None:
            o["x1"] = max(ech.X(o["t1"]), o["x0"] + MIN_W)
            o["x1_vis"] = o["x1"]
        elif o["statut"].startswith("actif"):
            o["x1"] = max(ech.X(T_AUJ), o["x0"] + MIN_W)
            o["x1_vis"] = o["x1"] + DEGRADE
        else:                                   # fin inconnue : courte barre et queue hachurée
            o["x1"] = o["x0"] + MIN_W
            o["x1_vis"] = o["x1"] + QUEUE
        # --- Cadres d'affiliation, emboîtés par niveau (intervalle le plus long à l'extérieur) ---
        cadres = []
        for a in o["affil"]:
            d = inter[a["international_id"]]
            fin_o = o["t1"] if o["t1"] is not None else T_AUJ
            ta = max(o["t0"], t_de(a["start"])) if a["start"] else o["t0"]
            tb = min(fin_o, t_de(a["end"])) if a["end"] else fin_o
            if tb <= ta:
                ta, tb = o["t0"], fin_o
            cadres.append(dict(intl=a["international_id"], ta=ta, tb=tb, connu=a["date_certainty"] == "known",
                               sortie=bool(a["end"]) or o["t1"] is not None, couleur=d["couleur"],
                               sigle=d["sigle"], nom=d["nom"]))
        cadres.sort(key=lambda c: (c["tb"] - c["ta"]))
        for c in cadres:   # niveau : le plus petit qui ne touche aucun cadre déjà placé
            pris = {c2["niveau"] for c2 in cadres if "niveau" in c2 and c2["ta"] < c["tb"] and c["ta"] < c2["tb"]}
            c["niveau"] = next(n for n in range(1, 10) if n not in pris)
        o["n_niv"] = max((c["niveau"] for c in cadres), default=0)
        for c in cadres:
            pad = 3 + (c["niveau"] - 1) * FRAME_PAS + FRAME_W / 2
            c["pad"] = pad
            c["xa"] = max(o["x0"], ech.X(c["ta"])) - pad
            c["xb"] = min(o["x1"], ech.X(c["tb"])) + pad
        # Onglets : au-dessus du cadre extérieur, de gauche à droite, sans se chevaucher
        pad_max = 3 + (o["n_niv"] - 1) * FRAME_PAS + FRAME_W if o["n_niv"] else 0
        x_min = o["x0"] - pad_max
        x_lib = -1e9
        for c in sorted(cadres, key=lambda c: c["xa"]):
            c["tab_txt"] = c["sigle"] + ("" if c["connu"] else " ?")
            c["tab_w"] = larg(c["tab_txt"], FS, True) + 8
            x = max(c["xa"] + 4, x_lib + 3)
            if o["tag_cote"] == "gauche":          # étiquette à gauche : l'onglet ne déborde pas dessus
                x = max(x, o["x0"] + 1)
            elif x + c["tab_w"] > o["x1"] - 2:     # étiquette à droite : l'onglet ne passe pas dessous
                x = max(x_min, x_lib + 3, o["x1"] - 2 - c["tab_w"])
            c["tab_x"] = x
            x_lib = x + c["tab_w"]
        o["cadres"] = cadres
        o["pad_max"] = pad_max
        # Hauteur du haut des onglets au-dessus du centre de la barre. Si un onglet déborde de la
        # barre du côté de l'étiquette (barre très courte), il passe au-dessus de l'étiquette.
        o["tab_haut"] = BAR_H / 2 + pad_max + TAB_H if cadres else 0
        deborde = any((c["tab_x"] + c["tab_w"] > o["x1_vis"]) if o["tag_cote"] == "droite"
                      else (c["tab_x"] < o["x0"]) for c in cadres)
        if deborde:
            o["tab_haut"] = max(o["tab_haut"], o["tag_h"] / 2 + TAB_H + 1)
        o["tab_gauche"] = min((c["tab_x"] for c in cadres), default=o["x0"])
        o["tab_droite"] = max((c["tab_x"] + c["tab_w"] for c in cadres), default=o["x0"])


def mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues=None, titre=""):
    voies_ordre = [v for v, _, _ in VOIES] + ["sans date"]
    if voies_voulues:
        voies_ordre = [v for v in voies_ordre if v in voies_voulues]
    items = {q: dict(o) for q, o in orgs.items() if o["voie"] in voies_ordre}
    ech = Echelle([o["t0"] for o in items.values() if o["t0"] is not None], T_AUJ)
    rang_voie = {v: i for i, v in enumerate(voies_ordre)}
    anomalies = []

    # ---------- Continuations : renommage dans la même voie, barres qui se touchent ----------
    par_cible, par_source = defaultdict(list), defaultdict(list)
    for l in liens:
        par_cible[l["b"]].append(l)
        par_source[l["a"]].append(l)
    preparer_items(items, inter, ech, T_AUJ)
    continuations = set()
    for l in liens:
        a, b = items.get(l["a"]), items.get(l["b"])
        if (a and b and l["rel"] == "renommage" and a["voie"] == b["voie"] != "sans date"
                and a["t1"] is not None and 0 <= b["x0"] - a["x1"] < GAP
                and len(par_cible[l["b"]]) == 1
                and sum(1 for x in par_source[l["a"]] if x["rel"] == "renommage") == 1):
            continuations.add((l["a"], l["b"]))
            a["tag_cote"] = "gauche"        # l'étiquette ne doit pas recouvrir la suite
    preparer_items(items, inter, ech, T_AUJ)      # onglets recalculés avec le côté de l'étiquette
    for a, _ in continuations:
        items[a]["tag_cote"] = "gauche"

    # ---------- Liens : tracés ou renvois (boucle : la distance en rangées dépend du placement) ----------
    renvoi_force = set()
    for _ in range(10):
        poly, renvois = [], []
        for l in liens:
            a, b = items.get(l["a"]), items.get(l["b"])
            if a is None and b is None:
                continue
            if a is None or b is None:
                renvois.append(dict(l, raison="hors de cette vue"))
                continue
            if a["sans_date"] or b["sans_date"] or (l["a"], l["b"]) in continuations:
                continue
            ev = abs(rang_voie[a["voie"]] - rang_voie[b["voie"]])
            t_dep = min(l["t"] - GOUTTIERE / PPA, a["t1"] if a["t1"] is not None else T_AUJ)
            if ev > SEUIL_VOIES or l["t"] - t_dep > SEUIL_ANNEES or (l["a"], l["b"]) in renvoi_force:
                renvois.append(dict(l, raison="trop long"))
            else:
                poly.append(dict(l))
        entrants = defaultdict(list)
        for l in poly:
            entrants[l["b"]].append(l)
        for o in items.values():
            o["renv_in"], o["renv_out"] = [], []
        for r in renvois:
            a, b = items.get(r["a"]), items.get(r["b"])
            if a is not None:
                cible = b or orgs[r["b"]]
                a["renv_out"].append((f"→ {cible['sigle'] or cible['nom_court']}", r["b"]))
            if b is not None:
                src = a or orgs[r["a"]]
                mot = {"scission": "scission de", "passage": "militants de"}.get(r["rel"], "issu de")
                b["renv_in"].append((f"{mot} {src['sigle'] or src['nom_court']}", r["a"]))
        for o in items.values():
            if o["sans_date"]:
                continue
            o["w_renv"] = sum(larg(t, FS) + 6 for t, _ in o["renv_in"] + o["renv_out"])
            gauche_lien = (GOUTTIERE + 6) if entrants.get(o["id"]) else 0
            L = min(o["x0"] - gauche_lien - o["pad_max"], o["tab_gauche"])
            R = max(o["x1_vis"], o["x1"] + o["pad_max"], o["tab_droite"])
            if o["tag_cote"] == "droite":
                R = max(R, o["x1_vis"] + o["tag_w"] + o["w_renv"])
            else:
                L = min(L, o["x0"] - o["tag_w"] - o["w_renv"])
            o["L"], o["R"] = L, R
        rangees = placer(items, voies_ordre, liens, poly, continuations)
        trop = {(l["a"], l["b"]) for l in poly
                if abs(items[l["a"]]["rang_g"] - items[l["b"]]["rang_g"]) > SEUIL_RANGS}
        if not trop:
            break
        renvoi_force |= trop

    # ---------- Ordonnées ----------
    entete_h, axe_h = 160, 34
    y = entete_h + axe_h
    voies_geo = []
    for v in voies_ordre:
        membres = [o for o in items.values() if o["voie"] == v]
        if not membres:
            continue
        y_voie = y
        if v == "sans date":
            y += axe_h + 12
            y_voie = y
            xc, ligne, x_max = X0, 0, ech.X(ech.T1)
            hmax = max(o["tag_h"] for o in membres)
            for o in sorted(membres, key=lambda o: o["label"]):
                if xc + o["tag_w"] > x_max and xc > X0:
                    xc, ligne = X0, ligne + 1
                o["tag_x"] = xc
                o["y_c"] = y_voie + VOIE_PAD + ligne * (hmax + ROW_GAP) + hmax / 2
                xc += o["tag_w"] + GAP
            h = 2 * VOIE_PAD + (ligne + 1) * (hmax + ROW_GAP)
            voies_geo.append(dict(cle=v, y=y_voie, h=h, n=len(membres)))
            y += h
            continue
        y += VOIE_PAD
        info = rangees[v]
        for i, contenu in enumerate(info["rangees"]):
            haut = bas = 0
            for q in contenu:
                o = items[q]
                haut = max(haut, o["tag_h"] / 2, BAR_H / 2 + o["pad_max"], o["tab_haut"])
                bas = max(bas, o["tag_h"] / 2, BAR_H / 2 + o["pad_max"])
            if i in info["debuts_blocs"] and i:
                y += 8           # écart entre deux arbres
            for q in contenu:
                items[q]["y_c"] = y + ROW_GAP / 2 + haut
                items[q]["rang_y"], items[q]["rang_h"] = y, haut + bas + ROW_GAP
            y += haut + bas + ROW_GAP
        y += VOIE_PAD
        voies_geo.append(dict(cle=v, y=y_voie, h=y - y_voie, n=len(membres)))
    if not any(g["cle"] == "sans date" for g in voies_geo):
        y += axe_h + 12
    y_axe_bas = next((g["y"] - axe_h - 12 for g in voies_geo if g["cle"] == "sans date"), y - axe_h - 12)
    for i, g in enumerate(voies_geo):
        g["i"] = i
    voie_index = {g["cle"]: g["i"] for g in voies_geo}

    # ---------- Géométrie des liens ----------
    traces = []
    entrants = defaultdict(list)
    for l in poly:
        entrants[l["b"]].append(l)
    for qb, ls in entrants.items():
        b = items[qb]
        ls.sort(key=lambda l: items[l["a"]]["y_c"])
        n = len(ls)
        for k, l in enumerate(ls):
            a = items[l["a"]]
            off = max(-(BAR_H / 2 - 3), min(BAR_H / 2 - 3, (k - (n - 1) / 2) * 5))
            xt, yt = b["x0"], b["y_c"] + off
            bas = yt > a["y_c"]
            if a["x1"] < xt - GOUTTIERE:            # la source a fini avant : départ de son extrémité
                xs, xv = a["x1"], xt - GOUTTIERE
                if a["rang_y"] == b["rang_y"]:
                    pts = [(xs, yt), (xt, yt)]
                else:
                    canal = a["rang_y"] + a["rang_h"] - 3 if bas else a["rang_y"] + 2
                    pts = [(xs, a["y_c"]), (xs, canal), (xv, canal), (xv, yt), (xt, yt)]
                depart = None
            else:
                xs = max(xt - GOUTTIERE, a["x0"] + min(2, (xt - a["x0"]) / 2))
                y_bord = a["y_c"] + BAR_H / 2 if bas else a["y_c"] - BAR_H / 2
                pts = [(xs, y_bord), (xs, yt), (xt, yt)]
                depart = (xs, y_bord, 1 if bas else -1)
            voies_pts = ([a["voie"]] * (len(pts) - 2) + [b["voie"]] * 2) if len(pts) > 2 else [a["voie"], b["voie"]]
            if xt - pts[-2][0] < 3:
                anomalies.append([l["a"], l["b"], l["rel"], a["an0"], b["an0"],
                                  "dates trop proches : segment final de moins de 3 px"])
                continue
            principal = l["rel"] in ("renommage", "filiation") or (l["rel"] == "fusion" and a["voie"] == b["voie"])
            traces.append(dict(l, pts=pts, voies_pts=voies_pts, depart=depart, principal=principal,
                               annees=(xt - pts[0][0]) / PPA,
                               voies=abs(rang_voie[a["voie"]] - rang_voie[b["voie"]]),
                               rangs=abs(a["rang_g"] - b["rang_g"])))

    # ---------- Clé des Internationales ----------
    utiles = {c["intl"] for o in items.values() for c in o.get("cadres", [])}
    succ = defaultdict(list)
    for i, d in inter.items():
        for p in d["pred"]:
            succ[p].append(i)

    def chaine(i):
        racine, vus = i, set()
        while inter[racine]["pred"] and racine not in vus and inter[racine]["pred"][0] in inter:
            vus.add(racine)
            racine = inter[racine]["pred"][0]
        etapes, x, vus = [], racine, set()
        while x and x not in vus:
            vus.add(x)
            etapes.append(f"{inter[x]['nom']} {inter[x]['debut'] or '?'}–{inter[x]['fin']}")
            x = next((s for s in succ[x] if s in inter), None)
        return ", puis ".join(etapes) if len(etapes) > 1 else ""

    cle = [dict(id=i, sigle=inter[i]["sigle"], nom=inter[i]["nom"],
                dates=f"{inter[i]['debut'] or '?'}–{inter[i]['fin']}", couleur=inter[i]["couleur"],
                succession=chaine(i), membres=[q for q in inter[i]["membres"] if q in items])
           for i in sorted(utiles, key=lambda i: (inter[i]["debut"] or "9999", inter[i]["nom"]))]

    largeur = max([o.get("R", 0) for o in items.values()]
                  + [o.get("tag_x", 0) + o["tag_w"] for o in items.values() if o["sans_date"]]
                  + [ech.X(ech.T1)]) + 40
    return dict(items=items, traces=traces, renvois=renvois, continuations=continuations,
                voies=voies_geo, voie_index=voie_index, ech=ech, T_AUJ=T_AUJ, largeur=largeur,
                hauteur=y, y_axe_haut=entete_h, y_axe_bas=y_axe_bas, cle=cle, inter=inter,
                titre=titre, anomalies=anomalies, rels=sorted({t["rel"] for t in traces}))


def placer(items, voies_ordre, liens, poly, continuations):
    """Rangées par voie. Chaque arbre (composante reliée dans la voie) forme un bloc contigu :
    racine en haut, descendants dessous par date, au plus près de leur ancêtre."""
    voisins, parents = defaultdict(set), defaultdict(list)
    for l in liens:
        a, b = items.get(l["a"]), items.get(l["b"])
        if a and b and a["voie"] == b["voie"]:
            voisins[l["a"]].add(l["b"])
            voisins[l["b"]].add(l["a"])
    for l in poly:
        parents[l["b"]].append(l["a"])
    cont_parent = {b: a for a, b in continuations}
    res, rang_global = {}, 0
    for v in voies_ordre:
        if v == "sans date":
            continue
        membres = [q for q, o in items.items() if o["voie"] == v]
        blocs, vus = [], set()
        for q in sorted(membres, key=lambda q: (items[q]["x0"], items[q]["label"])):
            if q in vus:
                continue
            comp, pile = set(), [q]
            while pile:
                x = pile.pop()
                if x not in comp:
                    comp.add(x)
                    pile.extend(y for y in voisins[x] if items[y]["voie"] == v)
            vus |= comp
            blocs.append(sorted(comp, key=lambda x: (items[x]["x0"], items[x]["label"])))
        rangees, debuts = [], set()
        for bloc in blocs:
            debut = len(rangees)
            debuts.add(debut)
            local = []

            def libre(r, L, R, sauf=None):
                for l2, r2, q2 in local[r]:
                    if q2 == sauf and L >= items[q2]["x1"] - 0.5 - (items[q2]["x1"] - l2 if False else 0):
                        continue
                    if not (R + GAP <= l2 or r2 + GAP <= L):
                        return False
                return True
            for q in bloc:
                o = items[q]
                o.pop("rang_l", None)
                place = None
                p = cont_parent.get(q)
                if p and "rang_l" in items[p] and libre(items[p]["rang_l"], o["L"], o["R"], sauf=p):
                    place = items[p]["rang_l"]
                if place is None:
                    prefs = [items[p]["rang_l"] for p in parents[q] if p in bloc and "rang_l" in items[p]]
                    pref = prefs[0] + 1 if prefs else 0
                    ordre = sorted(range(len(local)), key=lambda r: (abs(r - pref), r < pref))
                    place = next((r for r in ordre if libre(r, o["L"], o["R"])), len(local))
                if place == len(local):
                    local.append([])
                local[place].append((o["L"], o["R"], q))
                o["rang_l"] = place
            for r in local:
                rangees.append([q for _, _, q in r])
            for q in bloc:
                items[q]["rang_g"] = rang_global + debut + items[q]["rang_l"]
        rang_global += len(rangees)
        res[v] = dict(rangees=rangees, debuts_blocs=debuts)
    return res


# ======================================================================
# SVG
# ======================================================================

def defs_communs(m):
    out = []
    for c in {o["couleur"] for o in m["items"].values()} | {"#8C8C8C"}:
        out.append(f'<linearGradient id="g-{c[1:]}"><stop offset="0" stop-color="{c}"/>'
                   f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>')
        out.append(f'<pattern id="h-{c[1:]}" width="6" height="6" patternUnits="userSpaceOnUse" '
                   f'patternTransform="rotate(45)"><rect width="6" height="6" fill="#FFFFFF"/>'
                   f'<rect width="2.5" height="6" fill="{melange(c, "#FFFFFF", 0.35)}"/></pattern>')
    return "".join(out)


def dessiner(m, avec_cle=True, apercu=False):
    items, ech = m["items"], m["ech"]
    X = ech.X
    W = m["largeur"]
    fond, voies_svg, liens_svg, etiq_svg = [], defaultdict(list), [], defaultdict(list)

    # ---------- Voies, bandes de décennies, axes ----------
    for g in m["voies"]:
        c = TEINTE[g["cle"]]
        fond_c = melange(c, "#FFFFFF", 0.90 if g["i"] % 2 == 0 else 0.95)
        fond.append(f'<g class="voie" data-voie="{g["i"]}" data-cle="{esc(g["cle"])}">'
                    f'<rect class="fond-voie" x="0" y="{g["y"]:.1f}" width="{W:.1f}" height="{g["h"]:.1f}" fill="{fond_c}"/>'
                    f'<rect class="bord-voie" x="0" y="{g["y"]:.1f}" width="8" height="{g["h"]:.1f}" fill="{c}"/>'
                    + texte(16, g["y"] + 20, TITRES[g["cle"]], 13, True, "#1A1A1A", cls="voie-t")
                    + texte(16, g["y"] + 36, f"{g['n']} organisation{'s' if g['n'] > 1 else ''}", FS,
                            False, "#333333", cls="voie-t") + "</g>")
    y_h, y_b = m["y_axe_haut"], m["y_axe_bas"]
    for a in ech.graduations():
        if (a // 10) % 2 == 0 and a < ech.T1:
            fond.append(f'<rect class="bande-decennie" x="{X(a):.1f}" y="{y_h:.1f}" width="{X(a + 10) - X(a):.1f}" '
                        f'height="{y_b - y_h + 30:.1f}" fill="#000000" fill-opacity="0.035"/>')

    def axe(y, haut, cls):
        p = [f'<g class="{cls}"><line x1="{X(ech.T0):.1f}" x2="{X(ech.T1):.1f}" y1="{y:.1f}" y2="{y:.1f}" '
             f'stroke="#555555"/>']
        for a in ech.graduations():
            p.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="{y - 5:.1f}" y2="{y + 5:.1f}" stroke="#555555"/>')
            p.append(texte(X(a), y - 9 if haut else y + 20, str(a), 12, True, "#333333", "middle", cls="axe-t"))
        if ech.cassure:     # symbole de cassure explicite
            xc = X(ech.cassure[0]) + CASSURE_PX / 2
            p.append(f'<rect x="{xc - 9:.1f}" y="{y - 8:.1f}" width="18" height="16" fill="#FFFFFF"/>'
                     f'<path d="M{xc - 8:.1f} {y + 7:.1f} L{xc - 2:.1f} {y - 7:.1f} M{xc + 2:.1f} {y + 7:.1f} '
                     f'L{xc + 8:.1f} {y - 7:.1f}" stroke="#333333" stroke-width="2"/>')
        p.append("</g>")
        return "".join(p)
    fond.append(axe(y_h + 26, True, "axe-haut"))
    fond.append(axe(y_b + 4, False, "axe-bas"))
    xa = X(m["T_AUJ"])
    fond.append(f'<line x1="{xa:.1f}" x2="{xa:.1f}" y1="{y_h + 26:.1f}" y2="{y_b + 4:.1f}" stroke="#777777" '
                f'stroke-dasharray="2 4"/>')

    # ---------- Organisations : barre + cadres (calque bas), étiquette + onglets + renvois (calque haut) ----------
    for o in sorted(items.values(), key=lambda o: (o.get("y_c", 0), o.get("x0", 0))):
        if "y_c" not in o:
            continue
        vi = m["voie_index"][o["voie"]]
        intl = " ".join(c["intl"] for c in o.get("cadres", []))
        recherche = sans_accents(f"{o['sigle']} {o['nom_court']} {o['label']}")
        ouvre = (f'<g class="org" data-id="{esc(o["id"])}" data-intl="{esc(intl)}" '
                 f'data-recherche="{esc(recherche)}"><title>{esc(chr(10).join(o["details"]))}</title>')
        bas, haut = [ouvre], [ouvre.replace('class="org"', 'class="org org-haut"')]
        yc = o["y_c"]
        if o["sans_date"]:
            x, w, h = o["tag_x"], o["tag_w"], o["tag_h"]
            haut.append(f'<rect class="tag sans-date" data-id="{esc(o["id"])}" x="{x:.2f}" y="{yc - h / 2:.2f}" '
                        f'width="{w:.2f}" height="{h:.2f}" rx="3" fill="url(#h-{o["couleur"][1:]})" '
                        f'stroke="{o["couleur"]}" stroke-width="1.5" data-bbox="{x:.2f},{yc - h / 2:.2f},{w:.2f},{h:.2f}"/>')
            haut += lignes_tag(o, x, yc - h / 2, "#1A1A1A", "#333333")
        else:
            x0, x1 = o["x0"], o["x1"]
            yb = yc - BAR_H / 2
            fin = "actif" if o["statut"].startswith("actif") else (
                f"{o['t1']:.4f}" if o["t1"] is not None else "inconnue")
            if not apercu:
                for c in sorted(o["cadres"], key=lambda c: -c["niveau"]):
                    bas.append(cadre(o, c, yc))
            bas.append(f'<rect class="barre" data-id="{esc(o["id"])}" data-debut="{o["t0"]:.4f}" '
                       f'data-fin="{fin}" data-statut="{o["statut"]}" x="{x0:.2f}" y="{yb:.2f}" '
                       f'width="{x1 - x0:.2f}" height="{BAR_H}" rx="{0 if o["x1_vis"] > x1 else 3}" '
                       f'fill="{o["couleur"]}"/>')
            if o["x1_vis"] > x1:
                actif = o["statut"].startswith("actif")
                motif = f"url(#g-{o['couleur'][1:]})" if actif else f"url(#h-{o['couleur'][1:]})"
                bas.append(f'<rect class="fin-ouverte" x="{x1:.2f}" y="{yb:.2f}" width="{o["x1_vis"] - x1:.2f}" '
                           f'height="{BAR_H}" fill="{motif}"' + ("" if actif else ' fill-opacity="0.7"') + "/>")
            if not apercu:
                w, h = o["tag_w"], o["tag_h"]
                tx = o["x1_vis"] if o["tag_cote"] == "droite" else x0 - w
                o["tag_x"] = tx
                haut.append(f'<rect class="tag" data-id="{esc(o["id"])}" x="{tx:.2f}" y="{yc - h / 2:.2f}" '
                            f'width="{w:.2f}" height="{h:.2f}" rx="4" fill="{o["couleur"]}" '
                            f'data-bbox="{tx:.2f},{yc - h / 2:.2f},{w:.2f},{h:.2f}"/>')
                haut += lignes_tag(o, tx, yc - h / 2, texte_sur(o["couleur"]), gris_sur(o["couleur"]))
                for c in o["cadres"]:
                    ty = yc - o["tab_haut"]
                    fill = c["couleur"] if c["connu"] else melange(c["couleur"], "#FFFFFF", 0.15)
                    haut.append(f'<g class="onglet" data-intl="{esc(c["intl"])}" data-parti="{esc(o["id"])}">'
                                f'<title>{esc(c["nom"])}' + ("" if c["connu"] else " : dates à confirmer")
                                + f'</title><rect class="onglet-r" x="{c["tab_x"]:.2f}" y="{ty:.2f}" '
                                f'width="{c["tab_w"]:.2f}" height="{TAB_H}" rx="3" fill="{fill}" '
                                f'data-bbox="{c["tab_x"]:.2f},{ty:.2f},{c["tab_w"]:.2f},{TAB_H}"/>'
                                + texte(c["tab_x"] + 4, ty + 11.5, c["tab_txt"], FS, True, texte_sur(fill),
                                        cls="onglet-t",
                                        extra=f' data-bbox="{c["tab_x"] + 4:.2f},{ty + 1:.2f},{c["tab_w"] - 8:.2f},13"')
                                + "</g>")
                tous = o["renv_in"] + o["renv_out"]
                if o["tag_cote"] == "droite":
                    xr = tx + w
                    for t, autre in tous:
                        wt = larg(t, FS)
                        haut.append(renvoi(xr, yc, t, wt, o["id"], autre, t.startswith("→")))
                        xr += wt + 6
                else:
                    xr = tx
                    for t, autre in tous:
                        wt = larg(t, FS)
                        xr -= wt + 6
                        haut.append(renvoi(xr, yc, t, wt, o["id"], autre, t.startswith("→")))
        bas.append("</g>")
        haut.append("</g>")
        voies_svg[vi].append("".join(bas))
        etiq_svg[vi].append("".join(haut))

    for a, b in m["continuations"]:
        o = items[b]
        xj, yj = o["x0"], o["y_c"]
        vi = m["voie_index"][o["voie"]]
        etiq_svg[vi].append(
            f'<g class="continuation" data-a="{esc(a)}" data-b="{esc(b)}"><title>renommage : '
            f'{esc(items[a]["label"])} devient {esc(o["label"])}</title>'
            f'<polyline points="{xj - 4:.1f},{yj - 6:.1f} {xj + 3:.1f},{yj:.1f} {xj - 4:.1f},{yj + 6:.1f}" '
            f'fill="none" stroke="#FFFFFF" stroke-width="4"/>'
            f'<polyline points="{xj - 4:.1f},{yj - 6:.1f} {xj + 3:.1f},{yj:.1f} {xj - 4:.1f},{yj + 6:.1f}" '
            f'fill="none" stroke="#1A1A1A" stroke-width="1.6"/></g>')

    # ---------- Liens ----------
    fusions = defaultdict(list)
    for t in m["traces"]:
        st = STYLE_LIEN[t["rel"]]
        w = st["w"][0] if t["principal"] else st["w"][1]
        pts = t["pts"]
        d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts)
        geo = json.dumps([[round(x, 2), round(y, 2), m["voie_index"][v]] for (x, y), v in zip(pts, t["voies_pts"])])
        xt, yt = pts[-1]
        fl = [(xt, yt), (xt - FLECHE_L, yt - FLECHE_DEMI), (xt - FLECHE_L, yt + FLECHE_DEMI)]
        vb = m["voie_index"][items[t["b"]]["voie"]]
        g = [f'<g class="lien" data-a="{esc(t["a"])}" data-b="{esc(t["b"])}" data-rel="{t["rel"]}" '
             f'data-annees="{t["annees"]:.2f}" data-voies="{t["voies"]}" data-rangs="{t["rangs"]}" '
             f'data-va="{m["voie_index"][items[t["a"]]["voie"]]}" data-vb="{vb}">'
             f'<title>{esc(NOMS_LIENS[t["rel"]])} : {esc(items[t["a"]]["label"])} → {esc(items[t["b"]]["label"])} '
             f'({items[t["b"]]["an0"]})</title>',
             f'<path class="halo geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="#FFFFFF" '
             f'stroke-width="{w + 2.5:.1f}" stroke-opacity="0.85"/>',
             f'<path class="trait geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="{st["couleur"]}" '
             f'stroke-width="{w}"' + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + "/>",
             f'<polygon class="fleche geo" data-geo=\'{json.dumps([[round(x, 2), round(y, 2), vb] for x, y in fl])}\' '
             f'points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in fl)}" fill="{st["couleur"]}"/>']
        if t["rel"] == "scission" and t["depart"]:
            xs, ys, dn = t["depart"]
            fk = [(xs - 4, ys + dn * 6), (xs, ys), (xs + 4, ys + dn * 6)]
            va = m["voie_index"][items[t["a"]]["voie"]]
            g.append(f'<polyline class="fourche geo" data-geo=\'{json.dumps([[round(x, 2), round(y, 2), va] for x, y in fk])}\' '
                     f'points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in fk)}" fill="none" stroke="{st["couleur"]}" '
                     f'stroke-width="1.6"/>')
        if t["rel"] == "fusion":
            fusions[t["b"]].append(yt)
        g.append("</g>")
        liens_svg.append("".join(g))
    for qb, ys in fusions.items():
        o = items[qb]
        xm = o["x0"] - FLECHE_L - 2
        vb = m["voie_index"][o["voie"]]
        geo = json.dumps([[round(xm, 2), round(min(ys) - 3, 2), vb], [round(xm, 2), round(max(ys) + 3, 2), vb]])
        liens_svg.append(f'<g class="marque-fusion" data-b="{esc(qb)}"><path class="geo" data-geo=\'{geo}\' '
                         f'd="M{xm:.2f} {min(ys) - 3:.2f} L{xm:.2f} {max(ys) + 3:.2f}" stroke="#3D3D3D" '
                         f'stroke-width="3"/></g>')

    H = m["hauteur"] + 20
    cle_svg = ""
    if avec_cle and m["cle"] and not apercu:
        cle_svg, h_cle = cle_internationales(m, H, W)
        H += h_cle
    attrs = (f'data-x0="{X0}" data-t0="{ech.T0}" data-ppa="{PPA}" data-aujourdhui="{m["T_AUJ"]:.4f}" '
             f'data-min-w="{MIN_W}" data-seuil-annees="{SEUIL_ANNEES}" data-seuil-voies="{SEUIL_VOIES}" '
             f'data-seuil-rangs="{SEUIL_RANGS}" data-cassure="{",".join(map(str, ech.cassure)) if ech.cassure else ""}" '
             f'data-cassure-px="{CASSURE_PX}"' + (' data-apercu="oui"' if apercu else ""))
    corps = (f'<svg xmlns="http://www.w3.org/2000/svg" id="arbre" width="{W:.0f}" height="{H:.0f}" '
             f'viewBox="0 0 {W:.0f} {H:.0f}" {attrs} font-family="{POLICE}">'
             f'<title>Généalogie des organisations de gauche en France</title><defs>{defs_communs(m)}</defs>'
             f'<rect width="{W:.0f}" height="{H:.0f}" fill="#FFFFFF"/>' + "".join(fond))
    for g in m["voies"]:
        corps += f'<g class="contenu-voie" data-voie="{g["i"]}">' + "".join(voies_svg[g["i"]]) + "</g>"
    corps += f'<g class="liens">{"".join(liens_svg)}</g>'
    for g in m["voies"]:
        corps += f'<g class="contenu-voie" data-voie="{g["i"]}">' + "".join(etiq_svg[g["i"]]) + "</g>"
    return corps + legende(m, apercu) + cle_svg + "</svg>"


def lignes_tag(o, x, y, c_txt, c_date):
    out = []
    for k, ligne in enumerate(o["tag_lignes"]):
        xx, yy = x + TAG_PAD, y + 3 + LIGNE * (k + 1) - 2
        for i, (t, fs, gras, sorte) in enumerate(ligne):
            if i:
                xx += 6
            w = larg(t, fs, gras)
            out.append(texte(xx, yy, t, fs, gras, c_date if sorte == "dates" else c_txt, cls="tag-t",
                             extra=f' data-org="{esc(o["id"])}" data-bbox="{xx:.2f},{yy - fs + 1:.2f},{w:.2f},{fs + 1}"'))
            xx += w
    return out


def renvoi(x, yc, t, w, q, autre, sortant):
    a, b = (q, autre) if sortant else (autre, q)
    return texte(x + 3, yc + 4, t, FS, False, "#555555", cls="renvoi", italique=True,
                 extra=f' data-org="{esc(q)}" data-a="{esc(a)}" data-b="{esc(b)}" '
                       f'data-bbox="{x + 3:.2f},{yc - 7:.2f},{w:.2f},13"')


def cadre(o, c, yc):
    """Cadre arrondi autour de la barre pendant l'affiliation ; encoche à la sortie."""
    xa, xb, pad = c["xa"], c["xb"], c["pad"]
    yt, yb = yc - BAR_H / 2 - pad, yc + BAR_H / 2 + pad
    r = 4
    if c["sortie"]:     # encoche en V sur le bord droit : l'organisation sort de l'Internationale
        d = (f"M{xa + r:.2f} {yt:.2f} H{xb:.2f} V{yc - 4:.2f} L{xb - 5:.2f} {yc:.2f} L{xb:.2f} {yc + 4:.2f} "
             f"V{yb:.2f} H{xa + r:.2f} Q{xa:.2f} {yb:.2f} {xa:.2f} {yb - r:.2f} V{yt + r:.2f} "
             f"Q{xa:.2f} {yt:.2f} {xa + r:.2f} {yt:.2f}")
    else:               # toujours membre : cadre ouvert à droite
        d = (f"M{xb:.2f} {yt:.2f} H{xa + r:.2f} Q{xa:.2f} {yt:.2f} {xa:.2f} {yt + r:.2f} V{yb - r:.2f} "
             f"Q{xa:.2f} {yb:.2f} {xa + r:.2f} {yb:.2f} H{xb:.2f}")
    couleur = c["couleur"] if c["connu"] else melange(c["couleur"], "#FFFFFF", 0.35)
    dash = "" if c["connu"] else ' stroke-dasharray="5 3"'
    return (f'<path class="cadre" data-intl="{esc(c["intl"])}" data-parti="{esc(o["id"])}" '
            f'data-xa="{xa:.2f}" data-xb="{xb:.2f}" data-pad="{pad:.2f}" d="{d}" fill="none" '
            f'stroke="{couleur}" stroke-width="{FRAME_W}"{dash}><title>{esc(c["sigle"])} : {esc(c["nom"])}'
            + ("" if c["connu"] else " (dates à confirmer)") + "</title></path>")


def legende(m, apercu):
    el = ['<g class="legende">']
    n = sum(1 for o in m["items"].values() if not o["sans_date"])
    el.append(texte(16, 32, m["titre"] or "Généalogie des organisations de gauche en France", 22, True,
                    "#111111", cls="legende-t"))
    prov = any(o["statut"] == "actif_provisoire" for o in m["items"].values())
    sous = (f"{n} organisations en lignée directe d'une organisation active · {len(m['traces'])} liens · "
            f"échelle linéaire, {PPA:g} px par an · Wikidata et Wikipédia, "
            f"{datetime.date.today().strftime('%d/%m/%Y')}"
            + (" · organisations actives en mode provisoire (à valider)" if prov else "")
            + (" · aperçu : barres seules" if apercu else ""))
    el.append(texte(16, 52, sous, FS, False, "#333333", cls="legende-t"))
    x, y, xmax = 16, 80, m["largeur"] - 20

    def place(w):
        nonlocal x, y
        if x + w > xmax:
            x, y = 16, y + 26
        x0 = x
        x += w + 20
        return x0
    for k, t, c in VOIES:
        if k in m["voie_index"]:
            x0 = place(22 + larg(t, FS))
            el.append(f'<rect x="{x0}" y="{y - 10}" width="16" height="12" rx="2" fill="{c}"/>'
                      + texte(x0 + 22, y, t, FS, cls="legende-t"))
    for rel in ["renommage", "filiation", "fusion", "scission", "passage"]:
        if rel in m["rels"]:
            st = STYLE_LIEN[rel]
            x0 = place(46 + larg(NOMS_LIENS[rel], FS))
            el.append(f'<path d="M{x0} {y - 4} H{x0 + 30}" stroke="{st["couleur"]}" stroke-width="{st["w"][0]}"'
                      + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + ' fill="none"/>'
                      f'<polygon points="{x0 + 38},{y - 4} {x0 + 28},{y - 9} {x0 + 28},{y + 1}" fill="{st["couleur"]}"/>'
                      + texte(x0 + 44, y, NOMS_LIENS[rel], FS, cls="legende-t"))
    if m["continuations"]:
        t = "renommage sur la même rangée"
        x0 = place(26 + larg(t, FS))
        el.append(f'<rect x="{x0}" y="{y - 10}" width="18" height="12" fill="#8C8C8C"/>'
                  f'<polyline points="{x0 + 6},{y - 9} {x0 + 12},{y - 4} {x0 + 6},{y + 1}" fill="none" '
                  f'stroke="#FFFFFF" stroke-width="1.6"/>' + texte(x0 + 26, y, t, FS, cls="legende-t"))
    if m["renvois"] and not apercu:
        t = "issu de X / → Y : lien trop long, en renvoi"
        x0 = place(larg(t, FS))
        el.append(texte(x0, y, t, FS, False, "#555555", cls="legende-t", italique=True))
    statuts = {o["statut"] for o in m["items"].values()}
    if statuts & {"actif_valide", "actif_provisoire"}:
        t = "toujours active"
        x0 = place(40 + larg(t, FS))
        el.append(f'<rect x="{x0}" y="{y - 10}" width="10" height="12" fill="#8C8C8C"/>'
                  f'<rect x="{x0 + 10}" y="{y - 10}" width="24" height="12" fill="url(#g-8C8C8C)"/>'
                  + texte(x0 + 40, y, t, FS, cls="legende-t"))
    if "fin_inconnue" in statuts:
        t = "fin inconnue (queue hachurée)"
        x0 = place(40 + larg(t, FS))
        el.append(f'<rect x="{x0}" y="{y - 10}" width="34" height="12" fill="url(#h-8C8C8C)"/>'
                  + texte(x0 + 40, y, t, FS, cls="legende-t"))
    cadres = [c for o in m["items"].values() for c in o.get("cadres", [])]
    if cadres and not apercu:
        for connu, t in ((True, "membre d'une Internationale (cadre et onglet du sigle)"),
                         (False, "cadre en tirets, sigle suivi de « ? » : dates d'adhésion à confirmer")):
            if any(c["connu"] == connu for c in cadres):
                x0 = place(46 + larg(t, FS))
                el.append(f'<rect x="{x0}" y="{y - 12}" width="36" height="16" rx="4" fill="none" '
                          f'stroke="{"#2F5D9E" if connu else melange("#2F5D9E", "#FFFFFF", 0.35)}" '
                          f'stroke-width="{FRAME_W}"' + ("" if connu else ' stroke-dasharray="5 3"') + "/>"
                          + texte(x0 + 46, y, t, FS, cls="legende-t"))
    el.append("</g>")
    return "".join(el)


def cle_internationales(m, y0, W):
    el = [f'<g class="cle-internationales" transform="translate(0,{y0:.0f})">',
          texte(16, 30, "Clé des Internationales", 16, True, "#111111", cls="cle-t"),
          texte(16, 48, "Les Internationales ne sont pas des organisations de la généalogie : elles apparaissent "
                        "comme cadres et onglets autour des organisations membres.", FS, False, "#333333", cls="cle-t")]
    col_w = (W - 32) / 2
    ys = [68, 68]
    for c in m["cle"]:
        col = 0 if ys[0] <= ys[1] else 1
        x, y = 16 + col * col_w, ys[col]
        el.append(f'<g class="entree-cle" data-intl="{esc(c["id"])}">'
                  f'<rect x="{x:.0f}" y="{y:.0f}" width="26" height="13" rx="3" fill="{c["couleur"]}"/>')
        el.append(texte(x + 34, y + 11, c["sigle"], FS, True, "#111111", cls="cle-t"))
        el.append(texte(x + 40 + larg(c["sigle"], FS, True), y + 11,
                        f"{c['nom']} ({c['dates']}) · {len(c['membres'])} membre{'s' if len(c['membres']) > 1 else ''}",
                        FS, False, "#1A1A1A", cls="cle-t"))
        y += 18
        if c["succession"]:
            for morceau in couper("Succession : " + c["succession"], col_w - 50, FS, max_lignes=6):
                el.append(texte(x + 34, y + 11, morceau, FS, False, "#333333", cls="cle-t"))
                y += 16
        el.append("</g>")
        ys[col] = y + 6
    el.append("</g>")
    return "".join(el), max(ys) + 20


# ======================================================================
# Vue par Internationale
# ======================================================================

def vue_internationales(m):
    """Une bande par Internationale (dans l'ordre de leurs successions), avec les barres de ses
    membres pendant leur adhésion. Cliquer une barre mène à l'organisation dans la généalogie."""
    items, ech, inter = m["items"], m["ech"], m["inter"]
    X = ech.X
    presentes = {c["id"] for c in m["cle"]}
    ordre, vus = [], set()
    for c in m["cle"]:
        racine = c["id"]
        while inter[racine]["pred"] and inter[racine]["pred"][0] in inter and inter[racine]["pred"][0] not in vus:
            racine = inter[racine]["pred"][0]
        pile = [racine]
        while pile:
            i = pile.pop(0)
            if i in vus:
                continue
            vus.add(i)
            if i in presentes:
                ordre.append(i)
            pile += [s for s, d in inter.items() if i in d["pred"]]
    cles = {c["id"]: c for c in m["cle"]}
    y, corps, W = 110, [], m["largeur"]
    for k, i in enumerate(ordre):
        c = cles[i]
        membres = [(items[q], cd) for q in c["membres"] for cd in items[q]["cadres"] if cd["intl"] == i]
        rangees = []
        for o, cd in sorted(membres, key=lambda x: x[1]["ta"]):
            xa, xb = X(cd["ta"]), max(X(cd["tb"]), X(cd["ta"]) + MIN_W)
            etiq = o["sigle"] or o["nom_court"]
            w_e = larg(etiq, FS, True) + 10
            R = xb + (0 if xb - xa >= w_e else w_e)
            r = next((r for r, occ in enumerate(rangees) if all(R + GAP <= a or b + GAP <= xa for a, b in occ)),
                     len(rangees))
            if r == len(rangees):
                rangees.append([])
            rangees[r].append((xa, R))
            cd["vue"] = (r, xa, xb, w_e, etiq)
        h = 46 + max(1, len(rangees)) * 26 + 10
        corps.append(f'<g class="bande-inter" data-intl="{esc(i)}"><rect x="0" y="{y}" width="{W:.0f}" height="{h}" '
                     f'fill="{melange(c["couleur"], "#FFFFFF", 0.88 if k % 2 else 0.93)}"/>'
                     f'<rect x="0" y="{y}" width="8" height="{h}" fill="{c["couleur"]}"/>'
                     + texte(16, y + 18, f"{c['sigle']} – {c['nom']} ({c['dates']})", 13, True, "#111111", cls="voie-t")
                     + (texte(16, y + 34, "Succession : " + c["succession"], FS, False, "#333333", cls="voie-t")
                        if c["succession"] else ""))
        for o, cd in membres:
            r, xa, xb, w_e, etiq = cd["vue"]
            yy = y + 46 + r * 26
            fill = o["couleur"]
            corps.append(f'<a href="arbre.html#{esc(o["id"])}"><g class="membre" data-id="{esc(o["id"])}">'
                         f'<title>{esc(o["label"])} : membre{" (dates à confirmer)" if not cd["connu"] else ""}</title>'
                         f'<rect x="{xa:.2f}" y="{yy:.2f}" width="{xb - xa:.2f}" height="20" rx="3" fill="{fill}"'
                         + ("" if cd["connu"] else ' stroke="#555555" stroke-dasharray="4 2"') + "/>"
                         + (texte(xa + 5, yy + 14, etiq, FS, True, texte_sur(fill), cls="tag-t")
                            if xb - xa >= w_e else
                            f'<rect x="{xb:.2f}" y="{yy:.2f}" width="{w_e:.2f}" height="20" rx="3" fill="{fill}"/>'
                            + texte(xb + 5, yy + 14, etiq, FS, True, texte_sur(fill), cls="tag-t"))
                         + "</g></a>")
        corps.append("</g>")
        y += h
    axe = [f'<line x1="{X(ech.T0):.1f}" x2="{X(ech.T1):.1f}" y1="{y + 8}" y2="{y + 8}" stroke="#555555"/>',
           f'<line x1="{X(ech.T0):.1f}" x2="{X(ech.T1):.1f}" y1="88" y2="88" stroke="#555555"/>']
    for a in ech.graduations():
        axe.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="{y + 3}" y2="{y + 13}" stroke="#555555"/>'
                   + texte(X(a), y + 28, str(a), 12, True, "#333333", "middle", cls="axe-t"))
        axe.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="83" y2="93" stroke="#555555"/>'
                   + texte(X(a), 77, str(a), 12, True, "#333333", "middle", cls="axe-t"))
    H = y + 50
    return (f'<svg xmlns="http://www.w3.org/2000/svg" id="vue-inter" width="{W:.0f}" height="{H:.0f}" '
            f'viewBox="0 0 {W:.0f} {H:.0f}" font-family="{POLICE}"><title>Vue par Internationale</title>'
            f'<rect width="{W:.0f}" height="{H:.0f}" fill="#FFFFFF"/>'
            + texte(16, 32, "Vue par Internationale", 22, True, "#111111", cls="legende-t")
            + texte(16, 52, "Une bande par Internationale, dans l'ordre de leurs successions ; chaque barre est une "
                            "organisation membre pendant son adhésion (tirets : dates à confirmer). Cliquer : "
                            "voir l'organisation dans la généalogie.", FS, False, "#333333", cls="legende-t")
            + "".join(axe) + "".join(corps) + "</svg>")


# ======================================================================
# HTML
# ======================================================================

def page_html(m, svg):
    voies = [dict(i=g["i"], cle=g["cle"], titre=TITRES[g["cle"]], h=g["h"]) for g in m["voies"]]
    liens = [dict(a=t["a"], b=t["b"]) for t in m["traces"]] + [dict(a=r["a"], b=r["b"]) for r in m["renvois"]] \
        + [dict(a=a, b=b) for a, b in m["continuations"]]
    cle = [dict(id=c["id"], sigle=c["sigle"], nom=c["nom"], dates=c["dates"], couleur=c["couleur"],
                succession=c["succession"], membres=c["membres"]) for c in m["cle"]]
    donnees = json.dumps(dict(voies=voies, liens=liens, cle=cle), ensure_ascii=False)
    return HTML.replace("__SVG__", svg).replace("__DONNEES__", donnees.replace("</", "<\\/"))


HTML = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Généalogie de la gauche française</title>
<style>
  :root { --fond:#ffffff; --texte:#1a1a1a; --doux:#4a4a4a; --bord:#d0d0d0; --panneau:#f6f7f8; --accent:#1f5fa8; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
    --fond:#16181b; --texte:#ececec; --doux:#b8b8b8; --bord:#3a3d42; --panneau:#202328; --accent:#7fb2f0; } }
  :root[data-theme="dark"] { --fond:#16181b; --texte:#ececec; --doux:#b8b8b8; --bord:#3a3d42; --panneau:#202328; --accent:#7fb2f0; }
  * { box-sizing:border-box; }
  html, body { margin:0; height:100%; background:var(--fond); color:var(--texte); font-family:Arial, Helvetica, sans-serif; font-size:14px; }
  body { display:flex; flex-direction:column; }
  header { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; padding:8px 16px; border-bottom:1px solid var(--bord); background:var(--panneau); }
  header h1 { font-size:16px; margin:0 8px 0 0; }
  input[type=search] { padding:5px 8px; border:1px solid var(--bord); border-radius:4px; width:220px; background:var(--fond); color:var(--texte); font-size:14px; }
  button { padding:4px 10px; border:1px solid var(--bord); border-radius:4px; background:var(--fond); color:var(--texte); cursor:pointer; font-size:13px; }
  button[aria-pressed="true"] { background:var(--accent); color:#fff; border-color:var(--accent); }
  label { font-size:13px; display:inline-flex; gap:4px; align-items:center; }
  a { color:var(--accent); }
  #resultat { color:var(--doux); font-size:13px; min-width:90px; }
  main { flex:1; display:flex; min-height:0; }
  #vue { flex:1; overflow:hidden; position:relative; cursor:grab; background:#fff; }
  #vue.saisie { cursor:grabbing; }
  #vue svg { width:100%; height:100%; display:block; }
  aside { width:340px; max-width:40vw; overflow:auto; border-left:1px solid var(--bord); background:var(--panneau); padding:8px 12px; }
  aside summary { font-weight:bold; cursor:pointer; padding:4px 0; font-size:15px; }
  .familles { display:flex; flex-wrap:wrap; gap:4px; }
  .entree { padding:6px 4px; border-bottom:1px solid var(--bord); cursor:pointer; border-radius:4px; }
  .entree:hover, .entree.choisie { background:color-mix(in srgb, var(--accent) 14%, transparent); }
  .entree.flash { outline:2px solid var(--accent); }
  .entree .puce { display:inline-block; width:14px; height:10px; margin-right:6px; vertical-align:middle; border-radius:2px; }
  .entree .succ { color:var(--doux); font-size:12px; margin-top:2px; }
  #arbre .org, #arbre .lien { transition:opacity .15s; }
  #arbre.focus .org, #arbre.focus .lien, #arbre.focus .continuation, #arbre.focus .marque-fusion { opacity:.15; }
  #arbre.focus .org.sel, #arbre.focus .lien.sel, #arbre.focus .continuation.sel { opacity:1; }
  #arbre .org.trouve .barre, #arbre .org.trouve .tag { stroke:#000; stroke-width:3; }
  #arbre .renvoi { cursor:pointer; }
  #arbre .renvoi.sel { fill:#c0392b; font-weight:bold; }
  #arbre .onglet { cursor:pointer; }
  #arbre.sans-cadres .cadre, #arbre.sans-cadres .onglet { display:none; }
  .replie { opacity:.55; }
</style>
</head>
<body>
<header>
  <h1>Généalogie de la gauche française</h1>
  <input type="search" id="recherche" placeholder="Rechercher (sigle, nom)…" aria-label="Rechercher une organisation">
  <span id="resultat"></span>
  <button id="ajuster">Ajuster</button><button id="plus" aria-label="Zoom avant">+</button><button id="moins" aria-label="Zoom arrière">−</button>
  <label><input type="checkbox" id="cadres" checked> cadres des Internationales</label>
  <a href="vue_internationales.html">Vue par Internationale</a>
  <span class="familles" id="familles" aria-label="Replier une famille"></span>
</header>
<main>
  <div id="vue">__SVG__</div>
  <aside>
    <details open id="cle"><summary>Clé des Internationales</summary>
      <p style="font-size:12px;color:var(--doux);margin:4px 0 8px">Survol ou clic : met en évidence les organisations membres. Les Internationales ne sont pas des organisations de la généalogie.</p>
      <div id="entrees"></div>
    </details>
  </aside>
</main>
<script>
const D = __DONNEES__;
const svg = document.getElementById('arbre'), vue = document.getElementById('vue');
const W0 = svg.viewBox.baseVal.width, H0 = svg.viewBox.baseVal.height;
let vb = {x:0, y:0, w:W0, h:H0};
svg.removeAttribute('width'); svg.removeAttribute('height'); svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
function appliquer(){ svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); }
function ajuster(){ const r = vue.getBoundingClientRect(); vb = {x:0, y:0, w:W0, h:W0 * r.height / Math.max(1, r.width)}; appliquer(); }
function zoom(f, cx, cy){ const r = svg.getBoundingClientRect(); const s = Math.max(vb.w / r.width, vb.h / r.height);
  const px = vb.x + (cx - r.left) * s, py = vb.y + (cy - r.top) * s;
  vb.w *= f; vb.h *= f; vb.x = px - (px - vb.x) * f; vb.y = py - (py - vb.y) * f; appliquer(); }
vue.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1/1.15, e.clientX, e.clientY); }, {passive:false});
let glisse = null;
vue.addEventListener('pointerdown', e => { if (e.target.closest('.onglet,.renvoi')) return; glisse = {x:e.clientX, y:e.clientY, vx:vb.x, vy:vb.y}; vue.classList.add('saisie'); });
window.addEventListener('pointermove', e => { if (!glisse) return; const r = svg.getBoundingClientRect(); const s = Math.max(vb.w / r.width, vb.h / r.height);
  vb.x = glisse.vx - (e.clientX - glisse.x) * s; vb.y = glisse.vy - (e.clientY - glisse.y) * s; appliquer(); });
window.addEventListener('pointerup', () => { glisse = null; vue.classList.remove('saisie'); });
document.getElementById('ajuster').onclick = ajuster;
document.getElementById('plus').onclick = () => { const r = vue.getBoundingClientRect(); zoom(1/1.4, r.left + r.width/2, r.top + r.height/2); };
document.getElementById('moins').onclick = () => { const r = vue.getBoundingClientRect(); zoom(1.4, r.left + r.width/2, r.top + r.height/2); };
function centrer(el){ const b = el.getBBox(); const w = Math.max(900, b.width * 3); const r = vue.getBoundingClientRect();
  const h = w * r.height / r.width; vb = {x:b.x + b.width/2 - w/2, y:b.y + b.height/2 - h/2, w, h}; appliquer(); }
const parents = {}, enfants = {};
for (const l of D.liens) { (parents[l.b] ||= []).push(l.a); (enfants[l.a] ||= []).push(l.b); }
function parcours(q, m, vus){ for (const x of (m[q] || [])) if (!vus.has(x)) { vus.add(x); parcours(x, m, vus); } return vus; }
let choisie = null;
function membres(id){ const c = D.cle.find(c => c.id === id); return new Set(c ? c.membres : []); }
function surligner(ids){
  if (!ids) { svg.classList.remove('focus'); svg.querySelectorAll('.sel').forEach(e => e.classList.remove('sel')); return; }
  svg.classList.add('focus');
  svg.querySelectorAll('.org').forEach(e => e.classList.toggle('sel', ids.has(e.dataset.id)));
  svg.querySelectorAll('.lien,.continuation').forEach(e => e.classList.toggle('sel', ids.has(e.dataset.a) && ids.has(e.dataset.b)));
}
svg.querySelectorAll('.org').forEach(g => {
  g.addEventListener('mouseenter', () => { const q = g.dataset.id; const s = parcours(q, parents, new Set([q])); parcours(q, enfants, s); surligner(s); });
  g.addEventListener('mouseleave', () => surligner(choisie ? membres(choisie) : null));
});
svg.querySelectorAll('.renvoi').forEach(t => {
  const paire = () => svg.querySelectorAll(`.renvoi[data-a="${CSS.escape(t.dataset.a)}"][data-b="${CSS.escape(t.dataset.b)}"]`);
  t.addEventListener('mouseenter', e => { e.stopPropagation(); paire().forEach(x => x.classList.add('sel')); surligner(new Set([t.dataset.a, t.dataset.b])); });
  t.addEventListener('mouseleave', () => paire().forEach(x => x.classList.remove('sel')));
  t.addEventListener('click', e => { e.stopPropagation(); const autre = t.dataset.org === t.dataset.a ? t.dataset.b : t.dataset.a;
    const cible = svg.querySelector(`.org-haut[data-id="${CSS.escape(autre)}"]`); if (cible) centrer(cible); });
});
const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
let trouves = [], rang = 0;
const champ = document.getElementById('recherche'), res = document.getElementById('resultat');
champ.addEventListener('input', () => { const q = norm(champ.value.trim());
  svg.querySelectorAll('.org.trouve').forEach(e => e.classList.remove('trouve'));
  trouves = q ? [...svg.querySelectorAll('.org-haut')].filter(g => g.dataset.recherche.includes(q)) : [];
  trouves.forEach(g => svg.querySelectorAll(`.org[data-id="${CSS.escape(g.dataset.id)}"]`).forEach(x => x.classList.add('trouve')));
  rang = 0; res.textContent = q ? `${trouves.length} résultat${trouves.length > 1 ? 's' : ''}` : ''; if (trouves.length) centrer(trouves[0]); });
champ.addEventListener('keydown', e => { if (e.key === 'Enter' && trouves.length) { rang = (rang + 1) % trouves.length; centrer(trouves[rang]); } });
document.getElementById('cadres').onchange = e => svg.classList.toggle('sans-cadres', !e.target.checked);
const replies = new Set(), RESTE = 44;
function decalages(){ const d = {}; let c = 0; for (const v of D.voies) { d[v.i] = c; if (replies.has(v.i)) c -= (v.h - RESTE); } return [d, c]; }
function relayout(){ const [d, total] = decalages();
  svg.querySelectorAll('.voie, .contenu-voie').forEach(g => { const i = +g.dataset.voie; g.setAttribute('transform', `translate(0,${d[i]})`);
    if (g.classList.contains('contenu-voie')) g.style.display = replies.has(i) ? 'none' : '';
    if (g.classList.contains('voie')) { const v = D.voies.find(v => v.i === i); g.classList.toggle('replie', replies.has(i));
      g.querySelectorAll('.fond-voie,.bord-voie').forEach(r => r.setAttribute('height', replies.has(i) ? RESTE : v.h)); } });
  const sd = D.voies.find(v => v.cle === 'sans date'); const dBas = sd ? d[sd.i] : total;
  svg.querySelector('.axe-bas').setAttribute('transform', `translate(0,${dBas})`);
  svg.querySelectorAll('.bande-decennie').forEach(r => { r.dataset.h ||= r.getAttribute('height'); r.setAttribute('height', +r.dataset.h + dBas); });
  svg.querySelectorAll('.lien, .marque-fusion').forEach(g => { const cache = g.dataset.va && (replies.has(+g.dataset.va) || replies.has(+g.dataset.vb));
    g.style.display = cache ? 'none' : '';
    g.querySelectorAll('.geo').forEach(el => { const pts = JSON.parse(el.dataset.geo).map(([x, y, v]) => [x, y + d[v]]);
      if (el.tagName === 'path') el.setAttribute('d', 'M' + pts.map(p => p.join(' ')).join(' L')); else el.setAttribute('points', pts.map(p => p.join(',')).join(' ')); }); });
}
const fam = document.getElementById('familles');
for (const v of D.voies) { const b = document.createElement('button'); b.textContent = v.titre.replace(' (hors échelle)', '');
  b.title = 'Replier / déplier cette famille'; b.setAttribute('aria-pressed', 'false');
  b.onclick = () => { replies.has(v.i) ? replies.delete(v.i) : replies.add(v.i); b.setAttribute('aria-pressed', replies.has(v.i)); relayout(); }; fam.appendChild(b); }
const entrees = document.getElementById('entrees');
for (const c of D.cle) { const div = document.createElement('div'); div.className = 'entree'; div.id = 'cle-' + c.id;
  div.innerHTML = '<span class="puce"></span><b></b> <span class="nom"></span> <span class="dates" style="color:var(--doux)"></span>' + (c.succession ? '<div class="succ"></div>' : '');
  div.querySelector('.puce').style.background = c.couleur; div.querySelector('b').textContent = c.sigle; div.querySelector('.nom').textContent = c.nom;
  div.querySelector('.dates').textContent = `(${c.dates}) · ${c.membres.length} membre${c.membres.length > 1 ? 's' : ''}`;
  if (c.succession) div.querySelector('.succ').textContent = 'Succession : ' + c.succession;
  div.addEventListener('mouseenter', () => surligner(membres(c.id)));
  div.addEventListener('mouseleave', () => surligner(choisie ? membres(choisie) : null));
  div.addEventListener('click', () => { document.querySelectorAll('.entree').forEach(e => e.classList.remove('choisie'));
    if (choisie === c.id) { choisie = null; surligner(null); } else { choisie = c.id; div.classList.add('choisie'); surligner(membres(c.id)); } });
  entrees.appendChild(div); }
svg.querySelectorAll('.onglet').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); document.getElementById('cle').open = true;
  const ent = document.getElementById('cle-' + b.dataset.intl); if (!ent) return;
  ent.scrollIntoView({block:'center', behavior:'smooth'}); ent.classList.add('flash'); setTimeout(() => ent.classList.remove('flash'), 1500);
  choisie = b.dataset.intl; document.querySelectorAll('.entree').forEach(x => x.classList.toggle('choisie', x === ent)); surligner(membres(choisie)); }));
ajuster();
if (location.hash) { const q = decodeURIComponent(location.hash.slice(1)); const g = svg.querySelector(`.org-haut[data-id="${CSS.escape(q)}"]`);
  if (g) { centrer(g); const s = parcours(q, parents, new Set([q])); parcours(q, enfants, s); surligner(s); } }
</script>
</body>
</html>
"""

HTML_VUE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vue par Internationale</title>
<style>
  :root { --fond:#ffffff; --texte:#1a1a1a; --bord:#d0d0d0; --accent:#1f5fa8; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --fond:#16181b; --texte:#ececec; --bord:#3a3d42; --accent:#7fb2f0; } }
  :root[data-theme="dark"] { --fond:#16181b; --texte:#ececec; --bord:#3a3d42; --accent:#7fb2f0; }
  body { margin:0; background:var(--fond); color:var(--texte); font-family:Arial, Helvetica, sans-serif; }
  header { padding:8px 16px; border-bottom:1px solid var(--bord); }
  a { color:var(--accent); }
  #vue { overflow:auto; background:#fff; }
  #vue .membre { cursor:pointer; }
  #vue .membre:hover rect { stroke:#000; stroke-width:2; }
</style></head>
<body><header><a href="arbre.html">← Retour à la généalogie</a></header><div id="vue">__SVG__</div></body></html>
"""


# ======================================================================

def main():
    orgs, liens, inter, T_AUJ = charger()
    m = mise_en_page(orgs, liens, inter, T_AUJ)
    with open(os.path.join(SORTIE, "arbre.svg"), "w", encoding="utf-8") as f:
        f.write(dessiner(m))
    shutil.copyfile(os.path.join(SORTIE, "arbre.svg"), "arbre.svg")
    with open(os.path.join(SORTIE, "arbre.html"), "w", encoding="utf-8") as f:
        f.write(page_html(m, dessiner(m, avec_cle=False)))
    grand = m["hauteur"] > 3000 or m["largeur"] > 4000
    chemin_ap = os.path.join(SORTIE, "arbre_apercu.svg")
    if grand:
        with open(chemin_ap, "w", encoding="utf-8") as f:
            f.write(dessiner(m, avec_cle=False, apercu=True))
    elif os.path.exists(chemin_ap):
        os.remove(chemin_ap)
    vue = vue_internationales(m)
    with open(os.path.join(SORTIE, "vue_internationales.svg"), "w", encoding="utf-8") as f:
        f.write(vue)
    with open(os.path.join(SORTIE, "vue_internationales.html"), "w", encoding="utf-8") as f:
        f.write(HTML_VUE.replace("__SVG__", vue))
    for ancien in os.listdir(SORTIE):     # versions par famille d'un passage précédent
        if ancien.startswith("arbre_") and ancien.endswith(".svg") and ancien != "arbre_apercu.svg":
            os.remove(os.path.join(SORTIE, ancien))
    for k, t, _ in VOIES:
        if any(o["voie"] == k for o in orgs.values()):
            mf = mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues={k},
                              titre=f"Généalogie de la gauche française : {t.lower()}")
            with open(os.path.join(SORTIE, f"arbre_{slug(k)}.svg"), "w", encoding="utf-8") as f:
                f.write(dessiner(mf))
    chemin_an = os.path.join(SORTIE, "anomalies_rendu.csv")
    if m["anomalies"]:
        with open(chemin_an, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["source", "target", "relation", "source_date", "target_date", "probable_cause"])
            w.writerows(m["anomalies"])
    elif os.path.exists(chemin_an):
        os.remove(chemin_an)
    print(f"{len(m['items'])} organisations, {len(m['traces'])} liens tracés, {len(m['renvois'])} renvois, "
          f"{len(m['continuations'])} continuations, {len(m['anomalies'])} liens non dessinables.")
    print(f"Taille : {m['largeur']:.0f} x {m['hauteur']:.0f} px (hors clé)"
          + (" ; aperçu : data/sortie/arbre_apercu.svg" if grand else ""))


if __name__ == "__main__":
    main()
