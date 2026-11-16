"""
Phase 2 : mise en page et rendu de l'arbre, sans Graphviz.

Dessine les organisations gardées par la porte finale de nettoyage.py (colonne garde).

Règles (vérifiées par verifier.py) : R1 liens orthogonaux vers la droite ; R2 Internationales jamais
en boîte ; R3 dates exactes ; R4 noms dans les boîtes, étiquette au début de la barre ; R5 lignée
stricte ; R6 ni coalition ni satellite ; R8 citations complètes dans les infobulles ; zéro croisement
(routage par des couloirs entre rangées) ; liens majeurs jamais en renvoi (2.5).

Entrées : data/sortie/organisations.csv, liens.csv, etiquettes.csv, internationales.csv, affiliations.csv
Sorties : arbres/arbre.svg (+ copie arbre.svg à la racine), arbre.html, arbre_<famille>.svg,
          arbre_apercu.svg (si très grand), vue_internationales.svg et .html ; data/sortie/anomalies_rendu.csv

Usage : python rendu.py      puis      python verifier.py
"""

import csv
import datetime
import html
import itertools
import json
import math
import os
import re
import shutil
import unicodedata
from collections import Counter, defaultdict

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # racine du dépôt
SORTIE = os.path.join(RACINE, "data", "sortie")
ARBRES = os.path.join(RACINE, "arbres")          # images et pages produites

# ---------- Géométrie (px) ----------
PPA = 13.0
COL_VOIES = 210
X0 = COL_VOIES + 30
BAR_H = 20                 # barre assez haute pour porter son étiquette
GAP = 14
ROW_GAP = 12
GOUTTIERE = 10
FLECHE_L, FLECHE_DEMI = 10, 5
MIN_W = 6
DEGRADE = 28
TAG_PAD = 5
BANDE_H, BANDE_GAP, MAX_BANDES = 13, 2, 2
SEUIL_ANNEES, SEUIL_VOIES, SEUIL_RANGS, MAX_RENVOIS = 40, 2, 6, 3
VIE_MAJEURE = 20           # 2.5 : plus de 20 ans de vie, ou active, = lignée principale
CASSURE_ANS, CASSURE_PX = 60, 44
VOIE_PAD = 8
FS, FS_SIGLE = 11, 12
POLICE = "Arial, Helvetica, sans-serif"
CLE_W = 300

# Familles (palette Okabe-Ito). L'ordre affiché est calculé (2.1).
FAMILLES = {
    "socialistes": ("Socialistes", "#CC79A7"),
    "radicaux": ("Radicaux", "#F0E442"),
    "écologistes": ("Écologistes", "#009E73"),
    "communistes": ("Communistes", "#D55E00"),
    "trotskystes": ("Trotskystes", "#E69F00"),
    "maoïstes": ("Maoïstes", "#0072B2"),
    "anarchistes et libertaires": ("Anarchistes et libertaires", "#000000"),
    # Addendum 3, B2 : partis actifs sans ancêtre documenté, toujours dans la dernière voie
    "sans généalogie": ("Sans généalogie documentée", "#8C8C8C"),
}
VOIE_SANS_GEN = "sans généalogie"
BLOC = ("socialistes", "communistes", "trotskystes")      # côte à côte (2.1)
DEHORS = ("écologistes", "anarchistes et libertaires")     # hors de ce bloc
TEINTE = {k: c for k, (_, c) in FAMILLES.items()}
TITRES = {k: t for k, (t, _) in FAMILLES.items()}
NUANCES = {"communiste libertaire": 0.30, "anarcho-syndicaliste": 0.45,
           "luxemburgiste / conseilliste": 0.35, "écosocialiste": -0.30}
# Internationales : 12 teintes sûres pour les daltoniens (Paul Tol) ; une couleur par lignée
PALETTE_INTER = ["#332288", "#88CCEE", "#44AA99", "#117733", "#999933", "#DDCC77", "#CC6677",
                 "#882255", "#AA4499", "#4477AA", "#66CCEE", "#BBBBBB"]
STYLE_LIEN = {
    "renommage": dict(couleur="#3D3D3D", dash="", w=2.6, nom="renommage"),
    "refondation": dict(couleur="#3D3D3D", dash="8 3", w=2.0, nom="refondation"),
    "fusion": dict(couleur="#3D3D3D", dash="", w=2.0, nom="fusion"),
    "scission": dict(couleur="#C0392B", dash="6 3", w=1.6, nom="scission"),
    "absorption": dict(couleur="#5B4B8A", dash="", w=1.8, nom="absorption"),
    "filiation_idéologique": dict(couleur="#7F7F7F", dash="2 3", w=1.4, nom="filiation idéologique"),
    "indirect": dict(couleur="#7F7F7F", dash="1 4", w=1.6, nom="lien indirect (par une organisation étrangère)"),
    "passage": dict(couleur="#2471A3", dash="1.5 3", w=1.2, nom="passage de militants"),
    "composante": dict(couleur="#3D3D3D", dash="", w=3.2, nom="composante (membre de, sans fusion)"),
}
NAVY = "#1F2A5C"            # C1 : toutes les Internationales, une seule couleur
INTL_RUBAN, INTL_ONGLET, INTL_LIGNE = 14, 14, 22   # voie du haut : ruban, onglet au-dessus, hauteur de ligne
RX_EUROPEEN = re.compile(r"europ", re.I)
MED_R = BANDE_H / 2         # rayon du médaillon (sous les barres) ; INTL_RUBAN / 2 + 2 en haut
ONGLET_H = 15               # addendum 5, A2 : étiquette trop longue pour sa barre, en onglet collé au-dessus
FLECHE = 7                  # pointe du ruban : toujours membre, ou Internationale toujours existante
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
RENVOI_MOT = {"scission": "scission de", "absorption": "absorbe", "fusion": "issu de", "renommage": "issu de",
              "refondation": "refondation de", "filiation_idéologique": "filiation de", "passage": "militants de",
              "indirect": "issu de", "composante": "composante :"}
# Côté source, le renvoi est écrit avant la barre : le verbe dit le sens (« absorbé par LCR »,
# pas « → LCR » qui se lit comme une origine).
RENVOI_SORTANT = {"scission": "scission :", "absorption": "absorbé par", "fusion": "fusionne dans",
                  "renommage": "devient", "refondation": "refondé en", "filiation_idéologique": "inspire",
                  "passage": "militants vers", "indirect": "→", "composante": "membre de"}
MOTS_VIDES = {"de", "la", "le", "les", "des", "du", "pour", "l", "d", "et", "à", "en", "contre", "sur", "au", "aux",
              "envers", "un", "une"}


# ======================================================================
# Outils
# ======================================================================

