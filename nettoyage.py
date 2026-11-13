"""
Phase 1 : nettoyage des données, sans aucun dessin.

Entrées (jamais modifiées) :
    data/noeuds.csv, data/aretes.csv            (Wikidata, arbre.py)
    data/wp_noeuds.csv, data/wp_aretes.csv      (Wikipédia, infobox.py)
    data/corrections_noeuds.csv, data/corrections_aretes.csv   (corrections manuelles)
    data/cache_wikidata_orgs.json, data/cache_wikitext.json    (caches : pays, types, dates, catégories)
Sorties : data/sortie/*.csv, data/sortie/criteres.md, data/sortie/resume.md
          data/manuel/sigles.csv (créé s'il n'existe pas, sinon seules les lignes manquantes sont ajoutées)

Aucun accès réseau : tout est lu dans les caches.
Usage : python nettoyage.py
"""

import csv
import json
import os
import re
from collections import Counter, defaultdict, deque

from fusion import (ANCIEN, FRANCE, HUMAIN, NON_POLITIQUE, POLITIQUE, RX_CAT_DISPARU,
                    RX_CATEGORIE, RX_DROITE, RX_ETRANGER_CAT, RX_FRANCE_CAT, RX_GAUCHE,
                    RX_NOM_GAUCHE)
from fusion import INTERNATIONALE as TYPES_INTERNATIONALE

DATA = "data"
SORTIE = os.path.join(DATA, "sortie")
MANUEL = os.path.join(DATA, "manuel")
LIGNEE = ("filiation", "scission", "passage")
ORDRE_TYPES = ["appartenance", "filiation", "scission", "passage"]

# ---------- Internationales et fédérations européennes (par le nom, en plus des types Wikidata) ----------
RX_INTER = re.compile(
    r"^(Internationale|Quatrième Internationale|Comité international|Comité pour une Internationale|"
    r"Comité de coordination pour la refondation|Comité ouvrier international|Ligue internationale|"
    r"Ligue communiste internationale|Entente internationale|Conférence internationale|"
    r"Rencontre internationale|Solidarité internationale|Union communiste internationaliste$|"
    r"Tendance marxiste internationale|Courant communiste international|"
    r"Fédération anarchiste internationale|Association internationale des travailleurs|"
    r"Union des partis socialistes pour l'action internationale|Centre marxiste révolutionnaire international|"
    r"Bureau international|Groupe .*Parlement européen|"
    r"Parti (de la gauche|socialiste|vert|démocrate|pirate|des socialistes) européens?)"
    r"|– Quatrième Internationale$|\beuropéen(ne)?s?$", re.I)
# Clé de couleur d'une Internationale (premier motif trouvé)
COULEURS_INTER = [
    ("trotskyste", r"quatrième|trotsk|reconstruction|Comité pour une Internationale ouvrière|"
                   r"Comité ouvrier international|Union communiste internationaliste|Tendance marxiste"),
    ("anarchiste", r"anarch|libertaire|Association internationale des travailleurs"),
    ("écologiste", r"\bverts?\b|écolog"),
    ("régionaliste", r"Alliance libre européenne"),
    ("gauche radicale", r"gauche européenne|Gauche anticapitaliste|Parti de la gauche|Gauche au Parlement"),
    ("communiste", r"communis|marxistes-léninistes"),
    ("socialiste", r"sociali|Internationale ouvrière$"),
]
SIGLES_INTER = {
    "Internationale ouvrière": "IO", "Internationale ouvrière socialiste": "IOS",
    "Internationale socialiste": "IS", "Internationale communiste": "IC",
    "Quatrième Internationale": "QI", "Comité pour une Internationale ouvrière": "CIO",
    "Comité international de la Quatrième Internationale": "CIQI",
    "Parti socialiste européen": "PSE", "Parti de la gauche européenne": "PGE",
    "Parti vert européen": "PVE", "Alliance libre européenne": "ALE",
    "Union communiste internationaliste": "UCI",
    "Union des partis socialistes pour l'action internationale": "UPSAI",
    "Centre marxiste révolutionnaire international": "CMRI",
}

# ---------- Familles (voies) et courants (couleurs) ----------
# (courant, motif, famille). Premier motif trouvé dans le nom, puis dans les autres sources.
COURANTS = [
    ("trotskyste", r"trotsk|quatrième internationale|lambert|pabl", "trotskystes"),
    ("maoïste", r"maoï|marxiste-léniniste|marxistes-léninistes|hoxha", "maoïstes"),
    ("anarcho-syndicaliste", r"anarcho-syndical|syndicalis", "anarchistes et libertaires"),
    ("communiste libertaire", r"communis\w* libertaire|plateform", "anarchistes et libertaires"),
    ("anarchiste", r"anarch|libertaire", "anarchistes et libertaires"),
    ("luxemburgiste / conseilliste", r"luxemburg|conseillis", "communistes"),
    ("communiste", r"communis|léninis|stalinis|bolch", "communistes"),
    ("écosocialiste", r"écosocialis", "écologistes"),
    ("écologiste", r"écolog|\bverts?\b", "écologistes"),
    ("radical", r"\bradica", "radicaux"),
    ("social-démocrate", r"social-d[ée]mocr|socialis", "socialistes"),
    ("régionaliste / autonomiste", r"régionalis|autonomis|indépendantis|breton|kanak|corse|occitan",
     None),
]
FAMILLES = ["socialistes", "radicaux", "écologistes", "communistes", "trotskystes", "maoïstes",
            "anarchistes et libertaires", "outre-mer"]
