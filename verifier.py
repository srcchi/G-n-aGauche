"""
Vérification automatique des SVG produits par rendu.py. Échoue (code 1) si une règle est violée.

R1 : chaque lien est une polyligne orthogonale, x jamais décroissant, dernier segment horizontal
     vers la droite, flèche vers la droite ; aucun lien au-delà des seuils (années, voies, rangées).
R2 : aucune Internationale ni fédération européenne en barre ou en étiquette.
R3 : chaque barre commence et finit aux dates exactes des données.
R4 : tout texte est dans une étiquette, un onglet, l'axe, un titre de voie, la légende, la clé,
     ou est un renvoi collé à son étiquette ; aucun nom d'organisation hors de son étiquette.
R5 : chaque organisation dessinée est active ou ancêtre (chemin orienté de lignée) d'une active dessinée.
R6 : aucune coalition ni aucun satellite dessiné.
Et : cadres dans l'étendue de leur barre ; ni barres, ni étiquettes, ni onglets, ni renvois qui se
     chevauchent ; tout texte d'au moins 11 px.

Usage : python verifier.py [fichier.svg ...]   (par défaut : data/sortie/arbre*.svg)
"""

import csv
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

S = "{http://www.w3.org/2000/svg}"
SORTIE = os.path.join("data", "sortie")
EPS = 0.06
TEXTES_PERMIS = {"tag-t", "onglet-t", "axe-t", "voie-t", "legende-t", "cle-t", "renvoi"}


def lire(nom, dossier=SORTIE):
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def t_de(a, m=""):
    return int(a) + ((int(m) - 1) / 12 if m else 0)


def nombres(s):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


def bbox(el):
    return tuple(float(v) for v in el.get("data-bbox").split(","))


def chevauche(a, b, marge=0.5):
    return (a[0] + a[2] - marge > b[0] and b[0] + b[2] - marge > a[0]
            and a[1] + a[3] - marge > b[1] and b[1] + b[3] - marge > a[1])


def dedans(petit, grand, eps=0.6):
    return (petit[0] >= grand[0] - eps and petit[1] >= grand[1] - eps
            and petit[0] + petit[2] <= grand[0] + grand[2] + eps and petit[1] + petit[3] <= grand[1] + grand[3] + eps)