def lire_manuel(nom):
    chemin = os.path.join(RACINE, "data", "manuel", nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def formes_courtes(nom):
    """Formes d'un nom successif, de la plus longue à la plus courte : le nom, sa partie avant « – »
    (« Les Écologistes – Europe Écologie Les Verts »), les initiales des mots à majuscule sans accents
    (« Europe Écologie Les Verts » : EELV)."""
    import unicodedata
    tete = re.split(r"\s+[–-]\s+", nom)[0]
    init = "".join(w[0] for w in re.findall(r"[^\W\d_][\w'’-]*", tete) if w[0].isupper())
    init = unicodedata.normalize("NFD", init).encode("ascii", "ignore").decode()
    return list(dict.fromkeys(x for x in (nom, tete, init if len(init) >= 3 else "") if x))


def acronyme(nom):
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


def croise(p1, p2, b, eps=0.6):
    """Le segment orthogonal p1-p2 traverse-t-il l'intérieur de la boîte b = (x, y, w, h) ?"""
    (xa, ya), (xb, yb) = p1, p2
    bx, by, bw, bh = b
    if abs(ya - yb) < 1e-6:
        if not (by + eps < ya < by + bh - eps):
            return False
        g, d = sorted((xa, xb))
        return g < bx + bw - eps and d > bx + eps
    if not (bx + eps < xa < bx + bw - eps):
        return False
    h, b_ = sorted((ya, yb))
    return h < by + bh - eps and b_ > by + eps


def simplifier(pts):
    """Retire les points répétés et les points alignés au milieu d'un segment."""
    res = []
    for p in pts:
        if res and abs(res[-1][0] - p[0]) < 1e-6 and abs(res[-1][1] - p[1]) < 1e-6:
            continue
        res.append(p)
    i = 1
    while i < len(res) - 1:
        (xa, ya), (xb, yb), (xc, yc) = res[i - 1], res[i], res[i + 1]
        if (abs(xa - xb) < 1e-6 and abs(xb - xc) < 1e-6) or (abs(ya - yb) < 1e-6 and abs(yb - yc) < 1e-6):
            res.pop(i)
        else:
            i += 1
    return res


# ======================================================================
# Données
# ======================================================================

def charger():
    T_AUJ = aujourdhui()
    etiq = {r["id"]: r["etiquette"] for r in lire("etiquettes.csv")}
    noms_tous = {r["id"]: r["nom_complet"] for r in lire("etiquettes.csv")}
    inter = {}
    for r in lire("internationales.csv"):
        inter[r["id"]] = dict(id=r["id"], nom=r["name"], sigle=r["sigle"] or acronyme(r["name"]),
                              debut=r["start"], fin=r["end"], pred=[p for p in r["predecessor_id"].split(" | ") if p],
                              type_succ=r.get("succession_type", ""),
                              scissions=[p for p in r.get("scissions_de", "").split(" | ") if p], membres=[],
                              filles=[])
    # Internationales filles (scission, succession, réunification, « se réclame de ») : un clic sur la
    # mère, dans la clé de la page HTML, montre toute sa descendance et les partis membres
    for r in lire("internationales_filles.csv"):
        if r["parente"] in inter and r["fille"] in inter:
            inter[r["parente"]]["filles"].append((r["fille"], r["relation"]))
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
        fin_detail = ("toujours active (validée)" if statut.startswith("actif") else
                      f"fin : {date_longue(r['dissolution'], r['dissolution_mois'])} ({r['dissolution_source']})"
                      if r["dissolution"] else f"fin : {r['fin_deduite']} (fondation du successeur)")
        vie = ((t1 if t1 is not None else T_AUJ) - t0)
        sans_gen = r.get("sans_genealogie") == "oui"
        orgs[r["id"]] = dict(id=r["id"], label=r["label"], etiquette=etiq.get(r["id"], r["nom_court"]),
                             voie=VOIE_SANS_GEN if sans_gen else r["famille"], famille=r["famille"], couleur=couleur,
                             sans_gen=sans_gen, t0=t0, t1=t1, statut=statut, an0=r["fondation"],
                             fin_txt=fin_txt, affil=[], majeure=statut.startswith("actif") or vie > VIE_MAJEURE,
                             details=[r["label"], f"fondation : {date_longue(r['fondation'], r['fondation_mois'])}",
                                      fin_detail, f"famille : {r['famille']}",
                                      f"courants : {r['courants_sources'] or 'aucun reconnu'}"]
                             + ([f"organisations liées : {r['organisations_liees']}"] if r.get("organisations_liees") else [])
                             + ([f"journaux : {r['journaux']}"] if r["journaux"] else [])
                             + ([f"sans généalogie documentée : aucun ancêtre documenté ; position : "
                                 f"{r['sans_genealogie_source']}"] if sans_gen else []))
    # Branches éteintes (incontournables sans descendance active) : dites dans l'infobulle
    for r in lire("branches_eteintes.csv"):
        if r["id"] in orgs:
            orgs[r["id"]]["details"].append("branche éteinte : " + r["raison"])
    # Noms successifs d'une même organisation (infobox, champ fondation) : écrits dans la barre
    for r in lire("noms_successifs.csv"):
        if r["id"] in orgs and int(r["annee"]) >= int(orgs[r["id"]]["t0"]):   # pas avant l'année de la barre
            orgs[r["id"]].setdefault("noms", []).append((t_de(r["annee"]), r["nom"], r["citation"], r["source"]))
    for o in orgs.values():
        if o.get("noms"):
            o["noms"].sort()
            o["details"].append("noms successifs : " + ", ".join(f"{n} ({int(t)})" for t, n, _, _ in o["noms"])
                                + f" ; preuve ({o['noms'][0][3]}) : " + " ; ".join(f"« {c} »" for _, _, c, _ in o["noms"]))
    for r in lire("affiliations.csv"):
        if r["party_id"] in orgs and r["international_id"] in inter:
            orgs[r["party_id"]]["affil"].append(r)
            inter[r["international_id"]]["membres"].append(r["party_id"])
    liens, composantes = [], defaultdict(list)
    for r in lire("liens.csv"):
        if r["source"] in orgs and r["cible"] in orgs:
            liens.append(dict(a=r["source"], b=r["cible"], rel=r["relation"],
                              t=t_de(r["date_evenement"], r["date_evenement_mois"]),
                              preuve=r.get("preuve", ""), citation=r.get("citation", ""),
                              source_cit=r.get("source_citation", ""), inter_nom=r.get("intermediaire_nom", ""),
                              citation2=r.get("citation2", "")))
        elif r["cible"] in orgs and r["relation"] in ("fusion", "renommage", "absorption"):
            composantes[r["cible"]].append(noms_tous.get(r["source"], r["source_nom"]))   # 2.5 : en infobulle
    for q, noms in composantes.items():
        orgs[q]["details"].append("composantes non affichées : " + ", ".join(sorted(set(noms))))
    # Couleurs des Internationales : une par lignée (même chaîne de succession = même couleur)
    def racine(i, vus=None):
        vus = vus or set()
        while inter[i]["pred"] and inter[i]["pred"][0] in inter and i not in vus:
            vus.add(i)
            i = inter[i]["pred"][0]
        return i
    # Internationales dessinées en barres (origines.csv, style = internationale) : même style que les
    # bandes, couleur de leur lignée d'Internationales (l'IO a la couleur de l'IS sous le PS)
    barres_intl = {r["id"]: r.get("internationale", "").strip() for r in lire_manuel("origines.csv")
                   if r.get("style", "").strip() == "internationale" and r["id"] in orgs}
    affichees = sorted({a["international_id"] for o in orgs.values() for a in o["affil"]}
                       | {i for i in barres_intl.values() if i in inter},
                       key=lambda i: (inter[i]["debut"] or "9999", inter[i]["nom"]))
    couleur_lignee = {}
    for i in affichees:
        r_ = racine(i)
        if r_ not in couleur_lignee:
            k = len(couleur_lignee)
            couleur_lignee[r_] = (PALETTE_INTER[k % len(PALETTE_INTER)], k >= len(PALETTE_INTER))
        inter[i]["couleur"], inter[i]["motif"] = couleur_lignee[r_]
    for d in inter.values():
        d.setdefault("couleur", "#BBBBBB")
        d.setdefault("motif", False)
    # Les AIT (1864, anti-autoritaire, 1922), sans Internationale de référence : une couleur commune,
    # la suivante de la palette
    prises = {c for c, _m in couleur_lignee.values()}
    couleur_ait = next((c for c in PALETTE_INTER if c not in prises), "#EE3377")
    for q, i in barres_intl.items():
        orgs[q]["style_intl"] = True
        orgs[q]["intl_ref"] = i if i in inter else ""
        orgs[q]["couleur"] = inter[i]["couleur"] if i in inter else couleur_ait
    # ---------- C1 : les Internationales quittent les voies ----------
    # Les bandeaux d'origines.csv (AIT, AIT anti-autoritaire, IO, IC, AIT 1922) ne sont plus des barres :
    # ils deviennent des entrées de la voie « Internationales » du haut ; leur lien de composante vers
    # leur section (SFIO, PC-SFIC, CNT) devient un ruban sous la section quand aucune adhésion datée
    # n'existe déjà ; leurs liens entre Internationales restent dans la clé et dans la vue par Internationale.
    alias = {}
    for q, i in barres_intl.items():
        o = orgs[q]
        cle = i if i in inter else q
        if cle == q:
            # Addendum 5, C1 : « Première Internationale (AIT) » (origine) et « Association internationale des
            # travailleurs » (Wikidata) sont la même : une seule entrée, l'infobulle nomme les deux identifiants
            base = re.sub(r" \(\d{4}\)$", "", o["etiquette"])
            meme = next((j for j, d in inter.items() if (d["sigle"] or acronyme(d["nom"])) == base
                         and str(d["debut"]) == str(o["an0"]) and str(d["fin"]) == str(o["fin_txt"])), None)
            if meme:
                cle = meme
                inter[cle].update(sigle=o["etiquette"], nom=o["label"], autres_ids=[q])
        if cle not in inter:
            inter[cle] = dict(id=cle, nom=o["label"], sigle=o["etiquette"],
                              debut=str(o["an0"]), fin=str(o["fin_txt"] or ""), pred=[], type_succ="",
                              scissions=[], membres=[], filles=[], couleur=NAVY, motif=False)
        inter[cle]["origine"] = q
        alias[q] = cle
    for l in liens:
        if l["rel"] != "composante" or l["b"] not in alias or l["a"] not in orgs or l["a"] in alias:
            continue
        sec, cle = orgs[l["a"]], alias[l["b"]]
        if any(a_["international_id"] == cle for a_ in sec["affil"]):
            continue
        debut = max(int(sec["an0"]), int(l["t"] or sec["an0"]))
        fin_i = inter[cle]["fin"]
        fin = fin_i if fin_i and (sec["t1"] is None or int(fin_i) <= int(sec["t1"])) else (
            "toujours membre" if sec["t1"] is None else str(int(sec["t1"])))
        sec["affil"].append(dict(party_id=l["a"], international_id=cle, start=str(debut), end=fin,
                                 date_certainty="known", preuve=l["preuve"], citation=l["citation"]))
        inter[cle]["membres"].append(l["a"])
    for q in alias:
        del orgs[q]
    liens = [l for l in liens if l["a"] not in alias and l["b"] not in alias]
    for d in inter.values():                     # C1 : une seule couleur, le marine ; le sigle les distingue
        d["couleur"], d["motif"] = NAVY, False
        d["sigle"] = d["sigle"] or acronyme(d["nom"])
    # Addendum 5, C3 : un sigle d'Internationale déjà pris (par une organisation, ex. OCI, ou une autre
    # Internationale) prend son année de fondation : « OCI (1930) »
    pris = Counter(re.sub(r" \(\d{4}\)$", "", o["etiquette"]) for o in orgs.values())
    pris_i = Counter(d["sigle"] for d in inter.values())
    for d in inter.values():
        if (pris[d["sigle"]] or pris_i[d["sigle"]] > 1) and d["debut"] and not re.search(r"\(\d{4}\)$", d["sigle"]):
            d["sigle"] = f"{d['sigle']} ({d['debut']})"
    # Infobulles : liens (type, preuve, citation complète) et affiliations (dates)
    for l in liens:
        for q, autre, sens in ((l["a"], l["b"], "vers"), (l["b"], l["a"], "depuis")):
            txt = (f"{STYLE_LIEN[l['rel']]['nom']} {sens} {orgs[autre]['etiquette']} ({l['preuve']}) : « {l['citation']} »")
            if l["rel"] == "indirect":
                txt += f" puis « {l['citation2']} » (par {l['inter_nom']})"
            orgs[q]["details"].append(txt)
    # Addendum 5, E1-E2 : une barre au crochet ouvert (aucun ancêtre documenté) vit seulement dans la voie
    # « Sans généalogie documentée » ; sa famille se lit à sa couleur (Place publique, Génération écologie,
    # MEI, Parti pirate). La règle du 16 novembre (voie de la famille, près du parti qui partage une
    # affiliation) est abandonnée.
    for o in orgs.values():
        if o.get("sans_gen"):
            o["voie"] = VOIE_SANS_GEN
            o["details"].append(f"famille {o['famille']} (couleur), aucun ancêtre documenté")
    associee_de = defaultdict(list)       # Internationale -> [(parente, « organisation associée de … »)]
    for p_, d_ in inter.items():
        for f_, rel_ in d_["filles"]:
            if rel_ == "organisation associée":
                associee_de[f_].append((p_, f"organisation associée de {d_['sigle']}"))
    for o in orgs.values():
        for a in o["affil"]:
            d = inter[a["international_id"]]
            dates = f"{a['start']}–{a['end']}" if a["date_certainty"] == "known" else "dates à documenter"
            o["details"].append(f"membre de {d['sigle']} ({d['nom']}) : {dates} ; preuve {a.get('preuve', '')} : "
                                f"« {a.get('citation', '')} »")
            # Lien indirect vers une Internationale, par une organisation associée (Place publique,
            # membre du PSE, organisation associée de l'IS) : dit, jamais dessiné comme une adhésion (R7)
            for p_, f_ in associee_de.get(a["international_id"], []):
                o["details"].append(f"par le {d['sigle']}, lié à {inter[p_]['sigle']} ({inter[p_]['nom']}) : "
                                    f"{d['sigle']} {f_}")
    return orgs, liens, inter, T_AUJ


def ordre_voies(orgs, liens):
    """2.1 : Socialistes, Communistes, Trotskystes côte à côte ; Écologistes et Anarchistes hors de ce
    bloc ; les familles qui partagent des liens (surtout majeurs) le plus près possible."""
    presentes = [f for f in FAMILLES if f != VOIE_SANS_GEN and any(o["voie"] == f for o in orgs.values())]
    en_bas = [VOIE_SANS_GEN] if any(o["voie"] == VOIE_SANS_GEN for o in orgs.values()) else []
    poids = defaultdict(int)
    for l in liens:
        fa, fb = orgs[l["a"]]["voie"], orgs[l["b"]]["voie"]
        if fa != fb:
            poids[frozenset((fa, fb))] += 3 if orgs[l["a"]]["majeure"] and orgs[l["b"]]["majeure"] else 1
    meilleur, cout_min = presentes, None
    for perm in itertools.permutations(presentes):
        pos = {f: i for i, f in enumerate(perm)}
        bloc = sorted(pos[f] for f in BLOC if f in pos)
        if bloc and bloc[-1] - bloc[0] != len(bloc) - 1:
            continue
        if bloc and any(bloc[0] < pos[f] < bloc[-1] for f in DEHORS if f in pos):
            continue
        cout = sum(w * abs(pos[a] - pos[b]) for (a, b), w in ((tuple(k), w) for k, w in poids.items()))
        if cout_min is None or cout < cout_min:
            meilleur, cout_min = list(perm), cout
    return list(meilleur) + en_bas


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
    # Étiquette (2.6) : l'année d'un homonyme (« JCR (1966) ») ne sert à rien quand les dates sont
    # écrites à côté ; sans les dates (barre courte), on la garde seulement si une autre barre
    # dessinée porte le même sigle.
    def base(o):
        m = re.fullmatch(r"(.+) \((\d{4})\)", o["etiquette"])
        return m.group(1) if m and m.group(2) == str(o["an0"]) else o["etiquette"]
    n_base = Counter(base(o) for o in items.values())
    for o in items.values():
        o["x0"] = ech.X(o["t0"])
        if o["t1"] is not None:
            o["x1"] = max(ech.X(o["t1"]), o["x0"] + MIN_W)
            o["x1_vis"] = o["x1"]
        else:
            o["x1"] = max(ech.X(T_AUJ), o["x0"] + MIN_W)
            o["x1_vis"] = o["x1"] + DEGRADE
        o["dates"] = f"{o['an0']}–{o['fin_txt']}"
        b = base(o)
        # Noms successifs : l'étiquette donne le premier nom (SFIC), s'il tient dans la barre
        if o.get("noms") and abs(o["noms"][0][0] - o["t0"]) < 1:
            fin_1 = o["noms"][1][0] if len(o["noms"]) > 1 else (o["t1"] if o["t1"] is not None else T_AUJ)
            place_1 = max(min(ech.X(fin_1), o["x1"]) - o["x0"], 0)      # le premier segment seulement
            c_ = next((c for c in formes_courtes(o["noms"][0][1])
                       if larg(c, FS_SIGLE, True) + 2 * TAG_PAD <= place_1), None)
            if c_ is None:      # premier segment trop court (SFIC, 1920-1921) : son nom au début de la barre
                c_ = next((c for c in formes_courtes(o["noms"][0][1])
                           if larg(c, FS_SIGLE, True) + 2 * TAG_PAD <= o["x1"] - o["x0"]), None)
            if c_:
                b = c_
                o["nom_en_tete"] = True
        long_w = larg(b, FS_SIGLE, True) + 5 + larg(o["dates"], FS) + 2 * TAG_PAD
        seul = b if n_base.get(b, 1) <= 1 else o["etiquette"]
        seul_w = larg(seul, FS_SIGLE, True) + 2 * TAG_PAD
        place = o["x1"] - o["x0"]
        if long_w <= place or seul_w > place:
            # dans la barre avec les dates, ou dehors (dates écrites : elles distinguent les homonymes)
            o["etiq_aff"], o["avec_dates"], o["tag_w"] = b, True, long_w
        else:
            o["etiq_aff"], o["avec_dates"], o["tag_w"] = seul, False, seul_w    # sigle seul, dates en infobulle
        o["tag_dedans"] = o["tag_w"] <= place       # 2.6 : dans la barre si elle est assez longue
        o["tag_pad"] = TAG_PAD
        if not o["tag_dedans"] and larg(seul, FS_SIGLE, True) + 2 <= place:
            # Addendum 5, A1 : le sigle seul tient avec 1 px de marge (PSdF, 1902-1905) : dans la barre,
            # pas en onglet, qui gênerait le départ de ses liens
            o["etiq_aff"], o["avec_dates"], o["tag_w"] = seul, False, larg(seul, FS_SIGLE, True) + 2
            o["tag_dedans"], o["tag_pad"] = True, 1
        # Dernier nom d'une organisation active qui ne tient pas dans son segment (Les Écologistes,
        # 2023) : onglet collé au-dessus de la barre, à la date du changement (addendum 5, A2)
        if o.get("noms") and o["t1"] is None and len(o["noms"]) > 1:
            x_dernier = ech.X(o["noms"][-1][0])
            formes = formes_courtes(o["noms"][-1][1])
            if not any(x_dernier + 4 + larg(f_, FS_SIGLE, True) + 3 <= o["x1"] for f_ in formes):
                f_ = formes[1] if len(formes) > 1 and len(formes[1]) >= 4 else formes[0]
                o["nom_apres"] = (f_, larg(f_, FS_SIGLE, True))
                o["nom_apres_x"] = x_dernier
        # Bandes d'affiliation (2.7) : datées pleines, non datées hachurées sur toute la barre ; 2 au plus
        fin_o = o["t1"] if o["t1"] is not None else T_AUJ
        bandes = []
        for a in o["affil"]:
            d = inter[a["international_id"]]
            connu = a["date_certainty"] == "known" and bool(a["start"])
            if connu:
                ta = max(o["t0"], t_de(a["start"]))
                tb = fin_o if a["end"] in ("", "toujours membre") else min(fin_o, t_de(a["end"]))
                if tb <= ta:
                    connu, ta, tb = False, o["t0"], fin_o
            else:
                ta, tb = o["t0"], fin_o
            if not connu:
                # Période inconnue : hachurée sur la vie commune du parti et de l'Internationale seulement
                # (la SFIO n'est pas membre de l'IS avant 1951, date de naissance de l'IS)
                if d["debut"]:
                    ta = max(ta, t_de(d["debut"]))
                if d["fin"]:
                    tb = min(tb, t_de(d["fin"]))
                if tb <= ta:
                    continue
            xa, xb = max(o["x0"], ech.X(ta)), min(o["x1"], max(ech.X(tb), ech.X(ta) + MIN_W))
            txt = d["sigle"]          # période inconnue : la bande hachurée suffit (voir la légende)
            # C1 : pointe si toujours membre (parti toujours actif), bout coupé sinon
            encore = connu and a["end"] in ("", "toujours membre") and o["t1"] is None
            bandes.append(dict(intl=a["international_id"], connu=connu, xa=xa, xb=xb, couleur=d["couleur"],
                               motif=d["motif"], sigle=d["sigle"], nom=d["nom"], texte=txt, encore=encore,
                               debut=a["start"] if connu else "", fin=a["end"] if connu else "",
                               ecrit=larg(txt, FS, True) + 6 + 2 * MED_R + (FLECHE if encore else 0) <= xb - xa))
        o["bandes"], o["bandes_tooltip"] = bandes, []
        ranger_bandes(o)


def ranger_bandes(o, premier=None):
    """Bandes rangées en lignes (2.7) : des adhésions successives partagent une ligne (SFIO : IO,
    puis UPSAI, puis IOS) ; l'Internationale prolongée par son bandeau (premier) est sur la
    première ligne, dans le prolongement du bandeau. MAX_BANDES lignes, le reste en infobulle."""
    toutes = sorted(o["bandes"] + o["bandes_tooltip"],
                    key=lambda b: (b["intl"] != premier, not b["connu"], b["xa"], -(b["xb"] - b["xa"])))
    lignes, gardees, reste = [], [], []
    for b in toutes:
        k = next((i for i, l in enumerate(lignes)
                  if all(b["xa"] >= c["xb"] - 0.5 or b["xb"] <= c["xa"] + 0.5 for c in l)),
                 len(lignes))
        if k >= MAX_BANDES:
            reste.append(b)
            continue
        if k == len(lignes):
            lignes.append([])
        lignes[k].append(b)
        b["ligne"] = k
        gardees.append(b)
    for b in reste:
        if not b.get("signalee"):
            b["signalee"] = True
            o["details"].append(f"autre affiliation (non dessinée) : {b['sigle']} ({b['nom']})")
    o["bandes"], o["bandes_tooltip"] = gardees, reste
    o["bas"] = BAR_H / 2 + len(lignes) * (BANDE_H + BANDE_GAP)


def etiquette_bande(o, b):
    """Addendum 5, C4 : position (x, largeur) de l'étiquette pleine d'un ruban hachuré ou trop court, ou None.
    Hachuré assez long : sur sa partie gauche ; trop court : à gauche du ruban s'il y a la place sous la
    barre, sinon à droite."""
    if b["ecrit"] and b["connu"]:
        return None
    wb = larg(b["texte"], FS, True) + 6
    autres = [(c["xa"], c["xb"]) for c in o["bandes"] if c is not b and c.get("ligne") == b.get("ligne")]

    def libre(xa_, xb_):
        # ni hors de la barre, ni sur un autre ruban, ni là où un lien quitte la barre (LFI -> L'Après)
        return (o["x0"] - 0.5 <= xa_ and xb_ <= o["x1"] + 0.5 and all(xb_ + 1 <= ca or cb + 1 <= xa_ for ca, cb in autres)
                and not any(xa_ - 4 <= d_ - dx <= xb_ + 4 for d_ in o.get("departs_x", []) for dx in (0, GOUTTIERE)))
    if b["ecrit"]:
        return b["xa"] + 2 * MED_R + 1, wb
    if libre(b["xa"] - wb - 1, b["xa"] - 1):
        return b["xa"] - wb - 1, wb
    if libre(b["xb"] + 1, b["xb"] + wb + 1):
        return b["xb"] + 1, wb
    return None


def y_bande(o, b):
    """Haut d'une bande, relatif au centre de la barre."""
    return BAR_H / 2 + BANDE_GAP + b["ligne"] * (BANDE_H + BANDE_GAP)


def bandeaux(items, liens, ech, T_AUJ):
    """Internationale dessinée (origines.csv, style internationale) : un bandeau au style des bandes,
    seul jusqu'à la naissance de sa section française (composante), puis prolongé par la bande de
    cette Internationale sous la section (IO 1889 puis SFIO, IC 1919 puis PC-SFIC, AIT 1922 puis CNT).
    Sans section : bandeau seul, centré sur sa rangée (AIT, AIT anti-autoritaire)."""
    for o in items.values():
        if o.get("style_intl"):
            o["bandes"], o["bandes_tooltip"] = [], []
            o["strip_haut"] = -BANDE_H / 2
    for l in liens:
        q_i, q_s = l["b"], l["a"]
        if l["rel"] != "composante" or q_i not in items or q_s not in items:
            continue
        o, s = items[q_i], items[q_s]
        if not o.get("style_intl") or o.get("section") or not o["t0"] < s["t0"]:
            continue
        ref = o.get("intl_ref") or q_i
        b = next((x for x in s["bandes"] + s["bandes_tooltip"] if x["intl"] == ref), None)
        if b is None:
            # Pas d'affiliation datée dans les sources (AIT 1922 et CNT) : la bande vient de la
            # composante citée, de son année à la fin de l'une ou de l'autre
            fin_s = s["t1"] if s["t1"] is not None else T_AUJ
            fin_o = o["t1"] if o["t1"] is not None else T_AUJ
            ta = max(s["t0"], l["t"] or s["t0"])
            tb = min(fin_s, fin_o)
            xa = max(s["x0"], ech.X(ta))
            xb = min(s["x1"], max(ech.X(tb), xa + MIN_W))
            txt = re.sub(r" \(\d{4}\)$", "", o["etiquette"])
            b = dict(intl=ref, connu=True, xa=xa, xb=xb, couleur=o["couleur"], motif=False, sigle=txt,
                     nom=o["label"], texte=txt, debut=str(int(ta)),
                     fin="aujourd'hui" if tb >= T_AUJ else str(int(tb)), ecrit=larg(txt, FS, True) + 6 <= xb - xa)
            s["bandes"].append(b)
        ranger_bandes(s, premier=ref)
        b["prolonge"] = q_i                 # cette bande prolonge le bandeau : dessinés d'un seul tenant
        o["section"] = SECTION_DE[q_i] = q_s
        o["strip_haut"] = BAR_H / 2 + BANDE_GAP
        # Le bandeau va jusqu'au début de la bande (PC-SFIC : fin 1920, bande de l'IC en 1921)
        o["strip_x1"] = max(s["x0"], b["xa"]) if b in s["bandes"] else s["x0"]
        o["t1"], o["x1"], o["x1_vis"] = s["t0"], s["x0"], s["x0"]
    for o in items.values():
        if not o.get("style_intl"):
            continue
        o.setdefault("strip_x1", o["x1"])
        o["bas"] = o["strip_haut"] + BANDE_H
        # Étiquette au style des bandes : sigle (et dates si elles tiennent) dans le bandeau, sinon devant
        b_ = re.sub(r" \(\d{4}\)$", "", o["etiquette"])
        place = o["strip_x1"] - o["x0"]
        long_w = larg(b_, FS, True) + 5 + larg(o["dates"], FS) + 6
        seul_w = larg(b_, FS, True) + 6
        o["etiq_aff"], o["avec_dates"], o["tag_w"] = (b_, True, long_w) if long_w <= place else (b_, False, seul_w)
        o["tag_dedans"] = o["tag_w"] <= place
        # Bandeau collé trop court pour son sigle (IC 1919-1921) : pas d'étiquette devant (elle
        # boucherait le couloir des liens qui arrivent à la section) ; la bande qui le prolonge
        # porte le même sigle, le nom est dans l'infobulle
        o["sans_tag"] = bool(o.get("section")) and not o["tag_dedans"]
        if o["sans_tag"]:
            o["tag_dedans"], o["tag_w"] = True, 0


def avec_ancetres_inter(ids, inter):
    """Ajoute les Internationales ancêtres (succession, scission, parente saisie à la main) des
    Internationales données : la famille de la QI reste d'un seul tenant (QI, CIQI, LIT-QI...)."""
    parents = defaultdict(set)
    for p_, d_ in inter.items():
        for f_, _rel in d_["filles"]:
            parents[f_].add(p_)
    for i_, d_ in inter.items():
        parents[i_] |= {x for x in d_["pred"] + d_["scissions"] if x in inter}
    res, pile = set(ids), list(ids)
    while pile:
        x = pile.pop()
        for p_ in parents.get(x, ()):
            if p_ not in res and not RX_EUROPEEN.search(inter[p_]["nom"]):
                res.add(p_)
                pile.append(p_)
    return res


def voie_internationales(items, inter, ech, T_AUJ, avec_origines=True):
    """C1 : voie « Internationales » en haut. Une entrée par Internationale affichée (au moins un
    membre dessiné, ou une origine d'origines.csv) : médaillon rond, puis ruban sur sa vie, terminé
    par une pointe si elle existe toujours, coupé net sinon ; début inconnu : hachuré en tirets.
    Le sigle (et le nom, les dates s'ils tiennent) est dans le ruban, sinon dans un onglet collé
    au-dessus de son début (comme C3)."""
    # Partis, alliances et groupes européens (PSE, PGE, PVE...) : pas des Internationales ; ils restent
    # en rubans sous les barres de leurs membres, hors de la voie du haut
    ids = {b["intl"] for o in items.values() for b in o["bandes"] + o["bandes_tooltip"]
           if not RX_EUROPEEN.search(inter[b["intl"]]["nom"])}
    if avec_origines:
        ids |= {i for i, d in inter.items() if d.get("origine")}
    ids = avec_ancetres_inter(ids, inter)     # Internationales sans membre dessiné qui relient une famille
    entrees = []
    for i in ids:
        d = inter[i]
        membres = [b for o in items.values() for b in o["bandes"] + o["bandes_tooltip"] if b["intl"] == i]
        connu = bool(d["debut"])
        t0 = t_de(d["debut"]) if connu else None
        if not connu and not membres:
            # Ni date ni membre (LIT-QI) : au début de sa première fille datée, sinon pas dans la voie
            filles_x = [ech.X(t_de(inter[f]["debut"])) for f, _ in d["filles"] if inter[f]["debut"]]
            if not filles_x:
                continue
            xa = min(filles_x) - 2 * MED_R - 30
        else:
            xa = ech.X(t0) if connu else min(b["xa"] for b in membres)
        en_vie = not d["fin"]
        xb = ech.X(t_de(d["fin"])) if d["fin"] else ech.X(T_AUJ)
        xb = max(xb, xa + 2 * MED_R + 4)
        dates = f"{d['debut'] or '?'}–{d['fin'] or ''}"
        r = INTL_RUBAN / 2 + 2
        place = xb - (xa + 2 * r + 4) - (FLECHE if en_vie else 0)
        textes = [f"{d['sigle']}  {d['nom']}  {dates}", f"{d['sigle']}  {dates}", d["sigle"]]
        txt = next((t for t in textes if larg(t, FS, True) + 4 <= place), None)
        onglet = txt is None
        if onglet:
            txt = d["sigle"]
        w_txt = larg(txt, FS, True)
        droite = max(xb + (FLECHE if en_vie else 0), xa + w_txt + 8 if onglet else 0)
        entrees.append(dict(id=i, sigle=d["sigle"], nom=d["nom"], dates=dates, xa=xa, xb=xb, en_vie=en_vie,
                            connu=connu, texte=txt, onglet=onglet, w_txt=w_txt, L=xa - 2, R=droite,
                            membres=sorted({o["etiquette"] for o in items.values()
                                            for b in o["bandes"] + o["bandes_tooltip"] if b["intl"] == i})))
    entrees.sort(key=lambda e: (e["xa"], e["sigle"]))
    lignes = []
    for e in entrees:
        k = next((k for k, l in enumerate(lignes) if all(e["L"] >= f["R"] + GAP or e["R"] + GAP <= f["L"] for f in l)),
                 len(lignes))
        if k == len(lignes):
            lignes.append([])
        lignes[k].append(e)
        e["ligne"] = k
    # Hauteur de chaque ligne : le ruban, plus l'onglet si une entrée de la ligne en a un
    y = VOIE_PAD + 22                     # place du titre de la voie
    for l in lignes:
        h = INTL_LIGNE + (INTL_ONGLET if any(e["onglet"] for e in l) else 0)
        for e in l:
            e["y_rel"] = y + h - (INTL_LIGNE - INTL_RUBAN) / 2 - INTL_RUBAN / 2   # centre du ruban
        y += h
    ech.intl_h = (y + VOIE_PAD) if lignes else 0
    return entrees


def mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues=None, titre=""):
    ordre_complet = ordre_voies(orgs, liens)
    voies_ordre = [v for v in ordre_complet if not voies_voulues or v in voies_voulues]
    items = {q: dict(o, details=list(o["details"])) for q, o in orgs.items() if o["voie"] in voies_ordre}
    ech = Echelle([o["t0"] for o in items.values()], T_AUJ)
    rang_voie = {v: i for i, v in enumerate(voies_ordre)}
    preparer(items, inter, ech, T_AUJ)
    bandeaux(items, liens, ech, T_AUJ)
    intl_entrees = voie_internationales(items, inter, ech, T_AUJ, avec_origines=not voies_voulues)
    for l in liens:
        l["x_t"] = ech.X(l["t"])
    # Origines historiques (data/manuel/origines.csv) : leurs liens sont toujours dessinés, quelle que
    # soit leur longueur (exception voulue, ex. AIT -> AIT anti-autoritaire)
    origines = {r["id"] for r in lire_manuel("origines.csv")}
    def majeur(l):
        if l["rel"] == "composante":
            return False
        if items[l["a"]]["majeure"] and items[l["b"]]["majeure"]:
            return True
        # Lien d'une origine : forcé seulement s'il reste sous le seuil d'années (AIT -> AIT 1922, qui
        # partirait de 1876, reste un renvoi écrit)
        a = items[l["a"]]
        depart = min(l["t"], a["t1"]) if a["t1"] is not None else l["t"]
        if l.get("preuve") == "manuel" and l["rel"] in ("indirect", "passage") and FORCER_MANUELS                 and l["t"] - depart <= SEUIL_ANNEES:
            return True             # lien pointillé saisi à la main à la demande (PSOP -> Voix ouvrière)
        return (bool({l["a"], l["b"]} & origines) and l["rel"] != "filiation_idéologique"
                and l["t"] - depart <= SEUIL_ANNEES)
    # Un lien qui part pendant la zone de l'étiquette (scission peu après la fondation) : l'étiquette
    # passe juste avant la barre, pour que le départ et son cercle restent à la date exacte (2.4, 2.6).
    # Addendum 5, A1-A2 : le texte reste dans la barre, décalé juste après ces départs ; s'il ne tient
    # plus, l'étiquette devient un onglet collé au-dessus du début de la barre (jamais avant ni après).
    departs_de, marques_de = defaultdict(list), defaultdict(list)
    for l in liens:
        if l["rel"] not in ("absorption", "composante") and l["a"] in items and l["b"] in items:
            departs_de[l["a"]].append(ech.X(l["t"]))
            if l["rel"] == "scission":          # seule la scission porte une marque (losange) sur la barre
                marques_de[l["a"]].append(ech.X(l["t"]))
    for q, a in items.items():
        a["departs_x"] = departs_de.get(q, [])     # aussi pour l'étiquette des rubans (etiquette_bande)
        a["tag_decal"] = 0.0
        if not a["tag_dedans"]:
            continue
        # Le texte avance par-delà chaque losange qu'il couvrirait (FTSF : 1879, puis 1882) ; une fusion
        # ou un renommage, sans marque, part du bord de la barre et ne le gêne pas (PSdF -> SFIO)
        xt = a["x0"]
        while True:
            genants = [x for x in marques_de.get(q, []) if xt - 5 <= x <= xt + a["tag_w"] + 5]
            if not genants:
                break
            xt = max(genants) + 6
        if xt + a["tag_w"] <= a["x1"]:
            a["tag_decal"] = xt - a["x0"]
        else:
            a["tag_dedans"] = False

    # Continuation (2.4) : renommage dans la même voie, le successeur commence où finit le prédécesseur.
    # L'étiquette du successeur doit tenir dans sa barre (2.6 : jamais entre la fin et la suite).
    par_cible, par_source = defaultdict(list), defaultdict(list)
    for l in liens:
        par_cible[l["b"]].append(l)
        par_source[l["a"]].append(l)
    # Barre encore active, trop courte pour son étiquette et sans lien qui en part : l'étiquette
    # passe après la barre (après aujourd'hui, où rien ne suit), ex. NPA-A, L'Après. Elle ne gêne
    # alors ni les liens qui arrivent ni une continuation (2.6).
    for o in items.values():
        o["tag_apres"] = False             # addendum 5, A2 : jamais après la fin de la barre
    continuations = set()
    for l in liens:
        a, b = items.get(l["a"]), items.get(l["b"])
        if not (a and b and l["rel"] == "renommage" and a["voie"] == b["voie"] and a["t1"] is not None
                and 0 <= b["x0"] - a["x1"] < GAP
                and sum(1 for x in par_source[l["a"]] if x["rel"] == "renommage") == 1):
            continue
        continuations.add((l["a"], l["b"]))   # onglet au-dessus du début du successeur : rien ne gêne
    # Bandeau d'Internationale et sa section : même rangée, la bande de la section le prolonge
    suites_intl = {(q, o["section"]) for q, o in items.items() if o.get("section") in items}
    continuations |= suites_intl

    collages_tous = [(l["a"], l["b"]) for l in liens if l["rel"] == "composante" and l["a"] in items and l["b"] in items]

    def collages_actifs():
        """Composantes à garder voisines ; celle d'une section et de son bandeau ne compte pas tant
        qu'ils sont sur la même rangée (continuation), elle revient sinon."""
        return [c for c in collages_tous if (c[1], c[0]) not in continuations]
    # Unifications : organisations nées de la fusion d'au moins trois composantes la même année (SFIO 1905)
    n_fondatrices = Counter(l["b"] for l in liens if l["rel"] in ("fusion", "renommage") and l["a"] in items
                            and l["b"] in items and items[l["a"]]["t1"] is not None
                            and abs(items[l["a"]]["t1"] - items[l["b"]]["t0"]) <= 1.01   # PSR : fin 1901, PSdF 1902
                            and abs(l["t"] - items[l["b"]]["t0"]) < 1)
    force, anomalies, traces = set(), [], []
    for _tour in range(4):
      for _ in range(30):
          poly, renvois = [], []
          for l in liens:
              a, b = items.get(l["a"]), items.get(l["b"])
              if a is None and b is None:
                  continue
              if a is None or b is None:
                  renvois.append(dict(l, raison="hors de cette vue"))
                  continue
              if (l["a"], l["b"]) in continuations or (l["b"], l["a"]) in continuations:
                  continue
              ev = abs(rang_voie[a["voie"]] - rang_voie[b["voie"]])
              t_dep = min(l["t"] - GOUTTIERE / PPA, a["t1"] if a["t1"] is not None else T_AUJ)
              # Addendum 5, D1 : une composante (membre de, sans fusion) n'est jamais un trait : renvoi
              if l["rel"] == "composante":
                  renvois.append(dict(l, raison="composante"))
                  continue
              # Composante d'une unification (au moins trois composantes la même année : POF, PSR, ACR -> PSdF
              # en 1902 ; PSdF, PSF, POSR -> SFIO en 1905) : la source finit l'année où la cible naît, dans la
              # même voie ; toujours dessinée (signalé par l'utilisateur)
              fondatrice = (l["rel"] in ("fusion", "renommage") and ev == 0
                            and a["t1"] is not None and abs(a["t1"] - b["t0"]) <= 1.01 and abs(l["t"] - b["t0"]) < 1
                            and n_fondatrices.get(l["b"], 0) >= 3)      # unification (SFIO 1905), pas toute fusion
              if (majeur(l) or fondatrice) and not voies_voulues:
                  poly.append(dict(l, majeur=True))         # 2.5 : jamais en renvoi
              elif ev > SEUIL_VOIES or l["t"] - t_dep > SEUIL_ANNEES or (l["a"], l["b"]) in force:
                  renvois.append(dict(l, raison="trop long ou croisement"))
              else:
                  poly.append(dict(l, majeur=False))
          renvoyer(items, orgs, renvois)
          bornes(items, poly)
          rangees = placer(items, voies_ordre, poly, continuations, collages_actifs(),
                           souhaits=[r for r in renvois if r.get("raison") == "trop long ou croisement"])
          # Continuations qui n'ont pas pu rester sur la même rangée, ou dont le successeur porte des
          # renvois (ils seraient entre la fin et la suite) : lien dessiné normal
          # (un bandeau, sous le niveau de la barre, ne gêne pas les renvois de sa section)
          def renvois_genent(a, b):
              """Renvois de la section entre la fin et la suite ; pour un bandeau (plus bas que les
              renvois), seulement s'ils touchent ceux du bandeau lui-même."""
              if not items[b]["renv"]:
                  return False
              return (a, b) not in suites_intl
          ratees = {(a, b) for a, b in continuations
                    if items[a]["rang_g"] != items[b]["rang_g"] or renvois_genent(a, b)}
          if ratees:
              continuations -= ratees
              continue
          geo = ordonnees(items, voies_ordre, rangees, ech)
          boites = boites_obstacles(items)
          traces, anomalies, a_forcer = [], [], set()
          for l in poly:
              t = router(l, items, boites, rang_voie, poly)
              if t is None:
                  anomalies.append((l["a"], l["b"], l["rel"], items[l["a"]]["an0"], items[l["b"]]["an0"],
                                    "impossible à dessiner vers la droite (dates trop proches ou cible trop courte)"))
                  a_forcer.add((l["a"], l["b"]))
                  continue
              trop_loin = t["rangs"] > SEUIL_RANGS and not l["majeur"]
              if (t["croisements"] or trop_loin) and not l["majeur"]:
                  a_forcer.add((l["a"], l["b"]))
              traces.append(t)
          if not a_forcer - force:
              break
          force |= a_forcer
      traces = [t for t in traces if (t["a"], t["b"]) not in force or t["majeur"]]
      if voies_voulues or not any(t["croisements"] for t in traces):
          break
      geo = optimiser(items, voies_ordre, rangees, poly, ech, rang_voie)
      boites = boites_obstacles(items)
      traces = [t for t in (router(l, items, boites, rang_voie, poly) for l in poly) if t]
      # Liens mineurs devenus fautifs (croisement, plus de 6 rangées) : renvois, et on recommence
      fautifs = {(t["a"], t["b"]) for t in traces if not t["majeur"] and (t["croisements"] or t["rangs"] > SEUIL_RANGS)}
      if not fautifs - force:
          break
      force |= fautifs
    if not voies_voulues:
        poly, renvois, geo = repecher(items, orgs, voies_ordre, rangees, poly, renvois, ech, rang_voie, collages_actifs(),
                                     continuations)
        boites = boites_obstacles(items)
        traces = [t for t in (router(l, items, boites, rang_voie, poly) for l in poly) if t]
    cle = cle_donnees(items, inter)
    largeur = max([o["R"] for o in items.values()] + [ech.X(ech.T1)]) + 40
    return dict(items=items, traces=traces, renvois=renvois, continuations=continuations, ech=ech, T_AUJ=T_AUJ,
                intl_entrees=intl_entrees,
                largeur=largeur, cle=cle, inter=inter, titre=titre, anomalies=anomalies,
                rels=sorted({t["rel"] for t in traces} | ({"renommage"} if continuations else set())), **geo)


