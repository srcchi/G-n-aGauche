"""
Preuves : citations mot pour mot tirées du wikitexte brut en cache (règle R8).

Chaque lien, affiliation ou statut d'activité doit s'appuyer sur une citation trouvée telle quelle
dans le wikitexte d'un article (data/cache_wikitext.json, data/sortie/cache_enrichissement.json).
Ce module trouve ces citations et sait les revérifier.

  preuve = "explicite" : la citation dit la relation (champ d'infobox ou mot déclencheur)
  preuve = "deduit"    : la citation mentionne l'autre organisation sans dire la relation
"""

import json
import os
import re

DATA = "data"
SORTIE = os.path.join(DATA, "sortie")

# Champs d'infobox -> sens de la relation pour l'organisation de l'article
CHAMPS_LIGNEE = {
    "pred": r"pr[ée]d[ée]cesseur|pr[ée]c[ée]d[ée] par|fusion de|issu de|remplace|pr[ée]c[ée]dent",
    "succ": r"successeur|suivi par|fusionn[ée] dans|devenu|remplac[ée] par|suivant",
    "scission_de": r"scission de",
    "scission_vers": r"scissions?|scission vers|scission dans",
}
CHAMPS_AFFIL = r"international|internationale|affiliation|affi |affi_|europ"
# Mots déclencheurs dans une phrase -> type de relation
DECLENCHEURS = [
    ("fusion", r"fusion|fusionn"),
    ("scission", r"scission|scind|exclu|rupture avec"),
    ("refondation", r"refond"),
    ("renommage", r"rebaptis|renomm|nouveau nom|prend le nom|change de nom|devient le|devient la|"
                  r"ancien nom|anciennement"),
    ("absorption", r"absorb|rejoign|rejoint|int[èe]gre|se fond dans|dissout dans|entr[ée]e? dans"),
    ("filiation", r"issue? d|successeur|succède|héritier|fond[ée]e? par (?:des |d'anciens )?(?:militants|membres)"),
]
RX_DECL = [(t, re.compile(rf"\b(?:{m})", re.I)) for t, m in DECLENCHEURS]
RX_AFFIL = re.compile(r"membre|adh[èée]r|section|affili|rejoint|rejoign|fondat|observateur", re.I)
RX_LIEN = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")


def lire_json(chemin):
    if not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def titre_norm(t):
    t = t.replace("_", " ").strip()
    return t[:1].upper() + t[1:]


class Corpus:
    """Wikitextes bruts en cache, par identifiant, et résolution des liens internes."""

    def __init__(self):
        ancien = lire_json(os.path.join(DATA, "cache_wikitext.json"))
        self.enrich = lire_json(os.path.join(SORTIE, "cache_enrichissement.json"))
        self.res_ancienne = lire_json(os.path.join(DATA, "cache_resolution.json"))
        self.textes = {}          # q -> [(langue, titre, texte brut)]
        self.brut = {}            # "langue:titre" -> texte brut (pour revérifier)
        for t, v in ancien.items():
            if v.get("text"):
                self.brut[f"fr:{t}"] = v["text"]
                q = v.get("qid") or f"fr:{t}"
                self.textes.setdefault(q, []).append(("fr", t, v["text"]))
        for cle, txt in self.enrich.get("wikitext", {}).items():
            if txt and cle not in self.brut:
                self.brut[cle] = txt
        for q, e in self.enrich.get("entites", {}).items():
            for lang, t in e.get("liens", {}).items():
                cle = f"{lang}:{t}"
                if self.brut.get(cle) and not any(x[0] == lang for x in self.textes.get(q, [])):
                    self.textes.setdefault(q, []).append((lang, t, self.brut[cle]))
        self.manquants = set()

    def resoudre(self, lang, titre):
        t = titre_norm(titre)
        if lang == "fr" and t in self.res_ancienne:
            return self.res_ancienne[t][1] or f"fr:{self.res_ancienne[t][0]}"
        r = self.enrich.get("resolution", {}).get(f"{lang}:{t}")
        if r:
            return r[1] or (f"fr:{r[0]}" if lang == "fr" else None)
        self.manquants.add((lang, t))
        return f"fr:{t}" if lang == "fr" else None

    def verifier(self, citation, source):
        """La citation figure-t-elle mot pour mot dans le wikitexte en cache ?"""
        txt = self.brut.get(source)
        return bool(txt) and citation in txt


