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

import porte
import preuves
from fusion import (ANCIEN, FRANCE, HUMAIN, NON_POLITIQUE, POLITIQUE, RX_CAT_DISPARU,
                    RX_CATEGORIE, RX_DROITE, RX_ETRANGER_CAT, RX_FRANCE_CAT, RX_GAUCHE,
                    RX_NOM_GAUCHE)
from fusion import INTERNATIONALE as TYPES_INTERNATIONALE

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # racine du dépôt
DATA = os.path.join(RACINE, "data")
SORTIE = os.path.join(DATA, "sortie")
MANUEL = os.path.join(DATA, "manuel")
LIGNEE = ("filiation", "scission", "passage")
ORDRE_TYPES = ["appartenance", "emanation", "filiation", "scission", "passage"]
# Relations typées (1.2) : celles qui font une lignée (R5), celles où l'ancêtre disparaît
REL_LIGNEE = ("renommage", "scission", "fusion", "absorption", "refondation", "filiation_idéologique", "indirect")
REL_SUCCESSION = ("renommage", "fusion", "absorption", "refondation")
# Types des liens saisis à la main ou validés (phase 0) -> types internes
TYPE_LIEN_MANUEL = {"filiation": "filiation", "renommage": "filiation", "fusion": "filiation",
                    "scission": "scission", "passage_militants": "passage", "passage": "passage",
                    "emanation": "emanation", "refondation": "filiation", "absorption": "filiation",
                    "appartenance": "appartenance"}

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
    "Les Écologistes – Europe Écologie Les Verts": "Les Écologistes", "Les Verts": "Verts",
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


# Exclusions explicites à retester (1.5) : gardées seulement avec un lien documenté explicitement
RX_A_RETESTER = re.compile(r"^(Union démocratique bretonne|Union des étudiants communistes|Voix prolétarienne|"
                           r"Parti communiste des ouvriers de France|Parti communiste martiniquais|"
                           r"Mouvement socialiste guadeloupéen|Fédération guadeloupéenne du Parti socialiste|"
                           r"Fédération nationale des anarchistes|FNARC|Gauche révolutionnaire \(1935-1938\)|"
                           r"Union des clubs pour le renouveau de la gauche)")

# Organisations qui doivent figurer dans l'arbre, ou dont l'absence doit être expliquée (1.7)
INCONTOURNABLES = ["Parti communiste français", "Parti socialiste (France)",
                   "Section française de l'Internationale ouvrière", "Parti socialiste unifié (France)",
                   "Les Écologistes – Europe Écologie Les Verts", "Les Verts", "La France insoumise",
                   "Parti de gauche (France)", "Lutte ouvrière", "Parti ouvrier indépendant",
                   "Parti des travailleurs (France, 1991)", "Ligue communiste révolutionnaire",
                   "Ligue communiste (1969)", "Nouveau Parti anticapitaliste",
                   "Nouveau Parti anticapitaliste – Révolutionnaires", "Révolution permanente (parti politique)",
                   "Parti communiste révolutionnaire", "Fédération anarchiste (francophone)",
                   "Union communiste libertaire (francophone)", "Alternative libertaire (France)",
                   "Organisation communiste libertaire", "Gauche prolétarienne",
                   "Union des jeunesses communistes marxistes-léninistes",
                   "Parti communiste marxiste-léniniste de France", "Parti radical de gauche"]

# ---------- Types d'organisation (étape 6) ----------
# Types (1.1). Les anciens noms (première version de types.csv) sont convertis à la lecture.
TYPES = ["parti", "coalition", "satellite", "internationale", "fondatrice", "étrangère"]
ANCIENS_TYPES = {"parti_ou_organisation": "parti", "international_ou_federation_europeenne": "internationale",
                 "etrangere": "étrangère", "groupe_arme": "satellite", "syndicat": "satellite",
                 "club_ou_cercle": "satellite", "media": "satellite"}
DETAIL_TYPE = {"groupe_arme": "groupe armé", "syndicat": "syndicat", "club_ou_cercle": "club ou cercle",
               "media": "média"}
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
# Addendum 3 bis, 1 et 3 : motifs de nom (règle voulue, malgré « jamais par des mots du nom seuls »)
RX_R6_NOM = re.compile(r"^f[ée]d[ée]ration\b.*\bdu Parti socialiste\b|^groupe\b.*\bà l['’]Assembl[ée]e|"
                       r"^section\b|^comit[ée] de suivi\b", re.I)
RX_COURANT_DE = re.compile(r"'''[^\n]+?'''[^.\n]{0,120}?\best un courant (?:politique |interne )?"
                           r"(?:du|de la|de l'|des)\s*\[\[", re.I)
RX_INTER_NOM = re.compile(r"[-–]\s*Quatrième Internationale\s*$|^Quatrième Internationale\b")
# Addendum 3 bis, 2 : régionalistes et autonomistes (idéologie ou catégories de l'article)
RX_REGIONALISTE = re.compile(r"r[ée]gionalis|autonomis|ind[ée]pendantis|nationalisme (?:breton|basque|corse|"
                             r"occitan|catalan|alsacien|kanak)|nationaliste (?:breton|basque|corse|occitan|catalan)",
                             re.I)
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
    n_lignee, ancetres_de_partis = Counter(), set()
    for (a, b), e in (aretes or {}).items():
        if e["type"] in ("filiation", "scission", "passage"):
            n_lignee[a] += 1
            n_lignee[b] += 1
            if e["type"] != "passage" and classe.get(b) == "graphe":
                ancetres_de_partis.add(a)
    types_org, lignes = {}, []
    for q in a_classer:
        d = noeuds[q]
        if classe[q] == "internationale":
            t, pourquoi = "international_ou_federation_europeenne", "type Wikidata ou nom d'Internationale"
        elif classe[q] == "etranger":
            t, pourquoi = "etrangere", "hors de France (voir perimetre_exclu.csv)"
        elif normaliser(d["label"]) in coalitions:
            t, pourquoi = "coalition", "liste explicite des coalitions"
        elif RX_INTER_NOM.search(d["label"]):
            t, pourquoi = "international_ou_federation_europeenne", "nom d'une Internationale (addendum 3 bis, 3)"
        elif RX_R6_NOM.search(d["label"]):
            t, pourquoi = "satellite", f"nom : « {RX_R6_NOM.search(d['label']).group(0)} » (R6, addendum 3 bis)"
        elif (m_c := RX_COURANT_DE.search(wikitext.get(q, "")[:4000])):
            t, pourquoi = "satellite", f"courant d'un parti : « {m_c.group(0)[-70:]} » (R6, addendum 3 bis)"
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
        # Nouveau vocabulaire ; « fondatrice » : coalition ou satellite ancêtre d'un parti (R6)
        if t in DETAIL_TYPE:
            pourquoi = f"{DETAIL_TYPE[t]} ; {pourquoi}"
        t = ANCIENS_TYPES.get(t, t)
        # Une coalition de la liste explicite reste une coalition (ex. le Front de gauche,
        # dont le seul « descendant » est le Front de gauche Réunion, lien vers la page nationale)
        if t in ("satellite", "coalition") and q in ancetres_de_partis                 and normaliser(d["label"]) not in coalitions:
            pourquoi = f"{t} ancêtre d'un parti (organisme fondateur) ; {pourquoi}"
            t = "fondatrice"
        drapeaux = []
        if classe[q] == "graphe" and RX_SEMBLE_INTER.search(d["label"]) and "Section française" not in d["label"]:
            drapeaux.append("ressemble à une Internationale : à vérifier")
        if RX_DOUTEUX.search(d["label"]):
            drapeaux.append("périmètre discutable (radicaux) : à trancher")
        if t == "fondatrice" and n_lignee.get(q):
            # Ex. la JCR (1966) : organisation de jeunesse, mais ancêtre de la Ligue communiste
            drapeaux.append(f"a {n_lignee[q]} lien(s) de lignée : la retirer coupe la généalogie, à vérifier")
        auto = (t, pourquoi + (" ; " + " ; ".join(drapeaux) if drapeaux else ""))
        s = saisis.get(q)
        t_saisi = ANCIENS_TYPES.get(s.get("type", "").strip(), s.get("type", "").strip()) if s else ""
        if t_saisi in TYPES and s.get("valide", "").strip():
            types_org[q] = t_saisi                 # ligne validée à la main : prioritaire
            stats["types_saisis"] += 1
        else:
            types_org[q] = auto[0]
        lignes.append([q, d["label"], auto[0], auto[1], ""])
    stats.update({f"type_{t}": n for t, n in Counter(types_org.values()).items()})
    return types_org, lignes


RX_CHAMP_FONDATION = re.compile(r"^\s*\|\s*fondation\s*=(.*)$", re.M)