def bornes(items, poly):
    """Emprise horizontale de chaque barre : couloir d'arrivée, étiquette avant la barre, renvois."""
    entrants = defaultdict(list)
    for l in poly:
        if l["rel"] not in ("absorption", "composante"):
            entrants[l["b"]].append(l)
    for o in items.values():
        o["gauche_lien"] = (GOUTTIERE + 6) if entrants.get(o["id"]) else 0
        gauche = o["x0"] - o["gauche_lien"]
        o["onglet"] = not o["tag_dedans"] and not o.get("sans_tag")
        o["tag_x"] = o["x0"] + (o.get("tag_decal", 0) if o["tag_dedans"] else 0)
        bord = gauche
        o["renv_x"] = bord - o["w_renv"]
        o["L"] = min(bord, o["renv_x"]) - 1
        o["R"] = max(o["x1_vis"], o["x0"] + (o["tag_w"] if o["onglet"] else 0)) + 1
        if o.get("nom_apres"):
            # dernier nom qui ne tient pas dans son segment : onglet au-dessus, à la date du changement
            o["R"] = max(o["R"], o["nom_apres_x"] + o["nom_apres"][1] + 2 * TAG_PAD + 1) if o.get("nom_apres_x") else o["R"]


def renumeroter(items, voies_ordre, rangees):
    g = 0
    for v in voies_ordre:
        if v not in rangees:
            continue
        for r, contenu in enumerate(rangees[v]["rangees"]):
            for q in contenu:
                items[q]["rang_g"], items[q]["rang_l"] = g + r, r
        g += len(rangees[v]["rangees"])


