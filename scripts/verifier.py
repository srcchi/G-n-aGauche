"""
Vérification automatique (rapport complet). Échoue (code 1) si un compteur n'est pas à zéro.

Compteurs : barres sans lien, barres non datées, étiquettes en double, croisements (liens sur au plus
2 voies), bandes sans dates documentées dessinées pleines, successions d'Internationales contenant une
scission, R1, R2, R3, R4 (textes hors cadre, chevauchements), R5, R6, citations introuvables mot pour
mot (R8), types de relation contredits par leur citation, liens majeurs dessinés en renvoi,
incontournables absents sans explication, étiquettes placées après la fin d'une barre qui a un
successeur direct, textes de moins de 11 px, compte de la légende.

Usage : python verifier.py [fichier.svg ...]   (par défaut : arbres/arbre*.svg)
"""

import csv
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

S = "{http://www.w3.org/2000/svg}"
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # racine du dépôt
SORTIE = os.path.join(RACINE, "data", "sortie")
MANUEL = os.path.join(RACINE, "data", "manuel")
ARBRES = os.path.join(RACINE, "arbres")
EPS = 0.06
TEXTES_PERMIS = {"tag-t", "bande-t", "axe-t", "voie-t", "legende-t", "cle-t", "renvoi", "nom-t"}
REL_SUCC_DIRECTE = {"renommage", "fusion", "absorption", "refondation", "scission", "filiation_idéologique", "indirect"}


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
    vue_famille = racine.get("data-vue-famille") == "oui"
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
    types = {r["id"]: r["type"].strip() for r in lire("types.csv", MANUEL)}
    liens_csv = lire("liens.csv")
    successeur = {r["source"] for r in liens_csv if r["relation"] in REL_SUCC_DIRECTE}

    # ---------- Barres : R2, R3, R5, R6 ----------
    barres, ouvertes, majeures = {}, {}, set()
    for r in racine.iter(S + "rect"):
        if "barre" not in r.get("class", "").split():
            continue
        q = r.get("data-id")
        x, y, w, h = (float(r.get(k)) for k in ("x", "y", "width", "height"))
        barres[q] = (x, y, w, h)
        if r.get("data-majeure") == "oui":
            majeures.add(q)
        src = orgs.get(q)
        if src is None or not src["fondation"]:
            faute("barres non datées", q)
            continue
        debut = t_de(src["fondation"], src["fondation_mois"])
        if abs(x - X(debut)) > EPS:
            faute("R3 dates", f"{q} début x={x:.2f} attendu {X(debut):.2f}")
        if r.get("data-section"):
            # Bandeau d'Internationale collé à sa section : il finit où la section (et sa bande) commence
            sec = next((x for x in racine.iter(S + "rect") if "barre" in x.get("class", "").split()
                        and x.get("data-id") == r.get("data-section")), None)
            if sec is None or not (float(sec.get("x")) - EPS <= x + w <= float(sec.get("x")) + 40):
                faute("R3 dates", f"{q} : bandeau qui ne finit pas au début de sa section")
        elif src["statut_fin"].startswith("actif"):
            if r.get("data-fin") != "actif" or abs(x + w - max(X(t_auj), x + min_w)) > EPS:
                faute("R3 dates", f"{q} devrait finir aujourd'hui")
            ouvertes[q] = degrade
        else:
            fin = t_de(src["dissolution"], src["dissolution_mois"]) if src["dissolution"] else (
                t_de(src["fin_deduite"]) if src["fin_deduite"] else None)
            if fin is None:
                faute("barres non datées", f"{q} sans fin ni statut")
            elif abs(x + w - max(X(fin), x + min_w)) > EPS:
                faute("R3 dates", f"{q} fin x={x + w:.2f} attendu {max(X(fin), x + min_w):.2f}")
        if q in inter:
            faute("R2", f"Internationale {q} dessinée")
        if types.get(q) in ("coalition", "satellite"):
            faute("R6", f"{q} de type {types[q]} dessiné")
        if src.get("garde") != "oui":
            faute("R5", f"{q} dessinée mais pas gardée")
    # Départ de chaque lien sur sa barre (ou ses bandes si elles sont dessinées) : jamais dans le vide
    bandes_de = defaultdict(list)       # parti -> [(x, x fin, bas)] : une bande ne compte qu'à son abscisse
    for g in racine.iter(S + "g"):
        if g.get("class") == "bande":
            rb = g.find(S + "rect")
            bx_, bw_ = float(rb.get("x")), float(rb.get("width"))
            bandes_de[g.get("data-parti")].append((bx_, bx_ + bw_, float(rb.get("y")) + float(rb.get("height"))))
    for g in racine.iter(S + "g"):
        if g.get("class") != "lien":
            continue
        traits = [p for p in g.findall(S + "path") if "trait" in p.get("class", "")]
        a = g.get("data-a")
        if not traits or a not in barres:
            continue
        v = nombres(traits[0].get("d"))
        bx, by, bw, bh = barres[a]
        bas = max([by + bh] + [yb for xa_, xb_, yb in bandes_de.get(a, []) if xa_ - 1 <= v[0] <= xb_ + 1])
        if not (bx - 1 <= v[0] <= bx + bw + ouvertes.get(a, 0) + 1 and by - 1 <= v[1] <= bas + 1.5):
            faute("liens flottants", f"{a}->{g.get('data-b')} : départ ({v[0]:.0f}, {v[1]:.0f}) hors de sa barre")
        # Arrivée d'une composante par le bas (membre au-dessus) : sur le bas réel de la barre cible
        b_ = g.get("data-b")
        if g.get("data-rel") == "composante" and b_ in barres:
            w = nombres(traits[0].get("d"))[-2:]
            cx, cy, cw, ch = barres[b_]
            bas_b = max([cy + ch] + [yb for xa_, xb_, yb in bandes_de.get(b_, []) if xa_ - 1 <= w[0] <= xb_ + 1])
            if w[1] > cy + ch / 2 and not (cy + ch - 1 <= w[1] <= bas_b + 1.5):
                faute("liens flottants", f"{a}->{b_} : arrivée ({w[0]:.0f}, {w[1]:.0f}) hors de sa barre")
    if apercu:
        return
    cpt["_barres"] = max(cpt["_barres"], len(barres))

    # ---------- Étiquettes ----------
    tags, etiquettes = {}, {}
    for r in racine.iter(S + "rect"):
        if r.get("class") == "tag":
            q = r.get("data-id")
            tags[q] = bbox(r)
            bx, _, bw, _ = barres.get(q, (0, 0, 0, 0))
            if tags[q][0] >= bx + bw - 1 and q in successeur:
                faute("étiquettes après une fin", f"{q} : étiquette après la fin de sa barre")
    for t in racine.iter(S + "text"):
        if t.get("class") == "tag-t" and t.get("data-org"):     # sigle + dates : les dates distinguent les homonymes
            etiquettes[t.get("data-org")] = (etiquettes.get(t.get("data-org"), "") + " " + (t.text or "")).strip()
    for e, n in Counter(etiquettes.values()).items():
        if n > 1:
            faute("étiquettes en double", f"« {e} » x{n}")
    legende = " ".join(t.text or "" for t in racine.iter(S + "text") if t.get("class") == "legende-t")
    m = re.search(r"(\d+) organisations en lignée directe", legende)
    if not m or int(m.group(1)) != len(barres):
        faute("légende", f"compte annoncé {m.group(1) if m else '?'} pour {len(barres)} barres")

    # ---------- Bandes d'affiliation ----------
    bandes, sigles_bandes = [], []
    for g in racine.iter(S + "g"):
        if g.get("class") != "bande":
            continue
        rr = g.find(S + "rect")
        b = bbox(rr)
        q = g.get("data-parti")
        bandes.append((q, b))
        if g.get("data-certitude") != "documentee" and not rr.get("fill", "").startswith("url("):
            faute("bandes non datées pleines", f"{q} / {g.get('data-intl')}")
        bx, _, bw, _ = barres.get(q, (0, 0, 0, 0))
        if b[0] < bx - EPS or b[0] + b[2] > bx + bw + EPS:
            faute("R4 chevauchements", f"bande de {q} hors de l'étendue de sa barre")
        for t in g.findall(S + "text"):
            sigles_bandes.append((q, bbox(t)))
            if not dedans(bbox(t), b):
                faute("R4 textes", f"sigle « {t.text} » hors de sa bande")

    # ---------- Textes, renvois ----------
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
        elif cls == "nom-t":            # nom successif écrit dans sa barre (PC-SFIC, PCF)
            q = t.get("data-org")
            if q not in barres or not dedans(bbox(t), barres[q]):
                faute("R4 textes", f"nom « {t.text} » hors de la barre de {q}")
        elif cls == "renvoi":
            renvois[t.get("data-org")].append((bbox(t), "".join(t.itertext()), t.get("data-a"), t.get("data-b")))
    reliees = set()
    for q, rs in renvois.items():
        reliees.add(q)
        bord = min(tags.get(q, (1e9,))[0], barres.get(q, (1e9,))[0])
        rs.sort(key=lambda r: r[0][0])
        if bord - (rs[-1][0][0] + rs[-1][0][2]) > 24 or bord - (rs[-1][0][0] + rs[-1][0][2]) < -1:
            faute("R4 textes", f"renvois de {q} pas collés au début de la barre")
        for (b1, *_), (b2, *_) in zip(rs, rs[1:]):
            if not (-1 <= b2[0] - (b1[0] + b1[2]) <= 10):
                faute("R4 textes", f"renvois de {q} pas contigus")
        for b_, txt, a, b in rs:
            if a and b and a in majeures and b in majeures and not vue_famille                     and not txt.startswith(("membre de", "composante")):     # composante : pas une lignée
                faute("liens majeurs en renvoi", f"{a} -> {b} « {txt} »")

    # ---------- Liens : R1, seuils, croisements ----------
    obstacles = [(q, "barre", (b[0], b[1], b[2] + ouvertes.get(q, 0), b[3])) for q, b in barres.items()]
    obstacles += [(q, "étiquette", b) for q, b in tags.items()
                  if not dedans(b, (barres[q][0], barres[q][1], barres[q][2] + ouvertes.get(q, 0), barres[q][3]))]
    obstacles += [(q, "bande", b) for q, b in bandes] + [(q, "sigle de bande", b) for q, b in sigles_bandes]
    obstacles += [(q, "renvoi", r[0]) for q, rs in renvois.items() for r in rs]
    # Bandeau d'Internationale collé à sa section : c'est la bande de celle-ci, prolongée
    section_de = {r.get("data-id"): r.get("data-section") for r in racine.iter(S + "rect")
                  if "barre" in r.get("class", "").split() and r.get("data-section")}

    def a_soi(q, sorte, *bouts):
        return sorte in ("barre", "bande") and (q in bouts or section_de.get(q) in bouts)
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
        if g.get("data-rel") == "composante":
            # Composante : un trait vertical sans flèche, un point à chaque bout
            points_c = [c for c in g.findall(S + "circle") if "marque-composante" in c.get("class", "")]
            v = nombres(traits[0].get("d")) if len(traits) == 1 else []
            if len(traits) != 1 or fleches or len(points_c) != 2 or len(v) != 4 or abs(v[0] - v[2]) > 1e-6:
                faute("R1", f"{a}->{b} : composante mal dessinée")
                continue
            # Seule exception aux croisements : la barre d'un autre membre de la même organisation
            membres = {r["source"] for r in liens_csv if r["relation"] == "composante" and r["cible"] == b} - {a}
            for q, sorte, box in obstacles:
                if a_soi(q, sorte, a, b) or q in membres and sorte in ("barre", "bande"):
                    continue
                if croise((v[0], v[1]), (v[2], v[3]), box):
                    faute("croisements", f"{a}->{b} (composante) traverse {sorte} de {q}")
            continue
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
        if abs(f[0][0] - xb) > 1e-3 or abs(f[0][1] - yb) > 1e-3 or not (
                f[1][0] < f[0][0] and f[0][0] - f[1][0] >= 9 and abs(f[1][0] - f[2][0]) < 1e-6):
            faute("R1", f"{a}->{b} : flèche pas vers la droite ou trop petite")
        if g.get("data-majeur") != "oui":
            for attr, seuil in (("data-annees", s_ans), ("data-voies", s_voies), ("data-rangs", s_rangs)):
                if float(g.get(attr)) > seuil:
                    faute("R1", f"{a}->{b} : {attr} {g.get(attr)} au-delà du seuil {seuil:g}")
        if float(g.get("data-voies")) <= 2:
            for p1, p2 in zip(pts, pts[1:]):
                for q, sorte, box in obstacles:
                    if a_soi(q, sorte, a, b):
                        continue
                    if croise(p1, p2, box):
                        faute("croisements", f"{a}->{b} traverse {sorte} de {q}")
    for q in barres:
        if q not in reliees:
            faute("barres sans lien", f"{q} ({orgs.get(q, {}).get('label', '')})")

    # ---------- Marques de scission sur le texte d'une étiquette ----------
    textes_tags = [(t.get("data-org"), bbox(t)) for t in racine.iter(S + "text") if t.get("class") == "tag-t"]
    for c in racine.iter(S + "circle"):
        if "marque-scission" not in c.get("class", ""):
            continue
        cx, cy, r_ = float(c.get("cx")), float(c.get("cy")), float(c.get("r"))
        for q, b in textes_tags:
            if chevauche((cx - r_, cy - r_, 2 * r_, 2 * r_), b):
                faute("R4 chevauchements", f"cercle de scission sur l'étiquette de {q}")

    # ---------- Chevauchements (barres, étiquettes, bandes, renvois) ----------
    boites = [(q, "barre", (b[0], b[1], b[2] + ouvertes.get(q, 0), b[3])) for q, b in barres.items()]
    boites += [(q, "étiquette", b) for q, b in tags.items()] + [(q, "bande", b) for q, b in bandes]
    boites += [(q, "renvoi", r[0]) for q, rs in renvois.items() for r in rs]
    boites.sort(key=lambda x: x[2][0])
    for i, (qa, sa, ba) in enumerate(boites):
        for qb, sb, bb in boites[i + 1:]:
            if bb[0] >= ba[0] + ba[2]:
                break
            if qa == qb and {sa, sb} <= {"barre", "étiquette"}:
                continue          # étiquette dans sa propre barre
            if chevauche(ba, bb):
                faute("R4 chevauchements", f"{sa} de {qa} / {sb} de {qb}")


