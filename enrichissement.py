"""
Phase 0 : enrichissement des données (aucun dessin, aucun élagage).

0.1  data/manuel/actifs.csv : organisations marquées actives, avec les indices qui le confirment
     ou non, à valider à la main (colonne valide).
0.2  data/sortie/liens_candidats.csv : liens proposés, trouvés dans le texte des articles
     Wikipédia (phrases avec un mot déclencheur), dans les pages liées, dans les articles en
     d'autres langues, ou par une Internationale commune. Aucun n'est accepté automatiquement.
0.3  data/manuel/aretes_manuelles.csv : liens ajoutés à la main (source obligatoire).
0.4  data/sortie/liste_recherche.csv : organisations encore isolées, avec des adresses de
     recherche prêtes à ouvrir (rien n'est téléchargé sur ces sites).

Entrées (lecture seule) : data/sortie/*.csv (nettoyage.py), data/cache_wikitext.json,
data/cache_resolution.json. Les nouveaux téléchargements (Wikidata, Wikipédia) sont mis en cache
dans data/sortie/cache_enrichissement.json et ne sont jamais refaits.
Un fichier de data/manuel/ déjà présent n'est jamais écrasé.

Usage : python enrichissement.py
"""

import csv
import json
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from urllib.parse import quote

import requests

DATA = "data"
SORTIE = os.path.join(DATA, "sortie")
MANUEL = os.path.join(DATA, "manuel")
CACHE = os.path.join(SORTIE, "cache_enrichissement.json")
# Règle des API Wikimedia : un User-Agent descriptif avec un moyen de contact (ici, l'adresse du dépôt)
HEADERS = {"User-Agent": "G-n-aGauche/0.3 (https://github.com/srcchi/G-n-aGauche) python-requests"}
LANGUES = ["en", "es", "ca", "it", "de", "pt"]   # quand il n'y a pas d'article en français

# ---------- Mots déclencheurs ----------
# (motif, type proposé, la cible est-elle l'ancêtre quand elle suit le mot ?, mot de la liste demandée ?)
DECLENCHEURS = [
    (r"scission|scind[ée]e?s?", "scission", True, True),
    (r"exclue?s?", "scission", True, True),
    (r"issue?s? d", "filiation", True, True),
    (r"fond[ée]e?s? par des militants", "filiation", True, True),
    (r"fusionn[ée]e?s?|fusion", "fusion", None, True),
    (r"rebaptis[ée]e?s?|ancien nom|devenue?s?", "filiation", False, True),
    (r"courant|tendance|fraction", "scission", True, True),
    (r"jeunesse d|collectif d|émanation", "emanation", True, True),
    # Hors liste demandée : utiles pour les satellites (« impulsée par Révolution permanente »)
    (r"impuls[ée]e?s? par|lanc[ée]e?s? par|à l'initiative d|cré[ée]e?s? par|"
     r"organisation de jeunesse|branche jeunesse", "emanation", True, False),
    (r"rejoignent|ont rejoint|entrisme|entriste", "passage_militants", None, False),
]
RX_DECL = [(re.compile(rf"\b(?:{m})", re.I), t, anc, liste) for m, t, anc, liste in DECLENCHEURS]
# Déclencheurs dans les autres langues (signal autre_langue)
DECL_AUTRES = {
    "scission": r"split|splinter|broke away|expelled|escisi[oó]n|escindi|expulsad|scission|"
                r"scissione|espuls|Abspaltung|abgespalten|ausgeschlossen|cisão|expuls",
    "fusion": r"merg|fusi[oó]n|fusion|fusione|Fusion|fusão|zusammenschluss",
    "filiation": r"successor|predecessor|renamed|formerly|founded by (?:former )?members|sucesor|"
                 r"predecesor|renombrad|fundad[oa] por|successore|predecessore|rinominat|"
                 r"Nachfolge|Vorgänger|umbenannt|gegründet von|sucessor|antecessor|renomead",
    "emanation": r"youth wing|youth organi[sz]ation|front organi[sz]ation|juventud|juventude|"
                 r"giovanile|Jugendorganisation|Jugendverband",
}
RX_DECL_AUTRES = {t: re.compile(rf"\b(?:{m})", re.I) for t, m in DECL_AUTRES.items()}
# Faux positifs fréquents : une personne, pas une organisation (« ancien militant du NPA »)
RX_PERSONNE = re.compile(r"\b(ancien(ne)?s?|ex-)\s*(militant|membre|dirigeant|cadre|responsable|"
                         r"député|secrétaire|porte-parole|candidat)|\bmilitante?s? (de|du|des|à)\b", re.I)
RX_SECTION = re.compile(r"histoir|origin|fondation|création|scission|historique|naissance|genèse|"
                        r"évolution|fusion|chronolog|parcours|formation", re.I)
