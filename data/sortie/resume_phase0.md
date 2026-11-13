# Phase 0 : résumé de l'enrichissement

## Point de départ
- 502 organisations dans le graphe (datées et sans date).
- **202 avec au moins un lien de lignée, 300 sans aucun lien.**
- 8 arbres sans aucune organisation active (24 organisations).
- 324 organisations fouillées (sans lien, ou dans un arbre sans organisation active).

## 0.1 Organisations actives
- 217 organisations marquées actives, dans data/manuel/actifs.csv, à valider
  (colonne valide = oui). 7 sans aucun indice d'activité récente.

## 0.2 Liens candidats (data/sortie/liens_candidats.csv)
- 1731 candidats pour 308 organisations.
- Par signal : texte 1052, pages_liees 635, internationale_commune 34, autre_langue 10.
- Confiance d'au moins 0,5 : 762 (texte 623, pages_liees 135, autre_langue 4).
- Par type proposé : filiation 734, scission 589, fusion 235, emanation 109, passage_militants 64.
- Aucun n'est accepté automatiquement : mettre decision = oui sur les bons.

## 0.3 Liens manuels
- data/manuel/aretes_manuelles.csv : en-têtes et 3 lignes à compléter (source obligatoire).

## 0.4 Recherche ailleurs
- 181 organisations encore sans candidat solide, dans data/sortie/liste_recherche.csv,
  avec des adresses de recherche (Maitron, marxists.org, site officiel, Wikipédia, Wikidata).
  Rien n'a été téléchargé sur ces sites.
