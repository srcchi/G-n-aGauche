# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 1549 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 1884 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **445** |
| Graphe, sans date de fondation (sans_date.csv) | 96 |
| Internationales et fédérations européennes gardées (internationales.csv) | 47 |
| Exclues (perimetre_exclu.csv) | 1296 |
| dont étrangères en voie externe | 8 |

Raisons d'exclusion : ni positionnement de gauche ni courant reconnu (851), hors de France (187), pas une organisation politique (journal, librairie, think tank...) (113), Internationale sans membre dans le graphe (79), positionnement : extrême droite (21), positionnement : centrisme (9), positionnement : centre droit (7), positionnement : droite (7), personne, pas organisation (5), positionnement : centrisme centre droit (4), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : droite centre droit (2), positionnement : centre gauche Centre gauche | Centrisme (1), positionnement : centre gauche centre droit (1), positionnement : centre gauche centrisme Centrisme | centre gauche (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : droite extrême droite extrême droite politique (1), positionnement : extrême droite anticommunisme national-conservatisme opposition à l'immigration euroscepticisme populisme de droite ultranationalisme (1), positionnement : ultradroite (1).

Familles : socialistes (93), radicaux (8), écologistes (32), communistes (47), trotskystes (38), maoïstes (41), anarchistes et libertaires (43), outre-mer (41), non classé (102).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (98) : 2022 ou jamais, A Cuncolta Naziunalista, Action régionaliste corse, Agence internationale de l'énergie, Alliance nationaliste corse, Allons enfants, Anaram Au Patac, Armée révolutionnaire bretonne, Association des écrivains et artistes révolutionnaires, Autorité internationale de la Ruhr, Bataillon international de libération, Bloc révolutionnaire insurrectionnel et féministe, Breizh Europa, Camarades, Cap sur l'avenir, Cartel des gauches, Catalan Workers' Left, Club des jacobins, Collectif Golem, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Confédération internationale du travail, Conseil pour le maintien des occupations, Coordination des sans-abris, Core in Fronte, Corsica Libera, Corsica Nazione, Direction générale des relations internationales et de la stratégie, Dynamik unitaire Sud, Femu a Corsica, Fièr-e-s et révolutionnaires, Fraction nationaliste armée révolutionnaire, Front Algérie française, Front de libération de la Bretagne, Front de libération nationale corse, Front national, Front universitaire antifasciste, Fédération de la gauche républicaine, Fédération des comités de coordination indépendantistes, Fédération des gauches, Gauche constitutionnelle, Gauche révolutionnaire (1935-1938), Groupe arc-en-ciel, Groupe régionaliste breton, Here ai’a, Indulgents, Jeune Garde antifasciste, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche moderne, Le Discord insoumis, Les Nouveaux Démocrates, Libéraux, Ligue de la Jeune République, Maintenant le peuple, Mouvement Franche-Comté, Mouvement des jeunes bretons, Mouvement du 11 mai, Mouvement jeune révolution, Mouvement normand, Mouvement ouvrier social-national breton, Mouvement social révolutionnaire, National Union of North African Muslims, Nissa Rebela, Nouvelle Action royaliste, Occitanie País Nòstre, Organisation internationale de la francophonie, Organisation internationale de la vigne et du vin, Parti autonomiste breton, Parti frontiste, Parti lorrain, Parti national breton, Parti national breton, Parti occitan, Parti ouvrier et paysan, Parti travailliste, Partitu di a Nazione Corsa, Prouvènço Nacioun, Pè a Corsica, Péyi-A, Rassemblement des gauches républicaines, Rassemblement du peuple franc-comtois, Rassemblement démocratique océanien, Régions et peuples solidaires, Sabaudia-MRS, Société des républicaines révolutionnaires, Strollad ar Vro, Union des clubs pour le renouveau de la gauche, Union des démocrates musulmans français, Union du peuple alsacien, Union du peuple corse, Union progressiste, Union régionaliste bretonne, Unir et Construire dans le Renouveau, bloc des gauches, conseil exécutif de Corse, groupe Gauche démocrate et républicaine, montagnards, Éducation Démocratie Dignité
- plusieurs pays dans Wikidata (12) : Batasuna, Endavant, Euskadi ta Askatasuna, Eusko Alkartasuna, Fédération anarchiste (francophone), Paolistes, Post-Soviet Left, Socialist Youth Coordinator, Sortu, Terra Lliure, Union nationale espagnole, Zone internationale de Tanger
- radicaux : gauche ou centre ? (2) : Parti radical (France), Parti républicain, radical et radical-socialiste

## Arêtes
| Étape | Nombre |
|---|---|
| Wikidata (aretes.csv) | 1410 |
| Wikipédia (wp_aretes.csv) | 520 |
| Boucles (une organisation vers elle-même) retirées | 0 |
| Après fusion par (ancêtre, descendant) | 1812 |
| Corrections manuelles : ajouts / suppressions | 7 / 0 |
| Paires réciproques fusionnées (aretes_reciproques.csv) | 39 |
| Après fusion des réciproques | 1780, dont 1035 de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 1387 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 19 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 29 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 3 |
| **Liens du graphe (liens.csv)** | **157** |
| Affiliations à une Internationale (affiliations.csv) | 76 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 78 |

Liens par relation : scission (80), fusion (40), renommage (32), filiation (5).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : type de relation erroné (11), date erronée ou trop imprécise (5), lien entre deux Internationales de sens contraire au temps (2), date erronée (1).

Dates : 60 fondations et 26 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
13 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 541 organisations, dont 68 avec un sigle ; 70 ajoutées à cette exécution.