def repecher(items, orgs, voies_ordre, rangees, poly, renvois, ech, rang_voie, collages=(), continuations=(),
             budget=150):
    """Avant de laisser un lien en renvoi écrit, on essaie de le dessiner : tel quel, puis en
    déplaçant une de ses deux barres vers une rangée voisine de l'autre (dans une rangée où elle
    tient, ou une nouvelle rangée). Un essai n'est gardé que si tous les liens dessinés restent sans
    croisement et sous le seuil de rangées. Les composantes (PG et LFI...) passent en premier."""
    import time
    debut = time.time()

    suites = set(continuations)
    # Bandeau d'Internationale et sa section : ils bougent ensemble (la section n'est pas figée)
    compagnon = {}
    for a_, b_ in suites:
        if items[a_].get("style_intl"):
            compagnon[a_], compagnon[b_] = b_, a_
    dans_suite = {q for c in suites for q in c} - set(compagnon)

    def chevauchement():
        for v in voies_ordre:
            for contenu in rangees.get(v, {}).get("rangees", []):
                # bandeau et section sur la même rangée : un seul bloc (le bandeau finit où elle commence)
                bs = sorted((min([items[q]["L"]] + [items[c]["L"] for c in [compagnon.get(q)] if c in contenu]),
                             items[q]["R"], q) for q in contenu
                            if not (items[q].get("style_intl") and compagnon.get(q) in contenu))
                for b1, b2 in zip(bs, bs[1:]):
                    if (b1[2], b2[2]) in suites:          # suite collée : commence où l'autre finit
                        if items[b1[2]]["x1"] > items[b2[2]]["x0"] + 0.5:
                            return True
                    elif b1[1] + GAP > b2[0]:
                        return True
        return False

    def valide(p2):
        renumeroter(items, voies_ordre, rangees)
        geo = ordonnees(items, voies_ordre, rangees, ech)
        boites = boites_obstacles(items)
        for l in p2:
            t = router(l, items, boites, rang_voie, p2)
            if t is None or t["croisements"] or (not l["majeur"] and (
                    t["rangs"] > SEUIL_RANGS or t["annees"] > SEUIL_ANNEES or t["voies"] > SEUIL_VOIES)):
                return None
        return geo

    renumeroter(items, voies_ordre, rangees)
    geo = ordonnees(items, voies_ordre, rangees, ech)
    cands = [r for r in renvois if r.get("raison") == "trop long ou croisement"
             and r["a"] in items and r["b"] in items
             and abs(rang_voie[items[r["a"]]["voie"]] - rang_voie[items[r["b"]]["voie"]]) <= SEUIL_VOIES]
    cands.sort(key=lambda r: (r["rel"] != "composante", abs(items[r["a"]]["rang_g"] - items[r["b"]]["rang_g"])))
    for l in cands:
        if time.time() - debut > budget:
            break
        p2 = poly + [dict(l, majeur=False)]
        r2 = [r for r in renvois if r is not l]
        def options_barre(q, autre):
            if q in dans_suite:                  # une suite ne se sépare pas de son prédécesseur
                return []
            v = items[q]["voie"]
            lignes = rangees[v]["rangees"]
            if items[autre]["voie"] == v:
                ra = next(i for i, c in enumerate(lignes) if autre in c)
                return [(q, "dans", r) for r in (ra - 1, ra + 1) if 0 <= r < len(lignes)] +                        [(q, "nouvelle", r) for r in (ra, ra + 1)]
            haut = voies_ordre.index(items[autre]["voie"]) < voies_ordre.index(v)
            return [(q, "dans", 0 if haut else len(lignes) - 1), (q, "nouvelle", 0 if haut else len(lignes))]

        def bouger_barre(q, sorte, r):
            lignes = rangees[items[q]["voie"]]["rangees"]
            r0 = next(i for i, c in enumerate(lignes) if q in c)
            if sorte == "dans" and (r == r0 or r >= len(lignes)):
                return False
            groupe = [q] + ([compagnon[q]] if compagnon.get(q) in lignes[r0] else [])
            for x in groupe:
                lignes[r0].remove(x)
            if sorte == "dans":
                lignes[r].extend(groupe)
            else:
                lignes.insert(min(r, len(lignes)), groupe)
            lignes[:] = [c for c in lignes if c]
            return True

        def rangs_du_bloc(q, p_):
            """Rangées du groupe d'organisations reliées à q (liens dessinés et composantes de sa voie),
            si elles sont contiguës."""
            v = items[q]["voie"]
            adj = defaultdict(set)
            for x in p_:
                if items[x["a"]]["voie"] == v == items[x["b"]]["voie"]:
                    adj[x["a"]].add(x["b"]); adj[x["b"]].add(x["a"])
            for x, y in list(collages) + list(suites):
                if items[x]["voie"] == v == items[y]["voie"]:
                    adj[x].add(y); adj[y].add(x)
            comp, pile = set(), [q]
            while pile:
                x = pile.pop()
                if x not in comp:
                    comp.add(x)
                    pile.extend(adj[x])
            lignes = rangees[v]["rangees"]
            rs = sorted({i for i, c in enumerate(lignes) if set(c) & comp})
            if rs != list(range(rs[0], rs[-1] + 1)) or any(set(lignes[i]) - comp for i in rs):
                return None
            return rs

        def options_bloc(q, autre):
            """Déplacer tout le groupe de q contre le groupe de l'autre extrémité (ou en haut / en bas
            de la voie, si l'autre est dans une autre voie)."""
            v = items[q]["voie"]
            rq = rangs_du_bloc(q, poly)
            if not rq:
                return []
            if items[autre]["voie"] != v:
                haut = voies_ordre.index(items[autre]["voie"]) < voies_ordre.index(v)
                return [(v, rq, "haut" if haut else "bas", None)]
            ra = rangs_du_bloc(autre, poly)
            if not ra or set(ra) & set(rq):
                return []
            return [(v, rq, "avant", autre), (v, rq, "apres", autre)]

        def bouger_bloc(v, rq, ou, autre):
            lignes = rangees[v]["rangees"]
            bloc = [lignes[i] for i in rq]
            reste = [c for i, c in enumerate(lignes) if i not in set(rq)]
            if ou == "haut":
                k = 0
            elif ou == "bas":
                k = len(reste)
            else:
                ia = [i for i, c in enumerate(reste) if autre in c][0]
                ra = rangs_du_bloc(autre, poly)
                deb = ia - (next(i for i, r in enumerate(ra) if autre in lignes[r]))
                k = deb if ou == "avant" else deb + len(ra)
            lignes[:] = reste[:k] + bloc + reste[k:]
            return True

        def essayer():
            renvoyer(items, orgs, r2)
            bornes(items, p2)
            return None if chevauchement() else valide(p2)

        trouve = None
        avant = [None] + [b for q, autre in ((l["a"], l["b"]), (l["b"], l["a"])) for b in options_bloc(q, autre)]
        for pre in avant:
            if trouve is not None or time.time() - debut > budget:
                break
            sauvegarde = {v: [list(c) for c in rangees[v]["rangees"]] for v in rangees}
            if pre:
                bouger_bloc(*pre)
            etat = {v: [list(c) for c in rangees[v]["rangees"]] for v in rangees}
            barres = [None] + [o for q, autre in ((l["a"], l["b"]), (l["b"], l["a"])) for o in options_barre(q, autre)]
            for essai in barres:
                if essai and not bouger_barre(*essai):
                    continue
                g2 = essayer()
                if g2 is not None:
                    trouve = g2
                    break
                for v, ls in etat.items():
                    rangees[v]["rangees"][:] = [list(c) for c in ls]
            if trouve is None:
                for v, ls in sauvegarde.items():
                    rangees[v]["rangees"][:] = ls
        if trouve is not None:
            poly, renvois, geo = p2, r2, trouve
        renvoyer(items, orgs, renvois)
        bornes(items, poly)
    renumeroter(items, voies_ordre, rangees)
    geo = ordonnees(items, voies_ordre, rangees, ech)
    return poly, renvois, geo


def renvoyer(items, orgs, renvois):
    """Renvois (2.5) : petits textes avant le début de la barre ; plus de 3 : un « voir aussi »."""
    for o in items.values():
        o["renv"] = []
    for r in renvois:
        a, b = items.get(r["a"]), items.get(r["b"])
        if a is not None:
            cible = b or orgs[r["b"]]
            a["renv"].append((f"{RENVOI_SORTANT.get(r['rel'], '→')} {cible['etiquette']}", r["a"], r["b"]))
        if b is not None:
            src = a or orgs[r["a"]]
            b["renv"].append((f"{RENVOI_MOT.get(r['rel'], 'issu de')} {src['etiquette']}", r["a"], r["b"]))
    for o in items.values():
        o["voir_aussi"] = []
        if len(o["renv"]) > MAX_RENVOIS:
            o["voir_aussi"] = list(o["renv"])
            o["renv"] = [(f"voir aussi ({len(o['voir_aussi'])})", "", "")]
        o["w_renv"] = sum(larg(t, FS) + 6 for t, *_ in o["renv"])


FORCER_MANUELS = False      # forcer les liens pointillés saisis à la main : coûte 19 liens tracés (mesuré), désactivé
MODE_SOUHAITS = "rang"      # renvois de la même voie : "blocs", "rang" (blocs et rangée préférée) ou "tout"


def placer(items, voies_ordre, poly, continuations, collages=(), souhaits=()):
    """Rangées (2.2, 2.3) : un bloc contigu par arbre, placé en profondeur, enfants du plus récent au
    plus ancien ; une rangée est choisie d'abord pour ne créer aucun croisement. Barres à renvois
    seuls en bas de la voie, sans écart supplémentaire."""
    voisins, parents = defaultdict(set), defaultdict(list)
    # Souhaits : liens de la même voie restés en renvoi. Ils comptent pour grouper et rapprocher les
    # barres (sans quoi le groupe guesdiste, coupé de la FTSF, part en bas de la voie et ses liens
    # ne peuvent plus jamais être dessinés).
    souhaits = [l for l in souhaits if l["a"] in items and l["b"] in items
                and items[l["a"]]["voie"] == items[l["b"]]["voie"] and l["rel"] != "composante"]
    for l in list(poly) + souhaits:
        a, b = items[l["a"]], items[l["b"]]
        if a["voie"] == b["voie"]:
            voisins[l["a"]].add(l["b"])
            voisins[l["b"]].add(l["a"])
        if l in souhaits and MODE_SOUHAITS == "blocs":
            continue
        parents[l["b"]].append(l)
    for a, b in continuations:
        voisins[a].add(b)
        voisins[b].add(a)
    for q, o in items.items():           # affinité sans lien (Place publique près du PS)
        if o.get("affinite") in items and items[o["affinite"]]["voie"] == o["voie"]:
            voisins[q].add(o["affinite"])
            voisins[o["affinite"]].add(q)
    # Composantes (PG dans LFI...) : toujours voisines, même quand leur trait n'a pas encore pu être
    # dessiné ; sans cela, l'abandon du trait les éloigne et il ne peut plus jamais être dessiné.
    deja = {(l["a"], l["b"]) for l in poly}
    for a, b in collages:
        if items[a]["voie"] == items[b]["voie"]:
            voisins[a].add(b)
            voisins[b].add(a)
            if (a, b) not in deja:
                parents[b].append(dict(a=a, b=b, rel="composante"))
    cont_parent = {b: a for a, b in continuations if not items[a].get("style_intl")}
    bandeau_de_section = {b: a for a, b in continuations if items[a].get("style_intl")}
    section_du = {a: b for b, a in bandeau_de_section.items()}
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
        # Ordre des arbres dans la voie : ceux qui sont reliés à la voie du dessus en haut, ceux qui
        # sont reliés à la voie du dessous en bas (moins de rangées traversées, moins de croisements).
        iv = voies_ordre.index(v)

        def sens_vertical(bloc):
            s = 0
            for l in poly:
                for x, y in ((l["a"], l["b"]), (l["b"], l["a"])):
                    if x in bloc and items[y]["voie"] != v:
                        s += 3 if voies_ordre.index(items[y]["voie"]) > iv else -3
            return s
        blocs.sort(key=lambda bl: (sens_vertical(bl), items[bl[0]]["x0"]))
        if seuls:
            blocs.append([q for s in seuls for q in s])
        rangees, debuts = [], set()
        for bloc in blocs:
            debut = len(rangees)
            debuts.add(debut)
            local, segments = [], []
            for q in bloc:                       # aucune rangée héritée d'un passage précédent
                items[q].pop("rang_l", None)
                items[q].pop("bloc_v", None)
            enfants_v = defaultdict(list)
            for l in list(poly) + (souhaits if MODE_SOUHAITS == "tout" else []):
                if l["a"] in bloc and l["b"] in bloc:
                    enfants_v[l["a"]].append(l["b"])
            for a_, b_ in list(continuations) + [c for c in collages if (c[0], c[1]) not in deja]:
                if a_ in bloc and b_ in bloc:
                    enfants_v[a_].append(b_)
            dans = set(bloc)
            racines = [q for q in bloc if not any(q in enfants_v[p] for p in dans)] or bloc[:1]
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
            # Affinité sans lien (Place publique) : rangée juste après son parti (le PS), avant ses enfants
            for q in [q for q in ordre if items[q].get("affinite") in dans]:
                ordre.remove(q)
                ordre.insert(ordre.index(items[q]["affinite"]) + 1, q)
            # Bandeau d'Internationale : rangé juste après sa section, à sa gauche sur la même rangée
            # (la section garde la place que lui donnent ses propres ancêtres)
            ordre = [q for q in ordre if not (q in bandeau_de_section.values() and section_du[q] in dans)]

            def occupe(r, x):
                return any(l2 - 0.5 < x < r2 + 0.5 for l2, r2, _ in local[r])

            def cout(o, r):
                c = 0
                for l in parents[o["id"]]:
                    p = items[l["a"]]
                    if p.get("bloc_v") != (v, debut) or "rang_l" not in p:
                        continue
                    x = o["x0"] - GOUTTIERE
                    h, b = sorted((p["rang_l"], r))
                    c += sum(1 for rr in range(h + 1, b) if occupe(rr, x))
                    if abs(p["rang_l"] - r) > SEUIL_RANGS:
                        c += 1
                c += sum(1 for x, h, b in segments if h < r < b and o["L"] - 0.5 < x < o["R"] + 0.5)
                return c

            def libre(r, L, R, sauf=None):
                for l2, r2, q2 in local[r]:
                    if q2 == sauf and L >= items[q2]["x1"] - 1.5:     # suite collée : L = x0 - 1
                        continue
                    if not (R + GAP <= l2 or r2 + GAP <= L):
                        return False
                return True
            for q in ordre:
                o = items[q]
                o.pop("rang_l", None)
                o["bloc_v"] = (v, debut)
                place = None
                p = cont_parent.get(q)
                if p and "rang_l" in items[p] and items[p].get("bloc_v") == (v, debut) \
                        and libre(items[p]["rang_l"], o["x0"] - 1, o["R"], sauf=p):
                    place = items[p]["rang_l"]
                if place is None:
                    prefs = [items[l["a"]]["rang_l"] for l in parents[q]
                             if items[l["a"]].get("bloc_v") == (v, debut) and "rang_l" in items[l["a"]]]
                    aff = items.get(o.get("affinite") or "", {})
                    if not prefs and aff.get("bloc_v") == (v, debut) and "rang_l" in aff:
                        prefs = [aff["rang_l"]]     # affinité sans lien : au plus près de ce parti
                    pref = prefs[0] + 1 if prefs else 0
                    candidats = [r for r in range(len(local)) if libre(r, o["L"], o["R"])] + [len(local)]
                    while len(local) < candidats[-1] + 1:
                        local.append([])
                    place = min(candidats, key=lambda r: (cout(o, r), abs(r - pref), r < pref))
                if place == len(local):
                    local.append([])
                L_eff = o["x0"] - 1 if p and place == items.get(p, {}).get("rang_l") else o["L"]
                local[place].append((L_eff, o["R"], q))
                o["rang_l"] = place
                i_ = bandeau_de_section.get(q)
                if i_ in dans:
                    oi = items[i_]
                    oi.pop("rang_l", None)
                    oi["bloc_v"] = (v, debut)
                    if all(oi["R"] + GAP <= l2 or r2 + GAP <= oi["L"] for l2, r2, q2 in local[place] if q2 != q)                             and oi["R"] <= o["x0"] + 1.5:
                        r_i = place
                    else:
                        r_i = min([r for r in range(len(local)) if libre(r, oi["L"], oi["R"])] + [len(local)])
                        if r_i == len(local):
                            local.append([])
                    local[r_i].append((oi["L"], oi["R"], i_))
                    oi["rang_l"] = r_i
                for l in parents[q]:
                    pp = items[l["a"]]
                    if pp.get("bloc_v") == (v, debut) and "rang_l" in pp:
                        segments.append((o["x0"] - GOUTTIERE, *sorted((pp["rang_l"], place))))
            while local and not local[-1]:
                local.pop()
            for r in local:
                rangees.append([q for _, _, q in r])
            for q in bloc:
                items[q]["rang_g"] = rang_global + debut + items[q]["rang_l"]
        rang_global += len(rangees)
        res[v] = dict(rangees=rangees)
    return res


