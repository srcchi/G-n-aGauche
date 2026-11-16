"""Étape 3b : périodes d'adhésion lues dans les tableaux des membres des Internationales.

Les articles des Internationales (en et fr) ont souvent un tableau « pays | organisation | années »
(ex. en:Second International : « [[French Workers' Party]] (POF) | 1889–1902 »). Pour chaque ligne
française, on garde l'organisation liée (résolue en identifiant Wikidata), les années et la
citation mot pour mot de la ligne dans le wikitexte en cache (règle R8, revérifiée par verifier.py).

Réseau : seulement les articles et résolutions absents du cache (voir enrichissement.py).
Produit : data/sortie/affiliations_tableaux.csv, lu par nettoyage.py.
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrichissement as en  # noqa: E402
import porte  # noqa: E402

SORTIE = en.SORTIE
RX_TABLE = re.compile(r"^\{\|.*?^\|\}", re.S | re.M)
RX_LIEN = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
RX_ANNEES_TITRE = re.compile(r"year|period|membership|affiliat|joined|admitted|since|ann[ée]e|p[ée]riode|adh[ée]sion|"
                             r"depuis|status|statut", re.I)
RX_FRANCE = re.compile(r"\{\{\s*(?:flag(?:icon|country|deco)?\s*\|\s*(?:French Third Republic|France)|FRA)\b|"
                       r"\[\[France\]\]|^\s*France\s*$|\bFrance\b(?!\s*\()", re.I | re.M)
AN = r"(1[89]\d\d|20\d\d)"
RX_PERIODE = re.compile(AN + r"\s*(?:[–—-]|&ndash;|to|à|au)\s*(?:" + AN + r"|present|today|aujourd'hui|présent)?", re.I)
RX_DEPUIS = re.compile(r"(?:since|depuis|from)\s+" + AN, re.I)
RX_SEUL = re.compile(r"^\s*(?:\{\{[^{}]*\}\}\s*)?" + AN + r"\s*$")


def cellules(ligne_brute):
    """Cellules d'une ligne de tableau, avec leur texte brut exact et leurs attributs."""
    res = []
    for ligne in ligne_brute.split("\n"):
        if not ligne[:1] in ("|", "!") or ligne.startswith(("|-", "|+", "|}")):
            if res:          # suite de la cellule précédente sur plusieurs lignes
                res[-1]["texte"] += "\n" + ligne
            continue
        sep = "!!" if ligne[0] == "!" else "||"
        for morceau in ligne[1:].split(sep):
            attrs, texte = "", morceau
            # « rowspan="2" | texte » : attributs avant un | simple qui n'est pas dans un lien ou un modèle
            m = re.match(r"^([^\[\]{}|]*=[^\[\]{}|]*)\|(?!\|)(.*)$", morceau, re.S)
            if m:
                attrs, texte = m.group(1), m.group(2)
            rs = re.search(r"rowspan\s*=\s*\"?(\d+)", attrs)
            res.append(dict(texte=texte, rowspan=int(rs.group(1)) if rs else 1, entete=ligne[0] == "!"))
    return res


def periode(texte):
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|\{\{(?:sfn|efn|r)\|[^{}]*\}\}", "", texte, flags=re.S)
    t = t.replace("&ndash;", "–")
    m = RX_PERIODE.search(t)
    if m:
        fin = m.group(2) or ("toujours membre" if re.search(r"present|today|aujourd|présent", m.group(0), re.I)
                             else "")
        if not fin and re.search(AN + r"\s*[–—-]\s*$", t.strip()):
            fin = "toujours membre"
        return m.group(1), fin
    m = RX_DEPUIS.search(t)
    if m:
        return m.group(1), "toujours membre"
    m = RX_SEUL.match(t)
    if m:
        return m.group(1), ""
    return None


