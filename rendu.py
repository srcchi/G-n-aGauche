"""
Phase 2 : mise en page et rendu de l'arbre, sans Graphviz.

La mise en page est calculée ici (échelle de temps linéaire, voies par famille, rangées) et le SVG
est écrit directement.

Entrées : data/sortie/organisations.csv, liens.csv, sans_date.csv, perimetre_exclu.csv,
          internationales.csv, affiliations.csv   (produits par nettoyage.py)
          data/manuel/sigles.csv                   (sigles saisis à la main)
Sorties : data/sortie/arbre.svg      (statique)
          arbre.svg                  (copie à la racine du dépôt, affichée sur GitHub)
          data/sortie/arbre.html     (interactif, autonome)
          data/sortie/arbre_<famille>.svg   (une par famille, pour l'impression)
          data/sortie/anomalies_rendu.csv   (liens impossibles à dessiner selon R1, s'il y en a)

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
from collections import defaultdict

SORTIE = os.path.join("data", "sortie")
MANUEL = os.path.join("data", "manuel")

# ---------- Géométrie (en px, unités SVG) ----------
PPA = 13.0              # pixels par année
COL_VOIES = 210         # colonne des titres de voies, à gauche
X0 = COL_VOIES + 30     # abscisse de l'année T0
BAR_H = 30              # hauteur d'une barre
ROW_TOP = 4             # marge au-dessus de la barre, dans la rangée
ROW_GAP = 8             # marge sous la barre et ses bandes d'affiliation
STRIP_H, STRIP_PAS = 5, 6
GAP = 12                # écart minimal entre deux éléments d'une même rangée
GOUTTIERE = 10          # un lien part de la source à x(t) - GOUTTIERE
FLECHE_L, FLECHE_DEMI = 9, 4.5
MIN_W = 6               # largeur minimale d'une barre (durée de moins de 6 px)
DEGRADE = 28            # fin ouverte des organisations encore actives
SEUIL_ANNEES, SEUIL_VOIES = 40, 2
VOIE_PAD = 6
FS_TITRE_VOIE, FS_SIGLE, FS = 13, 12, 11
POLICE = "Arial, Helvetica, sans-serif"

# ---------- Familles : une teinte par famille (Okabe-Ito et proches, sûre pour les daltoniens) ----------
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
EXTERNE = ("externe", "Organisations étrangères", "#A6A6A6")
SANS_DATE = ("sans date", "Dates inconnues (hors échelle)", "#A6A6A6")
TEINTE = {k: c for k, _, c in VOIES + [EXTERNE, SANS_DATE]}
# Sous-courants : même teinte, autre clarté (positif = plus clair, négatif = plus sombre)
NUANCES = {"communiste libertaire": 0.30, "anarcho-syndicaliste": 0.45,
           "luxemburgiste / conseilliste": 0.35, "écosocialiste": -0.35}

# ---------- Internationales : gris, bleus et sarcelles, avec motifs ----------
COULEURS_INTER = {
    "socialiste": "#2F5D9E", "communiste": "#16365C", "trotskyste": "#1F7A7A",
    "anarchiste": "#4A5560", "écologiste": "#4C9BC9", "régionaliste": "#7A8894",
    "gauche radicale": "#1593A8", "autre": "#8A9AA8",
}
MOTIFS = ["diag", "diag2", "points", "croise"]
MOTS_VIDES = {"de", "la", "le", "les", "des", "du", "pour", "l", "d", "et", "à", "en", "contre",
              "sur", "au", "aux"}


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
    """Date décimale exacte : l'année seule = 1er janvier ; avec le mois = 1er du mois."""
    return int(annee) + ((int(mois) - 1) / 12 if mois else 0)


def aujourdhui():
    d = datetime.date.today()
    return d.year + (d.month - 1) / 12 + (d.day - 1) / 365


def larg(s, fs, gras=False):
    """Largeur estimée d'un texte (Arial), un peu généreuse pour éviter les chevauchements."""
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
    a, b = hex_rgb(c), hex_rgb(cible)
    return rgb_hex(*(x + (y - x) * f for x, y in zip(a, b)))


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
    """Gris pour les dates, avec un contraste d'au moins 4,5:1 sur le fond."""
    fonce = texte_sur(fond) == "#000000"
    for g in (["#3A3A3A", "#2A2A2A"] if fonce else ["#E6E6E6", "#F2F2F2"]):
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
    parts = re.split(r"\s+[-–]\s+", base)
    res = "-".join("".join(w[0].upper() for w in re.findall(r"[^\W\d_]+", p)
                           if w.lower() not in MOTS_VIDES) for p in parts)
    m = re.search(r"\(([^)]*)\)", nom)
    if m:
        res += "-" + m.group(1)[:5].rstrip()
    return res


# ======================================================================
# Données
# ======================================================================

def charger():
    sigles = {r["id"]: r for r in lire("sigles.csv", MANUEL)}
    T_AUJ = aujourdhui()

    def libelles(q, label, nom_court):
        s = sigles.get(q, {})
        nom = (s.get("short_name") or nom_court or label).strip()
        sigle = (s.get("sigle") or "").strip()
        return (sigle or nom), (nom if sigle and sigle != nom else "")

    # Internationales
    inter = {}
    par_cle = defaultdict(int)
    for r in lire("internationales.csv"):
        cle = r["color_key"] or "autre"
        motif = MOTIFS[par_cle[cle] % len(MOTIFS)]
        par_cle[cle] += 1
        inter[r["id"]] = dict(id=r["id"], nom=r["name"], sigle=r["sigle"] or acronyme(r["name"]),
                              debut=r["start"], fin=r["end"], pred=[p for p in r["predecessor_id"].split(" | ") if p],
                              couleur=COULEURS_INTER.get(cle, COULEURS_INTER["autre"]), motif=motif,
                              cle=cle, membres=[])
    affil = defaultdict(list)
    for r in lire("affiliations.csv"):
        if r["international_id"] in inter:
            affil[r["party_id"]].append(r)
            inter[r["international_id"]]["membres"].append(r["party_id"])

    orgs = {}
    for r in lire("organisations.csv"):
        t0 = t_de(r["fondation"], r["fondation_mois"])
        if r["actif"]:
            t1, fin_txt, etat = None, "", "actif"
        elif r["dissolution"]:
            t1, fin_txt, etat = t_de(r["dissolution"], r["dissolution_mois"]), r["dissolution"], "fini"
        elif r["fin_deduite"]:
            t1, fin_txt, etat = t_de(r["fin_deduite"]), r["fin_deduite"], "fini"
        else:
            t1, fin_txt, etat = None, "?", "fin inconnue"
        principal, nom = libelles(r["id"], r["label"], r["nom_court"])
        fam_c = r["famille_courant"] or r["famille"]
        couleur = nuance(TEINTE.get(fam_c, TEINTE["à classer"]), NUANCES.get(r["courant_principal"], 0))
        mois = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.",
                "nov.", "déc."]
        def date_longue(a, m):
            return f"{mois[int(m) - 1]} {a}" if m else str(a)
        details = [r["label"],
                   f"Fondation : {date_longue(r['fondation'], r['fondation_mois'])} ({r['fondation_source']})",
                   "Toujours active" if etat == "actif" else
                   f"Fin : {date_longue(r['dissolution'], r['dissolution_mois'])} ({r['dissolution_source']})"
                   if r["dissolution"] else
                   f"Fin : {r['fin_deduite']} ({r['fin_deduite_source']})" if r["fin_deduite"] else
                   "Fin : inconnue",
                   f"Famille : {r['famille']}" + (f" (couleur : {fam_c})" if fam_c != r["famille"] else ""),
                   f"Courants : {r['courants_sources'] or 'aucun reconnu'}"]
        if r["journaux"]:
            details.append(f"Journaux : {r['journaux']}")
        if r["perimetre_douteux"]:
            details.append(f"Périmètre à vérifier : {r['perimetre_douteux']}")
        details.append(f"Sources : {r['sources']}")
        orgs[r["id"]] = dict(
            id=r["id"], label=r["label"], principal=principal, nom=nom, voie=r["famille"],
            couleur=couleur, t0=t0, t1=t1, etat=etat, an0=r["fondation"], an1=fin_txt,
            dates=f"{r['fondation']}–{fin_txt}", details=details,
            affil=[a for a in affil.get(r["id"], [])], externe=False, sans_date=False)

    for r in lire("perimetre_exclu.csv"):
        if r["voie_externe"] != "oui" or not r["fondation"]:
            continue
        t0 = t_de(r["fondation"], r["fondation_mois"])
        if r["actif"]:
            t1, fin_txt, etat = None, "", "actif"
        elif r["dissolution"] or r["fin_deduite"]:
            fin = r["dissolution"] or r["fin_deduite"]
            t1, fin_txt, etat = t_de(fin, r["dissolution_mois"] if r["dissolution"] else ""), fin, "fini"
        else:
            t1, fin_txt, etat = None, "?", "fin inconnue"
        orgs[r["id"]] = dict(id=r["id"], label=r["label"], principal=r["label"], nom="",
                             voie="externe", couleur="#D0D0D0", t0=t0, t1=t1, etat=etat,
                             an0=r["fondation"], an1=fin_txt, dates=f"{r['fondation']}–{fin_txt}",
                             details=[r["label"], f"Organisation étrangère ({r['raison']})",
                                      "Liée à une organisation française du graphe ; liens non dessinés."],
                             affil=[], externe=True, sans_date=False)

    for r in lire("sans_date.csv"):
        principal, nom = libelles(r["id"], r["label"], "")
        orgs[r["id"]] = dict(id=r["id"], label=r["label"], principal=principal, nom=nom,
                             voie="sans date", couleur=TEINTE.get(r["famille"], "#8C8C8C"),
                             t0=None, t1=None, etat="sans date", an0="?", an1="?", dates="date inconnue",
                             details=[r["label"], "Date de fondation inconnue : hors échelle, sans lien.",
                                      f"Famille : {r['famille']}", f"Sources : {r['sources']}"],
                             affil=[], externe=False, sans_date=True, famille_sd=r["famille"])

    liens = [dict(a=r["source"], b=r["cible"], rel=r["relation"],
                  t=t_de(r["date_evenement"], r["date_evenement_mois"]), sources=r["sources"])
             for r in lire("liens.csv") if r["source"] in orgs and r["cible"] in orgs]
    return orgs, liens, inter, T_AUJ


