"""
Vérification automatique (rapport complet). Échoue (code 1) si un compteur n'est pas à zéro.

Compteurs : barres sans lien, barres non datées, étiquettes en double, croisements (liens sur au plus
2 voies), cadres sans leurs deux dates, successions d'Internationales contenant une scission,
violations R1, écarts de dates R3, textes hors cadre ou chevauchements R4, R2, R5, R6, citations
introuvables mot pour mot dans le wikitexte en cache (R8), textes de moins de 11 px.

Usage : python verifier.py [fichier.svg ...]   (par défaut : data/sortie/arbre*.svg)
"""

import csv
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

S = "{http://www.w3.org/2000/svg}"
SORTIE = os.path.join("data", "sortie")
EPS = 0.06
TEXTES_PERMIS = {"tag-t", "onglet-t", "axe-t", "voie-t", "legende-t", "cle-t", "renvoi"}
REL_LIGNEE = {"renommage", "scission", "fusion", "absorption", "refondation", "filiation_idéologique"}


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


def dedans(p, g, eps=0.6):
    return p[0] >= g[0] - eps and p[1] >= g[1] - eps and p[0] + p[2] <= g[0] + g[2] + eps and p[1] + p[3] <= g[1] + g[3] + eps


def croise(p1, p2, b, eps=0.6):
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