def lignes_francaises(texte):
    """(titre lié, début, fin, citation) pour chaque ligne française d'un tableau avec une colonne d'années."""
    for table in RX_TABLE.findall(texte):
        rangees = re.split(r"\n\|-[^\n]*", table)
        entetes = [c for r in rangees[:3] for c in cellules(r) if c["entete"]]
        if not any(RX_ANNEES_TITRE.search(c["texte"]) for c in entetes):
            continue
        en_cours = []            # (colonne, texte, rangées restantes) : cellules à rowspan
        for brute in rangees:
            cs = cellules(brute)
            if not cs or all(c["entete"] for c in cs) and not RX_LIEN.search(brute):
                continue
            herites = [t for _, t, n in en_cours if n > 0]
            en_cours = [(i, t, n - 1) for i, t, n in en_cours if n - 1 > 0]
            for i, c in enumerate(cs):
                if c["rowspan"] > 1:
                    en_cours.append((i, c["texte"], c["rowspan"] - 1))
            tout = herites + [c["texte"] for c in cs]
            if not any(RX_FRANCE.search(t) for t in tout):
                continue
            # L'organisation : premier lien d'une cellule de cette rangée (pas d'un drapeau ni d'un fichier)
            lien, i_lien = None, None
            for i, c in enumerate(cs):
                for m in RX_LIEN.finditer(c["texte"]):
                    if not re.match(r"(?:File|Fichier|Image|Category|Catégorie):", m.group(1), re.I) \
                            and m.group(1).strip() != "France":
                        lien, i_lien = m, i
                        break
                if lien:
                    break
            if not lien:
                continue
            per = None
            for c in cs[i_lien + 1:]:
                per = periode(c["texte"])
                if per:
                    fin_cit = c["texte"]
                    break
            if not per:
                continue
            # Citation : de la cellule de l'organisation à celle des années, telle quelle dans le wikitexte
            debut_i = brute.find(cs[i_lien]["texte"])
            fin_i = brute.find(fin_cit, debut_i) + len(fin_cit)
            citation = brute[debut_i:fin_i].strip()
            if debut_i < 0 or fin_i <= debut_i or len(citation) > 500 or citation not in texte:
                continue
            yield lien.group(1).strip(), per[0], per[1], citation


def main():
    inter = list(csv.DictReader(open(os.path.join(SORTIE, "internationales.csv"), encoding="utf-8")))
    en.entites([r["id"] for r in inter])
    trouves = []
    for r in inter:
        liens = en.cache["entites"].get(r["id"], {}).get("liens", {})
        for lang in ("en", "fr"):
            titre = liens.get(lang)
            if not titre:
                continue
            texte = en.wikitextes(lang, [titre]).get(titre) or ""
            for t, d, f, cit in lignes_francaises(texte):
                trouves.append((r["id"], r["name"], lang, titre, t, d, f, cit))
    res = {}
    for lang in ("en", "fr"):
        res.update({(lang, k): v for k, v in en.resoudre(lang, [x[4] for x in trouves if x[2] == lang]).items()})
    en.sauver_cache()
    lignes, vus = [], set()
    for q_i, nom_i, lang, titre, t, d, f, cit in trouves:
        q_p = res.get((lang, t), (t, None))[1] or (f"fr:{res.get((lang, t), (t,))[0]}" if lang == "fr" else "")
        if not q_p or (q_p, q_i, d) in vus:
            continue
        vus.add((q_p, q_i, d))
        lignes.append([q_p, q_i, d, f, f"{lang}:{t}", nom_i, cit, f"{lang}:{titre}"])
    # Addendum 4, 1 : seules les organisations politiques (pas les dirigeants, régions culturelles,
    # syndicats comme la CGT...) ; chaque rejet est noté avec sa raison
    rejets = porte.rejets({l[0] for l in lignes}, exemptes=porte.ids_manuels())
    ecartees = [l for l in lignes if l[0] in rejets]
    lignes = [l for l in lignes if l[0] not in rejets]
    with open(os.path.join(SORTIE, "rejets_porte_tableaux.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "label", "raison", "international_nom", "source_citation"])
        w.writerows(sorted([l[0], l[4], rejets[l[0]], l[5], l[7]] for l in ecartees))
    lignes.sort(key=lambda x: (x[1], x[2], x[0]))
    with open(os.path.join(SORTIE, "affiliations_tableaux.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["party_id", "international_id", "start", "end", "party_titre", "international_nom",
                    "citation", "source_citation"])
        w.writerows(lignes)
    print(f"{len(lignes)} adhésions françaises lues dans les tableaux des Internationales, "
          f"{len(ecartees)} lignes écartées par la porte politique (data/sortie/rejets_porte_tableaux.csv)")


if __name__ == "__main__":
    main()
