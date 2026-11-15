# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 1549 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 1898 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **392** |
| Graphe, sans date de fondation (sans_date.csv) | 61 |
| Internationales et fédérations européennes gardées (internationales.csv) | 39 |
| Exclues (perimetre_exclu.csv) | 1345 |
| dont étrangères en voie externe | 7 |

Raisons d'exclusion : ni positionnement de gauche ni courant reconnu (819), hors de France (177), pas une organisation politique (journal, librairie, think tank...) (113), Internationale sans membre dans le graphe (88), pas une organisation politique (institution, organisme intergouvernemental, groupe parlementaire) (68), positionnement : extrême droite (13), idéologie hors périmètre : fascis (9), positionnement : centrisme (8), positionnement : droite (7), positionnement : centre droit (6), idéologie hors périmètre : monarchi (5), personne, pas organisation (5), positionnement : centrisme centre droit (4), idéologie hors périmètre : royalis (3), idéologie hors périmètre : anti-indépendantis (2), idéologie hors périmètre : orléanis (2), idéologie hors périmètre : social-national (2), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : droite centre droit (2), idéologie hors périmètre : Algérie française (1), idéologie hors périmètre : Anti-indépendantis (1), idéologie hors périmètre : national-socialis (1), positionnement : centre gauche centre droit (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : droite extrême droite extrême droite politique (1), positionnement : extrême droite anticommunisme national-conservatisme opposition à l'immigration euroscepticisme populisme de droite ultranationalisme (1), positionnement : ultradroite (1).

Familles : socialistes (102), radicaux (8), écologistes (29), communistes (46), trotskystes (45), maoïstes (38), anarchistes et libertaires (39), à classer (85).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (41) : 2022 ou jamais, Allons enfants, Association des écrivains et artistes révolutionnaires, Bloc révolutionnaire insurrectionnel et féministe, Camarades, Cap sur l'avenir, Catalan Workers' Left, Club des jacobins, Collectif Golem, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Conseil pour le maintien des occupations, Coordination des sans-abris, Dynamik unitaire Sud, Fièr-e-s et révolutionnaires, Front universitaire antifasciste, Gauche révolutionnaire (1935-1938), Indulgents, Jeune Garde antifasciste, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche moderne, Le Discord insoumis, Les Nouveaux Démocrates, Ligue de la Jeune République, Maintenant le peuple, Mouvement du 11 mai, Mouvement jeune révolution, National Union of North African Muslims, Nouvel élan pour Mayotte, Nouvelle force de Guyane, Parti frontiste, Parti ouvrier et paysan, Rassemblement des gauches républicaines, Rassemblement démocratique océanien, Société des républicaines révolutionnaires, Union des clubs pour le renouveau de la gauche, Union des démocrates musulmans français, Union progressiste, Unir et Construire dans le Renouveau, À gauche en Guyane, Éducation Démocratie Dignité
- régionaliste sans courant de gauche reconnu : à vérifier (42) : A Cuncolta Naziunalista, Action régionaliste corse, Alliance nationaliste corse, Anaram Au Patac, Armée révolutionnaire bretonne, Breizh Europa, Core in Fronte, Corsica Libera, Corsica Nazione, Femu a Corsica, Forces démocratiques de Guyane, Front uni de libération kanak, Fédération des comités de coordination indépendantistes, Groupe régionaliste breton, Here ai’a, Mouvement Franche-Comté, Mouvement des jeunes bretons, Mouvement indépendantiste martiniquais, Mouvement normand, Nissa Rebela, Occitanie País Nòstre, Parti autonomiste breton, Parti lorrain, Parti national breton, Parti national breton, Parti occitan, Parti régionaliste martiniquais, Parti travailliste, Partitu di a Nazione Corsa, Prouvènço Nacioun, Péyi-A, Rassemblement du peuple franc-comtois, Rassemblement démocratique martiniquais, Régions et peuples solidaires, Sabaudia-MRS, Strollad ar Vro, Union du peuple alsacien, Union du peuple corse, Union du peuple guyanais, Union pour un destin calédonien, Union régionaliste bretonne, conseil exécutif de Corse
- plusieurs pays dans Wikidata (8) : Batasuna, Endavant, Eusko Alkartasuna, Fédération anarchiste (francophone), Paolistes, Post-Soviet Left, Sortu, Union nationale espagnole
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
| Après fusion des réciproques | 1800, dont 1053 de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 1408 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 8 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 21 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 1 |
| **Liens du graphe (liens.csv)** | **166** |
| Affiliations à une Internationale (affiliations.csv) | 74 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 73 |

Liens par relation : scission (75), renommage (42), fusion (29), composante (8), absorption (4), filiation_idéologique (3), passage (3), indirect (1), refondation (1).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : date erronée ou trop imprécise (3), type de relation erroné (3), lien entre deux Internationales de sens contraire au temps (2).

Dates : 104 fondations et 38 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
14 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 556 organisations, dont 82 avec un sigle ; 0 ajoutées à cette exécution.

## Liens validés à la main
- Candidats de la phase 0 acceptés (decision = oui) : 0
  (dont 0 ignorés car leur sens est « à vérifier »).
- Liens manuels (data/manuel/aretes_manuelles.csv) : 25 ajoutés,
  1 ignorés (source, type ou extrémité manquant).

## Types (data/manuel/types.csv)
parti 439, coalition 35, satellite 26, internationale 127, fondatrice 14, étrangère 177.
0 types saisis à la main, 0 lignes ajoutées au fichier.
Coalitions et satellites ne sont jamais des boîtes ; un satellite rattaché à un parent apparaît
dans la colonne organisations_liees de ce parent.

## Organisations actives
108 organisations validées actives, 22 refusées.
- Actives retenues : 71.

## Élagage strict (R5)
- **Gardées : 102 organisations** (actives ayant un lien de lignée, et leurs ancêtres),
  dont 0 sans date.
- Élaguées (data/sortie/elagues.csv), par cause : etrangere 177, a_dater 170, isolee 94, famille_non_determinee 54, coalition 35, satellite 26, non_ancetre_d_une_active 19, hors_perimetre 7, rejet_porte 4, arbre_sans_organisation_active 3.
- **Actives élaguées faute de lien (29)**, à relier à la main puis relancer :
  Combat ouvrier, Du Pain et des Roses, Démocrates et progressistes, Endavant, Eusko Alkartasuna, Fédération de la Guyane du Parti socialiste, Féministes révolutionnaires, Groupe révolution socialiste, Génération écologie, Mouvement des démocrates et écologistes pour une Martinique souveraine, Mouvement écologiste indépendant, Parti de la nation occitane, Parti de libération kanak, Parti pirate, Place publique (parti politique), Pour la Bretagne !, Rézistan's Égalité 974, UDB Jeunes, Un monde d'avance, Union calédonienne, Union des centristes et des écologistes, Unité internationale des travailleurs - Quatrième Internationale, Walwari, War-Sav – Gauche indépendantiste bretonne, fédération des Français à l’étranger du Parti socialiste, fédération des Hauts-de-Seine du Parti socialiste, fédération des Yvelines du Parti socialiste, fédération du Doubs du Parti socialiste, groupe socialiste à l'Assemblée nationale.

## Affiliations
- 57 affiliations sans dates connues : data/sortie/affiliations_a_dater.csv ;
  à compléter dans data/manuel/affiliations_dates.csv (source obligatoire).
