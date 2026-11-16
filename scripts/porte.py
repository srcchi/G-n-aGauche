"""
Porte « organisation politique » (addendum 4, 1), partagée par arbre.py, tableaux.py et nettoyage.py.

Une entité Wikidata est rejetée si l'une de ses classes (P31, sous-classes comprises) est :
- dans EXCLUES (personne, territoire, État, organisation intergouvernementale, syndicat, base de
  données...), même si Wikidata la classe aussi « organisation politique » (le G7 et le comté de
  Nice le sont) ;
- ou dans SANS_POLITIQUE (organisation à but non lucratif, organisation internationale) sans
  aucune classe de POLITIQUE.
Une entité sans type, ou seulement « organisation », est gardée : beaucoup de petits groupes
militants sont dans ce cas. Les identifiants cités dans data/manuel/ sont exemptés par les
appelants (la CNT, syndicat, est une origine dessinée).

Types directs lus dans data/cache_wikidata_orgs.json ; sur-classes des types distincts
demandées à Wikidata par lots de 50, mises en cache dans data/cache_porte.json.
"""

import json
import os
import re
import time

import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(RACINE, "data", "cache_porte.json")
ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "arbre-gauche-fr/0.1 (https://github.com/srcchi/G-n-aGauche) python-requests",
           "Accept": "application/sparql-results+json"}

EXCLUES = {
    "Q5": "personne",
    "Q56061": "entité territoriale administrative",
    "Q82794": "zone géographique",
    "Q1620908": "région historique",
    "Q6256": "pays",
    "Q3024240": "État historique",
    "Q245065": "organisation intergouvernementale",
    "Q178790": "syndicat",
    "Q8513": "base de données",
    "Q16519632": "organisation scientifique",
    "Q1047437": "association professionnelle",
}
POLITIQUE = {
    "Q7278": "parti politique",
    "Q7210356": "organisation politique",
    "Q2716508": "internationale",
    "Q24649": "parti politique européen",
    "Q6138528": "coalition politique",
    "Q2738074": "mouvement politique",
    "Q1393724": "tendance politique",
    "Q2493450": "organisation politique de jeunesse",
}
SANS_POLITIQUE = {
    "Q163740": "organisation à but non lucratif",
    "Q484652": "organisation internationale",
}
CLASSES = {**EXCLUES, **POLITIQUE, **SANS_POLITIQUE}

CACHE_TYPES_DIRECTS = os.path.join(RACINE, "data", "cache_wikidata_orgs.json")   # types P31 (fusion.py)
# Sur-classes des seuls types distincts (quelques centaines), bien moins coûteux que P279* sur
# chaque entité (Wikidata répond 429 puis expire sur 1 800 entités).
REQUETE_TYPES = """
SELECT ?t ?cls WHERE {
  VALUES ?t { %s }
  VALUES ?cls { %s }
  ?t wdt:P279* ?cls .
}
"""
REQUETE_P31 = """
SELECT ?x ?t WHERE { VALUES ?x { %s } ?x wdt:P31 ?t . }
"""


def _lire(chemin):
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _sparql(requete):
    for essai in range(6):
        try:
            r = requests.post(ENDPOINT, data={"query": requete, "format": "json"}, headers=HEADERS, timeout=90)
        except requests.exceptions.Timeout:
            print(f"  délai dépassé, pause de {20 * (essai + 1)}s...")
            time.sleep(20 * (essai + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            try:
                attente = int(r.headers.get("Retry-After", 15 * (essai + 1)))
            except ValueError:
                attente = 15 * (essai + 1)
            print(f"  {r.status_code}, pause de {min(attente, 180)}s (Retry-After)...")
            time.sleep(min(attente, 180))
            continue
        r.raise_for_status()
        time.sleep(2)
        return r.json()["results"]["bindings"]
    raise RuntimeError("Wikidata : trop d'erreurs consécutives, réessayer plus tard.")


def classes(qids, refresh=False):
    """Q id -> classes de CLASSES auxquelles il appartient (types directs, puis leurs sur-classes)."""
    cache = {} if refresh else _lire(CACHE)
    cache.setdefault("types", {})        # type direct -> classes de CLASSES
    cache.setdefault("p31", {})          # entité absente du cache Wikidata -> types directs
    directs_wd = _lire(CACHE_TYPES_DIRECTS)
    qids = [q for q in qids if re.fullmatch(r"Q\d+", q or "")]

    def types_de(q):
        if q in directs_wd and directs_wd[q].get("types") is not None:
            return directs_wd[q]["types"]
        return cache["p31"].get(q)
    sans = sorted(q for q in qids if types_de(q) is None)
    for i in range(0, len(sans), 200):
        lot = sans[i:i + 200]
        print(f"  porte politique : types de {i + len(lot)}/{len(sans)} entités")
        for q in lot:
            cache["p31"][q] = []
        for row in _sparql(REQUETE_P31 % " ".join(f"wd:{q}" for q in lot)):
            cache["p31"][row["x"]["value"].rsplit("/", 1)[-1]].append(row["t"]["value"].rsplit("/", 1)[-1])
    tous = sorted({t for q in qids for t in (types_de(q) or [])} - set(cache["types"]))
    for i in range(0, len(tous), 50):
        lot = tous[i:i + 50]
        print(f"  porte politique : sur-classes de {i + len(lot)}/{len(tous)} types")
        for t in lot:
            cache["types"][t] = []
        for row in _sparql(REQUETE_TYPES % (" ".join(f"wd:{t}" for t in lot), " ".join(f"wd:{c}" for c in CLASSES))):
            t, c = row["t"]["value"].rsplit("/", 1)[-1], row["cls"]["value"].rsplit("/", 1)[-1]
            if c not in cache["types"][t]:
                cache["types"][t].append(c)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return {q: sorted({c for t in (types_de(q) or []) for c in cache["types"].get(t, [])}) for q in qids}


def verdict(cls):
    """(gardée, raison) pour une liste de classes."""
    exclues = [EXCLUES[c] for c in cls if c in EXCLUES]
    if exclues:
        return False, "porte politique : " + ", ".join(sorted(set(exclues)))
    if any(c in SANS_POLITIQUE for c in cls) and not any(c in POLITIQUE for c in cls):
        return False, ("porte politique : " + ", ".join(sorted({SANS_POLITIQUE[c] for c in cls if c in SANS_POLITIQUE}))
                       + ", sans type politique")
    return True, ""


def rejets(qids, exemptes=(), refresh=False):
    """Q id -> raison du rejet, pour les seules entités rejetées (les exemptées ne le sont jamais)."""
    exemptes = set(exemptes)
    res = {}
    for q, cls in classes([q for q in qids if q not in exemptes], refresh).items():
        garde, pourquoi = verdict(cls)
        if not garde:
            res[q] = pourquoi
    return res


def ids_manuels():
    """Identifiants cités dans data/manuel/*.csv : jamais rejetés par la porte."""
    dossier = os.path.join(RACINE, "data", "manuel")
    ids = set()
    for nom in os.listdir(dossier):
        if nom.endswith(".csv") and nom not in ("types.csv", "sigles.csv", "actifs.csv"):
            with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                ids |= set(re.findall(r"\bQ\d+\b", f.read()))
    return ids
