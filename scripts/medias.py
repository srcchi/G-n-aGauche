"""Étape 3c : médias des organisations (journaux, revues, chaînes de télévision, émissions, médias
en ligne, radios, podcasts, chaînes YouTube).

Trois sources, chaque lien avec sa preuve :
1. Wikidata : propriétés structurées entre l'organisation et un média (média de l'organisation
   P2813, propriétaire de P1830 ; et dans l'autre sens éditeur P123, propriétaire P127, organisation
   mère P749, partie de P361, affiliation P1416, alignement politique P1387, fondé par P112,
   sponsor P859). Preuve « wikidata » avec la propriété.
2. Infobox Wikipédia de l'organisation : champs journal / journaux / presse / organe, et couples
   option-N / valeur-N dont l'intitulé parle de journal, presse, organe, média, revue, télévision,
   radio, site. Preuve « explicite », citation mot pour mot.
3. Proximités (« proche de », « organe de »…) : pages qui pointent vers chaque organisation dessinée,
   réduites aux médias par leur type Wikidata ; dans l'article du média, la phrase qui cite
   l'organisation. Ce sont des candidats : data/manuel/medias.csv (decision = oui pour garder),
   jamais écrasé, seules les nouvelles lignes sont ajoutées.

Le type d'un média vient des libellés de ses types Wikidata (P31). Les maisons d'édition, librairies,
sections locales, etc. ne sont pas des médias et sont écartées.

Réseau : Wikidata (SPARQL) et Wikipédia (API), User-Agent du dépôt, Retry-After respecté, tout en cache
(data/sortie/cache_medias.json, plus le cache d'enrichissement.py) ; --refresh vide le cache des médias.
Produit : data/sortie/medias.csv (liens retenus), data/sortie/medias_ecartes.csv (non-médias),
data/manuel/medias.csv (proximités à décider).
"""
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrichissement as en  # noqa: E402
import preuves  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "data", "sortie")
MANUEL = os.path.join(RACINE, "data", "manuel")
CACHE = os.path.join(SORTIE, "cache_medias.json")
UA = {"User-Agent": "G-n-aGauche/0.3 (https://github.com/srcchi/G-n-aGauche) python-requests",
      "Accept": "application/sparql-results+json"}

PROP_VERS_MEDIA = {"P2813": "organe", "P1830": "propriété"}           # organisation -> média
PROP_VERS_ORG = {"P123": "éditeur", "P127": "propriété", "P749": "organisation mère", "P361": "partie de",
                 "P1416": "affiliation", "P1387": "alignement politique", "P112": "fondé par",
                 "P859": "sponsor"}                                       # média -> organisation
# Type de média, d'après les libellés des types Wikidata (ordre : le plus précis d'abord)
TYPES_MEDIA = [
    ("chaîne YouTube", r"chaîne YouTube"),
    ("podcast", r"podcast|baladodiffusion"),
    ("émission", r"émission|programme de télévision|série télévisée|magazine télévisé"),
    ("télévision", r"chaîne de télévision|télévision|web TV|webtélé|web télé|station de télévision"),
    ("radio", r"radio"),
    ("agence de presse", r"agence de presse"),
    ("média en ligne", r"site web|média en ligne|site d'information|webzine|pure player|média numérique|"
                       r"revue numérique|blog"),
    ("journal", r"journal|quotidien|hebdomadaire|mensuel|bimensuel|trimestriel|périodique|revue|magazine|"
                r"bulletin|presse|publication"),
]
RX_PAS_MEDIA = re.compile(r"maison d'édition|éditeur|librairie|section locale|cellule|comité|fédération|"
                          r"organisation|parti|syndicat|association|immeuble|bâtiment|personne|être humain", re.I)
RX_OPTION_MEDIA = re.compile(r"journa|presse|organe|média|revue|périodique|publication|télé|radio|site|chaîne|"
                             r"émission|podcast|magazine", re.I)
RX_CHAMP_MEDIA = re.compile(r"^\s*\|\s*(journal|journaux|presse|organe|organes|publication|publications|média|"
                            r"médias)\s*=(.*)$", re.I | re.M)