# ======================================================================
# Mise en page
# ======================================================================

def mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues=None, titre=""):
    """Calcule toutes les positions. voies_voulues : clés de voies à dessiner (None = toutes)."""
    voies_ordre = [v[0] for v in VOIES] + ["externe", "sans date"]
    if voies_voulues:
        voies_ordre = [v for v in voies_ordre if v in voies_voulues]
    items = {q: dict(o) for q, o in orgs.items() if o["voie"] in voies_ordre}
    datees = [o for o in items.values() if o["t0"] is not None]
    T0 = math.floor(min(o["t0"] for o in datees) / 10) * 10 if datees else 1900
    T1 = math.ceil(T_AUJ / 10) * 10

    def X(t):
        return X0 + (t - T0) * PPA

    rang_voie = {v: i for i, v in enumerate(voies_ordre)}
    anomalies_rendu = []

    # ---------- Classement des liens : tracé, renvoi textuel ----------
    poly, renvois = [], []
    for l in liens:
        a, b = items.get(l["a"]), items.get(l["b"])
        if a is None and b is None:
            continue
        if a is None or b is None:   # l'autre bout est dans une autre voie (impression par famille)
            renvois.append(dict(l, raison="hors dessin"))
            continue
        ecart_voies = abs(rang_voie[a["voie"]] - rang_voie[b["voie"]])
        # Point de départ sur l'axe : x(t) - gouttière, ou la fin de la source si elle a fini avant
        fin_a = a["t1"] if a["t1"] is not None else T_AUJ
        t_dep = min(l["t"] - GOUTTIERE / PPA, fin_a)
        if ecart_voies > SEUIL_VOIES or l["t"] - t_dep > SEUIL_ANNEES:
            renvois.append(dict(l, raison=f"{ecart_voies} voies" if ecart_voies > SEUIL_VOIES
                                else f"{l['t'] - t_dep:.0f} ans"))
        else:
            poly.append(dict(l))

    entrants_poly = defaultdict(list)
    for l in poly:
        entrants_poly[l["b"]].append(l)

    # ---------- Étiquettes et emprise horizontale de chaque élément ----------
    for o in items.values():
        o["badges"] = [(inter[a["international_id"]]["sigle"], a["international_id"])
                       for a in o["affil"]]
        o["renvois_sortants"] = []
        o["renvois_entrants"] = []
    for r in renvois:
        a, b = items.get(r["a"]), items.get(r["b"])
        if a is not None:
            cible = b or orgs[r["b"]]
            a["renvois_sortants"].append((f"→ {cible['principal']}", r["b"]))
        if b is not None:
            src = a or orgs[r["a"]]
            mot = {"scission": "scission de", "passage": "militants de"}.get(r["rel"], "issu de")
            b["renvois_entrants"].append((f"{mot} : {src['principal']}", r["a"]))

    def largeur_badges(o):
        return sum(larg(s, FS, True) + 8 + 4 for s, _ in o["badges"])

    for o in items.values():
        if o["sans_date"]:
            o["x0"], o["x1"] = 0, 0
            continue
        o["x0"] = X(o["t0"])
        o["x1_vrai"] = X(o["t1"]) if o["t1"] is not None else X(T_AUJ)
        o["x1"] = max(o["x1_vrai"], o["x0"] + MIN_W)
        w = o["x1"] - o["x0"]
        ligne1 = larg(o["principal"], FS_SIGLE, True) + 6 + larg(o["dates"], FS) + largeur_badges(o)
        o["dedans"] = ligne1 + 12 <= w
        o["ligne2"] = bool(o["dedans"] and o["nom"] and larg(o["nom"], FS) + 12 <= w)
        o["w_gauche"] = 0 if o["dedans"] else ligne1
        a_entrant = bool(entrants_poly.get(o["id"]))
        o["lgap"] = (GOUTTIERE + 8) if a_entrant else 5
        o["w_renv_g"] = sum(larg(t, FS) + 8 for t, _ in o["renvois_entrants"])
        o["w_renv_d"] = sum(larg(t, FS) + 8 for t, _ in o["renvois_sortants"])
        ouvert = o["etat"] in ("actif", "fin inconnue")
        L = o["x0"]
        if o["w_gauche"]:
            L -= o["lgap"] + o["w_gauche"]
        if o["w_renv_g"]:
            L -= (o["lgap"] if not o["w_gauche"] else 6) + o["w_renv_g"]
        R = o["x1"] + (DEGRADE if ouvert else 0)
        if o["w_renv_d"]:
            R += 6 + o["w_renv_d"]
        o["L"], o["R"] = L, R
        o["libre_gauche"] = not o["w_gauche"] and not o["w_renv_g"]
        o["libre_droite"] = not ouvert and not o["w_renv_d"]

    # ---------- Rangées : par voie, glouton, descendants près de leur ancêtre ----------
    parents_voie = defaultdict(list)
    for l in poly:
        parents_voie[l["b"]].append(l)
    continuations = set()
    rangees_par_voie = {}
    for v in voies_ordre:
        if v == "sans date":
            continue
        membres = sorted((o for o in items.values() if o["voie"] == v),
                         key=lambda o: (o["x0"], o["label"]))
        rangees = []

        def libre(r, L, R, sauf=None):
            for (l2, r2, q2) in rangees[r]:
                if q2 == sauf and L >= r2 - 0.01:
                    continue
                if not (R + GAP <= l2 or r2 + GAP <= L):
                    return False
            return True

        for o in membres:
            place = None
            # Renommage dans la même voie : continuation sur la même rangée
            for l in parents_voie[o["id"]]:
                p = items[l["a"]]
                if (l["rel"] == "renommage" and p["voie"] == v and "rang" in p and o["libre_gauche"]
                        and p["libre_droite"] and o["x0"] >= p["x1"] - 0.01
                        and libre(p["rang"], o["L"], o["R"], sauf=p["id"])):
                    place = p["rang"]
                    if o["x0"] - p["x1"] < GAP:
                        continuations.add((p["id"], o["id"]))
                    break
            if place is None:
                prefs = [items[l["a"]]["rang"] for l in parents_voie[o["id"]]
                         if items[l["a"]]["voie"] == v and "rang" in items[l["a"]]]
                pref = prefs[0] if prefs else 0
                ordre = sorted(range(len(rangees)), key=lambda r: (abs(r - pref), r < pref))
                place = next((r for r in ordre if libre(r, o["L"], o["R"])), len(rangees))
            if place == len(rangees):
                rangees.append([])
            rangees[place].append((o["L"], o["R"], o["id"]))
            o["rang"] = place
        rangees_par_voie[v] = rangees

    # ---------- Ordonnées ----------
    y = 0
    entete_h = 150
    axe_h = 30
    y = entete_h + axe_h
    voies_geo = []
    for v in voies_ordre:
        y_voie = y
        if v == "sans date":
            sd = [o for o in items.values() if o["voie"] == v]
            if not sd:
                continue
            y += axe_h + 10       # l'axe du bas se place avant cette voie
            y_voie = y
            # Hors échelle : cases à la largeur de leur texte, rangées les unes après les autres
            x_max, xc, ligne = X(T1), X0, 0
            for o in sorted(sd, key=lambda o: o["label"]):
                larg_case = max(larg(o["principal"], FS_SIGLE, True),
                                larg(o["nom"], FS) if o["nom"] else 0) + 14
                if xc + larg_case > x_max and xc > X0:
                    xc, ligne = X0, ligne + 1
                o["x0"], o["x1"] = xc, xc + larg_case
                o["x1_vrai"] = o["x1"]
                o["y"] = y_voie + VOIE_PAD + ligne * (BAR_H + ROW_TOP + ROW_GAP) + ROW_TOP
                o["dedans"] = True
                o["ligne2"] = bool(o["nom"])
                o["w_gauche"] = o["w_renv_g"] = o["w_renv_d"] = 0
                o["lgap"] = 5
                o["L"], o["R"] = o["x0"], o["x1"]
                xc += larg_case + GAP
            nl = ligne + 1
            h = 2 * VOIE_PAD + nl * (BAR_H + ROW_TOP + ROW_GAP)
            voies_geo.append(dict(cle=v, y=y_voie, h=h, n=len(sd), rangees=[]))
            y += h
            continue
        rangees = rangees_par_voie.get(v, [])
        if not rangees:
            continue          # voie vide : repliée
        y += VOIE_PAD
        geo_rangees = []
        for r, contenu in enumerate(rangees):
            n_bandes = max((len(items[q]["affil"]) for _, _, q in contenu), default=0)
            h = ROW_TOP + BAR_H + n_bandes * STRIP_PAS + ROW_GAP
            geo_rangees.append(dict(y=y, h=h))
            for _, _, q in contenu:
                items[q]["y"] = y + ROW_TOP
                items[q]["rang_y"], items[q]["rang_h"] = y, h
            y += h
        y += VOIE_PAD
        voies_geo.append(dict(cle=v, y=y_voie, h=y - y_voie,
                              n=sum(len(c) for c in rangees), rangees=geo_rangees))
    if not any(g["cle"] == "sans date" for g in voies_geo):
        y += axe_h + 10
    y_axe_bas = next((g["y"] - axe_h - 10 for g in voies_geo if g["cle"] == "sans date"), y - axe_h - 10)
    hauteur_lanes = y
    for i, g in enumerate(voies_geo):
        g["i"] = i
    voie_index = {g["cle"]: g["i"] for g in voies_geo}

    # ---------- Géométrie des liens ----------
    traces = []
    entrants = defaultdict(list)
    for l in poly:
        if (l["a"], l["b"]) in continuations:
            continue
        entrants[l["b"]].append(l)
    for qb, ls in entrants.items():
        b = items[qb]
        ls.sort(key=lambda l: items[l["a"]]["y"])
        n = len(ls)
        for k, l in enumerate(ls):
            off = (k - (n - 1) / 2) * 6
            off = max(-(BAR_H / 2 - 4), min(BAR_H / 2 - 4, off))
            a = items[l["a"]]
            xt = b["x0"]
            yt = b["y"] + BAR_H / 2 + off
            ya_c = a["y"] + BAR_H / 2
            bas = yt > ya_c
            if a["x1_vrai"] < xt - GOUTTIERE:                 # la source a fini avant
                xs = a["x1_vrai"]
                xv = xt - GOUTTIERE
                if a["rang_y"] == b["rang_y"]:
                    pts = [(xs, yt), (xt, yt)]
                else:
                    canal = a["rang_y"] + a["rang_h"] - 3 if bas else a["rang_y"] + 1.5
                    pts = [(xs, ya_c), (xs, canal), (xv, canal), (xv, yt), (xt, yt)]
                    lanes = [a["voie"]] * 3 + [b["voie"]] * 2
                depart_bord = None
            else:
                xs = max(xt - GOUTTIERE, a["x0"] + min(2, (xt - a["x0"]) / 2))
                y_bord = a["y"] + BAR_H if bas else a["y"]
                pts = [(xs, y_bord), (xs, yt), (xt, yt)]
                depart_bord = (xs, y_bord, 1 if bas else -1)
            if len(pts) == 2:
                lanes = [a["voie"], b["voie"]]
            elif len(pts) == 3:
                lanes = [a["voie"], b["voie"], b["voie"]]
            if xt - pts[-2][0] < 3:
                anomalies_rendu.append([l["a"], l["b"], l["rel"], a["an0"], b["an0"],
                                        "dates trop proches : segment final de moins de 3 px"])
                continue
            principal = l["rel"] in ("renommage", "filiation") or (
                l["rel"] == "fusion" and a["voie"] == b["voie"])
            traces.append(dict(l, pts=pts, lanes=lanes, depart=depart_bord, principal=principal,
                               annees=(xt - pts[0][0]) / PPA,
                               voies=abs(rang_voie[a["voie"]] - rang_voie[b["voie"]])))

    # ---------- Clé des Internationales ----------
    inter_util = {i for o in items.values() for _, i in o["badges"]}
    succ = defaultdict(list)
    for i, d in inter.items():
        for p in d["pred"]:
            succ[p].append(i)

    def chaine(i):
        racine, vus = i, set()
        while inter[racine]["pred"] and racine not in vus:
            vus.add(racine)
            racine = inter[racine]["pred"][0]
        etapes, x, vus = [], racine, set()
        while x and x not in vus:
            vus.add(x)
            d = inter[x]
            etapes.append(f"{d['nom']} {d['debut'] or '?'}–{d['fin']}")
            x = succ[x][0] if succ[x] else None
        return ", puis ".join(etapes) if len(etapes) > 1 else ""

    cle = []
    for i in sorted(inter_util, key=lambda i: (inter[i]["debut"] or "9999", inter[i]["nom"])):
        d = inter[i]
        cle.append(dict(id=i, sigle=d["sigle"], nom=d["nom"], dates=f"{d['debut'] or '?'}–{d['fin']}",
                        couleur=d["couleur"], motif=d["motif"], succession=chaine(i),
                        membres=[q for q in d["membres"] if q in items]))

    largeur = max([o["R"] for o in items.values()] + [X(T1)]) + 40
    return dict(items=items, traces=traces, renvois=renvois, continuations=continuations,
                voies=voies_geo, voie_index=voie_index, T0=T0, T1=T1, X=X, T_AUJ=T_AUJ,
                largeur=largeur, hauteur_lanes=hauteur_lanes, y_axe_haut=entete_h,
                y_axe_bas=y_axe_bas, cle=cle, inter=inter, titre=titre,
                anomalies_rendu=anomalies_rendu, rels=sorted({t["rel"] for t in traces}))