RX_ORGA = re.compile(r"^(Parti|Ligue|Union|Mouvement|Organisation|Groupe|Fédération|Comité|Gauche|"
                     r"Front|Alliance|Collectif|Cercle|Jeunesse|Révolution|Courant|Tendance|Fraction|"
                     r"Rassemblement|Convention|Coordination|Association|Lutte|Pouvoir|Socialisme|"
                     r"Communistes?|Initiative|Alternative|Les |La |Le )", re.I)


# ======================================================================
# Outils : lecture, cache, API
# ======================================================================

def lire(nom, dossier=SORTIE):
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lire_json(chemin):
    if not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


cache = lire_json(CACHE)
for cle in ("entites", "wikitext", "resolution", "backlinks", "redirections"):
    cache.setdefault(cle, {})


def sauver_cache():
    """Écriture sûre : fichier temporaire puis remplacement, avec quelques essais si Windows
    (antivirus, indexation) tient le fichier un instant."""
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    for essai in range(10):
        try:
            os.replace(tmp, CACHE)
            return
        except OSError:
            time.sleep(0.5 * (essai + 1))
    raise RuntimeError(f"Impossible d'écrire {CACHE} (fichier bloqué par un autre programme ?)")


def api(url, **params):
    params.update(format="json", formatversion=2)
    for essai in range(6):
        r = requests.get(url, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            try:
                attente = int(r.headers.get("Retry-After", 5 * (essai + 1)))
            except ValueError:
                attente = 5 * (essai + 1)
            print(f"  {r.status_code}, pause de {min(attente, 120)}s (Retry-After)...")
            time.sleep(min(attente, 120))
            continue
        r.raise_for_status()
        time.sleep(0.4)
        return r.json()
    raise RuntimeError(f"{url} : trop d'erreurs consécutives, réessayer plus tard.")


def wp(lang):
    return f"https://{lang}.wikipedia.org/w/api.php"


def normaliser(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def titre_norm(t):
    t = t.replace("_", " ").strip()
    return t[:1].upper() + t[1:]


# ---------- Wikidata : liens vers les articles, site officiel, dirigeant, fin ----------

def entites(qids):
    manquants = [q for q in qids if q not in cache["entites"] and re.fullmatch(r"Q\d+", q)]
    for i in range(0, len(manquants), 50):
        lot = manquants[i:i + 50]
        print(f"  Wikidata {i + len(lot)}/{len(manquants)}")
        d = api("https://www.wikidata.org/w/api.php", action="wbgetentities", ids="|".join(lot),
                props="sitelinks|claims")
        for q, e in d.get("entities", {}).items():
            claims = e.get("claims", {})

            def valeurs(p):
                res = []
                for c in claims.get(p, []):
                    v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                    if isinstance(v, dict):
                        v = v.get("id") or v.get("time")
                    if v:
                        res.append(v)
                return res
            cache["entites"][q] = dict(
                liens={k[:-4]: v["title"] for k, v in e.get("sitelinks", {}).items()
                       if k.endswith("wiki") and k[:-4] in ["fr"] + LANGUES},
                site=valeurs("P856"), dirigeant=valeurs("P488") + valeurs("P6") + valeurs("P3975"),
                fin=valeurs("P576"), membres=valeurs("P2124"))
        sauver_cache()
    return {q: cache["entites"].get(q, {}) for q in qids}


# ---------- Wikipédia : texte, résolution des titres, pages liées ----------

ancien_wikitext = lire_json(os.path.join(DATA, "cache_wikitext.json"))
ancienne_resolution = lire_json(os.path.join(DATA, "cache_resolution.json"))


def wikitextes(lang, titres):
    """Texte des articles (cache d'abord : l'ancien cache fr, puis le nôtre)."""
    res, manquants = {}, []
    for t in titres:
        cle = f"{lang}:{t}"
        if lang == "fr" and t in ancien_wikitext and ancien_wikitext[t].get("text"):
            res[t] = ancien_wikitext[t]["text"]
        elif cle in cache["wikitext"]:
            res[t] = cache["wikitext"][cle]
        else:
            manquants.append(t)
    for i in range(0, len(manquants), 20):
        lot = manquants[i:i + 20]
        print(f"  texte {lang} {i + len(lot)}/{len(manquants)}")
        d = api(wp(lang), action="query", prop="revisions", rvprop="content", rvslots="main",
                titles="|".join(lot), redirects=1)
        q = d.get("query", {})
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        pages = {p["title"]: p for p in q.get("pages", [])}
        for t in lot:
            t2 = norm.get(t, t)
            p = pages.get(redir.get(t2, t2), {})
            texte = p["revisions"][0]["slots"]["main"]["content"] if p.get("revisions") else ""
            cache["wikitext"][f"{lang}:{t}"] = texte
            res[t] = texte
        sauver_cache()
    return res


def resoudre(lang, titres):
    """Titre -> (titre de l'article après redirection, Q id)."""
    res, manquants = {}, []
    for t in set(titres):
        cle = f"{lang}:{t}"
        if lang == "fr" and t in ancienne_resolution:
            res[t] = tuple(ancienne_resolution[t])
        elif cle in cache["resolution"]:
            res[t] = tuple(cache["resolution"][cle])
        else:
            manquants.append(t)
    for i in range(0, len(manquants), 50):
        lot = manquants[i:i + 50]
        print(f"  résolution {lang} {i + len(lot)}/{len(manquants)}")
        d = api(wp(lang), action="query", titles="|".join(lot), redirects=1, prop="pageprops",
                ppprop="wikibase_item")
        q = d.get("query", {})
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        pages = {p["title"]: p for p in q.get("pages", [])}
        for t in lot:
            t2 = norm.get(t, t)
            t3 = redir.get(t2, t2)
            qid = pages.get(t3, {}).get("pageprops", {}).get("wikibase_item")
            cache["resolution"][f"{lang}:{t}"] = [t3, qid]
            res[t] = (t3, qid)
        sauver_cache()
    return res


def pages_liees(titre):
    """Articles (espace principal) qui pointent vers ce titre, redirections comprises."""
    cle = f"fr:{titre}"
    if cle not in cache["backlinks"]:
        titres, suite = [], {}
        while True:
            d = api(wp("fr"), action="query", list="backlinks", bltitle=titre, blnamespace=0,
                    bllimit=500, blredirect=1, **suite)
            for b in d.get("query", {}).get("backlinks", []):
                titres.append(b["title"])
                titres += [r["title"] for r in b.get("redirlinks", [])]
            if "continue" not in d:
                break
            suite = d["continue"]
        cache["backlinks"][cle] = sorted(set(titres))
    return cache["backlinks"][cle]


def redirections(titre):
    """Titres qui redirigent vers cet article (pour reconnaître les liens vers lui)."""
    cle = f"fr:{titre}"
    if cle not in cache["redirections"]:
        d = api(wp("fr"), action="query", titles=titre, prop="redirects", rdlimit=500)
        pages = d.get("query", {}).get("pages", [])
        cache["redirections"][cle] = [r["title"] for p in pages for r in p.get("redirects", [])]
    return cache["redirections"][cle]


# ======================================================================
# Texte : nettoyage, sections utiles, phrases, liens
# ======================================================================

RX_LIEN = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|([^\[\]]*))?\]\]")
RX_TITRE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.M)