def verifier_donnees(cpt, err):
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
        if r.get("citation2") and not corpus.verifier(r["citation2"], r.get("source_citation2", "")):
            faute("citations introuvables", f"lien indirect {r['source_nom']} -> {r['cible_nom']}")
        m = re.match(r"\s*\|\s*([^=|]+?)\s*=", r.get("citation", ""))
        champ = preuves.type_du_champ(m.group(1)) if m else None
        if (champ == "scission" and r["relation"] != "scission") or \
                (champ == "fusion" and r["relation"] not in ("fusion", "renommage", "absorption")):
            faute("types contredits", f"{r['source_nom']} -> {r['cible_nom']} : « {r['relation']} » / champ « {champ} »")
    for r in lire("affiliations.csv"):
        if r["party_id"] in affiches and r.get("preuve") != "manuel"                 and not corpus.verifier(r.get("citation", ""), r.get("source_citation", "")):
            faute("citations introuvables", f"affiliation {r['party_nom']} / {r['international_nom']}")
    expliques = {r["label"] for r in lire("elagage_rejets.csv") if r["raison"].startswith("incontournable absent")}
    for r in lire("incontournables.csv", MANUEL):
        if r["id"] not in affiches and r["nom"] not in expliques:
            faute("incontournables inexpliqués", r["nom"])


COMPTEURS = ["liens flottants", "barres sans lien", "barres non datées", "étiquettes en double", "croisements",
             "bandes non datées pleines", "successions avec scission", "R1", "R2", "R3 dates", "R4 textes",
             "R4 chevauchements", "R5", "R6", "citations introuvables", "types contredits",
             "liens majeurs en renvoi", "incontournables inexpliqués", "étiquettes après une fin",
             "textes < 11 px", "légende"]


def main():
    fichiers = sys.argv[1:] or sorted(glob.glob(os.path.join(ARBRES, "arbre*.svg")))
    cpt, err = Counter(), []
    for f in fichiers:
        verifier_svg(f, cpt, err)
    verifier_donnees(cpt, err)
    print("Rapport de vérification (" + ", ".join(os.path.basename(f) for f in fichiers) + ")")
    print(f"  barres dessinées (arbre complet) : {cpt['_barres']}")
    for c in COMPTEURS:
        print(f"  {c:<30} {cpt[c]:>4}  {'OK' if cpt[c] == 0 else 'ÉCHEC'}")
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