def verifier_svg(chemin, cpt, err):
    racine = ET.parse(chemin).getroot()
    if racine.get("data-x0") is None:
        return
    x0, t0, ppa = (float(racine.get(k)) for k in ("data-x0", "data-t0", "data-ppa"))
    t_auj, min_w, degrade = (float(racine.get(k)) for k in ("data-aujourdhui", "data-min-w", "data-degrade"))
    s_ans, s_voies, s_rangs = (float(racine.get(k)) for k in ("data-seuil-annees", "data-seuil-voies", "data-seuil-rangs"))
    cass = [float(v) for v in racine.get("data-cassure", "").split(",") if v]
    cass_px = float(racine.get("data-cassure-px", 0))
    apercu = racine.get("data-apercu") == "oui"
    nom = os.path.basename(chemin)

    def X(t):
        if not cass:
            return x0 + (t - t0) * ppa
        a1, b0 = cass
        if t <= a1:
            return x0 + (t - t0) * ppa
        if t >= b0:
            return x0 + (a1 - t0) * ppa + cass_px + (t - b0) * ppa
        return x0 + (a1 - t0) * ppa + (t - a1) / (b0 - a1) * cass_px

    def faute(compteur, msg):
        cpt[compteur] += 1
        err.append(f"[{nom}] {compteur} : {msg}")

    orgs = {r["id"]: r for r in lire("organisations.csv")}
    inter = {r["id"]: r for r in lire("internationales.csv")}
    types = {r["id"]: r["type"].strip() for r in lire("types.csv", os.path.join("data", "manuel"))}

    # ---------- Barres ----------
    barres, ouvertes, tags, etiquettes = {}, {}, {}, {}
    for r in racine.iter(S + "rect"):
        cls = r.get("class", "").split()
        q = r.get("data-id")
        if "barre" in cls:
            x, y, w, h = (float(r.get(k)) for k in ("x", "y", "width", "height"))
            barres[q] = (x, y, w, h)
            src = orgs.get(q)
            if src is None or not src["fondation"]:
                faute("barres non datées", q)
                continue
            debut = t_de(src["fondation"], src["fondation_mois"])
            if abs(x - X(debut)) > EPS:
                faute("R3 dates", f"{q} début x={x:.2f} attendu {X(debut):.2f}")
            if src["statut_fin"].startswith("actif"):
                if r.get("data-fin") != "actif" or abs(x + w - max(X(t_auj), x + min_w)) > EPS:
                    faute("R3 dates", f"{q} devrait finir aujourd'hui")
                ouvertes[q] = degrade
            else:
                fin = t_de(src["dissolution"], src["dissolution_mois"]) if src["dissolution"] else (
                    t_de(src["fin_deduite"]) if src["fin_deduite"] else None)
                if fin is None:
                    faute("barres non datées", f"{q} sans fin ni statut")
                else:
                    xf = max(X(fin), x + min_w)
                    if abs(x + w - xf) > EPS:
                        faute("R3 dates", f"{q} fin x={x + w:.2f} attendu {xf:.2f}")
            if q in inter:
                faute("R2", f"Internationale {q} dessinée")
            if types.get(q) in ("coalition", "satellite"):
                faute("R6", f"{q} de type {types[q]} dessiné")
            if src.get("garde") != "oui":
                faute("R5", f"{q} dessinée mais pas gardée")
        if "tag" in cls:
            tags[q] = bbox(r)
    if apercu:
        return
    for t in racine.iter(S + "text"):
        if t.get("class") == "tag-t" and t.get("data-org") and t.get("data-org") not in etiquettes:
            etiquettes[t.get("data-org")] = t.text
    for e, n in Counter(etiquettes.values()).items():
        if n > 1:
            faute("étiquettes en double", f"« {e} » x{n}")
    cpt["_barres"] = max(cpt["_barres"], len(barres))
    legende = " ".join(t.text or "" for t in racine.iter(S + "text") if t.get("class") == "legende-t")
    m = re.search(r"(\d+) organisations en lignée directe", legende)
    if not m or int(m.group(1)) != len(barres):
        faute("légende", f"compte annoncé {m.group(1) if m else '?'} pour {len(barres)} barres")

    # ---------- Liens (R1, seuils), barres sans lien ----------
    reliees = set()
    obstacles = [(q, "barre", (b[0], b[1], b[2] + ouvertes.get(q, 0), b[3])) for q, b in barres.items()]
    obstacles += [(q, "étiquette", b) for q, b in tags.items()]
    onglets = []
    for g in racine.iter(S + "g"):
        if g.get("class") == "onglet":
            rr = g.find(S + "rect")
            onglets.append((g.get("data-parti"), bbox(rr)))
            for t in g.findall(S + "text"):
                if not dedans(bbox(t), bbox(rr)):
                    faute("R4 textes", f"texte d'onglet « {t.text} » hors de son onglet")
    obstacles += [(q, "onglet", b) for q, b in onglets]
    for g in racine.iter(S + "g"):
        cls = g.get("class")
        if cls == "continuation":
            reliees |= {g.get("data-a"), g.get("data-b")}
        if cls != "lien":
            continue
        a, b = g.get("data-a"), g.get("data-b")
        reliees |= {a, b}
        traits = [p for p in g.findall(S + "path") if "trait" in p.get("class", "")]
        fleches = [p for p in g.findall(S + "polygon") if "fleche" in p.get("class", "")]
        if len(traits) != 1 or len(fleches) != 1:
            faute("R1", f"{a}->{b} : tracé ou flèche manquant")
            continue
        v = nombres(traits[0].get("d"))
        pts = list(zip(v[0::2], v[1::2]))
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xb < xa - 1e-6:
                faute("R1", f"{a}->{b} : x décroît")
            if abs(xa - xb) > 1e-6 and abs(ya - yb) > 1e-6:
                faute("R1", f"{a}->{b} : segment non orthogonal")
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        if abs(ya - yb) > 1e-6 or xb <= xa:
            faute("R1", f"{a}->{b} : dernier segment pas horizontal vers la droite")
        f = [tuple(map(float, c.split(","))) for c in fleches[0].get("points").split()]
        if abs(f[0][0] - xb) > 1e-3 or abs(f[0][1] - yb) > 1e-3 or not (f[1][0] < f[0][0] and f[0][0] - f[1][0] >= 9
                                                                        and abs(f[1][0] - f[2][0]) < 1e-6):
            faute("R1", f"{a}->{b} : flèche pas vers la droite ou trop petite")
        for attr, seuil in (("data-annees", s_ans), ("data-voies", s_voies), ("data-rangs", s_rangs)):
            if float(g.get(attr)) > seuil:
                faute("R1", f"{a}->{b} : {attr} {g.get(attr)} au-delà du seuil {seuil:g}")
        if float(g.get("data-voies")) <= 2:
            for p1, p2 in zip(pts, pts[1:]):
                for q, sorte, box in obstacles:
                    if sorte == "barre" and q in (a, b):
                        continue
                    if croise(p1, p2, box):
                        faute("croisements", f"{a}->{b} traverse {sorte} de {q}")

    # ---------- R4 : textes ----------
    renvois = defaultdict(list)
    for t in racine.iter(S + "text"):
        cls = t.get("class", "")
        if t.get("font-size") is None or float(t.get("font-size")) < 11:
            faute("textes < 11 px", f"« {t.text} »")
        if cls not in TEXTES_PERMIS:
            faute("R4 textes", f"texte flottant « {t.text} »")
        elif cls == "tag-t" and t.get("data-org"):
            q = t.get("data-org")
            if q not in tags or not dedans(bbox(t), tags[q]):
                faute("R4 textes", f"« {t.text} » déborde de l'étiquette de {q}")
        elif cls == "renvoi":
            renvois[t.get("data-org")].append((bbox(t), "".join(t.itertext())))
            reliees |= {t.get("data-a"), t.get("data-b"), t.get("data-org")}
    for q, rs in renvois.items():
        if q not in tags:
            faute("R4 textes", f"renvoi sans étiquette ({q})")
            continue
        tb = tags[q]
        rs.sort(key=lambda r: r[0][0])
        droite = rs[0][0][0] >= tb[0] + tb[2] - 1
        bord = tb[0] + tb[2] if droite else tb[0]
        for b_, txt in (rs if droite else list(reversed(rs))):
            ecart = (b_[0] - bord) if droite else (bord - (b_[0] + b_[2]))
            if not (-1 <= ecart <= 10):
                faute("R4 textes", f"renvoi « {txt} » pas collé à l'étiquette de {q}")
            bord = b_[0] + b_[2] if droite else b_[0]
    for q in barres:
        if q not in reliees:
            faute("barres sans lien", f"{q} ({orgs.get(q, {}).get('label', '')})")

    # ---------- Cadres ----------
    for p in racine.iter(S + "path"):
        if p.get("class") != "cadre":
            continue
        if not p.get("data-debut") or not p.get("data-fin"):
            faute("cadres sans dates", f"{p.get('data-parti')} / {p.get('data-intl')}")
        q, pad = p.get("data-parti"), float(p.get("data-pad"))
        bx, _, bw, _ = barres.get(q, (0, 0, 0, 0))
        if float(p.get("data-xa")) < bx - pad - EPS or float(p.get("data-xb")) > bx + bw + pad + EPS:
            faute("R4 chevauchements", f"cadre de {q} hors de sa barre")

    # ---------- Chevauchements ----------
    boites = [("barre " + q, (b[0], b[1], b[2] + ouvertes.get(q, 0), b[3])) for q, b in barres.items()]
    boites += [("étiquette " + q, b) for q, b in tags.items()] + [("onglet", b) for _, b in onglets]
    boites += [(f"renvoi « {txt} »", b) for rs in renvois.values() for b, txt in rs]
    boites.sort(key=lambda x: x[1][0])
    for i, (na, ba) in enumerate(boites):
        for nb, bb in boites[i + 1:]:
            if bb[0] >= ba[0] + ba[2]:
                break
            if chevauche(ba, bb):
                faute("R4 chevauchements", f"{na} / {nb}")


