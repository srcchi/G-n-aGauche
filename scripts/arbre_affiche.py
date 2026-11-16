"""
Affiche (addendum 3, A3 et E) : affiche.svg et affiche.pdf, A0 portrait (choix de l'utilisateur, 16 novembre 2026).

Ce script ne change ni les données ni la logique de lignée (A4) : il relit les sorties de nettoyage.py,
applique le thème de theme_affiche.json (palette, polices, tailles), refait sa propre mise en page avec
l'algorithme de rendu.py (A3), puis compose la page :
- en haut, le titre et le sous-titre (période, sources) ;
- au centre, l'arbre complet (voie des Internationales comprise), avec les six repères datés de
  data/manuel/reperes.csv en filets verticaux, et à droite la colonne des partis actifs (E4) ;
- en bas à gauche, la clé des Internationales ; en bas à droite, la vue par Internationale.

Les largeurs de texte sont mesurées avec les vraies polices (Pillow lit les fichiers de fonts/), et les
polices sont déclarées à fontconfig pour que CairoSVG les incorpore au PDF.

Sorties : arbres/affiche_arbre.svg (l'arbre seul, vérifié par verifier.py), arbres/affiche.svg,
arbres/affiche.pdf, data/sortie/mise_en_page_affiche.json. Échoue si la vérification échoue.

Usage : python scripts/arbre_affiche.py
Dépendances : cairosvg (requirements.txt), Pillow (fourni avec Anaconda).
"""
import csv
import html
import json
import os
import re
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
THEME = json.load(open(os.path.join(RACINE, "theme_affiche.json"), encoding="utf-8"))
ARBRES = os.path.join(RACINE, "arbres")
SORTIE = os.path.join(RACINE, "data", "sortie")

# ---------- Polices : fontconfig doit les voir avant l'import de CairoSVG ----------
CONF = os.path.join(SORTIE, "fonts_affiche.conf")
os.makedirs(SORTIE, exist_ok=True)
with open(CONF, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
            f'<dir>{html.escape(os.path.join(RACINE, "fonts"))}</dir>'
            '<include ignore_missing="yes">/etc/fonts/fonts.conf</include></fontconfig>')
os.environ["FONTCONFIG_FILE"] = CONF

from PIL import ImageFont  # noqa: E402
import rendu as R  # noqa: E402

P = THEME["polices"]
T = THEME["tailles"]
ENCRE, PAPIER = THEME["encre"], THEME["papier"]
RX_DATE = re.compile(r"^\s*[0-9?]{0,4}\s*[–-]\s*[0-9]{0,4}\s*$|^\d{4}$")
_cache_polices = {}


def police(fichier, taille):
    cle = (fichier, round(taille * 4))
    if cle not in _cache_polices:
        _cache_polices[cle] = ImageFont.truetype(os.path.join(RACINE, fichier), max(1, round(taille * 4)))
    return _cache_polices[cle]


def larg_vraie(s, fs, gras=False):
    """Largeur réelle du texte dans la police de l'affiche (mesurée au quadruple puis réduite)."""
    fam = P["dates"] if RX_DATE.match(s) else P["noms"]
    fichier = fam.get("fichier_gras", fam["fichier"]) if gras else fam["fichier"]
    return police(fichier, fs).getlength(s) / 4 + 2


_texte_origine = R.texte


def texte_affiche(x, y, s, fs=None, gras=False, couleur="#1A1A1A", ancre="start", cls="", extra="", italique=False):
    """Même texte que rendu.py, police de l'affiche : dates en IBM Plex Mono, titres de voie en Fraunces."""
    fs = R.FS if fs is None else fs
    if couleur in ("#1A1A1A", "#111111", "#333333"):
        couleur = ENCRE
    t = _texte_origine(x, y, s, fs, gras, couleur, ancre, cls, extra, italique)
    fam = (P["dates"]["famille"] if RX_DATE.match(str(s)) else
           P["titre"]["famille"] if cls == "voie-t" and gras else P["noms"]["famille"])
    return t.replace(f'font-family="{R.POLICE}"', f'font-family="{fam}"', 1)