# ======================================================================
# SVG
# ======================================================================

STYLE_LIEN = {
    "renommage": dict(couleur="#3D3D3D", dash="", w=(2.6, 1.5)),
    "filiation": dict(couleur="#3D3D3D", dash="", w=(2.6, 1.5)),
    "fusion": dict(couleur="#3D3D3D", dash="", w=(2.2, 1.5)),
    "scission": dict(couleur="#C0392B", dash="6 3", w=(1.6, 1.6)),
    "passage": dict(couleur="#2471A3", dash="1.5 3", w=(1.2, 1.2)),
}
NOMS_LIENS = {"renommage": "renommage", "filiation": "filiation", "fusion": "fusion",
              "scission": "scission", "passage": "passage de militants"}


HALO = ' stroke="#FFFFFF" stroke-width="3" stroke-linejoin="round" paint-order="stroke"'


def texte(x, y, s, fs=FS, gras=False, couleur="#1A1A1A", ancre="start", cls="", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" font-family="{POLICE}"'
            f'{" font-weight=\"bold\"" if gras else ""} fill="{couleur}" text-anchor="{ancre}"'
            f'{f" class=\"{cls}\"" if cls else ""}{extra}>{esc(s)}</text>')


def motif_def(i, couleur, motif):
    pid = f"m-{slug(i)}"
    if motif == "points":
        corps = (f'<rect width="6" height="6" fill="#FFFFFF"/>'
                 f'<circle cx="3" cy="3" r="1.6" fill="{couleur}"/>')
        tr = ""
    elif motif == "croise":
        corps = (f'<rect width="6" height="6" fill="#FFFFFF"/>'
                 f'<path d="M0 3H6M3 0V6" stroke="{couleur}" stroke-width="1.6"/>')
        tr = ' patternTransform="rotate(45)"'
    else:
        corps = f'<rect width="6" height="6" fill="#FFFFFF"/><rect width="3" height="6" fill="{couleur}"/>'
        tr = f' patternTransform="rotate({45 if motif == "diag" else -45})"'
    return (f'<pattern id="{pid}" width="6" height="6" patternUnits="userSpaceOnUse"{tr}>'
            f'{corps}</pattern>'), pid