RX_OUTREMER = re.compile(r"guadeloup|martiniq|guyan|Réunion|réunionnais|\b974\b|mayott|kanak|"
                         r"calédoni|polynési|tahiti|wallis|futuna|saint-pierre-et-miquelon|antillais|"
                         r"outre-mer", re.I)
# Périmètre discutable : signalé, pas tranché
RX_DOUTEUX = re.compile(r"^Parti (républicain, radical et radical-socialiste|radical)( \([^)]*\))?$")

# ---------- Organisations étrangères repérées par le nom ----------
PAYS = (r"Canada|Québec|Belgique|Suisse|Angleterre|Écosse|Royaume-Uni|Irlande|Italie|Espagne|"
        r"Portugal|Allemagne|Autriche|Luxembourg|Pays-Bas|Grèce|Turquie|Russie|URSS|Pologne|"
        r"Suède|Danemark|Norvège|États-Unis|Mexique|Argentine|Brésil|Chili|Pérou|Bolivie|Japon|"
        r"Chine|Inde|Népal|Viêt Nam|Algérie|Tunisie|Maroc|Sénégal|Cameroun|Haïti|Australie")
RX_PAYS_NOM = re.compile(rf"\((?:[^)]*\b)?(?:{PAYS})\b[^)]*\)")
RX_LANGUE_NOM = re.compile(r"^(The|Partito|Partido|Circolo|Militant)\b|\b(Party|League|Tendency|"
                           r"Comunista|Operaio|Socialist|Workers|Independentists|of the)\b")

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre"]
RX_MOIS = re.compile(r"\b(" + "|".join(MOIS) + r")\s+(?:\d{1,2}\s+)?(1[89]\d\d|20\d\d)\b", re.I)
RX_CHAMP_DATE = re.compile(r"^\s*\|\s*(fondation|création|date de fondation|date fondation|"
                           r"disparition|dissolution)\s*=\s*(.*)$", re.I | re.M)

# Sigles connus, pour préremplir data/manuel/sigles.csv (nom sans qualificatif -> sigle)
SIGLES = {
    "Parti communiste français": "PCF", "Parti socialiste": "PS", "Lutte ouvrière": "LO",
    "Section française de l'Internationale ouvrière": "SFIO", "Ligue communiste révolutionnaire": "LCR",
    "Nouveau Parti anticapitaliste": "NPA", "Organisation communiste internationaliste": "OCI",
    "Parti socialiste unifié": "PSU", "La France insoumise": "LFI", "Parti de gauche": "PG",
    "Mouvement républicain et citoyen": "MRC", "Mouvement des citoyens": "MDC",
    "Fédération anarchiste": "FA", "Alternative libertaire": "AL", "Union communiste libertaire": "UCL",
    "Parti radical de gauche": "PRG", "Europe Écologie Les Verts": "EELV",
    "Les Écologistes – Europe Écologie Les Verts": "EELV", "Les Verts": "Verts",
    "Union démocratique bretonne": "UDB", "Parti ouvrier indépendant": "POI",
    "Parti des travailleurs": "PT", "Parti ouvrier français": "POF",
    "Fédération des travailleurs socialistes de France": "FTSF",
    "Parti ouvrier socialiste révolutionnaire": "POSR", "Parti socialiste de France": "PSdF",
    "Parti socialiste français": "PSF", "Parti socialiste révolutionnaire": "PSR",
    "Parti communiste internationaliste": "PCI", "Gauche républicaine et socialiste": "GRS",
    "Pôle de renaissance communiste en France": "PRCF",
    "Parti communiste des ouvriers de France": "PCOF",
    "Parti communiste marxiste-léniniste de France": "PCMLF", "Gauche prolétarienne": "GP",
    "Jeunesse communiste révolutionnaire": "JCR", "Mouvement jeunes communistes de France": "MJCF",
    "Union des étudiants communistes": "UEC", "Front de gauche": "FDG",
    "Parti républicain, radical et radical-socialiste": "PRRRS", "Révolution permanente": "RP",
    "Parti communiste révolutionnaire": "PCR", "Gauche unitaire": "GU",
    "Convention pour une alternative progressiste": "CAP",
    "Parti socialiste ouvrier et paysan": "PSOP", "Parti d'unité prolétarienne": "PUP",
    "Voix des travailleurs": "VdT", "Mouvement des progressistes": "MdP",
    "Nouvelle Union populaire écologique et sociale": "NUPES", "Nouveau Front populaire": "NFP",
    "Parti communiste révolutionnaire trotskiste": "PCRT", "Jeunesses communistes révolutionnaires": "JCR",
    "Fédération pour une gauche alternative": "FGA", "Parti socialiste guyanais": "PSG",
    "Parti progressiste martiniquais": "PPM", "Mouvement socialiste guadeloupéen": "MSG",
    "Parti communiste réunionnais": "PCR", "Parti communiste guadeloupéen": "PCG",
    "Parti communiste martiniquais": "PCM", "Ligue trotskyste de France": "LTF",
    "Union communiste": "UC", "Organisation révolutionnaire anarchiste": "ORA",
    "Organisation communiste libertaire": "OCL", "Confédération nationale du travail": "CNT",
}


# ---------- Lecture ----------

def lire(nom):
    chemin = os.path.join(DATA, nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lire_json(nom):
    chemin = os.path.join(DATA, nom)
    if not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def ecrire(nom, entetes, lignes, dossier=SORTIE):
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, nom), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(entetes)
        w.writerows(lignes)


def annee(s):
    m = re.match(r"-?(\d{4})", str(s or ""))
    return int(m.group(1)) if m else None


def nom_court(label):
    return re.sub(r" \((parti politique|organisation politique|France|parti français|"
                  r"organisation|mouvement politique)\)$", "", label)


