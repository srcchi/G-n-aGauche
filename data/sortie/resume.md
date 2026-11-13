# Phase 1 : résumé du nettoyage

## Nœuds
| | Nombre |
|---|---|
| Wikidata (noeuds.csv) | 1549 |
| Wikipédia (wp_noeuds.csv) | 524 |
| Après fusion par identifiant (+ corrections) | 1884 |
| **Graphe : organisations de gauche françaises datées** (organisations.csv) | **370** |
| Graphe, sans date de fondation (sans_date.csv) | 54 |
| Internationales et fédérations européennes gardées (internationales.csv) | 44 |
| Exclues (perimetre_exclu.csv) | 1341 |
| dont étrangères en voie externe | 7 |

Raisons d'exclusion : ni positionnement de gauche ni courant reconnu (819), hors de France (177), pas une organisation politique (journal, librairie, think tank...) (113), Internationale sans membre dans le graphe (82), pas une organisation politique (institution, organisme intergouvernemental, groupe parlementaire) (68), positionnement : extrême droite (13), idéologie hors périmètre : fascis (9), positionnement : centrisme (8), positionnement : droite (7), positionnement : centre droit (6), idéologie hors périmètre : monarchi (5), personne, pas organisation (5), positionnement : centrisme centre droit (4), idéologie hors périmètre : royalis (3), idéologie hors périmètre : anti-indépendantis (2), idéologie hors périmètre : social-national (2), positionnement : centre droit centrisme (2), positionnement : centre gauche centre droit centrisme (2), positionnement : droite centre droit (2), idéologie hors périmètre : Algérie française (1), idéologie hors périmètre : Anti-indépendantis (1), idéologie hors périmètre : national-socialis (1), idéologie hors périmètre : nationalisme intégral (1), idéologie hors périmètre : orléanis (1), positionnement : centre gauche Centre gauche | Centrisme (1), positionnement : centre gauche centre droit (1), positionnement : centre gauche centrisme Centrisme | centre gauche (1), positionnement : centrisme Centrisme politique en France | centre gauche | centre droit (1), positionnement : droite extrême droite extrême droite politique (1), positionnement : extrême droite anticommunisme national-conservatisme opposition à l'immigration euroscepticisme populisme de droite ultranationalisme (1), positionnement : ultradroite (1).

Familles : socialistes (81), radicaux (7), écologistes (24), communistes (36), trotskystes (35), maoïstes (37), anarchistes et libertaires (36), outre-mer (47), à classer (67).

Périmètre discutable, gardé mais signalé (colonne perimetre_douteux), à trancher à la main :
- aucun courant reconnu (34) : 2022 ou jamais, Allons enfants, Association des écrivains et artistes révolutionnaires, Bloc révolutionnaire insurrectionnel et féministe, Camarades, Catalan Workers' Left, Club des jacobins, Collectif Golem, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Conseil pour le maintien des occupations, Coordination des sans-abris, Fièr-e-s et révolutionnaires, Front universitaire antifasciste, Gauche révolutionnaire (1935-1938), Indulgents, Jeune Garde antifasciste, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche moderne, Le Discord insoumis, Les Nouveaux Démocrates, Ligue de la Jeune République, Maintenant le peuple, Mouvement du 11 mai, Mouvement jeune révolution, National Union of North African Muslims, Parti frontiste, Parti ouvrier et paysan, Rassemblement des gauches républicaines, Société des républicaines révolutionnaires, Union des clubs pour le renouveau de la gauche, Union des démocrates musulmans français, Union progressiste, Éducation Démocratie Dignité
- régionaliste sans courant de gauche reconnu : à vérifier (31) : A Cuncolta Naziunalista, Action régionaliste corse, Alliance nationaliste corse, Anaram Au Patac, Armée révolutionnaire bretonne, Breizh Europa, Core in Fronte, Corsica Libera, Corsica Nazione, Femu a Corsica, Groupe régionaliste breton, Mouvement Franche-Comté, Mouvement des jeunes bretons, Mouvement normand, Nissa Rebela, Occitanie País Nòstre, Parti autonomiste breton, Parti lorrain, Parti national breton, Parti national breton, Parti occitan, Partitu di a Nazione Corsa, Prouvènço Nacioun, Rassemblement du peuple franc-comtois, Régions et peuples solidaires, Sabaudia-MRS, Strollad ar Vro, Union du peuple alsacien, Union du peuple corse, Union régionaliste bretonne, conseil exécutif de Corse
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
| Après fusion des réciproques | 1780, dont 1035 de lignée |
| Hors périmètre : une extrémité exclue ou étrangère (liens_hors_perimetre.csv) | 1424 |
| Anomalies R1 et lignée parti / Internationale (anomalies.csv) | 13 |
| Extrémité sans date, non dessinables (liens_date_manquante.csv) | 14 |
| Filiations redondantes retirées par réduction transitive (reduction_transitive.csv) | 3 |
| **Liens du graphe (liens.csv)** | **150** |
| Affiliations à une Internationale (affiliations.csv) | 70 |
| Appartenances à une organisation française : coalition, fédération (appartenances_nationales.csv) | 72 |

