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
import unicodedata
from collections import Counter, defaultdict, deque

from fusion import (ANCIEN, FRANCE, HUMAIN, NON_POLITIQUE, POLITIQUE, RX_CAT_DISPARU,
                    RX_CATEGORIE, RX_DROITE, RX_ETRANGER_CAT, RX_FRANCE_CAT, RX_GAUCHE,
                    RX_NOM_GAUCHE)
from fusion import INTERNATIONALE as TYPES_INTERNATIONALE

DATA = "data"
SORTIE = os.path.join(DATA, "sortie")
MANUEL = os.path.join(DATA, "manuel")
LIGNEE = ("filiation", "scission", "passage")
ORDRE_TYPES = ["appartenance", "emanation", "filiation", "scission", "passage"]
# Types des liens saisis à la main ou validés (phase 0) -> types internes
TYPE_LIEN_MANUEL = {"filiation": "filiation", "renommage": "filiation", "fusion": "filiation",
                    "scission": "scission", "passage_militants": "passage", "passage": "passage",
                    "emanation": "emanation"}

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
    ("écosocialiste", r"écosocialis", "socialistes"),   # PG, LFI : gauche socialiste, pas écologie politique
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

# Idéologies hors périmètre, qui l'emportent sur un positionnement « gauche » (Wikidata en a d'erronés)
# (?<!anti) : « antifascisme » ou « antimonarchisme » ne doivent pas exclure
RX_IDEO_DROITE = re.compile(r"(?<!anti)(?<!anti-)(?:royalis|monarchi|bonapartis|légitimis|orléanis|"
                            r"fascis|national-socialis|social-national|collaborationnis|pétainis)|"
                            r"anti-?indépendantis|algérie française|nationalisme intégral", re.I)
# Le nom seul suffit à classer à gauche, sans « internationale » (Agence internationale de l'énergie)
RX_NOM_GAUCHE_STRICT = re.compile(r"gauche|sociali|communis|ouvri|travailleu|révolution|anarch|"
                                  r"libertaire|trotsk|maoï|marxis|léninis|prolétar|syndical|insoumis|"
                                  r"front populaire|spartak|bolch", re.I)
# Types Wikidata d'organismes qui ne sont pas des organisations politiques
NON_POLITIQUE_PLUS = {
    "Q245065",     # organisation intergouvernementale
    "Q327333",     # agence gouvernementale
    "Q3754526",    # direction d'administration centrale
    "Q18087867",   # service de l'État
    "Q848197",     # groupe parlementaire
    "Q779079",     # groupe politique du Parlement européen
}

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


# ---------- Types d'organisation (étape 6) ----------
TYPES = ["parti_ou_organisation", "coalition", "satellite", "groupe_arme", "syndicat",
         "club_ou_cercle", "media", "etrangere", "international_ou_federation_europeenne"]
# Liste explicite des coalitions (demandée) ; comparaison sans accents ni casse
COALITIONS = ["Front populaire", "Front populaire (France)", "Nouvelle Union populaire écologique et sociale",
              "Nouveau Front populaire", "Gauche plurielle", "Front de gauche", "Front de gauche (France)",
              "Cartel des gauches", "Programme commun", "Programme commun de la gauche",
              "Union de la gauche", "Bloc des gauches", "bloc des gauches",
              "Fédération de la gauche démocrate et socialiste"]
# (type, motif) lus dans les libellés des types Wikidata (P31), dans l'ordre de priorité
TYPE_PAR_LIBELLE = [
    ("coalition", r"coalition|alliance électorale|cartel électoral|union électorale|front électoral"),
    ("groupe_arme", r"groupe armé|organisation armée|terroris|guérilla|milice|paramilitaire"),
    ("satellite", r"jeunesse|organisation étudiante|syndicat étudiant|association étudiante|"
                  r"organisation de femmes|organisation féministe"),
    ("syndicat", r"syndicat|confédération syndicale|centrale syndicale"),
    ("club_ou_cercle", r"\bclub|cercle|société de pensée|think tank|laboratoire d'idées|groupe de réflexion"),
    ("media", r"journal|périodique|revue|presse|média|maison d'édition"),
    ("satellite", r"\bcollectif|association"),
]
TYPE_PAR_INFOBOX = [
    ("parti_ou_organisation", r"parti politique|parti"),
    ("coalition", r"coalition|alliance"),
    ("groupe_arme", r"groupe armé|organisation armée|terroris"),
    ("syndicat", r"syndicat"),
    ("media", r"presse|périodique|média|journal"),
]
TYPE_PAR_CATEGORIE = [
    ("coalition", r"coalition|alliance électorale|union électorale"),
    ("groupe_arme", r"organisation armée|groupe armé|faction armée|lutte armée|terroris"),
    ("satellite", r"organisation de jeunesse|mouvement de jeunesse|syndicat étudiant|"
                  r"organisation étudiante|association étudiante|jeunesse politique|organisation de femmes"),
    ("syndicat", r"\bsyndicat"),
    ("club_ou_cercle", r"club politique|société de pensée|club révolutionnaire"),
    ("media", r"\bpresse|périodique|\brevue|\bjournal"),
]
RX_SEMBLE_INTER = re.compile(r"Internationale|Confédération internationale|Quatrième Internationale")
CACHE_TYPES = os.path.join(SORTIE, "cache_types.json")