def verifier_donnees(cpt, err):
    """Successions d'Internationales et citations (R8), indépendamment des SVG."""
    import preuves
    corpus = preuves.Corpus()

    def faute(compteur, msg):
        cpt[compteur] += 1
        err.append(f"[données] {compteur} : {msg}")
    for r in lire("internationales.csv"):
        if r["predecessor_id"] and r.get("succession_type") not in ("renommage", "fusion", "refondation"):
            faute("successions avec scission", f"{r['name']} : type « {r.get('succession_type')} »")
        if r["predecessor_id"] and not corpus.verifier(r.get("succession_citation", ""), r.get("succession_source", "")):
            faute("citations introuvables", f"succession de {r['name']}")
    affiches = {r["id"] for r in lire("organisations.csv") if r.get("garde") == "oui"}
    for r in lire("liens.csv"):
        if r["source"] not in affiches or r["cible"] not in affiches or r.get("preuve") == "manuel":
            continue
        if not corpus.verifier(r.get("citation", ""), r.get("source_citation", "")):
            faute("citations introuvables", f"lien {r['source_nom']} -> {r['cible_nom']}")
    for r in lire("affiliations.csv"):
        if r["party_id"] in affiches and not corpus.verifier(r.get("citation", ""), r.get("source_citation", "")):
            faute("citations introuvables", f"affiliation {r['party_nom']} / {r['international_nom']}")


COMPTEURS = ["barres sans lien", "barres non datées", "étiquettes en double", "croisements", "cadres sans dates",
             "successions avec scission", "R1", "R2", "R3 dates", "R4 textes", "R4 chevauchements", "R5", "R6",
             "citations introuvables", "textes < 11 px", "légende"]


def main():
    fichiers = sys.argv[1:] or sorted(glob.glob(os.path.join(SORTIE, "arbre*.svg")))
    cpt, err = Counter(), []
    for f in fichiers:
        verifier_svg(f, cpt, err)
    verifier_donnees(cpt, err)
    print("Rapport de vérification (" + ", ".join(os.path.basename(f) for f in fichiers) + ")")
    print(f"  barres dessinées (arbre complet) : {cpt['_barres']}")
    for c in COMPTEURS:
        print(f"  {c:<28} {cpt[c]:>4}  {'OK' if cpt[c] == 0 else 'ÉCHEC'}")
    total = sum(cpt[c] for c in COMPTEURS)
    for e in err[:40]:
        print("   ", e)
    if len(err) > 40:
        print(f"    ... et {len(err) - 40} autres")
    if total:
        print(f"\nÉCHEC : {total} problème(s).")
        sys.exit(1)
    print("\nToutes les vérifications sont passées.")


if __name__ == "__main__":
    main()