def phrase_autour(txt, debut, fin, maxi=320):
    """Phrase brute (mot pour mot) autour d'une position, sans couper un lien [[...]]."""
    g = debut
    while g > 0:
        c = txt[g - 1]
        if c == "\n" or (c == " " and txt[g - 2:g - 1] in ".!?" and txt.count("[[", 0, g) == txt.count("]]", 0, g)):
            break
        g -= 1
    d = fin
    while d < len(txt):
        c = txt[d]
        if c == "\n" or (c in ".!?" and txt.count("[[", 0, d) == txt.count("]]", 0, d)):
            d += 1 if c != "\n" else 0
            break
        d += 1
    phrase = txt[g:d]
    if len(phrase) > maxi:                    # fenêtre autour du lien, toujours mot pour mot
        rel_d, rel_f = debut - g, fin - g
        a = max(0, min(rel_d - 150, len(phrase) - maxi))
        phrase = phrase[a:a + maxi]
    return phrase.strip()


def occurrences(corpus, q, cible):
    """Passages de l'article de q qui contiennent un lien vers cible : (source, citation, champ)."""
    for lang, titre, txt in corpus.textes.get(q, []):
        for m in RX_LIEN.finditer(txt):
            if corpus.resoudre(lang, m.group(1)) != cible:
                continue
            debut_ligne = txt.rfind("\n", 0, m.start()) + 1
            fin_ligne = txt.find("\n", m.end())
            ligne = txt[debut_ligne:fin_ligne if fin_ligne >= 0 else len(txt)]
            mc = re.match(r"\s*\|\s*([^=|]+?)\s*=", ligne)
            if mc:                             # champ d'infobox : la ligne entière est la citation
                yield f"{lang}:{titre}", ligne.strip(), mc.group(1).strip().lower()
            else:
                yield f"{lang}:{titre}", phrase_autour(txt, m.start(), m.end()), ""


def type_de_phrase(citation):
    for t, rx in RX_DECL:
        if rx.search(citation):
            return t
    return None


def preuve_lien(corpus, a, b):
    """Meilleure citation pour un lien entre a (ancêtre) et b (descendant), cherchée dans les
    articles des deux organisations. Renvoie dict(preuve, citation, source, indice) ou None."""
    meilleure = None
    for x, y, cote in ((b, a, "descendant"), (a, b, "ancetre")):
        for source, citation, champ in occurrences(corpus, x, y):
            indice, rang = None, 3
            if champ:
                for role, rx in CHAMPS_LIGNEE.items():
                    if re.search(rx, champ, re.I):
                        coherent = (role in ("pred", "scission_de") and cote == "descendant") or \
                                   (role in ("succ", "scission_vers") and cote == "ancetre")
                        indice = "scission" if role.startswith("scission") else (
                            "fusion" if "fusion" in champ else "filiation")
                        rang = 0 if coherent else 2
                        break
                else:
                    continue      # autre champ d'infobox (siège, idéologie...) : pas une preuve
            else:
                indice = type_de_phrase(citation)
                rang = 1 if indice else 3
            p = dict(preuve="explicite" if rang <= 1 else "deduit", citation=citation, source=source,
                     indice=indice or "", rang=rang)
            if meilleure is None or rang < meilleure["rang"]:
                meilleure = p
            if rang == 0:
                return meilleure
    return meilleure


def preuve_affiliation(corpus, parti, intl):
    """R7 : citation tirée de l'article de l'organisation elle-même."""
    meilleure = None
    for source, citation, champ in occurrences(corpus, parti, intl):
        if champ:
            if not re.search(CHAMPS_AFFIL, champ, re.I):
                continue
            p = dict(preuve="explicite", citation=citation, source=source, rang=0)
        else:
            rang = 1 if RX_AFFIL.search(citation) else 2
            p = dict(preuve="explicite" if rang == 1 else "deduit", citation=citation, source=source, rang=rang)
        if meilleure is None or p["rang"] < meilleure["rang"]:
            meilleure = p
    return meilleure


RX_ACTIF_OUI = re.compile(r"'''[^']+'''[^.\n]{0,120}?\best (?:un|une)\b", re.I)
RX_ACTIF_NON = re.compile(r"'''[^']+'''[^.\n]{0,160}?\b(?:était|fut|a été|est un ancien|est une ancienne)\b|"
                          r"\b(?:dissous|dissoute|autodissous|autodissoute|disparu|disparue)\b", re.I)


def preuve_activite(corpus, q):
    """Proposition pour la colonne valide d'actifs.csv : (valeur, confiance, citation, source)."""
    for lang, titre, txt in corpus.textes.get(q, []):
        if lang != "fr":
            continue
        corps = re.sub(r"\{\{[^{}]*\}\}", lambda m: " " * len(m.group(0)), txt)   # garde les positions
        m_oui = RX_ACTIF_OUI.search(corps)
        m_non = RX_ACTIF_NON.search(corps[:4000])
        if m_non and (not m_oui or m_non.start() < m_oui.end() + 200):
            return "non", "moyenne", phrase_autour(txt, m_non.start(), m_non.end()), f"fr:{titre}"
        if m_oui:
            return "oui", "faible", phrase_autour(txt, m_oui.start(), m_oui.end()), f"fr:{titre}"
    return "", "", "", ""