def nettoyer(t):
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<ref[^>/]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    for _ in range(8):     # modèles imbriqués, du plus intérieur au plus extérieur
        t2 = re.sub(r"\{\{[^{}]*\}\}", "", t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"\{\|.*?\|\}", "", t, flags=re.S)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    return t


def sections_utiles(texte, tout=False):
    """Introduction + sections Histoire, Origines, Fondation, Scission... (ou tout l'article)."""
    texte = nettoyer(texte)
    morceaux, pos, titre, parent = [], 0, "", ""
    for m in RX_TITRE.finditer(texte):
        morceaux.append((titre, parent, texte[pos:m.start()]))
        niveau, titre = len(m.group(1)), m.group(2)
        if niveau == 2:
            parent = titre
        pos = m.end()
    morceaux.append((titre, parent, texte[pos:]))
    fin = re.compile(r"notes|référence|voir aussi|liens externes|bibliographie|annexe", re.I)
    garde = []
    for titre, parent, corps in morceaux:
        if fin.search(parent or "") or fin.search(titre or ""):
            continue
        if tout or not titre or RX_SECTION.search(titre) or RX_SECTION.search(parent):
            garde.append(corps)
    return "\n".join(garde)


def phrases(texte):
    for para in texte.split("\n"):
        para = para.strip(" *#:;")
        if len(para) < 20 or para.startswith(("[[Fichier", "[[File", "[[Catégorie", "[[Image")):
            continue
        for p in re.split(r"(?<=[.!?])\s+(?=[A-ZÉÈÀÂÎ«\[])", para):
            if len(p) > 15:
                yield p


def liens_de(phrase):
    for m in RX_LIEN.finditer(phrase):
        cible = titre_norm(m.group(1))
        if re.match(r"(Fichier|File|Image|Catégorie|Category|Portail|Wikipédia|Aide|Modèle):", cible, re.I):
            continue
        yield cible, m.start()


def texte_brut(phrase):
    return re.sub(r"\s+", " ", RX_LIEN.sub(lambda m: m.group(2) or m.group(1), phrase)).strip()


# ======================================================================
# Programme
# ======================================================================