def ordonnees(items, voies_ordre, rangees, ech):
    entete_h, axe_h = 160, 34
    y = entete_h + axe_h
    intl_voie = dict(y=y, h=getattr(ech, "intl_h", 0))     # C1 : voie « Internationales » en haut
    y += intl_voie["h"]
    voies_geo = []
    for v in voies_ordre:
        membres = [o for o in items.values() if o["voie"] == v]
        if not membres:
            continue
        y_voie = y
        y += VOIE_PAD
        for contenu in rangees[v]["rangees"]:
            haut = BAR_H / 2 + (ONGLET_H if any(items[q].get("onglet") or items[q].get("nom_apres_x")
                                                for q in contenu) else 0)
            bas = max([BAR_H / 2] + [items[q]["bas"] for q in contenu])
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
                y_axe_haut=entete_h, y_axe_bas=y - axe_h - 12, intl_voie=intl_voie)


def optimiser(items, voies_ordre, rangees, poly, ech, rang_voie, passes=3):
    """2.3 : un lien majeur qui croise encore quelque chose essaie de déplacer sa cible, puis sa source,
    vers quelques rangées choisies de sa voie (près de l'autre extrémité, ou en haut ou en bas de la
    voie selon le côté de l'autre voie). Un déplacement n'est gardé que s'il réduit les croisements
    des liens majeurs sans en créer sur les autres liens."""
    def renumeroter():
        g = 0
        for v in voies_ordre:
            if v not in rangees:
                continue
            for r, contenu in enumerate(rangees[v]["rangees"]):
                for q in contenu:
                    items[q]["rang_g"], items[q]["rang_l"] = g + r, r
            g += len(rangees[v]["rangees"])

    def evaluer():
        renumeroter()
        geo = ordonnees(items, voies_ordre, rangees, ech)
        boites = boites_obstacles(items)
        majeurs, autres, croisants = 0, 0, []
        for l in poly:
            t = router(l, items, boites, rang_voie, poly)
            n = 100 if t is None else t["croisements"]
            if l["majeur"]:
                majeurs += n
                if n:
                    croisants.append(l)
            else:
                autres += n + (1 if t is not None and t["rangs"] > SEUIL_RANGS else 0)
        return (majeurs, autres), croisants, geo

    def tient(q, contenu):
        o = items[q]
        return all(o["R"] + GAP <= items[x]["L"] or items[x]["R"] + GAP <= o["L"] for x in contenu if x != q)
    score, croisants, geo = evaluer()
    for _ in range(passes):
        if not score[0]:
            break
        ameliore = False
        for l in list(croisants):
            for q, autre in ((l["b"], l["a"]), (l["a"], l["b"])):
                v = items[q]["voie"]
                lignes = rangees[v]["rangees"]
                r0 = next(i for i, c in enumerate(lignes) if q in c)
                if items[autre]["voie"] == v:
                    ra = next(i for i, c in enumerate(lignes) if autre in c)
                    cibles = [ra, ra + 1]
                else:
                    cibles = [0] if voies_ordre.index(items[autre]["voie"]) < voies_ordre.index(v) else [len(lignes)]
                essais = [("nouvelle", k) for k in cibles] +                          [("dans", r) for k in cibles for r in range(max(0, k - 3), min(len(lignes), k + 4))
                          if r != r0 and tient(q, lignes[r])]
                for sorte, r in essais:
                    sauvegarde = [list(c) for c in lignes]
                    lignes[r0].remove(q)
                    if sorte == "dans":
                        lignes[r].append(q)
                    else:
                        lignes.insert(min(r, len(lignes)), [q])
                    lignes[:] = [c for c in lignes if c]
                    s2, c2, g2 = evaluer()
                    if s2[0] < score[0]:
                        score, croisants, geo, ameliore = s2, c2, g2, True
                        break
                    lignes[:] = sauvegarde
                else:
                    continue
                break
        if not ameliore:
            break
    score, croisants, geo = evaluer()
    return geo


def boites_obstacles(items):
    """Ce qu'un lien ne doit jamais traverser : barres, étiquettes, bandes et leurs sigles, renvois."""
    boites = []
    for o in items.values():
        yb = o["y_c"] - BAR_H / 2
        if o.get("style_intl"):           # bandeau : sa seule emprise est celle de la bande
            ys = o["y_c"] + o["strip_haut"]
            boites.append((o["id"], "barre", (o["x0"], ys, o["strip_x1"] - o["x0"], BANDE_H)))
            if not o["tag_dedans"]:
                boites.append((o["id"], "etiquette", (o["tag_x"], ys, o["tag_w"], BANDE_H)))
            if o["renv"]:
                boites.append((o["id"], "renvoi", (o["renv_x"], ys, o["w_renv"], 13)))
            continue
        boites.append((o["id"], "barre", (o["x0"], yb, o["x1_vis"] - o["x0"], BAR_H)))
        if o.get("onglet"):
            boites.append((o["id"], "etiquette", (o["x0"], yb - ONGLET_H, o["tag_w"], ONGLET_H)))
        if o.get("nom_apres_x"):
            boites.append((o["id"], "etiquette", (o["nom_apres_x"], yb - ONGLET_H,
                                                  o["nom_apres"][1] + 2 * TAG_PAD, ONGLET_H)))
        for b in o["bandes"]:
            y = o["y_c"] + y_bande(o, b)
            boites.append((o["id"], "bande", (b["xa"], y, b["xb"] - b["xa"], BANDE_H)))
            pos = etiquette_bande(o, b)
            if pos:
                boites.append((o["id"], "sigle de bande", (pos[0], y, pos[1], BANDE_H)))
            elif b["ecrit"]:
                boites.append((o["id"], "sigle de bande", (b["xa"] + 2 * MED_R + 1, y, larg(b["texte"], FS, True) + 4, BANDE_H)))
        if o["renv"]:
            ym = o["y_c"] + (o["strip_haut"] + BANDE_H / 2 if o.get("style_intl") else 0)
            boites.append((o["id"], "renvoi", (o["renv_x"], ym - 7, o["w_renv"], 13)))
    return boites


SECTION_DE = {}      # bandeau d'Internationale -> sa section (rempli par bandeaux)


def a_soi(q, sorte, *bouts):
    """Barre ou bande d'un des deux bouts du lien : le lien en part ou y arrive. Le bandeau d'une
    Internationale est la bande de sa section prolongée : il compte aussi comme bande de celle-ci."""
    return sorte in ("barre", "bande") and (q in bouts or SECTION_DE.get(q) in bouts)


def croisements(pts, a, b, boites):
    n = 0
    for p1, p2 in zip(pts, pts[1:]):
        for q, sorte, box in boites:
            if a_soi(q, sorte, a, b):
                continue          # un lien part de sa barre (et de ses bandes) et arrive sur sa cible
            if croise(p1, p2, box):
                n += 1
    return n


def router(l, items, boites, rang_voie, poly):
    """Chemin orthogonal, x jamais décroissant, dernier segment horizontal. Essaie le chemin direct,
    puis des couloirs : le long des limites de rangées, avec une descente là où rien ne gêne."""
    a, b = items[l["a"]], items[l["b"]]
    if l["rel"] == "absorption":
        xs = a["x1"] - 2
        xt = xs + 12
        if not (b["x0"] + 2 <= xt <= b["x1"] - 1) or a["rang_y"] == b["rang_y"]:
            return None
        bas = b["y_c"] > a["y_c"]
        y_dep = a["y_c"] + (a["bas"] if bas else -BAR_H / 2)
        y_arr = b["y_c"] - BAR_H / 2 - 1 if bas else b["y_c"] + b["bas"] + 1
        pts = [(xs, y_dep), (xs, y_arr), (xt, y_arr)]
        return trace(l, a, b, pts, None, boites, rang_voie)
    if l["rel"] == "composante":
        # Trait vertical « collé » entre les deux barres, à la date où le membre rejoint l'autre
        # (ou plus tard si une étiquette est là), sans flèche
        bord_a = a["x0"] + (a["tag_w"] + 2 if a["tag_dedans"] else 3)
        bord_b = b["x0"] + (b["tag_w"] + 2 if b["tag_dedans"] else 3)
        xs = max(l["x_t"], bord_a, bord_b)
        if a["rang_y"] == b["rang_y"] or xs > min(a["x1"], b["x1"]) - 3:
            return None
        bas = b["y_c"] > a["y_c"]
        y1 = a["y_c"] + (a["bas"] if bas else -BAR_H / 2)
        y2 = b["y_c"] - BAR_H / 2 if bas else b["y_c"] + b["bas"]
        if b.get("style_intl") and bas:
            y2 = b["y_c"] + b["strip_haut"]
        # Groupe collé : le trait peut passer sur la barre d'un autre membre de la même organisation
        # (POI -> LFI par-dessus le PG, membre de LFI lui aussi), jamais sur autre chose.
        membres = {x["a"] for x in poly if x["rel"] == "composante" and x["b"] == l["b"]} - {l["a"]}
        boites_c = [bx for bx in boites if not (bx[0] in membres and bx[1] in ("barre", "bande"))]
        return trace(l, a, b, [(xs, y1), (xs, y2)], None, boites_c, rang_voie)
    normaux = sorted([x for x in poly if x["b"] == l["b"] and x["rel"] not in ("absorption", "composante")],
                     key=lambda x: items[x["a"]]["y_c"])
    n, k = len(normaux), next(i for i, x in enumerate(normaux) if x["a"] == l["a"])
    off = max(-(BAR_H / 2 - 3), min(BAR_H / 2 - 3, (k - (n - 1) / 2) * 5))
    xt, yt = b["x0"], b["y_c"] + off
    if b.get("style_intl"):        # bandeau : flèche au milieu de la bande
        yt = b["y_c"] + b["strip_haut"] + BANDE_H / 2 + max(-(BANDE_H / 2 - 2), min(BANDE_H / 2 - 2, off))
    xv = xt - GOUTTIERE
    bas = yt > a["y_c"]
    fini_avant = a["x1"] < xv
    # Un départ (et son cercle de scission) ne doit jamais tomber sur l'étiquette dans la barre source
    debut_libre = a["x0"] + (a["tag_w"] - 2 if a["tag_dedans"] else 2)
    xs = a["x1"] - 1 if fini_avant else max(xv, a["x0"] + min(2, (xt - a["x0"]) / 2))
    if xs < debut_libre <= min(a["x1"] - 1, xv):
        xs = debut_libre
    if xt - xs < 3:
        return None
    y_bord = a["y_c"] + (a["bas"] if bas else (a["strip_haut"] if a.get("style_intl") else -BAR_H / 2))
    y_mil = a["y_c"] + (a["strip_haut"] + BANDE_H / 2 if a.get("style_intl") else 0)
    depart = (xs, y_mil)
    candidats = []
    if a["rang_y"] == b["rang_y"]:
        candidats.append([(xs, yt), (xt, yt)] if fini_avant else [(xs, y_bord), (xs, yt), (xt, yt)])
    else:
        candidats.append([(xs, y_bord), (xs, yt), (xt, yt)])
        # Couloirs : on peut quitter la barre source plus tôt (x ne décroît jamais), descendre là où
        # rien ne gêne, longer la limite de la rangée cible jusqu'au couloir d'arrivée, puis la cible.
        y_ga = a["rang_y"] + a["rang_h"] if bas else a["rang_y"]
        y_gb = b["rang_y"] if bas else b["rang_y"] + b["rang_h"]
        x_min = max(a["x0"] + 2, min(debut_libre, a["x1"] - 1))

        def libres(y1, y2, x_lo, x_hi):
            """Abscisses où une verticale de y1 à y2 ne traverse rien, entre x_lo et x_hi."""
            h, bb = sorted((y1, y2))
            bloque = sorted((bx - 1, bx + bw + 1) for q, sorte, (bx, by, bw, bh) in boites
                            if by < bb and by + bh > h and bx + bw > x_lo and bx < x_hi
                            and not a_soi(q, sorte, l["a"]))
            res, cur = [], x_lo
            for g, d in bloque:
                if g > cur + 2:
                    res.append((cur, g))
                cur = max(cur, d)
            if x_hi > cur + 2:
                res.append((cur, x_hi))
            return res

        def points(intervalles):
            return sorted({p for g, d in intervalles for p in (g + 1, d - 1) if g + 1 <= d - 1}, reverse=True)
        # Limites de rangées entre la source et la cible : on peut y changer de couloir
        y_lo, y_hi = sorted((a["y_c"], y_gb))
        frontieres = sorted({y for o in items.values() for y in (o["rang_y"], o["rang_y"] + o["rang_h"])
                             if y_lo < y < y_hi} | {y_gb})
        depart_max = min(xv, a["x1"] - 1)
        for yf in frontieres:
            x1s = [x for x in points(libres(a["y_c"], yf, x_min, depart_max)) if x <= depart_max][:6]
            if not x1s and a["x1"] - 1 < xv:
                x1s = []
            for x1 in x1s:
                x2s = [x for x in points(libres(yf, y_gb, x1, xv)) if x >= x1][:4] if yf != y_gb else [x1]
                for x2 in x2s:
                    candidats.append([(x1, y_bord), (x1, yf), (x2, yf), (x2, y_gb), (xv, y_gb), (xv, yt), (xt, yt)])
        if fini_avant:                    # la source a fini avant : départ de son extrémité, puis couloir
            xd = a["x1"] - 1
            for xc in points(libres(y_ga, y_gb, xd, xv))[:8]:
                candidats.append([(xd, y_bord), (xd, y_ga), (xc, y_ga), (xc, y_gb), (xv, y_gb), (xv, yt), (xt, yt)])
    meilleur = None
    for pts in candidats:
        pts = simplifier(pts)
        if len(pts) < 2 or abs(pts[-1][1] - pts[-2][1]) > 1e-6 or pts[-1][0] - pts[-2][0] < 3:
            continue
        if any(q[0] < p[0] - 1e-6 for p, q in zip(pts, pts[1:])):
            continue
        t = trace(l, a, b, pts, (pts[0][0], a["y_c"] + (a["strip_haut"] + BANDE_H / 2 if a.get("style_intl") else 0)),
                  boites, rang_voie)
        cle = (t["croisements"], len(pts), sum(abs(q[0] - p[0]) + abs(q[1] - p[1]) for p, q in zip(pts, pts[1:])))
        if meilleur is None or cle < meilleur[0]:
            meilleur = (cle, t)
    return meilleur[1] if meilleur else None


def trace(l, a, b, pts, depart, boites, rang_voie):
    vp = [a["voie"] if i < len(pts) - 2 else b["voie"] for i in range(len(pts))]
    return dict(l, pts=pts, voies_pts=vp, depart=depart, annees=(pts[-1][0] - pts[0][0]) / PPA,
                voies=abs(rang_voie[a["voie"]] - rang_voie[b["voie"]]), rangs=abs(a["rang_g"] - b["rang_g"]),
                croisements=croisements(pts, l["a"], l["b"], boites))


def cle_donnees(items, inter):
    """Addendum 5, B3 : la clé lit data/sortie/cle_internationales.csv (relations typées et citées) ;
    plus de chaîne reconstruite en remontant et redescendant les prédécesseurs."""
    utiles = avec_ancetres_inter({a["international_id"] for o in items.values() for a in o["affil"]}, inter)
    rel = [r for r in lire("cle_internationales.csv") if r["id"] in inter and r["autre_id"] in inter]
    sig = lambda i: inter[i]["sigle"]

    def succession(i):
        avant = [f"issue de {sig(r['autre_id'])} ({r['type']})" for r in rel if r["id"] == i and r["relation"] == "succession"]
        apres = [f"devient {sig(r['id'])} ({r['type']})" if r["type"] == "renommage" else
                 f"fusionne dans {sig(r['id'])}" if r["type"] == "fusion" else f"refondée en {sig(r['id'])}"
                 for r in rel if r["autre_id"] == i and r["relation"] == "succession"]
        return ", ".join(avant + apres)

    def scissions(i):
        return ", ".join(f"{sig(r['autre_id'])}" for r in rel if r["id"] == i and r["relation"] == "scission")

    def famille(i):
        vus, pile = [], [i]
        while pile:
            x = pile.pop(0)
            if x not in vus:
                vus.append(x)
                pile += [f for f, _ in inter[x]["filles"]]
        return vus

    def membres_de(ids):
        return [q for i_ in ids for q in dict.fromkeys(inter[i_]["membres"]) if q in items]
    return [dict(id=i, sigle=inter[i]["sigle"], nom=inter[i]["nom"], dates=f"{inter[i]['debut'] or '?'}–{inter[i]['fin']}",
                 filles=", ".join(f"{inter[f]['sigle'] or inter[f]['nom']} ({rel_})" for f, rel_ in inter[i]["filles"]),
                 famille=famille(i), membres_famille=list(dict.fromkeys(membres_de(famille(i)))),
                 couleur=inter[i]["couleur"], motif=inter[i]["motif"], succession=succession(i),
                 scissions=scissions(i), origine=bool(inter[i].get("origine")),
                 ids=[i] + inter[i].get("autres_ids", []),
                 membres=[q for q in dict.fromkeys(inter[i]["membres"]) if q in items])
            for i in sorted(utiles, key=lambda i: (inter[i]["debut"] or "9999", inter[i]["nom"]))]


