# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 276 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 702 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **239** |
| Graphe, sans date de fondation (sans_date.csv) | 25 |
| Internationales et fédérations européennes gardées (internationales.csv) | 36 |
| Exclues (perimetre_exclu.csv) | 402 |
| dont étrangères en voie externe | 5 |

Raisons d'exclusion : hors de France (152), ni positionnement de gauche ni courant reconnu (117), pas une organisation politique (journal, librairie, think tank...) (47), Internationale sans membre dans le graphe (27), positionnement : extrême droite (19), positionnement : centrisme (11), positionnement : droite (6), positionnement : centre droit (5), personne, pas organisation (4), positionnement : centrisme centre droit (3), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : droite centre droit (2), positionnement : centre gauche Centre gauche | Centrisme (1), positionnement : centre gauche centrisme Centrisme | centre gauche (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : droite extrême droite (1), positionnement : droite extrême droite extrême droite politique (1).

Familles : socialistes (68), radicaux (3), écologistes (14), communistes (25), trotskystes (30), maoïstes (17), anarchistes et libertaires (28), outre-mer (24), non classé (30).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (29) : Bataillon international de libération, Cartel des gauches, Club des jacobins, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Confédération internationale du travail, En commun, Front de gauche (France), Front de libération de la Bretagne, Front de libération nationale corse, Front populaire (France), Front universitaire antifasciste, Gauche révolutionnaire (1935-1938), Groupe régionaliste breton, Jeune Garde antifasciste, La Gauche moderne, Le Discord insoumis, Ligue de la Jeune République, Maintenant le peuple, Mouvement du 11 mai, National Union of North African Muslims, Nouveau Front populaire, Nouvelle Donne (parti politique), Parti autonomiste breton, Parti occitan, Parti ouvrier et paysan, Péyi-A, Rassemblement des gauches républicaines, Union des clubs pour le renouveau de la gauche, Éducation Démocratie Dignité
- plusieurs pays dans Wikidata (2) : Fédération anarchiste (francophone), Terra Lliure
- radicaux : gauche ou centre ? (2) : Parti radical (France), Parti républicain, radical et radical-socialiste

## Arêtes
| Étape | Nombre |
|---|---|
| Wikidata (aretes.csv) | 166 |
| Wikipédia (wp_aretes.csv) | 520 |
| Boucles (une organisation vers elle-même) retirées | 0 |
| Après fusion par (ancêtre, descendant) | 575 |
| Corrections manuelles : ajouts / suppressions | 7 / 0 |
| Paires réciproques fusionnées (aretes_reciproques.csv) | 10 |
| Après fusion des réciproques | 572, dont 276 de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 281 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 15 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 10 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 2 |
| **Liens du graphe (liens.csv)** | **135** |
| Affiliations à une Internationale (affiliations.csv) | 62 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 66 |

Liens par relation : scission (67), fusion (36), renommage (29), filiation (3).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : type de relation erroné (5), lien entre deux Internationales de type scission, non représenté (5), date erronée ou trop imprécise (4), date erronée (1).

Dates : 59 fondations et 26 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
13 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 264 organisations, dont 65 avec un sigle ; 0 ajoutées à cette exécution.
