# Phase 0 : résumé de l'enrichissement

## Point de départ
- 436 organisations dans le graphe (datées et sans date).
- **175 avec au moins un lien de lignée, 261 sans aucun lien.**
- 7 arbres sans aucune organisation active (14 organisations).
- 275 organisations fouillées (sans lien, ou dans un arbre sans organisation active).

## 0.1 Organisations actives
- 181 organisations marquées actives, dans data/manuel/actifs.csv, à valider
  (colonne valide = oui). 6 sans aucun indice d'activité récente.

## 0.2 Liens candidats (data/sortie/liens_candidats.csv)
- 1274 candidats pour 250 organisations.
- Par signal : texte 919, pages_liees 329, internationale_commune 16, autre_langue 10.
- Confiance d'au moins 0,5 : 635 (texte 548, pages_liees 81, autre_langue 6).
- Par type proposé : scission 475, filiation 440, fusion 224, emanation 87, passage_militants 48.
- Aucun n'est accepté automatiquement : mettre decision = oui sur les bons.

## 0.3 Liens manuels
- data/manuel/aretes_manuelles.csv : en-têtes et 3 lignes à compléter (source obligatoire).

## 0.4 Recherche ailleurs
- 170 organisations encore sans candidat solide, dans data/sortie/liste_recherche.csv,
  avec des adresses de recherche (Maitron, marxists.org, site officiel, Wikipédia, Wikidata).
  Rien n'a été téléchargé sur ces sites.