RX_PROCHE = re.compile(r"proche d|organe d|lié[e]? à|liée? au|liens? (?:très )?(?:étroits? |serrés? )?avec|"
                       r"émanation|soutien d|initiée? par|lancée? par|fondée? par|créée? par|propriété d|"
                       r"édité par|éditée par|publié par|publiée par|journal (?:officiel |central )?d|"
                       r"porte-parole d|au service d", re.I)


def lire_cache():
    if "--refresh" in sys.argv[1:] or not os.path.exists(CACHE):
        return {"wd": {}, "p31": {}, "libelles": {}}
    with open(CACHE, encoding="utf-8") as f:
        return json.load(f)


def sauver(cache):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def sparql(requete):
    import requests
    for essai in range(6):
        r = requests.post("https://query.wikidata.org/sparql", data={"query": requete, "format": "json"},
                          headers=UA, timeout=180)
        if r.status_code == 429 or r.status_code >= 500:
            attente = int(r.headers.get("Retry-After", 0) or 0) or 10 * (essai + 1)
            print(f"  Wikidata {r.status_code}, nouvel essai dans {attente} s")
            time.sleep(attente)
            continue
        r.raise_for_status()
        return r.json()["results"]["bindings"]
    raise SystemExit("Wikidata ne répond pas")


def q_de(uri):
    return uri.rsplit("/", 1)[-1]


def liens_wikidata(ids, cache):
    """Pour chaque organisation : [(média, propriété, sens)], en cache."""
    manquants = [q for q in ids if q not in cache["wd"] and re.fullmatch(r"Q\d+", q)]
    for k in range(0, len(manquants), 25):
        lot = manquants[k:k + 25]
        print(f"  liens Wikidata {k + len(lot)}/{len(manquants)}")
        vers_org = " ".join(f"wdt:{p}" for p in PROP_VERS_ORG)
        vers_media = " ".join(f"wdt:{p}" for p in PROP_VERS_MEDIA)
        req = f"""SELECT ?org ?m ?pd ?sens WHERE {{
          VALUES ?org {{ {" ".join("wd:" + q for q in lot)} }}
          {{ VALUES ?pd {{ {vers_org} }} ?m ?pd ?org . BIND("org" AS ?sens) }}
          UNION {{ VALUES ?pd {{ {vers_media} }} ?org ?pd ?m . BIND("media" AS ?sens) }}
          FILTER(isIRI(?m))
        }}"""
        for q in lot:
            cache["wd"][q] = []
        for b in sparql(req):
            cache["wd"][q_de(b["org"]["value"])].append([q_de(b["m"]["value"]), q_de(b["pd"]["value"]),
                                                         b["sens"]["value"]])
        sauver(cache)
    return {q: cache["wd"].get(q, []) for q in ids}


def types_de(items, cache):
    """Libellés français des types (P31) de chaque élément, en cache."""
    manquants = sorted({m for m in items if m not in cache["p31"] and re.fullmatch(r"Q\d+", m)})
    for k in range(0, len(manquants), 200):
        lot = manquants[k:k + 200]
        print(f"  types Wikidata {k + len(lot)}/{len(manquants)}")
        req = f"""SELECT ?m ?t ?tl ?ml WHERE {{
          VALUES ?m {{ {" ".join("wd:" + q for q in lot)} }}
          OPTIONAL {{ ?m wdt:P31 ?t . OPTIONAL {{ ?t rdfs:label ?tl . FILTER(LANG(?tl) = "fr") }} }}
          OPTIONAL {{ ?m rdfs:label ?ml . FILTER(LANG(?ml) = "fr") }}
        }}"""
        for m in lot:
            cache["p31"][m] = []
        for b in sparql(req):
            m = q_de(b["m"]["value"])
            if b.get("tl"):
                cache["p31"][m].append(b["tl"]["value"])
            if b.get("ml"):
                cache["libelles"][m] = b["ml"]["value"]
        sauver(cache)
    return {m: cache["p31"].get(m, []) for m in items}


def type_media(libelles):
    """(type de média, raison) ou (None, raison du rejet)."""
    texte = " | ".join(libelles)
    for nom, rx in TYPES_MEDIA:
        m = re.search(rx, texte, re.I)
        if m:
            return nom, m.group(0)
    return None, (texte or "aucun type Wikidata")