def mois_infobox(texte, champs, an):
    """Mois d'une date d'infobox, seulement s'il accompagne l'année retenue."""
    if not an:
        return None
    for m in RX_CHAMP_DATE.finditer(texte):
        if m.group(1).lower() not in champs:
            continue
        valeur = re.sub(r"[\[\]{}|]", " ", m.group(2))
        for mm in RX_MOIS.finditer(valeur):
            if int(mm.group(2)) == an:
                return MOIS.index(mm.group(1).lower()) + 1
    return None


def main():
    os.makedirs(SORTIE, exist_ok=True)
    stats = Counter()
    wd = lire_json("cache_wikidata_orgs.json")
    wikitext = {(d["qid"] or f"fr:{t}"): d["text"] for t, d in lire_json("cache_wikitext.json").items()}

    # ================= 1. Fusion des nœuds =================
    noeuds = {}

    def nouveau(i, label):
        return dict(id=i, label=label, sources=set(), dates_f=[], dates_d=[], ideologies=[],
                    positionnement="", categories="", pays=[], pos_wd=[], types=[])

    for source, fichier, col_ideo in (("wikidata", "noeuds.csv", "ideologies_wikidata"),
                                      ("wikipedia", "wp_noeuds.csv", "ideologies_wikipedia")):
        lignes = lire(fichier)
        stats[f"noeuds_{source}"] = len(lignes)
        for r in lignes:
            d = noeuds.setdefault(r["id"], nouveau(r["id"], r["label"]))
            d["sources"].add(source)
            if source == "wikipedia":
                d["label"] = r["label"]     # libellé Wikipédia plus lisible
                d["positionnement"] = r.get("positionnement_wikipedia", "")
                d["categories"] = r.get("categories_wikipedia", "")
            if annee(r["fondation"]):
                d["dates_f"].append((annee(r["fondation"]), source))
            if annee(r["dissolution"]):
                d["dates_d"].append((annee(r["dissolution"]), source))
            d["ideologies"] += [(x, source) for x in r.get(col_ideo, "").split(" | ") if x]
    stats["noeuds_fusionnes"] = len(noeuds)

    # Compléments du cache Wikidata : pays, positionnement, types, dates (prioritaires)
    for q, d in noeuds.items():
        w = wd.get(q, {})
        d["pays"], d["pos_wd"], d["types"] = w.get("pays", []), w.get("pos", []), w.get("types", [])
        if w.get("debut"):
            d["dates_f"].insert(0, (w["debut"], "wikidata"))
        if w.get("fin"):
            d["dates_d"].insert(0, (w["fin"], "wikidata"))
        d["cats_article"] = RX_CATEGORIE.findall(wikitext.get(q, ""))
        for c in d["cats_article"]:     # « Organisme disparu en 1980 »
            m = re.search(r"(?:disparue?s?|dissoute?s?) en (\d{4})", c, re.I)
            if m:
                d["dates_d"].append((int(m.group(1)), "wikipedia:catégorie"))

    # Corrections manuelles des nœuds
    forcer = {}
    for r in lire("corrections_noeuds.csv"):
        forcer[r["id"]] = r["action"].strip().lower()
        d = noeuds.setdefault(r["id"], nouveau(r["id"], r["id"]))
        d.setdefault("cats_article", [])
        d["sources"].add("correction")
        if r.get("label"):
            d["label"] = r["label"]
        if annee(r.get("fondation")):
            d["dates_f"].insert(0, (annee(r["fondation"]), "correction"))
        if annee(r.get("dissolution")):
            d["dates_d"].insert(0, (annee(r["dissolution"]), "correction"))
        d["courants_manuels"] = [c.strip() for c in r.get("courants", "").split("|") if c.strip()]

    # Dates retenues : la première source (correction > Wikidata > Wikipédia), les autres notées
    for q, d in noeuds.items():
        for cle, liste, champs in (("fondation", d["dates_f"], ("fondation", "création",
                                    "date de fondation", "date fondation")),
                                   ("dissolution", d["dates_d"], ("disparition", "dissolution"))):
            an, src = liste[0] if liste else (None, "")
            d[cle], d[cle + "_source"] = an, src
            d[cle + "_autres"] = " | ".join(sorted({f"{a} ({s})" for a, s in liste if a != an}))
            d[cle + "_mois"] = mois_infobox(wikitext.get(q, ""), champs, an)

    # ================= 6. Trois ensembles =================
    def est_internationale(d):
        return bool(set(d["types"]) & TYPES_INTERNATIONALE or RX_INTER.search(d["label"]))

    def de_gauche(d):
        positions = " ".join(d["pos_wd"]) + " " + d["positionnement"]
        # « centre gauche » seul compte comme gauche ; avec « centre droit » ou « centrisme »
        # (ex. Renaissance, Alliance démocratique), non.
        sans_centre_gauche = re.sub(r"centre[- ]gauche", "", positions, flags=re.I)
        if RX_GAUCHE.search(sans_centre_gauche):
            return None
        if RX_DROITE.search(positions):
            return f"positionnement : {positions.strip()}"
        if RX_GAUCHE.search(positions):
            return None
        ideo = " ".join(x for x, _ in d["ideologies"])
        if any(re.search(rx, ideo + " " + d["label"], re.I) for _, rx, _ in COURANTS) \
                or RX_NOM_GAUCHE.search(d["label"]):
            return None
        return "ni positionnement de gauche ni courant reconnu"

    def francais(d):
        if d["pays"]:
            return FRANCE in d["pays"]
        if RX_PAYS_NOM.search(d["label"]) or RX_LANGUE_NOM.search(d["label"]):
            return False
        cats = d["categories"] + " " + " ".join(d["cats_article"])
        if RX_FRANCE_CAT.search(cats):
            return True
        return not RX_ETRANGER_CAT.search(cats)

    classe, raison = {}, {}
    for q, d in noeuds.items():
        f = forcer.get(q)
        if f == "exclure":
            classe[q], raison[q] = "exclu", "exclu à la main"
        elif f in ("inclure", "vivant", "disparu") or RX_DOUTEUX.search(d["label"]):
            classe[q] = "graphe"    # les radicaux : gardés et signalés, pas tranchés ici
        elif HUMAIN in d["types"]:
            classe[q], raison[q] = "exclu", "personne, pas organisation"
        elif est_internationale(d):
            classe[q] = "internationale"
        elif set(d["types"]) & NON_POLITIQUE and not set(d["types"]) & POLITIQUE:
            classe[q], raison[q] = "exclu", "pas une organisation politique (journal, librairie, think tank...)"
        elif (r := de_gauche(d)):
            classe[q], raison[q] = "exclu", r
        elif not francais(d):
            classe[q], raison[q] = "etranger", "hors de France"
        else:
            classe[q] = "graphe"

    # ================= Arêtes : fusion par (ancêtre, descendant) =================
    aretes = {}
    for source, fichier, col in (("wikidata", "aretes.csv", "relation_wikidata"),
                                 ("wikipedia", "wp_aretes.csv", "relation_wikipedia")):
        lignes = lire(fichier)
        stats[f"aretes_{source}"] = len(lignes)
        for r in lignes:
            a, b = r["ancetre"], r["descendant"]
            if a == b:
                stats["boucles"] += 1
                continue
            e = aretes.setdefault((a, b), dict(type=r["type"], sources=set(), relations=set()))
            e["sources"].add(source)
            e["relations"].add(r[col])
            if ORDRE_TYPES.index(r["type"]) > ORDRE_TYPES.index(e["type"]):
                e["type"] = r["type"]
    stats["aretes_fusionnees"] = len(aretes)
    for r in lire("corrections_aretes.csv"):
        cle = (r["ancetre"], r["descendant"])
        if r.get("action", "").strip().lower() == "supprimer":
            stats["corrections_suppression"] += aretes.pop(cle, None) is not None
        else:
            stats["corrections_ajout"] += 1
            aretes[cle] = dict(type=r["type"], sources={"correction"}, relations={"correction"})
            noeuds.setdefault(r["ancetre"], None)
            noeuds.setdefault(r["descendant"], None)
    # Extrémités inconnues (ne devrait pas arriver)
    for k in [k for k in aretes if not noeuds.get(k[0]) or not noeuds.get(k[1])]:
        stats["aretes_extremite_inconnue"] += 1
        del aretes[k]
    noeuds = {q: d for q, d in noeuds.items() if d}

    def lab(q):
        return noeuds[q]["label"]

    def debut(q):
        d = noeuds[q]
        return (d["fondation"], d["fondation_mois"] or 0) if d["fondation"] else None

    # ================= 2. Arêtes réciproques =================
    reciproques = []
    for a, b in sorted(aretes):
        if (a, b) not in aretes or (b, a) not in aretes:
            continue
        e1, e2 = aretes[(a, b)], aretes[(b, a)]
        if e1["type"] == "appartenance" and e2["type"] == "appartenance":
            # On garde le sens « membre -> Internationale / coalition »
            garde = (a, b) if classe.get(b) == "internationale" else (b, a)
            pourquoi = "appartenance : le membre pointe vers l'organisation parente"
        else:
            da, db = debut(a), debut(b)
            if da and db and da != db:
                garde = (a, b) if da < db else (b, a)
                pourquoi = "lignée : l'organisation la plus ancienne est l'ancêtre"
            else:
                garde = (a, b) if len(e1["sources"]) >= len(e2["sources"]) else (b, a)
                pourquoi = "dates égales ou manquantes : sens le plus attesté"
        retire = (garde[1], garde[0])
        eg, er = aretes[garde], aretes.pop(retire)
        eg["sources"] |= er["sources"]
        eg["relations"] |= er["relations"]
        types = [t for t in (eg["type"], er["type"]) if t != "appartenance"] or ["appartenance"]
        eg["type"] = max(types, key=ORDRE_TYPES.index)
        eg["reciproque"] = True
        reciproques.append([garde[0], lab(garde[0]), garde[1], lab(garde[1]), eg["type"], pourquoi])
    stats["reciproques"] = len(reciproques)
    ecrire("aretes_reciproques.csv", ["source", "source_nom", "cible", "cible_nom", "relation",
                                      "raison"], reciproques)

    # ================= Tri des arêtes selon les ensembles =================
    lignee, anomalies, hors, affil_brutes, nationales, inter_lignee, date_manquante = \
        [], [], [], [], [], [], []

    def ligne_anomalie(a, b, t, cause):
        return [a, b, t, noeuds[a]["fondation"] or "", noeuds[b]["fondation"] or "", cause,
                lab(a), lab(b), " | ".join(sorted(aretes[(a, b)]["sources"]))]

    for (a, b), e in sorted(aretes.items()):
        t, ca, cb = e["type"], classe[a], classe[b]
        if t == "appartenance":
            if ca == "internationale" and cb != "internationale":
                a, b, ca, cb = b, a, cb, ca      # « X a pour membre Y » écrit à l'envers
                stats["appartenances_retournees"] += 1
            if ca == "graphe" and cb == "internationale":
                affil_brutes.append((a, b, e))
            elif ca == "graphe" and cb == "graphe":
                nationales.append([a, lab(a), b, lab(b), " | ".join(sorted(e["sources"]))])
            else:
                hors.append([a, lab(a), b, lab(b), t, f"{ca} -> {cb}"])
            continue
        if ca == "internationale" and cb == "internationale":
            inter_lignee.append((a, b, t))
        elif "internationale" in (ca, cb) and "graphe" in (ca, cb):
            anomalies.append(ligne_anomalie(a, b, t, "type de relation erroné : lien de lignée entre "
                                            "une organisation et une Internationale (affiliation ?)"))
        elif ca == "graphe" and cb == "graphe":
            lignee.append((a, b, t, e))
        else:
            hors.append([a, lab(a), b, lab(b), t, f"{ca} -> {cb}"])

    # Voie externe : organisations étrangères liées à une organisation française du graphe
    voie_externe = set()
    for a, _, b, _, t, _ in hors:
        if t in LIGNEE:
            for x, y in ((a, b), (b, a)):
                if classe[x] == "etranger" and classe[y] == "graphe":
                    voie_externe.add(x)

    # ================= 3. Règle R1 : sens du temps =================
    def cause_inversion(a, b):
        fa, fb = noeuds[a]["fondation"], noeuds[b]["fondation"]
        fin_b = noeuds[b]["dissolution"]
        if fin_b and fin_b <= fa:
            return ("lien inversé : la cible a disparu avant la fondation de la source, "
                    "elle en est sans doute l'ancêtre")
        if fa - fb <= 2:
            return f"date erronée : écart de {fa - fb} an(s), une des deux dates est probablement fausse"
        return ("type de relation erroné : la cible existait déjà (adhésion, ralliement ou passage "
                "de militants plutôt que filiation ?)")

    valides = []
    for a, b, t, e in lignee:
        da, db = debut(a), debut(b)
        if not da or not db:
            date_manquante.append([a, lab(a), b, lab(b), t,
                                   "source" if not da else "cible"])
            continue
        if db[0] < da[0] or (db[0] == da[0] and da[1] and db[1] and db[1] < da[1]):
            anomalies.append(ligne_anomalie(a, b, t, cause_inversion(a, b)))
            continue
        e["meme_annee"] = db[0] == da[0] and not (da[1] and db[1] and db[1] > da[1])
        valides.append((a, b, t, e))

    # ================= 4. Réduction transitive des filiations =================
    # Une filiation A -> C est redondante s'il existe un autre chemin de lignée A -> B -> ... -> C
    # (filiations et scissions : ex. FTSF -> POSR (scission) -> PSF rend FTSF -> PSF redondant).
    fil = defaultdict(set)
    for a, b, t, _ in valides:
        if t in ("filiation", "scission"):
            fil[a].add(b)

    def chemin(a, c):
        """Chemin de lignée de a à c qui n'emprunte pas l'arête directe a -> c."""
        parent, file = {a: None}, deque([a])
        while file:
            x = file.popleft()
            for y in fil[x]:
                if (x, y) == (a, c) or y in parent:
                    continue
                parent[y] = x
                if y == c:
                    res = [c]
                    while parent[res[-1]] is not None:
                        res.append(parent[res[-1]])
                    return res[::-1]
                file.append(y)
        return None

    reduites, gardees = [], []
    for a, b, t, e in valides:
        if t == "filiation" and (p := chemin(a, b)):
            fil[a].discard(b)
            reduites.append([a, lab(a), b, lab(b), " -> ".join(lab(x) for x in p)])
        else:
            gardees.append((a, b, t, e))

    # Fusion (plusieurs ancêtres en filiation) et renommage (un seul ancêtre, un seul successeur)
    parents_fil, enfants_fil = defaultdict(list), defaultdict(list)
    for a, b, t, _ in gardees:
        if t == "filiation":
            parents_fil[b].append(a)
            enfants_fil[a].append(b)
    liens = []
    for a, b, t, e in gardees:
        rel = t
        if t == "filiation":
            if len(parents_fil[b]) >= 2:
                rel = "fusion"
            elif len(enfants_fil[a]) == 1:
                fin_a = noeuds[a]["dissolution"]
                if not fin_a or abs(fin_a - noeuds[b]["fondation"]) <= 1:
                    rel = "renommage"
        liens.append((a, b, rel, e))

    # ================= Fin de vie et activité =================
    successeur = {a for a, b, rel, _ in liens if rel in ("filiation", "fusion", "renommage")}
    for q, d in noeuds.items():
        cats_mortes = [c for c in d.get("cats_article", []) if RX_CAT_DISPARU.search(c)]
        d["actif"] = (not d["dissolution"] and q not in successeur
                      and not set(d["types"]) & ANCIEN and not cats_mortes
                      and not re.search(r"Catégorie:Ancien", d["categories"]))
        if forcer.get(q) in ("vivant", "disparu"):
            d["actif"] = forcer[q] == "vivant"
        d["fin_deduite"], d["fin_deduite_source"] = "", ""
        if not d["dissolution"] and not d["actif"]:
            succ = [noeuds[b]["fondation"] for a, b, rel, _ in liens
                    if a == q and rel in ("filiation", "fusion", "renommage")]
            if succ:
                d["fin_deduite"], d["fin_deduite_source"] = min(succ), "fondation du successeur"

    # ================= 8. Familles et courants =================
    for q, d in noeuds.items():
        textes = [(d["label"], "nom")]
        textes += [(c, "correction") for c in d.get("courants_manuels", [])]
        textes += [(x, s) for x, s in d["ideologies"]]
        textes += [(c, "wikipedia:catégorie") for c in d["categories"].split(" | ") if c]
        trouves = defaultdict(set)
        famille = None
        # Un courant saisi à la main décide de la famille ; sinon le nom, puis le reste.
        ordre = sorted(textes, key=lambda x: {"correction": 0, "nom": 1}.get(x[1], 2))
        for texte, src in ordre:
            for nom, rx, fam in COURANTS:
                if re.search(rx, texte, re.I):
                    trouves[nom].add(src)
                    if famille is None and fam:
                        famille = fam
        d["courants"] = trouves
        tout = " ".join([d["label"], d["categories"]] + d.get("cats_article", []))
        d["outre_mer"] = bool(RX_OUTREMER.search(tout))
        d["famille"] = "outre-mer" if d["outre_mer"] else (famille or "non classé")

    # ================= 9. Sigles =================
    def sigle_de(d):
        base = re.sub(r" \([^)]*\)$", "", d["label"])
        return SIGLES.get(base, "")

    graphe = {q for q in noeuds if classe[q] == "graphe"}
    datees = {q for q in graphe if noeuds[q]["fondation"]}
    sans_date = graphe - datees

    # Homonymes : on garde le qualificatif quand deux noms courts se confondent
    courts = Counter(nom_court(noeuds[q]["label"]) for q in graphe)
    def court(q):
        n = nom_court(noeuds[q]["label"])
        return noeuds[q]["label"] if courts[n] > 1 else n

    chemin_sigles = os.path.join(MANUEL, "sigles.csv")
    existants = {r["id"] for r in (csv.DictReader(open(chemin_sigles, encoding="utf-8"))
                                   if os.path.exists(chemin_sigles) else [])}
    nouveaux = [[q, sigle_de(noeuds[q]), court(q)] for q in sorted(graphe, key=lambda q: lab(q))
                if q not in existants]
    os.makedirs(MANUEL, exist_ok=True)
    if not existants:
        ecrire("sigles.csv", ["id", "sigle", "short_name"], nouveaux, dossier=MANUEL)
    elif nouveaux:
        with open(chemin_sigles, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(nouveaux)
    stats["sigles_ajoutes"] = len(nouveaux)
    stats["sigles_preremplis"] = sum(1 for n in nouveaux if n[1])

    # ================= Internationales et affiliations =================
    inter_utiles = {b for _, b, _ in affil_brutes}
    pred = defaultdict(list)
    for a, b, t in inter_lignee:
        da, db = debut(a), debut(b)
        if t == "filiation" and (not da or not db or da <= db):
            pred[b].append(a)
        else:
            anomalies.append(ligne_anomalie(a, b, t, "lien entre deux Internationales "
                                            + ("de sens contraire au temps" if t == "filiation"
                                               else f"de type {t}, non représenté")))
    # Les prédécesseurs des Internationales utilisées sont gardés aussi
    pile = list(inter_utiles)
    while pile:
        x = pile.pop()
        for p in pred[x]:
            if p not in inter_utiles:
                inter_utiles.add(p)
                pile.append(p)

    def cle_couleur(label):
        return next((c for c, rx in COULEURS_INTER if re.search(rx, label, re.I)), "autre")

    lignes_inter = []
    for q in sorted(inter_utiles, key=lambda q: (noeuds[q]["fondation"] or 9999, lab(q))):
        d = noeuds[q]
        base = re.sub(r" \([^)]*\)$", "", d["label"])
        lignes_inter.append([q, d["label"], SIGLES_INTER.get(base, ""), d["fondation"] or "",
                             d["dissolution"] or "", " | ".join(pred[q]), cle_couleur(d["label"])])

    lignes_affil = []
    for a, b, e in affil_brutes:
        da, di = noeuds[a], noeuds[b]
        # Période inconnue : durée de vie du parti, bornée par celle de l'Internationale
        fin_a = da["dissolution"] or da["fin_deduite"] or None
        debut_ = max(x for x in (da["fondation"], di["fondation"], 0) if x is not None) or ""
        fins = [x for x in (fin_a, di["dissolution"]) if x]
        fin_ = min(fins) if fins else ""
        lignes_affil.append([a, b, debut_, fin_, "unknown", " | ".join(sorted(e["sources"])),
                             lab(a), lab(b)])
    inter_sans_membre = {q for q in noeuds if classe[q] == "internationale"} - inter_utiles

    # ================= Écriture =================
    def courants_txt(d):
        return (" | ".join(sorted(d["courants"])),
                " | ".join(f"{c}: {', '.join(sorted(s))}" for c, s in sorted(d["courants"].items())))

    def douteux_de(q):
        """Raison pour laquelle le périmètre est discutable (à trancher à la main), ou vide."""
        d = noeuds[q]
        if RX_DOUTEUX.search(d["label"]):
            return "radicaux : gauche ou centre ?"
        if len(d["pays"]) > 1:
            return "plusieurs pays dans Wikidata"
        if d["famille"] == "non classé":
            return "aucun courant reconnu"
        return ""

    lignes_orgs = []
    for q in sorted(datees, key=lambda q: (noeuds[q]["fondation"], lab(q))):
        d = noeuds[q]
        ct, cs = courants_txt(d)
        lignes_orgs.append([q, d["label"], court(q), d["fondation"], d["fondation_mois"] or "",
                            d["fondation_source"], d["fondation_autres"], d["dissolution"] or "",
                            d["dissolution_mois"] or "", d["dissolution_source"],
                            d["fin_deduite"], d["fin_deduite_source"], "oui" if d["actif"] else "",
                            d["famille"], "oui" if d["outre_mer"] else "", ct, cs,
                            douteux_de(q),
                            " | ".join(sorted(d["sources"]))])
    ecrire("organisations.csv",
           ["id", "label", "nom_court", "fondation", "fondation_mois", "fondation_source",
            "fondation_autres_sources", "dissolution", "dissolution_mois", "dissolution_source",
            "fin_deduite", "fin_deduite_source", "actif", "famille", "outre_mer", "courants",
            "courants_sources", "perimetre_douteux", "sources"], lignes_orgs)

    lignes_liens = []
    for a, b, rel, e in sorted(liens, key=lambda x: (noeuds[x[1]]["fondation"], lab(x[0]))):
        if a in sans_date or b in sans_date:
            continue
        lignes_liens.append([a, b, rel, noeuds[b]["fondation"], noeuds[b]["fondation_mois"] or "",
                             "oui" if e.get("meme_annee") else "", "oui" if e.get("reciproque") else "",
                             " | ".join(sorted(e["sources"])), " | ".join(sorted(e["relations"])),
                             lab(a), lab(b)])
    ecrire("liens.csv", ["source", "cible", "relation", "date_evenement", "date_evenement_mois",
                         "meme_annee", "fusion_reciproque", "sources", "relations_brutes",
                         "source_nom", "cible_nom"], lignes_liens)

    ecrire("anomalies.csv", ["source", "target", "relation", "source_date", "target_date",
                             "probable_cause", "source_nom", "target_nom", "sources"], anomalies)
    ecrire("reduction_transitive.csv", ["source", "source_nom", "cible", "cible_nom",
                                        "chemin_conserve"], reduites)
    ecrire("liens_date_manquante.csv", ["source", "source_nom", "cible", "cible_nom", "relation",
                                        "extremite_sans_date"], date_manquante)
    lignes_sd = []
    for q in sorted(sans_date, key=lab):
        d = noeuds[q]
        ct, _ = courants_txt(d)
        lignes_sd.append([q, d["label"], d["famille"], ct, " | ".join(sorted(d["sources"]))])
    ecrire("sans_date.csv", ["id", "label", "famille", "courants", "sources"], lignes_sd)

    lignes_exclu = []
    for q in sorted(noeuds, key=lambda q: (raison.get(q, ""), lab(q))):
        if classe[q] in ("exclu", "etranger"):
            lignes_exclu.append([q, lab(q), raison[q], "oui" if q in voie_externe else "",
                                 " | ".join(noeuds[q]["pays"])])
        elif q in inter_sans_membre:
            lignes_exclu.append([q, lab(q), "Internationale sans membre dans le graphe", "", ""])
    ecrire("perimetre_exclu.csv", ["id", "label", "raison", "voie_externe", "pays_wikidata"],
           lignes_exclu)
    ecrire("liens_hors_perimetre.csv", ["source", "source_nom", "cible", "cible_nom", "relation",
                                        "ensembles"], hors)
    ecrire("internationales.csv", ["id", "name", "sigle", "start", "end", "predecessor_id",
                                   "color_key"], lignes_inter)
    ecrire("affiliations.csv", ["party_id", "international_id", "start", "end", "date_certainty",
                                "source", "party_nom", "international_nom"], lignes_affil)
    ecrire("appartenances_nationales.csv", ["membre", "membre_nom", "organisation",
                                            "organisation_nom", "sources"], nationales)

    # ================= Résumé =================
    familles = Counter(noeuds[q]["famille"] for q in datees)
    rels = Counter(r[2] for r in lignes_liens)
    causes = Counter(r[5].split(" :")[0] for r in anomalies)
    raisons = Counter(r[2] for r in lignes_exclu)
    douteux = defaultdict(list)
    for q in sorted(datees, key=lab):
        if douteux_de(q):
            douteux[douteux_de(q)].append(noeuds[q]["label"])
    douteux_txt = "\n".join(f"- {r} ({len(l)}) : {', '.join(l)}" for r, l in douteux.items())
    nb_lignee_brut = sum(1 for e in aretes.values() if e["type"] != "appartenance")
    res = f"""# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | {stats['noeuds_wikidata']} |
| Wikipédia (wp_noeuds.csv) | {stats['noeuds_wikipedia']} |
| Après fusion par identifiant (+ corrections) | {len(noeuds)} |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **{len(datees)}** |
| Graphe, sans date de fondation (sans_date.csv) | {len(sans_date)} |
| Internationales et fédérations européennes gardées (internationales.csv) | {len(inter_utiles)} |
| Exclues (perimetre_exclu.csv) | {len(lignes_exclu)} |
| dont étrangères en voie externe | {len(voie_externe)} |

Raisons d'exclusion : {", ".join(f"{r} ({n})" for r, n in raisons.most_common())}.

Familles : {", ".join(f"{f} ({familles[f]})" for f in FAMILLES + ["non classé"] if familles[f])}.

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
{douteux_txt or "aucun"}

## Arêtes
| Étape | Nombre |
|---|---|
| Wikidata (aretes.csv) | {stats['aretes_wikidata']} |
| Wikipédia (wp_aretes.csv) | {stats['aretes_wikipedia']} |
| Boucles (une organisation vers elle-même) retirées | {stats['boucles']} |
| Après fusion par (ancêtre, descendant) | {stats['aretes_fusionnees']} |
| Corrections manuelles : ajouts / suppressions | {stats['corrections_ajout']} / {stats['corrections_suppression']} |
| Paires réciproques fusionnées (aretes_reciproques.csv) | {len(reciproques)} |
| Après fusion des réciproques | {len(aretes)}, dont {nb_lignee_brut} de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | {len(hors)} |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | {len(anomalies)} |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | {len(date_manquante)} |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | {len(reduites)} |
| **Liens du graphe (liens.csv)** | **{len(lignes_liens)}** |
| Affiliations à une Internationale (affiliations.csv) | {len(lignes_affil)} |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | {len(nationales)} |

Liens par relation : {", ".join(f"{r} ({n})" for r, n in rels.most_common())}.
Dont {sum(1 for r in lignes_liens if r[5])} entre deux organisations fondées la même année (mois inconnu) : colonne meme_annee.

Causes probables des anomalies : {", ".join(f"{c} ({n})" for c, n in causes.most_common())}.

Dates : {sum(1 for q in datees if noeuds[q]['fondation_mois'])} fondations et {sum(1 for q in datees if noeuds[q]['dissolution_mois'])} dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
{sum(1 for q in datees if noeuds[q]['fondation_autres'])} organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles : {stats['sigles_ajoutes']} lignes ajoutées à data/manuel/sigles.csv, dont {stats['sigles_preremplis']} préremplies.
"""
    with open(os.path.join(SORTIE, "resume.md"), "w", encoding="utf-8") as f:
        f.write(res)
    with open(os.path.join(SORTIE, "criteres.md"), "w", encoding="utf-8") as f:
        f.write(CRITERES)
    print(res)


CRITERES = """# Critères de répartition des nœuds (phase 1)

Chaque organisation (fusion de Wikidata, Wikipédia et des corrections manuelles, par identifiant)
est rangée dans un seul ensemble, dans cet ordre :

1. **Corrections manuelles** (data/corrections_noeuds.csv) : `exclure` -> exclue ;
   `inclure`, `vivant`, `disparu` -> graphe, sans autre test.
2. **Personne** (type Wikidata Q5) -> exclue.
3. **Internationale ou fédération européenne** -> internationales.csv, jamais un nœud du graphe.
   Critère : un type Wikidata d'organisation internationale (Q2716508, Q484652, Q24649, Q1194093),
   ou un nom qui commence par « Internationale », « Quatrième Internationale », « Comité
   international », « Comité pour une Internationale », « Ligue internationale », « Conférence
   internationale »..., qui finit par « – Quatrième Internationale » ou par « européen(ne) »,
   ou qui est un parti européen (PSE, PGE, PVE, ALE...).
   Seules sont gardées celles dont une organisation du graphe est membre, et leurs prédécesseurs.
   Les autres vont dans perimetre_exclu.csv.
4. **Pas une organisation politique** : type Wikidata de journal, librairie, think tank, syndicat...
   sans type de parti ou d'organisation politique -> exclue.
5. **Pas de gauche** : positionnement (Wikidata ou infobox) de droite ou du centre, ou ni
   positionnement de gauche, ni courant reconnu dans le nom ou les idéologies -> exclue.
6. **Étrangère** -> perimetre_exclu.csv (raison « hors de France »). Critère : pays Wikidata
   (P17) autre que la France ; à défaut, un pays entre parenthèses dans le nom (« (Canada) »),
   un nom dans une autre langue (« The... », « Partito... », « ...Party »), ou des catégories
   Wikipédia d'un autre pays sans catégorie française.
   Une organisation étrangère reliée par une lignée à une organisation du graphe est marquée
   voie_externe = oui : elle sera dessinée dans une voie externe discrète, sans lien.
7. Sinon : **graphe** (organisations de gauche françaises, outre-mer compris).
   Sans date de fondation : sans_date.csv, pas de barre ni de lien.

Positionnement : « centre gauche » seul compte comme gauche ; accompagné de « centre droit » ou
« centrisme », l'organisation est exclue.

Gardés dans le graphe mais signalés dans la colonne perimetre_douteux, à trancher à la main :
« Parti républicain, radical et radical-socialiste » et « Parti radical » ; les organisations
que Wikidata place dans plusieurs pays ; celles dont aucun courant n'est reconnu.

## Famille (voie) et courants (couleur)

Courants : motifs cherchés dans le nom, les courants saisis à la main, les idéologies (Wikidata,
Wikipédia) et les catégories Wikipédia. Plusieurs courants possibles ; la colonne
courants_sources indique d'où vient chacun.

Famille : celle du premier courant trouvé, en lisant d'abord le courant saisi à la main, puis le
nom, puis les autres sources. Ordre de priorité des courants : trotskyste, maoïste,
anarcho-syndicaliste, communiste libertaire, anarchiste, luxemburgiste / conseilliste,
communiste, écosocialiste, écologiste, radical, social-démocrate.
Familles : socialistes, radicaux, écologistes, communistes, trotskystes, maoïstes, anarchistes et
libertaires, outre-mer. Une organisation d'outre-mer (nom ou catégories : Guadeloupe, Martinique,
Guyane, La Réunion, Mayotte, Nouvelle-Calédonie, Polynésie...) va dans la voie outre-mer et garde
ses courants. Sans courant reconnu : « non classé ».

## Liens

- Fusion par (ancêtre, descendant) ; type le plus informatif : passage > scission > filiation.
- Paires réciproques (A -> B et B -> A) : un seul lien, dans le sens du temps (l'organisation la
  plus ancienne est l'ancêtre) ; à date égale ou inconnue, le sens le plus attesté.
- R1 : un lien dont la cible est fondée avant la source (année, ou mois si les deux sont connus)
  va dans anomalies.csv avec une cause probable. Même année sans mois : gardé, meme_annee = oui.
- Lien de lignée entre une organisation et une Internationale : anomalies.csv.
- Réduction transitive des filiations : la filiation A -> C est retirée s'il existe un autre
  chemin de lignée (filiations et scissions) A -> B -> ... -> C.
- Relation finale : fusion (cible à plusieurs ancêtres en filiation), renommage (un seul ancêtre
  qui n'a qu'un successeur, et qui disparaît au plus un an avant ou après), filiation, scission,
  passage. Date de l'événement : fondation de la cible.
- « Membre de » vers une Internationale : affiliations.csv. Vers une organisation française
  (coalition, fédération) : appartenances_nationales.csv.
"""

if __name__ == "__main__":
    main()
