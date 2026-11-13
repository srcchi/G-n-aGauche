"""
Vérification automatique des SVG produits par rendu.py. Échoue (code 1) si une règle est violée.

R1 : chaque lien est une polyligne orthogonale, x jamais décroissant, dernier segment horizontal
     vers la droite, flèche pointant à droite ; pas de longueur horizontale nulle.
R2 : aucune Internationale (ni fédération européenne) n'est une barre ou une étiquette des voies.
R3 : chaque barre commence et finit aux dates exactes des CSV.
Et : bandes d'affiliation dans l'étendue de leur barre ; pas de chevauchement de barres ni
     d'étiquettes ; aucun lien au-delà des seuils ; tout texte d'au moins 11 px.

Usage : python verifier.py [fichier.svg ...]   (par défaut : data/sortie/arbre*.svg)
"""

import csv
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = {"s": "http://www.w3.org/2000/svg"}
SORTIE = os.path.join("data", "sortie")
EPS = 0.06


def lire(nom):
    with open(os.path.join(SORTIE, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def t_de(a, m=""):
    return int(a) + ((int(m) - 1) / 12 if m else 0)


def points_path(d):
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", d)]
    return list(zip(nums[0::2], nums[1::2]))


def points_poly(p):
    return [tuple(float(v) for v in c.split(",")) for c in p.split()]


def bbox(el):
    return tuple(float(v) for v in el.get("data-bbox").split(","))


def chevauche(a, b, marge=0.5):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax + aw - marge > bx and bx + bw - marge > ax and ay + ah - marge > by and by + bh - marge > ay


def verifier(chemin):
    erreurs = []
    racine = ET.parse(chemin).getroot()
    x0, t0, ppa = float(racine.get("data-x0")), float(racine.get("data-t0")), float(racine.get("data-ppa"))
    t_auj, min_w = float(racine.get("data-aujourdhui")), float(racine.get("data-min-w"))
    seuil_a, seuil_v = float(racine.get("data-seuil-annees")), float(racine.get("data-seuil-voies"))

    def X(t):
        return x0 + (t - t0) * ppa

    orgs = {r["id"]: r for r in lire("organisations.csv")}
    externes = {r["id"]: r for r in lire("perimetre_exclu.csv") if r["voie_externe"] == "oui"}
    inter = {r["id"]: r for r in lire("internationales.csv")}
    noms_inter = {r["name"] for r in inter.values()}

    # ---------- R1 : liens ----------
    n_liens = 0
    for g in racine.iter("{http://www.w3.org/2000/svg}g"):
        if g.get("class") != "lien":
            continue
        n_liens += 1
        nom = f"lien {g.get('data-a')} -> {g.get('data-b')}"
        traits = [p for p in g.findall("s:path", NS) if "trait" in p.get("class", "")]
        fleches = [p for p in g.findall("s:polygon", NS) if "fleche" in p.get("class", "")]
        if len(traits) != 1 or len(fleches) != 1:
            erreurs.append(f"R1 {nom} : {len(traits)} tracé(s), {len(fleches)} flèche(s)")
            continue
        pts = points_path(traits[0].get("d"))
        if len(pts) < 2:
            erreurs.append(f"R1 {nom} : moins de deux points")
            continue
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xb < xa - 1e-6:
                erreurs.append(f"R1 {nom} : x décroît ({xa:.1f} -> {xb:.1f})")
            if abs(xa - xb) > 1e-6 and abs(ya - yb) > 1e-6:
                erreurs.append(f"R1 {nom} : segment non orthogonal")
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        if abs(ya - yb) > 1e-6 or xb - xa <= 0:
            erreurs.append(f"R1 {nom} : le dernier segment n'est pas horizontal vers la droite")
        if pts[-1][0] - pts[0][0] <= 0:
            erreurs.append(f"R1 {nom} : longueur horizontale nulle")
        f = points_poly(fleches[0].get("points"))
        pointe, b1, b2 = f
        if not (abs(pointe[0] - xb) < 1e-3 and abs(pointe[1] - yb) < 1e-3):
            erreurs.append(f"R1 {nom} : la pointe de la flèche n'est pas au bout du lien")
        if not (b1[0] < pointe[0] and b2[0] < pointe[0] and abs(b1[0] - b2[0]) < 1e-6
                and abs((b1[1] + b2[1]) / 2 - pointe[1]) < 1e-3):
            erreurs.append(f"R1 {nom} : la flèche ne pointe pas vers la droite")
        if float(g.get("data-annees")) > seuil_a:
            erreurs.append(f"Seuil {nom} : {g.get('data-annees')} ans > {seuil_a:g}")
        if float(g.get("data-voies")) > seuil_v:
            erreurs.append(f"Seuil {nom} : traverse {g.get('data-voies')} voies > {seuil_v:g}")

    # ---------- Barres : R2, R3 ----------
    barres = {}
    for r in racine.iter("{http://www.w3.org/2000/svg}rect"):
        if "barre" not in r.get("class", "").split():
            continue
        q = r.get("data-id")
        x, y, w, h = (float(r.get(k)) for k in ("x", "y", "width", "height"))
        barres[q] = (x, y, w, h)
        if q in inter:
            erreurs.append(f"R2 : l'Internationale {q} est dessinée comme une barre")
        if "sans-date" in r.get("class"):
            continue
        src = orgs.get(q) or externes.get(q)
        if src is None:
            erreurs.append(f"R3 : barre {q} absente des CSV")
            continue
        debut = t_de(src["fondation"], src["fondation_mois"])
        if abs(float(r.get("data-debut")) - debut) > 1e-3 or abs(x - X(debut)) > EPS:
            erreurs.append(f"R3 {q} : début {r.get('data-debut')} / x={x:.2f}, attendu {debut} / {X(debut):.2f}")
        fin_attr = r.get("data-fin")
        if src.get("actif"):
            attendu = t_auj
            if fin_attr != "actif":
                erreurs.append(f"R3 {q} : devrait être active")
        elif src.get("dissolution") or src.get("fin_deduite"):
            attendu = (t_de(src["dissolution"], src["dissolution_mois"]) if src["dissolution"]
                       else t_de(src["fin_deduite"]))
            if fin_attr in ("actif", "inconnue") or abs(float(fin_attr) - attendu) > 1e-3:
                erreurs.append(f"R3 {q} : fin {fin_attr}, attendu {attendu}")
        else:
            attendu = None
            if fin_attr != "inconnue":
                erreurs.append(f"R3 {q} : fin {fin_attr}, attendu « inconnue »")
        if attendu is not None:
            x_fin = X(attendu)
            if x_fin - x >= min_w and abs(x + w - x_fin) > EPS:
                erreurs.append(f"R3 {q} : fin x={x + w:.2f}, attendu {x_fin:.2f}")
            if x_fin - x < min_w and abs(w - min_w) > EPS:
                erreurs.append(f"R3 {q} : barre courte de largeur {w:.2f}, attendu {min_w}")

    # R2 : aucun texte des voies ne porte le nom d'une Internationale
    for t in racine.iter("{http://www.w3.org/2000/svg}text"):
        if t.get("class") in ("etiquette",) and (t.text or "").strip() in noms_inter:
            erreurs.append(f"R2 : étiquette « {t.text} » dans les voies")

    # ---------- Bandes d'affiliation dans leur barre ----------
    n_bandes = 0
    for r in racine.iter("{http://www.w3.org/2000/svg}rect"):
        if r.get("class") != "bande-affil":
            continue
        n_bandes += 1
        q = r.get("data-parti")
        if q not in barres:
            erreurs.append(f"Bande d'affiliation sans barre : {q}")
            continue
        bx, _, bw, _ = barres[q]
        x, w = float(r.get("x")), float(r.get("width"))
        if x < bx - EPS or x + w > bx + bw + EPS or w <= 0:
            erreurs.append(f"Bande {q} / {r.get('data-intl')} hors de la barre")
        if r.get("data-intl") not in inter:
            erreurs.append(f"Bande {q} : Internationale inconnue {r.get('data-intl')}")

    # ---------- Texte : taille minimale ----------
    for t in racine.iter("{http://www.w3.org/2000/svg}text"):
        fs = t.get("font-size")
        if fs is None or float(fs) < 11:
            erreurs.append(f"Texte de moins de 11 px : « {t.text} » ({fs})")

    # ---------- Chevauchements ----------
    boites = [("barre " + q, b, q) for q, b in barres.items()]
    for t in racine.iter("{http://www.w3.org/2000/svg}text"):
        if t.get("data-bbox") is None:
            continue
        b = bbox(t)
        dans = t.get("data-dans")
        if dans:   # étiquette dans sa barre : doit y être contenue
            bx, by, bw, bh = barres[dans]
            x, y, w, h = b
            if x < bx - EPS or x + w > bx + bw + EPS or y < by - EPS or y + h > by + bh + EPS:
                erreurs.append(f"Étiquette « {t.text} » déborde de sa barre {dans}")
        else:
            boites.append((f"texte « {t.text} »", b, None))
    boites.sort(key=lambda x: x[1][0])
    for i, (na, ba, qa) in enumerate(boites):
        for nb, bb, qb in boites[i + 1:]:
            if bb[0] >= ba[0] + ba[2]:
                break
            if chevauche(ba, bb):
                erreurs.append(f"Chevauchement : {na} / {nb}")

    return erreurs, n_liens, len(barres), n_bandes


def main():
    fichiers = sys.argv[1:] or sorted(glob.glob(os.path.join(SORTIE, "arbre*.svg")))
    total = 0
    for f in fichiers:
        erreurs, n_l, n_b, n_s = verifier(f)
        total += len(erreurs)
        etat = "OK" if not erreurs else f"{len(erreurs)} ERREUR(S)"
        print(f"{f} : {n_b} barres, {n_l} liens, {n_s} bandes d'affiliation -> {etat}")
        for e in erreurs[:40]:
            print("   ", e)
        if len(erreurs) > 40:
            print(f"    ... et {len(erreurs) - 40} autres")
    if total:
        print(f"\nÉCHEC : {total} erreur(s).")
        sys.exit(1)
    print("\nToutes les vérifications sont passées.")


if __name__ == "__main__":
    main()
