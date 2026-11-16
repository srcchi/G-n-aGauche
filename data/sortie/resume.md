# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 1007 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 1358 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **377** |
| Graphe, sans date de fondation (sans_date.csv) | 59 |
| Internationales et fédérations européennes gardées (internationales.csv) | 41 |
| Exclues (perimetre_exclu.csv) | 810 |
| dont étrangères en voie externe | 7 |

Raisons d'exclusion : ni positionnement de gauche ni courant reconnu (384), hors de France (174), pas une organisation politique (institution, organisme intergouvernemental, groupe parlementaire) (41), Internationale sans membre dans le graphe (27), porte politique : entité territoriale administrative, région historique, zone géographique, État historique (27), porte politique : organisation à but non lucratif, sans type politique (25), pas une organisation politique (journal, librairie, think tank...) (24), porte politique : organisation intergouvernementale (13), positionnement : extrême droite (12), idéologie hors périmètre : fascis (8), positionnement : centrisme (8), porte politique : entité territoriale administrative, zone géographique (7), positionnement : droite (7), porte politique : syndicat (6), positionnement : centre droit (6), porte politique : personne (4), positionnement : centrisme centre droit (4), idéologie hors périmètre : monarchi (3), idéologie hors périmètre : royalis (3), idéologie hors périmètre : anti-indépendantis (2), idéologie hors périmètre : social-national (2), porte politique : organisation internationale, organisation à but non lucratif, sans type politique (2), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : droite centre droit (2), hors périmètre (centre) : centre gauche à centre (1), hors périmètre (centre) : centre gauche à centre (article de l'UDE) (1), idéologie hors périmètre : Algérie française (1), idéologie hors périmètre : Anti-indépendantis (1), idéologie hors périmètre : national-socialis (1), idéologie hors périmètre : orléanis (1), porte politique : base de données (1), porte politique : entité territoriale administrative, organisation intergouvernementale, zone géographique (1), porte politique : entité territoriale administrative, pays, zone géographique (1), porte politique : entité territoriale administrative, région historique, zone géographique (1), porte politique : zone géographique (1), positionnement : centre gauche centre droit (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : droite extrême droite extrême droite politique (1), positionnement : extrême droite anticommunisme national-conservatisme opposition à l'immigration euroscepticisme populisme de droite ultranationalisme (1).

Familles : socialistes (93), radicaux (8), écologistes (26), communistes (46), trotskystes (42), maoïstes (38), anarchistes et libertaires (39), à classer (84).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (40) : 2022 ou jamais, Allons enfants, Association des écrivains et artistes révolutionnaires, Bloc révolutionnaire insurrectionnel et féministe, Camarades, Cap sur l'avenir, Catalan Workers' Left, Club des jacobins, Collectif Golem, Conseil pour le maintien des occupations, Coordination des sans-abris, Dynamik unitaire Sud, Fièr-e-s et révolutionnaires, Front universitaire antifasciste, Gauche révolutionnaire (1935-1938), Indulgents, Jeune Garde antifasciste, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche moderne, Le Discord insoumis, Les Nouveaux Démocrates, Ligue de la Jeune République, Maintenant le peuple, Mouvement du 11 mai, Mouvement jeune révolution, National Union of North African Muslims, Nouvel élan pour Mayotte, Nouvelle force de Guyane, Parti frontiste, Parti ouvrier et paysan, Rassemblement des gauches républicaines, Rassemblement démocratique océanien, Société des républicaines révolutionnaires, Union des clubs pour le renouveau de la gauche, Union des démocrates musulmans français, Union progressiste, Unir et Construire dans le Renouveau, À gauche en Guyane, Éducation Démocratie Dignité
- régionaliste sans courant de gauche reconnu : à vérifier (42) : A Cuncolta Naziunalista, Action régionaliste corse, Alliance nationaliste corse, Anaram Au Patac, Armée révolutionnaire bretonne, Breizh Europa, Core in Fronte, Corsica Libera, Corsica Nazione, Femu a Corsica, Forces démocratiques de Guyane, Front uni de libération kanak, Fédération des comités de coordination indépendantistes, Groupe régionaliste breton, Here ai’a, Mouvement Franche-Comté, Mouvement des jeunes bretons, Mouvement indépendantiste martiniquais, Mouvement normand, Nissa Rebela, Occitanie País Nòstre, Parti autonomiste breton, Parti lorrain, Parti national breton, Parti national breton, Parti occitan, Parti régionaliste martiniquais, Parti travailliste, Partitu di a Nazione Corsa, Prouvènço Nacioun, Péyi-A, Rassemblement du peuple franc-comtois, Rassemblement démocratique martiniquais, Régions et peuples solidaires, Sabaudia-MRS, Strollad ar Vro, Union du peuple alsacien, Union du peuple corse, Union du peuple guyanais, Union pour un destin calédonien, Union régionaliste bretonne, conseil exécutif de Corse
- plusieurs pays dans Wikidata (8) : Batasuna, Endavant, Eusko Alkartasuna, Fédération anarchiste (francophone), Paolistes, Post-Soviet Left, Sortu, Union nationale espagnole
- radicaux : gauche ou centre ? (2) : Parti radical (France), Parti républicain, radical et radical-socialiste

## Arêtes
| Étape | Nombre |
|---|---|
| Wikidata (aretes.csv) | 563 |
| Wikipédia (wp_aretes.csv) | 520 |
| Boucles (une organisation vers elle-même) retirées | 0 |
| Après fusion par (ancêtre, descendant) | 965 |
| Corrections manuelles : ajouts / suppressions | 7 / 0 |
| Paires réciproques fusionnées (aretes_reciproques.csv) | 13 |
| Après fusion des réciproques | 981, dont 644 de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 615 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 7 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 21 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 1 |
| **Liens du graphe (liens.csv)** | **163** |
| Affiliations à une Internationale (affiliations.csv) | 68 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 71 |

Liens par relation : scission (72), renommage (43), fusion (27), composante (8), absorption (4), filiation_idéologique (3), passage (3), refondation (2), indirect (1).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : date erronée ou trop imprécise (3), type de relation erroné (3), lien entre deux Internationales de sens contraire au temps (1).

Dates : 102 fondations et 39 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
14 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 556 organisations, dont 130 avec un sigle ; 0 ajoutées à cette exécution.

## Liens validés à la main
- Candidats de la phase 0 acceptés (decision = oui) : 0
  (dont 0 ignorés car leur sens est « à vérifier »).
- Liens manuels (data/manuel/aretes_manuelles.csv) : 29 ajoutés,
  1 ignorés (source, type ou extrémité manquant).

## Types (data/manuel/types.csv)
parti 420, coalition 35, satellite 36, internationale 68, fondatrice 16, étrangère 174.
2 types saisis à la main, 0 lignes ajoutées au fichier.
Coalitions et satellites ne sont jamais des boîtes ; un satellite rattaché à un parent apparaît
dans la colonne organisations_liees de ce parent.

## Organisations actives
109 organisations validées actives, 26 refusées.
- Actives retenues : 61.

## Élagage strict (R5)
- **Gardées : 105 organisations** (actives ayant un lien de lignée, et leurs ancêtres),
  dont 0 sans date.
- Élaguées (data/sortie/elagues.csv), par cause : etrangere 174, a_dater 166, hors_perimetre 63, isolee 57, satellite 36, coalition 35, famille_non_determinee 23, non_ancetre_d_une_active 19, rejet_porte 3.
- **Actives élaguées faute de lien (6)**, à relier à la main puis relancer :
  Démocrates et progressistes, Féministes révolutionnaires, Gauche révolutionnaire, Mouvement écologiste indépendant, Union des centristes et des écologistes, groupe socialiste à l'Assemblée nationale.

## Affiliations
- 51 affiliations sans dates connues : data/sortie/affiliations_a_dater.csv ;
  à compléter dans data/manuel/affiliations_dates.csv (source obligatoire).