def dessiner(m, avec_cle=True, interactif=False):
    items, X = m["items"], m["X"]
    inter = m["inter"]
    W = m["largeur"]
    out_defs, out_fond, out_voies, out_liens, out_haut = [], [], [], [], []

    # Motifs des Internationales, hachures des dates inconnues, dégradés de fin ouverte
    motif_id = {}
    for i, d in inter.items():
        s, pid = motif_def(i, d["couleur"], d["motif"])
        out_defs.append(s)
        motif_id[i] = pid
    for v, _, c in VOIES + [EXTERNE]:
        out_defs.append(f'<pattern id="h-{slug(v)}" width="7" height="7" patternUnits="userSpaceOnUse" '
                        f'patternTransform="rotate(45)"><rect width="7" height="7" fill="#FFFFFF"/>'
                        f'<rect width="3" height="7" fill="{melange(c, "#FFFFFF", 0.45)}"/></pattern>')
    couleurs_deg = {o["couleur"] for o in items.values()}
    for c in couleurs_deg:
        out_defs.append(f'<linearGradient id="g-{c[1:]}"><stop offset="0" stop-color="{c}"/>'
                        f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>')

    # ---------- Fond : voies, bandes de décennies, axes ----------
    y_haut = m["y_axe_haut"]
    voies_scale = [g for g in m["voies"] if g["cle"] != "sans date"]
    y_bas_bandes = m["y_axe_bas"]
    for g in m["voies"]:
        cle = g["cle"]
        titre = dict((k, t) for k, t, _ in VOIES + [EXTERNE, SANS_DATE])[cle]
        c = TEINTE[cle]
        fond = melange(c, "#FFFFFF", 0.90 if g["i"] % 2 == 0 else 0.94)
        out_voies.append(f'<g class="voie" data-voie="{g["i"]}" data-cle="{esc(cle)}">')
        out_voies.append(f'<rect class="fond-voie" x="0" y="{g["y"]:.1f}" width="{W:.1f}" '
                         f'height="{g["h"]:.1f}" fill="{fond}"/>')
        out_voies.append(f'<rect x="0" y="{g["y"]:.1f}" width="8" height="{g["h"]:.1f}" fill="{c}"/>')
        out_voies.append(texte(16, g["y"] + 20, titre, FS_TITRE_VOIE, True, "#1A1A1A", cls="titre-voie"))
        out_voies.append(texte(16, g["y"] + 36, f"{g['n']} organisation{'s' if g['n'] > 1 else ''}",
                               FS, False, "#3A3A3A"))
        out_voies.append("</g>")
    for dec in range(m["T0"], m["T1"], 10):
        if (dec // 10) % 2 == 0:
            out_fond.append(f'<rect x="{X(dec):.1f}" y="{y_haut:.1f}" width="{10 * PPA:.1f}" '
                            f'height="{y_bas_bandes - y_haut + 30:.1f}" fill="#000000" '
                            f'fill-opacity="0.035" class="bande-decennie"/>')

    def axe(y, en_haut, cls):
        parts = [f'<g class="{cls}">',
                 f'<line x1="{X(m["T0"]):.1f}" x2="{X(m["T1"]):.1f}" y1="{y:.1f}" y2="{y:.1f}" '
                 f'stroke="#555555" stroke-width="1"/>']
        for a in range(m["T0"], m["T1"] + 1, 10):
            parts.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="{y - 5:.1f}" y2="{y + 5:.1f}" '
                         f'stroke="#555555"/>')
            parts.append(texte(X(a), y - 9 if en_haut else y + 20, str(a), 12, True, "#333333", "middle"))
        parts.append("</g>")
        return "".join(parts)
    out_fond.append(axe(y_haut + 26, True, "axe-haut"))
    out_fond.append(axe(y_bas_bandes + 4, False, "axe-bas"))
    # Aujourd'hui
    xa = X(m["T_AUJ"])
    out_fond.append(f'<line x1="{xa:.1f}" x2="{xa:.1f}" y1="{y_haut + 26:.1f}" y2="{y_bas_bandes + 4:.1f}" '
                    f'stroke="#777777" stroke-dasharray="2 4" stroke-width="1"/>')

    # ---------- Barres, étiquettes, bandes d'affiliation, renvois ----------
    groupes_voie = defaultdict(list)       # calque des barres et bandes d'affiliation
    etiquettes_voie = defaultdict(list)    # calque des étiquettes, au-dessus des liens
    for o in sorted(items.values(), key=lambda o: (o.get("y", 0), o["x0"])):
        if "y" not in o:
            continue
        vi = m["voie_index"][o["voie"]]
        el = []
        x0, x1, yb = o["x0"], o["x1"], o["y"]
        w = x1 - x0
        intl = " ".join(i for _, i in o["badges"])
        recherche = sans_accents(f"{o['principal']} {o['nom']} {o['label']}")
        el.append(f'<g class="org" data-id="{esc(o["id"])}" data-intl="{esc(intl)}" '
                  f'data-recherche="{esc(recherche)}">')
        el.append(f'<title>{esc(chr(10).join(o["details"]))}</title>')
        if o["sans_date"]:
            fill = f'url(#h-{slug(o.get("famille_sd", "à classer"))})' \
                if o.get("famille_sd") in TEINTE else "url(#h-a-classer)"
            el.append(f'<rect class="barre sans-date" data-id="{esc(o["id"])}" x="{x0:.2f}" y="{yb:.2f}" '
                      f'width="{w:.2f}" height="{BAR_H}" rx="3" fill="{fill}" '
                      f'stroke="{o["couleur"]}" stroke-width="1.5"/>')
            fond_txt = "#FFFFFF"
        else:
            ouvert = o["etat"] in ("actif", "fin inconnue")
            fin_attr = {"actif": "actif", "fin inconnue": "inconnue"}.get(o["etat"])
            if fin_attr is None:
                fin_attr = f"{o['t1']:.4f}"
            attrs = f'data-id="{esc(o["id"])}" data-debut="{o["t0"]:.4f}" data-fin="{fin_attr}"'
            style = ' stroke="#555555" stroke-dasharray="4 2" stroke-width="1.2"' if o["externe"] else ""
            el.append(f'<rect class="barre" {attrs} x="{x0:.2f}" y="{yb:.2f}" width="{w:.2f}" '
                      f'height="{BAR_H}" rx="{0 if ouvert else 3}" fill="{o["couleur"]}"{style}/>')
            if ouvert:
                el.append(f'<rect class="fin-ouverte" x="{x1:.2f}" y="{yb:.2f}" width="{DEGRADE}" '
                          f'height="{BAR_H}" fill="url(#g-{o["couleur"][1:]})"/>')
                if o["etat"] == "fin inconnue":
                    el.append(texte(x1 + 4, yb + BAR_H / 2 + 4, "?", FS, True, texte_sur(o["couleur"])))
            fond_txt = o["couleur"]
        # Les étiquettes vont dans un calque au-dessus des liens : les traits passent dessous
        barre_part = el
        el = [barre_part[0].replace('class="org"', 'class="org org-etiquettes"')]
        # Étiquette
        if o.get("dedans"):
            c_txt = texte_sur(fond_txt) if not o["sans_date"] else "#1A1A1A"
            c_date = gris_sur(fond_txt) if not o["sans_date"] else "#3A3A3A"
            y1 = yb + (13 if o["ligne2"] else BAR_H / 2 + 4.5)
            xx = x0 + 6
            wl = larg(o["principal"], FS_SIGLE, True)
            el.append(texte(xx, y1, o["principal"], FS_SIGLE, True, c_txt, cls="etiquette",
                            extra=f' data-bbox="{xx:.1f},{y1 - 11:.1f},{wl:.1f},14" data-dans="{esc(o["id"])}"'))
            xx += wl + 6
            if not o["sans_date"]:
                wd = larg(o["dates"], FS)
                el.append(texte(xx, y1, o["dates"], FS, False, c_date, cls="etiquette",
                                extra=f' data-bbox="{xx:.1f},{y1 - 10:.1f},{wd:.1f},13" data-dans="{esc(o["id"])}"'))
                xx += wd + 6
            for s, i in o["badges"]:
                el.append(badge(xx, y1, s, i, inter, o["id"], dedans=True))
                xx += larg(s, FS, True) + 8 + 4
            if o["ligne2"]:
                wn = larg(o["nom"], FS)
                el.append(texte(x0 + 6, yb + 26, o["nom"], FS, False, c_txt, cls="etiquette",
                                extra=f' data-bbox="{x0 + 6:.1f},{yb + 16:.1f},{wn:.1f},13" data-dans="{esc(o["id"])}"'))
        else:
            xx = x0 - o["lgap"] - o["w_gauche"]
            y1 = yb + BAR_H / 2 + 4.5
            wl = larg(o["principal"], FS_SIGLE, True)
            el.append(texte(xx, y1, o["principal"], FS_SIGLE, True, "#1A1A1A", cls="etiquette",
                            extra=f' data-bbox="{xx:.1f},{y1 - 11:.1f},{wl:.1f},14"' + HALO))
            xx += wl + 6
            wd = larg(o["dates"], FS)
            el.append(texte(xx, y1, o["dates"], FS, False, "#3A3A3A", cls="etiquette",
                            extra=f' data-bbox="{xx:.1f},{y1 - 10:.1f},{wd:.1f},13"' + HALO))
            xx += wd + 6
            for s, i in o["badges"]:
                el.append(badge(xx, y1, s, i, inter, o["id"], dedans=False))
                xx += larg(s, FS, True) + 8 + 4
        # Bandes d'affiliation, sous la barre
        for k, a in enumerate(o["affil"]):
            i = a["international_id"]
            d = inter[i]
            ta = max(o["t0"], t_de(a["start"])) if a["start"] else o["t0"]
            fin_parti = o["t1"] if o["t1"] is not None else m["T_AUJ"]
            tb = min(fin_parti, t_de(a["end"])) if a["end"] else fin_parti
            xa_, xb_ = max(x0, X(ta)), min(x1, X(tb))
            if xb_ <= xa_:
                xa_, xb_ = x0, x1
            inconnue = a["date_certainty"] != "known"
            fill = f"url(#{motif_id[i]})" if inconnue else d["couleur"]
            titre_b = f"{d['sigle']} – {d['nom']}" + (" (période inconnue)" if inconnue else "")
            barre_part.append(f'<rect class="bande-affil" data-parti="{esc(o["id"])}" data-intl="{esc(i)}" '
                      f'x="{xa_:.2f}" y="{yb + BAR_H + 1 + k * STRIP_PAS:.2f}" width="{xb_ - xa_:.2f}" '
                      f'height="{STRIP_H}" fill="{fill}" stroke="{d["couleur"]}" stroke-width="0.6">'
                      f'<title>{esc(titre_b)}</title></rect>')
        # Renvois textuels (liens trop longs)
        y1 = yb + BAR_H / 2 + 4.5
        xr = x0 - (o["lgap"] if not o["w_gauche"] else o["lgap"] + o["w_gauche"] + 6) - o["w_renv_g"]
        for t, autre in o["renvois_entrants"]:
            wt = larg(t, FS)
            el.append(texte(xr, y1, t, FS, False, "#1A1A1A", cls="renvoi",
                            extra=f' data-a="{esc(autre)}" data-b="{esc(o["id"])}" '
                                  f'data-bbox="{xr:.1f},{y1 - 10:.1f},{wt:.1f},13"' + HALO))
            xr += wt + 8
        xr = x1 + (DEGRADE if o["etat"] in ("actif", "fin inconnue") else 0) + 6
        for t, autre in o["renvois_sortants"]:
            wt = larg(t, FS)
            el.append(texte(xr, y1, t, FS, False, "#1A1A1A", cls="renvoi",
                            extra=f' data-a="{esc(o["id"])}" data-b="{esc(autre)}" '
                                  f'data-bbox="{xr:.1f},{y1 - 10:.1f},{wt:.1f},13"' + HALO))
            xr += wt + 8
        barre_part.append("</g>")
        el.append("</g>")
        groupes_voie[vi].append("".join(barre_part))
        etiquettes_voie[vi].append("".join(el))

    # Continuations (renommage sur la même rangée) : chevron à la jonction
    for a, b in m["continuations"]:
        o = items[b]
        xj, yj = o["x0"], o["y"] + BAR_H / 2
        vi = m["voie_index"][o["voie"]]
        etiquettes_voie[vi].append(
            f'<g class="continuation" data-a="{esc(a)}" data-b="{esc(b)}">'
            f'<title>Renommage : {esc(items[a]["label"])} devient {esc(o["label"])}</title>'
            f'<polyline points="{xj - 4:.1f},{yj - 7:.1f} {xj + 3:.1f},{yj:.1f} {xj - 4:.1f},{yj + 7:.1f}" '
            f'fill="none" stroke="#FFFFFF" stroke-width="4"/>'
            f'<polyline points="{xj - 4:.1f},{yj - 7:.1f} {xj + 3:.1f},{yj:.1f} {xj - 4:.1f},{yj + 7:.1f}" '
            f'fill="none" stroke="#1A1A1A" stroke-width="1.6"/></g>')

    # ---------- Liens ----------
    fusions = defaultdict(list)
    for t in m["traces"]:
        st = STYLE_LIEN[t["rel"]]
        w = st["w"][0] if t["principal"] else st["w"][1]
        pts = t["pts"]
        d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts)
        geo = json.dumps([[round(x, 2), round(y, 2), m["voie_index"][v]] for (x, y), v in zip(pts, t["lanes"])])
        xt, yt = pts[-1]
        fl = [(xt, yt), (xt - FLECHE_L, yt - FLECHE_DEMI), (xt - FLECHE_L, yt + FLECHE_DEMI)]
        vb = m["voie_index"][items[t["b"]]["voie"]]
        geo_f = json.dumps([[round(x, 2), round(y, 2), vb] for x, y in fl])
        a_nom, b_nom = items[t["a"]]["label"], items[t["b"]]["label"]
        g = [f'<g class="lien" data-a="{esc(t["a"])}" data-b="{esc(t["b"])}" data-rel="{t["rel"]}" '
             f'data-annees="{t["annees"]:.2f}" data-voies="{t["voies"]}" '
             f'data-va="{m["voie_index"][items[t["a"]]["voie"]]}" data-vb="{vb}">',
             f'<title>{esc(NOMS_LIENS[t["rel"]])} : {esc(a_nom)} → {esc(b_nom)} ({items[t["b"]]["an0"]})</title>',
             f'<path class="halo geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="#FFFFFF" '
             f'stroke-width="{w + 2.5:.1f}" stroke-opacity="0.85"/>',
             f'<path class="trait geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="{st["couleur"]}" '
             f'stroke-width="{w}"' + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + "/>",
             f'<polygon class="fleche geo" data-geo=\'{geo_f}\' points="'
             + " ".join(f"{x:.2f},{y:.2f}" for x, y in fl) + f'" fill="{st["couleur"]}"/>']
        if t["rel"] == "scission" and t["depart"]:
            xs, ys, dirn = t["depart"]
            fk = [(xs - 4, ys + dirn * 6), (xs, ys), (xs + 4, ys + dirn * 6)]
            va = m["voie_index"][items[t["a"]]["voie"]]
            g.append(f'<polyline class="fourche geo" data-geo=\'{json.dumps([[round(x, 2), round(y, 2), va] for x, y in fk])}\' '
                     f'points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in fk)}" fill="none" '
                     f'stroke="{st["couleur"]}" stroke-width="1.6"/>')
        if t["rel"] == "fusion":
            fusions[t["b"]].append(yt)
        g.append("</g>")
        out_liens.append("".join(g))
    # Marqueur de fusion : barre verticale qui réunit les arrivées
    for qb, ys in fusions.items():
        o = items[qb]
        xm = o["x0"] - FLECHE_L - 2
        y_a, y_b = min(ys) - 3, max(ys) + 3
        vb = m["voie_index"][o["voie"]]
        geo = json.dumps([[round(xm, 2), round(y_a, 2), vb], [round(xm, 2), round(y_b, 2), vb]])
        out_liens.append(f'<g class="marque-fusion" data-b="{esc(qb)}"><path class="geo" data-geo=\'{geo}\' '
                         f'd="M{xm:.2f} {y_a:.2f} L{xm:.2f} {y_b:.2f}" stroke="#3D3D3D" '
                         f'stroke-width="3"/></g>')

    # ---------- En-tête : titre et légende en bandeau ----------
    n_orgs = sum(1 for o in items.values() if not o["sans_date"] and not o["externe"])
    out_haut.append(texte(16, 32, m["titre"] or "Généalogie des organisations de gauche en France",
                          22, True, "#111111"))
    out_haut.append(texte(16, 52, f"{n_orgs} organisations datées · {len(m['traces'])} liens dessinés · "
                          f"{len(m['renvois'])} liens longs en renvoi textuel · échelle linéaire, "
                          f"{PPA:g} px par an · données Wikidata et Wikipédia, "
                          f"générées le {datetime.date.today().strftime('%d/%m/%Y')}",
                          FS, False, "#3A3A3A"))
    out_haut.append(legende(m, motif_id))

    H = (m["hauteur_lanes"] + 20)
    cle_svg, h_cle = ("", 0)
    if avec_cle and m["cle"]:
        cle_svg, h_cle = cle_internationales(m, motif_id, H, W)
    H += h_cle

    voies_svg, etiquettes_svg = [], []
    for g in m["voies"]:
        voies_svg.append(f'<g class="contenu-voie" data-voie="{g["i"]}">' + "".join(groupes_voie[g["i"]]) + "</g>")
        etiquettes_svg.append(f'<g class="contenu-voie" data-voie="{g["i"]}">'
                              + "".join(etiquettes_voie[g["i"]]) + "</g>")

    attrs = (f'data-x0="{X0}" data-t0="{m["T0"]}" data-ppa="{PPA}" data-aujourdhui="{m["T_AUJ"]:.4f}" '
             f'data-min-w="{MIN_W}" data-seuil-annees="{SEUIL_ANNEES}" data-seuil-voies="{SEUIL_VOIES}"')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" id="arbre" width="{W:.0f}" height="{H:.0f}" '
           f'viewBox="0 0 {W:.0f} {H:.0f}" {attrs} font-family="{POLICE}">'
           f'<title>Généalogie des organisations de gauche en France</title>'
           f'<defs>{"".join(out_defs)}</defs>'
           f'<rect width="{W:.0f}" height="{H:.0f}" fill="#FFFFFF"/>'
           + "".join(out_voies) + "".join(out_fond) + "".join(voies_svg)
           + f'<g class="liens">{"".join(out_liens)}</g>'
           + "".join(etiquettes_svg)
           + "".join(out_haut) + cle_svg + "</svg>")
    return svg