def appliquer_theme():
    R.larg = larg_vraie
    R.texte = texte_affiche
    R.POLICE = P["noms"]["famille"]
    R.FS, R.FS_SIGLE = T["texte"], T["sigle"]
    R.BAR_H, R.BANDE_H, R.ONGLET_H = T["barre"], T["bande"], T["onglet"]
    R.MED_R = R.BANDE_H / 2
    R.INTL_RUBAN, R.INTL_ONGLET, R.INTL_LIGNE = T["intl_ruban"], T["intl_onglet"], T["intl_ligne"]
    R.PPA = float(T["px_par_an"])
    R.NAVY = THEME["internationales"]
    for cle, coul in THEME["familles"].items():
        if cle in R.FAMILLES:
            R.FAMILLES[cle] = (R.FAMILLES[cle][0], coul)
    R.TEINTE.clear()
    R.TEINTE.update({k: c for k, (_, c) in R.FAMILLES.items()})
    for st in R.STYLE_LIEN.values():           # E3 : liens à l'encre, 1,5 px ; le type se lit au tiret
        st["couleur"], st["w"] = ENCRE, THEME["liens"]["epaisseur"]


def habiller(svg, m):
    """E1 et E3 sur le SVG de l'arbre : papier, fonds de voie à 8 %, ancêtres à 70 %, liens à 70 %,
    ligne d'aujourd'hui dorée."""
    svg = re.sub(r'</defs><rect width="([\d.]+)" height="([\d.]+)" fill="#FFFFFF"/>',
                 lambda mm: f'</defs><rect width="{mm.group(1)}" height="{mm.group(2)}" fill="{PAPIER}"/>', svg, count=1)
    # le titre de l'arbre double celui de l'affiche : retiré (la ligne des comptes reste, verifier.py la lit)
    svg = re.sub(r'(<g class="legende">)<text [^>]*class="legende-t">[^<]*</text>', r"\1", svg, count=1)
    for g in m["voies"]:
        coul = R.TEINTE.get(g["cle"], "#8C8C8C")
        svg = re.sub(r'(<g class="voie" data-voie="%d"[^>]*><rect class="fond-voie"[^>]*?)fill="[^"]*"' % g["i"],
                     lambda mm: mm.group(1) + f'fill="{coul}" fill-opacity="{THEME["opacite_fond_voie"]}"', svg, count=1)
    svg = re.sub(r'(<rect class="barre"[^>]*data-statut="(?!actif)[^"]*"[^>]*?)(/>)',
                 lambda mm: mm.group(1) + f' fill-opacity="{THEME["opacite_ancetres"]}"' + mm.group(2), svg)
    svg = svg.replace('stroke="#777777" stroke-dasharray="2 4"', f'stroke="{THEME["aujourdhui"]}" stroke-width="2" '
                                                              'stroke-dasharray="6 4"')
    svg = svg.replace('<g class="liens">', f'<g class="liens" opacity="{THEME["liens"]["opacite"]}">', 1)
    return svg


