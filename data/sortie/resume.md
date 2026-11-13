# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 1549 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 1884 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **416** |
| Graphe, sans date de fondation (sans_date.csv) | 86 |
| Internationales et fédérations européennes gardées (internationales.csv) | 46 |
| Exclues (perimetre_exclu.csv) | 1336 |
| dont étrangères en voie externe | 7 |

Raisons d'exclusion : ni positionnement de gauche ni courant reconnu (819), hors de France (174), pas une organisation politique (journal, librairie, think tank...) (113), Internationale sans membre dans le graphe (80), pas une organisation politique (institution, organisme intergouvernemental, groupe parlementaire) (68), positionnement : extrême droite (13), idéologie hors périmètre : fascis (9), positionnement : centrisme (8), positionnement : droite (7), positionnement : centre droit (6), idéologie hors périmètre : monarchi (5), personne, pas organisation (5), positionnement : centrisme centre droit (4), idéologie hors périmètre : royalis (3), idéologie hors périmètre : anti-indépendantis (2), idéologie hors périmètre : social-national (2), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : droite centre droit (2), idéologie hors périmètre : Algérie française (1), idéologie hors périmètre : Anti-indépendantis (1), idéologie hors périmètre : national-socialis (1), idéologie hors périmètre : nationalisme intégral (1), idéologie hors périmètre : orléanis (1), positionnement : centre gauche Centre gauche | Centrisme (1), positionnement : centre gauche centre droit (1), positionnement : centre gauche centrisme Centrisme | centre gauche (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : droite extrême droite extrême droite politique (1), positionnement : extrême droite anticommunisme national-conservatisme opposition à l'immigration euroscepticisme populisme de droite ultranationalisme (1), positionnement : ultradroite (1).

Familles : socialistes (87), radicaux (8), écologistes (30), communistes (44), trotskystes (38), maoïstes (41), anarchistes et libertaires (43), outre-mer (40), non classé (85).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (44) : 2022 ou jamais, Allons enfants, Association des écrivains et artistes révolutionnaires, Bataillon international de libération, Bloc révolutionnaire insurrectionnel et féministe, Camarades, Cap sur l'avenir, Cartel des gauches, Catalan Workers' Left, Club des jacobins, Collectif Golem, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Conseil pour le maintien des occupations, Coordination des sans-abris, Dynamik unitaire Sud, Fièr-e-s et révolutionnaires, Fraction nationaliste armée révolutionnaire, Front universitaire antifasciste, Fédération de la gauche républicaine, Gauche révolutionnaire (1935-1938), Indulgents, Jeune Garde antifasciste, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche moderne, Le Discord insoumis, Les Nouveaux Démocrates, Ligue de la Jeune République, Maintenant le peuple, Mouvement du 11 mai, Mouvement jeune révolution, National Union of North African Muslims, Parti frontiste, Parti ouvrier et paysan, Rassemblement des gauches républicaines, Rassemblement démocratique océanien, Société des républicaines révolutionnaires, Union des clubs pour le renouveau de la gauche, Union des démocrates musulmans français, Union progressiste, Unir et Construire dans le Renouveau, bloc des gauches, groupe Gauche démocrate et républicaine, Éducation Démocratie Dignité
- régionaliste sans courant de gauche reconnu : à vérifier (38) : A Cuncolta Naziunalista, Action régionaliste corse, Alliance nationaliste corse, Anaram Au Patac, Armée révolutionnaire bretonne, Breizh Europa, Core in Fronte, Corsica Libera, Corsica Nazione, Femu a Corsica, Front de libération de la Bretagne, Front de libération nationale corse, Fédération des comités de coordination indépendantistes, Groupe régionaliste breton, Here ai’a, Mouvement Franche-Comté, Mouvement des jeunes bretons, Mouvement normand, Nissa Rebela, Occitanie País Nòstre, Parti autonomiste breton, Parti lorrain, Parti national breton, Parti national breton, Parti occitan, Parti travailliste, Partitu di a Nazione Corsa, Prouvènço Nacioun, Pè a Corsica, Péyi-A, Rassemblement du peuple franc-comtois, Régions et peuples solidaires, Sabaudia-MRS, Strollad ar Vro, Union du peuple alsacien, Union du peuple corse, Union régionaliste bretonne, conseil exécutif de Corse
- plusieurs pays dans Wikidata (11) : Batasuna, Endavant, Euskadi ta Askatasuna, Eusko Alkartasuna, Fédération anarchiste (francophone), Paolistes, Post-Soviet Left, Socialist Youth Coordinator, Sortu, Terra Lliure, Union nationale espagnole
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
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 1398 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 15 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 27 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 3 |
| **Liens du graphe (liens.csv)** | **156** |
| Affiliations à une Internationale (affiliations.csv) | 73 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 77 |

Liens par relation : scission (80), fusion (40), renommage (31), filiation (5).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : type de relation erroné (7), date erronée ou trop imprécise (5), lien entre deux Internationales de sens contraire au temps (2), date erronée (1).

Dates : 60 fondations et 26 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
13 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 541 organisations, dont 68 avec un sigle ; 0 ajoutées à cette exécution.