# ======================================================================
# SVG
# ======================================================================

def marque(cls, x, y, r, voie, couleur, losange=True):
    """C2 : marque de scission en losange, marque de composante en carré (plus de rond hors des
    médaillons). Polygone « geo » : la page HTML le déplace quand une famille est repliée."""
    pts = ([(x, y - r), (x + r, y), (x, y + r), (x - r, y)] if losange else
           [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)])
    geo = "[" + ",".join(f"[{px:.2f},{py:.2f},{voie}]" for px, py in pts) + "]"
    return (f'<polygon class="{cls} geo" points="{" ".join(f"{px:.2f},{py:.2f}" for px, py in pts)}" '
            f'fill="{couleur}" stroke="#FFFFFF" stroke-width="1" data-geo="{geo}" data-voie="{voie}"/>')


def dessiner(m, avec_cle=True, apercu=False):
    items, ech = m["items"], m["ech"]
    X = ech.X
    W = m["largeur"] + (CLE_W if avec_cle and not apercu else 0)
    fond, bas_v, liens_svg, haut_v = [], defaultdict(list), [], defaultdict(list)
    motifs = set()
    for g in m["voies"]:
        c = TEINTE[g["cle"]]
        fond.append(f'<g class="voie" data-voie="{g["i"]}" data-cle="{esc(g["cle"])}">'
                    f'<rect class="fond-voie" x="0" y="{g["y"]:.1f}" width="{m["largeur"]:.1f}" height="{g["h"]:.1f}" '
                    f'fill="{melange(c, "#FFFFFF", 0.90 if g["i"] % 2 == 0 else 0.95)}"/>'
                    f'<rect class="bord-voie" x="0" y="{g["y"]:.1f}" width="8" height="{g["h"]:.1f}" fill="{c}"/>'
                    + texte(16, g["y"] + 20, TITRES[g["cle"]], 13, True, "#1A1A1A", cls="voie-t")
                    + texte(16, g["y"] + 36, f"{g['n']} organisation{'s' if g['n'] > 1 else ''}", FS, False,
                            "#333333", cls="voie-t") + "</g>")
    # ---------- C1 : voie « Internationales » en haut ----------
    iv_ = m.get("intl_voie") or {}
    if iv_.get("h") and m.get("intl_entrees"):
        y0 = iv_["y"]
        n_i = len(m["intl_entrees"])
        fond.append(f'<g class="voie-intl" data-cle="internationales">'
                    f'<rect class="fond-voie" x="0" y="{y0:.1f}" width="{m["largeur"]:.1f}" height="{iv_["h"]:.1f}" '
                    f'fill="{melange(NAVY, "#FFFFFF", 0.92)}"/>'
                    f'<rect class="bord-voie" x="0" y="{y0:.1f}" width="8" height="{iv_["h"]:.1f}" fill="{NAVY}"/>'
                    + texte(16, y0 + 20, "Internationales", 13, True, "#1A1A1A", cls="voie-t")
                    + texte(16, y0 + 36, f"{n_i} Internationale{'s' if n_i > 1 else ''}", FS, False, "#333333",
                            cls="voie-t") + "</g>")
        r_m = INTL_RUBAN / 2 + 2
        for e in m["intl_entrees"]:
            yc_ = y0 + e["y_rel"]
            yt, yb_ = yc_ - INTL_RUBAN / 2, yc_ + INTL_RUBAN / 2
            if e["connu"]:
                fill, trait = NAVY, ""
            else:
                motifs.add((f"h-{NAVY[1:]}", NAVY))
                fill, trait = f"url(#h-{NAVY[1:]})", ' stroke="#1F2A5C" stroke-width="1" stroke-dasharray="3 2"'
            info = (f"{e['nom']} ({e['sigle']}) : {e['dates']}" + ("" if e["connu"] else ", date de fondation inconnue")
                    + (" ; toujours existante" if e["en_vie"] else "")
                    + (f" ; membres dessinés : {', '.join(e['membres'])}" if e["membres"] else " ; origine")
                    + (f" ; identifiants : {', '.join([e['id']] + m['inter'][e['id']].get('autres_ids', []))}"
                       if m["inter"][e["id"]].get("autres_ids") else ""))
            g_ = [f'<g class="intl" data-intl="{esc(e["id"])}"><title>{esc(info)}</title>',
                  f'<rect class="intl-r" x="{e["xa"]:.2f}" y="{yt:.2f}" width="{e["xb"] - e["xa"]:.2f}" '
                  f'height="{INTL_RUBAN}" fill="{fill}"{trait} data-bbox="{e["xa"]:.2f},{yt:.2f},'
                  f'{e["xb"] - e["xa"] + (FLECHE if e["en_vie"] else 0):.2f},{INTL_RUBAN}"/>']
            if e["en_vie"]:
                g_.append(f'<polygon class="intl-pointe" points="{e["xb"]:.2f},{yt:.2f} {e["xb"] + FLECHE:.2f},{yc_:.2f} '
                          f'{e["xb"]:.2f},{yb_:.2f}" fill="{fill}"/>')
            g_.append(f'<circle class="medaillon" cx="{e["xa"] + r_m:.2f}" cy="{yc_:.2f}" r="{r_m - 1:.2f}" fill="#FFFFFF" '
                      f'stroke="{NAVY}" stroke-width="2.5"/>')
            if e["onglet"]:
                # Ruban trop court pour son sigle : onglet collé au-dessus de son début (C3)
                xo, wo = e["xa"], e["w_txt"] + 8
                g_.append(f'<rect class="intl-onglet" x="{xo:.2f}" y="{yt - INTL_ONGLET:.2f}" width="{wo:.2f}" '
                          f'height="{INTL_ONGLET}" fill="{NAVY}" data-bbox="{xo:.2f},{yt - INTL_ONGLET:.2f},{wo:.2f},'
                          f'{INTL_ONGLET}"/>')
                g_.append(texte(xo + 4, yt - 3, e["texte"], FS, True, "#FFFFFF", cls="intl-t",
                                extra=f' data-bbox="{xo + 4:.2f},{yt - INTL_ONGLET + 1:.2f},{e["w_txt"]:.2f},12"'))
            else:
                xt = e["xa"] + 2 * r_m + 4
                if not e["connu"]:          # addendum 5, C4 : texte sur une étiquette pleine, pas sur les hachures
                    g_.append(f'<rect class="intl-etiquette" x="{xt - 3:.2f}" y="{yt:.2f}" width="{e["w_txt"] + 6:.2f}" '
                              f'height="{INTL_RUBAN}" fill="{NAVY}" data-bbox="{xt - 3:.2f},{yt:.2f},{e["w_txt"] + 6:.2f},'
                              f'{INTL_RUBAN}"/>')
                g_.append(texte(xt, yc_ + 4, e["texte"], FS, True, "#FFFFFF", cls="intl-t",
                                extra=f' data-bbox="{xt:.2f},{yt + 1:.2f},{e["w_txt"]:.2f},12"'))
            fond.append("".join(g_) + "</g>")
    y_h, y_b = m["y_axe_haut"], m["y_axe_bas"]
    for a in ech.graduations():
        if (a // 10) % 2 == 0 and a < ech.T1:
            fond.append(f'<rect class="bande-decennie" x="{X(a):.1f}" y="{y_h:.1f}" width="{X(a + 10) - X(a):.1f}" '
                        f'height="{y_b - y_h + 30:.1f}" fill="#000000" fill-opacity="0.06"/>')

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
        strip = o.get("style_intl")
        if strip:
            # Bandeau d'Internationale, au style des bandes ; collé à sa section, il est à la hauteur
            # de la première ligne de bandes de celle-ci, qui le prolonge
            yb, h_b, x1 = yc + o["strip_haut"], BANDE_H, o["strip_x1"]
            fin = "section" if o.get("section") else fin
        else:
            h_b = BAR_H
        bas.append(f'<rect class="barre" data-id="{esc(o["id"])}" data-debut="{o["t0"]:.4f}" data-fin="{fin}" '
                   f'data-statut="{o["statut"]}" data-majeure="{"oui" if o["majeure"] else ""}" x="{x0:.2f}" '
                   f'y="{yb:.2f}" width="{x1 - x0:.2f}" height="{h_b}" rx="{0 if o["x1_vis"] > x1 else (2 if strip else 3)}" '
                   f'fill="{o["couleur"]}"'
                   + ((' data-style="internationale"' if o.get("section") else
                       ' stroke="#333333" stroke-width="0.8" data-style="internationale"') if strip else "")
                   + (f' data-section="{esc(o["section"])}"' if o.get("section") else "")
                   + '/>')
        if o.get("sans_gen"):
            bas.append(f'<path class="sans-ancetre" d="M{x0 - 2:.2f} {yb - 2:.2f} H{x0 - 6:.2f} V{yb + h_b + 2:.2f} '
                       f'H{x0 - 2:.2f}" stroke="#333333" stroke-width="1.6" fill="none"/>')
        if o["x1_vis"] > x1 and not strip:
            bas.append(f'<rect class="fin-ouverte" x="{x1:.2f}" y="{yb:.2f}" width="{o["x1_vis"] - x1:.2f}" '
                       f'height="{BAR_H}" fill="url(#g-{o["couleur"][1:]})"/>')
        if not apercu:
            # Bandes d'affiliation sous la barre (2.7), contour pour rester lisibles
            for b in o["bandes"]:
                y = yc + y_bande(o, b)
                # C1 : ruban marine ; médaillon rond au début ; pointe si toujours membre, bout coupé
                # sinon ; dates inconnues : hachuré, contour en tirets
                if b["connu"]:
                    fill, trait = NAVY, ""
                else:
                    pid = f"h-{NAVY[1:]}"
                    motifs.add((pid, NAVY))
                    fill, trait = f"url(#{pid})", ' stroke="#1F2A5C" stroke-width="1" stroke-dasharray="3 2"'
                corps = b["xb"] - (FLECHE if b["encore"] else 0)
                ym = y + BANDE_H / 2
                haut.append(f'<g class="bande" data-intl="{esc(b["intl"])}" data-parti="{esc(o["id"])}" '
                            f'data-certitude="{"documentee" if b["connu"] else "a_documenter"}" '
                            f'data-fin="{"membre" if b["encore"] else "coupee"}">'
                            f'<title>{esc(b["nom"])} : ' + (f'{esc(b["debut"])}–{esc(b["fin"])}' if b["connu"] else
                                                            "affiliation citée, dates à documenter") + "</title>"
                            f'<rect class="bande-r" x="{b["xa"]:.2f}" y="{y:.2f}" width="{corps - b["xa"]:.2f}" '
                            f'height="{BANDE_H}" fill="{fill}"{trait}'
                            f' data-bbox="{b["xa"]:.2f},{y:.2f},{b["xb"] - b["xa"]:.2f},{BANDE_H}"/>')
                if b["encore"]:
                    haut.append(f'<polygon class="bande-pointe" points="{corps:.2f},{y:.2f} {b["xb"]:.2f},{ym:.2f} '
                                f'{corps:.2f},{y + BANDE_H:.2f}" fill="{fill}"/>')
                haut.append(f'<circle class="medaillon" cx="{b["xa"] + MED_R:.2f}" cy="{ym:.2f}" r="{MED_R - 1:.2f}" '
                            f'fill="#FFFFFF" stroke="{NAVY}" stroke-width="2"/>')
                wt = larg(b["texte"], FS, True)
                wb = wt + 6
                if b["ecrit"] and b["connu"]:
                    xt = b["xa"] + 2 * MED_R + 3
                    haut.append(texte(xt, y + 10.5, b["texte"], FS, True, "#FFFFFF", cls="bande-t",
                                      extra=f' data-bbox="{xt:.2f},{y + 1:.2f},{wt:.2f},12"'))
                else:
                    # Addendum 5, C4 : étiquette pleine (marine, texte blanc), voir etiquette_bande
                    pos = etiquette_bande(o, b)
                    xe = pos[0] if pos else None
                    if xe is not None:
                        haut.append(f'<rect class="bande-etiquette" x="{xe:.2f}" y="{y:.2f}" width="{wb:.2f}" '
                                    f'height="{BANDE_H}" fill="{NAVY}" data-bbox="{xe:.2f},{y:.2f},{wb:.2f},{BANDE_H}"/>')
                        haut.append(texte(xe + 3, y + 10.5, b["texte"], FS, True, "#FFFFFF", cls="bande-t",
                                          extra=f' data-bbox="{xe + 3:.2f},{y + 1:.2f},{wt:.2f},12"'))
                haut.append("</g>")
            # Étiquette au début de la barre (2.6)
            ct, cd = texte_sur(o["couleur"]), gris_sur(o["couleur"])
            if o.get("sans_tag"):
                bas.append("</g>")
                haut.append("</g>")
                bas_v[vi].append("".join(bas))
                haut_v[vi].append("".join(haut))
                continue
            onglet = not o["tag_dedans"]
            if not onglet:
                tag_box = (x0, yb, x1 - x0, h_b)
            else:
                # Addendum 5, A2 et C3 : onglet collé au-dessus du début de la barre, à sa couleur
                tag_box = (x0, yb - ONGLET_H, o["tag_w"], ONGLET_H)
                haut.append(f'<rect class="tag-fond onglet" x="{x0:.2f}" y="{yb - ONGLET_H:.2f}" width="{o["tag_w"]:.2f}" '
                            f'height="{ONGLET_H + 1}" rx="3" fill="{o["couleur"]}"/>')
            haut.append(f'<rect class="tag" data-id="{esc(o["id"])}" data-dedans="{"oui" if not onglet else ""}" '
                        f'data-onglet="{"oui" if onglet else ""}" x="{tag_box[0]:.2f}" y="{tag_box[1]:.2f}" '
                        f'width="{tag_box[2]:.2f}" height="{tag_box[3]}" fill="none" '
                        f'data-bbox="{tag_box[0]:.2f},{tag_box[1]:.2f},{tag_box[2]:.2f},{tag_box[3]}"/>')
            if strip:      # comme le sigle d'une bande
                xx, yy, fs_s = (x0 if o["tag_dedans"] else o["tag_x"]) + 3, yb + 10.5, FS
                ws = larg(o["etiq_aff"], FS, True)
                haut.append(texte(xx, yy, o["etiq_aff"], FS, True, ct, cls="tag-t",
                                  extra=f' data-org="{esc(o["id"])}" data-bbox="{xx:.2f},{yb + 1:.2f},{ws:.2f},12"'))
            else:
                xx = o["tag_x"] + o.get("tag_pad", TAG_PAD)
                yy = yc + 4.5 if not onglet else yb - 3.5
                ws = larg(o["etiq_aff"], FS_SIGLE, True)
                haut.append(texte(xx, yy, o["etiq_aff"], FS_SIGLE, True, ct, cls="tag-t",
                                  extra=f' data-org="{esc(o["id"])}" data-bbox="{xx:.2f},{yy - 11:.2f},{ws:.2f},13"'))
            xx += ws + 5
            if o["avec_dates"]:
                haut.append(texte(xx, yy, o["dates"], FS, False, cd, cls="tag-t",
                                  extra=f' data-org="{esc(o["id"])}" data-bbox="{xx:.2f},{yy - 10:.2f},{larg(o["dates"], FS):.2f},12"'))
            # Noms successifs (PC-SFIC 1921, PCF 1943) : trait blanc à la date, nom écrit après lui
            # s'il tient avant le nom suivant et ne couvre aucun départ de lien
            if o.get("noms"):
                fin_tag = (o["tag_x"] + o["tag_w"]) if o["tag_dedans"] else x0
                departs = [t_["depart"][0] for t_ in m["traces"] if t_["a"] == o["id"] and t_.get("depart")] +                           [t_["pts"][0][0] for t_ in m["traces"] if t_["a"] == o["id"]]
                a_ecrire = o["noms"][1:] if o.get("nom_en_tete") else o["noms"]
                suivants = [X(t_) for t_, *_ in a_ecrire[1:]] + [x1]
                for k_, (t_n, nom, _c, _s) in enumerate(a_ecrire):
                    xn = X(t_n)
                    if not (x0 + 1 < xn < x1 - 1):
                        continue
                    if k_ == len(a_ecrire) - 1 and o.get("nom_apres"):
                        # Addendum 5, A2 : nom trop long pour son segment, en onglet au-dessus de la barre,
                        # à la date du changement (jamais après la fin de la barre)
                        haut.append(f'<line class="nom-trait" x1="{xn:.2f}" x2="{xn:.2f}" y1="{yb:.2f}" '
                                    f'y2="{yb + BAR_H:.2f}" stroke="#FFFFFF" stroke-width="1.5"/>')
                        nom_a, w_a = o["nom_apres"]
                        wo = w_a + 2 * TAG_PAD
                        haut.append(f'<rect class="tag-fond onglet nom-onglet" x="{xn:.2f}" y="{yb - ONGLET_H:.2f}" '
                                    f'width="{wo:.2f}" height="{ONGLET_H + 1}" rx="3" fill="{o["couleur"]}" '
                                    f'data-bbox="{xn:.2f},{yb - ONGLET_H:.2f},{wo:.2f},{ONGLET_H}"/>')
                        haut.append(texte(xn + TAG_PAD, yb - 3.5, nom_a, FS_SIGLE, True, ct, cls="nom-t",
                                          extra=f' data-org="{esc(o["id"])}" data-onglet="oui" '
                                                f'data-bbox="{xn + TAG_PAD:.2f},{yb - ONGLET_H + 1:.2f},{w_a:.2f},13"'))
                        continue
                    if xn > fin_tag + 1:
                        haut.append(f'<line class="nom-trait" x1="{xn:.2f}" x2="{xn:.2f}" y1="{yb:.2f}" '
                                    f'y2="{yb + BAR_H:.2f}" stroke="#FFFFFF" stroke-width="1.5"/>')
                    if nom == o["etiq_aff"] and xn <= fin_tag:
                        continue
                    pose = None
                    for nom in formes_courtes(nom):     # le nom entier s'il tient, sinon plus court
                        xt_ = max(xn + 4, fin_tag + 5)
                        wn = larg(nom, FS_SIGLE, True)
                        gene = [xd for xd in departs if xt_ - 6 <= xd <= xt_ + wn + 6]
                        while gene:                 # première place libre après les départs de liens
                            xt_ = max(gene) + 7
                            gene = [xd for xd in departs if xt_ - 6 <= xd <= xt_ + wn + 6]
                        if xt_ + wn + 3 <= suivants[k_]:
                            pose = (nom, xt_, wn)
                            break
                    if not pose:
                        continue
                    nom, xt_, wn = pose
                    haut.append(texte(xt_, yc + 4.5, nom, FS_SIGLE, True, ct, cls="nom-t",
                                      extra=f' data-org="{esc(o["id"])}" data-bbox="{xt_:.2f},{yc - 6.5:.2f},{wn:.2f},13"'))
            # Renvois, juste avant (étiquette ou couloir d'arrivée)
            xr = o["renv_x"]
            for t, ra, rb in o["renv"]:
                wt = larg(t, FS)
                infob = ("<title>" + esc("voir aussi : " + " ; ".join(x[0] for x in o["voir_aussi"])) + "</title>"
                         if o["voir_aussi"] else "")
                ym = yc + (o["strip_haut"] + BANDE_H / 2 if strip else 0)     # bandeau : à sa hauteur
                haut.append(f'<text x="{xr + 3:.1f}" y="{ym + 4:.1f}" font-size="{FS}" font-family="{POLICE}" '
                            f'font-style="italic" fill="#555555" class="renvoi" data-org="{esc(o["id"])}" '
                            f'data-a="{esc(ra)}" data-b="{esc(rb)}" data-bbox="{xr + 3:.2f},{ym - 7:.2f},{wt:.2f},13">'
                            f'{infob}{esc(t)}</text>')
                xr += wt + 6
        bas.append("</g>")
        haut.append("</g>")
        bas_v[vi].append("".join(bas))
        haut_v[vi].append("".join(haut))

    for a, b in m["continuations"]:
        o = items[b]
        if items[a].get("style_intl"):
            # Bandeau prolongé par la bande de sa section : pas de trait blanc, seulement le lien
            haut_v[m["voie_index"][o["voie"]]].append(
                f'<g class="continuation" data-a="{esc(a)}" data-b="{esc(b)}"><title>{esc(o["label"])}, section de '
                f'{esc(items[a]["label"])}</title></g>')
            continue
        xj, yj = o["x0"], o["y_c"]
        haut_v[m["voie_index"][o["voie"]]].append(
            f'<g class="continuation" data-a="{esc(a)}" data-b="{esc(b)}"><title>renommage : {esc(items[a]["label"])} '
            f'devient {esc(o["label"])}</title><line x1="{xj:.1f}" x2="{xj:.1f}" y1="{yj - BAR_H / 2:.1f}" '
            f'y2="{yj + BAR_H / 2:.1f}" stroke="#FFFFFF" stroke-width="2"/></g>')

    fusions = defaultdict(list)
    for t in m["traces"]:
        st = STYLE_LIEN[t["rel"]]
        pts = list(t["pts"])
        # Un trait qui part (ou arrive, pour une composante) sous les bandes s'accroche au bas réel
        # à son abscisse : la barre, plus les seules bandes présentes à cette date (aucune dans
        # l'aperçu). Sinon il flotte dans le vide là où la bande ne couvre pas (PCF avant 1977).
        vp = list(t["voies_pts"])
        for i_, q_ in ((0, t["a"]), (len(pts) - 1, t["b"])):
            o_ = items[q_]
            if o_.get("style_intl"):
                continue
            bas_barre = o_["y_c"] + BAR_H / 2
            x_, y_ = pts[i_]
            if bas_barre < y_ <= o_["y_c"] + o_["bas"] + 1.5:
                bas_x = bas_barre
                if not apercu:
                    for bd in o_["bandes"]:
                        if bd["xa"] - 0.5 <= x_ <= bd["xb"] + 0.5:
                            bas_x = max(bas_x, o_["y_c"] + y_bande(o_, bd) + BANDE_H)
                pts[i_] = (x_, bas_x + (y_ - (o_["y_c"] + o_["bas"]) if y_ > o_["y_c"] + o_["bas"] else 0))
        # Bandeau d'Internationale : le trait part de son bord, ou arrive en son milieu
        for fin_, q_ in ((False, t["a"]), (True, t["b"])):
            o_ = items[q_]
            if not o_.get("style_intl"):
                continue
            haut_s = o_["y_c"] + o_["strip_haut"]
            bas_s, mil = haut_s + BANDE_H, haut_s + BANDE_H / 2
            i_, j_ = (len(pts) - 1, len(pts) - 2) if fin_ else (0, 1)
            (x_, y_), (xv_, yv_) = pts[i_], pts[j_]
            if xv_ == x_:            # segment vertical : on s'accroche au bord tourné vers l'autre bout
                pts[i_] = (x_, haut_s if yv_ < mil else bas_s)
            elif fin_:               # arrivée horizontale : au milieu du bandeau
                y_n = mil + max(-(BANDE_H / 2 - 2), min(BANDE_H / 2 - 2, y_ - o_["y_c"]))
                if len(pts) == 2:    # trait droit : petit décroché avant la flèche
                    xm = x_ - GOUTTIERE / 2
                    pts[1:1] = [(xm, y_), (xm, y_n)]
                    vp[1:1] = [vp[0], vp[-1]]
                    pts[-1] = (x_, y_n)
                else:
                    pts[-1], pts[-2] = (x_, y_n), (xv_, y_n)
            else:                    # départ horizontal (même rangée) : du milieu du bandeau
                pts[0:1] = [(x_, mil), (x_, y_)]
                vp[0:1] = [vp[0], vp[0]]
        d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts)
        geo = json.dumps([[round(x, 2), round(y, 2), m["voie_index"][v]] for (x, y), v in zip(pts, vp)])
        xt, yt = pts[-1]
        fl = [(xt, yt), (xt - FLECHE_L, yt - FLECHE_DEMI), (xt - FLECHE_L, yt + FLECHE_DEMI)]
        vb = m["voie_index"][items[t["b"]]["voie"]]
        va = m["voie_index"][items[t["a"]]["voie"]]
        infob = (f'{st["nom"]} : {items[t["a"]]["label"]} vers {items[t["b"]]["label"]} ; preuve {t["preuve"]} : '
                 f'« {t["citation"]} »' + (f' puis « {t["citation2"]} » (par {t["inter_nom"]})' if t["rel"] == "indirect" else ""))
        g = [f'<g class="lien" data-a="{esc(t["a"])}" data-b="{esc(t["b"])}" data-rel="{t["rel"]}" '
             f'data-annees="{t["annees"]:.2f}" data-voies="{t["voies"]}" data-rangs="{t["rangs"]}" '
             f'data-majeur="{"oui" if t["majeur"] else ""}" data-va="{va}" data-vb="{vb}"><title>{esc(infob)}</title>',
             f'<path class="halo geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="#FFFFFF" stroke-width="{st["w"] + 2.5:.1f}" stroke-opacity="0.85"/>',
             f'<path class="trait geo" d="{d}" data-geo=\'{geo}\' fill="none" stroke="{st["couleur"]}" stroke-width="{st["w"]}"'
             + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + "/>",
             f'<polygon class="fleche geo" data-geo=\'{json.dumps([[round(x, 2), round(y, 2), vb] for x, y in fl])}\' '
             f'points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in fl)}" fill="{st["couleur"]}"/>']
        if t["rel"] == "composante":
            # Pas de flèche : un trait épais « collé » aux deux barres, un point à chaque bout
            g.pop()
            for (xc, yc), vc in ((pts[0], va), (pts[-1], vb)):
                g.append(marque("marque-composante", xc, yc, 3.0, vc, st["couleur"], losange=False))
        if t["rel"] == "scission" and t["depart"]:
            xs, ys = t["depart"]
            g.append(marque("marque-scission", xs, ys, 4.2, va, st["couleur"]))     # C2 : losange
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
    if avec_cle and not apercu:
        idx, h = index_sigles(m, H, m["largeur"])
        cle_bas += idx
        H += h
    attrs = (f'data-x0="{X0}" data-t0="{ech.T0}" data-ppa="{PPA}" data-aujourdhui="{m["T_AUJ"]:.4f}" '
             f'data-min-w="{MIN_W}" data-seuil-annees="{SEUIL_ANNEES}" data-seuil-voies="{SEUIL_VOIES}" '
             f'data-seuil-rangs="{SEUIL_RANGS}" data-cassure="{",".join(map(str, ech.cassure)) if ech.cassure else ""}" '
             f'data-cassure-px="{CASSURE_PX}" data-degrade="{DEGRADE}" data-n-barres="{len(items)}"'
             + (' data-apercu="oui"' if apercu else "") + (' data-vue-famille="oui"' if m["titre"] else ""))
    defs = "".join(f'<linearGradient id="g-{c[1:]}"><stop offset="0" stop-color="{c}"/><stop offset="1" '
                   f'stop-color="{c}" stop-opacity="0"/></linearGradient>'
                   for c in {o["couleur"] for o in items.values()} | {"#8C8C8C"})
    for pid, c in motifs | {("h-332288", "#332288")}:
        rot = -45 if pid.endswith("-m") else 45
        defs += (f'<pattern id="{pid}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate({rot})">'
                 f'<rect width="6" height="6" fill="#FFFFFF"/><rect width="3" height="6" fill="{c}"/></pattern>')
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