def polices_css():
    """Polices incorporées au SVG (@font-face, fichiers en base64) : sans elles, un visualiseur qui ne les a
    pas installées prend une police plus large et les dates chevauchent les noms (le PDF, lui, les incorpore
    déjà). Familles et graisses : celles du thème."""
    import base64
    regles = []
    for fam, fichier, graisse in (
            (P["noms"]["famille"], P["noms"]["fichier"], "400"),
            (P["noms"]["famille"], P["noms"]["fichier_gras"], "700"),
            (P["dates"]["famille"], P["dates"]["fichier"], "400"),
            (P["dates"]["famille"], P["dates"]["fichier_gras"], "700"),
            (P["titre"]["famille"], P["titre"]["fichier"], "100 900")):
        with open(os.path.join(RACINE, fichier), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        regles.append(f"@font-face{{font-family:'{fam}';font-weight:{graisse};"
                      f"src:url(data:font/ttf;base64,{b64}) format('truetype')}}")
    return "<defs><style>" + "".join(regles) + "</style></defs>"


def incorporer_polices(svg):
    """Insère les @font-face juste après la balise <svg> racine."""
    return re.sub(r"(<svg\b[^>]*>)", lambda mm: mm.group(1) + polices_css(), svg, count=1)


def lire_reperes():
    with open(os.path.join(RACINE, THEME["reperes"]), encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("citation", "").strip()]


def grille(v):
    g = THEME["page"]["grille"]
    return round(v / g) * g


NON_PARTIS = set()          # rempli dans main : organisations typées fondatrice ou satellite (types.csv)


def texte_repere(x, y, s, x_max):
    w = R.larg(s, T["repere"], True)
    debord = x + 6 + w > x_max
    return (f'<text x="{(x - 6) if debord else (x + 6):.1f}" y="{y:.1f}" text-anchor="{"end" if debord else "start"}" '
            f'font-family="{P["noms"]["famille"]}" font-size="{T["repere"]}" font-weight="600" fill="{ENCRE}">'
            f'{html.escape(s)}</text>')


def _largeur_colonne(m):
    actifs = [o for o in m["items"].values() if o["statut"].startswith("actif")]
    return grille(max(R.larg(o["etiquette"], T["actifs"], True) for o in actifs) + 260)


def composer(m, svg_arbre):
    """E4 : titre en haut à gauche, arbre et colonne des actifs, clé en bas à gauche, vue par
    Internationale en bas à droite, six repères datés."""
    marge = THEME["page"]["marge"]
    ech = m["ech"]
    W_a, H_a = m["largeur"], m["hauteur"]
    actifs = sorted((o for o in m["items"].values() if o["statut"].startswith("actif") and o["id"] not in NON_PARTIS),
                    key=lambda o: (list(R.FAMILLES).index(o["voie"]) if o["voie"] in R.FAMILLES else 99, o["etiquette"]))
    col_w = _largeur_colonne(m)
    ligne_a = T["actifs"] + 12
    # Clé des Internationales et vue par Internationale, côte à côte en bas
    cle_svg, cle_h = R.cle_complete(m, 0, W_a * 0.5)
    vue = R.vue_internationales(m)
    vw, vh = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', vue).groups())
    y_titre = marge
    y_arbre = grille(marge + T["titre"] + T["sous_titre"] + 60)
    y_bas = grille(y_arbre + H_a + 40)
    larg_bas = W_a + col_w + 40
    ech_v = min((larg_bas - W_a * 0.5 - 40) / vw, cle_h / vh)     # dans la place de la clé, sans l'agrandir
    vue_w, vue_h = vw * ech_v, vh * ech_v
    H = grille(y_bas + T["titre_panneau"] + 24 + max(cle_h, vue_h) + marge)
    W = grille(2 * marge + larg_bas)
    # Rapport A0 portrait : la page s'agrandit dans la dimension qui manque, le contenu reste à sa place
    rapport = THEME["page"]["largeur_mm"] / THEME["page"]["hauteur_mm"]
    if W / H < rapport:
        W = grille(H * rapport)
    else:
        H = grille(W / rapport)
    x_arbre = marge
    debut, fin = int(ech.T0), int(m["T_AUJ"])
    el = [f'<rect width="{W}" height="{H}" fill="{PAPIER}"/>']
    # Titre et sous-titre
    el.append(f'<text x="{marge}" y="{y_titre + T["titre"] * 0.85:.0f}" font-family="{P["titre"]["famille"]}" '
              f'font-size="{T["titre"]}" font-weight="700" fill="{ENCRE}">{html.escape(THEME["titre"])}</text>')
    el.append(f'<text x="{marge}" y="{y_titre + T["titre"] + T["sous_titre"] + 6:.0f}" font-family="{P["noms"]["famille"]}" '
              f'font-size="{T["sous_titre"]}" fill="{ENCRE}">'
              f'{html.escape(THEME["sous_titre"].format(debut=debut, fin=fin))}</text>')
    # L'arbre (SVG imbriqué : il garde ses attributs de vérification)
    el.append(f'<g transform="translate({x_arbre},{y_arbre})">{svg_arbre}</g>')
    # Repères datés : filets verticaux sur toute la hauteur de l'arbre, légende courte en haut
    y_r0, y_r1 = y_arbre + m["y_axe_haut"] + 26, y_arbre + m["y_axe_bas"] + 4
    for k, r in enumerate(lire_reperes()):
        x = x_arbre + ech.X(int(r["annee"]))
        el.append(f'<g class="repere" data-annee="{r["annee"]}"><title>{html.escape(r["legende"])} : '
                  f'{html.escape(r["source"])} : « {html.escape(r["citation"])} »</title>'
                  f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y_r0:.1f}" y2="{y_r1:.1f}" stroke="{ENCRE}" stroke-width="1" '
                  f'stroke-opacity="0.35"/>'
                  + texte_repere(x, y_arbre + m["y_axe_haut"] - 6 - (k % 2) * (T["repere"] + 6),
                                 f'{r["annee"]}, {r["legende"]}', x_arbre + W_a) + '</g>')
    # Colonne des partis actifs (point d'entrée, à droite de l'arbre, à la hauteur de ses voies)
    x_c = x_arbre + W_a + 40
    y_c = y_arbre + m["y_axe_haut"] + 40
    el.append(f'<text x="{x_c}" y="{y_c}" font-family="{P["titre"]["famille"]}" font-size="{T["titre_panneau"]}" '
              f'font-weight="700" fill="{ENCRE}">Partis actifs ({len(actifs)})</text>')
    y = y_c + 24
    for o in actifs:
        y += ligne_a
        el.append(f'<rect x="{x_c}" y="{y - T["actifs"] + 3}" width="14" height="{T["actifs"]}" fill="{o["couleur"]}"/>')
        el.append(f'<text x="{x_c + 22}" y="{y}" font-family="{P["noms"]["famille"]}" font-size="{T["actifs"]}" '
                  f'font-weight="600" fill="{ENCRE}">{html.escape(o["etiquette"])}</text>')
        nom = re.sub(r" \((parti politique|parti français|France|organisation politique|francophone)\)$", "", o["label"])
        base = re.sub(r" \(\d{4}\)$", "", o["etiquette"])
        if nom.lower() != base.lower():
            place = col_w - 40 - R.larg(o["etiquette"], T["actifs"], True)
            while nom and R.larg(nom, T["actifs"] - 3) > place:      # coupe sur un mot, avec points de suspension
                nom = nom.rsplit(" ", 1)[0].rstrip(" ,–-") + "…" if " " in nom.rstrip("…") else ""
            el.append(f'<text x="{x_c + 30 + R.larg(o["etiquette"], T["actifs"], True)}" y="{y}" '
                      f'font-family="{P["noms"]["famille"]}" font-size="{T["actifs"] - 3}" fill="{ENCRE}" '
                      f'fill-opacity="0.75">{html.escape(nom)}</text>')
    # Bas de page : clé des Internationales à gauche, vue par Internationale à droite
    el.append(f'<text x="{marge}" y="{y_bas + T["titre_panneau"]}" font-family="{P["titre"]["famille"]}" '
              f'font-size="{T["titre_panneau"]}" font-weight="700" fill="{ENCRE}">Clé des Internationales</text>')
    el.append(f'<g transform="translate({marge},{y_bas + T["titre_panneau"] + 8})">{cle_svg}</g>')
    x_v = marge + W_a * 0.5 + 40
    el.append(f'<text x="{x_v:.0f}" y="{y_bas + T["titre_panneau"]}" font-family="{P["titre"]["famille"]}" '
              f'font-size="{T["titre_panneau"]}" font-weight="700" fill="{ENCRE}">Vue par Internationale</text>')
    vue_corps = re.sub(r"^<svg[^>]*>", "", vue).rsplit("</svg>", 1)[0]
    el.append(f'<svg x="{x_v:.0f}" y="{y_bas + T["titre_panneau"] + 8}" width="{vue_w:.0f}" height="{vue_h:.0f}" '
              f'viewBox="0 0 {vw:.0f} {vh:.0f}">{vue_corps}</svg>')
    mm_l, mm_h = THEME["page"]["largeur_mm"], THEME["page"]["hauteur_mm"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{mm_l}mm" height="{mm_h}mm" viewBox="0 0 {W} {H}" '
            f'font-family="{P["noms"]["famille"]}"><title>{html.escape(THEME["titre"])}</title>' + "".join(el) + "</svg>"), W, H


