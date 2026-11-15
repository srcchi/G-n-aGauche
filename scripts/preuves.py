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

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # racine du dépôt
DATA = os.path.join(RACINE, "data")
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


def mentions(corpus, q, noms):
    """Phrases de l'article de q qui citent en clair l'un des noms donnés (sans lien interne),
    ex. « le '''NPA – Révolutionnaires''' (NPA-R) ». Les noms de moins de 3 lettres sont ignorés."""
    noms = [n for n in noms if n and len(n) >= 3]
    if not noms:
        return
    rx = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in sorted(noms, key=len, reverse=True)) + r")(?![\w-])")
    for lang, titre, txt in corpus.textes.get(q, []):
        for m in rx.finditer(txt):
            ligne_deb = txt.rfind("\n", 0, m.start()) + 1
            if txt[ligne_deb:m.start()].lstrip().startswith(("|", "{", "*", "[[Fichier", "<")):
                continue          # infobox, modèle, liste ou légende : pas une phrase
            yield f"{lang}:{titre}", phrase_autour(txt, m.start(), m.end()), ""


def preuve_lien(corpus, a, b, noms=None):
    """Meilleure citation pour un lien entre a (ancêtre) et b (descendant), cherchée dans les
    articles des deux organisations : liens internes, puis mentions en clair du nom ou du sigle
    (noms = {identifiant: [noms]}). Renvoie dict(preuve, citation, source, indice) ou None."""
    meilleure = None
    noms = noms or {}
    for x, y, cote in ((b, a, "descendant"), (a, b, "ancetre")):
        trouves = list(occurrences(corpus, x, y))
        if not any(not ch and type_de_phrase(c) for _, c, ch in trouves):
            trouves += list(mentions(corpus, x, noms.get(y, [])))
        for source, citation, champ in trouves:
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
                     indice=indice or "", rang=rang, champ=champ, cote=cote)
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


def type_du_champ(champ):
    """Type de relation dit par un champ d'infobox (règle 1.2c), ou None."""
    if not champ:
        return None
    if re.search(r"scission", champ, re.I):
        return "scission"
    if re.search(r"fusion", champ, re.I):
        return "fusion"
    if re.search(CHAMPS_LIGNEE["pred"] + "|" + CHAMPS_LIGNEE["succ"], champ, re.I):
        return "succession"
    return None


RX_FIN = re.compile(r"\b(?:disparition|dissolution|autodissolution|auto-dissolution|dissous|dissoute|"
                    r"se dissout|s'autodissout|s'auto-dissout|cesse d'exister|met fin à ses activités)\b", re.I)
RX_ANNEE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def fin_dans_texte(corpus, q, noms, fondation):
    """Date de fin lue dans le texte de l'article : phrase qui dit la disparition de l'organisation
    (son sigle ou son nom tout près du mot), avec une année. Renvoie (année, citation, source) ou None.
    Ex. « En 2024, les deux groupes trouvent un accord, actant la disparition du NPA… »."""
    rx_nom = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in noms if len(n) >= 2) + r")\b")
    for lang, titre, txt in corpus.textes.get(q, []):
        if lang != "fr":
            continue
        for m in RX_FIN.finditer(txt):
            phrase = phrase_autour(txt, m.start(), m.end())
            if phrase.lstrip().startswith(("|", "{", "<", "*")) or "<ref" in phrase[:5]:
                continue
            pos = phrase.find(m.group(0))
            voisinage = phrase[max(0, pos - 60):pos + len(m.group(0)) + 60]
            if not rx_nom.search(voisinage):
                continue
            annees = [int(a) for a in RX_ANNEE.findall(phrase) if not fondation or int(a) >= fondation]
            if len(set(annees)) == 1:            # une seule année possible : pas d'ambiguïté
                return annees[0], phrase, f"{lang}:{titre}"
    return None


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
