# Phase 0 : résumé de l'enrichissement

## Point de départ
- 465 organisations dans le graphe (datées et sans date).
- **203 avec au moins un lien de lignée, 262 sans aucun lien.**
- 10 arbres sans aucune organisation active (28 organisations).
- 290 organisations fouillées (sans lien, ou dans un arbre sans organisation active).

## 0.1 Organisations actives
- 189 organisations marquées actives, dans data/manuel/actifs.csv, à valider
  (colonne valide = oui). 8 sans aucun indice d'activité récente.

## 0.2 Liens candidats (data/sortie/liens_candidats.csv)
- 882 candidats pour 163 organisations.
- Par signal : pages_liees 510, texte 356, autre_langue 10, internationale_commune 6.
- Confiance d'au moins 0,5 : 330 (texte 203, pages_liees 123, autre_langue 4).
- Par type proposé : filiation 472, scission 249, fusion 76, emanation 48, passage_militants 37.
- Aucun n'est accepté automatiquement : mettre decision = oui sur les bons.

## 0.3 Liens manuels
- data/manuel/aretes_manuelles.csv : en-têtes et 3 lignes à compléter (source obligatoire).

## 0.4 Recherche ailleurs
- 160 organisations encore sans candidat solide, dans data/sortie/liste_recherche.csv,
  avec des adresses de recherche (Maitron, marxists.org, site officiel, Wikipédia, Wikidata).
  Rien n'a été téléchargé sur ces sites.