def verifier(chemin):
    err = []
    racine = ET.parse(chemin).getroot()
    if racine.get("data-x0") is None:
        return ["pas un arbre produit par rendu.py"], 0, 0, 0
    x0, t0, ppa = float(racine.get("data-x0")), float(racine.get("data-t0")), float(racine.get("data-ppa"))
    t_auj, min_w = float(racine.get("data-aujourdhui")), float(racine.get("data-min-w"))
    s_ans, s_voies, s_rangs = (float(racine.get(k)) for k in ("data-seuil-annees", "data-seuil-voies",
                                                              "data-seuil-rangs"))
    cass = [float(v) for v in racine.get("data-cassure", "").split(",") if v]
    cass_px = float(racine.get("data-cassure-px", 0))
    apercu = racine.get("data-apercu") == "oui"

    def X(t):
        if not cass:
            return x0 + (t - t0) * ppa
        a1, b0 = cass
        if t <= a1:
            return x0 + (t - t0) * ppa
        if t >= b0:
            return x0 + (a1 - t0) * ppa + cass_px + (t - b0) * ppa
        return x0 + (a1 - t0) * ppa + (t - a1) / (b0 - a1) * cass_px

    orgs = {r["id"]: r for r in lire("organisations.csv")}
    sans_date = {r["id"]: r for r in lire("sans_date.csv")}
    inter = {r["id"]: r for r in lire("internationales.csv")}
    types = {r["id"]: r["type"].strip() for r in lire("types.csv", os.path.join("data", "manuel"))}

    # ---------- R1 ----------
    n_liens = 0
    for g in racine.iter(S + "g"):
        if g.get("class") != "lien":
            continue
        n_liens += 1
        nom = f"lien {g.get('data-a')} -> {g.get('data-b')}"
        traits = [p for p in g.findall(S + "path") if "trait" in p.get("class", "")]
        fleches = [p for p in g.findall(S + "polygon") if "fleche" in p.get("class", "")]
        if len(traits) != 1 or len(fleches) != 1:
            err.append(f"R1 {nom} : {len(traits)} tracé(s), {len(fleches)} flèche(s)")
            continue
        v = nombres(traits[0].get("d"))
        pts = list(zip(v[0::2], v[1::2]))
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xb < xa - 1e-6:
                err.append(f"R1 {nom} : x décroît")
            if abs(xa - xb) > 1e-6 and abs(ya - yb) > 1e-6:
                err.append(f"R1 {nom} : segment non orthogonal")
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        if abs(ya - yb) > 1e-6 or xb - xa <= 0:
            err.append(f"R1 {nom} : le dernier segment n'est pas horizontal vers la droite")
        f = [tuple(map(float, c.split(","))) for c in fleches[0].get("points").split()]
        pointe, b1, b2 = f
        if abs(pointe[0] - xb) > 1e-3 or abs(pointe[1] - yb) > 1e-3:
            err.append(f"R1 {nom} : la flèche n'est pas au bout du lien")
        if not (b1[0] < pointe[0] and abs(b1[0] - b2[0]) < 1e-6 and pointe[0] - b1[0] >= 9):
            err.append(f"R1 {nom} : flèche pas vers la droite, ou de moins de 9 px")
        for attr, seuil, quoi in (("data-annees", s_ans, "ans"), ("data-voies", s_voies, "voies"),
                                  ("data-rangs", s_rangs, "rangées")):
            if float(g.get(attr)) > seuil:
                err.append(f"Seuil {nom} : {g.get(attr)} {quoi} > {seuil:g}")

    # ---------- Barres, étiquettes : R2, R3, R5, R6 ----------
    barres, tags, affiches = {}, {}, set()
    for r in racine.iter(S + "rect"):
        cls = r.get("class", "").split()
        q = r.get("data-id")
        if "barre" in cls:
            barres[q] = tuple(float(r.get(k)) for k in ("x", "y", "width", "height"))
            affiches.add(q)
            src = orgs.get(q)
            if src is None:
                err.append(f"R3 : barre {q} absente de organisations.csv")
                continue
            debut = t_de(src["fondation"], src["fondation_mois"])
            x, _, w, _ = barres[q]
            if abs(float(r.get("data-debut")) - debut) > 1e-3 or abs(x - X(debut)) > EPS:
                err.append(f"R3 {q} : début x={x:.2f}, attendu {X(debut):.2f} ({debut})")
            statut = src["statut_fin"]
            if statut.startswith("actif"):
                fin, attendu = "actif", t_auj
            elif src["dissolution"] or src["fin_deduite"]:
                attendu = t_de(src["dissolution"], src["dissolution_mois"]) if src["dissolution"] else t_de(src["fin_deduite"])
                fin = f"{attendu:.4f}"
            else:
                fin, attendu = "inconnue", None
            if r.get("data-fin") != fin and not (fin not in ("actif", "inconnue") and r.get("data-fin") not in ("actif", "inconnue")
                                                 and abs(float(r.get("data-fin")) - attendu) < 1e-3):
                err.append(f"R3 {q} : fin {r.get('data-fin')}, attendu {fin}")
            if attendu is not None:
                xf = X(attendu)
                if xf - x >= min_w and abs(x + w - xf) > EPS:
                    err.append(f"R3 {q} : fin x={x + w:.2f}, attendu {xf:.2f}")
                if xf - x < min_w and abs(w - min_w) > EPS:
                    err.append(f"R3 {q} : barre courte de {w:.2f} px, attendu {min_w}")
            elif abs(w - min_w) > EPS:
                err.append(f"R3 {q} : fin inconnue, la barre devrait faire {min_w} px")
        if "tag" in cls:
            tags[q] = bbox(r)
            affiches.add(q)
    for q in affiches:
        if q in inter:
            err.append(f"R2 : l'Internationale {q} est dessinée")
        if types.get(q) in ("coalition", "satellite"):
            err.append(f"R6 : {q} est de type {types[q]} et ne doit pas être dessiné")
        if q not in inter and not (orgs.get(q, {}).get("garde") == "oui" or sans_date.get(q, {}).get("garde") == "oui"):
            err.append(f"R5 : {q} est dessinée mais n'est pas gardée par l'élagage")
    # R5 : chemin orienté de lignée vers une organisation active dessinée
    enfants = defaultdict(set)
    for l in lire("liens.csv"):
        if l["relation"] in ("filiation", "renommage", "fusion", "scission"):
            enfants[l["source"]].add(l["cible"])
    for l in lire("liens_date_manquante.csv"):
        if l["relation"] in ("filiation", "scission"):
            enfants[l["source"]].add(l["cible"])
    actives = {q for q in affiches
               if (orgs.get(q) or sans_date.get(q) or {}).get("statut_fin", "").startswith("actif")}
    if not racine.get("data-apercu") and "arbre_" not in os.path.basename(chemin):
        for q in affiches - actives:
            vus, pile, ok = set(), [q], False
            while pile and not ok:
                x = pile.pop()
                for y in enfants[x]:
                    if y in actives:
                        ok = True
                        break
                    if y not in vus:
                        vus.add(y)
                        pile.append(y)
            if not ok:
                err.append(f"R5 : {q} n'est ni active ni ancêtre d'une organisation active dessinée")

    # ---------- R4 : textes ----------
    onglets = {}
    for g in racine.iter(S + "g"):
        if g.get("class") == "onglet":
            rr = g.find(S + "rect")
            onglets[id(g)] = bbox(rr)
            for t in g.findall(S + "text"):
                if not dedans(bbox(t), bbox(rr)):
                    err.append(f"R4 : texte d'onglet « {t.text} » hors de son onglet")
    renvois = defaultdict(list)
    for t in racine.iter(S + "text"):
        cls = t.get("class", "")
        fs = t.get("font-size")
        if fs is None or float(fs) < 11:
            err.append(f"Texte de moins de 11 px : « {t.text} »")
        if cls not in TEXTES_PERMIS:
            err.append(f"R4 : texte flottant « {t.text} » (classe « {cls} »)")
        elif cls == "tag-t" and t.get("data-org"):
            q = t.get("data-org")
            if q not in tags or not dedans(bbox(t), tags[q]):
                err.append(f"R4 : « {t.text} » hors de l'étiquette de {q}")
        elif cls == "renvoi":
            renvois[t.get("data-org")].append((bbox(t), t.text))
    for q, rs in renvois.items():
        if q not in tags:
            err.append(f"R4 : renvoi sans étiquette pour {q}")
            continue
        tb = tags[q]
        # Collés : en chaîne depuis le bord de l'étiquette, sur la même ligne
        rs.sort(key=lambda r: r[0][0])
        droite = rs[0][0][0] >= tb[0] + tb[2] - 1
        chaine = rs if droite else list(reversed(rs))
        bord = tb[0] + tb[2] if droite else tb[0]
        for b, txt in chaine:
            ecart = (b[0] - bord) if droite else (bord - (b[0] + b[2]))
            if not (-1 <= ecart <= 10) or not (b[1] < tb[1] + tb[3] and b[1] + b[3] > tb[1]):
                err.append(f"R4 : renvoi « {txt} » pas collé à l'étiquette de {q}")
            bord = b[0] + b[2] if droite else b[0]

    # ---------- Cadres dans l'étendue de la barre ----------
    n_cadres = 0
    for p in racine.iter(S + "path"):
        if p.get("class") != "cadre":
            continue
        n_cadres += 1
        q, pad = p.get("data-parti"), float(p.get("data-pad"))
        if q not in barres:
            err.append(f"Cadre sans barre : {q}")
            continue
        bx, _, bw, _ = barres[q]
        xa, xb = float(p.get("data-xa")), float(p.get("data-xb"))
        if xa < bx - pad - EPS or xb > bx + bw + pad + EPS or xb <= xa:
            err.append(f"Cadre {q} / {p.get('data-intl')} hors de l'étendue de sa barre")
        if p.get("data-intl") not in inter:
            err.append(f"Cadre {q} : Internationale inconnue {p.get('data-intl')}")

    # ---------- Chevauchements : barres, étiquettes, onglets, renvois ----------
    boites = [("barre " + q, b) for q, b in barres.items()] + [("étiquette " + q, b) for q, b in tags.items()]
    boites += [("onglet", b) for b in onglets.values()]
    boites += [(f"renvoi « {txt} »", b) for rs in renvois.values() for b, txt in rs]
    boites.sort(key=lambda x: x[1][0])
    for i, (na, ba) in enumerate(boites):
        for nb, bb in boites[i + 1:]:
            if bb[0] >= ba[0] + ba[2]:
                break
            if chevauche(ba, bb):
                err.append(f"Chevauchement : {na} / {nb}")
    return err, n_liens, len(barres), n_cadres


def main():
    fichiers = sys.argv[1:] or sorted(f for f in glob.glob(os.path.join(SORTIE, "arbre*.svg")))
    total = 0
    for f in fichiers:
        erreurs, n_l, n_b, n_c = verifier(f)
        total += len(erreurs)
        print(f"{f} : {n_b} barres, {n_l} liens, {n_c} cadres -> {'OK' if not erreurs else f'{len(erreurs)} ERREUR(S)'}")
        for e in erreurs[:30]:
            print("   ", e)
        if len(erreurs) > 30:
            print(f"    ... et {len(erreurs) - 30} autres")
    if total:
        print(f"\nÉCHEC : {total} erreur(s).")
        sys.exit(1)
    print("\nToutes les vérifications sont passées.")


if __name__ == "__main__":
    main()