def badge(x, y_base, sigle, i, inter, parti, dedans):
    d = inter[i]
    w = larg(sigle, FS, True) + 8
    y = y_base - 11.5
    return (f'<g class="badge" data-intl="{esc(i)}" data-parti="{esc(parti)}">'
            f'<title>{esc(d["nom"])} ({d["debut"] or "?"}–{d["fin"]})</title>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="15" rx="7.5" fill="{d["couleur"]}" '
            f'stroke="#FFFFFF" stroke-width="1"/>'
            + texte(x + w / 2, y_base, sigle, FS, True, texte_sur(d["couleur"]), "middle",
                    cls="etiquette-badge",
                    extra=f' data-bbox="{x:.1f},{y:.1f},{w:.1f},15"' + (f' data-dans="{esc(parti)}"' if dedans else ""))
            + "</g>")


def legende(m, motif_id):
    """Bandeau horizontal : familles présentes, types de liens présents, conventions."""
    el = ['<g class="legende">']
    x, y = 16, 78
    xmax = m["largeur"] - 20

    def place(w):
        nonlocal x, y
        if x + w > xmax:
            x, y = 16, y + 24
        x0 = x
        x += w + 18
        return x0

    presentes = [g["cle"] for g in m["voies"]]
    for k, t, c in VOIES:
        if k not in presentes:
            continue
        w = 22 + larg(t, FS)
        x0 = place(w)
        el.append(f'<rect x="{x0}" y="{y - 10}" width="16" height="12" rx="2" fill="{c}"/>')
        el.append(texte(x0 + 22, y, t, FS, False, "#1A1A1A"))
    for rel in ["renommage", "filiation", "fusion", "scission", "passage"]:
        if rel not in m["rels"]:
            continue
        st = STYLE_LIEN[rel]
        nom = NOMS_LIENS[rel]
        w = 44 + larg(nom, FS)
        x0 = place(w)
        el.append(f'<path d="M{x0} {y - 4} H{x0 + 30}" stroke="{st["couleur"]}" stroke-width="{st["w"][0]}"'
                  + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + ' fill="none"/>')
        el.append(f'<polygon points="{x0 + 36},{y - 4} {x0 + 27},{y - 8.5} {x0 + 27},{y + 0.5}" '
                  f'fill="{st["couleur"]}"/>')
        el.append(texte(x0 + 42, y, nom, FS, False, "#1A1A1A"))
    if m["continuations"]:
        nom = "renommage sur la même rangée"
        x0 = place(24 + larg(nom, FS))
        el.append(f'<rect x="{x0}" y="{y - 11}" width="18" height="14" fill="#8C8C8C"/>'
                  f'<polyline points="{x0 + 6},{y - 10} {x0 + 12},{y - 4} {x0 + 6},{y + 2}" fill="none" '
                  f'stroke="#FFFFFF" stroke-width="1.6"/>')
        el.append(texte(x0 + 24, y, nom, FS, False, "#1A1A1A"))
    if m["renvois"]:
        nom = "→ X / issu de : X  lien trop long, en renvoi"
        x0 = place(larg(nom, FS))
        el.append(texte(x0, y, nom, FS, False, "#1A1A1A"))
    nom = "toujours active"
    x0 = place(40 + larg(nom, FS))
    el.append(f'<rect x="{x0}" y="{y - 11}" width="10" height="14" fill="#8C8C8C"/>'
              f'<rect x="{x0 + 10}" y="{y - 11}" width="24" height="14" fill="url(#g-8C8C8C)"/>')
    el.append(texte(x0 + 40, y, nom, FS, False, "#1A1A1A"))
    if m["cle"]:
        nom = "affiliation à une Internationale (hachures : période inconnue) + badge du sigle"
        x0 = place(40 + larg(nom, FS))
        i0 = m["cle"][0]["id"]
        el.append(f'<rect x="{x0}" y="{y - 7}" width="34" height="5" fill="url(#{motif_id[i0]})" '
                  f'stroke="{m["cle"][0]["couleur"]}" stroke-width="0.6"/>')
        el.append(texte(x0 + 40, y, nom, FS, False, "#1A1A1A"))
    el.append("</g>")
    return "".join(el)


