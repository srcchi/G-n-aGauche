# G-n-aGauche

Arbre généa-phylo-génétique des organisations de gauche en France : filiations, scissions,
fusions, appartenance aux Internationales, et (à venir) passages de militants d'une
organisation à l'autre.

## Chaîne de traitement

Dépendances : `pip install requests networkx mwparserfromhell`, et Graphviz (commande `dot`).

| Étape | Script | Source | Produit |
|---|---|---|---|
| 1 | `arbre.py` | Wikidata (SPARQL) | `data/noeuds.csv`, `data/aretes.csv` |
| 2 | `infobox.py` | Infobox de Wikipédia FR | `data/wp_noeuds.csv`, `data/wp_aretes.csv`, `data/wp_valeurs_sans_lien.csv` |
| 3 | `fusion.py` | Les deux + corrections manuelles | `data/org_noeuds.csv`, `data/org_aretes.csv`, `data/org_exclus.csv` |
| 4 | `arbre_orgs.py` | Sortie de `fusion.py` | `data/arbre_orgs.svg` (+ `.dot`) |

```bash
python arbre.py && python infobox.py && python fusion.py && python arbre_orgs.py
```

Après une correction manuelle, seules les deux dernières étapes sont à relancer :
`python fusion.py && python arbre_orgs.py`.

### Options

- `infobox.py --refresh`, `fusion.py --refresh` : vident les caches et retéléchargent tout.
- `arbre_orgs.py --tout` : toutes les organisations, même disparues sans descendance actuelle.
  Par défaut, l'arbre part des organisations françaises encore existantes et remonte leurs ancêtres.
- `arbre_orgs.py --sans-internationales` : masque les Internationales.
- `arbre_orgs.py --depuis 1900` : seulement les organisations fondées après cette année.
- `arbre_orgs.py --min-taille 20000` : seulement les « grandes » organisations, celles dont l'article
  Wikipédia fait au moins ce nombre de caractères (plus celles ajoutées dans les corrections).
  Une lignée qui passe par des petites organisations est résumée par un lien gris en tirets.

## Caches

Les fichiers `data/cache_*.json` gardent les données brutes téléchargées. Les CSV sont
recalculés entièrement à chaque exécution à partir de ces caches : on peut modifier le code
d'analyse et relancer en quelques secondes, sans réseau.

## Corrections manuelles

Les CSV produits par les scripts sont **écrasés** à chaque exécution : ne pas les modifier à la main.
Les corrections vont dans deux fichiers, relus à chaque exécution de `fusion.py` :

**`data/corrections_noeuds.csv`** : `id,action,label,fondation,dissolution,courants,journaux`

- `id` : identifiant Wikidata (`Q...`) ou identifiant libre (`fr:Mon organisation`) pour une
  organisation absente de Wikidata.
- `action` : `inclure`, `exclure`, `vivant` (existe encore) ou `disparu`.
- Les autres colonnes, si remplies, remplacent les données des sources.
  Plusieurs courants ou journaux se séparent par `|`.

**`data/corrections_aretes.csv`** : `ancetre,descendant,type,action`

- `type` : `filiation`, `scission`, `passage` (militants passés d'une organisation à l'autre,
  ex. entrisme) ou `appartenance` (membre d'une Internationale).
- `action` : vide pour ajouter le lien, `supprimer` pour retirer un lien erroné.

## Lecture de l'arbre

- Couleur = courant : noir (anarchisme), rouge (communisme : trotskysme, maoïsme...),
  rose (social-démocratie), vert (écologie), gris clair (inconnu).
- Trait gris : filiation ou fusion. Tirets rouges : scission. Pointillés bleus : passage de militants.
- Double bordure : Internationale ; pointillés gris sans flèche : « membre de ».
- Bordure en tirets : organisation étrangère.
