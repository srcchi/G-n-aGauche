# Phase 0 : résumé de l'enrichissement

## Point de départ
- 541 organisations dans le graphe (datées et sans date).
- **208 avec au moins un lien de lignée, 333 sans aucun lien.**
- 11 arbres sans aucune organisation active (30 organisations).
- 363 organisations fouillées (sans lien, ou dans un arbre sans organisation active).

## 0.1 Organisations actives
- 232 organisations marquées actives, dans data/manuel/actifs.csv, à valider
  (colonne valide = oui). 9 sans aucun indice d'activité récente.

## 0.2 Liens candidats (data/sortie/liens_candidats.csv)
- 1857 candidats pour 329 organisations.
- Par signal : texte 1100, pages_liees 710, internationale_commune 37, autre_langue 10.
- Confiance d'au moins 0,5 : 793 (texte 639, pages_liees 150, autre_langue 4).
- Par type proposé : filiation 819, scission 604, fusion 246, emanation 118, passage_militants 70.
- Aucun n'est accepté automatiquement : mettre decision = oui sur les bons.

## 0.3 Liens manuels
- data/manuel/aretes_manuelles.csv : en-têtes et 3 lignes à compléter (source obligatoire).

## 0.4 Recherche ailleurs
- 206 organisations encore sans candidat solide, dans data/sortie/liste_recherche.csv,
  avec des adresses de recherche (Maitron, marxists.org, site officiel, Wikipédia, Wikidata).
  Rien n'a été téléchargé sur ces sites.