def noms_successifs(corpus, garde):
    """Noms successifs d'une même organisation, lus dans le champ « fondation » de son infobox :
    « 1920 (SFIC)<br/>1921 (PC-SFIC)<br/>1943 (PCF) ». Gardés : au moins deux noms, chacun un nom
    propre (pas « courant du NPA », pas un lien vers un autre article comme « 1905 ([[SFIO]]) »),
    avec la citation mot pour mot de chaque morceau (R8)."""
    lignes = []
    for q in sorted(garde):
        for lang, titre, txt in corpus.textes.get(q, []):
            if lang != "fr":
                continue
            m = RX_CHAMP_FONDATION.search(txt)
            if not m:
                continue
            valeur = m.group(1)
            # « {{date|13|novembre|2010}}<br><small>(Europe Écologie Les Verts)</small> » : la date et son
            # nom sont sur deux lignes, on les recolle
            valeur = re.sub(r"<br\s*/?>\s*(?=<small>\s*\()", " ", valeur)
            morceaux = re.split(r"<br\s*/?>", re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", valeur, flags=re.S))
            noms = []
            for mo in morceaux:
                n = re.search(r"(1[89]\d\d|20\d\d)\s*(?:\}\})?\s*(?:<small>|\{\{petit\|)?\s*\(([^()\[\]{}]{2,60})\)", mo)
                if not n or not n.group(2).strip()[:1].isupper():
                    continue
                # Citation dans le texte brut : de l'année à la parenthèse fermante
                c = re.search(re.escape(n.group(1)) + r"[^\n]{0,40}?\(" + re.escape(n.group(2)) + r"\)", txt)
                if c and corpus.verifier(c.group(0), f"fr:{titre}"):
                    noms.append([q, titre, n.group(1), n.group(2).strip(), c.group(0), f"fr:{titre}"])
            if len(noms) >= 2 and len({x[3] for x in noms}) >= 2:
                lignes += noms
            break
    return lignes


def ecrire_manuel_types(lignes, stats):
    """data/manuel/types.csv : créé une fois ; ensuite, seules les nouvelles organisations sont ajoutées."""
    chemin = os.path.join(MANUEL, "types.csv")
    existants = set()
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            deja = list(csv.DictReader(f))
        # Aucune ligne validée à la main et ancien vocabulaire : le fichier n'est qu'un
        # préremplissage, on peut le régénérer. Sinon, on n'ajoute que les nouvelles lignes.
        if any(r.get("valide", "").strip() for r in deja) or                 not any(r.get("type") in ANCIENS_TYPES for r in deja):
            existants = {r["id"] for r in deja}
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


MOTS_VIDES_SIGLE = {"de", "la", "le", "les", "des", "du", "pour", "l", "d", "et", "à", "en", "au", "aux",
                    "un", "une", "sur", "contre"}
RX_SIGLE_ARTICLE = re.compile(r"'''[^'\n]{3,120}'''\s*\(\s*(?:'''|'')?([A-ZÉÈ][A-Za-zÉÈÀéèàô0-9\-.&]{1,11})"
                              r"(?:'''|'')?\s*[),]")


def etiquette_de(q, label, sigle_saisi, texte):
    """Étiquette courte : sigle saisi ; sinon sigle de la première phrase de l'article ; sinon
    acronyme du nom usuel (« Alliance communiste révolutionnaire » -> « ACR ») ; sinon nom raccourci."""
    if sigle_saisi.strip():
        return sigle_saisi.strip(), "sigles.csv"
    m = RX_SIGLE_ARTICLE.search(texte[:20000])
    if m and m.group(1).upper() == m.group(1):
        return m.group(1), "article"
    nom = re.sub(r"\s*\([^)]*\)$", "", label).strip()
    mots = [w for w in re.findall(r"[^\W\d_]+", nom) if w.lower() not in MOTS_VIDES_SIGLE]
    if len(mots) >= 3:
        return "".join(w[0].upper() for w in mots), "acronyme du nom"
    if len(nom) <= 24:
        return nom, "nom court"
    return nom[:23].rsplit(" ", 1)[0] + "…", "nom raccourci"


def main():
    os.makedirs(SORTIE, exist_ok=True)
    stats = Counter()
    corpus = preuves.Corpus()      # wikitextes bruts en cache, pour les citations (R8)
    # Organisations affichées au passage précédent (test de régression, 1.7)
    precedents = {r["id"]: r["label"] for r in lire(os.path.join("sortie", "organisations.csv"))
                  if r.get("garde") == "oui"}
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

    # Nœuds corrigés à la main avec source (data/manuel/noeuds_manuels.csv) : dates prioritaires.
    # Ligne ignorée sans source ni citation. Un nœud absent des données est créé.
    stats["noeuds_manuels"] = 0
    for r in lire(os.path.join("manuel", "noeuds_manuels.csv")):
        q = r.get("id", "").strip()
        if not q or not r.get("source", "").strip() or not r.get("citation", "").strip():
            continue
        if q not in noeuds and not RX_INTER.search(r.get("label", "")):
            forcer.setdefault(q, "inclure")    # organisation connue seulement par une mention
        d = noeuds.setdefault(q, nouveau(q, r.get("label", "").strip() or q))
        d.setdefault("cats_article", [])
        d.setdefault("pays", []), d.setdefault("pos_wd", []), d.setdefault("types", [])
        d.setdefault("journaux", [])
        d["sources"].add("manuel")
        if r.get("label", "").strip():
            d["label"] = r["label"].strip()
        if annee(r.get("fondation")):
            d["dates_f"].insert(0, (annee(r["fondation"]), "manuel"))
        if annee(r.get("dissolution")):
            d["dates_d"].insert(0, (annee(r["dissolution"]), "manuel"))
        if r.get("courants", "").strip():
            d["courants_manuels"] = [c.strip() for c in r["courants"].split("|") if c.strip()]
        stats["noeuds_manuels"] += 1

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
        ideo_txt = " ".join(x for x, _ in d["ideologies"]) + " " + d["label"]
        courant_gauche = any(re.search(rx, ideo_txt, re.I) for _, rx, fam in COURANTS if fam)
        if RX_DROITE.search(positions):
            # « centre gauche » + « centrisme » avec un courant de gauche reconnu (ex. PRG, radical) : gardé
            if re.search(r"centre[- ]gauche", positions, re.I) and courant_gauche \
                    and not re.search(r"droit", positions, re.I):
                return None
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

    # Addendum 4, 1 : porte « organisation politique » (territoires, G7, bases de données, personnes,
    # syndicats...), par les classes Wikidata ; les identifiants cités dans data/manuel/ sont exemptés
    rejets_porte = porte.rejets(list(noeuds), exemptes=porte.ids_manuels() | set(forcer))
    # Addendum 5, F2 : partis du centre lus un par un (position citée), décision dans
    # data/manuel/perimetre_centre.csv ; « hors_perimetre » : écartés et listés dans hors_perimetre.csv
    centre_hors = {r["id"].strip(): r for r in lire(os.path.join("manuel", "perimetre_centre.csv"))
                   if r.get("decision", "").strip() == "hors_perimetre" and r.get("citation", "").strip()}
    stats["rejets_porte_politique"] = len(rejets_porte)
    classe, raison = {}, {}
    for q, d in noeuds.items():
        f = forcer.get(q)
        if f == "exclure":
            classe[q], raison[q] = "exclu", "exclu à la main"
        elif f in ("inclure", "vivant", "disparu") or RX_DOUTEUX.search(d["label"]):
            classe[q] = "graphe"    # les radicaux : gardés et signalés, pas tranchés ici
        elif q in rejets_porte:
            classe[q], raison[q] = "exclu", rejets_porte[q]
        elif q in centre_hors:
            classe[q], raison[q] = "exclu", f"hors périmètre (centre) : {centre_hors[q]['positionnement']}"
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
        if r["type"].strip() == "composante":
            continue                              # pas une lignée : lue avec les composantes
        if r["type"].strip() == "supprimer":      # lien automatique erroné, retiré avec sa justification
            for k in ((a, b), (b, a)):
                if aretes.pop(k, None) is not None:
                    stats["manuels_supprimes"] += 1
            continue
        t = TYPE_LIEN_MANUEL.get(r["type"].strip(), "filiation")
        aretes[(a, b)] = dict(type=t, sources={"manuel"}, relations={r["type"].strip()},
                              date=r.get("date_evenement", "").strip(), source_manuelle=src,
                              type_manuel=r["type"].strip())      # gardé à part : relations est un ensemble
        if r["type"].strip() == "indirect":
            # Lien indirect saisi à la main (PSOP -> Voix ouvrière par le groupe Barta) : deux citations,
            # « lang:Page : « … » ; lang:Page : « … » », l'intermédiaire nommé dans la note (« par : … »)
            cits = re.findall(r"(\w+:[^:«»;]+?)\s*:\s*«\s*(.+?)\s*»", src, re.S)
            m_par = re.search(r"par\s*:\s*([^(;]+)", r.get("note", ""))
            if len(cits) == 2 and all(corpus.verifier(c_, s_) for s_, c_ in cits) and m_par:
                aretes[(a, b)].update(citation1=cits[0], preuve2=dict(citation=cits[1][1], source=cits[1][0]),
                                      intermediaire_nom=m_par.group(1).strip())
            else:
                stats["indirects_manuels_sans_citation"] = stats.get("indirects_manuels_sans_citation", 0) + 1
                del aretes[(a, b)]
                continue
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
        for k in ("type_manuel", "source_manuelle", "date", "citation1", "preuve2", "intermediaire_nom"):     # un lien manuel garde son type et sa citation
            if er.get(k) and not eg.get(k):
                eg[k] = er[k]
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
        if t == "internationale":
            classe[q] = "internationale"
        elif t in ("parti", "fondatrice") and classe[q] in ("internationale", "graphe"):
            classe[q] = "graphe"        # une fondatrice est dessinée (exception de R6)
        elif t in ("coalition", "satellite") and classe[q] == "graphe":
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
            inter_lignee.append((a, b, t, e))
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

    # ================= Dates de fin lues dans le texte (citation) =================
    # Une organisation sans date de fin dans les sources structurées peut avoir sa disparition
    # écrite dans l'article (ex. le NPA en 2024). La phrase doit nommer l'organisation et ne
    # contenir qu'une année possible ; la citation est gardée dans fins_extraites.csv.
    fins_texte = []
    actifs_valides = {r["id"] for r in lire(os.path.join("manuel", "actifs.csv"))
                      if r.get("valide", "").strip().lower() == "oui"}
    sigles_saisis = {r["id"]: r["sigle"].strip() for r in lire(os.path.join("manuel", "sigles.csv")) if r["sigle"].strip()}
    for q, d in noeuds.items():
        if classe.get(q) != "graphe" or d["dissolution"] or not d["fondation"]:
            continue
        if q in actifs_valides:          # une organisation validée active n'a pas de fin (ex. PCF dissous en 1939)
            continue
        sig = RX_SIGLE_ARTICLE.search(wikitext.get(q, "")[:20000])
        noms = {nom_court(d["label"]), re.sub(r"\s*\([^)]*\)$", "", d["label"])} | ({sig.group(1)} if sig else set())
        if sigles_saisis.get(q):
            noms.add(sigles_saisis[q])
        r = preuves.fin_dans_texte(corpus, q, noms, d["fondation"])
        if r:
            d["dissolution"], d["dissolution_source"] = r[0], "wikipedia (texte)"
            fins_texte.append([q, d["label"], r[0], r[1], r[2]])
    ecrire("fins_extraites.csv", ["id", "label", "annee_fin", "citation", "source_citation"], fins_texte)
    # Noms et sigles de chaque organisation, pour trouver les mentions en clair (sans lien interne)
    noms_de = {}
    for q, d in noeuds.items():
        if classe.get(q) not in ("graphe", "etranger"):
            continue
        sig = RX_SIGLE_ARTICLE.search(wikitext.get(q, "")[:20000])
        noms_de[q] = [n for n in {re.sub(r"\s*\([^)]*\)$", "", d["label"]), sigles_saisis.get(q, ""),
                                  sig.group(1) if sig else ""} if n and (len(n) >= 4 or re.search(r"[A-Z].*[A-Z]", n))]
    stats["fins_texte"] = len(fins_texte)

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

    # ---------- R8 : chaque lien doit s'appuyer sur une citation mot pour mot ----------
    def attacher_preuve(a, b, e):
        if "manuel" in e["sources"]:
            # Le type saisi à la main est retenu tel quel (renommage, refondation, fusion...)
            typ = e.get("type_manuel", "")
            e["preuve"] = dict(preuve="manuel", citation=e.get("source_manuelle", ""),
                               source="data/manuel/aretes_manuelles.csv",
                               indice=typ if typ in REL_LIGNEE else "")
            if e.get("citation1"):
                e["preuve"].update(citation=e["citation1"][1], source=e["citation1"][0])
            return True
        p = preuves.preuve_lien(corpus, a, b, noms_de)
        if p:
            e["preuve"] = p
        return bool(p)

    valides, sans_preuve, absorptions = [], [], []
    for a, b, t, e in lignee:
        da, db = debut(a), debut(b)
        if not da or not db:
            date_manquante.append([a, lab(a), b, lab(b), t,
                                   "source" if not da else "cible"])
            continue
        if not attacher_preuve(a, b, e):
            sans_preuve.append([a, lab(a), b, lab(b), t, " | ".join(sorted(e["sources"]))])
            continue
        if t == "passage" and "manuel" in e["sources"] and str(e.get("date", "")).isdigit():
            # Passage de militants saisi à la main, daté : la cible peut exister depuis longtemps
            # (Ligue communiste dans la SFIO en 1934) ; il suffit que les deux vivent à cette date
            an_p = int(e["date"])
            if da[0] <= an_p <= (noeuds[a]["dissolution"] or 9999) and db[0] <= an_p <= (noeuds[b]["dissolution"] or 9999):
                valides.append((a, b, t, e))
                continue
        if db[0] < da[0] or (db[0] == da[0] and da[1] and db[1] and db[1] < da[1]):
            # La cible existait déjà : absorption si la source disparaît dans une cible encore vivante
            fin_a, fin_b = noeuds[a]["dissolution"], noeuds[b]["dissolution"]
            if t != "scission" and fin_a and fin_a > da[0] and (not fin_b or fin_b >= fin_a):
                e["date_absorption"] = fin_a
                absorptions.append((a, b, "absorption", e))
                continue
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
    # (filiations et scissions), sauf succession directe (voir succession_directe).
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

    def succession_directe(a, c):
        """A finit l'année où C naît : A s'est fondue elle-même dans C (POSR -> SFIO en 1905),
        même si une scission de A (le PSF de 1902) y a mené aussi. Jamais redondant."""
        fin_a = annee(noeuds[a].get("dissolution")) or annee(noeuds[a].get("fin_deduite"))
        dc = debut(c)
        return bool(fin_a and dc and abs(fin_a - dc[0]) <= 1)

    reduites, gardees = [], []
    for a, b, t, e in valides:
        if t == "filiation" and not succession_directe(a, b) and (p := chemin(a, b)):
            fil[a].discard(b)
            reduites.append([a, lab(a), b, lab(b), " -> ".join(lab(x) for x in p)])
        else:
            gardees.append((a, b, t, e))

    # ---------- 1.2 Relations typées ----------
    # renommage, scission, fusion, absorption, refondation, filiation_idéologique (+ passage).
    # Plusieurs prédécesseurs et un successeur : fusion, jamais scission (ex. Ensemble).
    parents_lin, enfants_fil = defaultdict(list), defaultdict(list)
    for a, b, t, _ in gardees:
        if t in ("filiation", "scission"):
            parents_lin[b].append(a)
        if t == "filiation":
            enfants_fil[a].append(b)
    # Ordre des règles : (1) le champ de la citation décide (« scission de » -> scission, « fusion de »
    # -> fusion) ; (2) continuation 1.2b : « remplacé par », « successeur », « précédent »... et fin du
    # prédécesseur = début du successeur -> renommage, les autres apports devenant des fusions
    # secondaires ; (3) sinon, plusieurs prédécesseurs -> fusion (1.2a) ; (4) sinon selon la citation.
    RX_SUCCESSION_WD = re.compile(r"remplac|suivi par|précédé par|successeur|prédécesseur|wikipedia:(?:pred|succ)$", re.I)
    def periode(citation, source, cible):
        """Période écrite après le lien dans l'infobox : « [[Front de gauche]] <small>(2008-2016)</small> »."""
        lang = source.split(":", 1)[0]
        for morceau in re.split(r"<br\s*/?>", citation):
            if any(corpus.resoudre(lang, m.group(1)) == cible for m in preuves.RX_LIEN.finditer(morceau)):
                m = re.search(r"\(\s*(?:depuis\s+)?(1[89]\d\d|20\d\d)\s*(?:[-–]\s*(1[89]\d\d|20\d\d))?", morceau)
                if m:
                    return int(m.group(1)), int(m.group(2)) if m.group(2) else None
                break
        return None, None

    def fusion_tardive(a, b, p):
        """« fusion de = … Ensemble ! <small>(2025)</small> » dans l'infobox de L'Après, fondée en 2024 :
        une fusion datée après la fondation du descendant n'est pas une continuation."""
        if not p.get("citation") or p.get("source") != f"fr:{noeuds[b]['label']}":
            return None
        an, _fin = periode(p["citation"], p["source"], a)
        f_b = noeuds[b]["dissolution"] or noeuds[b].get("fin_deduite") or 9999
        return an if an and noeuds[b]["fondation"] < an <= f_b else None

    liens, contradictions = [], []
    for a, b, t, e in gardees:
        p = e["preuve"]
        indice, champ_t = p.get("indice", ""), preuves.type_du_champ(p.get("champ", ""))
        fin_a = noeuds[a]["dissolution"]
        colle = bool(fin_a) and abs(fin_a - noeuds[b]["fondation"]) <= 1
        dit_succession = champ_t == "succession" or indice == "renommage" or \
            any(RX_SUCCESSION_WD.search(r) for r in e["relations"])
        if t == "passage":
            rel = "passage"
        elif p.get("preuve") == "manuel" and indice:
            rel = indice               # lien saisi à la main : son type fait foi
        elif champ_t == "scission":
            rel = "scission"
        elif dit_succession and colle and t != "scission" and not (champ_t == "fusion" and fusion_tardive(a, b, p)):
            rel = "renommage"          # continuation (1.2b), même si l'infobox du successeur dit « fusion de »
        elif champ_t == "fusion":
            rel = "fusion"
        elif len(parents_lin[b]) >= 2:
            rel = "fusion"
        elif t == "scission":
            rel = "scission"
        elif indice == "refondation" or (dit_succession and not colle and fin_a):
            rel = "refondation"
        elif p["preuve"] == "deduit":
            rel = "filiation_idéologique"      # la citation cite l'autre sans dire la relation
        else:
            rel = "renommage" if colle else "refondation"
        # 1.2c : le type doit être compatible avec le champ de la citation
        if (champ_t == "scission" and rel != "scission") or (champ_t == "fusion" and rel not in ("fusion", "renommage")):
            contradictions.append((a, b, t, e, rel, champ_t))
            continue
        liens.append((a, b, rel, e))
    # Un seul renommage (continuation) par successeur : la source qui a vécu le plus longtemps ;
    # les autres deviennent des fusions secondaires (ex. SFIO -> PS 1969, avec UCRG, UGCS, CIR).
    par_cible = defaultdict(list)
    for i, (a, b, rel, e) in enumerate(liens):
        if rel == "renommage":
            par_cible[b].append(i)
    for b, idx in par_cible.items():
        if len(idx) > 1:
            garde_i = max(idx, key=lambda i: (noeuds[liens[i][0]]["dissolution"] or 9999) - noeuds[liens[i][0]]["fondation"])
            for i in idx:
                if i != garde_i:
                    a_, b_, _, e_ = liens[i]
                    liens[i] = (a_, b_, "fusion", e_)
    for a, b, t, e, rel, champ_t in contradictions:
        anomalies.append(ligne_anomalie(a, b, t, f"type de relation contredit par la citation : « {rel} » "
                                                 f"mais le champ dit « {champ_t} »"))
    stats["contradictions_type"] = len(contradictions)
    liens += absorptions
    # R9 : A (française) -> F (étrangère) -> B (française), chaque étape citée : lien indirect en
    # pointillés de A vers B ; F n'est nommée que dans l'infobulle du lien.
    vers_etr, depuis_etr = defaultdict(list), defaultdict(list)
    for a_, _, b_, _, t_, ens in hors:
        if t_ in ("filiation", "scission"):
            if classe.get(a_) == "graphe" and classe.get(b_) == "etranger":
                vers_etr[b_].append(a_)
            elif classe.get(a_) == "etranger" and classe.get(b_) == "graphe":
                depuis_etr[a_].append(b_)
    deja = {(a_, b_) for a_, b_, _, _ in liens}
    for f_, sources in vers_etr.items():
        for a_ in sources:
            for b_ in depuis_etr.get(f_, []):
                if a_ == b_ or (a_, b_) in deja or not debut(a_) or not debut(b_) or debut(b_) <= debut(a_):
                    continue
                p1, p2 = preuves.preuve_lien(corpus, a_, f_), preuves.preuve_lien(corpus, f_, b_)
                if not p1 or not p2:
                    continue
                e_ = dict(type="filiation", sources={"indirect"}, relations={"indirect"}, intermediaire=f_,
                          preuve=dict(preuve="deduit", citation=p1["citation"], source=p1["source"], indice=""),
                          preuve2=p2)
                liens.append((a_, b_, "indirect", e_))
                deja.add((a_, b_))
    stats["liens_indirects"] = sum(1 for l in liens if l[2] == "indirect")

    # ================= Fin de vie et activité =================
    successeur = {a for a, b, rel, _ in liens if rel in REL_SUCCESSION}
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
                    if a == q and rel in REL_SUCCESSION]
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
        # Addendum 3 bis, 2 : régionaliste ou autonomiste d'après l'idéologie ou les catégories
        ideo = " ".join(x for x, _ in d["ideologies"])
        d["regionaliste"] = bool(RX_REGIONALISTE.search(ideo + " " + tout)
                                 or "régionaliste / autonomiste" in d["courants"])
        # 2.1 : la voie suit la famille politique (idéologie), pas la région ; l'outre-mer va dans
        # la voie de sa famille. Sans famille reconnue : écartée (plus de voie « à classer »).
        d["famille"] = famille or "à classer"
        d["famille_note"] = ""

    # Famille héritée du parent : une organisation issue d'une scission, d'un renommage ou
    # d'une refondation, dont les sources ne donnent qu'un courant générique (communiste,
    # social-démocrate, écosocialiste) et seulement par Wikidata (pas d'article à lire), prend la
    # famille précise de son parent (ex. NPA-R et NPA-A, issus du NPA trotskyste, que Wikidata dit
    # seulement « communisme » ou « écosocialisme » et qui n'ont pas d'article Wikipédia).
    # La voie et la couleur changent ; le lien de lignée, lui, a sa citation. Liste : familles_heritees.csv.
    GENERIQUES = {"communiste", "social-démocrate", "écosocialiste"}
    PRECISES = {"trotskystes", "maoïstes", "anarchistes et libertaires"}
    heritees, deja = [], set()
    for a, b, rel, e in liens:
        if rel not in ("scission", "renommage", "refondation"):
            continue
        da, db = noeuds.get(a), noeuds.get(b)
        if not da or not db or da["famille"] not in PRECISES or db["famille"] == da["famille"]:
            continue
        if "correction" in {s for ss in db["courants"].values() for s in ss}:
            continue                       # courant saisi à la main : il l'emporte
        if not set(db["courants"]) or not set(db["courants"]) <= GENERIQUES:
            continue
        # Seulement faute de texte : courants connus par Wikidata seul (pas d'article, pas
        # d'infobox). Une organisation dont l'article dit « communiste » ou « socialiste » garde
        # cette famille (ex. Gauche socialiste, courant du PS issu de la LCR).
        if {s for ss in db["courants"].values() for s in ss} != {"wikidata"}:
            continue
        if b in deja or a in deja:
            continue                       # pas d'héritage en cascade
        ancienne = db["famille"]
        db["famille"] = db["famille_courant"] = da["famille"]
        db["courant_principal"] = da["courant_principal"]   # et sa couleur
        db["famille_note"] = f"famille déduite du parent : {da['label']} ({rel})"
        deja.add(b)
        p = e.get("preuve") or {}
        heritees.append([b, db["label"], ancienne, da["famille"], a, da["label"], rel,
                         " | ".join(sorted(db["courants"])), p.get("citation", ""),
                         p.get("source", "")])
    ecrire("familles_heritees.csv", ["id", "label", "famille_par_courant", "famille_retenue",
                                     "parent", "parent_label", "lien", "courants", "citation",
                                     "source_citation"], heritees)
    stats["familles_heritees"] = len(heritees)

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
    # Tableaux des membres des Internationales (scripts/tableaux.py) : période et citation de la ligne
    # (ex. en:Second International : « [[French Workers' Party]] (POF) | 1889–1902 »).
    tableaux = defaultdict(list)
    for r in lire(os.path.join("sortie", "affiliations_tableaux.csv")):
        a, b = r["party_id"], r["international_id"]
        if a in classe and b in classe and classe[a] == "graphe" and classe[b] == "internationale" \
                and corpus.verifier(r["citation"], r["source_citation"]):
            tableaux[(a, b)].append(r)
    deja = {(a, b) for a, b, _ in affil_brutes}
    for (a, b) in sorted(set(tableaux) - deja):
        affil_brutes.append((a, b, dict(sources={"tableau"}, type="appartenance")))
    stats["affiliations_tableaux"] = len(tableaux)

    # R7 : une affiliation n'existe que si l'article de l'organisation elle-même la cite, ou si le
    # tableau des membres de l'Internationale la donne avec ses années.
    affil_ok, affil_sans = [], []
    for a, b, e in affil_brutes:
        if (a, b) in tableaux and not preuves.preuve_affiliation(corpus, a, b):
            r = tableaux[(a, b)][0]
            e["preuve"] = dict(preuve="explicite", citation=r["citation"], source=r["source_citation"], rang=0)
            affil_ok.append((a, b, e))
            continue
        if "manuel" in e["sources"]:
            # Affiliation saisie à la main (aretes_manuelles.csv, type appartenance) : la citation
            # vient de l'article de l'Internationale quand l'organisation n'a pas d'article (R7 assoupli).
            e["preuve"] = dict(preuve="manuel", citation=e.get("source_manuelle", ""),
                               source="data/manuel/aretes_manuelles.csv", rang=0)
            affil_ok.append((a, b, e))
            continue
        p = preuves.preuve_affiliation(corpus, a, b)
        if p:
            e["preuve"] = p
            affil_ok.append((a, b, e))
        else:
            affil_sans.append([a, lab(a), b, lab(b), " | ".join(sorted(e["sources"]))])
    # Successeur par renommage sans article à lui (NPA -> NPA-L'Anticapitaliste, un seul article pour
    # les deux) : il garde les affiliations que l'infobox de cet article donne au présent. Ce n'est pas
    # un héritage (R7) : c'est le même article, qui décrit l'organisation actuelle.
    sans_article = {q for q in noeuds if not any(l_ == "fr" for l_, _, _ in corpus.textes.get(q, []))}
    deja_aff = {(x, i) for x, i, _ in affil_ok}
    for (x, y), e_ in aretes.items():
        if y in sans_article and noeuds.get(y, {}).get("actif") and e_["type"] == "filiation" \
                and noeuds[x]["dissolution"] and abs(noeuds[x]["dissolution"] - (noeuds[y]["fondation"] or 0)) <= 1:
            for x2, i, ea in list(affil_ok):
                if x2 == x and (y, i) not in deja_aff and ea["preuve"].get("citation", "").lstrip().startswith("|"):
                    affil_ok.append((y, i, dict(sources={f"successeur sans article ({lab(x)})"},
                                                type="appartenance", preuve=dict(ea["preuve"]))))
                    deja_aff.add((y, i))
                    stats["affiliations_successeur"] = stats.get("affiliations_successeur", 0) + 1
    affil_brutes = affil_ok
    inter_utiles = {b for _, b, _ in affil_brutes}
    # 1.3 Succession entre Internationales : seulement renommage, fusion ou refondation, avec
    # citation, et sans chevauchement (la précédente a disparu). Le reste : ligne « Scissions ».
    def succession_confirmee(a, b, p):
        """Un simple champ « précédent » / « suivant » ne suffit pas (ex. Kominform et Komintern) :
        l'autre article doit confirmer par un champ de succession en retour. Une phrase explicite
        ou un champ « fusion de » suffit."""
        if not p["citation"].lstrip().startswith("|") or preuves.type_du_champ(p.get("champ", "")) != "succession":
            return True
        x, y = (a, b) if p.get("cote") == "descendant" else (b, a)
        return any(preuves.type_du_champ(ch) == "succession" for _, _, ch in preuves.occurrences(corpus, x, y))

    pred, scissions_inter, info_succ = defaultdict(list), defaultdict(list), {}
    # Addendum 5, B : chaque relation entre Internationales est typée et citée. Succession : seulement si
    # la citation dit fusion, renommage ou refondation (un champ « précédent » ne suffit pas : Kominform).
    # Scission : seulement si la citation dit scission. Le reste (filiation) reste dans la famille, hors
    # des lignes « Succession » et « Scissions » de la clé. Une négation (« refuse cette fusion ») annule.
    filiations_inter, info_rel = defaultdict(list), {}
    RX_NEGATION = re.compile(r"refus\w*\s+(?:cette|la|de la|toute)?\s*(?:fusion|réunification)", re.I)
    for a, b, t, e in inter_lignee:
        da, db = debut(a), debut(b)
        if "manuel" in e["sources"] and e.get("type_manuel", "") in ("renommage", "fusion", "refondation"):
            # Succession saisie à la main : « lang:Titre : « citation » » (citation revérifiée par verifier.py)
            m = re.fullmatch(r"\s*(\w+:[^:]+?)\s*:\s*«\s*(.+?)\s*»\s*", e.get("source_manuelle", ""), re.S)
            if m and corpus.verifier(m.group(2), m.group(1)):
                pred[b].append(a)
                info_succ[b] = (e.get("type_manuel", ""), dict(citation=m.group(2), source=m.group(1)))
                info_rel[(a, b)] = ("succession", e.get("type_manuel", ""), dict(citation=m.group(2), source=m.group(1)))
            else:
                stats["successions_manuelles_sans_citation"] = stats.get("successions_manuelles_sans_citation", 0) + 1
            continue
        if da and db and db < da:
            anomalies.append(ligne_anomalie(a, b, t, "lien entre deux Internationales de sens contraire au temps"))
            continue
        p = preuves.preuve_lien(corpus, a, b)
        if not p:
            continue
        fin_a = noeuds[a]["dissolution"]
        chevauche = not fin_a or (db and fin_a > db[0] + 1)
        ind = p["indice"]
        nie = bool(RX_NEGATION.search(p.get("citation", "")))
        if t != "scission" and not chevauche and not nie and succession_confirmee(a, b, p) and \
                ind in ("renommage", "fusion", "refondation"):
            pred[b].append(a)
            info_succ[b] = (ind, p)
            info_rel[(a, b)] = ("succession", ind, p)
        elif ind == "scission" or (t == "scission" and re.search(r"scission|split", p.get("citation", ""), re.I)):
            scissions_inter[b].append(a)
            info_rel[(a, b)] = ("scission", "scission", p)
        else:
            filiations_inter[b].append(a)
            info_rel[(a, b)] = ("filiation", "filiation" if not nie else "filiation (fusion refusée)", p)
    # Successions lues dans le texte des articles des Internationales : lien vers une Internationale
    # qui avait disparu (au plus 15 ans avant), avec un mot de refondation, renommage, fusion ou succession.
    ids_inter = {q for q in noeuds if classe[q] == "internationale"}
    for b in ids_inter:
        cibles = {corpus.resoudre(lang, m.group(1)) for lang, _t, txt in corpus.textes.get(b, [])
                  for m in preuves.RX_LIEN.finditer(txt)}
        for a in (cibles & ids_inter) - {b} - set(pred[b]):
            fa, fb = noeuds[a]["dissolution"], noeuds[b]["fondation"]
            if not fa or not fb or not (fa - 1 <= fb <= fa + 15):
                continue
            p = preuves.preuve_lien(corpus, a, b)
            if p and p["preuve"] == "explicite" and p["indice"] in ("refondation", "renommage", "fusion") \
                    and not RX_NEGATION.search(p.get("citation", "")) and succession_confirmee(a, b, p):
                pred[b].append(a)
                info_succ[b] = (p["indice"], p)
                info_rel[(a, b)] = ("succession", p["indice"], p)
                for liste in (scissions_inter[b], filiations_inter[b]):
                    if a in liste:
                        liste.remove(a)
    # Les ancêtres des Internationales utilisées sont gardés aussi : prédécesseurs (succession), mais
    # aussi l'Internationale dont elles sont issues par scission, et les parentes saisies à la main
    # (internationales_filles.csv). Sans cela, la famille de la QI est coupée : le CIQI, la LIT-QI et
    # le CIO, sans membre français dessiné, disparaissaient (QI -> CIQI -> LCI, QI-SU -> LIT -> CRP-QI).
    parentes_man = defaultdict(set)
    for r in lire("manuel/internationales_filles.csv"):
        if r.get("parente", "").strip() in noeuds and r.get("fille", "").strip() in noeuds:
            parentes_man[r["fille"].strip()].add(r["parente"].strip())
    ajoutees_ancetres = set()
    pile = list(inter_utiles)
    while pile:
        x = pile.pop()
        for p in list(pred[x]) + list(scissions_inter.get(x, [])) + list(filiations_inter.get(x, [])) \
                + sorted(parentes_man.get(x, ())):
            if p not in inter_utiles and classe.get(p) == "internationale":
                inter_utiles.add(p)
                ajoutees_ancetres.add(p)
                pile.append(p)
    stats["internationales_ancetres"] = len(ajoutees_ancetres)

    def cle_couleur(label):
        return next((c for c, rx in COULEURS_INTER if re.search(rx, label, re.I)), "autre")

    lignes_inter = []
    for q in sorted(inter_utiles, key=lambda q: (noeuds[q]["fondation"] or 9999, lab(q))):
        d = noeuds[q]
        # Nom exact seulement : « Quatrième Internationale (lambertiste) » n'est pas la QI
        typ, p = info_succ.get(q, ("", {}))
        lignes_inter.append([q, d["label"], SIGLES_INTER.get(d["label"], ""), d["fondation"] or "",
                             d["dissolution"] or "", " | ".join(pred[q]), cle_couleur(d["label"]),
                             typ, p.get("citation", ""), p.get("source", ""),
                             " | ".join(x for x in scissions_inter[q] if x in noeuds)])

    # Dates d'adhésion saisies à la main (data/manuel/affiliations_dates.csv, source obligatoire)
    dates_saisies = {(r["party_id"], r["international_id"]): r
                     for r in lire(os.path.join("manuel", "affiliations_dates.csv"))
                     if r.get("source", "").strip() and (r.get("start", "").strip() or r.get("end", "").strip())}
    lignes_affil, a_dater = [], []
    rx_entree = re.compile(r"(?:adh[èée]r\w*|rejoin\w*|rejoint|membre depuis|affili\w*)[^.\n]{0,60}?\b(1[89]\d\d|20\d\d)", re.I)
    rx_sortie = re.compile(r"(?:quitt\w*|exclu\w*|rompt|rupture|désaffili\w*)[^.\n]{0,60}?\b(1[89]\d\d|20\d\d)", re.I)
    # Une section collée au bandeau de son Internationale (origines.csv) garde sa bande : rendu.py
    # dessine le bandeau jusqu'à elle, puis cette bande le prolonge (ex. IO 1889, puis SFIO 1905-1914).
    for a, b, e in affil_brutes:
        da, di = noeuds[a], noeuds[b]
        p = e["preuve"]
        cit = [p["preuve"], p["citation"], p["source"]]
        s = dates_saisies.get((a, b))
        if s:
            lignes_affil.append([a, b, s["start"].strip(), s["end"].strip(), "known",
                                 f"manuel : {s['source'].strip()}", lab(a), lab(b)] + cit)
            continue
        if (a, b) in tableaux:
            # Une ligne par période (un parti peut adhérer, partir puis revenir)
            for r in tableaux[(a, b)]:
                fin_t = r["end"] or ("toujours membre" if da.get("actif") else "")
                lignes_affil.append([a, b, r["start"], fin_t, "known", "tableau", lab(a), lab(b),
                                     "explicite", r["citation"], r["source_citation"]])
            continue
        # Dates lues dans la citation elle-même ; « toujours membre » si l'infobox actuelle d'une
        # organisation active la cite (le champ d'infobox décrit l'affiliation présente).
        m_e, m_s = rx_entree.search(p["citation"]), rx_sortie.search(p["citation"])
        entree = m_e.group(1) if m_e else ""
        sortie = m_s.group(1) if m_s else ("toujours membre" if da.get("actif") and p["citation"].lstrip().startswith("|")
                                           else "")
        # Période écrite juste après le lien dans l'infobox : « [[Parti de la gauche européenne]]
        # <small>(depuis 2004)</small> », « [[Alliance radicale européenne|ARE]] <small>(1994-1999)</small> »
        if not (entree and sortie) and p.get("source", "").count(":") >= 1 and p["citation"].lstrip().startswith("|"):
            d_p, f_p = periode(p["citation"], p["source"], b)
            if d_p:
                entree = str(d_p)
                sortie = str(f_p) if f_p else ("toujours membre" if da.get("actif") else "")
        if entree and sortie:
            lignes_affil.append([a, b, entree, sortie, "known", "citation", lab(a), lab(b)] + cit)
            continue
        # Période inconnue : recouvrement de la vie du parti et de celle de l'Internationale
        fin_a = da["dissolution"] or da["fin_deduite"] or None
        debut_ = max(x for x in (da["fondation"], di["fondation"], 0) if x is not None) or ""
        fins = [x for x in (fin_a, di["dissolution"]) if x]
        fin_ = min(fins) if fins else ""
        lignes_affil.append([a, b, entree or debut_, sortie or fin_, "unknown",
                             " | ".join(sorted(e["sources"])), lab(a), lab(b)] + cit)
        a_dater.append([a, b, entree, sortie, "", lab(a), lab(b), debut_, fin_])
    inter_sans_membre = {q for q in noeuds if classe[q] == "internationale"} - inter_utiles

    # ================= 8. Élagage strict (R5) =================
    # Gardées : les organisations actives ayant au moins un lien de lignée, et tous leurs ancêtres
    # (chemins orientés de filiation, renommage, fusion, scission ; les émanations et les passages
    # de militants ne comptent pas). Tout le reste va dans elagues.csv avec une cause.
    # Éligibles à une barre (1.5) : datées, avec une date de fin ou un statut actif validé, et une
    # famille politique reconnue. Les autres n'ont jamais de barre : a_dater.csv ou causes ci-dessous.
    orgs_a_dater, rejets = [], []
    eligibles = set()
    for q in graphe:
        d = noeuds[q]
        if not d["fondation"]:
            orgs_a_dater.append([q, lab(q), "pas de date de fondation", d["famille"]])
        elif d["statut_fin"] == "fin_inconnue":
            orgs_a_dater.append([q, lab(q), "ni date de fin, ni statut actif validé", d["famille"]])
        elif d["famille"] != "à classer":
            eligibles.add(q)
    parents_r5, voisins_r5, preuve_de = defaultdict(set), defaultdict(set), {}
    for a, b, rel, e in liens:
        if rel in REL_LIGNEE and a in eligibles and b in eligibles:
            parents_r5[b].add(a)
            voisins_r5[a].add(b)
            voisins_r5[b].add(a)
            preuve_de[(a, b)] = preuve_de[(b, a)] = e.get("preuve", {}).get("preuve", "")
    # Exclusions à retester : gardées seulement avec un lien documenté explicitement (citation)
    for q in sorted(eligibles):
        if RX_A_RETESTER.search(lab(q)):
            explicites = {y for y in voisins_r5[q] if preuve_de.get((q, y)) in ("explicite", "manuel")}
            if not explicites:
                rejets.append([q, lab(q), "exclusion à retester : aucun lien documenté explicitement"])
                eligibles.discard(q)
                for y in voisins_r5.pop(q, set()):
                    voisins_r5[y].discard(q)
                    parents_r5[y].discard(q)
                parents_r5.pop(q, None)
    actives = {q for q in eligibles if noeuds[q]["actif"]}
    garde, pile = set(), [q for q in actives if voisins_r5[q]]
    while pile:
        x = pile.pop()
        if x not in garde:
            garde.add(x)
            pile.extend(p for p in parents_r5[x] if p in eligibles)
    # Exception (data/manuel/origines.csv) : origines historiques dessinées sans descendance active,
    # ex. la Première Internationale (AIT) et sa branche anti-autoritaire. Il leur faut quand même un
    # lien vers une autre organisation affichée (porte finale ci-dessous).
    lignes_origines = [r for r in lire("manuel/origines.csv") if r.get("source", "").strip()]
    origines = {r["id"].strip() for r in lignes_origines}
    garde |= origines & eligibles
    stats["origines"] = len(origines & garde)
    # Incontournables (data/manuel/incontournables.csv) sans descendance active : dessinés en
    # « branche éteinte », avec leurs seuls liens documentés (aucun lien inventé pour les relier)
    incontournables = {r["id"].strip() for r in lire("manuel/incontournables.csv") if r.get("id", "").strip()}
    branches_eteintes = (incontournables & eligibles) - garde
    garde |= branches_eteintes
    stats["branches_eteintes"] = len(branches_eteintes)
    # Addendum 3, B2 et 3 bis, 4 : colonne « Sans généalogie documentée », décidée dans
    # data/manuel/actifs_absents.csv (decision = colonne, avec la citation de l'article)
    # Addendum 5, F1 : famille décidée à la main, citation à l'appui (data/manuel/famille_decision.csv) ;
    # la dernière ligne d'un identifiant l'emporte
    for q, r in {r.get("id", "").strip(): r for r in lire(os.path.join("manuel", "famille_decision.csv"))}.items():
        if q in noeuds and r.get("famille", "").strip() and r.get("source", "").strip():
            noeuds[q]["famille"] = noeuds[q]["famille_courant"] = r["famille"].strip()
            noeuds[q]["famille_note"] = f"famille décidée : {r['source'].strip()}"
            stats["familles_decidees"] += 1
    sans_genealogie = set()
    derniere = {r.get("id", "").strip(): r for r in lire(os.path.join("manuel", "actifs_absents.csv"))}
    for q, r in derniere.items():         # le fichier ne fait que grandir : la dernière ligne l'emporte
        if r.get("decision", "").strip() != "colonne" or q not in noeuds or not r.get("source", "").strip():
            continue
        if not noeuds[q]["fondation"]:
            stats["sans_genealogie_sans_date"] += 1
            continue
        d = noeuds[q]
        d["sans_genealogie"] = True
        d["actif"] = True
        if not d["dissolution"]:             # décision « colonne » : active (Ligue trotskyste de France)
            d["statut_fin"] = "actif_valide"
        if r.get("famille", "").strip():
            d["famille"] = d["famille_courant"] = r["famille"].strip()
        else:
            d["famille"] = "aucune"          # aucune famille de l'arbre : couleur neutre
            d["famille_courant"] = ""
        d["sans_genealogie_source"] = r["source"].strip()
        sans_genealogie.add(q)
    garde |= sans_genealogie
    stats["sans_genealogie"] = len(sans_genealogie)
    exemptes = origines | branches_eteintes | sans_genealogie
    # Porte finale : chaque organisation gardée a au moins un lien vers une autre gardée
    while True:
        seules = {q for q in garde if not (voisins_r5[q] & garde)} - exemptes   # une origine peut n'avoir qu'un lien de composante
        if not seules:
            break
        for q in seules:
            rejets.append([q, lab(q), "porte finale : aucun lien vers une organisation affichée"])
        garde -= seules
    # R10 : un parti d'outre-mer n'est gardé qu'avec un lien documenté vers une organisation
    # métropolitaine affichée. Les autres vont dans hors_perimetre.csv.
    hors_perim = []
    while True:
        a_retirer = {q for q in garde if noeuds[q]["outre_mer"]
                     and not any(not noeuds[y]["outre_mer"] for y in voisins_r5[q] & garde)}
        if not a_retirer:
            break
        for q in a_retirer:
            hors_perim.append([q, lab(q), "outre-mer sans lien documenté vers une organisation métropolitaine affichée"])
        garde -= a_retirer
        while True:                       # la porte finale, à nouveau
            seules = {q for q in garde if not (voisins_r5[q] & garde)} - exemptes
            if not seules:
                break
            for q in seules:
                rejets.append([q, lab(q), "porte finale : aucun lien vers une organisation affichée"])
            garde -= seules
    composante, vus = {}, set()
    for q in eligibles:
        if q in vus:
            continue
        comp, pile = set(), [q]
        while pile:
            x = pile.pop()
            if x not in comp:
                comp.add(x)
                pile.extend(voisins_r5[x])
        vus |= comp
        for x in comp:
            composante[x] = bool(comp & actives)
    dates_manquantes = {r[0] for r in orgs_a_dater}
    rejetees = {r[0] for r in rejets}
    lignes_elag, actives_sans_lien = [], []
    for q in sorted(noeuds, key=lab):
        d = noeuds[q]
        statut = d.get("statut_fin", "")
        if classe[q] == "graphe" and q not in garde:
            if q in dates_manquantes:
                cause = "a_dater"
            elif q in {r[0] for r in hors_perim}:
                cause = "hors_perimetre"
            elif not voisins_r5[q] and (d["outre_mer"] or d["regionaliste"]):
                # Addendum 3 bis, 2 et R10 : jamais « isolee » pour un régionaliste ou un parti
                # d'outre-mer sans lignée
                cause = "hors_perimetre"
                hors_perim.append([q, lab(q), "outre-mer sans lignée documentée" if d["outre_mer"]
                                   else "régionaliste ou autonomiste sans lignée documentée"])
            elif d["famille"] == "à classer":
                cause = "famille_non_determinee"
            elif q in rejetees:
                cause = "rejet_porte"
            elif not voisins_r5[q]:
                cause = "isolee"
                if d["actif"]:
                    actives_sans_lien.append(q)
            elif not composante.get(q):
                cause = "arbre_sans_organisation_active"
            else:
                cause = "non_ancetre_d_une_active"
            lignes_elag.append([q, lab(q), cause, statut, d.get("famille", ""), ""])
        elif classe[q] in ("coalition", "satellite"):
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
                            " | ".join(sorted(lab(s) for s in emanations.get(q, ()))),
                            "oui" if d.get("sans_genealogie") else "",
                            d.get("sans_genealogie_source", "")])
    ecrire("noms_successifs.csv", ["id", "label", "annee", "nom", "citation", "source"],
           noms_successifs(corpus, garde))
    ecrire("organisations.csv",
           ["id", "label", "nom_court", "fondation", "fondation_mois", "fondation_source",
            "fondation_autres_sources", "dissolution", "dissolution_mois", "dissolution_source",
            "fin_deduite", "fin_deduite_source", "actif", "famille", "outre_mer", "courants",
            "courants_sources", "courant_principal", "famille_courant", "perimetre_douteux",
            "sources", "journaux", "statut_fin", "actif_auto", "garde", "organisations_liees",
            "sans_genealogie", "sans_genealogie_source"],
           lignes_orgs)
    ecrire("elagues.csv", ["id", "label", "cause", "statut_fin", "famille", "detail"], lignes_elag)
    ecrire("a_dater.csv", ["id", "label", "raison", "famille"], orgs_a_dater)
    hors_perim += [[q, lab(q), f"position du centre ({r['positionnement']}) : {r['source']} : « {r['citation']} »"]
                   for q, r in centre_hors.items() if q in noeuds]
    ecrire("hors_perimetre.csv", ["id", "label", "raison"], hors_perim)

    # ---------- 1.6 Étiquettes : un sigle court pour chaque organisation ----------
    saisis = {r["id"]: r for r in lire(os.path.join("manuel", "sigles.csv"))}
    etiquettes = {}
    for q in graphe:
        etiquettes[q] = etiquette_de(q, noeuds[q]["label"], saisis.get(q, {}).get("sigle", ""), wikitext.get(q, ""))
    # Homonymes dans toute la base (0.5, 1.6) : on ajoute un lieu pour l'outre-mer, sinon l'année
    # de fondation, ex. « PCR (Réunion) » et « PCR (2024) », « PT (1991) » et « PT (2015) ».
    RX_LIEU = re.compile(r"Réunion|Guadeloupe|Martinique|Guyane|Mayotte|Nouvelle-Calédonie|Polynésie|Wallis")

    def lieu(q):
        d = noeuds[q]
        if not d["outre_mer"]:
            return ""
        m = RX_LIEU.search(" ".join([d["label"], d["categories"]] + d.get("cats_article", [])))
        return m.group(0) if m else ""
    compte = Counter(etiquettes[q][0] for q in graphe)
    for q in graphe:
        e, o = etiquettes[q]
        if compte[e] > 1:
            l_ = lieu(q)
            autres = [x for x in graphe if x != q and etiquettes[x][0] == e]
            if l_ and not any(lieu(x) == l_ for x in autres):
                etiquettes[q] = (f"{e} ({l_})", o + " + lieu (homonyme)")
            else:
                etiquettes[q] = (f"{e} ({noeuds[q]['fondation'] or '?'})", o + " + année (homonyme)")
    ecrire("etiquettes.csv", ["id", "etiquette", "origine", "nom_complet", "affiche"],
           [[q, etiquettes[q][0], etiquettes[q][1], lab(q), "oui" if q in garde else ""]
            for q in sorted(graphe, key=lab)])
    stats["etiquettes_doublons"] = sum(1 for n in Counter(etiquettes[q][0] for q in garde).values() if n > 1)

    # ---------- 1.7 Couverture : incontournables et test de régression ----------
    chemin_inc = os.path.join(MANUEL, "incontournables.csv")
    if not os.path.exists(chemin_inc):
        par_nom = {}
        for q in noeuds:
            par_nom.setdefault(lab(q), q)
        ecrire("incontournables.csv", ["id", "nom"],
               [[par_nom.get(n, ""), n] for n in INCONTOURNABLES], dossier=MANUEL)
    cause_de = {l[0]: (l[2], l[5]) for l in lignes_elag}
    a_dater_de = {r[0]: r[2] for r in orgs_a_dater}
    sans_citation = defaultdict(list)
    for r in sans_preuve:
        sans_citation[r[0]].append(f"{r[1]} -> {r[3]}")
        sans_citation[r[2]].append(f"{r[1]} -> {r[3]}")

    def explication(q):
        if q not in noeuds:
            return "absente des sources (Wikidata, Wikipédia)"
        if classe.get(q) != "graphe":
            return f"hors du graphe : {raison.get(q) or classe.get(q)}"
        cause, detail = cause_de.get(q, ("", ""))
        lien_manquant = {"isolee": "aucun lien de lignée cité vers une organisation affichée",
                         "arbre_sans_organisation_active": "aucune organisation active validée descendante",
                         "non_ancetre_d_une_active": "n'est ancêtre d'aucune organisation active affichée",
                         "a_dater": f"pas de barre : {a_dater_de.get(q, '')}",
                         "famille_non_determinee": "famille politique non reconnue",
                         "hors_perimetre": "outre-mer sans lien vers la métropole",
                         "rejet_porte": "rejetée par la porte finale"}.get(cause, cause or "?")
        if sans_citation.get(q):
            lien_manquant += " ; liens sans citation : " + " ; ".join(sans_citation[q][:4])
        return lien_manquant
    manquants_inc = []
    for r in lire(os.path.join("manuel", "incontournables.csv")):
        q = r["id"].strip()
        if q and q in garde:
            continue
        pourquoi = explication(q) if q else "identifiant à renseigner dans incontournables.csv"
        rejets.append([q, r["nom"], f"incontournable absent : {pourquoi}"])
        manquants_inc.append((r["nom"], pourquoi))
    # Journal exhaustif : chaque candidat des sources brutes (Wikidata data/noeuds.csv, Wikipédia
    # data/wp_noeuds.csv, nœuds manuels) qui n'est pas dessiné, avec sa raison
    brut_wd = {r["id"]: r for r in lire("noeuds.csv")}
    brut_wp = {r["id"]: r for r in lire("wp_noeuds.csv")}
    motif_rejet = {}
    for r_ in rejets:
        motif_rejet.setdefault(r_[0], r_[2])
    journal = []
    for q in sorted(set(brut_wd) | set(brut_wp) | set(noeuds), key=lambda q: (q not in noeuds, q)):
        if q in garde:
            continue
        d = noeuds.get(q)
        b = brut_wd.get(q) or brut_wp.get(q) or {}
        if d:
            actif = "oui" if d["actif"] else ("non" if d["dissolution"] or d["statut_fin"] == "fin_connue" else "inconnu")
            famille = d["famille"] if d["famille"] != "à classer" else ""
            sources_ = " | ".join(sorted(d["sources"]))
        else:
            actif = "non" if b.get("dissolution") else "inconnu"
            famille, sources_ = "", ""
        if d is None:
            raison_ = "absente après fusion des sources (doublon ou identifiant remplacé)"
            manquant = ""
        elif classe.get(q) != "graphe":
            raison_ = f"hors du graphe ({classe.get(q)}) : {raison.get(q, '')}".rstrip(" :")
            manquant = ""
        else:
            cause, detail = cause_de.get(q, ("", ""))
            raison_ = motif_rejet.get(q) or (f"{cause} : {detail}" if detail else cause) or "élaguée"
            manquant = explication(q)
        provenance = " + ".join(x for x, ok in (("Wikidata", q in brut_wd), ("Wikipédia", q in brut_wp)) if ok) or "manuel"
        journal.append([q, lab(q) if d else b.get("label", ""), actif, famille, raison_, manquant,
                        f"{provenance} ({sources_})" if sources_ else provenance])
    # Entités écartées dès la collecte par la porte politique d'arbre.py (addendum 4, 1)
    deja = {l[0] for l in journal} | set(garde)
    for r in lire("rejets_porte_arbre.csv"):
        if r["id"] not in deja:
            deja.add(r["id"])
            journal.append([r["id"], r["label"], "inconnu", "", f"écartée à la collecte : {r['raison']}", "",
                            "Wikidata (arbre.py)"])
    for r in lire("sortie/rejets_porte_tableaux.csv"):   # lignes des tableaux d'Internationales (tableaux.py)
        if r["id"] not in deja:
            deja.add(r["id"])
            journal.append([r["id"], r["label"], "inconnu", "", f"ligne de tableau écartée : {r['raison']}", "",
                            f"tableau des membres ({r['source_citation']})"])
    ecrire("elagage_rejets.csv", ["id", "label", "actif", "famille_si_connue", "raison", "lien_manquant", "source"],
           journal)
    stats["candidats_non_dessines"] = len(journal)
    # Test de couverture : chaque incontournable et Place publique ont-ils été collectés ?
    couverture = []
    a_tester = [(r["id"].strip(), r["nom"]) for r in lire("manuel/incontournables.csv")]
    if not any(q == "Q58366009" for q, _ in a_tester):
        a_tester.append(("Q58366009", "Place publique"))
    for q, nom in a_tester:
        wd, wp = q in brut_wd, q in brut_wp
        if not (wd or wp or q in noeuds):
            pourquoi = ("jamais collectée : hors de la requête Wikidata (scripts/arbre.py : pays France, type "
                        "d'organisation, propriété de succession ou idéologie) et hors des catégories Wikipédia "
                        "explorées (scripts/infobox.py, CATEGORIES)")
        elif q in garde:
            pourquoi = "dessinée" + (" (branche éteinte)" if q in branches_eteintes else "")
        else:
            pourquoi = "collectée mais non dessinée : " + (explication(q) if q in noeuds else "?")
        couverture.append([q, nom, "oui" if wd else "non", "oui" if wp else "non",
                           "manuel" if q in noeuds and not (wd or wp) else "", "oui" if q in garde else "non", pourquoi])
    ecrire("branches_eteintes.csv", ["id", "label", "raison"],
           [[q, lab(q), "incontournable sans descendance active, dessiné avec ses seuls liens documentés"]
            for q in sorted(branches_eteintes, key=lab)])
    ecrire("couverture.csv", ["id", "nom", "collectee_wikidata", "collectee_wikipedia", "autre_source", "dessinee",
                              "explication"], couverture)
    disparues = [[q, nom, explication(q)] for q, nom in sorted(precedents.items(), key=lambda x: x[1])
                 if q not in garde]
    # Addendum 4, 5 : un incontournable absent (NPA, NPA-R...) est listé à chaque exécution, pas
    # seulement à celle où il a disparu
    deja_r = {r[0] for r in disparues}
    disparues += [[q, nom, "incontournable absent : " + explication(q)] for q, nom in a_tester
                  if q and q not in garde and q not in deja_r]
    apparues = sorted(lab(q) for q in garde - set(precedents))
    ecrire("regression.csv", ["id", "label", "raison_disparition"], disparues)
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

    def date_ev(a, b, rel, e):
        # Absorption : à la disparition de la source ; fusion datée dans l'infobox du descendant
        # (« Ensemble ! <small>(2025)</small> ») ; sinon : fondation du descendant
        if rel == "absorption":
            return e["date_absorption"], ""
        if rel == "passage" and "manuel" in e["sources"] and str(e.get("date", "")).isdigit():
            return int(e["date"]), ""          # passage saisi à la main : à sa date
        an = fusion_tardive(a, b, e.get("preuve") or {}) if rel == "fusion" else None
        if an:
            return an, ""
        return noeuds[b]["fondation"], noeuds[b]["fondation_mois"] or ""

    for a, b, rel, e in sorted(liens, key=lambda x: (date_ev(*x)[0], lab(x[0]))):
        if a in sans_date or b in sans_date:
            continue
        p = e.get("preuve", {})
        lignes_liens.append([a, b, rel, *date_ev(a, b, rel, e),
                             "oui" if e.get("meme_annee") else "", "oui" if e.get("reciproque") else "",
                             " | ".join(sorted(e["sources"])), " | ".join(sorted(e["relations"])),
                             lab(a), lab(b), p.get("preuve", ""), p.get("citation", ""), p.get("source", ""),
                             e.get("intermediaire", ""),
                             lab(e["intermediaire"]) if e.get("intermediaire") else e.get("intermediaire_nom", ""),
                             e.get("preuve2", {}).get("citation", ""), e.get("preuve2", {}).get("source", "")])
    # Composantes : une organisation de l'arbre membre d'une autre organisation de l'arbre (ex. PG et
    # POI dans LFI). Pas une lignée : un trait « collé » sans flèche, à la date où les deux existent.
    # Citation tirée de l'article du membre lui-même (comme R7), explicite seulement.
    vus_comp = set()
    for a, _la, b, _lb, _src in nationales:
        if a == b or (a, b) in vus_comp or a not in garde or b not in garde or a in sans_date or b in sans_date:
            continue
        p = preuves.preuve_affiliation(corpus, a, b)
        if not p or p["preuve"] != "explicite":
            continue
        # Période écrite après le lien dans l'infobox : « [[Front de gauche]] <small>(2008-2016)</small> ».
        # Une période finie avant la fondation du membre (ex. GDS : « LCR (1975-1994) », passé de ses
        # fondateurs) n'est pas une appartenance de l'organisation.
        debut_p, fin_p = periode(p["citation"], p["source"], b)
        f_a = noeuds[a]["dissolution"] or noeuds[a]["fin_deduite"] or 9999
        if fin_p and fin_p < noeuds[a]["fondation"]:
            continue
        vus_comp.add((a, b))
        an = max(noeuds[a]["fondation"], noeuds[b]["fondation"], debut_p or 0)
        if an > min(f_a, noeuds[b]["dissolution"] or noeuds[b]["fin_deduite"] or 9999):
            vus_comp.discard((a, b))
            continue
        mois = (noeuds[b]["fondation_mois"] if an == noeuds[b]["fondation"] else
                noeuds[a]["fondation_mois"] if an == noeuds[a]["fondation"] else "")
        lignes_liens.append([a, b, "composante", an, mois or "", "", "", "wikipedia", "membre de",
                             lab(a), lab(b), p["preuve"], p["citation"], p["source"], "", "", "", ""])
    # Composantes saisies à la main (ex. GES dans L'Après) : citation mot pour mot obligatoire.
    for r in lire("manuel/aretes_manuelles.csv"):
        if r.get("type", "").strip() != "composante":
            continue
        a, b = r.get("ancetre", "").strip(), r.get("descendant", "").strip()
        m = re.fullmatch(r"\s*(\w+:[^:]+?)\s*:\s*«\s*(.+?)\s*»\s*", r.get("source", ""), re.S)
        if (a, b) in vus_comp or a not in garde or b not in garde or a in sans_date or b in sans_date:
            continue
        if not m or not corpus.verifier(m.group(2), m.group(1)):
            stats["composantes_manuelles_sans_citation"] += 1
            continue
        vus_comp.add((a, b))
        an = (int(r["date_evenement"]) if r.get("date_evenement", "").strip().isdigit()
              else max(noeuds[a]["fondation"], noeuds[b]["fondation"]))
        lignes_liens.append([a, b, "composante", an, "", "", "", "manuel", "membre de", lab(a), lab(b),
                             "manuel", m.group(2), m.group(1), "", "", "", ""])
    stats["composantes"] = len(vus_comp)
    ecrire("liens.csv", ["source", "cible", "relation", "date_evenement", "date_evenement_mois",
                         "meme_annee", "fusion_reciproque", "sources", "relations_brutes",
                         "source_nom", "cible_nom", "preuve", "citation", "source_citation", "intermediaire",
                         "intermediaire_nom", "citation2", "source_citation2"], lignes_liens)
    ecrire("liens_sans_preuve.csv", ["source", "source_nom", "cible", "cible_nom", "type", "sources"],
           sans_preuve)
    # Extrait court de liens_candidats.csv à lire en premier : non décidés, confiance >= 0,7, touchant
    # une organisation dessinée, pas déjà dessinés ; « ligne » = numéro de ligne dans liens_candidats.csv,
    # où l'on écrit decision = oui.
    deja_l = {(r[0], r[1]) for r in lignes_liens} | {(r[1], r[0]) for r in lignes_liens}
    # Addendum 5, F4 : liens des branches éteintes à trancher en premier, quelle que soit leur
    # confiance (UEC -> UJC(ml), UJC(ml) -> PCMLF), avec leur citation
    PRIORITAIRES = [("Q3550228", "Q3550161"), ("Q3550161", "Q3366229")]
    prio = {}
    for i, r in enumerate(lire("sortie/liens_candidats.csv"), start=2):
        o_, c_ = r["org"], r["cible"]
        anc_, desc_ = (c_, o_) if r["sens"] == "cible → org" else (o_, c_)
        if (anc_, desc_) in PRIORITAIRES and not r.get("decision", "").strip():
            conf = float(r.get("confiance") or 0)
            if (anc_, desc_) not in prio or conf > prio[(anc_, desc_)][0]:
                prio[(anc_, desc_)] = (conf, i, r)
    meilleurs = {}
    for i, r in enumerate(lire("sortie/liens_candidats.csv"), start=2):
        try:
            conf = float(r.get("confiance") or 0)
        except ValueError:
            continue
        o_, c_ = r["org"], r["cible"]
        if (r.get("decision", "").strip() or conf < 0.7 or (o_, c_) in deja_l or c_ not in noeuds or o_ not in noeuds
                or not ({o_, c_} & garde)):
            continue
        k = tuple(sorted((o_, c_)))
        if k not in meilleurs or conf > meilleurs[k][0]:
            meilleurs[k] = (conf, i, r)
    a_lire = [[i, lab(r["org"]), lab(r["cible"]), r["sens"], r["type_propose"], f"{conf:.2f}",
               "oui" if r["org"] in garde and r["cible"] in garde else "une seule",
               re.sub(r"\s+", " ", r["phrase_source"])[:300], r.get("source_citation", "")]
              for conf, i, r in sorted(meilleurs.values(), key=lambda x: (-x[0], x[1]))]
    # Addendum 4, 4 : un lien écarté parce que la cible existait déjà (LCR -> PS 1974/1969, LCR -> OCI
    # 1974/1952) n'est pas dessiné ; il est proposé comme passage de militants, dans le sens de
    # l'anomalie, avec la phrase de l'article quand elle existe. Validation : une ligne de type
    # passage dans data/manuel/aretes_manuelles.csv (ce fichier-ci est régénéré à chaque exécution).
    phrases_de = defaultdict(list)
    for i, r in enumerate(lire("sortie/liens_candidats.csv"), start=2):
        phrases_de[frozenset((r["org"], r["cible"]))].append((i, r))
    manuels_ = {(r.get("ancetre", "").strip(), r.get("descendant", "").strip())
                for r in lire("manuel/aretes_manuelles.csv")}
    for an in anomalies:
        a_, b_ = an[0], an[1]
        if not an[5].startswith("type de relation erroné : la cible existait déjà") or not {a_, b_} <= garde \
                or (a_, b_) in manuels_ or (a_, b_) in deja_l:
            continue
        cands = sorted(phrases_de.get(frozenset((a_, b_)), []),
                       key=lambda x: (x[1]["type_propose"] != "passage_militants", -float(x[1]["confiance"] or 0)))
        i, r = cands[0] if cands else ("", {})
        a_lire.insert(0, [i, lab(a_), lab(b_), "org → cible", "passage", r.get("confiance", ""), "oui",
                          re.sub(r"\s+", " ", r.get("phrase_source", ""))[:300] or f"anomalie : {an[5]}",
                          (r.get("source_citation", "") + " ; " if r else "")
                          + "à valider par une ligne « passage » dans data/manuel/aretes_manuelles.csv"])
        stats["passages_proposes"] += 1
    tete = []
    for k in PRIORITAIRES:
        if k in prio:
            conf, i, r = prio[k]
            tete.append([i, lab(r["org"]), lab(r["cible"]), r["sens"], r["type_propose"], f"{conf:.2f}",
                         "oui" if r["org"] in garde and r["cible"] in garde else "une seule",
                         re.sub(r"\s+", " ", r["phrase_source"])[:300],
                         (r.get("source_citation", "") + " ; " if r.get("source_citation") else "")
                         + "branche éteinte, à trancher en premier (addendum 5, F4)"])
    a_lire = tete + [l for l in a_lire if l[0] not in {t[0] for t in tete}]
    ecrire("liens_candidats_a_lire.csv", ["ligne", "org", "cible", "sens", "type_propose", "confiance",
                                          "deux_dessinees", "phrase", "source"], a_lire)
    stats["candidats_a_lire"] = len(a_lire)

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
                          "oui" if q in garde else "", d.get("statut_fin", "")])
    ecrire("sans_date.csv", ["id", "label", "famille", "courants", "sources", "garde", "statut_fin"], lignes_sd)

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
                                   "color_key", "succession_type", "succession_citation",
                                   "succession_source", "scissions_de"], lignes_inter)
    # Internationales filles (ex. les fractions de la Quatrième Internationale) : celles qui en sont
    # issues par scission ou succession (déjà citées ci-dessus), et celles de
    # data/manuel/internationales_filles.csv (réunification, se réclame de…), citation revérifiée
    filles = []
    for l_ in lignes_inter:
        for p_ in (x for x in l_[5].split(" | ") if x):
            filles.append([p_, l_[0], l_[7] or "succession", l_[8], l_[9]])
        for p_ in (x for x in l_[10].split(" | ") if x):
            _r, _t, pp_ = info_rel.get((p_, l_[0]), ("", "", {}))
            filles.append([p_, l_[0], "scission", pp_.get("citation", ""), pp_.get("source", "")])
    for b_, ps_ in filiations_inter.items():
        for p_ in ps_:
            if b_ in inter_utiles and p_ in inter_utiles:
                _r, t_, pp_ = info_rel[(p_, b_)]
                filles.append([p_, b_, t_, pp_.get("citation", ""), pp_.get("source", "")])
    for r in lire("manuel/internationales_filles.csv"):
        a_, b_ = r.get("parente", "").strip(), r.get("fille", "").strip()
        if a_ in noeuds and b_ in noeuds and corpus.verifier(r.get("citation", ""), r.get("source", "").strip()):
            filles.append([a_, b_, r.get("relation", "").strip(), r["citation"], r["source"].strip()])
        elif a_ or b_:
            stats["filles_sans_citation"] = stats.get("filles_sans_citation", 0) + 1
    vus_f = set()
    n_auto = sum(1 for _ in lignes_inter for x in (_[5] + " | " + _[10]).split(" | ") if x)
    filles = filles[n_auto:] + filles[:n_auto]          # une ligne saisie à la main prime
    filles = [f for f in filles if not ((f[0], f[1]) in vus_f or vus_f.add((f[0], f[1])))]
    ecrire("internationales_filles.csv", ["parente", "fille", "relation", "citation", "source"], filles)
    # Addendum 5, B3 : la clé des Internationales, une ligne par relation typée et citée
    cle_l = []
    for (a_, b_), (rel_, typ_, pp_) in sorted(info_rel.items()):
        if a_ in inter_utiles and b_ in inter_utiles and rel_ in ("succession", "scission"):
            cle_l.append([b_, lab(b_), noeuds[b_]["fondation"] or "", noeuds[b_]["dissolution"] or "", rel_, typ_,
                          a_, lab(a_), pp_.get("citation", ""), pp_.get("source", "")])
    for r in lire("manuel/internationales_filles.csv"):
        a_, b_ = r.get("parente", "").strip(), r.get("fille", "").strip()
        rel_ = r.get("relation", "").strip()
        if a_ in inter_utiles and b_ in inter_utiles and rel_ in ("renommage", "fusion", "refondation") \
                and corpus.verifier(r.get("citation", ""), r.get("source", "").strip()):
            cle_l.append([b_, lab(b_), noeuds[b_]["fondation"] or "", noeuds[b_]["dissolution"] or "", "succession",
                          rel_, a_, lab(a_), r["citation"], r["source"].strip()])
    ecrire("cle_internationales.csv", ["id", "nom", "debut", "fin", "relation", "type", "autre_id", "autre_nom",
                                       "citation", "source"], cle_l)
    stats["cle_relations"] = len(cle_l)
    ecrire("affiliations.csv", ["party_id", "international_id", "start", "end", "date_certainty",
                                "source", "party_nom", "international_nom", "preuve", "citation",
                                "source_citation"], lignes_affil)
    ecrire("affiliations_sans_preuve.csv", ["party_id", "party_nom", "international_id",
                                            "international_nom", "sources"], affil_sans)
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
Famille héritée : une organisation issue d'une scission, d'un renommage ou d'une refondation, dont
le seul courant connu est générique (communiste, social-démocrate, écosocialiste) et vient de
Wikidata seul (pas d'article à lire), prend la famille précise de son parent (trotskyste, maoïste,
libertaire) et sa couleur, sans cascade. Ex. le NPA-R, issu du NPA. Liste et citation du lien :
familles_heritees.csv.
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
  chemin de lignée (filiations et scissions) A -> B -> ... -> C, sauf si A finit l'année où C
  naît (A s'est fondue elle-même dans C, ex. POSR -> SFIO en 1905).
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