def cle_internationales(m, motif_id, y0, W):
    """Panneau « Clé des Internationales », sous la frise, en deux colonnes."""
    el = [f'<g class="cle-internationales" transform="translate(0,{y0:.0f})">',
          f'<rect x="0" y="0" width="{W:.0f}" height="10" fill="#FFFFFF"/>',
          texte(16, 30, "Clé des Internationales", 16, True, "#111111"),
          texte(16, 48, "Les Internationales ne sont pas des organisations de la généalogie : elles "
                "apparaissent comme bandes et badges sur les partis membres.", FS, False, "#3A3A3A")]
    col_w = (W - 32) / 2
    ys = [68, 68]
    for k, c in enumerate(m["cle"]):
        col = 0 if ys[0] <= ys[1] else 1
        x, y = 16 + col * col_w, ys[col]
        el.append(f'<g class="entree-cle" data-intl="{esc(c["id"])}">')
        el.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="26" height="12" fill="url(#{motif_id[c["id"]]})" '
                  f'stroke="{c["couleur"]}"/>')
        ligne = f"{c['nom']} ({c['dates']}) · {len(c['membres'])} membre{'s' if len(c['membres']) > 1 else ''}"
        el.append(texte(x + 34, y + 11, c["sigle"], FS, True, "#111111"))
        el.append(texte(x + 40 + larg(c["sigle"], FS, True), y + 11, ligne, FS, False, "#1A1A1A"))
        y += 18
        if c["succession"]:
            for morceau in couper("Succession : " + c["succession"], col_w - 50):
                el.append(texte(x + 34, y + 11, morceau, FS, False, "#3A3A3A"))
                y += 16
        el.append("</g>")
        ys[col] = y + 6
    el.append("</g>")
    return "".join(el), max(ys) + 20