def main():
    appliquer_theme()
    with open(os.path.join(RACINE, "data", "manuel", "types.csv"), encoding="utf-8") as f:
        types = {}
        for r in csv.DictReader(f):              # la dernière ligne validée l'emporte
            if r.get("valide", "").strip() or r["id"] not in types:
                types[r["id"]] = r.get("type", "").strip()
    NON_PARTIS.update(q for q, t in types.items() if t in ("fondatrice", "satellite", "coalition"))
    # La page A0 portrait est plus large que l'arbre : on élargit l'échelle du temps (px par an) pour la
    # remplir, en quelques passes (la hauteur bouge peu ; des barres plus longues portent mieux leur nom)
    for _passe in range(4):
        orgs, liens, inter, T_AUJ = R.charger()
        m = R.mise_en_page(orgs, liens, inter, T_AUJ)
        svg_arbre = habiller(R.dessiner(m, avec_cle=False), m)
        _page, W, H = composer(m, svg_arbre)
        utile = W - 2 * THEME["page"]["marge"]
        contenu = m["largeur"] + (W - 2 * THEME["page"]["marge"] - m["largeur"]) * 0 + _largeur_colonne(m) + 40
        if contenu >= utile * 0.97:
            break
        R.PPA = round(R.PPA * min(1.6, (utile - _largeur_colonne(m) - 40) / m["largeur"]) * 0.98, 1)
        print(f"  passe {_passe + 1} : page {W} x {H}, contenu {contenu:.0f} sur {utile:.0f} : {R.PPA} px par an")
    chemin_arbre = os.path.join(ARBRES, "affiche_arbre.svg")
    with open(chemin_arbre, "w", encoding="utf-8") as f:
        f.write(svg_arbre)
    # A2 : la mise en page de l'affiche, lisible par un autre outil
    with open(os.path.join(SORTIE, "mise_en_page_affiche.json"), "w", encoding="utf-8") as f:
        json.dump(dict(largeur=m["largeur"], hauteur=m["hauteur"], px_par_an=R.PPA,
                       organisations=[dict(id=q, etiquette=o["etiquette"], voie=o["voie"], x0=round(o["x0"], 2),
                                           x1=round(o["x1"], 2), y=round(o["y_c"], 2), couleur=o["couleur"])
                                      for q, o in m["items"].items()],
                       liens=[dict(a=t["a"], b=t["b"], relation=t["rel"], points=[[round(x, 2), round(y, 2)]
                                                                               for x, y in t["pts"]])
                              for t in m["traces"]]), f, ensure_ascii=False)
    # A3 : même vérification que l'arbre, échec si elle échoue
    r = subprocess.run([sys.executable, os.path.join(RACINE, "scripts", "verifier.py"), chemin_arbre],
                       capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-500:])
    if r.returncode != 0:
        print(r.stdout[-3000:])
        raise SystemExit("Vérification de l'affiche en échec : pas de PDF.")
    page, W, H = composer(m, re.sub(r"^<\?xml[^>]*>", "", svg_arbre))
    chemin_svg = os.path.join(ARBRES, "affiche.svg")
    with open(chemin_svg, "w", encoding="utf-8") as f:
        f.write(incorporer_polices(page))
    with open(chemin_arbre, "w", encoding="utf-8") as f:      # l'arbre seul aussi, une fois vérifié
        f.write(incorporer_polices(svg_arbre))
    import cairosvg
    cairosvg.svg2pdf(url=chemin_svg, write_to=os.path.join(ARBRES, "affiche.pdf"))
    print(f"Affiche : {W} x {H} px sur {THEME['page']['largeur_mm']} x {THEME['page']['hauteur_mm']} mm "
          f"({THEME['page']['largeur_mm'] / W:.3f} mm par px ; texte de {R.FS} px = "
          f"{R.FS * THEME['page']['largeur_mm'] / W:.1f} mm) ; {len(m['items'])} organisations, "
          f"{len(m['traces'])} liens tracés.")
    print("Fichiers : arbres/affiche_arbre.svg, arbres/affiche.svg, arbres/affiche.pdf, data/sortie/mise_en_page_affiche.json")


if __name__ == "__main__":
    main()