def legende(m, apercu):
    el = ['<g class="legende">']
    n = len(m["items"])
    el.append(texte(16, 32, m["titre"] or "Généalogie des organisations de gauche en France", 22, True, "#111111",
                    cls="legende-t"))
    el.append(texte(16, 52, f"{n} organisations en lignée directe, {len(m['traces'])} liens dessinés, "
                            f"{len(m['renvois'])} liens en renvoi, échelle linéaire de {PPA:g} px par an, "
                            f"Wikidata et Wikipédia, {datetime.date.today().strftime('%d/%m/%Y')}"
                            + (", aperçu en barres seules" if apercu else ""), FS, False, "#333333", cls="legende-t"))
    x, y, xmax = 16, 80, m["largeur"] - 20

    def place(w):
        nonlocal x, y
        if x + w > xmax:
            x, y = 16, y + 26
        x0 = x
        x += w + 20
        return x0
    for k, (t, c) in FAMILLES.items():
        if k in m["voie_index"] and k != VOIE_SANS_GEN:
            x0 = place(22 + larg(t, FS))
            el.append(f'<rect x="{x0}" y="{y - 10}" width="16" height="12" rx="2" fill="{c}"/>' + texte(x0 + 22, y, t, FS, cls="legende-t"))
    for rel, st in STYLE_LIEN.items():
        if rel in m["rels"]:
            x0 = place(46 + larg(st["nom"], FS))
            el.append(f'<path d="M{x0} {y - 4} H{x0 + 30}" stroke="{st["couleur"]}" stroke-width="{st["w"]}"'
                      + (f' stroke-dasharray="{st["dash"]}"' if st["dash"] else "") + ' fill="none"/>'
                      f'<polygon points="{x0 + 38},{y - 4} {x0 + 28},{y - 9} {x0 + 28},{y + 1}" fill="{st["couleur"]}"/>'
                      + (f'<polygon points="{x0 + 3},{y - 8.2} {x0 + 7.2},{y - 4} {x0 + 3},{y + 0.2} {x0 - 1.2},{y - 4}" '
                         f'fill="{st["couleur"]}"/>' if rel == "scission" else "")
                      + texte(x0 + 44, y, st["nom"], FS, cls="legende-t"))
    if m["continuations"]:
        t = "renommage : la barre continue sur la même rangée"
        x0 = place(30 + larg(t, FS))
        el.append(f'<rect x="{x0}" y="{y - 10}" width="12" height="12" fill="#8C8C8C"/><rect x="{x0 + 12}" y="{y - 10}" '
                  f'width="12" height="12" fill="#5A5A5A"/>' + texte(x0 + 30, y, t, FS, cls="legende-t"))
    if m["renvois"] and not apercu:
        t = "issu de X, devient Y, absorbé par Y… : lien en renvoi"
        x0 = place(larg(t, FS))
        el.append(texte(x0, y, t, FS, False, "#555555", cls="legende-t", italique=True))
    if VOIE_SANS_GEN in m["voie_index"]:
        t = "aucun ancêtre documenté"
        x0 = place(30 + larg(t, FS))
        el.append(f'<path d="M{x0 + 10} {y - 11} H{x0 + 6} V{y + 2} H{x0 + 10}" stroke="#333333" stroke-width="1.6" '
                  f'fill="none"/><rect x="{x0 + 12}" y="{y - 10}" width="12" height="12" fill="#8C8C8C"/>'
                  + texte(x0 + 30, y, t, FS, cls="legende-t"))
    t = "toujours active"
    x0 = place(40 + larg(t, FS))
    el.append(f'<rect x="{x0}" y="{y - 10}" width="10" height="12" fill="#8C8C8C"/><rect x="{x0 + 10}" y="{y - 10}" '
              f'width="24" height="12" fill="url(#g-8C8C8C)"/>' + texte(x0 + 40, y, t, FS, cls="legende-t"))
    if not apercu:
        bandes = [b for o in m["items"].values() for b in o["bandes"]]

        def ruban(x0, plein=True, pointe=False):
            # C1 : médaillon rond et ruban marine, pointe ou bout coupé, hachuré en tirets si non daté
            fill = NAVY if plein else f"url(#h-{NAVY[1:]})"
            trait = "" if plein else ' stroke="#1F2A5C" stroke-width="1" stroke-dasharray="3 2"'
            corps = 36 - (FLECHE if pointe else 0)
            r = BANDE_H / 2
            return (f'<rect x="{x0}" y="{y - 11}" width="{corps}" height="{BANDE_H}" fill="{fill}"{trait}/>'
                    + (f'<polygon points="{x0 + corps},{y - 11} {x0 + 36},{y - 11 + r} {x0 + corps},{y - 11 + BANDE_H}" '
                       f'fill="{fill}"/>' if pointe else "")
                    + f'<circle class="medaillon" cx="{x0 + r}" cy="{y - 11 + r}" r="{r - 1}" fill="#FFFFFF" stroke="{NAVY}" '
                      f'stroke-width="2"/>')
        for cond, t, plein, pointe in (
                (any(b["connu"] and b["encore"] for b in bandes), "ruban à pointe : toujours membre de l'Internationale",
                 True, True),
                (any(b["connu"] and not b["encore"] for b in bandes), "ruban coupé : membre jusqu'à cette date",
                 True, False),
                (any(not b["connu"] for b in bandes),
                 "ruban hachuré en tirets : affiliation citée, dates inconnues (au plus la période commune)", False, False)):
            if cond:
                x0 = place(46 + larg(t, FS))
                el.append(ruban(x0, plein, pointe) + texte(x0 + 46, y, t, FS, cls="legende-t"))
        if m.get("intl_entrees"):
            t = "voie Internationales : une Internationale sur sa vie, pointe si elle existe toujours"
            x0 = place(46 + larg(t, FS))
            el.append(ruban(x0, True, True) + texte(x0 + 46, y, t, FS, cls="legende-t"))
    return "".join(el) + "</g>"


def cle_compacte(m):
    """Clé compacte juste à droite de l'arbre (2.8) : pastille, sigle, années, membres affichés."""
    x = m["largeur"] + 10
    y = m["y_axe_haut"] + 40
    el = [f'<g class="cle-compacte"><rect x="{x - 6}" y="{y - 26}" width="{CLE_W - 14}" '
          f'height="{30 + 18 * len(m["cle"])}" rx="6" fill="#F6F7F8" stroke="#D0D0D0"/>',
          texte(x + 4, y - 8, "Internationales", 13, True, "#111111", cls="cle-t")]
    for k, c in enumerate(m["cle"]):
        yy = y + 18 * k + 6
        el.append(f'<circle class="medaillon" cx="{x + 11}" cy="{yy - 4}" r="5" fill="#FFFFFF" stroke="{NAVY}" '
                  f'stroke-width="2"/>')
        txt = f"{c['sigle']}  {c['dates']}, {len(c['membres'])}"
        el.append(texte(x + 24, yy, txt if larg(txt, FS) < CLE_W - 50 else txt[:34] + "…", FS, False, "#1A1A1A", cls="cle-t"))
    return "".join(el) + "</g>"