def main():
    orgs = {r["id"]: r for r in lire("organisations.csv")}
    sd = {r["id"]: dict(r, fondation="", actif="", famille=r["famille"]) for r in lire("sans_date.csv")}
    graphe = {**orgs, **sd}
    exclus = {r["id"]: r for r in lire("perimetre_exclu.csv")}
    internationales = {r["id"]: r for r in lire("internationales.csv")}
    connus = {**{q: dict(label=r["label"]) for q, r in exclus.items()}, **graphe}

    # ---------- Organisations sans lien, arbres sans organisation active ----------
    voisins = defaultdict(set)
    for fichier, col_a, col_b in (("liens.csv", "source", "cible"),
                                  ("liens_date_manquante.csv", "source", "cible"),
                                  ("anomalies.csv", "source", "target")):
        for r in lire(fichier):
            a, b = r[col_a], r[col_b]
            if a in graphe and b in graphe:
                voisins[a].add(b)
                voisins[b].add(a)
    sans_lien = {q for q in graphe if not voisins[q]}
    arbres_sans_actif, vus = [], set()
    for q in graphe:
        if q in vus or not voisins[q]:
            continue
        comp, pile = set(), [q]
        while pile:
            x = pile.pop()
            if x not in comp:
                comp.add(x)
                pile += voisins[x]
        vus |= comp
        if not any(graphe[x].get("actif") for x in comp):
            arbres_sans_actif.append(comp)
    a_fouiller = sans_lien | set().union(*arbres_sans_actif) if arbres_sans_actif else set(sans_lien)
    actifs = [q for q in orgs if orgs[q].get("actif_auto", orgs[q]["actif"])]   # drapeau automatique
    print(f"{len(graphe)} organisations : {len(graphe) - len(sans_lien)} avec lien, {len(sans_lien)} sans ; "
          f"{len(arbres_sans_actif)} arbres sans organisation active ; {len(a_fouiller)} à fouiller.")

    # ---------- Titres des articles ----------
    print("Wikidata : articles, site officiel, dirigeants...")
    ent = entites(sorted(graphe))
    titre_fr_de = {}
    for t, v in ancien_wikitext.items():
        if v.get("qid") in graphe:
            titre_fr_de.setdefault(v["qid"], t)
    for q in graphe:
        if q.startswith("fr:"):
            titre_fr_de[q] = q[3:]
        elif ent.get(q, {}).get("liens", {}).get("fr"):
            titre_fr_de.setdefault(q, ent[q]["liens"]["fr"])
    qid_de_titre = {t: q for q, t in titre_fr_de.items()}

    # ================= 0.1 Organisations actives =================
    print("Textes français des organisations actives et à fouiller...")
    textes_fr = wikitextes("fr", sorted({titre_fr_de[q] for q in set(a_fouiller) | set(actifs)
                                         if q in titre_fr_de}))
    lignes_actifs = []
    for q in sorted(actifs, key=lambda q: (orgs[q]["famille"], orgs[q]["label"])):
        o, e = orgs[q], ent.get(q, {})
        pourquoi = ["aucune date de fin (Wikidata, Wikipédia)", "aucun successeur connu",
                    "pas de catégorie « Ancien… »"]
        if "correction" in o["sources"]:
            pourquoi = ["marquée « vivant » dans corrections_noeuds.csv"]
        indices = []
        if e.get("site"):
            indices.append(f"site officiel (Wikidata) : {e['site'][0]}")
        if e.get("dirigeant"):
            indices.append(f"dirigeant renseigné (Wikidata, {len(e['dirigeant'])})")
        if e.get("membres"):
            indices.append("nombre de membres renseigné (Wikidata)")
        texte = textes_fr.get(titre_fr_de.get(q, ""), "")
        info = re.search(r"\{\{\s*Infobox[^\n]*", texte, re.I)
        if info:
            for champ, nom in ((r"site\s*web|site", "site web"),
                               (r"secr[ée]taire|pr[ée]sident|porte-parole|dirigeant|leader|"
                                r"coordinat|responsable", "dirigeant"),
                               (r"adh[ée]rents|membres", "adhérents"),
                               (r"journal|publication|presse", "journal")):
                m = re.search(rf"^\s*\|\s*(?:{champ})[^=\n]*=\s*([^\n]+)", texte, re.I | re.M)
                if m and len(nettoyer(m.group(1)).strip(" |")) > 1:
                    indices.append(f"infobox : {nom} renseigné")
            annees = [int(a) for a in re.findall(r"\b(20[12]\d)\b", texte)]
            if annees:
                indices.append(f"année la plus récente citée dans l'article : {max(annees)}")
        if not titre_fr_de.get(q):
            indices.append("pas d'article en français")
        if not indices:
            indices.append("AUCUN indice d'activité récente")
        fond = int(o["fondation"])
        if fond < 1945 and not e.get("site"):
            indices.append(f"fondée en {fond}, sans site officiel : activité à vérifier")
        lignes_actifs.append([q, o["label"], o["fondation"], " ; ".join(pourquoi), " ; ".join(indices), ""])
    ecrire_manuel("actifs.csv", ["id", "name", "founding", "why_flagged", "evidence", "valide"], lignes_actifs)

    # ================= 0.2 Liens candidats =================
    candidats = {}

    def ajouter(org, cible, phrase, mot, signal, type_p, conf, sens, note=""):
        cle = (org, cible, signal, type_p)
        if cle in candidats and candidats[cle][6] >= conf:
            return
        candidats[cle] = [org, cible, phrase[:400], mot, signal, type_p, round(max(0.05, min(0.95, conf)), 2),
                          "", graphe[org]["label"], connus.get(cible, {}).get("label", cible),
                          sens, note]

    def annee(q):
        f = graphe.get(q, {}).get("fondation") or (orgs.get(q, {}) or {}).get("fondation")
        return int(f) if f else None

    def sens_et_bonus(org, cible, anc_si_apres, avant):
        """Sens du lien : par les dates si elles sont connues, sinon par la grammaire."""
        ao, ac = annee(org), annee(cible)
        if ao and ac and ao != ac:
            sens = "cible → org" if ac < ao else "org → cible"
            coherent = anc_si_apres is None or (anc_si_apres == avant) == (ac < ao)
            return sens, (0.15 if coherent else -0.1)
        if anc_si_apres is not None and avant:
            return ("cible → org" if anc_si_apres else "org → cible"), 0
        return "à vérifier", -0.05

    def miner_phrase(org, phrase, liens_resolus, signal, base):
        """Liens vers des organisations dans une phrase contenant un mot déclencheur."""
        trouves = [(m.start(), m.group(0), t, anc, liste) for rx, t, anc, liste in RX_DECL
                   for m in rx.finditer(phrase)]
        if not trouves:
            return
        for cible_titre, pos in liens_de(phrase):
            resolu = liens_resolus.get(cible_titre)
            if not resolu:
                continue
            titre_res, qid = resolu
            cible = qid if qid in connus else (f"fr:{titre_res}" if f"fr:{titre_res}" in connus else None)
            if cible == org:
                continue
            note = ""
            if cible is None:
                if not RX_ORGA.search(titre_res):
                    continue
                cible, note = (qid or f"fr:{titre_res}"), "cible absente des données (organisation ?)"
            # Mot déclencheur le plus proche avant le lien, sinon le plus proche après
            avant = [x for x in trouves if x[0] < pos]
            pos_m, mot, type_p, anc, liste = (max(avant, key=lambda x: x[0]) if avant
                                              else min(trouves, key=lambda x: x[0]))
            conf = base + (0.2 if avant and pos - pos_m < 60 else 0) - (0 if liste else 0.1)
            if RX_PERSONNE.search(phrase[max(0, pos - 80):pos]):
                conf -= 0.3
                note = (note + " ; " if note else "") + "contexte « ancien militant » : faux positif probable"
            sens, bonus = sens_et_bonus(org, cible, anc, bool(avant))
            if type_p == "emanation":
                sens = "cible → org"
            if graphe.get(cible, {}).get("famille") == graphe[org]["famille"]:
                conf += 0.1
            ajouter(org, cible, texte_brut(phrase), mot.lower(), signal, type_p, conf + bonus, sens, note)

    # --- Signal « texte » : l'article de l'organisation ---
    # Tous les articles du graphe, pas seulement les isolés : une organisation déjà reliée peut
    # avoir des ancêtres manquants (Voix prolétarienne : Ligne rouge, OCML...).
    print("Fouille des articles...")
    a_lire = set(graphe)
    textes_fr.update(wikitextes("fr", sorted({titre_fr_de[q] for q in a_lire if q in titre_fr_de})))
    a_resoudre = defaultdict(set)
    phr_par_org = defaultdict(list)
    for q in sorted(a_lire):
        t = titre_fr_de.get(q)
        if not t or not textes_fr.get(t):
            continue
        for p in phrases(sections_utiles(textes_fr[t])):
            if any(rx.search(p) for rx, *_ in RX_DECL):
                phr_par_org[q].append(p)
                a_resoudre["fr"] |= {c for c, _ in liens_de(p)}
    resolus_fr = resoudre("fr", sorted(a_resoudre["fr"]))
    for q, ps in phr_par_org.items():
        for p in ps:
            miner_phrase(q, p, resolus_fr, "texte", 0.4)

    # --- Signal « pages_liees » : articles d'organisations du graphe qui citent l'organisation ---
    print("Pages liées...")
    titres_graphe = {t for q, t in titre_fr_de.items()}
    textes_liees_titres = set()
    liees_par_org = {}
    for i, q in enumerate(sorted(a_fouiller)):
        t = titre_fr_de.get(q)
        if not t:
            continue
        if i % 25 == 0:
            print(f"  {i}/{len(a_fouiller)}")
        liees = [b for b in pages_liees(t) if b in titres_graphe and b != t]
        liees_par_org[q] = liees
        textes_liees_titres |= set(liees)
        if i % 25 == 0:
            sauver_cache()
    sauver_cache()
    textes_liees = wikitextes("fr", sorted(textes_liees_titres))
    for q, liees in liees_par_org.items():
        t = titre_fr_de[q]
        noms = {titre_norm(t)} | {titre_norm(r) for r in redirections(t)}
        for b in liees:
            qb = qid_de_titre.get(b)
            if not qb or qb not in graphe:
                continue
            meilleure = None
            for p in phrases(sections_utiles(textes_liees.get(b, ""), tout=True)):
                if not any(c in noms for c, _ in liens_de(p)):
                    continue
                if any(rx.search(p) for rx, *_ in RX_DECL):
                    meilleure = p
                    break
                meilleure = meilleure or p
            if not meilleure:
                continue
            mots = [m.group(0) for rx, *_ in RX_DECL for m in rx.finditer(meilleure)]
            types = [t_ for rx, t_, *_ in RX_DECL if rx.search(meilleure)]
            anc = next((a for rx, _, a, _ in RX_DECL if rx.search(meilleure)), None)
            sens, bonus = sens_et_bonus(q, qb, None, False)
            conf = (0.35 if mots else 0.1) + bonus + (0.1 if graphe[qb]["famille"] == graphe[q]["famille"] else 0)
            if RX_PERSONNE.search(meilleure):
                conf -= 0.2
            ajouter(q, qb, texte_brut(meilleure), (mots[0].lower() if mots else "(mention sans déclencheur)"),
                    "pages_liees", types[0] if types else "filiation", conf, sens,
                    f"phrase de l'article « {b} »")
    sauver_cache()

    # --- Signal « autre_langue » : pas d'article en français ---
    print("Articles en d'autres langues...")
    par_langue = defaultdict(dict)
    for q in sorted(a_fouiller):
        if titre_fr_de.get(q):
            continue
        liens = ent.get(q, {}).get("liens", {})
        lang = next((l for l in LANGUES if l in liens), None)
        if lang:
            par_langue[lang][q] = liens[lang]
    for lang, quoi in par_langue.items():
        txt = wikitextes(lang, sorted(quoi.values()))
        a_res = set()
        phr = defaultdict(list)
        for q, t in quoi.items():
            for p in phrases(sections_utiles(txt.get(t, ""), tout=True)):
                for typ, rx in RX_DECL_AUTRES.items():
                    if rx.search(p):
                        phr[q].append((p, typ, rx.search(p).group(0)))
                        a_res |= {c for c, _ in liens_de(p)}
                        break
        res = resoudre(lang, sorted(a_res))
        for q, ps in phr.items():
            for p, typ, mot in ps:
                for c, _ in liens_de(p):
                    titre_res, qid = res.get(c, (c, None))
                    if not qid or qid not in connus or qid == q:
                        continue
                    sens, bonus = sens_et_bonus(q, qid, None, False)
                    if typ == "emanation":
                        sens = "cible → org"
                    ajouter(q, qid, texte_brut(p), mot.lower(), "autre_langue", typ, 0.35 + bonus, sens,
                            f"article {lang} « {quoi[q]} »")
    sauver_cache()

    # --- Signal « internationale_commune » : même Internationale et même famille ---
    membres = defaultdict(set)
    for r in lire("affiliations.csv"):
        membres[r["international_id"]].add(r["party_id"])
    for i, ms in membres.items():
        if len(ms) > 12:
            continue      # grandes Internationales : trop de paires sans signification
        for a in ms:
            if a not in a_fouiller:
                continue
            for b in ms:
                if b != a and b in graphe and graphe[b]["famille"] == graphe[a]["famille"]:
                    sens, bonus = sens_et_bonus(a, b, None, False)
                    nom_i = internationales.get(i, {}).get("name", i)
                    ajouter(a, b, f"membres de la même Internationale ({nom_i}) et de la même famille",
                            "", "internationale_commune", "filiation", 0.1 + bonus / 2, sens)

    # ---------- R8 : citations mot pour mot ----------
    # Les titres des liens internes des articles du graphe sont résolus (et mis en cache) pour que
    # chaque candidat reçoive une citation brute, revérifiable, tirée de l'un des deux articles.
    print("Résolution des liens internes des articles (pour les citations)...")
    import preuves
    corpus = preuves.Corpus()
    # Articles des Internationales (pour leurs successions, règle 1.3, et les citations)
    ids_inter = sorted(q for q in internationales if re.fullmatch(r"Q\d+", q))
    ent_inter = entites(ids_inter)
    wikitextes("fr", sorted({e["liens"]["fr"] for e in ent_inter.values() if e.get("liens", {}).get("fr")}))
    sauver_cache()
    corpus = preuves.Corpus()
    a_res = defaultdict(set)
    for q in list(graphe) + ids_inter:
        for lang, _t, txt in corpus.textes.get(q, []):
            a_res[lang] |= {preuves.titre_norm(m.group(1)) for m in preuves.RX_LIEN.finditer(txt)}
    for lang, titres in a_res.items():
        resoudre(lang, sorted(titres))
    sauver_cache()
    corpus = preuves.Corpus()
    anciennes = {(r["org"], r["cible"], r["signal"], r["type_propose"]): r.get("decision", "")
                 for r in lire("liens_candidats.csv")}
    lignes, sans_citation = [], 0
    for r in sorted(candidats.values(), key=lambda r: (graphe[r[0]]["label"], -r[6])):
        org, cible, sens = r[0], r[1], r[10]
        couples = [(cible, org)] if sens == "cible → org" else [(org, cible)] if sens == "org → cible" \
            else [(cible, org), (org, cible)]
        p = next((p for a, b in couples if (p := preuves.preuve_lien(corpus, a, b))), None)
        if not p:
            sans_citation += 1        # aucune citation mot pour mot : candidat écarté (R8)
            continue
        r[2] = p["citation"]
        r[7] = anciennes.get((org, cible, r[4], r[5]), "")    # décision déjà saisie : conservée
        lignes.append(r + [p["preuve"], p["source"]])
    print(f"  {len(lignes)} candidats avec citation, {sans_citation} écartés faute de citation mot pour mot.")
    ecrire(os.path.join(SORTIE, "liens_candidats.csv"),
           ["org", "cible", "phrase_source", "mot_declencheur", "signal", "type_propose", "confiance",
            "decision", "org_nom", "cible_nom", "sens", "note", "preuve", "source_citation"], lignes)

    # ---------- 0.1 bis : cases vides de actifs.csv, résolues par le texte de l'article ----------
    completer_actifs(corpus)

    # ================= 0.3 Liens manuels =================
    ecrire_manuel("aretes_manuelles.csv",
                  ["ancetre", "descendant", "type", "date_evenement", "source", "note"], [
                      ["", "fr:Parti communiste révolutionnaire (2024)", "renommage", "2024", "",
                       "Révolution (section française de la TMI) devient le PCR : identifiant et date de "
                       "fondation de Révolution à ajouter, source à indiquer"],
                      ["Q158073", "Q1631185", "scission", "", "",
                       "CIO -> Tendance marxiste internationale (devenue ICR) : déjà dans les données, "
                       "date et source à confirmer"],
                      ["", "Q158073", "", "", "",
                       "origine du CIO dans la Quatrième Internationale (via le RSL britannique) : à sourcer"],
                  ])

    # ================= 0.4 Liste de recherche =================
    avec_candidat = {r[0] for r in lignes if r[6] >= 0.5}
    restants = sorted((q for q in sans_lien if q not in avec_candidat), key=lambda q: graphe[q]["label"])
    lignes_rech = []
    for q in restants:
        nom = graphe[q]["label"]
        nom_q = quote(f'"{re.sub(r" \\([^)]*\\)$", "", nom)}"')
        site = (ent.get(q, {}).get("site") or [""])[0]
        t = titre_fr_de.get(q)
        lignes_rech.append([
            q, nom, graphe[q].get("fondation", ""), graphe[q]["famille"],
            sum(1 for r in lignes if r[0] == q),
            f"https://maitron.fr/spip.php?page=recherche&recherche={quote(re.sub(r' \\([^)]*\\)$', '', nom))}",
            f"https://duckduckgo.com/?q=site%3Amarxists.org+{nom_q}",
            site,
            f"https://fr.wikipedia.org/wiki/{quote(t.replace(' ', '_'))}" if t else "",
            f"https://www.wikidata.org/wiki/{q}" if q.startswith("Q") else ""])
    # Organisations importantes à réexaminer, quelle que soit leur situation (demande explicite)
    a_reexaminer = {"Du Pain et des Roses": "émanation probable de Révolution permanente : lien à sourcer",
                    "Le Poing Levé": "émanation probable de Révolution permanente : lien à sourcer",
                    "Parti communiste révolutionnaire": "PCR 2024 : renommage de Révolution (TMI, devenue ICR) "
                                                        "à sourcer ; Révolution absente des sources"}
    deja = {l[0] for l in lignes_rech}
    for l in lignes_rech:
        l.append(a_reexaminer.get(graphe[l[0]]["label"], ""))
    for q, o in graphe.items():
        if o["label"] in a_reexaminer and q not in deja:
            t = titre_fr_de.get(q)
            lignes_rech.append([q, o["label"], o.get("fondation", ""), o["famille"],
                                sum(1 for r in lignes if r[0] == q),
                                f"https://maitron.fr/spip.php?page=recherche&recherche={quote(o['label'])}",
                                f"https://duckduckgo.com/?q=site%3Amarxists.org+{quote(chr(34) + o['label'] + chr(34))}",
                                (ent.get(q, {}).get("site") or [""])[0],
                                f"https://fr.wikipedia.org/wiki/{quote(t.replace(' ', '_'))}" if t else "",
                                f"https://www.wikidata.org/wiki/{q}" if q.startswith("Q") else "",
                                a_reexaminer[o["label"]]])
    ecrire(os.path.join(SORTIE, "liste_recherche.csv"),
           ["id", "nom", "fondation", "famille", "nb_candidats", "maitron", "marxists_org",
            "site_officiel", "wikipedia", "wikidata", "note"], lignes_rech)

    # ================= Résumé =================
    par_signal = Counter(r[4] for r in lignes)
    par_signal_fort = Counter(r[4] for r in lignes if r[6] >= 0.5)
    orgs_avec = len({r[0] for r in lignes})
    txt = f"""# Phase 0 : résumé de l'enrichissement

## Point de départ
- {len(graphe)} organisations dans le graphe (datées et sans date).
- **{len(graphe) - len(sans_lien)} avec au moins un lien de lignée, {len(sans_lien)} sans aucun lien.**
- {len(arbres_sans_actif)} arbres sans aucune organisation active ({sum(map(len, arbres_sans_actif))} organisations).
- {len(a_fouiller)} organisations fouillées (sans lien, ou dans un arbre sans organisation active).

## 0.1 Organisations actives
- {len(lignes_actifs)} organisations marquées actives, dans data/manuel/actifs.csv, à valider
  (colonne valide = oui). {sum(1 for l in lignes_actifs if 'AUCUN' in l[4])} sans aucun indice d'activité récente.

## 0.2 Liens candidats (data/sortie/liens_candidats.csv)
- {len(lignes)} candidats pour {orgs_avec} organisations.
- Par signal : {", ".join(f"{s} {n}" for s, n in par_signal.most_common())}.
- Confiance d'au moins 0,5 : {sum(par_signal_fort.values())} ({", ".join(f"{s} {n}" for s, n in par_signal_fort.most_common())}).
- Par type proposé : {", ".join(f"{t} {n}" for t, n in Counter(r[5] for r in lignes).most_common())}.
- Aucun n'est accepté automatiquement : mettre decision = oui sur les bons.

## 0.3 Liens manuels
- data/manuel/aretes_manuelles.csv : en-têtes et 3 lignes à compléter (source obligatoire).

## 0.4 Recherche ailleurs
- {len(lignes_rech)} organisations encore sans candidat solide, dans data/sortie/liste_recherche.csv,
  avec des adresses de recherche (Maitron, marxists.org, site officiel, Wikipédia, Wikidata).
  Rien n'a été téléchargé sur ces sites.
"""
    with open(os.path.join(SORTIE, "resume_phase0.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)


def completer_actifs(corpus):
    """Cases vides de la colonne valide d'actifs.csv : proposition lue dans le texte de l'article
    (présent « est un parti » ou passé « était », « dissous »...), avec confiance et citation.
    Les valeurs déjà saisies (oui / non) ne sont jamais modifiées."""
    import preuves
    chemin = os.path.join(MANUEL, "actifs.csv")
    if not os.path.exists(chemin):
        return
    brut = open(chemin, encoding="utf-8", newline="").read()
    fin = "\r\n" if "\r\n" in brut else "\n"
    lignes = list(csv.reader(brut.splitlines()))
    entete = lignes[0]
    # Colonnes sans nom et toujours vides (artefacts du tableur) : retirées
    vides = [i for i, h in enumerate(entete) if not h.strip() and all(i >= len(l) or not l[i].strip() for l in lignes[1:])]
    lignes = [[c for i, c in enumerate(l) if i not in vides] for l in lignes]
    entete = lignes[0]
    for col in ("confiance", "source"):
        if col not in entete:
            entete.append(col)
    iv, ic, isrc = entete.index("valide"), entete.index("confiance"), entete.index("source")
    n, a_revoir = Counter(), []
    for l in lignes[1:]:
        l += [""] * (len(entete) - len(l))
        if l[iv].strip():
            continue
        val, conf, citation, source = preuves.preuve_activite(corpus, l[0])
        if not val:
            n["sans texte"] += 1
            continue
        a_revoir.append([l[0], l[1], val, conf, source, citation])
        if conf == "faible":
            # Le présent de narration (« est un parti ») ne prouve pas l'activité : à revoir, pas deviné
            n[f"{val} faible (à revoir)"] += 1
            continue
        l[iv], l[ic] = val, conf
        l[isrc] = f"automatique, {source} : « {citation} »"
        n[val] += 1
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator=fin).writerows(lignes)
    ecrire(os.path.join(SORTIE, "actifs_a_revoir.csv"),
           ["id", "nom", "proposition", "confiance", "source", "citation"], a_revoir)
    print(f"  actifs.csv : cases vides : {dict(n)} ; propositions dans data/sortie/actifs_a_revoir.csv")


def ecrire(chemin, entetes, lignes):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(entetes)
        w.writerows(lignes)


def ecrire_manuel(nom, entetes, lignes):
    """Fichier à remplir à la main : créé une seule fois, jamais écrasé."""
    chemin = os.path.join(MANUEL, nom)
    if os.path.exists(chemin):
        print(f"  {chemin} existe déjà : laissé tel quel.")
        return
    ecrire(chemin, entetes, lignes)


if __name__ == "__main__":
    main()