def couper(s, w):
    lignes, cour = [], ""
    for mot in s.split(" "):
        essai = (cour + " " + mot).strip()
        if larg(essai, FS) > w and cour:
            lignes.append(cour)
            cour = mot
        else:
            cour = essai
    return lignes + [cour] if cour else lignes


# ======================================================================
# HTML interactif
# ======================================================================

def page_html(m, svg):
    voies = [dict(i=g["i"], cle=g["cle"], titre=dict((k, t) for k, t, _ in VOIES + [EXTERNE, SANS_DATE])[g["cle"]],
                  h=g["h"], y=g["y"]) for g in m["voies"]]
    liens = [dict(a=t["a"], b=t["b"]) for t in m["traces"]] \
        + [dict(a=r["a"], b=r["b"]) for r in m["renvois"]] \
        + [dict(a=a, b=b) for a, b in m["continuations"]]
    cle = [dict(id=c["id"], sigle=c["sigle"], nom=c["nom"], dates=c["dates"], couleur=c["couleur"],
                succession=c["succession"], membres=c["membres"]) for c in m["cle"]]
    noms = {q: o["principal"] for q, o in m["items"].items()}
    donnees = json.dumps(dict(voies=voies, liens=liens, cle=cle, noms=noms,
                              axeBas=m["y_axe_bas"]), ensure_ascii=False)
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
  * { box-sizing: border-box; }
  html, body { margin:0; height:100%; background:var(--fond); color:var(--texte);
    font-family: Arial, Helvetica, sans-serif; font-size:14px; }
  body { display:flex; flex-direction:column; }
  header { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; padding:8px 16px;
    border-bottom:1px solid var(--bord); background:var(--panneau); }
  header h1 { font-size:16px; margin:0 8px 0 0; }
  input[type=search] { padding:5px 8px; border:1px solid var(--bord); border-radius:4px; width:220px;
    background:var(--fond); color:var(--texte); font-size:14px; }
  button { padding:4px 10px; border:1px solid var(--bord); border-radius:4px; background:var(--fond);
    color:var(--texte); cursor:pointer; font-size:13px; }
  button[aria-pressed="true"] { background:var(--accent); color:#fff; border-color:var(--accent); }
  label { font-size:13px; display:inline-flex; gap:4px; align-items:center; }
  #resultat { color:var(--doux); font-size:13px; min-width:90px; }
  main { flex:1; display:flex; min-height:0; }
  #vue { flex:1; overflow:hidden; position:relative; cursor:grab; background:#ffffff; }
  #vue.saisie { cursor:grabbing; }
  #vue svg { width:100%; height:100%; display:block; }
  aside { width:340px; max-width:40vw; overflow:auto; border-left:1px solid var(--bord);
    background:var(--panneau); padding:8px 12px; }
  aside summary { font-weight:bold; cursor:pointer; padding:4px 0; font-size:15px; }
  .familles { display:flex; flex-wrap:wrap; gap:4px; }
  .entree { padding:6px 4px; border-bottom:1px solid var(--bord); cursor:pointer; border-radius:4px; }
  .entree:hover, .entree.choisie { background:color-mix(in srgb, var(--accent) 14%, transparent); }
  .entree.flash { outline:2px solid var(--accent); }
  .entree .puce { display:inline-block; width:14px; height:10px; margin-right:6px; vertical-align:middle;
    border-radius:2px; }
  .entree .succ { color:var(--doux); font-size:12px; margin-top:2px; }
  #arbre .org, #arbre .lien, #arbre .renvoi, #arbre .badge { transition: opacity .15s; }
  #arbre.focus .org, #arbre.focus .lien, #arbre.focus .continuation, #arbre.focus .marque-fusion { opacity:.15; }
  #arbre.focus .org.sel, #arbre.focus .lien.sel, #arbre.focus .continuation.sel { opacity:1; }
  #arbre .org.trouve .barre { stroke:#000; stroke-width:3; }
  #arbre .renvoi { cursor:pointer; }
  #arbre .renvoi.sel { fill:#c0392b; font-weight:bold; }
  #arbre .badge { cursor:pointer; }
  #arbre.sans-bandes .bande-affil { display:none; }
  .replie { opacity:.55; }
</style>
</head>
<body>
<header>
  <h1>Généalogie de la gauche française</h1>
  <input type="search" id="recherche" placeholder="Rechercher (sigle, nom)…" aria-label="Rechercher une organisation">
  <span id="resultat"></span>
  <button id="ajuster">Ajuster</button><button id="plus" aria-label="Zoom avant">+</button><button id="moins" aria-label="Zoom arrière">−</button>
  <label><input type="checkbox" id="bandes" checked> bandes d'affiliation</label>
  <span class="familles" id="familles" aria-label="Replier une famille"></span>
</header>
<main>
  <div id="vue">__SVG__</div>
  <aside>
    <details open id="cle"><summary>Clé des Internationales</summary>
      <p style="font-size:12px;color:var(--doux);margin:4px 0 8px">Survol ou clic : met en évidence les partis membres. Les Internationales ne sont pas des organisations de la généalogie.</p>
      <div id="entrees"></div>
    </details>
  </aside>
</main>
<script>
const D = __DONNEES__;
const svg = document.getElementById('arbre');
const vue = document.getElementById('vue');
const W0 = svg.viewBox.baseVal.width, H0 = svg.viewBox.baseVal.height;
let vb = {x:0, y:0, w:W0, h:H0};
function appliquer(){ svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); }
function ajuster(){ const r = vue.getBoundingClientRect();
  vb = {x:0, y:0, w:W0, h:W0 * r.height / Math.max(1, r.width)}; appliquer(); }   // pleine largeur
svg.removeAttribute('width'); svg.removeAttribute('height');
svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
function zoom(f, cx, cy){
  const r = svg.getBoundingClientRect();
  const s = Math.max(vb.w / r.width, vb.h / r.height);
  const px = vb.x + (cx - r.left) * s, py = vb.y + (cy - r.top) * s;
  vb.w *= f; vb.h *= f; vb.x = px - (px - vb.x) * f; vb.y = py - (py - vb.y) * f; appliquer();
}
vue.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1/1.15, e.clientX, e.clientY); }, {passive:false});
let glisse = null;
vue.addEventListener('pointerdown', e => { if (e.target.closest('.badge,.renvoi')) return;
  glisse = {x:e.clientX, y:e.clientY, vx:vb.x, vy:vb.y}; vue.classList.add('saisie'); });
window.addEventListener('pointermove', e => { if (!glisse) return;
  const r = svg.getBoundingClientRect(); const s = Math.max(vb.w / r.width, vb.h / r.height);
  vb.x = glisse.vx - (e.clientX - glisse.x) * s; vb.y = glisse.vy - (e.clientY - glisse.y) * s; appliquer(); });
window.addEventListener('pointerup', () => { glisse = null; vue.classList.remove('saisie'); });
document.getElementById('ajuster').onclick = ajuster;
document.getElementById('plus').onclick = () => { const r = vue.getBoundingClientRect(); zoom(1/1.4, r.left + r.width/2, r.top + r.height/2); };
document.getElementById('moins').onclick = () => { const r = vue.getBoundingClientRect(); zoom(1.4, r.left + r.width/2, r.top + r.height/2); };
function centrer(el){
  const b = el.getBBox(); const w = Math.max(900, b.width * 3);
  const r = vue.getBoundingClientRect(); const h = w * r.height / r.width;
  vb = {x: b.x + b.width/2 - w/2, y: b.y + b.height/2 - h/2, w, h}; appliquer();
}

