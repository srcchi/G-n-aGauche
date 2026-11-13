# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 605 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 953 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **379** |
| Graphe, sans date de fondation (sans_date.csv) | 86 |
| Internationales et fédérations européennes gardées (internationales.csv) | 44 |
| Exclues (perimetre_exclu.csv) | 444 |
| dont étrangères en voie externe | 8 |

Raisons d'exclusion : hors de France (175), ni positionnement de gauche ni courant reconnu (143), pas une organisation politique (journal, librairie, think tank...) (86), Internationale sans membre dans le graphe (18), personne, pas organisation (4), positionnement : centrisme (4), positionnement : centre droit (2), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : centre gauche Centre gauche | Centrisme (1), positionnement : centre gauche centre droit (1), positionnement : centre gauche centrisme Centrisme | centre gauche (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : centrisme centre droit (1), positionnement : droite (1), positionnement : extrême droite (1), positionnement : ultradroite (1).

Familles : socialistes (90), radicaux (8), écologistes (19), communistes (47), trotskystes (38), maoïstes (41), anarchistes et libertaires (43), outre-mer (32), non classé (61).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (59) : 2022 ou jamais, Allons enfants, Armée révolutionnaire bretonne, Association des écrivains et artistes révolutionnaires, Bataillon international de libération, Bloc révolutionnaire insurrectionnel et féministe, Camarades, Cap sur l'avenir, Cartel des gauches, Catalan Workers' Left, Club des jacobins, Collectif Golem, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Confédération internationale du travail, Conseil pour le maintien des occupations, Coordination des sans-abris, Core in Fronte, Dynamik unitaire Sud, Fièr-e-s et révolutionnaires, Fraction nationaliste armée révolutionnaire, Front de libération de la Bretagne, Front de libération nationale corse, Front universitaire antifasciste, Fédération de la gauche républicaine, Fédération des comités de coordination indépendantistes, Fédération des gauches, Gauche constitutionnelle, Gauche révolutionnaire (1935-1938), Indulgents, Jeune Garde antifasciste, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche moderne, Le Discord insoumis, Les Nouveaux Démocrates, Libéraux, Ligue de la Jeune République, Maintenant le peuple, Mouvement du 11 mai, Mouvement jeune révolution, Mouvement ouvrier social-national breton, Mouvement social révolutionnaire, National Union of North African Muslims, Nouvelle Action royaliste, Parti frontiste, Parti ouvrier et paysan, Parti travailliste, Péyi-A, Rassemblement des gauches républicaines, Rassemblement démocratique océanien, Société des républicaines révolutionnaires, Union des clubs pour le renouveau de la gauche, Union des démocrates musulmans français, Union progressiste, Unir et Construire dans le Renouveau, bloc des gauches, groupe Gauche démocrate et républicaine, montagnards, Éducation Démocratie Dignité
- plusieurs pays dans Wikidata (9) : Batasuna, Endavant, Euskadi ta Askatasuna, Fédération anarchiste (francophone), Post-Soviet Left, Socialist Youth Coordinator, Sortu, Terra Lliure, Union nationale espagnole
- radicaux : gauche ou centre ? (2) : Parti radical (France), Parti républicain, radical et radical-socialiste

## Arêtes
| Étape | Nombre |
|---|---|
| Wikidata (aretes.csv) | 330 |
| Wikipédia (wp_aretes.csv) | 520 |
| Boucles (une organisation vers elle-même) retirées | 0 |
| Après fusion par (ancêtre, descendant) | 734 |
| Corrections manuelles : ajouts / suppressions | 7 / 0 |
| Paires réciproques fusionnées (aretes_reciproques.csv) | 14 |
| Après fusion des réciproques | 727, dont 328 de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 366 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 16 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 29 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 3 |
| **Liens du graphe (liens.csv)** | **154** |
| Affiliations à une Internationale (affiliations.csv) | 66 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 76 |

Liens par relation : scission (79), fusion (40), renommage (30), filiation (5).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : type de relation erroné (9), date erronée ou trop imprécise (5), date erronée (1), lien entre deux Internationales de sens contraire au temps (1).

Dates : 60 fondations et 26 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
13 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 471 organisations, dont 68 avec un sigle ; 207 ajoutées à cette exécution.
