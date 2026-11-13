# Critères de répartition des nœuds (phase 1)

Chaque organisation (fusion de Wikidata, Wikipédia et des corrections manuelles, par identifiant)
est rangée dans un seul ensemble, dans cet ordre :

1. **Corrections manuelles** (data/corrections_noeuds.csv) : `exclure` -> exclue ;
   `inclure`, `vivant`, `disparu` -> graphe, sans autre test.
2. **Personne** (type Wikidata Q5) -> exclue.
3. **Internationale ou fédération européenne** -> internationales.csv, jamais un nœud du graphe.
   Critère : un type Wikidata d'organisation internationale (Q2716508, Q484652, Q24649, Q1194093),
   ou un nom qui commence par « Internationale », « Quatrième Internationale », « Comité
   international », « Comité pour une Internationale », « Ligue internationale », « Conférence
   internationale »..., qui finit par « – Quatrième Internationale » ou par « européen(ne) »,
   ou qui est un parti européen (PSE, PGE, PVE, ALE...).
   Seules sont gardées celles dont une organisation du graphe est membre, et leurs prédécesseurs.
   Les autres vont dans perimetre_exclu.csv.
4. **Pas une organisation politique** : type Wikidata de journal, librairie, think tank, syndicat...
   sans type de parti ou d'organisation politique -> exclue.
5. **Pas de gauche** : positionnement (Wikidata ou infobox) de droite ou du centre, ou ni
   positionnement de gauche, ni courant reconnu dans le nom ou les idéologies -> exclue.
6. **Étrangère** -> perimetre_exclu.csv (raison « hors de France »). Critère : pays Wikidata
   (P17) autre que la France ; à défaut, un pays entre parenthèses dans le nom (« (Canada) »),
   un nom dans une autre langue (« The... », « Partito... », « ...Party »), ou des catégories
   Wikipédia d'un autre pays sans catégorie française.
   Une organisation étrangère reliée par une lignée à une organisation du graphe est marquée
   voie_externe = oui : elle sera dessinée dans une voie externe discrète, sans lien.
7. Sinon : **graphe** (organisations de gauche françaises, outre-mer compris).
   Sans date de fondation : sans_date.csv, pas de barre ni de lien.

Positionnement : « centre gauche » seul compte comme gauche ; accompagné de « centre droit » ou
« centrisme », l'organisation est exclue.

Gardés dans le graphe mais signalés dans la colonne perimetre_douteux, à trancher à la main :
« Parti républicain, radical et radical-socialiste » et « Parti radical » ; les organisations
que Wikidata place dans plusieurs pays ; celles dont aucun courant n'est reconnu.

## Famille (voie) et courants (couleur)

Courants : motifs cherchés dans le nom, les courants saisis à la main, les idéologies (Wikidata,
Wikipédia) et les catégories Wikipédia. Plusieurs courants possibles ; la colonne
courants_sources indique d'où vient chacun.

Famille : donnée par un courant saisi à la main s'il y en a un ; sinon par un courant reconnu
dans le nom (sauf « communiste » ou « socialiste » génériques quand un courant plus précis est
trouvé ailleurs : la LCR et l'OCI sont trotskystes malgré leur nom) ; sinon par le premier courant trouvé dans l'ordre de priorité suivant, quelle que
soit sa source : trotskyste, maoïste, anarcho-syndicaliste, communiste libertaire, anarchiste,
luxemburgiste / conseilliste, communiste, écosocialiste, écologiste, radical, social-démocrate.
L'écosocialisme (PG, LFI...) est rangé dans la famille socialiste, pas dans l'écologie politique.
Familles : socialistes, radicaux, écologistes, communistes, trotskystes, maoïstes, anarchistes et
libertaires, outre-mer. Une organisation d'outre-mer (nom ou catégories : Guadeloupe, Martinique,
Guyane, La Réunion, Mayotte, Nouvelle-Calédonie, Polynésie...) va dans la voie outre-mer et garde
ses courants. Sans courant reconnu : « non classé ».

## Liens

- Fusion par (ancêtre, descendant) ; type le plus informatif : passage > scission > filiation.
- Paires réciproques (A -> B et B -> A) : un seul lien, dans le sens du temps (l'organisation la
  plus ancienne est l'ancêtre) ; à date égale ou inconnue, le sens le plus attesté.
- R1 : un lien dont la cible est fondée avant la source (année, ou mois si les deux sont connus)
  va dans anomalies.csv avec une cause probable. Même année sans mois : gardé, meme_annee = oui.
- Lien de lignée entre une organisation et une Internationale : anomalies.csv.
- Réduction transitive des filiations : la filiation A -> C est retirée s'il existe un autre
  chemin de lignée (filiations et scissions) A -> B -> ... -> C.
- Relation finale : fusion (cible à plusieurs ancêtres en filiation), renommage (un seul ancêtre
  qui n'a qu'un successeur, et qui disparaît au plus un an avant ou après), filiation, scission,
  passage. Date de l'événement : fondation de la cible.
- « Membre de » vers une Internationale : affiliations.csv. Vers une organisation française
  (coalition, fédération) : appartenances_nationales.csv.
