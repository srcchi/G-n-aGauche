"""
Phase 2 : mise en page et rendu de l'arbre, sans Graphviz.

Dessine les organisations gardées par la porte finale de nettoyage.py (colonne garde) : organisations
actives validées reliées et leurs ancêtres, toutes datées, chacune avec au moins un lien affiché.

Règles (vérifiées par verifier.py) : R1 liens orthogonaux vers la droite ; R2 Internationales jamais
en boîte ; R3 dates exactes ; R4 noms dans les étiquettes ; R5 lignée stricte ; R6 ni coalition ni
satellite ; R8 citations ; zéro croisement (un lien qui croiserait une barre, une étiquette ou un
onglet devient un renvoi, après tentative de placement sans croisement).

Entrées : data/sortie/organisations.csv, liens.csv, etiquettes.csv, internationales.csv,
          affiliations.csv (nettoyage.py)
Sorties : data/sortie/arbre.svg (+ copie arbre.svg à la racine), arbre.html, arbre_<famille>.svg,
          arbre_apercu.svg (si très grand), vue_internationales.svg et .html, anomalies_rendu.csv

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

# ---------- Géométrie (px) ----------
PPA = 13.0
COL_VOIES = 210
X0 = COL_VOIES + 30
BAR_H = 16
GAP = 14
ROW_GAP = 12
GOUTTIERE = 10
FLECHE_L, FLECHE_DEMI = 10, 5
MIN_W = 6
DEGRADE = 28
TAG_PAD, TAG_H = 6, 22
FRAME_W, FRAME_PAS, TAB_H = 2.4, 5, 15
POINT_R = 3.5
SEUIL_ANNEES, SEUIL_VOIES, SEUIL_RANGS, MAX_RENVOIS = 40, 2, 6, 3
CASSURE_ANS, CASSURE_PX = 60, 44
VOIE_PAD = 8
FS, FS_SIGLE = 11, 13
POLICE = "Arial, Helvetica, sans-serif"
CLE_W = 300                      # colonne de clé compacte, à droite de l'arbre

# Voies (2.1) : une par famille politique, palette Okabe-Ito
VOIES = [
    ("socialistes", "Socialistes", "#CC79A7"),
    ("radicaux", "Radicaux", "#F0E442"),
    ("écologistes", "Écologistes", "#009E73"),
    ("communistes", "Communistes", "#D55E00"),
    ("trotskystes", "Trotskystes", "#E69F00"),
    ("maoïstes", "Maoïstes", "#0072B2"),
    ("anarchistes et libertaires", "Anarchistes et libertaires", "#000000"),
]
TEINTE = {k: c for k, _, c in VOIES}
TITRES = {k: t for k, t, _ in VOIES}
NUANCES = {"communiste libertaire": 0.30, "anarcho-syndicaliste": 0.45,
           "luxemburgiste / conseilliste": 0.35, "écosocialiste": -0.30}
# Internationales : 12 couleurs distinctes et sûres pour les daltoniens (Paul Tol, « muted » et « bright »)
PALETTE_INTER = ["#332288", "#88CCEE", "#44AA99", "#117733", "#999933", "#DDCC77", "#CC6677",
                 "#882255", "#AA4499", "#4477AA", "#66CCEE", "#BBBBBB"]
STYLE_LIEN = {
    "renommage": dict(couleur="#3D3D3D", dash="", w=2.6, nom="renommage"),
    "refondation": dict(couleur="#3D3D3D", dash="8 3", w=2.0, nom="refondation"),
    "fusion": dict(couleur="#3D3D3D", dash="", w=2.0, nom="fusion"),
    "scission": dict(couleur="#C0392B", dash="6 3", w=1.6, nom="scission"),
    "absorption": dict(couleur="#5B4B8A", dash="", w=1.8, nom="absorption"),
    "filiation_idéologique": dict(couleur="#7F7F7F", dash="2 3", w=1.4, nom="filiation idéologique"),
    "passage": dict(couleur="#2471A3", dash="1.5 3", w=1.2, nom="passage de militants"),
}
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
RENVOI_MOT = {"scission": "scission de", "absorption": "absorbe", "fusion": "issu de", "renommage": "issu de",
              "refondation": "refondation de", "filiation_idéologique": "filiation de", "passage": "militants de"}


# ======================================================================
# Outils
# ======================================================================

def lire(nom):
    chemin = os.path.join(SORTIE, nom)
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


MOTS_VIDES = {"de", "la", "le", "les", "des", "du", "pour", "l", "d", "et", "à", "en", "contre", "sur", "au", "aux",
              "envers", "un", "une"}


def acronyme(nom):
    """Sigle d'une Internationale sans sigle connu : initiales du nom, partie entre parenthèses à part.
    Ex. « Quatrième Internationale (lambertiste) » -> « QI (lambertiste) »."""
    base = re.sub(r"\s*\([^)]*\)", "", nom)
    res = "-".join("".join(w[0].upper() for w in re.findall(r"[^\W\d_]+", p) if w.lower() not in MOTS_VIDES)
                   for p in re.split(r"\s+[-–]\s+", base))
    m = re.search(r"\(([^)]*)\)", nom)
    return f"{res} ({m.group(1)})" if m and len(m.group(1)) <= 12 else res


def couper(s, w, fs, gras=False, max_lignes=2):
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


def segments_croisent_boite(p1, p2, b, eps=0.6):
    """Le segment orthogonal p1-p2 traverse-t-il l'intérieur de la boîte b = (x, y, w, h) ?"""
    (xa, ya), (xb, yb) = p1, p2
    bx, by, bw, bh = b
    if abs(ya - yb) < 1e-6:          # horizontal
        y = ya
        if not (by + eps < y < by + bh - eps):
            return False
        g, d = sorted((xa, xb))
        return g < bx + bw - eps and d > bx + eps
    x = xa                           # vertical
    if not (bx + eps < x < bx + bw - eps):
        return False
    h, b_ = sorted((ya, yb))
    return h < by + bh - eps and b_ > by + eps


# ======================================================================
# Données
# ======================================================================