def index_sigles(m, y0, W):
    """Index des sigles : chaque sigle affiché sur une barre, avec le nom complet et les dates."""
    # Sans la précision d'homonymie de Wikipédia : « Alternative libertaire (France) », « (France, 1991) »
    propre = lambda nom: re.sub(r" \((?:[^()]*(?:France|français|française)[^()]*)\)$", "", nom)
    entrees = sorted(((o["etiq_aff"], propre(o["label"]), o["dates"]) for o in m["items"].values()
                      if o["etiq_aff"] != o["label"]), key=lambda e: (sans_accents(e[0]).lower(), e[2]))
    n_col = 4
    col_w = (W - 32) / n_col
    el = [f'<g class="index-sigles" transform="translate(0,{y0:.0f})">',
          texte(16, 30, "Index des sigles", 16, True, "#111111", cls="cle-t")]
    par_col = -(-len(entrees) // n_col)
    y_max = 0
    for i, (sig, nom, dates) in enumerate(entrees):
        col, k = divmod(i, par_col)
        x = 16 + col * col_w
        y = 52 + k * 17
        ws = larg(sig, FS, True)
        el.append(texte(x, y, sig, FS, True, "#111111", cls="cle-t"))
        reste = couper(f"{nom} ({dates})", col_w - ws - 20, FS, max_lignes=1)[0]
        el.append(texte(x + ws + 6, y, reste, FS, False, "#333333", cls="cle-t"))
        y_max = max(y_max, y)
    return "".join(el) + "</g>", y_max + 24


def cle_complete(m, y0, W):
    items = m["items"]
    el = [f'<g class="cle-internationales" transform="translate(0,{y0:.0f})">',
          texte(16, 30, "Clé des Internationales", 16, True, "#111111", cls="cle-t"),
          texte(16, 48, "Les Internationales ne sont pas des organisations de la généalogie : elles apparaissent en bandes "
                        "sous les barres des organisations membres (hachurées si les dates ne sont pas documentées).",
                FS, False, "#333333", cls="cle-t")]
    col_w = (W - 32) / 2
    ys = [68, 68]
    for c in m["cle"]:
        col = 0 if ys[0] <= ys[1] else 1
        x, y = 16 + col * col_w, ys[col]
        el.append(f'<g class="entree-cle" data-intl="{esc(c["id"])}"><rect x="{x:.0f}" y="{y:.0f}" width="26" '
                  f'height="13" fill="{NAVY}"/><circle class="medaillon" cx="{x + 6.5:.1f}" cy="{y + 6.5:.1f}" r="5.5" '
                  f'fill="#FFFFFF" stroke="{NAVY}" stroke-width="2"/>')
        el.append(texte(x + 34, y + 11, c["sigle"], FS, True, "#111111", cls="cle-t"))
        el.append(texte(x + 40 + larg(c["sigle"], FS, True), y + 11, f"{c['nom']} ({c['dates']})", FS, False,
                        "#1A1A1A", cls="cle-t"))
        y += 18
        lignes = []
        if c["succession"]:
            lignes.append("Succession : " + c["succession"])
        if c["scissions"]:
            lignes.append("Scission de : " + c["scissions"])
        if c["membres"]:
            lignes.append(f"Membres affichés ({len(c['membres'])}) : " + ", ".join(items[q]["etiquette"] for q in c["membres"]))
        else:       # addendum 5, C5 : « (0) » seulement pour une origine
            lignes.append(("Origine (R5) : aucun membre dessiné" if c["origine"] else
                           "Aucun membre dessiné : relie sa famille d'Internationales")
                          + (f", identifiants : {', '.join(c['ids'])}" if len(c["ids"]) > 1 else ""))
        for l in lignes:
            for morceau in couper(l, col_w - 50, FS, max_lignes=6):
                el.append(texte(x + 34, y + 11, morceau, FS, False, "#333333", cls="cle-t"))
                y += 16
        el.append("</g>")
        ys[col] = y + 8
    return "".join(el) + "</g>", max(ys) + 20


def vue_internationales(m):
    items, ech = m["items"], m["ech"]
    X = ech.X
    y, corps, W = 110, [], m["largeur"]
    for k, c in enumerate(m["cle"]):
        membres = []
        for q in c["membres"]:
            o = items[q]
            for a in o["affil"]:
                if a["international_id"] == c["id"]:
                    connu = a["date_certainty"] == "known" and bool(a["start"])
                    fin_o = o["t1"] if o["t1"] is not None else m["T_AUJ"]
                    ta = max(o["t0"], t_de(a["start"])) if connu else o["t0"]
                    tb = (fin_o if a["end"] in ("", "toujours membre") else min(fin_o, t_de(a["end"]))) if connu else fin_o
                    membres.append((o, ta, max(tb, ta + 0.5), connu))
        rangees, place = [], []
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


def page_html(m, svg):
    voies = [dict(i=g["i"], cle=g["cle"], titre=TITRES[g["cle"]], h=g["h"]) for g in m["voies"]]
    liens = [dict(a=t["a"], b=t["b"]) for t in m["traces"]] + [dict(a=r["a"], b=r["b"]) for r in m["renvois"]] \
        + [dict(a=a, b=b) for a, b in m["continuations"]]
    cle = [dict(id=c["id"], sigle=c["sigle"], nom=c["nom"], dates=c["dates"], couleur=c["couleur"],
                succession=c["succession"], scissions=c["scissions"], membres=c["membres"],
                filles=c["filles"], famille=c["famille"], membres_famille=c["membres_famille"],
                tags=[m["items"][q]["etiquette"] for q in c["membres"]],
                tags_famille=[m["items"][q]["etiquette"] for q in c["membres_famille"]]) for c in m["cle"]]
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
  .entree { padding:6px 4px; border-bottom:1px solid var(--bord); cursor:pointer; border-radius:4px; font-size:13px; }
  .entree:hover, .entree.choisie { background:color-mix(in srgb, var(--accent) 14%, transparent); }
  .entree.famille { background:color-mix(in srgb, var(--accent) 7%, transparent); box-shadow:inset 3px 0 0 var(--accent); }
  .entree.flash { outline:2px solid var(--accent); }
  .entree .puce { display:inline-block; width:14px; height:10px; margin-right:6px; vertical-align:middle; border-radius:2px; }
  .entree .succ { color:var(--doux); font-size:12px; margin-top:2px; }
  #arbre .org, #arbre .lien { transition:opacity .15s; }
  #arbre.focus .org, #arbre.focus .lien, #arbre.focus .continuation, #arbre.focus .marque-fusion { opacity:.15; }
  #arbre.focus .org.sel, #arbre.focus .lien.sel, #arbre.focus .continuation.sel { opacity:1; }
  #arbre.focus .intl { opacity:.2; }
  #arbre.focus .intl.sel { opacity:1; }
  #arbre .intl { cursor:pointer; }
  #arbre .org.trouve .barre { stroke:#000; stroke-width:3; }
  #arbre .renvoi { cursor:pointer; }
  #arbre .renvoi.sel { fill:#c0392b; font-weight:bold; }
  #arbre .bande { cursor:pointer; }
  #arbre.sans-cadres .bande { display:none; }
  .replie { opacity:.55; }
  /* Infobulle lisible (remplace les infobulles natives du SVG) */
  #bulle { position:fixed; z-index:20; display:none; max-width:min(520px, calc(100vw - 32px)); max-height:60vh; overflow:auto;
    background:var(--fond); color:var(--texte); border:1px solid var(--bord); border-radius:8px; padding:10px 12px;
    box-shadow:0 6px 24px rgba(0,0,0,.18); font-size:13px; line-height:1.45; }
  #bulle.epinglee { border-color:var(--accent); }
  #bulle .titre { font-weight:bold; font-size:15px; margin-bottom:4px; }
  #bulle .ligne { margin:3px 0; }
  #bulle .etiquette { color:var(--doux); }
  #bulle q { display:block; quotes:none; font-style:italic; color:var(--doux); border-left:3px solid var(--bord);
    padding:1px 0 1px 8px; margin:2px 0 4px; word-break:break-word; }
  #bulle .aide { font-size:11px; color:var(--doux); margin-top:6px; }
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
  <div id="bulle" role="tooltip"></div>
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
vue.addEventListener('pointerdown', e => { if (e.target.closest('.bande,.renvoi')) return; glisse = {x:e.clientX, y:e.clientY, vx:vb.x, vy:vb.y}; vue.classList.add('saisie'); });
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
// Clic sur une Internationale : elle et toute sa descendance (filles, petites-filles…) et leurs membres
function familleMembres(id){ const c = D.cle.find(c => c.id === id); return new Set(c ? c.membres_famille : []); }
function marquerFamille(id){ const c = D.cle.find(c => c.id === id); const f = new Set(c ? c.famille : []);
  document.querySelectorAll('.entree').forEach(e => { e.classList.toggle('choisie', e.id === 'cle-' + id);
    e.classList.toggle('famille', e.id !== 'cle-' + id && f.has(e.id.slice(4))); }); }
function surligner(ids){
  if (!ids) { svg.classList.remove('focus'); svg.querySelectorAll('.sel').forEach(e => e.classList.remove('sel')); return; }
  svg.classList.add('focus');
  // Voie du haut : l'Internationale choisie et toute sa descendance (filles, petites-filles…)
  const fam = new Set(choisie ? (D.cle.find(c => c.id === choisie) || {famille: [choisie]}).famille : []);
  svg.querySelectorAll('.intl').forEach(e => e.classList.toggle('sel', fam.has(e.dataset.intl)));
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
  div.innerHTML = '<span class="puce"></span><b></b> <span class="nom"></span> <span class="dates" style="color:var(--doux)"></span><div class="succ s1"></div><div class="succ s2"></div><div class="succ s4"></div><div class="succ s3"></div><div class="succ s5"></div>';
  div.querySelector('.puce').style.background = c.couleur; div.querySelector('b').textContent = c.sigle; div.querySelector('.nom').textContent = c.nom;
  div.querySelector('.dates').textContent = `(${c.dates})`;
  div.querySelector('.s1').textContent = c.succession ? 'Succession : ' + c.succession : '';
  div.querySelector('.s2').textContent = c.scissions ? 'Scission de : ' + c.scissions : '';
  div.querySelector('.s4').textContent = c.filles ? 'Filles : ' + c.filles : '';
  div.querySelector('.s3').textContent = c.membres.length ? `Membres affichés (${c.membres.length}) : ${c.tags.join(', ')}`
    : (c.origine ? 'Origine (R5) : aucun membre dessiné' : 'Aucun membre dessiné : relie sa famille d\'Internationales')
    + (c.ids.length > 1 ? ` ; identifiants : ${c.ids.join(', ')}` : '');
  div.querySelector('.s5').textContent = c.famille.length > 1 ? `Avec sa descendance (clic) : ${c.tags_famille.length} membres, ${c.tags_famille.join(', ')}` : '';
  div.addEventListener('mouseenter', () => surligner(choisie ? familleMembres(choisie) : membres(c.id)));
  div.addEventListener('mouseleave', () => surligner(choisie ? familleMembres(choisie) : null));
  div.addEventListener('click', () => {
    if (choisie === c.id) { choisie = null; marquerFamille(null); surligner(null); }
    else { choisie = c.id; marquerFamille(c.id); surligner(familleMembres(c.id)); } });
  entrees.appendChild(div); }
svg.querySelectorAll('.bande, .intl').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); document.getElementById('cle').open = true;
  const ent = document.getElementById('cle-' + b.dataset.intl); if (!ent) return;
  ent.scrollIntoView({block:'center', behavior:'smooth'}); ent.classList.add('flash'); setTimeout(() => ent.classList.remove('flash'), 1500);
  choisie = b.dataset.intl; marquerFamille(choisie); surligner(familleMembres(choisie)); }));
// Infobulles : le texte des <title> du SVG, mis en forme (nom en gras, une ligne par fait,
// citations à part). Un clic l'épingle (pour la lire et la faire défiler), Échap ou un clic ailleurs la ferme.
const bulle = document.getElementById('bulle');
let epinglee = false;
function echapper(t){ return t.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function formater(txt){
  const lignes = txt.split('\n').filter(l => l.trim());
  return lignes.map((l, i) => {
    let h = echapper(l).replace(/« ([\s\S]*?) »/g, (m, c) => '<q>« ' + c + ' »</q>');
    const k = h.indexOf(' : '); if (i > 0 && k > 0 && k < 90) h = '<span class="etiquette">' + h.slice(0, k) + ' :</span>' + h.slice(k + 2);
    return i === 0 ? '<div class="titre">' + h + '</div>' : '<div class="ligne">' + h + '</div>';
  }).join('') + '<div class="aide">Clic : épingler · Échap : fermer</div>';
}
function placer(e){ const m = 14, w = bulle.offsetWidth, h = bulle.offsetHeight;
  let x = e.clientX + m, y = e.clientY + m;
  if (x + w > innerWidth - 8) x = Math.max(8, e.clientX - w - m);
  if (y + h > innerHeight - 8) y = Math.max(8, innerHeight - h - 8);
  bulle.style.left = x + 'px'; bulle.style.top = y + 'px'; }
svg.querySelectorAll('title').forEach(t => { const p = t.parentNode;
  if (p && p !== svg) { p.dataset.info = t.textContent; t.remove(); } });
svg.querySelectorAll('[data-info]').forEach(el => {
  el.addEventListener('mouseenter', e => { if (epinglee) return; e.stopPropagation();
    bulle.innerHTML = formater(el.dataset.info); bulle.style.display = 'block'; placer(e); });
  el.addEventListener('mousemove', e => { if (!epinglee) placer(e); });
  el.addEventListener('mouseleave', () => { if (!epinglee) bulle.style.display = 'none'; });
  el.addEventListener('click', e => { if (e.target.closest('.renvoi')) return;
    bulle.innerHTML = formater(el.dataset.info); bulle.style.display = 'block'; placer(e);
    epinglee = true; bulle.classList.add('epinglee'); e.stopPropagation(); });
});
function fermer(){ epinglee = false; bulle.classList.remove('epinglee'); bulle.style.display = 'none'; }
document.addEventListener('keydown', e => { if (e.key === 'Escape') fermer(); });
document.getElementById('vue').addEventListener('click', e => { if (epinglee && !bulle.contains(e.target)) fermer(); });
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
    os.makedirs(ARBRES, exist_ok=True)
    orgs, liens, inter, T_AUJ = charger()
    m = mise_en_page(orgs, liens, inter, T_AUJ)
    with open(os.path.join(ARBRES, "arbre.svg"), "w", encoding="utf-8") as f:
        f.write(dessiner(m))
    shutil.copyfile(os.path.join(ARBRES, "arbre.svg"), os.path.join(RACINE, "arbre.svg"))
    with open(os.path.join(ARBRES, "arbre.html"), "w", encoding="utf-8") as f:
        f.write(page_html(m, dessiner(m, avec_cle=False)))
    grand = m["hauteur"] > 3000 or m["largeur"] > 4000
    chemin_ap = os.path.join(ARBRES, "arbre_apercu.svg")
    if grand:
        with open(chemin_ap, "w", encoding="utf-8") as f:
            f.write(dessiner(m, avec_cle=False, apercu=True))
    elif os.path.exists(chemin_ap):
        os.remove(chemin_ap)
    vue = vue_internationales(m)
    with open(os.path.join(ARBRES, "vue_internationales.svg"), "w", encoding="utf-8") as f:
        f.write(vue)
    with open(os.path.join(ARBRES, "vue_internationales.html"), "w", encoding="utf-8") as f:
        f.write(HTML_VUE.replace("__SVG__", vue))
    for ancien in os.listdir(ARBRES):
        if ancien.startswith("arbre_") and ancien.endswith(".svg") and ancien != "arbre_apercu.svg":
            os.remove(os.path.join(ARBRES, ancien))
    for k, (t, _) in FAMILLES.items():
        if k != VOIE_SANS_GEN and any(o["voie"] == k for o in orgs.values()):   # pas une famille
            mf = mise_en_page(orgs, liens, inter, T_AUJ, voies_voulues={k},
                              titre=f"Généalogie de la gauche française, {t.lower()}")
            with open(os.path.join(ARBRES, f"arbre_{slug(k)}.svg"), "w", encoding="utf-8") as f:
                f.write(dessiner(mf))
    chemin_an = os.path.join(SORTIE, "anomalies_rendu.csv")
    if m["anomalies"]:
        with open(chemin_an, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["source", "target", "relation", "source_date", "target_date", "probable_cause"])
            w.writerows(m["anomalies"])
    elif os.path.exists(chemin_an):
        os.remove(chemin_an)
    majeurs = sum(1 for t in m["traces"] if t["majeur"])
    print(f"{len(m['items'])} organisations, {len(m['traces'])} liens tracés (dont {majeurs} majeurs), "
          f"{len(m['renvois'])} renvois, {len(m['continuations'])} continuations, {len(m['anomalies'])} non dessinables.")
    print(f"Voies : {', '.join(TITRES[g['cle']] for g in m['voies'])}")
    print(f"Taille : {m['largeur'] + CLE_W:.0f} x {m['hauteur']:.0f} px (hors clé du bas)")


if __name__ == "__main__":
    main()