// Parenté : ancêtres et descendants
const parents = {}, enfants = {};
for (const l of D.liens) { (parents[l.b] ||= []).push(l.a); (enfants[l.a] ||= []).push(l.b); }
function parcours(q, m, vus){ for (const x of (m[q] || [])) if (!vus.has(x)) { vus.add(x); parcours(x, m, vus); } return vus; }
function surligner(ids){
  if (!ids) { svg.classList.remove('focus'); svg.querySelectorAll('.sel').forEach(e => e.classList.remove('sel')); return; }
  svg.classList.add('focus');
  svg.querySelectorAll('.org').forEach(e => e.classList.toggle('sel', ids.has(e.dataset.id)));
  svg.querySelectorAll('.lien,.continuation').forEach(e => e.classList.toggle('sel', ids.has(e.dataset.a) && ids.has(e.dataset.b)));
}
svg.querySelectorAll('.org').forEach(g => {
  g.addEventListener('mouseenter', () => { const q = g.dataset.id;
    const s = parcours(q, parents, new Set([q])); parcours(q, enfants, s); surligner(s); });
  g.addEventListener('mouseleave', () => surligner(null));
});
svg.querySelectorAll('.renvoi').forEach(t => {
  const paire = () => svg.querySelectorAll(`.renvoi[data-a="${CSS.escape(t.dataset.a)}"][data-b="${CSS.escape(t.dataset.b)}"]`);
  t.addEventListener('mouseenter', e => { e.stopPropagation(); paire().forEach(x => x.classList.add('sel')); surligner(new Set([t.dataset.a, t.dataset.b])); });
  t.addEventListener('mouseleave', () => { paire().forEach(x => x.classList.remove('sel')); });
  t.addEventListener('click', e => { e.stopPropagation(); const autre = [...paire()].find(x => x !== t);
    const cible = autre || svg.querySelector(`.org[data-id="${CSS.escape(t.dataset.a === t.closest('.org').dataset.id ? t.dataset.b : t.dataset.a)}"]`);
    if (cible) centrer(cible); });
});

// Recherche
const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
let trouves = [], rang = 0;
const champ = document.getElementById('recherche'), res = document.getElementById('resultat');
champ.addEventListener('input', () => {
  const q = norm(champ.value.trim());
  svg.querySelectorAll('.org.trouve').forEach(e => e.classList.remove('trouve'));
  trouves = q ? [...svg.querySelectorAll('.org')].filter(g => g.dataset.recherche.includes(q)) : [];
  trouves.forEach(g => g.classList.add('trouve')); rang = 0;
  res.textContent = q ? `${trouves.length} résultat${trouves.length > 1 ? 's' : ''}` : '';
  if (trouves.length) centrer(trouves[0]);
});
champ.addEventListener('keydown', e => { if (e.key === 'Enter' && trouves.length) { rang = (rang + 1) % trouves.length; centrer(trouves[rang]); } });

// Bandes d'affiliation
document.getElementById('bandes').onchange = e => svg.classList.toggle('sans-bandes', !e.target.checked);

// Repli des familles : décale les voies suivantes et recalcule les liens
const replies = new Set();
const RESTE = 44;
function decalages(){ const d = {}; let cumul = 0;
  for (const v of D.voies) { d[v.i] = cumul; if (replies.has(v.i)) cumul -= (v.h - RESTE); } return [d, cumul]; }
function relayout(){
  const [d, total] = decalages();
  svg.querySelectorAll('.voie, .contenu-voie').forEach(g => {
    const i = +g.dataset.voie; g.setAttribute('transform', `translate(0,${d[i]})`);
    if (g.classList.contains('contenu-voie')) g.style.display = replies.has(i) ? 'none' : '';
    if (g.classList.contains('voie')) { g.classList.toggle('replie', replies.has(i));
      const r = g.querySelector('.fond-voie'); const v = D.voies.find(v => v.i === i);
      r.setAttribute('height', replies.has(i) ? RESTE : v.h); g.querySelectorAll('rect')[1].setAttribute('height', replies.has(i) ? RESTE : v.h); }
  });
  const iSD = D.voies.find(v => v.cle === 'sans date');
  const dBas = iSD ? d[iSD.i] : total;
  svg.querySelector('.axe-bas').setAttribute('transform', `translate(0,${dBas})`);
  svg.querySelectorAll('.bande-decennie').forEach(r => { r.dataset.h ||= r.getAttribute('height'); r.setAttribute('height', +r.dataset.h + dBas); });
  const cle = svg.querySelector('.cle-internationales'); if (cle) { cle.dataset.t ||= cle.getAttribute('transform'); }
  svg.querySelectorAll('.lien, .marque-fusion').forEach(g => {
    const cache = (g.dataset.va && (replies.has(+g.dataset.va) || replies.has(+g.dataset.vb)));
    g.style.display = cache ? 'none' : '';
    g.querySelectorAll('.geo').forEach(el => { const pts = JSON.parse(el.dataset.geo).map(([x, y, v]) => [x, y + d[v]]);
      if (el.tagName === 'path') el.setAttribute('d', 'M' + pts.map(p => p.join(' ')).join(' L'));
      else el.setAttribute('points', pts.map(p => p.join(',')).join(' ')); });
  });
}
const fam = document.getElementById('familles');
for (const v of D.voies) { const b = document.createElement('button'); b.textContent = v.titre.replace(' (hors échelle)', '');
  b.title = 'Replier / déplier cette famille'; b.setAttribute('aria-pressed', 'false');
  b.onclick = () => { replies.has(v.i) ? replies.delete(v.i) : replies.add(v.i); b.setAttribute('aria-pressed', replies.has(v.i)); relayout(); };
  fam.appendChild(b); }

// Clé des Internationales
const entrees = document.getElementById('entrees');
let choisie = null;
function membres(id){ const c = D.cle.find(c => c.id === id); return new Set(c ? c.membres : []); }
for (const c of D.cle) {
  const div = document.createElement('div'); div.className = 'entree'; div.id = 'cle-' + c.id;
  div.innerHTML = `<span class="puce" style="background:${c.couleur}"></span><b></b> <span class="nom"></span> <span style="color:var(--doux)"></span>` +
    (c.succession ? '<div class="succ"></div>' : '');
  div.querySelector('b').textContent = c.sigle; div.querySelector('.nom').textContent = c.nom;
  div.querySelectorAll('span')[2].textContent = `(${c.dates}) · ${c.membres.length} membre${c.membres.length > 1 ? 's' : ''}`;
  if (c.succession) div.querySelector('.succ').textContent = 'Succession : ' + c.succession;
  div.addEventListener('mouseenter', () => surligner(membres(c.id)));
  div.addEventListener('mouseleave', () => { if (choisie) surligner(membres(choisie)); else surligner(null); });
  div.addEventListener('click', () => { document.querySelectorAll('.entree').forEach(e => e.classList.remove('choisie'));
    if (choisie === c.id) { choisie = null; surligner(null); } else { choisie = c.id; div.classList.add('choisie'); surligner(membres(c.id)); } });
  entrees.appendChild(div);
}
svg.querySelectorAll('.badge').forEach(b => b.addEventListener('click', e => { e.stopPropagation();
  const d = document.getElementById('cle'); d.open = true; const ent = document.getElementById('cle-' + b.dataset.intl);
  if (ent) { ent.scrollIntoView({block:'center', behavior:'smooth'}); ent.classList.add('flash'); setTimeout(() => ent.classList.remove('flash'), 1500);
    choisie = b.dataset.intl; document.querySelectorAll('.entree').forEach(e => e.classList.toggle('choisie', e === ent)); surligner(membres(choisie)); } }));
ajuster();
</script>
</body>
</html>
"""


# ======================================================================

def main():
    orgs, liens, inter, T_AUJ = charger()
    m = mise_en_page(orgs, liens, inter, T_AUJ)
    svg = dessiner(m, avec_cle=True)
    with open(os.path.join(SORTIE, "arbre.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    shutil.copyfile(os.path.join(SORTIE, "arbre.svg"), "arbre.svg")
    with open(os.path.join(SORTIE, "arbre.html"), "w", encoding="utf-8") as f:
        f.write(page_html(m, dessiner(m, avec_cle=False, interactif=True)))
    for k, t, _ in VOIES:
        if not any(o["voie"] == k for o in orgs.values()):
            continue
        mf = mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues={k},
                          titre=f"Généalogie de la gauche française : {t.lower()}")
        with open(os.path.join(SORTIE, f"arbre_{slug(k)}.svg"), "w", encoding="utf-8") as f:
            f.write(dessiner(mf, avec_cle=True))
    if m["anomalies_rendu"]:
        with open(os.path.join(SORTIE, "anomalies_rendu.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["source", "target", "relation", "source_date", "target_date", "probable_cause"])
            w.writerows(m["anomalies_rendu"])
    print(f"{sum(1 for o in m['items'].values())} organisations dessinées, {len(m['traces'])} liens tracés, "
          f"{len(m['renvois'])} renvois textuels, {len(m['continuations'])} continuations, "
          f"{len(m['anomalies_rendu'])} liens non dessinables.")
    print(f"Taille : {m['largeur']:.0f} x {m['hauteur_lanes']:.0f} px (hors clé). "
          f"Fichiers : data/sortie/arbre.svg, arbre.svg, data/sortie/arbre.html, data/sortie/arbre_<famille>.svg")


if __name__ == "__main__":
    main()