def charger():
    T_AUJ = aujourdhui()
    etiq = {r["id"]: r["etiquette"] for r in lire("etiquettes.csv")}
    inter = {}
    for r in lire("internationales.csv"):
        inter[r["id"]] = dict(id=r["id"], nom=r["name"], sigle=r["sigle"] or acronyme(r["name"]),
                              debut=r["start"], fin=r["end"],
                              pred=[p for p in r["predecessor_id"].split(" | ") if p],
                              type_succ=r.get("succession_type", ""), cit_succ=r.get("succession_citation", ""),
                              scissions=[p for p in r.get("scissions_de", "").split(" | ") if p], membres=[])
    orgs = {}
    for r in lire("organisations.csv"):
        if r.get("garde") != "oui":
            continue
        statut = r["statut_fin"]
        t0 = t_de(r["fondation"], r["fondation_mois"])
        if statut.startswith("actif"):
            t1, fin_txt = None, ""
        elif r["dissolution"]:
            t1, fin_txt = t_de(r["dissolution"], r["dissolution_mois"]), r["dissolution"]
        else:
            t1, fin_txt = t_de(r["fin_deduite"]), r["fin_deduite"]
        fam_c = r["famille_courant"] if r["famille_courant"] in TEINTE else r["famille"]
        couleur = nuance(TEINTE.get(fam_c, "#8C8C8C"), NUANCES.get(r["courant_principal"], 0))

        def date_longue(a, m):
            return f"{MOIS[int(m) - 1]} {a}" if m else str(a)
        fin_detail = ("toujours active (validée)" if statut == "actif_valide" else
                      f"fin : {date_longue(r['dissolution'], r['dissolution_mois'])}" if r["dissolution"] else
                      f"fin : {r['fin_deduite']} (fondation du successeur)")
        orgs[r["id"]] = dict(id=r["id"], label=r["label"], etiquette=etiq.get(r["id"], r["nom_court"]),
                             voie=r["famille"], couleur=couleur, t0=t0, t1=t1, statut=statut,
                             an0=r["fondation"], fin_txt=fin_txt, affil=[],
                             details=[r["label"], f"fondation : {date_longue(r['fondation'], r['fondation_mois'])}",
                                      fin_detail, f"famille : {r['famille']}",
                                      f"courants : {r['courants_sources'] or 'aucun reconnu'}"]
                             + ([f"organisations liées : {r['organisations_liees']}"] if r.get("organisations_liees") else [])
                             + ([f"journaux : {r['journaux']}"] if r["journaux"] else []))
    for r in lire("affiliations.csv"):
        if r["party_id"] in orgs and r["international_id"] in inter:
            orgs[r["party_id"]]["affil"].append(r)
            inter[r["international_id"]]["membres"].append(r["party_id"])
    liens = []
    for r in lire("liens.csv"):
        if r["source"] in orgs and r["cible"] in orgs:
            liens.append(dict(a=r["source"], b=r["cible"], rel=r["relation"],
                              t=t_de(r["date_evenement"], r["date_evenement_mois"]),
                              preuve=r.get("preuve", ""), citation=r.get("citation", ""),
                              source_cit=r.get("source_citation", "")))
    # Couleurs des Internationales : une par Internationale affichée, dans l'ordre chronologique
    affichees = sorted({i for o in orgs.values() for a in o["affil"] for i in [a["international_id"]]},
                       key=lambda i: (inter[i]["debut"] or "9999", inter[i]["nom"]))
    for k, i in enumerate(affichees):
        inter[i]["couleur"] = PALETTE_INTER[k % len(PALETTE_INTER)]
        inter[i]["motif"] = k >= len(PALETTE_INTER)          # au-delà de 12 : couleur + hachures
    for i, d in inter.items():
        d.setdefault("couleur", "#BBBBBB")
        d.setdefault("motif", False)
    # Infobulles : liens (type, preuve, citation) et affiliations (dates)
    for l in liens:
        for q, autre, sens in ((l["a"], l["b"], "→"), (l["b"], l["a"], "←")):
            orgs[q]["details"].append(f"{sens} {STYLE_LIEN[l['rel']]['nom']} {'vers' if sens == '→' else 'depuis'} "
                                      f"{orgs[autre]['etiquette']} ({l['preuve']}) : « {l['citation'][:160]} »")
    for o in orgs.values():
        for a in o["affil"]:
            d = inter[a["international_id"]]
            dates = f"{a['start']}–{a['end']}" if a["date_certainty"] == "known" else "dates à confirmer"
            o["details"].append(f"membre de {d['sigle']} ({d['nom']}) : {dates} ; preuve {a.get('preuve', '')} : "
                                f"« {a.get('citation', '')[:140]} »")
    return orgs, liens, inter, T_AUJ


class Echelle:
    def __init__(self, debuts, T_AUJ):
        d = sorted(debuts)
        self.T0 = math.floor(d[0] / 10) * 10 if d else 1900
        self.T1 = math.ceil(T_AUJ / 10) * 10
        self.cassure = None
        for a, b in zip(d, d[1:]):
            if b - a > CASSURE_ANS:
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
            if not (self.cassure and self.cassure[0] < a < self.cassure[1]):
                yield a


# ======================================================================
# Mise en page
# ======================================================================