Liens par relation : scission (80), fusion (34), renommage (31), filiation (5).
Les liens entre deux organisations fondées la même année (mois inconnus) sont dans anomalies.csv :
leur longueur sur l'axe du temps serait nulle (règle R1).

Causes probables des anomalies : type de relation erroné (6), date erronée ou trop imprécise (4), lien entre deux Internationales de sens contraire au temps (2), date erronée (1).

Dates : 102 fondations et 37 dissolutions avec un mois (lu dans l'infobox, seulement s'il accompagne l'année retenue).
11 organisations ont une autre année de fondation dans une autre source (colonne fondation_autres_sources).

Affiliations : toutes en date_certainty = unknown (les sources ne donnent pas la période d'adhésion).
Période recopiée : durée de vie du parti, bornée par celle de l'Internationale.

Sigles (data/manuel/sigles.csv) : 541 organisations, dont 68 avec un sigle ; 0 ajoutées à cette exécution.

## Liens validés à la main
- Candidats de la phase 0 acceptés (decision = oui) : 0
  (dont 0 ignorés car leur sens est « à vérifier »).
- Liens manuels (data/manuel/aretes_manuelles.csv) : 0 ajoutés,
  3 ignorés (source, type ou extrémité manquant).

## Types (data/manuel/types.csv)
parti_ou_organisation 424, coalition 45, satellite 15, groupe_arme 13, syndicat 2, etrangere 177, international_ou_federation_europeenne 126.
802 types saisis à la main, 0 lignes ajoutées au fichier.
Coalitions et satellites ne sont jamais des boîtes ; un satellite rattaché à un parent apparaît
dans la colonne organisations_liees de ce parent.

## Organisations actives
**Mode provisoire** : aucune ligne de data/manuel/actifs.csv n'a valide = oui. Une organisation compte comme active si le drapeau automatique le dit et qu'il existe au moins un indice d'activité récente. Dès qu'une ligne est validée, seules les lignes validées comptent.
- Actives retenues : 219.

## Élagage strict (R5)
- **Gardées : 133 organisations** (actives ayant un lien de lignée, et leurs ancêtres),
  dont 9 sans date.
- Élaguées (data/sortie/elagues.csv), par cause : isolee 252, etrangere 177, coalition 45, non_ancetre_d_une_active 26, satellite 15, groupe_arme 13, arbre_sans_organisation_active 13, syndicat 2.
- **Actives élaguées faute de lien (152)**, à relier à la main puis relancer :
  2022 ou jamais, Alliance des jeunes pour la révolution, Alliance libre des anarchistes de la région du Midi, Alliance ouvrière anarchiste, Allons enfants, Alternative démocratie socialisme, Armée révolutionnaire bretonne, Bloc républicain de gauche, Bloc révolutionnaire insurrectionnel et féministe, Breizh Europa, Cap sur l'avenir, Caraïbe Écologie Les Verts Guadeloupe, Collectif Golem, Collectif militant communiste, Colère et espoir, Combat ouvrier, Comité communiste des Bouches-du-Rhône, Comité communiste internationaliste, Comité de liaison des jeunes pour la révolution, Comité de suivi contre les violences sexistes et sexuelles de La France insoumise, Comité féminin populaire, Comité national pour l'unification du mouvement communiste en France, Comités populaires d'entraide et de solidarité, Communistes en lutte, Coordination des libertaires de l'Ain, Coordination féministe, Core in Fronte, Corse social-démocrate, Corsica Libera, Du Pain et des Roses, Dynamik unitaire Sud, Dynamique autochtone, Démocrates et progressistes, En commun, Endavant, Eusko Alkartasuna, Femu a Corsica, Fièr-e-s et révolutionnaires, Forces démocratiques de Guyane, French India Socialist Party, Front communiste révolutionnaire, Front prolétaire, Front révolutionnaire antifasciste de Provence, Front révolutionnaire antifasciste/anticapitaliste et populaire, Front uni de libération kanak, Front-Uni, Fédération de la Guyane du Parti socialiste, Fédération des comités de coordination indépendantistes, Fédération libertaire unitaire ouverte, Fédération nationale des élus socialistes et républicains, Fédération progressiste, Fédération socialiste de la Martinique, Féministes révolutionnaires, Gauche révolutionnaire, Gauche sociale et radicale, Groupe libertaire Jules Durand, Groupe révolution socialiste, Génération écologie, Here ai’a, Hoxhaïsme, Jeunes communistes marxistes-léninistes d'Albi, Jeunes pour la renaissance communiste en France, Jeunesse Révolution, Jeunesse communiste marxiste-léniniste, Jeunesses communistes marxistes-léninistes de Pau, Juives et Juifs révolutionnaires, La France Républicaine et Solidaire, La Gauche populaire, La gauche conflanaise, Conflans pour tous, Le Discord insoumis, Les Radicaux de gauche, Les amis de Karl Marx, Ligue communiste révolutionnaire (Bangladesh), Ligue trotskyste de France, Liste de gauche - conflans ste honorine 2001, Mahe Socialist Party, Maintenant le peuple, Marxist–Leninist Communist Organisation of Réunion, Mouvement Franche-Comté, Mouvement des démocrates et écologistes pour une Martinique souveraine, Mouvement des jeunes bretons, Mouvement normand, Mouvement populaire des femmes, Mouvement pour la démocratie en Europe : Diem 25, Mouvement révolutionnaire de la jeunesse, Mouvement écologiste indépendant, Nouveau communisme en France, Nouvel élan pour Mayotte, Nouvelle Gauche socialiste, Nouvelle Écologie démocrate, Occitanie País Nòstre, Organisation des communistes de France, Orléans Solidaire Écologique, Paolistes, Parti communiste internationaliste du Japon, Parti de la nation occitane, Parti de libération kanak, Parti lorrain, Parti national breton, Parti occitan, Parti pirate, Parti radical (France), Parti régionaliste martiniquais, Parti travailliste, Partitu di a Nazione Corsa, Place publique (parti politique), Plateformisme, Post-Soviet Left, Pour la Bretagne !, Pour une écologie populaire et sociale, Prouvènço Nacioun, Rassemblement du peuple franc-comtois, Rassemblement démocratique martiniquais, Rassemblement démocratique océanien, Reconstruction communiste, Régions et peuples solidaires, République et socialisme, Révolution écologique pour le vivant, Rézistan's Égalité 974, Sabaudia-MRS, Section universitaire du Parti socialiste, Socialisme et démocratie, Socialist Movement, Sortu, Tendance CLAIRE, Territoires44, Treger Disuj, UDB Jeunes, Un monde d'avance, Union calédonienne, Union des centristes et des écologistes, Union des démocrates musulmans français, Union des jeunes révolutionnaires, Union des républicains radicaux, Union nationale pour l'indépendance, Union pour un destin calédonien, Unir et Construire dans le Renouveau, Unité communiste, Unité internationale des travailleurs - Quatrième Internationale, Walwari, War-Sav – Gauche indépendantiste bretonne, Zone à défendre, conseil exécutif de Corse, fédération de Loir-et-Cher du Parti socialiste, fédération des Français à l’étranger du Parti socialiste, fédération des Hauts-de-Seine du Parti socialiste, fédération des Yvelines du Parti socialiste, fédération du Doubs du Parti socialiste, lutte ouvriere faire entendre le camp des travailleurs, À gauche en Guyane, Écologie Solidarité, Égalités.

## Affiliations
- 70 affiliations sans dates connues : data/sortie/affiliations_a_dater.csv ;
  à compléter dans data/manuel/affiliations_dates.csv (source obligatoire).