def periode(texte):
    m = re.search(r"\(\s*(?:depuis\s+)?(1[89]\d\d|20\d\d)\s*(?:[-–]\s*(1[89]\d\d|20\d\d)?)?\s*\)", texte)
    if not m:
        return "", ""
    fin = m.group(2) or ("toujours" if re.search(r"depuis|[-–]\s*\)", m.group(0)) else "")
    return m.group(1), fin


def medias_infobox(texte):
    """[(nom, titre lié ou None, début, fin, citation)] lus dans l'infobox."""
    valeurs = []
    for m in RX_CHAMP_MEDIA.finditer(texte):
        valeurs.append(m.group(2))
    for m in re.finditer(r"^\s*\|\s*option-(\d+)\s*=(.*)$", texte, re.M):
        if RX_OPTION_MEDIA.search(re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", m.group(2))):
            v = re.search(rf"^\s*\|\s*valeur-{m.group(1)}\s*=(.*)$", texte, re.M)
            if v:
                valeurs.append(v.group(1))
    res = []
    for v in valeurs:
        propre = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", v, flags=re.S)
        for morceau in re.split(r"<br\s*/?>|,(?![^\[]*\]\])", propre):
            morceau = morceau.strip()
            if not morceau or morceau.startswith(("{{refnec", "<!--")):
                continue
            lien = re.search(r"\[\[([^\[\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]", morceau)
            if lien:
                titre, nom = lien.group(1).strip(), (lien.group(2) or lien.group(1)).strip()
            else:
                it = re.search(r"''+([^']+?)''+", morceau)
                if not it:
                    continue
                titre, nom = None, re.sub(r"\{\{'\}\}", "'", it.group(1)).strip()
            if not nom or len(nom) > 80:
                continue
            d, f = periode(morceau)
            if morceau in texte:
                res.append((nom, titre, d, f, morceau))
    return res


def phrase_citant(texte, cibles):
    """Première phrase du texte qui lie l'une des cibles et parle de proximité, telle quelle."""
    for m in re.finditer(r"\[\[([^\[\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]", texte):
        if preuves.titre_norm(m.group(1)) not in cibles:
            continue
        phrase = preuves.phrase_autour(texte, m.start(), m.end())
        if RX_PROCHE.search(phrase) and phrase in texte:
            return phrase
    return None


def main():
    cache = lire_cache()
    corpus = preuves.Corpus()
    orgs = list(csv.DictReader(open(os.path.join(SORTIE, "organisations.csv"), encoding="utf-8")))
    lab = {r["id"]: r["label"] for r in orgs}
    dessinees = [r["id"] for r in orgs if r["garde"] == "oui"]
    titre_fr = {q: next((t for l_, t, _ in corpus.textes.get(q, []) if l_ == "fr"), None) for q in lab}

    lignes, ecartes, vus = [], [], {}

    def ajouter(q, mid, nom, typ, relation, d, f, preuve, citation, source):
        """Un média par organisation ; donné deux fois (Wikidata et infobox), on garde les deux preuves :
        la période et la citation de l'infobox, la propriété Wikidata dans la source."""
        cle = (q, mid or nom)
        if cle in vus:
            l_ = vus[cle]
            if d and not l_[6]:
                l_[6], l_[7] = d, f
            if preuve == "explicite" and l_[8] != "explicite":
                l_[8], l_[9], l_[5] = "explicite", citation, l_[5] or relation
            if source not in l_[10]:
                l_[10] += " + " + source
            return
        vus[cle] = [q, lab[q], mid or "", nom, typ, relation, d, f, preuve, citation, source]
        lignes.append(vus[cle])

    # 1. Wikidata
    wd = liens_wikidata(list(lab), cache)
    tous = {m for v in wd.values() for m, _, _ in v}
    # 2. Infobox : titres liés résolus en identifiants
    par_org = {}
    for q in lab:
        t = titre_fr[q]
        if t:
            txt = corpus.brut.get(f"fr:{t}", "")
            par_org[q] = medias_infobox(txt[:txt.find("\n}}") + 3] if "\n}}" in txt else txt)
    res = en.resoudre("fr", sorted({ti for v in par_org.values() for _, ti, *_ in v if ti}))
    tous |= {r[1] for r in res.values() if r[1]}
    types = types_de(tous, cache)
    for q, v in wd.items():
        for m, p, sens in v:
            typ, pourquoi = type_media(types.get(m, []))
            nom = cache["libelles"].get(m, m)
            relation = PROP_VERS_MEDIA.get(p) if sens == "media" else PROP_VERS_ORG.get(p)
            if not typ:
                ecartes.append([q, lab[q], m, nom, f"wikidata:{p}", pourquoi])
                continue
            ajouter(q, m, nom, typ, relation, "", "", "wikidata", f"{q} {p} {m}" if sens == "media" else f"{m} {p} {q}",
                    f"wikidata:{p}")
    for q, v in par_org.items():
        for nom, ti, d, f, cit in v:
            mid = res.get(ti, (None, None))[1] if ti else None
            typ, pourquoi = type_media(types.get(mid, [])) if mid else ("journal", "nommé dans le champ de l'infobox")
            if mid and not typ:
                # Lié à un article sans type de média : on garde le nom donné par l'infobox (champ « journaux »)
                typ = "journal"
            ajouter(q, mid, nom, typ, "organe", d, f, "explicite", cit, f"fr:{titre_fr[q]}")
    lignes.sort(key=lambda x: (x[1], x[3]))
    with open(os.path.join(SORTIE, "medias.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["org_id", "org_label", "media_id", "media_nom", "type_media", "relation", "debut", "fin",
                    "preuve", "citation", "source"])
        w.writerows(lignes)
    with open(os.path.join(SORTIE, "medias_ecartes.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["org_id", "org_label", "element_id", "element_nom", "source", "raison (types Wikidata)"])
        w.writerows(sorted(ecartes, key=lambda x: (x[1], x[3])))
    print(f"{len(lignes)} liens organisation-média (data/sortie/medias.csv), {len(ecartes)} non-médias écartés")

    # 3. Proximités : pages liées aux organisations dessinées, réduites aux médias
    if "--sans-proches" in sys.argv[1:]:
        return
    candidats = {}
    for i, q in enumerate(dessinees):
        t = titre_fr[q]
        if not t:
            continue
        print(f"  pages liées {i + 1}/{len(dessinees)} : {t}")
        for p in en.pages_liees(t):
            candidats.setdefault(p, set()).add(q)
        en.sauver_cache()
    res_c = en.resoudre("fr", sorted(candidats))
    en.sauver_cache()
    types_c = types_de({r[1] for r in res_c.values() if r[1]}, cache)
    medias_c = {p: (res_c[p], type_media(types_c.get(res_c[p][1], []))[0]) for p in candidats
                if res_c.get(p, (None, None))[1] and type_media(types_c.get(res_c[p][1], []))[0]}
    print(f"  {len(medias_c)} médias parmi {len(candidats)} pages liées")
    textes = en.wikitextes("fr", sorted({r[0] for r, _ in medias_c.values()}))
    en.sauver_cache()
    deja = {(l[0], l[2]) for l in lignes}
    proches = []
    for p, ((titre, mid), typ) in sorted(medias_c.items()):
        texte = textes.get(titre) or ""
        for q in sorted(candidats[p]):
            if (q, mid) in deja:
                continue
            cibles = {preuves.titre_norm(titre_fr[q])} | {preuves.titre_norm(r) for r in en.redirections(titre_fr[q])}
            ph = phrase_citant(texte, cibles)
            if ph:
                proches.append([q, lab[q], mid, cache["libelles"].get(mid, titre), typ, "proche", ph, f"fr:{titre}", ""])
    en.sauver_cache()
    chemin = os.path.join(MANUEL, "medias.csv")
    entetes = ["org_id", "org_label", "media_id", "media_nom", "type_media", "relation", "citation", "source",
               "decision"]
    existants = set()
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as fh:
            existants = {(r["org_id"], r["media_id"]) for r in csv.DictReader(fh)}
    nouveaux = [p for p in proches if (p[0], p[2]) not in existants]
    neuf = not os.path.exists(chemin)
    with open(chemin, "a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if neuf:
            w.writerow(entetes)
        w.writerows(nouveaux)
    print(f"{len(proches)} proximités trouvées, {len(nouveaux)} nouvelles ajoutées à data/manuel/medias.csv "
          f"(decision = oui pour les garder)")


if __name__ == "__main__":
    main()