def preparer(items, inter, ech, T_AUJ):
    for o in items.values():
        o["x0"] = ech.X(o["t0"])
        if o["t1"] is not None:
            o["x1"] = max(ech.X(o["t1"]), o["x0"] + MIN_W)
            o["x1_vis"] = o["x1"]
        else:
            o["x1"] = max(ech.X(T_AUJ), o["x0"] + MIN_W)
            o["x1_vis"] = o["x1"] + DEGRADE
        o["dates"] = f"{o['an0']}–{o['fin_txt']}"
        o["tag_w"] = larg(o["etiquette"], FS_SIGLE, True) + 6 + larg(o["dates"], FS) + 2 * TAG_PAD
        o["tag_cote"] = o.get("tag_cote", "droite")
        # Cadres : seulement si l'entrée et la sortie sont documentées ; 2 au plus (les plus longs)
        fin_o = o["t1"] if o["t1"] is not None else T_AUJ
        cadres, points = [], []
        for a in o["affil"]:
            d = inter[a["international_id"]]
            if a["date_certainty"] == "known" and a["start"]:
                ta = max(o["t0"], t_de(a["start"]))
                tb = fin_o if a["end"] in ("", "toujours membre") else min(fin_o, t_de(a["end"]))
                if tb > ta:
                    cadres.append(dict(intl=a["international_id"], ta=ta, tb=tb, couleur=d["couleur"],
                                       sigle=d["sigle"], nom=d["nom"], sortie=a["end"] != "toujours membre",
                                       debut=a["start"], fin=a["end"]))
                    continue
            points.append(dict(intl=a["international_id"], couleur=d["couleur"], sigle=d["sigle"], nom=d["nom"]))
        cadres.sort(key=lambda c: -(c["tb"] - c["ta"]))
        o["cadres_tooltip"] = cadres[2:]
        cadres = cadres[:2]
        for c in sorted(cadres, key=lambda c: c["tb"] - c["ta"]):
            pris = {c2["niveau"] for c2 in cadres if "niveau" in c2 and c2["ta"] < c["tb"] and c["ta"] < c2["tb"]}
            c["niveau"] = next(n for n in range(1, 5) if n not in pris)
        o["n_niv"] = max((c["niveau"] for c in cadres), default=0)
        o["pad_max"] = 3 + (o["n_niv"] - 1) * FRAME_PAS + FRAME_W if o["n_niv"] else 0
        x_lib = -1e9
        for c in sorted(cadres, key=lambda c: c["ta"]):
            c["pad"] = 3 + (c["niveau"] - 1) * FRAME_PAS + FRAME_W / 2
            c["xa"] = max(o["x0"], ech.X(c["ta"])) - c["pad"]
            c["xb"] = min(o["x1"], ech.X(c["tb"])) + c["pad"]
            c["tab_txt"] = c["sigle"]
            c["tab_w"] = larg(c["tab_txt"], FS, True) + 8
            c["tab_x"] = max(c["xa"] + 4, x_lib + 3)
            x_lib = c["tab_x"] + c["tab_w"]
        o["cadres"] = cadres
        o["tab_haut"] = (BAR_H / 2 + o["pad_max"] + TAB_H) if cadres else 0
        if cadres and max(c["tab_x"] + c["tab_w"] for c in cadres) > o["x1_vis"] - 2:
            o["tab_haut"] = max(o["tab_haut"], TAG_H / 2 + TAB_H + 1)   # onglet au-dessus de l'étiquette
        # Points « ? » : affiliation sans dates documentées, sur le bord haut de la barre
        o["points"] = points[:max(1, int((o["x1"] - o["x0"] - 6) // 9))] if points else []
        o["points_tooltip"] = points[len(o["points"]):]


def mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues=None, titre=""):
    voies_ordre = [v for v, _, _ in VOIES if not voies_voulues or v in voies_voulues]
    items = {q: dict(o) for q, o in orgs.items() if o["voie"] in voies_ordre}
    ech = Echelle([o["t0"] for o in items.values()], T_AUJ)
    rang_voie = {v: i for i, v in enumerate(voies_ordre)}
    preparer(items, inter, ech, T_AUJ)

    # Continuations : renommage dans la même voie, barres qui se touchent
    par_cible, par_source = defaultdict(list), defaultdict(list)
    for l in liens:
        par_cible[l["b"]].append(l)
        par_source[l["a"]].append(l)
    continuations = set()
    for l in liens:
        a, b = items.get(l["a"]), items.get(l["b"])
        if (a and b and l["rel"] == "renommage" and a["voie"] == b["voie"] and a["t1"] is not None
                and 0 <= b["x0"] - a["x1"] < GAP and len(par_cible[l["b"]]) == 1
                and sum(1 for x in par_source[l["a"]] if x["rel"] == "renommage") == 1):
            continuations.add((l["a"], l["b"]))
            a["tag_cote"] = "gauche"

    force = set()
    anomalies = []
    for _ in range(25):
        poly, renvois = [], []
        for l in liens:
            a, b = items.get(l["a"]), items.get(l["b"])
            if a is None and b is None:
                continue
            if a is None or b is None:
                renvois.append(dict(l, raison="hors de cette vue"))
                continue
            if (l["a"], l["b"]) in continuations:
                continue
            ev = abs(rang_voie[a["voie"]] - rang_voie[b["voie"]])
            t_dep = min(l["t"] - GOUTTIERE / PPA, a["t1"] if a["t1"] is not None else T_AUJ)
            if ev > SEUIL_VOIES or l["t"] - t_dep > SEUIL_ANNEES or (l["a"], l["b"]) in force:
                renvois.append(dict(l, raison="trop long ou croisement"))
            else:
                poly.append(dict(l))
        renvoyer(items, orgs, renvois)
        entrants = defaultdict(list)
        for l in poly:
            if l["rel"] != "absorption":
                entrants[l["b"]].append(l)
        for o in items.values():
            gauche_lien = (GOUTTIERE + 6) if entrants.get(o["id"]) else 0
            tabs = [(c["tab_x"], c["tab_x"] + c["tab_w"]) for c in o["cadres"]]
            L = min([o["x0"] - gauche_lien - o["pad_max"], o["x0"] - POINT_R] + [t[0] for t in tabs])
            R = max([o["x1_vis"], o["x1"] + o["pad_max"]] + [t[1] for t in tabs])
            if o["tag_cote"] == "droite":
                R = max(R, o["x1_vis"] + o["tag_w"] + o["w_renv"])
            else:
                L = min(L, o["x0"] - gauche_lien - o["tag_w"] - o["w_renv"])
            o["gauche_lien"] = gauche_lien
            o["L"], o["R"] = L, R
        rangees = placer(items, voies_ordre, liens, poly, continuations)
        geo = ordonnees(items, voies_ordre, rangees, ech)
        traces, nouv_anom = geometrie(items, poly, rang_voie)
        anomalies = nouv_anom
        boites = boites_obstacles(items)
        a_forcer = {(t["a"], t["b"]) for t in traces
                    if t["rangs"] > SEUIL_RANGS or croisements(t, boites, items)}
        a_forcer |= {(x[0], x[1]) for x in nouv_anom}
        if not a_forcer - force:
            break
        force |= a_forcer
    traces = [t for t in traces if (t["a"], t["b"]) not in force]
    cle = cle_internationales_donnees(items, inter)
    largeur = max([o["R"] for o in items.values()] + [ech.X(ech.T1)]) + 40
    return dict(items=items, traces=traces, renvois=renvois, continuations=continuations, ech=ech,
                T_AUJ=T_AUJ, largeur=largeur, cle=cle, inter=inter, titre=titre, anomalies=anomalies,
                rels=sorted({t["rel"] for t in traces}), **geo)


def renvoyer(items, orgs, renvois):
    """Textes de renvoi collés à l'étiquette ; plus de 3 : un seul « voir aussi »."""
    for o in items.values():
        o["renv"] = []
    for r in renvois:
        a, b = items.get(r["a"]), items.get(r["b"])
        if a is not None:
            cible = b or orgs[r["b"]]
            a["renv"].append((f"→ {cible['etiquette']}", r["b"], r["a"], r["b"]))
        if b is not None:
            src = a or orgs[r["a"]]
            b["renv"].append((f"{RENVOI_MOT.get(r['rel'], 'issu de')} {src['etiquette']}", r["a"], r["a"], r["b"]))
    for o in items.values():
        if len(o["renv"]) > MAX_RENVOIS:
            o["voir_aussi"] = list(o["renv"])
            o["renv"] = [(f"voir aussi ({len(o['voir_aussi'])})", "", "", "")]
        else:
            o["voir_aussi"] = []
        o["w_renv"] = sum(larg(t, FS) + 6 for t, *_ in o["renv"])


def placer(items, voies_ordre, liens, poly, continuations):
    """Rangées par voie (2.2) : chaque arbre relié par des liens dessinés forme un bloc contigu ;
    les barres reliées seulement par des renvois vont en bas de la voie. Dans un bloc, une rangée
    est choisie d'abord pour ne créer aucun croisement (2.3), puis pour rester près de l'ancêtre."""
    voisins = defaultdict(set)
    parents = defaultdict(list)
    for l in poly:
        a, b = items[l["a"]], items[l["b"]]
        if a["voie"] == b["voie"]:
            voisins[l["a"]].add(l["b"])
            voisins[l["b"]].add(l["a"])
        parents[l["b"]].append(l)
    for a, b in continuations:
        voisins[a].add(b)
        voisins[b].add(a)
    cont_parent = {b: a for a, b in continuations}
    res, rang_global = {}, 0
    for v in voies_ordre:
        membres = [q for q, o in items.items() if o["voie"] == v]
        blocs, seuls, vus = [], [], set()
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
            (blocs if len(comp) > 1 else seuls).append(sorted(comp, key=lambda x: (items[x]["x0"], items[x]["label"])))
        if seuls:
            blocs.append([q for s in seuls for q in s])       # barres à renvois seuls : en bas, ensemble
        rangees, debuts = [], set()
        for bloc in blocs:
            debut = len(rangees)
            debuts.add(debut)
            local, segments = [], []                            # segments verticaux : (x, rangée min, rangée max)

            def occupe(r, x):
                return any(l2 - 0.5 < x < r2 + 0.5 for l2, r2, _ in local[r])

            def cout(o, r):
                c = 0
                for l in parents[o["id"]]:
                    p = items[l["a"]]
                    if p.get("bloc_v") != (v, debut) or "rang_l" not in p:
                        continue
                    x = o["x0"] - GOUTTIERE if l["rel"] != "absorption" else p["x1"] - 2
                    h, b = sorted((p["rang_l"], r))
                    c += sum(1 for rr in range(h + 1, b) if occupe(rr, x))
                c += sum(1 for x, h, b in segments if h < r < b and o["L"] - 0.5 < x < o["R"] + 0.5)
                for l in parents[o["id"]]:          # au-delà de 6 rangées, le lien deviendrait un renvoi
                    p = items[l["a"]]
                    if p.get("bloc_v") == (v, debut) and "rang_l" in p and abs(p["rang_l"] - r) > SEUIL_RANGS:
                        c += 1
                return c

            def libre(r, L, R, sauf=None):
                for l2, r2, q2 in local[r]:
                    if q2 == sauf and L >= items[q2]["x1"] - 0.5:
                        continue
                    if not (R + GAP <= l2 or r2 + GAP <= L):
                        return False
                return True
            # Ordre de placement : parcours en profondeur depuis la racine, enfants du plus récent au
            # plus ancien. Le lien vers un enfant plus ancien ne traverse alors que des rangées
            # d'organisations fondées après lui : leurs barres ne couvrent pas encore la date du lien.
            enfants_v = defaultdict(list)
            for l in poly:
                if l["a"] in bloc and l["b"] in bloc:
                    enfants_v[l["a"]].append(l["b"])
            for a_, b_ in continuations:
                if a_ in bloc and b_ in bloc:
                    enfants_v[a_].append(b_)
            dans_bloc = set(bloc)
            racines = [q for q in bloc if not any(q in enfants_v[p] for p in dans_bloc)] or bloc[:1]
            ordre, vus_o = [], set()

            def visite(n):
                if n in vus_o:
                    return
                vus_o.add(n)
                ordre.append(n)
                for c in sorted(enfants_v[n], key=lambda c: -items[c]["x0"]):
                    visite(c)
            for r_ in racines:
                visite(r_)
            ordre += [q for q in bloc if q not in vus_o]
            for q in ordre:
                o = items[q]
                o.pop("rang_l", None)
                o["bloc_v"] = (v, debut)
                place = None
                p = cont_parent.get(q)
                if p and "rang_l" in items[p] and items[p].get("bloc_v") == (v, debut) \
                        and libre(items[p]["rang_l"], o["L"], o["R"], sauf=p):
                    place = items[p]["rang_l"]
                if place is None:
                    prefs = [items[l["a"]]["rang_l"] for l in parents[q]
                             if items[l["a"]].get("bloc_v") == (v, debut) and "rang_l" in items[l["a"]]]
                    pref = prefs[0] + 1 if prefs else 0
                    candidats = [r for r in range(len(local)) if libre(r, o["L"], o["R"])] + [len(local)]
                    while len(local) < candidats[-1] + 1:
                        local.append([])
                    place = min(candidats, key=lambda r: (cout(o, r), abs(r - pref), r < pref))
                if place == len(local):
                    local.append([])
                local[place].append((o["L"], o["R"], q))
                o["rang_l"] = place
                for l in parents[q]:
                    pp = items[l["a"]]
                    if pp.get("bloc_v") == (v, debut) and "rang_l" in pp:
                        x = o["x0"] - GOUTTIERE if l["rel"] != "absorption" else pp["x1"] - 2
                        segments.append((x, *sorted((pp["rang_l"], place))))
            while local and not local[-1]:
                local.pop()
            for r in local:
                rangees.append([q for _, _, q in r])
            for q in bloc:
                items[q]["rang_g"] = rang_global + debut + items[q]["rang_l"]
        rang_global += len(rangees)
        res[v] = dict(rangees=rangees, debuts_blocs=debuts)
    return res


def ordonnees(items, voies_ordre, rangees, ech):
    entete_h, axe_h = 160, 34
    y = entete_h + axe_h
    voies_geo = []
    for v in voies_ordre:
        membres = [o for o in items.values() if o["voie"] == v]
        if not membres:
            continue
        y_voie = y
        y += VOIE_PAD
        info = rangees[v]
        for i, contenu in enumerate(info["rangees"]):
            haut = bas = TAG_H / 2
            for q in contenu:
                o = items[q]
                haut = max(haut, BAR_H / 2 + o["pad_max"], o["tab_haut"], BAR_H / 2 + POINT_R + 1)
                bas = max(bas, BAR_H / 2 + o["pad_max"])
            for q in contenu:
                items[q]["y_c"] = y + ROW_GAP / 2 + haut
                items[q]["rang_y"], items[q]["rang_h"] = y, haut + bas + ROW_GAP
            y += haut + bas + ROW_GAP
        y += VOIE_PAD
        voies_geo.append(dict(cle=v, y=y_voie, h=y - y_voie, n=len(membres)))
    y += axe_h + 12
    for i, g in enumerate(voies_geo):
        g["i"] = i
    return dict(voies=voies_geo, voie_index={g["cle"]: g["i"] for g in voies_geo}, hauteur=y,
                y_axe_haut=entete_h, y_axe_bas=y - axe_h - 12)


def geometrie(items, poly, rang_voie):
    traces, anomalies = [], []
    entrants = defaultdict(list)
    for l in poly:
        entrants[l["b"]].append(l)
    for qb, ls in entrants.items():
        b = items[qb]
        normaux = sorted([l for l in ls if l["rel"] != "absorption"], key=lambda l: items[l["a"]]["y_c"])
        n = len(normaux)
        for k, l in enumerate(ls):
            a = items[l["a"]]
            if l["rel"] == "absorption":
                # Flèche qui finit sur la barre absorbante, au moment de l'absorption
                xs = a["x1"] - 2
                xt = xs + 12
                if not (b["x0"] + 2 <= xt <= b["x1"] - 1) or a["rang_y"] == b["rang_y"]:
                    anomalies.append((l["a"], l["b"], l["rel"], a["an0"], b["an0"],
                                      "absorption impossible à dessiner (la cible ne couvre pas la date)"))
                    continue
                bas = b["y_c"] > a["y_c"]
                y_dep = a["y_c"] + BAR_H / 2 if bas else a["y_c"] - BAR_H / 2
                y_arr = b["y_c"] - BAR_H / 2 - 1 if bas else b["y_c"] + BAR_H / 2 + 1
                pts = [(xs, y_dep), (xs, y_arr), (xt, y_arr)]
                depart = None
            else:
                kk = normaux.index(l)
                off = max(-(BAR_H / 2 - 3), min(BAR_H / 2 - 3, (kk - (n - 1) / 2) * 5))
                xt, yt = b["x0"], b["y_c"] + off
                bas = yt > a["y_c"]
                if a["x1"] < xt - GOUTTIERE:
                    xs, xv = a["x1"], xt - GOUTTIERE
                    if a["rang_y"] == b["rang_y"]:
                        pts = [(xs, yt), (xt, yt)]
                    else:
                        canal = a["rang_y"] + a["rang_h"] - 3 if bas else a["rang_y"] + 2
                        pts = [(xs, a["y_c"]), (xs, canal), (xv, canal), (xv, yt), (xt, yt)]
                    depart = (xs, a["y_c"])
                else:
                    xs = max(xt - GOUTTIERE, a["x0"] + min(2, (xt - a["x0"]) / 2))
                    y_bord = a["y_c"] + BAR_H / 2 if bas else a["y_c"] - BAR_H / 2
                    pts = [(xs, y_bord), (xs, yt), (xt, yt)]
                    depart = (xs, a["y_c"])
                if xt - pts[-2][0] < 3:
                    anomalies.append((l["a"], l["b"], l["rel"], a["an0"], b["an0"],
                                      "dates trop proches : segment final de moins de 3 px"))
                    continue
            vp = [a["voie"]] * (len(pts) - 2) + [b["voie"]] * 2 if len(pts) > 2 else [a["voie"], b["voie"]]
            traces.append(dict(l, pts=pts, voies_pts=vp, depart=depart,
                               annees=(pts[-1][0] - pts[0][0]) / PPA,
                               voies=abs(rang_voie[a["voie"]] - rang_voie[b["voie"]]),
                               rangs=abs(a["rang_g"] - b["rang_g"])))
    return traces, anomalies


def boites_obstacles(items):
    """Barres, étiquettes et onglets : ce qu'un lien ne doit jamais traverser."""
    boites = []
    for o in items.values():
        yb = o["y_c"] - BAR_H / 2
        boites.append((o["id"], "barre", (o["x0"], yb, o["x1_vis"] - o["x0"], BAR_H)))
        tx = o["x1_vis"] if o["tag_cote"] == "droite" else o["x0"] - o.get("gauche_lien", 0) - o["tag_w"]
        boites.append((o["id"], "etiquette", (tx, o["y_c"] - TAG_H / 2, o["tag_w"], TAG_H)))
        for c in o["cadres"]:
            boites.append((o["id"], "onglet", (c["tab_x"], o["y_c"] - o["tab_haut"], c["tab_w"], TAB_H)))
    return boites


def croisements(t, boites, items):
    n = 0
    for p1, p2 in zip(t["pts"], t["pts"][1:]):
        for q, sorte, b in boites:
            if sorte == "barre" and q in (t["a"], t["b"]):
                continue          # départ et arrivée sur leurs propres barres
            if segments_croisent_boite(p1, p2, b):
                n += 1
    return n


def cle_internationales_donnees(items, inter):
    utiles = {a["international_id"] for o in items.values() for a in o["affil"]}
    nom_annee = lambda i: f"{inter[i]['nom']} {inter[i]['debut'] or '?'}–{inter[i]['fin']}"

    def succession(i):
        """Chaîne de succession (renommage, fusion, refondation) seulement (règle 1.3)."""
        racine, vus = i, set()
        while inter[racine]["pred"] and racine not in vus and inter[racine]["pred"][0] in inter:
            vus.add(racine)
            racine = inter[racine]["pred"][0]
        etapes, x, vus = [], racine, set()
        while x and x not in vus:
            vus.add(x)
            etapes.append(nom_annee(x))
            x = next((s for s, d in inter.items() if x in d["pred"]), None)
        return ", puis ".join(etapes) if len(etapes) > 1 else ""
    return [dict(id=i, sigle=inter[i]["sigle"], nom=inter[i]["nom"],
                 dates=f"{inter[i]['debut'] or '?'}–{inter[i]['fin']}", couleur=inter[i]["couleur"],
                 succession=succession(i),
                 scissions=", ".join(nom_annee(s) for s in inter[i]["scissions"] if s in inter),
                 membres=[q for q in dict.fromkeys(inter[i]["membres"]) if q in items])
            for i in sorted(utiles, key=lambda i: (inter[i]["debut"] or "9999", inter[i]["nom"]))]


# ======================================================================
# SVG
# ======================================================================

def dessiner(m, avec_cle=True, apercu=False):
    items, ech = m["items"], m["ech"]
    X = ech.X
    W = m["largeur"] + (CLE_W if avec_cle and not apercu else 0)
    fond, bas_v, liens_svg, haut_v = [], defaultdict(list), [], defaultdict(list)
    for g in m["voies"]:
        c = TEINTE[g["cle"]]
        fond.append(f'<g class="voie" data-voie="{g["i"]}" data-cle="{esc(g["cle"])}">'
                    f'<rect class="fond-voie" x="0" y="{g["y"]:.1f}" width="{m["largeur"]:.1f}" height="{g["h"]:.1f}" '
                    f'fill="{melange(c, "#FFFFFF", 0.90 if g["i"] % 2 == 0 else 0.95)}"/>'
                    f'<rect class="bord-voie" x="0" y="{g["y"]:.1f}" width="8" height="{g["h"]:.1f}" fill="{c}"/>'
                    + texte(16, g["y"] + 20, TITRES[g["cle"]], 13, True, "#1A1A1A", cls="voie-t")
                    + texte(16, g["y"] + 36, f"{g['n']} organisation{'s' if g['n'] > 1 else ''}", FS, False,
                            "#333333", cls="voie-t") + "</g>")
    y_h, y_b = m["y_axe_haut"], m["y_axe_bas"]
    for a in ech.graduations():
        if (a // 10) % 2 == 0 and a < ech.T1:
            fond.append(f'<rect class="bande-decennie" x="{X(a):.1f}" y="{y_h:.1f}" width="{X(a + 10) - X(a):.1f}" '
                        f'height="{y_b - y_h + 30:.1f}" fill="#000000" fill-opacity="0.035"/>')

    def axe(y, haut, cls):
        p = [f'<g class="{cls}"><line x1="{X(ech.T0):.1f}" x2="{X(ech.T1):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="#555555"/>']
        for a in ech.graduations():
            p.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="{y - 5:.1f}" y2="{y + 5:.1f}" stroke="#555555"/>')
            p.append(texte(X(a), y - 9 if haut else y + 20, str(a), 12, True, "#333333", "middle", cls="axe-t"))
        if ech.cassure:
            xc = X(ech.cassure[0]) + CASSURE_PX / 2
            p.append(f'<rect x="{xc - 9:.1f}" y="{y - 8:.1f}" width="18" height="16" fill="#FFFFFF"/>'
                     f'<path d="M{xc - 8:.1f} {y + 7:.1f} L{xc - 2:.1f} {y - 7:.1f} M{xc + 2:.1f} {y + 7:.1f} '
                     f'L{xc + 8:.1f} {y - 7:.1f}" stroke="#333333" stroke-width="2"/>')
        return "".join(p) + "</g>"
    fond.append(axe(y_h + 26, True, "axe-haut"))
    fond.append(axe(y_b + 4, False, "axe-bas"))
    xa = X(m["T_AUJ"])
    fond.append(f'<line x1="{xa:.1f}" x2="{xa:.1f}" y1="{y_h + 26:.1f}" y2="{y_b + 4:.1f}" stroke="#777777" stroke-dasharray="2 4"/>')

    for o in sorted(items.values(), key=lambda o: (o["y_c"], o["x0"])):
        vi = m["voie_index"][o["voie"]]
        intl = " ".join(a["international_id"] for a in o["affil"])
        rech = sans_accents(f"{o['etiquette']} {o['label']}")
        ouvre = (f'<g class="org" data-id="{esc(o["id"])}" data-intl="{esc(intl)}" data-recherche="{esc(rech)}">'
                 f'<title>{esc(chr(10).join(o["details"]))}</title>')
        bas, haut = [ouvre], [ouvre.replace('class="org"', 'class="org org-haut"')]
        yc, x0, x1 = o["y_c"], o["x0"], o["x1"]
        yb = yc - BAR_H / 2
        fin = "actif" if o["statut"].startswith("actif") else f"{o['t1']:.4f}"
        if not apercu:
            for c in sorted(o["cadres"], key=lambda c: -c["niveau"]):
                bas.append(cadre(o, c, yc))
        bas.append(f'<rect class="barre" data-id="{esc(o["id"])}" data-debut="{o["t0"]:.4f}" data-fin="{fin}" '
                   f'data-statut="{o["statut"]}" x="{x0:.2f}" y="{yb:.2f}" width="{x1 - x0:.2f}" height="{BAR_H}" '
                   f'rx="{0 if o["x1_vis"] > x1 else 3}" fill="{o["couleur"]}"/>')
        if o["x1_vis"] > x1:
            bas.append(f'<rect class="fin-ouverte" x="{x1:.2f}" y="{yb:.2f}" width="{o["x1_vis"] - x1:.2f}" '
                       f'height="{BAR_H}" fill="url(#g-{o["couleur"][1:]})"/>')
        if not apercu:
            for k, p in enumerate(o["points"]):
                px = x0 + 5 + 9 * k
                haut.append(f'<circle class="point-affil" data-intl="{esc(p["intl"])}" data-parti="{esc(o["id"])}" '
                            f'cx="{px:.2f}" cy="{yb:.2f}" r="{POINT_R}" fill="{p["couleur"]}" stroke="#FFFFFF" '
                            f'stroke-width="1"><title>{esc(p["sigle"])} ({esc(p["nom"])}) : affiliation citée, '
                            f'dates à documenter</title></circle>')
            w = o["tag_w"]
            tx = o["x1_vis"] if o["tag_cote"] == "droite" else x0 - o.get("gauche_lien", 0) - w
            o["tag_x"] = tx
            haut.append(f'<rect class="tag" data-id="{esc(o["id"])}" x="{tx:.2f}" y="{yc - TAG_H / 2:.2f}" '
                        f'width="{w:.2f}" height="{TAG_H}" rx="4" fill="{o["couleur"]}" '
                        f'data-bbox="{tx:.2f},{yc - TAG_H / 2:.2f},{w:.2f},{TAG_H}"/>')
            ct, cd = texte_sur(o["couleur"]), gris_sur(o["couleur"])
            xx, yy = tx + TAG_PAD, yc + 4.5
            ws = larg(o["etiquette"], FS_SIGLE, True)
            haut.append(texte(xx, yy, o["etiquette"], FS_SIGLE, True, ct, cls="tag-t",
                              extra=f' data-org="{esc(o["id"])}" data-bbox="{xx:.2f},{yy - 12:.2f},{ws:.2f},14"'))
            xx += ws + 6
            haut.append(texte(xx, yy, o["dates"], FS, False, cd, cls="tag-t",
                              extra=f' data-org="{esc(o["id"])}" data-bbox="{xx:.2f},{yy - 10:.2f},{larg(o["dates"], FS):.2f},12"'))
            for c in o["cadres"]:
                ty = yc - o["tab_haut"]
                haut.append(f'<g class="onglet" data-intl="{esc(c["intl"])}" data-parti="{esc(o["id"])}">'
                            f'<title>{esc(c["nom"])} : {esc(c["debut"])}–{esc(c["fin"])}</title>'
                            f'<rect class="onglet-r" x="{c["tab_x"]:.2f}" y="{ty:.2f}" width="{c["tab_w"]:.2f}" '
                            f'height="{TAB_H}" rx="3" fill="{c["couleur"]}" '
                            f'data-bbox="{c["tab_x"]:.2f},{ty:.2f},{c["tab_w"]:.2f},{TAB_H}"/>'
                            + texte(c["tab_x"] + 4, ty + 11.5, c["tab_txt"], FS, True, texte_sur(c["couleur"]),
                                    cls="onglet-t", extra=f' data-bbox="{c["tab_x"] + 4:.2f},{ty + 1:.2f},{c["tab_w"] - 8:.2f},13"')
                            + "</g>")
            xr = tx + w if o["tag_cote"] == "droite" else tx
            for t, autre, ra, rb in o["renv"]:
                wt = larg(t, FS)
                if o["tag_cote"] != "droite":
                    xr -= wt + 6
                infob = ""
                if o["voir_aussi"]:
                    infob = "<title>" + esc("voir aussi : " + " ; ".join(x[0] for x in o["voir_aussi"])) + "</title>"
                haut.append(f'<text x="{xr + 3:.1f}" y="{yc + 4:.1f}" font-size="{FS}" font-family="{POLICE}" '
                            f'font-style="italic" fill="#555555" class="renvoi" data-org="{esc(o["id"])}" '
                            f'data-a="{esc(ra)}" data-b="{esc(rb)}" data-bbox="{xr + 3:.2f},{yc - 7:.2f},{wt:.2f},13">'
                            f'{infob}{esc(t)}</text>')
                if o["tag_cote"] == "droite":
                    xr += wt + 6
        bas.append("</g>")
        haut.append("</g>")
        bas_v[vi].append("".join(bas))
        haut_v[vi].append("".join(haut))

    for a, b in m["continuations"]:
        o = items[b]
        xj, yj = o["x0"], o["y_c"]
        haut_v[m["voie_index"][o["voie"]]].append(
            f'<g class="continuation" data-a="{esc(a)}" data-b="{esc(b)}"><title>renommage : {esc(items[a]["label"])} '
            f'devient {esc(o["label"])}</title><polyline points="{xj - 4:.1f},{yj - 6:.1f} {xj + 3:.1f},{yj:.1f} '
            f'{xj - 4:.1f},{yj + 6:.1f}" fill="none" stroke="#FFFFFF" stroke-width="4"/><polyline points="'
            f'{xj - 4:.1f},{yj - 6:.1f} {xj + 3:.1f},{yj:.1f} {xj - 4:.1f},{yj + 6:.1f}" fill="none" stroke="#1A1A1A" '
            f'stroke-width="1.6"/></g>')

    fusions = defaultdict(list)
    for t in m["traces"]:
        st = STYLE_LIEN[t["rel"]]
        pts = t["pts"]
        d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts)
        geo = json.dumps([[round(x, 2), round(y, 2), m["voie_index"][v]] for (x, y), v in zip(pts, t["voies_pts"])])
        xt, yt = pts[-1]
        fl = [(xt, yt), (xt - FLECHE_L, yt - FLECHE_DEMI), (xt - FLECHE_L, yt + FLECHE_DEMI)]
        vb = m["voie_index"][items[t["b"]]["voie"]]
        va = m["voie_index"][items[t["a"]]["voie"]]
        g = [f'<g class="lien" data-a="{esc(t["a"])}" data-b="{esc(t["b"])}" data-rel="{t["rel"]}" '
             f'data-annees="{t["annees"]:.2f}" data-voies="{t["voies"]}" data-rangs="{t["rangs"]}" '
             f'data-va="{va}" data-vb="{vb}"><title>{esc(st["nom"])} : {esc(items[t["a"]]["label"])} → '
             f'{esc(items[t["b"]]["label"])} ; preuve {esc(t["preuve"])} : « {esc(t["citation"][:200])} »</title>',
             f'<path class="halo geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="#FFFFFF" stroke-width="{st["w"] + 2.5:.1f}" stroke-opacity="0.85"/>',
             f'<path class="trait geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="{st["couleur"]}" stroke-width="{st["w"]}"'
             + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + "/>",
             f'<polygon class="fleche geo" data-geo=\'{json.dumps([[round(x, 2), round(y, 2), vb] for x, y in fl])}\' '
             f'points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in fl)}" fill="{st["couleur"]}"/>']
        if t["rel"] == "scission" and t["depart"]:
            # Petit cercle plein sur la barre mère, à la date de la scission
            xs, ys = t["depart"]
            g.append(f'<circle class="marque-scission geo-c" cx="{xs:.2f}" cy="{ys:.2f}" r="3.5" fill="{st["couleur"]}" '
                     f'stroke="#FFFFFF" stroke-width="1" data-voie="{va}"/>')
        if t["rel"] == "fusion":
            fusions[t["b"]].append(yt)
        liens_svg.append("".join(g) + "</g>")
    for qb, ys in fusions.items():
        o = items[qb]
        xm = o["x0"] - FLECHE_L - 2
        vb = m["voie_index"][o["voie"]]
        geo = json.dumps([[round(xm, 2), round(min(ys) - 3, 2), vb], [round(xm, 2), round(max(ys) + 3, 2), vb]])
        liens_svg.append(f'<g class="marque-fusion" data-b="{esc(qb)}"><path class="geo" data-geo=\'{geo}\' '
                         f'd="M{xm:.2f} {min(ys) - 3:.2f} L{xm:.2f} {max(ys) + 3:.2f}" stroke="#3D3D3D" stroke-width="3"/></g>')

    H = m["hauteur"] + 20
    cle_bas = ""
    if avec_cle and m["cle"] and not apercu:
        cle_bas, h = cle_complete(m, H, m["largeur"])
        H += h
    attrs = (f'data-x0="{X0}" data-t0="{ech.T0}" data-ppa="{PPA}" data-aujourdhui="{m["T_AUJ"]:.4f}" '
             f'data-min-w="{MIN_W}" data-seuil-annees="{SEUIL_ANNEES}" data-seuil-voies="{SEUIL_VOIES}" '
             f'data-seuil-rangs="{SEUIL_RANGS}" data-cassure="{",".join(map(str, ech.cassure)) if ech.cassure else ""}" '
             f'data-cassure-px="{CASSURE_PX}" data-degrade="{DEGRADE}" data-n-barres="{len(items)}"'
             + (' data-apercu="oui"' if apercu else ""))
    defs = "".join(f'<linearGradient id="g-{c[1:]}"><stop offset="0" stop-color="{c}"/><stop offset="1" '
                   f'stop-color="{c}" stop-opacity="0"/></linearGradient>'
                   for c in {o["couleur"] for o in items.values()} | {"#8C8C8C"})
    corps = (f'<svg xmlns="http://www.w3.org/2000/svg" id="arbre" width="{W:.0f}" height="{H:.0f}" '
             f'viewBox="0 0 {W:.0f} {H:.0f}" {attrs} font-family="{POLICE}"><title>Généalogie des organisations '
             f'de gauche en France</title><defs>{defs}</defs><rect width="{W:.0f}" height="{H:.0f}" fill="#FFFFFF"/>'
             + "".join(fond))
    for g in m["voies"]:
        corps += f'<g class="contenu-voie" data-voie="{g["i"]}">' + "".join(bas_v[g["i"]]) + "</g>"
    corps += f'<g class="liens">{"".join(liens_svg)}</g>'
    for g in m["voies"]:
        corps += f'<g class="contenu-voie" data-voie="{g["i"]}">' + "".join(haut_v[g["i"]]) + "</g>"
    if avec_cle and not apercu:
        corps += cle_compacte(m)
    return corps + legende(m, apercu) + cle_bas + "</svg>"


def cadre(o, c, yc):
    xa, xb, pad = c["xa"], c["xb"], c["pad"]
    yt, yb = yc - BAR_H / 2 - pad, yc + BAR_H / 2 + pad
    r = 4
    if c["sortie"]:
        d = (f"M{xa + r:.2f} {yt:.2f} H{xb:.2f} V{yc - 4:.2f} L{xb - 5:.2f} {yc:.2f} L{xb:.2f} {yc + 4:.2f} "
             f"V{yb:.2f} H{xa + r:.2f} Q{xa:.2f} {yb:.2f} {xa:.2f} {yb - r:.2f} V{yt + r:.2f} Q{xa:.2f} {yt:.2f} {xa + r:.2f} {yt:.2f}")
    else:
        d = (f"M{xb:.2f} {yt:.2f} H{xa + r:.2f} Q{xa:.2f} {yt:.2f} {xa:.2f} {yt + r:.2f} V{yb - r:.2f} "
             f"Q{xa:.2f} {yb:.2f} {xa + r:.2f} {yb:.2f} H{xb:.2f}")
    return (f'<path class="cadre" data-intl="{esc(c["intl"])}" data-parti="{esc(o["id"])}" data-xa="{xa:.2f}" '
            f'data-xb="{xb:.2f}" data-pad="{pad:.2f}" data-debut="{esc(c["debut"])}" data-fin="{esc(c["fin"])}" '
            f'd="{d}" fill="none" stroke="{c["couleur"]}" stroke-width="{FRAME_W}"><title>{esc(c["sigle"])} : '
            f'{esc(c["debut"])}–{esc(c["fin"])}</title></path>')


def legende(m, apercu):
    el = ['<g class="legende">']
    n = len(m["items"])
    el.append(texte(16, 32, m["titre"] or "Généalogie des organisations de gauche en France", 22, True, "#111111",
                    cls="legende-t"))
    el.append(texte(16, 52, f"{n} organisations en lignée directe · {len(m['traces'])} liens dessinés · "
                            f"{len(m['renvois'])} liens en renvoi · échelle linéaire, {PPA:g} px par an · "
                            f"Wikidata et Wikipédia, {datetime.date.today().strftime('%d/%m/%Y')}"
                            + (" · aperçu, barres seules" if apercu else ""), FS, False, "#333333", cls="legende-t"))
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
            el.append(f'<rect x="{x0}" y="{y - 10}" width="16" height="12" rx="2" fill="{c}"/>' + texte(x0 + 22, y, t, FS, cls="legende-t"))
    for rel, st in STYLE_LIEN.items():
        if rel in m["rels"]:
            x0 = place(46 + larg(st["nom"], FS))
            el.append(f'<path d="M{x0} {y - 4} H{x0 + 30}" stroke="{st["couleur"]}" stroke-width="{st["w"]}"'
                      + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + ' fill="none"/>'
                      f'<polygon points="{x0 + 38},{y - 4} {x0 + 28},{y - 9} {x0 + 28},{y + 1}" fill="{st["couleur"]}"/>'
                      + (f'<circle cx="{x0 + 3}" cy="{y - 4}" r="3.5" fill="{st["couleur"]}"/>' if rel == "scission" else "")
                      + texte(x0 + 44, y, st["nom"], FS, cls="legende-t"))
    if m["continuations"]:
        t = "renommage : la barre continue"
        x0 = place(26 + larg(t, FS))
        el.append(f'<rect x="{x0}" y="{y - 10}" width="18" height="12" fill="#8C8C8C"/><polyline points="{x0 + 6},{y - 9} '
                  f'{x0 + 12},{y - 4} {x0 + 6},{y + 1}" fill="none" stroke="#FFFFFF" stroke-width="1.6"/>'
                  + texte(x0 + 26, y, t, FS, cls="legende-t"))
    if m["renvois"] and not apercu:
        t = "issu de X, → Y : lien en renvoi (trop long ou croisement)"
        x0 = place(larg(t, FS))
        el.append(texte(x0, y, t, FS, False, "#555555", cls="legende-t", italique=True))
    t = "toujours active"
    x0 = place(40 + larg(t, FS))
    el.append(f'<rect x="{x0}" y="{y - 10}" width="10" height="12" fill="#8C8C8C"/><rect x="{x0 + 10}" y="{y - 10}" '
              f'width="24" height="12" fill="url(#g-8C8C8C)"/>' + texte(x0 + 40, y, t, FS, cls="legende-t"))
    if not apercu:
        if any(o["cadres"] for o in m["items"].values()):
            t = "membre d'une Internationale, dates documentées (cadre, onglet du sigle, encoche de sortie)"
            x0 = place(46 + larg(t, FS))
            el.append(f'<rect x="{x0}" y="{y - 12}" width="36" height="16" rx="4" fill="none" stroke="#332288" '
                      f'stroke-width="{FRAME_W}"/>' + texte(x0 + 46, y, t, FS, cls="legende-t"))
        if any(o["points"] for o in m["items"].values()):
            t = "point : affiliation citée, dates non documentées"
            x0 = place(16 + larg(t, FS))
            el.append(f'<circle cx="{x0 + 5}" cy="{y - 4}" r="{POINT_R}" fill="#332288"/>' + texte(x0 + 16, y, t, FS, cls="legende-t"))
    return "".join(el) + "</g>"


def cle_compacte(m):
    """Clé compacte juste à droite de l'arbre (2.7) : sigle, années, nombre de membres affichés."""
    x = m["largeur"] + 10
    y = m["y_axe_haut"] + 40
    el = [f'<g class="cle-compacte"><rect x="{x - 6}" y="{y - 26}" width="{CLE_W - 14}" '
          f'height="{30 + 18 * len(m["cle"])}" rx="6" fill="#F6F7F8" stroke="#D0D0D0"/>',
          texte(x + 4, y - 8, "Internationales", 13, True, "#111111", cls="cle-t")]
    for k, c in enumerate(m["cle"]):
        yy = y + 18 * k + 6
        el.append(f'<rect x="{x + 4}" y="{yy - 10}" width="14" height="12" rx="2" fill="{c["couleur"]}"/>')
        txt = f"{c['sigle']}  {c['dates']}  · {len(c['membres'])}"
        el.append(texte(x + 24, yy, txt if larg(txt, FS) < CLE_W - 50 else txt[:34] + "…", FS, False, "#1A1A1A", cls="cle-t"))
    return "".join(el) + "</g>"


def cle_complete(m, y0, W):
    items = m["items"]
    el = [f'<g class="cle-internationales" transform="translate(0,{y0:.0f})">',
          texte(16, 30, "Clé des Internationales", 16, True, "#111111", cls="cle-t"),
          texte(16, 48, "Les Internationales ne sont pas des organisations de la généalogie : elles apparaissent en cadres "
                        "(dates documentées) ou en points (dates à documenter) sur les organisations membres.",
                FS, False, "#333333", cls="cle-t")]
    col_w = (W - 32) / 2
    ys = [68, 68]
    for c in m["cle"]:
        col = 0 if ys[0] <= ys[1] else 1
        x, y = 16 + col * col_w, ys[col]
        el.append(f'<g class="entree-cle" data-intl="{esc(c["id"])}"><rect x="{x:.0f}" y="{y:.0f}" width="26" '
                  f'height="13" rx="3" fill="{c["couleur"]}"/>')
        el.append(texte(x + 34, y + 11, c["sigle"], FS, True, "#111111", cls="cle-t"))
        el.append(texte(x + 40 + larg(c["sigle"], FS, True), y + 11, f"{c['nom']} ({c['dates']})", FS, False,
                        "#1A1A1A", cls="cle-t"))
        y += 18
        lignes = []
        if c["succession"]:
            lignes.append("Succession : " + c["succession"])
        if c["scissions"]:
            lignes.append("Scissions : " + c["scissions"])
        tags = ", ".join(items[q]["etiquette"] for q in c["membres"])
        lignes.append(f"Membres affichés ({len(c['membres'])}) : {tags}")
        for l in lignes:
            for morceau in couper(l, col_w - 50, FS, max_lignes=6):
                el.append(texte(x + 34, y + 11, morceau, FS, False, "#333333", cls="cle-t"))
                y += 16
        el.append("</g>")
        ys[col] = y + 8
    return "".join(el) + "</g>", max(ys) + 20


# ======================================================================
# Vue par Internationale (2.8)
# ======================================================================

def vue_internationales(m):
    items, ech, inter = m["items"], m["ech"], m["inter"]
    X = ech.X
    y, corps, W = 110, [], m["largeur"]
    for k, c in enumerate(m["cle"]):
        membres = []
        for q in c["membres"]:
            o = items[q]
            for a in o["affil"]:
                if a["international_id"] == c["id"]:
                    connu = a["date_certainty"] == "known"
                    fin_o = o["t1"] if o["t1"] is not None else m["T_AUJ"]
                    ta = max(o["t0"], t_de(a["start"])) if a["start"] else o["t0"]
                    tb = fin_o if a["end"] in ("", "toujours membre") else min(fin_o, t_de(a["end"])) if a["end"] else fin_o
                    membres.append((o, ta, max(tb, ta + 0.5), connu))
        rangees = []
        place = []
        for o, ta, tb, connu in sorted(membres, key=lambda x: x[1]):
            xa, xb = X(ta), X(tb)
            w_e = larg(o["etiquette"], FS, True) + 10
            R = xb + (0 if xb - xa >= w_e else w_e)
            r = next((r for r, occ in enumerate(rangees) if all(R + GAP <= a or b + GAP <= xa for a, b in occ)), len(rangees))
            if r == len(rangees):
                rangees.append([])
            rangees[r].append((xa, R))
            place.append((o, xa, xb, w_e, r, connu))
        h = 50 + max(1, len(rangees)) * 26 + 10
        corps.append(f'<g class="bande-inter" data-intl="{esc(c["id"])}"><rect x="0" y="{y}" width="{W:.0f}" height="{h}" '
                     f'fill="{melange(c["couleur"], "#FFFFFF", 0.85 if k % 2 else 0.92)}"/><rect x="0" y="{y}" width="8" '
                     f'height="{h}" fill="{c["couleur"]}"/>'
                     + texte(16, y + 18, f"{c['sigle']}, {c['nom']} ({c['dates']})", 13, True, "#111111", cls="voie-t")
                     + texte(16, y + 34, ("Succession : " + c["succession"]) if c["succession"] else
                             "Pas de succession documentée", FS, False, "#333333", cls="voie-t"))
        for o, xa, xb, w_e, r, connu in place:
            yy = y + 50 + r * 26
            corps.append(f'<a href="arbre.html#{esc(o["id"])}"><g class="membre" data-id="{esc(o["id"])}"><title>'
                         f'{esc(o["label"])} : {"dates documentées" if connu else "dates à documenter"}</title>'
                         f'<rect x="{xa:.2f}" y="{yy:.2f}" width="{xb - xa:.2f}" height="20" rx="3" fill="{o["couleur"]}"'
                         + ("" if connu else ' stroke="#555555" stroke-dasharray="4 2"') + "/>"
                         + (texte(xa + 5, yy + 14, o["etiquette"], FS, True, texte_sur(o["couleur"]), cls="tag-t")
                            if xb - xa >= w_e else
                            f'<rect x="{xb:.2f}" y="{yy:.2f}" width="{w_e:.2f}" height="20" rx="3" fill="{o["couleur"]}"/>'
                            + texte(xb + 5, yy + 14, o["etiquette"], FS, True, texte_sur(o["couleur"]), cls="tag-t"))
                         + "</g></a>")
        corps.append("</g>")
        y += h
    axe = [f'<line x1="{X(ech.T0):.1f}" x2="{X(ech.T1):.1f}" y1="88" y2="88" stroke="#555555"/>',
           f'<line x1="{X(ech.T0):.1f}" x2="{X(ech.T1):.1f}" y1="{y + 8}" y2="{y + 8}" stroke="#555555"/>']
    for a in ech.graduations():
        axe.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="83" y2="93" stroke="#555555"/>'
                   + texte(X(a), 77, str(a), 12, True, "#333333", "middle", cls="axe-t"))
        axe.append(f'<line x1="{X(a):.1f}" x2="{X(a):.1f}" y1="{y + 3}" y2="{y + 13}" stroke="#555555"/>'
                   + texte(X(a), y + 28, str(a), 12, True, "#333333", "middle", cls="axe-t"))
    H = y + 50
    return (f'<svg xmlns="http://www.w3.org/2000/svg" id="vue-inter" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" '
            f'font-family="{POLICE}"><title>Vue par Internationale</title><rect width="{W:.0f}" height="{H:.0f}" fill="#FFFFFF"/>'
            + texte(16, 32, "Vue par Internationale", 22, True, "#111111", cls="legende-t")
            + texte(16, 52, "Organisations françaises affichées, regroupées par Internationale, pendant leur adhésion "
                            "(tirets : dates à documenter). Cliquer : voir l'organisation dans la généalogie.",
                    FS, False, "#333333", cls="legende-t") + "".join(axe) + "".join(corps) + "</svg>")


# ======================================================================
# HTML
# ======================================================================

def page_html(m, svg):
    voies = [dict(i=g["i"], cle=g["cle"], titre=TITRES[g["cle"]], h=g["h"]) for g in m["voies"]]
    liens = [dict(a=t["a"], b=t["b"]) for t in m["traces"]] + [dict(a=r["a"], b=r["b"]) for r in m["renvois"]] \
        + [dict(a=a, b=b) for a, b in m["continuations"]]
    cle = [dict(id=c["id"], sigle=c["sigle"], nom=c["nom"], dates=c["dates"], couleur=c["couleur"],
                succession=c["succession"], scissions=c["scissions"], membres=c["membres"],
                tags=[m["items"][q]["etiquette"] for q in c["membres"]]) for c in m["cle"]]
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
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --fond:#16181b; --texte:#ececec; --doux:#b8b8b8; --bord:#3a3d42; --panneau:#202328; --accent:#7fb2f0; } }
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
  aside { width:340px; max-width:40vw; overflow:auto; border-left:1px solid var(--bord); background:var(--panneau); padding:8px 12px; position:sticky; top:0; }
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
  #arbre .onglet, #arbre .point-affil { cursor:pointer; }
  #arbre.sans-cadres .cadre, #arbre.sans-cadres .onglet, #arbre.sans-cadres .point-affil { display:none; }
  .replie { opacity:.55; }
</style>
</head>
<body>
<header>
  <h1>Généalogie de la gauche française</h1>
  <input type="search" id="recherche" placeholder="Rechercher (sigle, nom)…" aria-label="Rechercher une organisation">
  <span id="resultat"></span>
  <button id="ajuster">Ajuster</button><button id="plus" aria-label="Zoom avant">+</button><button id="moins" aria-label="Zoom arrière">−</button>
  <label><input type="checkbox" id="cadres" checked> affiliations</label>
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
  const px = vb.x + (cx - r.left) * s, py = vb.y + (cy - r.top) * s; vb.w *= f; vb.h *= f; vb.x = px - (px - vb.x) * f; vb.y = py - (py - vb.y) * f; appliquer(); }