def libelles_types(ids):
    """Libellé français des types Wikidata (P31), avec cache (data/sortie/cache_types.json)."""
    cache = lire_json(os.path.join("sortie", "cache_types.json"))
    manquants = sorted(i for i in ids if i not in cache)
    import requests
    for k in range(0, len(manquants), 200):
        lot = manquants[k:k + 200]
        print(f"  libellés des types Wikidata {k + len(lot)}/{len(manquants)}")
        q = ("SELECT ?t ?l WHERE { VALUES ?t { %s } OPTIONAL { ?t rdfs:label ?l . "
             "FILTER(LANG(?l) = 'fr') } }" % " ".join(f"wd:{i}" for i in lot))
        r = requests.post("https://query.wikidata.org/sparql", data={"query": q, "format": "json"},
                          headers={"User-Agent": "G-n-aGauche/0.3 (https://github.com/srcchi/G-n-aGauche) "
                                                 "python-requests",
                                   "Accept": "application/sparql-results+json"}, timeout=120)
        r.raise_for_status()
        for i in lot:
            cache.setdefault(i, "")
        for b in r.json()["results"]["bindings"]:
            cache[b["t"]["value"].rsplit("/", 1)[-1]] = b.get("l", {}).get("value", "")
        with open(CACHE_TYPES, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    return cache


def classer_types(noeuds, classe, wikitext, stats, aretes=None):
    """Type de chaque organisation : types.csv (saisi à la main) d'abord, sinon préremplissage
    par la liste des coalitions, les types Wikidata, le modèle d'infobox et les catégories.
    Jamais par des mots du nom seuls."""
    a_classer = [q for q in noeuds if classe[q] in ("graphe", "internationale", "etranger")]
    saisis = {r["id"]: r for r in lire(os.path.join("manuel", "types.csv"))}
    libs = libelles_types({t for q in a_classer for t in noeuds[q]["types"]})
    coalitions = {normaliser(c) for c in COALITIONS}
    n_lignee = Counter()
    for (a, b), e in (aretes or {}).items():
        if e["type"] in ("filiation", "scission", "passage"):
            n_lignee[a] += 1
            n_lignee[b] += 1
    types_org, lignes = {}, []
    for q in a_classer:
        d = noeuds[q]
        if classe[q] == "internationale":
            t, pourquoi = "international_ou_federation_europeenne", "type Wikidata ou nom d'Internationale"
        elif classe[q] == "etranger":
            t, pourquoi = "etrangere", "hors de France (voir perimetre_exclu.csv)"
        elif normaliser(d["label"]) in coalitions:
            t, pourquoi = "coalition", "liste explicite des coalitions"
        else:
            t = pourquoi = None
            libelles = [libs.get(x, "") for x in d["types"]]
            texte = wikitext.get(q, "")
            m_inf = re.search(r"\{\{\s*Infobox\s+([^\n|}]+)", texte, re.I)
            infobox = m_inf.group(1).strip().lower() if m_inf else ""
            cats = " | ".join(d.get("cats_article", [])) + " | " + d["categories"]
            # Jeunesse, étudiants, sections locales, groupes parlementaires : avant « parti politique »,
            # car ces organisations ont souvent aussi le type « organisation politique ».
            l_sat = next((l for l in libelles if re.search(
                r"jeunesse|étudiant|section locale|fédération départementale|\bcellule", l, re.I)), None)
            l_grp = next((l for l in libelles if re.search(r"groupe parlementaire|groupe politique", l, re.I)),
                         None)
            if l_sat:
                t, pourquoi = "satellite", f"type Wikidata : {l_sat}"
            elif l_grp:
                t, pourquoi = "coalition", f"type Wikidata : {l_grp} (groupe d'élus, pas une organisation)"
            elif any(re.search(r"parti politique|organisation politique|mouvement politique", l, re.I)
                     for l in libelles):
                t, pourquoi = "parti_ou_organisation", "type Wikidata : " + ", ".join(l for l in libelles if l)
            elif re.search(r"parti", infobox):
                t, pourquoi = "parti_ou_organisation", f"infobox « {m_inf.group(1).strip()} »"
            if t is None:
                for typ, rx in TYPE_PAR_LIBELLE:
                    l = next((l for l in libelles if re.search(rx, l, re.I)), None)
                    if l:
                        t, pourquoi = typ, f"type Wikidata : {l}"
                        break
            if t is None and infobox:
                for typ, rx in TYPE_PAR_INFOBOX:
                    if re.search(rx, infobox, re.I):
                        t, pourquoi = typ, f"infobox « {m_inf.group(1).strip()} »"
                        break
            if t is None:
                for typ, rx in TYPE_PAR_CATEGORIE:
                    m = re.search(rf"[^|]*(?:{rx})[^|]*", cats, re.I)
                    if m:
                        t, pourquoi = typ, f"catégorie : {m.group(0).strip()}"
                        break
            if t is None:
                t, pourquoi = "parti_ou_organisation", "aucun indice contraire"
        drapeaux = []
        if classe[q] == "graphe" and RX_SEMBLE_INTER.search(d["label"]) and "Section française" not in d["label"]:
            drapeaux.append("ressemble à une Internationale : à vérifier")
        if RX_DOUTEUX.search(d["label"]):
            drapeaux.append("périmètre discutable (radicaux) : à trancher")
        if t in ("satellite", "coalition") and n_lignee.get(q):
            # Ex. la JCR (1966) : organisation de jeunesse, mais ancêtre de la Ligue communiste
            drapeaux.append(f"a {n_lignee[q]} lien(s) de lignée : la retirer coupe la généalogie, à vérifier")
        auto = (t, pourquoi + (" ; " + " ; ".join(drapeaux) if drapeaux else ""))
        s = saisis.get(q)
        if s and s.get("type", "").strip() in TYPES:
            types_org[q] = s["type"].strip()       # saisie à la main : prioritaire
            stats["types_saisis"] += 1
        else:
            types_org[q] = auto[0]
        lignes.append([q, d["label"], auto[0], auto[1], ""])
    stats.update({f"type_{t}": n for t, n in Counter(types_org.values()).items()})
    return types_org, lignes


def ecrire_manuel_types(lignes, stats):
    """data/manuel/types.csv : créé une fois ; ensuite, seules les nouvelles organisations sont ajoutées."""
    chemin = os.path.join(MANUEL, "types.csv")
    existants = set()
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            existants = {r["id"] for r in csv.DictReader(f)}
    nouvelles = [l for l in sorted(lignes, key=lambda l: (l[2] != "parti_ou_organisation", l[2], l[1]))
                 if l[0] not in existants]
    os.makedirs(MANUEL, exist_ok=True)
    if not existants:
        ecrire("types.csv", ["id", "name", "type", "reason", "valide"], nouvelles, dossier=MANUEL)
    elif nouvelles:
        with open(chemin, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(nouvelles)
    stats["types_ajoutes"] = len(nouvelles)


def normaliser(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def main():
    os.makedirs(SORTIE, exist_ok=True)
    stats = Counter()
    wd = lire_json("cache_wikidata_orgs.json")
    wikitext = {(d["qid"] or f"fr:{t}"): d["text"] for t, d in lire_json("cache_wikitext.json").items()}
    # Articles téléchargés en phase 0 (enrichissement.py) : titre français donné par Wikidata
    enrich = lire_json(os.path.join("sortie", "cache_enrichissement.json"))
    for q, e in enrich.get("entites", {}).items():
        t = e.get("liens", {}).get("fr")
        if t and not wikitext.get(q) and enrich.get("wikitext", {}).get(f"fr:{t}"):
            wikitext[q] = enrich["wikitext"][f"fr:{t}"]

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

    # Organisations absentes du cache (nouvelle collecte) : on va chercher pays, types, dates.
    # Seul accès réseau de ce script, et seulement pour les identifiants manquants.
    manquants = [q for q in noeuds if re.fullmatch(r"Q\d+", q) and q not in wd]
    if manquants:
        print(f"{len(manquants)} organisations absentes du cache Wikidata : téléchargement...")
        from fusion import wikidata
        wd = wikidata([q for q in noeuds if re.fullmatch(r"Q\d+", q)])

    # Compléments du cache Wikidata : pays, positionnement, types, dates (prioritaires)
    for q, d in noeuds.items():
        w = wd.get(q, {})
        d["pays"], d["pos_wd"], d["types"] = w.get("pays", []), w.get("pos", []), w.get("types", [])
        d["journaux"] = w.get("journaux", [])
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
        if r.get("journaux"):
            d["journaux"] = [j.strip() for j in r["journaux"].split("|") if j.strip()]

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
        ideo_nom = " ".join(x for x, _ in d["ideologies"]) + " " + d["label"]
        m = RX_IDEO_DROITE.search(ideo_nom)
        if m:   # royalisme, Algérie française... l'emporte sur un positionnement « gauche » douteux
            return f"idéologie hors périmètre : {m.group(0)}"
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
        # Le régionalisme compte (Parti occitan, UPC...) mais l'organisation est signalée
        # « à vérifier » si c'est son seul signe (voir douteux_de) ; l'extrême droite régionaliste
        # est déjà écartée par RX_IDEO_DROITE.
        if any(re.search(rx, ideo + " " + d["label"], re.I) for _, rx, _ in COURANTS) \
                or RX_NOM_GAUCHE_STRICT.search(d["label"]):
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
        elif set(d["types"]) & NON_POLITIQUE_PLUS:
            classe[q], raison[q] = "exclu", "pas une organisation politique (institution, organisme " \
                                            "intergouvernemental, groupe parlementaire)"
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
    # Liens validés à la main : candidats de la phase 0 (decision = oui) et liens manuels sourcés.
    # Rien n'est accepté sans décision explicite.
    for r in lire("sortie/liens_candidats.csv"):
        if r.get("decision", "").strip().lower() != "oui":
            continue
        if r["sens"] == "cible → org":
            a, b = r["cible"], r["org"]
        elif r["sens"] == "org → cible":
            a, b = r["org"], r["cible"]
        else:
            stats["candidats_sens_a_verifier"] += 1
            continue
        t = TYPE_LIEN_MANUEL.get(r["type_propose"], "filiation")
        aretes[(a, b)] = dict(type=t, sources={f"candidat validé ({r['signal']})"},
                              relations={r["type_propose"]})
        stats["candidats_valides"] += 1
    for r in lire("manuel/aretes_manuelles.csv"):
        a, b, src = r.get("ancetre", "").strip(), r.get("descendant", "").strip(), r.get("source", "").strip()
        if not a or not b or not src or not r.get("type", "").strip():
            stats["manuels_incomplets"] += 1      # source obligatoire
            continue
        t = TYPE_LIEN_MANUEL.get(r["type"].strip(), "filiation")
        aretes[(a, b)] = dict(type=t, sources={"manuel"}, relations={r["type"].strip()},
                              date=r.get("date_evenement", "").strip(), source_manuelle=src)
        for x in (a, b):
            noeuds.setdefault(x, None)
        stats["manuels_ajoutes"] += 1
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

    # ================= 6. Types : data/manuel/types.csv =================
    # Une coalition, un satellite, un groupe armé... n'est jamais une boîte de la généalogie.
    # Le type saisi dans types.csv l'emporte toujours sur le préremplissage.
    types_org, lignes_types = classer_types(noeuds, classe, wikitext, stats, aretes)
    for q, t in types_org.items():
        if t == "international_ou_federation_europeenne":
            classe[q] = "internationale"
        elif t == "parti_ou_organisation" and classe[q] == "internationale":
            classe[q] = "graphe"        # corrigé à la main dans types.csv
        elif t not in ("parti_ou_organisation", "etrangere") and classe[q] == "graphe":
            classe[q] = t
    ecrire_manuel_types(lignes_types, stats)

    # ================= Tri des arêtes selon les ensembles =================
    lignee, anomalies, hors, affil_brutes, nationales, inter_lignee, date_manquante = \
        [], [], [], [], [], [], []
    emanations = defaultdict(set)     # parent -> organisations liées (satellites)

    def ligne_anomalie(a, b, t, cause):
        return [a, b, t, noeuds[a]["fondation"] or "", noeuds[b]["fondation"] or "", cause,
                lab(a), lab(b), " | ".join(sorted(aretes[(a, b)]["sources"]))]

    for (a, b), e in sorted(aretes.items()):
        t, ca, cb = e["type"], classe[a], classe[b]
        if t == "emanation" or (t != "appartenance" and "satellite" in (ca, cb)
                                and "graphe" in (ca, cb)):
            # Satellite : rattaché à son parent, montré dans l'infobulle, jamais une boîte
            parent, sat = (a, b) if ca == "graphe" else (b, a)
            if classe[parent] == "graphe":
                emanations[parent].add(sat)
            else:
                hors.append([a, lab(a), b, lab(b), t, f"{ca} -> {cb}"])
            continue
        if t == "appartenance":
            if ca == "internationale" and cb != "internationale":
                a, b, ca, cb = b, a, cb, ca      # « X a pour membre Y » écrit à l'envers
                stats["appartenances_retournees"] += 1
            if ca == "graphe" and cb == "internationale":
                affil_brutes.append((a, b, e))
            elif ca == "graphe" and cb in ("graphe", "coalition"):
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
        if db[0] == da[0] and not (da[1] and db[1] and db[1] > da[1]):
            # Même année, mois inconnus : le lien aurait une longueur nulle sur l'axe du temps
            anomalies.append(ligne_anomalie(a, b, t, "date erronée ou trop imprécise : source et "
                                            "cible fondées la même année (mois inconnus), le sens "
                                            "du temps ne peut pas être vérifié"))
            continue
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
    # Validation à la main (data/manuel/actifs.csv, colonne valide) : seule « oui » rend active.
    # Tant qu'aucune ligne n'est validée : mode provisoire = drapeau automatique, sauf les
    # organisations sans aucun indice d'activité récente.
    saisie_actifs = {r["id"]: r for r in lire(os.path.join("manuel", "actifs.csv"))}
    valides = {q for q, r in saisie_actifs.items() if r.get("valide", "").strip().lower() == "oui"}
    refuses = {q for q, r in saisie_actifs.items() if r.get("valide", "").strip().lower() == "non"}
    provisoire = not valides
    stats["actifs_valides"], stats["actifs_refuses"] = len(valides), len(refuses)
    for q, d in noeuds.items():
        cats_mortes = [c for c in d.get("cats_article", []) if RX_CAT_DISPARU.search(c)]
        d["actif_auto"] = (not d["dissolution"] and q not in successeur
                           and not set(d["types"]) & ANCIEN and not cats_mortes
                           and not re.search(r"Catégorie:Ancien", d["categories"]))
        if forcer.get(q) in ("vivant", "disparu"):
            d["actif_auto"] = forcer[q] == "vivant"
        if q in valides:
            d["statut_fin"] = "actif_valide"
        elif (provisoire and d["actif_auto"] and q not in refuses
              and "AUCUN indice" not in saisie_actifs.get(q, {}).get("evidence", "")):
            d["statut_fin"] = "actif_provisoire"
        else:
            d["statut_fin"] = ""
        d["actif"] = bool(d["statut_fin"])
        d["fin_deduite"], d["fin_deduite_source"] = "", ""
        if not d["dissolution"] and not d["actif"]:
            succ = [noeuds[b]["fondation"] for a, b, rel, _ in liens
                    if a == q and rel in ("filiation", "fusion", "renommage")]
            if succ:
                d["fin_deduite"], d["fin_deduite_source"] = min(succ), "fondation du successeur"
        if not d["statut_fin"]:
            d["statut_fin"] = ("fin_connue" if d["dissolution"] else
                               "fin_deduite" if d["fin_deduite"] else "fin_inconnue")

    # ================= 8. Familles et courants =================
    for q, d in noeuds.items():
        textes = [(d["label"], "nom")]
        textes += [(c, "correction") for c in d.get("courants_manuels", [])]
        textes += [(x, s) for x, s in d["ideologies"]]
        textes += [(c, "wikipedia:catégorie") for c in d["categories"].split(" | ") if c]
        trouves = defaultdict(set)
        for texte, src in textes:
            for nom, rx, fam in COURANTS:
                if re.search(rx, texte, re.I):
                    trouves[nom].add(src)
        # Famille : un courant saisi à la main l'emporte ; sinon un courant présent dans le nom ;
        # sinon le premier courant dans l'ordre de priorité de COURANTS (trotskyste d'abord...),
        # quelle que soit sa source. L'ordre d'écriture des idéologies dans la source ne compte pas.
        # Un courant générique du nom (« communiste », « socialiste ») ne l'emporte pas sur un
        # courant précis trouvé ailleurs : la LCR ou l'OCI sont trotskystes malgré leur nom.
        # Seule une spécialisation du même courant compte : « communiste » cède devant
        # trotskyste, maoïste, libertaire... ; « socialiste » devant trotskyste ou écosocialiste.
        precis_de = {"communiste": {"trotskyste", "maoïste", "luxemburgiste / conseilliste",
                                    "communiste libertaire", "anarchiste", "anarcho-syndicaliste"},
                     "social-démocrate": {"trotskyste", "écosocialiste"}}
        famille, principal, restreint = None, "", None
        # Ordre d'examen : priorité de COURANTS, sauf entre les deux courants génériques,
        # départagés par le nombre de sources qui les citent (la SFIO est citée « socialiste »
        # par plus de sources que « communiste »).
        ordre_courants = list(COURANTS)
        if len(trouves.get("social-démocrate", ())) > len(trouves.get("communiste", ())):
            com = next(c for c in ordre_courants if c[0] == "communiste")
            ordre_courants.remove(com)
            ordre_courants.insert(ordre_courants.index(
                next(c for c in ordre_courants if c[0] == "social-démocrate")) + 1, com)
        for niveau in ({"correction"}, {"nom"}, None):
            for nom, _, fam in ordre_courants:
                if not fam or nom not in trouves:
                    continue
                if niveau is not None and not trouves[nom] & niveau:
                    continue
                if niveau is None and restreint is not None and nom not in restreint:
                    continue
                if niveau == {"nom"} and set(trouves) & precis_de.get(nom, set()):
                    restreint = precis_de[nom]     # le nom est générique : on cherche plus précis
                    continue
                famille, principal = fam, nom
                break
            if famille:
                break
        d["courants"] = trouves
        d["courant_principal"] = principal     # donne la couleur, même en outre-mer
        d["famille_courant"] = famille or "à classer"
        tout = " ".join([d["label"], d["categories"]] + d.get("cats_article", []))
        d["outre_mer"] = bool(RX_OUTREMER.search(tout))
        d["famille"] = "outre-mer" if d["outre_mer"] else (famille or "à classer")

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
    with open(chemin_sigles, encoding="utf-8") as f:
        tous = list(csv.DictReader(f))
    stats["sigles_total"] = len(tous)
    stats["sigles_remplis"] = sum(1 for r in tous if r["sigle"].strip())

    # ================= Internationales et affiliations =================
    inter_utiles = {b for _, b, _ in affil_brutes}
    pred = defaultdict(list)
    for a, b, t in inter_lignee:
        da, db = debut(a), debut(b)
        # Filiation ou scission entre Internationales : succession, affichée dans la clé
        # (ex. CIO -> Tendance marxiste internationale, devenue Internationale communiste révolutionnaire)
        if t in ("filiation", "scission") and (not da or not db or da <= db):
            pred[b].append(a)
        else:
            anomalies.append(ligne_anomalie(a, b, t, "lien entre deux Internationales "
                                            + ("de sens contraire au temps"
                                               if t in ("filiation", "scission")
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
        # Nom exact seulement : « Quatrième Internationale (lambertiste) » n'est pas la QI
        lignes_inter.append([q, d["label"], SIGLES_INTER.get(d["label"], ""), d["fondation"] or "",
                             d["dissolution"] or "", " | ".join(pred[q]), cle_couleur(d["label"])])

    # Dates d'adhésion saisies à la main (data/manuel/affiliations_dates.csv, source obligatoire)
    dates_saisies = {(r["party_id"], r["international_id"]): r
                     for r in lire(os.path.join("manuel", "affiliations_dates.csv"))
                     if r.get("source", "").strip() and (r.get("start", "").strip() or r.get("end", "").strip())}
    lignes_affil, a_dater = [], []
    for a, b, e in affil_brutes:
        da, di = noeuds[a], noeuds[b]
        s = dates_saisies.get((a, b))
        if s:
            lignes_affil.append([a, b, s["start"].strip(), s["end"].strip(), "known",
                                 f"manuel : {s['source'].strip()}", lab(a), lab(b)])
            continue
        # Période inconnue : recouvrement de la vie du parti et de celle de l'Internationale
        fin_a = da["dissolution"] or da["fin_deduite"] or None
        debut_ = max(x for x in (da["fondation"], di["fondation"], 0) if x is not None) or ""
        fins = [x for x in (fin_a, di["dissolution"]) if x]
        fin_ = min(fins) if fins else ""
        lignes_affil.append([a, b, debut_, fin_, "unknown", " | ".join(sorted(e["sources"])),
                             lab(a), lab(b)])
        a_dater.append([a, b, "", "", "", lab(a), lab(b), debut_, fin_])
    inter_sans_membre = {q for q in noeuds if classe[q] == "internationale"} - inter_utiles

    # ================= 8. Élagage strict (R5) =================
    # Gardées : les organisations actives ayant au moins un lien de lignée, et tous leurs ancêtres
    # (chemins orientés de filiation, renommage, fusion, scission ; les émanations et les passages
    # de militants ne comptent pas). Tout le reste va dans elagues.csv avec une cause.
    parents_r5, voisins_r5 = defaultdict(set), defaultdict(set)
    for a, b, rel, _ in liens:
        if rel in ("filiation", "renommage", "fusion", "scission"):
            parents_r5[b].add(a)
            voisins_r5[a].add(b)
            voisins_r5[b].add(a)
    for a, _, b, _, t, _ in date_manquante:      # un ancêtre sans date reste un ancêtre
        if t in ("filiation", "scission"):
            parents_r5[b].add(a)
            voisins_r5[a].add(b)
            voisins_r5[b].add(a)
    actives = {q for q in graphe if noeuds[q]["actif"]}
    garde, pile = set(), [q for q in actives if voisins_r5[q]]
    while pile:
        x = pile.pop()
        if x not in garde:
            garde.add(x)
            pile.extend(parents_r5[x])
    composante, vus = {}, set()
    for q in graphe:
        if q in vus:
            continue
        comp, pile = set(), [q]
        while pile:
            x = pile.pop()
            if x not in comp:
                comp.add(x)
                pile.extend(voisins_r5[x])
        vus |= comp
        a_active = bool(comp & actives)
        for x in comp:
            composante[x] = a_active
    lignes_elag, actives_sans_lien = [], []
    for q in sorted(noeuds, key=lab):
        d = noeuds[q]
        statut = d.get("statut_fin", "")
        if classe[q] == "graphe" and q not in garde:
            if not voisins_r5[q]:
                cause = "isolee"
                if d["actif"]:
                    actives_sans_lien.append(q)
            elif not composante[q]:
                cause = "arbre_sans_organisation_active"
            else:
                cause = "non_ancetre_d_une_active"
            lignes_elag.append([q, lab(q), cause, statut, d.get("famille", ""), ""])
        elif classe[q] in TYPES and classe[q] not in ("parti_ou_organisation",
                                                       "international_ou_federation_europeenne"):
            parent = next((p for p, sats in emanations.items() if q in sats), None)
            lignes_elag.append([q, lab(q), classe[q], statut, d.get("famille", ""),
                                f"organisation liée à {lab(parent)}" if parent else ""])
        elif classe[q] == "etranger":
            lignes_elag.append([q, lab(q), "etrangere", statut, "", raison.get(q, "")])
    stats["gardes"] = len(garde)
    stats.update({f"elague_{c}": n for c, n in Counter(l[2] for l in lignes_elag).items()})

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
        if d["famille"] == "à classer" and "régionaliste / autonomiste" in d["courants"]:
            return "régionaliste sans courant de gauche reconnu : à vérifier"
        if d["famille"] == "à classer":
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
                            d["courant_principal"], d["famille_courant"], douteux_de(q),
                            " | ".join(sorted(d["sources"])), " | ".join(d.get("journaux", [])),
                            d["statut_fin"], "oui" if d["actif_auto"] else "",
                            "oui" if q in garde else "",
                            " | ".join(sorted(lab(s) for s in emanations.get(q, ())))])
    ecrire("organisations.csv",
           ["id", "label", "nom_court", "fondation", "fondation_mois", "fondation_source",
            "fondation_autres_sources", "dissolution", "dissolution_mois", "dissolution_source",
            "fin_deduite", "fin_deduite_source", "actif", "famille", "outre_mer", "courants",
            "courants_sources", "courant_principal", "famille_courant", "perimetre_douteux",
            "sources", "journaux", "statut_fin", "actif_auto", "garde", "organisations_liees"],
           lignes_orgs)
    ecrire("elagues.csv", ["id", "label", "cause", "statut_fin", "famille", "detail"], lignes_elag)
    ecrire("affiliations_a_dater.csv", ["party_id", "international_id", "start", "end", "source",
                                        "party_nom", "international_nom", "recouvrement_debut",
                                        "recouvrement_fin"], a_dater)
    # Fichier à compléter à la main : créé une fois, jamais écrasé (lu au prochain passage)
    chemin_ad = os.path.join(MANUEL, "affiliations_dates.csv")
    if not os.path.exists(chemin_ad):
        ecrire("affiliations_dates.csv", ["party_id", "international_id", "start", "end", "source",
                                          "party_nom", "international_nom"],
               [l[:7] for l in a_dater], dossier=MANUEL)

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
        lignes_sd.append([q, d["label"], d["famille"], ct, " | ".join(sorted(d["sources"])),
                          "oui" if q in garde else ""])
    ecrire("sans_date.csv", ["id", "label", "famille", "courants", "sources", "garde"], lignes_sd)

    lignes_exclu = []
    for q in sorted(noeuds, key=lambda q: (raison.get(q, ""), lab(q))):
        d = noeuds[q]
        dates = [d["fondation"] or "", d["fondation_mois"] or "", d["dissolution"] or "",
                 d["dissolution_mois"] or "", d["fin_deduite"], "oui" if d["actif"] else ""]
        if classe[q] in ("exclu", "etranger"):
            lignes_exclu.append([q, lab(q), raison[q], "oui" if q in voie_externe else "",
                                 " | ".join(d["pays"])] + dates)
        elif q in inter_sans_membre:
            lignes_exclu.append([q, lab(q), "Internationale sans membre dans le graphe", "", ""]
                                + dates)
    ecrire("perimetre_exclu.csv", ["id", "label", "raison", "voie_externe", "pays_wikidata",
                                   "fondation", "fondation_mois", "dissolution", "dissolution_mois",
                                   "fin_deduite", "actif"], lignes_exclu)
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

Familles : {", ".join(f"{f} ({familles[f]})" for f in FAMILLES + ["à classer"] if familles[f])}.

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
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : {", ".join(f"{c} ({n})" for c, n in causes.most_common())}.

Dates : {sum(1 for q in datees if noeuds[q]['fondation_mois'])} fondations et {sum(1 for q in datees if noeuds[q]['dissolution_mois'])} dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
{sum(1 for q in datees if noeuds[q]['fondation_autres'])} organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : {stats['sigles_total']} organisations, dont {stats['sigles_remplis']} avec un sigle ; {stats['sigles_ajoutes']} ajoutées à cette exécution.

## Liens validés à la main
- Candidats de la phase 0 acceptés (decision = oui) : {stats['candidats_valides']}
  (dont {stats['candidats_sens_a_verifier']} ignorés car leur sens est « à vérifier »).
- Liens manuels (data/manuel/aretes_manuelles.csv) : {stats['manuels_ajoutes']} ajoutés,
  {stats['manuels_incomplets']} ignorés (source, type ou extrémité manquant).

## Types (data/manuel/types.csv)
{", ".join(f"{t} {stats['type_' + t]}" for t in TYPES if stats['type_' + t])}.
{stats['types_saisis']} types saisis à la main, {stats['types_ajoutes']} lignes ajoutées au fichier.
Coalitions et satellites ne sont jamais des boîtes ; un satellite rattaché à un parent apparaît
dans la colonne organisations_liees de ce parent.

## Organisations actives
{"**Mode provisoire** : aucune ligne de data/manuel/actifs.csv n'a valide = oui. Une organisation "
 "compte comme active si le drapeau automatique le dit et qu'il existe au moins un indice "
 "d'activité récente. Dès qu'une ligne est validée, seules les lignes validées comptent."
 if provisoire else f"{stats['actifs_valides']} organisations validées actives, {stats['actifs_refuses']} refusées."}
- Actives retenues : {len(actives)}.

## Élagage strict (R5)
- **Gardées : {len(garde)} organisations** (actives ayant un lien de lignée, et leurs ancêtres),
  dont {len(garde & sans_date)} sans date.
- Élaguées (data/sortie/elagues.csv), par cause : {", ".join(f"{c} {n}" for c, n in Counter(l[2] for l in lignes_elag).most_common())}.
- **Actives élaguées faute de lien ({len(actives_sans_lien)})**, à relier à la main puis relancer :
  {", ".join(sorted(lab(q) for q in actives_sans_lien))}.

## Affiliations
- {len(a_dater)} affiliations sans dates connues : data/sortie/affiliations_a_dater.csv ;
  à compléter dans data/manuel/affiliations_dates.csv (source obligatoire).
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

Famille : donnée par un courant saisi à la main s'il y en a un ; sinon par un courant reconnu
dans le nom (sauf « communiste » ou « socialiste » génériques quand un courant plus précis est
trouvé ailleurs : la LCR et l'OCI sont trotskystes malgré leur nom) ; sinon par le premier courant trouvé dans l'ordre de priorité suivant, quelle que
soit sa source : trotskyste, maoïste, anarcho-syndicaliste, communiste libertaire, anarchiste,
luxemburgiste / conseilliste, communiste, écosocialiste, écologiste, radical, social-démocrate.
L'écosocialisme (PG, LFI...) est rangé dans la famille socialiste, pas dans l'écologie politique.
Familles : socialistes, radicaux, écologistes, communistes, trotskystes, maoïstes, anarchistes et
libertaires, outre-mer. Une organisation d'outre-mer (nom ou catégories : Guadeloupe, Martinique,
Guyane, La Réunion, Mayotte, Nouvelle-Calédonie, Polynésie...) va dans la voie outre-mer et garde
ses courants. Sans courant reconnu : « à classer » (petite voie, jamais un fourre-tout).

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
- Liens ajoutés à la main : candidats de la phase 0 marqués decision = oui (sens « cible → org »
  ou « org → cible » ; un sens « à vérifier » est ignoré), et lignes de
  data/manuel/aretes_manuelles.csv qui ont une source. Aucun candidat n'est accepté seul.

## Types (data/manuel/types.csv)

Types : parti_ou_organisation (seul type dessiné), coalition, satellite (jeunesse, groupe
étudiant, section locale, collectif, association), groupe_arme, syndicat, club_ou_cercle, media,
etrangere, international_ou_federation_europeenne.

Préremplissage, dans cet ordre, jamais par des mots du nom seuls :
1. liste explicite des coalitions (Front populaire, NUPES, Nouveau Front populaire, Gauche
   plurielle, Front de gauche, Cartel des gauches, Programme commun, Union de la gauche, FGDS...) ;
2. types Wikidata (P31) : jeunesse, étudiants, section locale -> satellite ; groupe parlementaire
   -> coalition (groupe d'élus) ; parti ou organisation politique -> parti ; puis coalition,
   groupe armé, syndicat, club, média, association ou collectif ;
3. modèle d'infobox Wikipédia ; 4. catégories de l'article ; 5. sinon parti_ou_organisation.

Signalés « à vérifier » dans la colonne reason : ce qui ressemble à une Internationale, les deux
partis radicaux, et toute coalition ou tout satellite qui a des liens de lignée (le retirer
couperait la généalogie, ex. la JCR de 1966, ancêtre de la Ligue communiste).
Le type saisi dans types.csv l'emporte toujours sur le préremplissage. Un satellite rattaché à son
parent (lien d'émanation) figure dans la colonne organisations_liees du parent.

## Organisations actives

Seules les lignes de data/manuel/actifs.csv marquées valide = oui sont actives (« non » : jamais).
Tant qu'aucune ligne n'est validée, mode provisoire : drapeau automatique (pas de date de fin,
pas de successeur, pas de catégorie « Ancien… »), sauf les organisations sans aucun indice
d'activité récente. Colonne statut_fin : actif_valide, actif_provisoire, fin_connue,
fin_deduite (fondation du successeur), fin_inconnue.

## Élagage strict (R5)

Gardées (colonne garde) : les organisations actives qui ont au moins un lien de lignée, et tous
leurs ancêtres par des chemins orientés de filiation, renommage, fusion ou scission (les
émanations et les passages de militants ne comptent pas ; un ancêtre sans date compte).
Toutes les autres sont dans elagues.csv, avec une cause : isolee (aucun lien de lignée),
arbre_sans_organisation_active, non_ancetre_d_une_active, coalition, satellite, groupe_arme,
syndicat, club_ou_cercle, media, etrangere.
"""

if __name__ == "__main__":
    main()
