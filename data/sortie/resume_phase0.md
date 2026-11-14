# Phase 0 : résumé de l'enrichissement

## Point de départ
- 440 organisations dans le graphe (datées et sans date).
- **152 avec au moins un lien de lignée, 288 sans aucun lien.**
- 9 arbres sans aucune organisation active (24 organisations).
- 312 organisations fouillées (sans lien, ou dans un arbre sans organisation active).

## 0.1 Organisations actives
- 190 organisations marquées actives, dans data/manuel/actifs.csv, à valider
  (colonne valide = oui). 6 sans aucun indice d'activité récente.

## 0.2 Liens candidats (data/sortie/liens_candidats.csv)
- 1440 candidats pour 265 organisations.
- Par signal : texte 953, pages_liees 461, internationale_commune 16, autre_langue 10.
- Confiance d'au moins 0,5 : 681 (texte 567, pages_liees 108, autre_langue 6).
- Par type proposé : filiation 547, scission 534, fusion 223, emanation 85, passage_militants 51.
- Aucun n'est accepté automatiquement : mettre decision = oui sur les bons.

## 0.3 Liens manuels
- data/manuel/aretes_manuelles.csv : en-têtes et 3 lignes à compléter (source obligatoire).

## 0.4 Recherche ailleurs
- 185 organisations encore sans candidat solide, dans data/sortie/liste_recherche.csv,
  avec des adresses de recherche (Maitron, marxists.org, site officiel, Wikipédia, Wikidata).
  Rien n'a été téléchargé sur ces sites.