vue.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1/1.15, e.clientX, e.clientY); }, {passive:false});
let glisse = null;
vue.addEventListener('pointerdown', e => { if (e.target.closest('.onglet,.renvoi,.point-affil')) return; glisse = {x:e.clientX, y:e.clientY, vx:vb.x, vy:vb.y}; vue.classList.add('saisie'); });
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
  if (!t.dataset.a) return;
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
  svg.querySelector('.axe-bas').setAttribute('transform', `translate(0,${total})`);
  svg.querySelectorAll('.bande-decennie').forEach(r => { r.dataset.h ||= r.getAttribute('height'); r.setAttribute('height', +r.dataset.h + total); });
  svg.querySelectorAll('.lien, .marque-fusion').forEach(g => { const cache = g.dataset.va && (replies.has(+g.dataset.va) || replies.has(+g.dataset.vb));
    g.style.display = cache ? 'none' : '';
    g.querySelectorAll('.geo').forEach(el => { const pts = JSON.parse(el.dataset.geo).map(([x, y, v]) => [x, y + d[v]]);
      if (el.tagName === 'path') el.setAttribute('d', 'M' + pts.map(p => p.join(' ')).join(' L')); else el.setAttribute('points', pts.map(p => p.join(',')).join(' ')); });
    g.querySelectorAll('.geo-c').forEach(c => { c.dataset.cy ||= c.getAttribute('cy'); c.setAttribute('cy', +c.dataset.cy + d[+c.dataset.voie]); }); });
}
const fam = document.getElementById('familles');
for (const v of D.voies) { const b = document.createElement('button'); b.textContent = v.titre; b.title = 'Replier / déplier cette famille'; b.setAttribute('aria-pressed', 'false');
  b.onclick = () => { replies.has(v.i) ? replies.delete(v.i) : replies.add(v.i); b.setAttribute('aria-pressed', replies.has(v.i)); relayout(); }; fam.appendChild(b); }
const entrees = document.getElementById('entrees');
for (const c of D.cle) { const div = document.createElement('div'); div.className = 'entree'; div.id = 'cle-' + c.id;
  div.innerHTML = '<span class="puce"></span><b></b> <span class="nom"></span> <span class="dates" style="color:var(--doux)"></span><div class="succ s1"></div><div class="succ s2"></div><div class="succ s3"></div>';
  div.querySelector('.puce').style.background = c.couleur; div.querySelector('b').textContent = c.sigle; div.querySelector('.nom').textContent = c.nom;
  div.querySelector('.dates').textContent = `(${c.dates})`;
  div.querySelector('.s1').textContent = c.succession ? 'Succession : ' + c.succession : '';
  div.querySelector('.s2').textContent = c.scissions ? 'Scissions : ' + c.scissions : '';
  div.querySelector('.s3').textContent = `Membres affichés (${c.membres.length}) : ${c.tags.join(', ')}`;
  div.addEventListener('mouseenter', () => surligner(membres(c.id)));
  div.addEventListener('mouseleave', () => surligner(choisie ? membres(choisie) : null));
  div.addEventListener('click', () => { document.querySelectorAll('.entree').forEach(e => e.classList.remove('choisie'));
    if (choisie === c.id) { choisie = null; surligner(null); } else { choisie = c.id; div.classList.add('choisie'); surligner(membres(c.id)); } });
  entrees.appendChild(div); }
svg.querySelectorAll('.onglet, .point-affil').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); document.getElementById('cle').open = true;
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
<body><header><a href="arbre.html">Retour à la généalogie</a></header><div id="vue">__SVG__</div></body></html>
"""


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
    for ancien in os.listdir(SORTIE):
        if ancien.startswith("arbre_") and ancien.endswith(".svg") and ancien != "arbre_apercu.svg":
            os.remove(os.path.join(SORTIE, ancien))
    for k, t, _ in VOIES:
        if any(o["voie"] == k for o in orgs.values()):
            mf = mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues={k},
                              titre=f"Généalogie de la gauche française, {t.lower()}")
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
    print(f"Taille : {m['largeur'] + CLE_W:.0f} x {m['hauteur']:.0f} px (hors clé du bas)")


if __name__ == "__main__":
    main()
