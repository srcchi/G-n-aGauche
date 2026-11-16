# Prompt maître : G-n-aGauche

Consolidated master prompt, state of 15 November 2026 (branch `Affiche`). It merges the original project prompt, the standing constraints given since, every decision taken while building the tree, Addendum 3 and Addendum 3 bis. When two rules conflict, the later section wins, and the conflict is noted.

---

## 0. Project, context, standing constraints

PROJECT: Genealogy tree of French left and far-left political organisations.
GOAL: understand the present through its lineage. Show renamings, splits, mergers, absorptions, and affiliations to Internationals, as a readable and aesthetic tree.

CONTEXT: repository `D:\G-n-aGauche` (Windows, git, remote github.com/srcchi/G-n-aGauche, branches `main` and `Affiche`), conda environment. Layout:

| Folder | Content |
|---|---|
| `scripts/` | `arbre.py` (Wikidata SPARQL), `infobox.py` (Wikipedia FR infoboxes), `enrichissement.py` (texts, linked pages, candidate links, cached fetcher), `tableaux.py` (member tables of the Internationals), `nettoyage.py` (cleaning, typing, pruning, all outputs), `rendu.py` (SVG and HTML), `verifier.py` (report, fails on any non-zero counter), `preuves.py` (quote checking), `fusion.py` (used by nettoyage); `scripts/ancien/` old Graphviz version |
| `data/` | raw data and caches at the root, `manuel/` (files edited by hand), `sortie/` (generated tables), `ancien/` |
| `arbres/` | every tree: full, per family, HTML, preview, Vue par Internationale |
| root | `README.md` and `arbre.svg` only |

Run: `python scripts/nettoyage.py && python scripts/rendu.py && python scripts/verifier.py` (network steps, rare: `arbre.py`, `infobox.py`, `enrichissement.py`, `tableaux.py`).

STANDING CONSTRAINTS (always in force):
- All user-facing text in the tree stays in FRENCH. Use only commas, never em dashes, in any text written for display.
- Never modify input files. Generated files go to `data/sortie/`. Files the user edits by hand go to `data/manuel/`: create them once with headers and prefilled candidate rows, then only append rows, never overwrite a file the user may have edited.
- Conda environment: never install heavy dependencies without telling the user first.
- No Maitron scraping. Before scraping any site other than Wikipedia and Wikidata, read its robots.txt and terms and report what they say.
- Wikipedia and Wikidata requests: descriptive User-Agent naming only the repository URL (never the user's email or name), respect Retry-After on HTTP 429, cache everything, never refetch what is cached unless `--refresh` is passed.
- Sources: Wikipedia (fr, en) and Wikidata only. No loosening to other sources for now.
- Commit or push only when the user asks. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

GENERAL PRINCIPLES
- Rigour over volume, but coverage of well-known militant organisations matters (see 1.7): fewer organisations with documented lineage is better than many with doubtful links, yet a missing major organisation is a defect.
- Every non-trivial claim (link, type, date, affiliation, name, family) must be traceable to a verbatim quote from the raw cached wikitext. No invented facts. When unsure, write to a review file, do not guess.
- Be idempotent and cache everything. Handle HTTP 429 with backoff.

---

## 1. Hard rules

R1. Time direction. Every link is drawn with orthogonal segments only, with non-decreasing x, a final horizontal segment, and a right-pointing arrowhead. A link that cannot satisfy this goes to `data/sortie/anomalies.csv` and is not drawn (or becomes a renvoi). Never draw an arrow pointing up, down or left. R1 applies to every link type.

R2. Internationals are never boxes in the genealogy lanes. They appear only as affiliation marks along member bars, in the keys, and (Addendum 3, C1) in their own top lane "Internationales".

R3. Exact dates. Bar start and end positions follow the documented dates on a linear time axis (ticks every 10 years, top and bottom). Unknown end: faded hatched tail, status `fin_inconnue`. Validated active: gradient to the present.

R4. Every name is inside a box. Name tags are attached to bars. Only renvois (short "issu de X" / "scission de X" notes) may float.

R5. Strict lineage. A displayed organisation is either a validated active organisation, or an ancestor of a displayed active one. Active organisations with no lineage link are not displayed. No bar without at least one displayed link (renvois count). Exceptions, and only these:
- historical origins listed in `data/manuel/origines.csv` (First International and its anti-authoritarian branch, IO, IC, AIT 1922, with the CNT as its French section), each with a reason and a quote;
- incontournables (`data/manuel/incontournables.csv`) with no active descendant, drawn as "branche éteinte" with only their documented links (`data/sortie/branches_eteintes.csv`);
- the "Sans généalogie documentée" column (Addendum 3, B2 and 3 bis, 4).

R6. No coalitions and no satellites. Exclude coalitions and electoral alliances (Front populaire, NUPES, NFP, Gauche plurielle, Front de gauche, etc.), student and youth wings, local or federal échelons of a party, parliamentary groups, currents of a party, associations and clubs that are not parties. Exception: a body that was the founding body of a displayed party is drawn, flagged `type=fondatrice`. Name patterns are allowed for this rule (Addendum 3 bis, 1).

R7. No inherited affiliations. An organisation is affiliated to an International only if a source says so for that organisation itself: its own article, or the member table of the International's article naming it with its years (read by `tableaux.py`). The lineage of the Internationals themselves is its own graph, kept apart from the French tree.

R8. Evidence. Every link and affiliation carries `preuve` = explicite (the text says it), deduit (inferred) or manuel, plus a verbatim quote, checked by script against the raw cached wikitext. Quotes that cannot be found verbatim invalidate the link. Tooltips show the quote in full, never truncated.

R9. Foreign organisations are stored in the database only, never drawn. They can serve as an intermediate in an indirect dotted link between two French organisations, and are then named only in that link's tooltip. A hand-entered indirect link may also go through an undrawn French group (example: PSOP to Voix ouvrière through the Barta group).

R10. Scope. Overseas regional parties are kept only if they have a documented lineage link to a displayed metropolitan organisation. Otherwise they go to `data/sortie/hors_perimetre.csv`. Regionalist and autonomist parties without lineage are also hors_perimetre, never "isolee" (Addendum 3 bis, 2).

---

## 2. Phase 0: enrichment and validation

0.1 Validate `data/manuel/actifs.csv`: column `valide` (oui/non/blank) says whether the organisation is still active. Resolve blanks by reading the article text (and, when needed, other language versions and neighbouring pages). Columns `confiance` and `source`. A party is validated active only if its article states ongoing activity or cites a source after 2024; verify homonyms by identifier before keeping the flag (Addendum 3, B4).

0.2 For each candidate organisation, read the full article text, not only the infobox, and its neighbours (including other languages). Extract lineage statements ("formed by the merger of", "split from", "successor of", "renamed"), including chains passing through foreign organisations. Output `data/sortie/liens_candidats.csv` with the quote, the type and the confidence, plus the short extract `liens_candidats_a_lire.csv` (confidence at least 0.7, touching a drawn organisation, not yet drawn). The user validates with `decision = oui`.

0.3 Manual edges go to `data/manuel/aretes_manuelles.csv` (`ancetre, descendant, type, date_evenement, source, note`), source written `lang:Page : « verbatim quote »`. Types: renommage, scission, fusion, absorption, refondation, filiation, passage (militants; a dated passage may enter an older organisation, both must be alive at that date), indirect (two quotes `lang:Page : « … » ; lang:Page : « … »`, intermediary named in the note as `par : …`), composante (member of, single quote), supprimer (removes a wrong automatic link). No Maitron scraping.

0.4 Organisations that matter but cannot be resolved go to `data/sortie/liste_recherche.csv`.

0.5 Homonyms are disambiguated by identifier, never by name alone (example: the PCR of Réunion and the Parti communiste révolutionnaire of 2024; the Groupe Octobre theatre troupe and the Trotskyist group of the same name).

0.6 Member tables of the Internationals (`scripts/tableaux.py`): for every International, read the member tables of its en and fr articles, keep the French rows (organisation link, years, verbatim row as the quote) in `data/sortie/affiliations_tableaux.csv`. Table years rank after hand-entered dates and before every other source.

---

## 3. Phase 1: cleaning and classification

1.1 Classify each organisation in `data/manuel/types.csv`: parti, coalition, satellite, internationale, fondatrice, étrangère. Apply R6, R9, R10. A row marked `valide` wins over every automatic rule.

1.2 Typed relations. Each link has one type: renommage, scission, fusion, absorption, refondation, filiation_idéologique (plus passage, indirect, composante).
  a. A relation with several predecessors and one successor is a fusion, never a scission.
  b. Continuation rule: if the successor article or Wikidata says "replaced by", "transformed into", "succeeded by", and the end date of the predecessor equals the start date of the successor, type the link renommage (continuation, same row), and draw the other contributors as secondary joining arrows. Only one renommage per successor: the longest-lived source. SFIO to PS in 1969 is a renommage, with UCRG, UGCS as secondary contributors, and CIR in 1971.
  c. Type check: for every link, compare the relation type with the field of its quote. Mismatches go to `anomalies.csv` and are not drawn until resolved.
  d. Transitive reduction: a filiation A to C is removed when another lineage path A to B to C exists, except when A ends the year C is founded (A merged itself into C, example POSR to SFIO in 1905).
  e. Successive names of one organisation, read from the infobox `fondation` field ("1920 (SFIC), 1921 (PC-SFIC), 1943 (PCF)"), go to `data/sortie/noms_successifs.csv` with a quote for each; names dated before the bar's start are ignored.

1.3 Internationals go to `data/sortie/internationales.csv`, with exact start and end years. Succession lines come ONLY from typed relations (renommage, fusion, refondation). A split is not a succession. Second and Third International are separate roots. Internationale socialiste descends from the Socialist International of 1951, itself a refoundation of the Labour and Socialist International, with a quote. The Kominform is not the successor of the Comintern unless a source says so. Splits go to a separate "Scissions" line. Families of Internationals: `data/sortie/internationales_filles.csv` (splits, successions, plus the hand-edited `data/manuel/internationales_filles.csv` for reunifications and "se réclame de", each with a quote; a hand-entered row wins). Example: QI, with QI-SU, the lambertist QI and CRP-QI (formerly FT-QI) as daughters.

1.4 Affiliations go to `data/sortie/affiliations.csv` (entry date, exit date or "toujours membre", quote). Undated ones go to `affiliations_a_dater.csv`; hand-entered dates go to `data/manuel/affiliations_dates.csv` (source required), prefilled from infoboxes when they give dates.

1.5 Strict pruning to `data/sortie/elagues.csv`, with a final gate: every displayed organisation has at least one displayed link, or is a validated active organisation with a displayed ancestor (origins and dead branches exempt). Organisations with no start date, or no end date and no status, never get a bar: they go to `a_dater.csv`. `data/sortie/elagage_rejets.csv` is the exhaustive log: one row for EVERY candidate of the raw sources (Wikidata `data/noeuds.csv`, Wikipedia `data/wp_noeuds.csv`, manual nodes) that is not displayed, columns `id, label, actif (oui/non/inconnu), famille_si_connue, raison, lien_manquant, source`.

1.6 Tags (`data/manuel/sigles.csv`). Every organisation gets a short tag, from the official sigle or the usual short name of the French article, else a shortened name of at most 24 characters. The full name goes only in the tooltip. Disambiguate every ambiguous sigle against the whole database ("PT (1991)", "PT (2015)", "PCR (Réunion)", "PCR (2024)").

1.7 Coverage check. Every organisation of `data/manuel/incontournables.csv` appears in the tree (as a dead branch if needed), or is explained. `data/sortie/couverture.csv` says, for each incontournable and for Place publique, whether it was collected at all (Wikidata, Wikipedia, manual) and, if not, why (query filter, category, ideology field). An organisation never collected is added explicitly (Wikidata id and article) and the run is repeated. A regression test (`regression.csv`) lists every organisation that disappeared since the previous run and why.

---

## 4. Phase 2: layout and SVG (Python writing SVG directly)

2.1 Lanes by political family, following the ideology and positioning fields of the French article, not the country or region. A regionalist or autonomist party is not "Écologistes" unless the article says so. Lane order follows lineage adjacency: Socialistes, Communistes and Trotskystes next to each other, Écologistes and Anarchistes outside that block. An overseas party sits in the overseas lane but keeps its current's colour.

2.2 Rows inside a lane by lineage cluster, related bars on adjacent rows. Isolated bars at the bottom of the lane, no extra gaps. A renamed successor continues on the same row (continuation, white tick).

2.3 Zero crossings. No link segment may cross another bar, name tag, band or band label (exemption: bars and bands of the link's own two ends, and co-members of the same organisation for composantes). The verifier fails if the count is not 0 for links spanning at most 2 lanes. No floating link: every link starts on its source bar, or on a band present at that date.

2.4 Link markers. Scission: a marker on the parent bar at the split date (Addendum 3, C2: a small diamond), right-pointing arrowhead on the child. Fusion: converging fork. Renommage: plain continuation. Absorption: arrow ending on the absorbing bar. Passage: blue dotted. Indirect: grey dotted. Filiation idéologique ("inspire"): grey dotted. No arrowhead ever points up or down.

2.5 Major links are never renvois: both ends in the top lineage (more than 20 years of life, or active today), always drawn whatever the span (SFIO to PCF 1920, SFIO to PS 1969). An origin link is forced only if it is not a filiation idéologique and spans under 40 years. Other links become renvois when they span more than 2 lanes, more than 40 years, or more than 6 rows. More than 3 renvois on a bar: one "voir aussi (n)" marker. Components of a fusion that are not displayed are listed in the tooltip.

2.6 Name tags at the START of the bar, never after its end (except a live short bar with no outgoing link, whose tag may sit after today). The base sigle drops the homonym year when the dates are printed; when the dates do not fit, the sigle alone. Successive names (1.2e) are written inside the bar after a white tick at each change date; the tag gives the first name when it fits. Overridden by Addendum 3, C3.

2.7 Affiliations. One band per affiliation under the bar over the documented period, sigle inside. Dated: solid. Undated: hatched over the whole bar, no "?" (the hatching says it, see the legend). Successive affiliations share one line (SFIO: IO, then UPSAI, then IOS, then IS); at most 2 lines, the rest in the tooltip. Outlined to stay readable. One colour per lineage of Internationals. Overridden by Addendum 3, C1.

2.8 Keys: compact key beside the tree, the full "Clé des Internationales" below, then the index of organisation sigles (4 columns). Each entry: exact years, Succession line (1.3 only), Scissions line, daughters ("Filles"), count and tags of displayed members. In the HTML, a click on an International highlights it, all its descendants and all their members.

2.9 "Vue par Internationale": separate SVG and HTML.

2.10 Outputs: `arbre.svg` (root, copy of `arbres/arbre.svg`), one SVG per family, `arbre_apercu.svg`, a self-contained `arbres/arbre.html` (zoom, search, kinship on hover, fold families, key), tooltips with name, exact dates, type, preuve and full quote of every link, affiliations with dates. Legend counts computed from the displayed set.

2.11 Layout quality: no overlap, constant bar thickness, padding, text never clipped; decade bands as alternating backgrounds (opacity 0.06).

---

## 5. Verification (`scripts/verifier.py`, plus PNG render)

Report and fail on: liens flottants, bars without link (dead branches exempt), undated bars, duplicate tags (sigle plus dates), crossings, undated bands drawn solid, key successions containing a split, R1 to R8 violations, R3 date mismatches (a strip glued to its section ends at the section's start), R4 text overflows or overlaps (names inside bars included), quotes not found verbatim, types contradicting their quote, major links in renvoi, incontournables missing without explanation, tags after a bar end with a direct successor, texts under 11 px, legend count. Render the PNG and inspect the crops listed in Addendum 3, D2. Fix everything flagged before delivering. Summarise what was dropped and why, and list every rule conflict resolved.

---

## 6. Data decisions already taken (do not reopen without the user)

- Coalitions not drawn (Front de gauche, NUPES, NFP). POI, PG, LFI and L'Après glued as composantes (to become renvois or brackets under C5). GES and Ensemble in L'Après.
- EELV renamed Les Écologistes in 2023. POI founded 2008 after the PT; POID split in 2015, renamed Parti des travailleurs in 2023 (continuation).
- PCOF, URC (2025, Charles Hoareau), URCF, PCRF, Socialisme ou Barbarie (NPA tendency, 2025), JCR and PCI link, CIO/CWI then TMI then ICR.
- SFIO founded by PSF, PSdF, POSR (POSR continues on the SFIO row as the longest-lived source), PUP absorbed in 1937; their IO periods from the Second International member table.
- PCF: SFIC 1920, PC-SFIC 1921, PCF 1943 inside one bar; IC membership 1921 to 1943 from the Comintern table.
- Lutte ouvrière drawn from 1956 (Voix ouvrière, then Lutte ouvrière 1968); the Barta group (1939 to 1950) is not drawn; indirect dotted link PSOP to Voix ouvrière through the Barta group; POI to PSOP passage in 1939 (Craipeau minority).
- Ligue communiste (1930): fusion into the POI in 1936, passage into the SFIO in 1934 (renvoi). PCF to Ligue communiste not drawn (only "tendance interne au sein du PCF").
- PCI (1944): Groupe Octobre link on Wikipedia points to a theatre troupe (homonym), Comité communiste internationaliste has no article: tooltip mention only.
- Gauche prolétarienne and UJC(ml): dead branches; candidate links (UEC to UJCml, UJCml to PCMLF) await the user's decision in `liens_candidats.csv`.
- Place publique: collected, active, no documented ancestor; goes to the "Sans généalogie documentée" column, not under the PS (no source calls it a PS current).

---

## 7. ADDENDUM 3 (review of the SVG with 99 organisations, 82 drawn links, 23 renvoi links)

It overrides any conflicting rule above, in particular 2.1, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8 and 2.10. Report in your final summary every conflict you had to resolve.

A. OUTPUT ARCHITECTURE
A1. Keep the current renderer as arbre_html.py (SVG plus self-contained HTML, tooltips, quotes, verification report, PNG). Do not change its look beyond sections B to D.
A2. Split computation from drawing. A layout step writes data/mise_en_page.json (organisations, bars, rows, lanes, routed links, bands, keys), parameterised by font sizes and row height. Both renderers read it.
A3. Create arbre_affiche.py, a second renderer producing affiche.svg and affiche.pdf (A1 landscape, 841 x 594 mm, vector, fonts embedded or outlined). It applies only a theme read from theme_affiche.json (section E). It runs its own layout pass with the same algorithm and the theme's sizes, then the same verification (section F), and fails if verification fails.
A4. Never change data or lineage logic inside a renderer. Any data fix belongs to the shared steps.

B. DATA FIXES
B1. Write data/elagage_rejets.csv on every run (organisation, id, active yes/no, reason for rejection, missing link). I will send it back for review.
B2. New zone "Sans généalogie documentée": a column at the right edge for validated active parties that have no documented ancestor. Each is drawn as a bar from its founding date, with a small open bracket at the left end meaning "no documented ancestor", and no links. Place publique (2018) belongs here. This is the only exception to R5 and applies only to active parties that are left or centre-left in the French article. List candidates to verify in Phase 0, never to assume: Génération écologie, Cap écologie, Parti pirate, Parti de la démondialisation, Résistons!, Parti animaliste. Write data/actifs_absents.csv with the decision and the source for each. Coalitions (NFP, NUPES) stay excluded (R6).
B3. Scope by position. Parties whose French article gives a centre or centre-right position are not displayed, unless they are an ancestor of a displayed organisation (Parti radical is kept only as the ancestor of the Parti radical de gauche, with a note). Overseas parties follow R10.
B4. Activity validation. A party is validated active only if its article states ongoing activity or cites a source after 2024. Verify homonyms by identifier before keeping the "active" flag. "Socialisme ou barbarie" is currently marked active, and the historical group of 1948 to 1967 is not: check which entity is meant, and fix or drop it.
B5. Key of the Internationals. Rebuild every Succession line from typed relations only (renommage, fusion, refondation). Currently wrong: UPSAI and CMRI show the same chain as the IOS, and the Kominform is shown as the successor of the Communist International. Fix or remove each, with a quote. A split goes to "Scissions", never to "Succession".
B6. Typed relations. Re-run the type check on all 82 drawn links. A "composante" (member of, without merger) is not a time link: do not draw it as a link between rows (see C5).
B7. Renaming chains. SFIO to PS in 1969 is a renommage, with UCRG, UGCS as secondary contributors and CIR in 1971 (rule 1.2b). Generalise the inner-name feature already used for PC-SFIC then PCF and Voix ouvrière then Lutte ouvrière: for every renommage chain on one row, write each successive name inside the bar at the date of the change.

C. LAYOUT AND SHAPES
C1. Internationals leave the lanes. Remove the Internationals (AIT, IO, IC and others) from the lanes and from the organisation count. Create a top lane "Internationales", using the same ribbon for each International over its life span. Distinct shape for every International, everywhere: a round medallion carrying the sigle, extended by an arrow ribbon. An arrow tip means still a member, a cut end means left, a dashed hatched ribbon means dates unknown. All Internationals use one colour, a dark navy. They are told apart by their sigle only. Under a party's bar, only the medallion and its ribbon appear, never a rectangle.
C2. No other round shapes in the drawing. Replace the scission marker (currently a small circle) by a small diamond. Affiliation marks never reuse shape or colour of scission markers.
C3. Name tags. Every bar carries its tag at its start. When the bar is at least as long as the tag, the tag sits inside the bar, left-aligned. When it is shorter, the tag becomes a tab attached flush above the bar's left end, in the bar's colour, never beside the bar and never after its end. Currently 35 of 99 tags sit outside their bar: the target is 0. The date range written in the tag is the segment's own range, never the whole chain's range or an open "1920–" for a segment that ended (for example the SFIC segment).
C4. Links must not hug other elements. Keep at least 4 px between any link segment and a band edge, tag or bar, and 6 px between parallel links. Include affiliation ribbons in the crossing test. The cluster FTSF, POSR, PSF, PSdF, CRC, POF currently shows black lines running along the edges of the IO ribbons: re-route it, spreading the links in separate channels.
C5. Composante links ("member of, without merger", for example PG to LFI, GES to L'Après and LFI). Never draw them as dotted vertical lines without a head. Show them as a renvoi ("membre de LFI") unless both ends sit on adjacent rows, and then as a thin solid bracket with an open arrowhead pointing right. R1 applies to every link type.
C6. Major links stay drawn (SFIO to PCF, SFIO to PS). With the Internationals moved out of the lanes, no link may cross a band, tag or bar. Check this for SFIO to PCF in particular.
C7. Renvois: keep at most 3 per bar, then a "voir aussi (n)" marker. With 82 drawn links and 23 in renvoi, review which renvois can now be drawn.

D. VERIFICATION (extend the script, used by both renderers)
D1. Report and fail on: tags outside their bar (0), Internationals inside lanes (0), links crossing a band, tag or bar (0), composante links drawn as headless dotted lines (0), wrong or split-as-succession entries in the key (0), actives validated without a source after 2024 (0), homonym errors (0).
D2. Render the PNG and crop at least: the FTSF to SFIO cluster, the SFIO to PCF to IC area, the Trotskyist lane (LCR, NPA, Révolution permanente), the new "Sans généalogie" column, the top Internationals lane.

E. POSTER THEME (theme_affiche.json, used only by arbre_affiche.py)
E1. Palette. Paper #F5F0E6, ink #1C1B22. Families: socialistes #E4759B, communistes #B8232F, trotskystes #E8A317, anarchistes #1C1B22, écologistes #2F9E6B, maoïstes #1F6FA8, radicaux #E9D44C. Internationals: navy #1F2A5C. "Today" line: gold #C9962B. Ancestors at 70 percent opacity, active parties at full colour with the fade to the present. Lane backgrounds: the family colour at about 8 percent opacity. Text on dark bars is white, on light bars is ink.
E2. Fonts (open licence): Fraunces for titles, Barlow Condensed for names and tags, IBM Plex Mono for dates. Names at least 14 px, tags at least 14 px at the 2981 px reference width; scale proportionally to the A1 page.
E3. Style. Flat colours, no outlines on bars, 2 px gap between bars, 8 px grid, links 1.5 px ink at 70 percent opacity. A subtle paper grain of at most 4 percent is allowed on the poster only.
E4. Composition. Large title at top left, "D'où vient la gauche ?", with a subtitle giving the period and the data sources. Key bottom left. "Vue par Internationale" bottom right. A larger column of the active parties at the right edge, as the entry point. Six reference dates as thin vertical rules with short captions, listed in data/reperes.csv with a source each: 1871, 1905, 1920, 1968, 1981, 2024.
E5. Variant (optional, only if asked): black background and bright flat colours.

---

## 8. ADDENDUM 3 bis (from reading data/elagues.csv, 592 rejected candidates)

1. Rule R6 pattern: classify as satellite any name matching "fédération (départementale|de|du|des) ... du Parti socialiste", "groupe ... à l'Assemblée", "section ...", "comité de suivi", and courants of a displayed party ("Un monde d'avance").
2. Classify regionalist and overseas actives (Walwari, Union calédonienne, Parti de libération kanak, Eusko Alkartasuna, Endavant, War-Sav, Pour la Bretagne, Parti de la nation occitan, Rézistan's Égalité 974, UDB Jeunes) as hors_perimetre, never isolee.
3. Never place an International in the party candidates (Unité internationale des travailleurs - Quatrième Internationale goes to internationales.csv).
4. "Sans généalogie documentée" column: only national active parties with cause isolee after the previous filters. Initial candidates: Place publique, Génération écologie, Mouvement écologiste indépendant. Decide Parti pirate by its French article's position. Re-derive each family from the article, not from the first ideology found (Place publique is currently placed in "écologistes").
5. Duplicate check: when two items share a name root or one is a documented earlier name of another (Mouvement des citoyens and MRC), merge them as one chain with a renommage. Re-check Parti communiste (France, 1919): wrong family and wrong cause.
6. Le Poing Levé and Du Pain et des Roses stay out of the lanes (R6) but are listed in Révolution permanente's tooltip as linked organisations.

---

## 9. Conflicts resolved, and open questions

Resolved:
- R6 classification by name words (3 bis, 1) overrides the earlier principle "never classify by name words alone".
- R7: an International's member table naming the organisation counts as a source "for that organisation itself".
- R5: three exceptions only (origins, dead branches, Sans généalogie column).
- 2.7 "?" in undated band sigles: removed, the hatching and the legend say it.
- B1 superseded by the exhaustive log of 1.5 (more columns).

Decided by the user on 16 November 2026 (formerly open questions):
- C1 confirmed: it replaces the strip design of 14 November. Top lane "Internationales", round medallion plus ribbon, one navy colour for all, told apart by sigle only.
- Parti communiste (France, 1919) (Raymond Péricat): anarchist family, Anarchistes lane, link to the Union anarchiste (1920). Every link needs a verbatim quote from the article (R8); if no quote supports the link, draw the bar without it and log why.
- Spartacist LCI (QI) and Ligue trotskyste de France: look for a source, French article first, then English. If a quote documents the origin (tendency expelled from the US SWP, 1963-1964), draw an "indirect" grey dotted link from the QI to the LCI. Otherwise draw no link and log why.
- Poster: CairoSVG (conda or pip) for the vector PDF. Fonts (Fraunces, Barlow Condensed, IBM Plex Mono, all OFL) downloaded once into a `fonts/` folder of the repository, after reading the licence and terms. No browser is available for PNG crops.

Open (ask the user before acting):
- none at this time.

---

## 10. ADDENDUM 4 (from the latest run files: arbre.log, anomalies, aretes_reciproques, affiliations_tableaux, actifs_a_revoir)

1. Political-type gate. Both the ancestor crawl (`arbre.py`) and the member-table parser (`tableaux.py`) must keep only political organisations. The last run pulled in territories (Moselle, Bas-Rhin, Alsace-Lorraine, comté de Nice), the G7 and G8, DataCite, ORCID, an association of publishers and the Bureau international de l'heure, and the member tables produced rows for persons (party leaders), cultural regions and a trade union (CGT). Filter by Wikidata instance type and by article category, and write every rejection to `elagage_rejets.csv` with the reason.
2. Activity confidence. A proposal with `confiance` = faible never validates anything: it goes to `actifs_a_revoir.csv`. The cited text must be about the entity itself, never about a parent or related organisation (Tendance CLAIRE currently cites the NPA article). A coalition such as the Nouveau Front populaire must never be proposed as active.
3. Duplicates. The anomaly "scission 1993 to 1993" between Mouvement des citoyens and Mouvement républicain et citoyen shows a duplicate: merge them as one chain with a renommage (see 3 bis, 5).
4. LCR to PS (1974 to 1969) and LCR to OCI (1974 to 1952): keep them out of the drawn links. Treat them as candidate `passage` links (militants), to be validated by the user in `liens_candidats_a_lire.csv`.
5. Do not lose the NPA and NPA-R, displayed in an earlier version: `regression.csv` must list them if they disappear.
---

## 10 bis. Progress, 16 November 2026 (session at work, branch `Affiche`)

Done, verified by `nettoyage.py`, `rendu.py` and `verifier.py` (all counters at 0, 108 organisations drawn):
- 3 bis, 1: `RX_COURANT_DE` fixed (a bold name containing an apostrophe, "Un monde d'avance", did not match). Un monde d'avance typed satellite in `types.csv`.
- 3 bis, 2: regionalist or autonomist organisations (ideology, categories, or the "régionaliste / autonomiste" current) and overseas organisations with no lineage link go to `hors_perimetre`, never `isolee` (63 organisations).
- 3 bis, 4 and B2: decisions in `data/manuel/actifs_absents.csv` (decision colonne / exclu / a_verifier, verbatim quote of the article). Column: Place publique (socialist family, centre left), Génération écologie, Parti pirate (neutral colour, tag "Parti pirate" to avoid two "PP"). Excluded: MEI (centre), Cap écologie (redirects to Cap21, centre), Parti de la démondialisation (no article), Résistons ! (position disputed), Parti animaliste (catch-all). To decide: Démocrates et progressistes and Union des centristes et des écologistes (centre to centre left).
- 3 bis, 5 and 4, 3: Mouvement des citoyens and MRC are one chain: MRC founded 2003 (`noeuds_manuels.csv`), MDC ends 2003, inverted automatic link removed, renommage MDC -> MRC 2003 (`aretes_manuelles.csv`).
- 3 bis, 6: Le Poing Levé and Du Pain et des Roses attached to Révolution permanente (type `emanation`), listed in its tooltip; Du Pain et des Roses typed satellite.
- Parti communiste (France, 1919): anarchist family; drawn with the Union anarchiste as ancestors of the Fédération anarchiste, through a sourced filiation UA -> FA 1945 (militants of the UA and the FAF).
- Spartacist LCI: sourced descent recorded in `data/manuel/internationales_filles.csv`, from the CIQI, indirect through the US SWP (two quotes, both verified). The Ligue trotskyste de France stays undated (empty fondation field).
- 4, 1: `scripts/porte.py`, a political-type gate by Wikidata classes (P31 then P279* of the distinct types, cached in `data/cache_porte.json`). Used by `nettoyage.py` (581 rejections with their reason in `elagage_rejets.csv`), `tableaux.py` (11 rows rejected: Occitanie, Alsace, Corse, Savoie, Pays catalans, three persons, the CGT; `data/sortie/rejets_porte_tableaux.csv`) and `arbre.py` (no climbing through a rejected entity, `data/rejets_porte_arbre.csv`; not run yet, takes effect at the next collection). Identifiers cited in `data/manuel/` are exempt.
- 4, 2: in `enrichissement.completer_actifs`, a coalition (Wikidata type) is never proposed active, and a quote whose bold subject is another organisation (Tendance CLAIRE citing the NPA) is rejected; reason in the new `note` column of `actifs_a_revoir.csv`.
- 4, 4: links rejected because the target already existed are proposed as `passage` at the top of `liens_candidats_a_lire.csv` (LCR -> OCI 1979, LCR -> PS). Validation: a `passage` row in `aretes_manuelles.csv`.
- 4, 5: `regression.csv` lists every missing incontournable on every run, not only on the run where it disappeared (NPA and NPA-R are incontournables).

Conflicts resolved in this session:
- B2 asks for a column "at the right edge". It is drawn as the last lane, at the bottom, bars at their real dates (so on the right of the time axis), with an open bracket at the left end: a separate column would break R3 (linear time axis).
- LCI: the user asked for an indirect link from the QI; the sources document the CIQI (founded in 1953 with the SWP), a daughter of the QI. The CIQI was kept.

- Place publique (user's request): PSE membership dated 17 October 2025 (`affiliations_dates.csv`, quote of its article); PSE recorded as "organisation associée" of the IS in `internationales_filles.csv` (fr:Parti socialiste européen). Place publique is linked to the IS only through the PSE, never drawn as an IS member (R7): its tooltip says "par le PSE, lié à IS", and the HTML key of the IS highlights the PSE and its members.
- Place publique next to the PS (user's request, overrides the separate column of B2 for it): a "Sans généalogie" party whose family has a lane goes into that lane when it shares an affiliation with a drawn party of that family, on the first free row after that party (an "affinité", used only for placement, never drawn as a link). Place publique and the PS share the PSE. It keeps its open bracket. Then extended at the user's request: every "Sans généalogie" party with a known family goes into its family's lane (Génération écologie in Écologistes, at the bottom of the lane); only parties with no family (Parti pirate) stay in the "Sans généalogie documentée" lane.
- To check: two bars tagged "UDE" in the Écologistes lane (2015 and 2020), homonym or successor of the Union des démocrates et des écologistes; the duplicate-tag check misses it because the dates differ (rule 1.6).
- Network collection rerun on 16 November 2026 with the political gate in `arbre.py`: `noeuds.csv` went from 1549 to 1007 entities (162 rejected directly, listed in `data/rejets_porte_arbre.csv`, plus the ancestors no longer reached through them), none added; the tree is unchanged (108 organisations kept, 165 links, empty `regression.csv`).

C1 and C2 done (all verifier counters at 0, 103 organisations: the 5 strips left the lanes):
- The strips of `origines.csv` (AIT, AIT anti-autoritaire, IO, IC, AIT 1922) are no longer bars. Their composante link to their section (SFIO, PC-SFIC, CNT) becomes a ribbon under the section when no dated membership exists (the CNT keeps its AIT 1922 ribbon). Their links between Internationals stay in the key and the Vue par Internationale. The CNT, an origin, is exempt from "barres sans lien".
- Top lane "Internationales" (`voie_internationales` in `rendu.py`): one navy ribbon per International over its life, round medallion at its start, arrow tip if it still exists, cut end otherwise, hatched with a dashed outline if its founding date is unknown (UCI). Sigle, name and dates inside the ribbon when they fit, else the sigle in a tab glued above its start (C3). Rows packed, 22 px, plus 14 px for rows with a tab.
- European parties, alliances and groups (PSE, PGE, PVE, PALDE, GAE, ACE, AGEPP, Pirates européens, GGPE) are not Internationals: they stay as ribbons under their members' bars, not in the top lane (otherwise 26 rows, since 25 of them still exist). 24 Internationals in the top lane, 16 rows, 432 px.
- Under the bars: navy ribbon, medallion at its start, arrow tip if still a member of an active party, cut end otherwise, hatched with a dashed outline if undated. Deviation from C1: the sigle is written in the ribbon after the medallion, not inside it (a 13 px medallion cannot hold "PSE" or "QI-SU" at the 11 px minimum).
- Medallions are white with a navy border (navy on navy was invisible). All Internationals are navy, told apart by sigle (key swatches are medallions too).
- C2: scission marker is a diamond, composante marker a small square, both `geo` polygons (moved by the HTML page when a family is folded). The verifier fails on any circle that is not a medallion, on any International bar in a lane, and on any International text outside its ribbon or tab.
- Not tested: folding families in `arbres/arbre.html` (no JavaScript runtime at work; the top lane uses the class `voie-intl`, not `voie`, so the folding code ignores it).

- Family of an International (user's report: a click on the QI did not show its daughters): `nettoyage.py` now also keeps the Internationals a kept one split from, and the parents entered in `internationales_filles.csv` (CIQI, LIT-QI, CIO came back; 41 in `internationales.csv`). The top lane and the key include these ancestors. In the HTML page, the top-lane ribbons are clickable, and a click highlights the International, all its descendants (top lane) and all their members. A click on the QI: QI, QI-SU, QI (lambertiste), CRP-QI, CIQI, LIT-QI, LCI; members PCI, POI (1936), LCR, POI, RP. JavaScript syntax checked with Node; the click itself was not run (no DOM library).

Next: the poster (A2, A3, E, CairoSVG and fonts in `fonts/`).

---

## 11. ADDENDUM 5 (review of the 103-organisation SVG, state of 16 November 2026)

It overrides any conflicting rule above. Context: the run passed all 22 verifier counters, yet the render still shows the defects below. Fix the defects, then extend `verifier.py` so that each one can no longer pass silently (section G). Report in the final summary every rule conflict you had to resolve, and stop after each stage as before.

A. SUCCESSOR NAMES AND TAGS (completes B7 and C3)
A1. Every renommage chain on one row must write each successive name INSIDE the bar, at the date of the change, after a white tick. Today only PC-SFIC/PCF and Voix ouvrière/Lutte ouvrière do it. Bars visibly without any name: PSF, FTSF, CAP, MGR and the unlabeled segment after "NPA 2009 to 2024", "PCF", "Parti radical", "Les Écologistes", "Génération écologie" and others. Count every `org` whose bar has no visible text at all, and make that count 0.
A2. A tag never sits after the end of its bar. NPA-A, L'Après, URC, PCR (2024) and PT (2023) currently have their tag right of the bar. Put the tag at the START of the bar, or as a tab flush above its left end when the bar is shorter than the tag (C3). The "live short bar with no outgoing link" exemption of 2.6 is withdrawn.
A3. The date range written in a tag is the segment's own range.

B. KEY OF THE INTERNATIONALS (completes B5)
B1. Rebuild the "Succession" line of every International from typed relations only (renommage, fusion, refondation), each with a verbatim quote. Currently wrong: the Kominform is shown as the successor of the Communist International (IC), the IC key lists the Internationale ouvrière under "Scissions", and UPSAI and CMRI show the same chain as the IOS. Remove every chain you cannot source. A chain that mixes an International with another one that is not its documented successor is an error.
B2. Splits go to a "Scissions" line, and only when a source says split. If it says succession or ideological filiation, name it so, or write nothing.
B3. Write `data/sortie/cle_internationales.csv` (International, years, succession chain, splits, quote for each) and make the key read from it.

C. INTERNATIONALS LANE
C1. Remove the duplicate: "Première Internationale (AIT)" and "Association internationale des travailleurs (AIT)" are drawn twice for 1864 to 1876. Keep one, with the tooltip naming both identifiers.
C2. Remove the duplicated sigle in "AIT AIT anarcho-syndicaliste (1922)". Use "AIT (1922)" and "AIT (1864)".
C3. Disambiguate against the whole database: the Opposition communiste internationale (1930) and the Organisation communiste internationaliste both use "OCI". Use "OCI (1930)" for the first.
C4. Text on hatched ribbons must stay readable: put the sigle in a solid label box (navy, white text) at the left of the ribbon, never white text directly on the hatching. This concerns UCI, LIT-QI, IFA, SIL, PGE, CIPOML, EITP and every other hatched ribbon. Every medallion carries its sigle: one under LFI has none.
C5. "Membres affichés (0)" for AIT and OCI is allowed only for origins (R5 exception); otherwise show the member count.

D. COMPOSANTE LINKS (C5, R1)
D1. The dotted vertical line between PG and LFI is a headless composante link and must disappear: draw it as a renvoi ("membre de LFI"), or as a thin solid bracket with an open arrowhead pointing right if both ends are on adjacent rows. Extend the verifier so that composante links count in R1.

E. "SANS GÉNÉALOGIE DOCUMENTÉE" (B2, 3 bis 4)
E1. This is a lane at the bottom of the chart, and the only place where a bar with the open bracket may sit. An organisation with the bracket is not drawn in its family lane. Today Place publique is in Socialistes, Génération écologie in Écologistes, and only the Parti pirate is in the lane. Move all three into it, and add the Mouvement écologiste indépendant (collected, active, rejected as "isolee").
E2. The lane title counts the real number of organisations. The family of each member is shown by the bar colour, derived from the French article (not from the first ideology found, and never "socialistes" for Place publique, since no source calls it a current of the PS).
E3. Cap Écologie is rejected as `a_dater`: look for its start date and activity in Phase 0. Write the decision and source for each candidate in `actifs_absents.csv`.

F. FAMILIES AND SCOPE
F1. Re-derive the family of the three scissions of the NPA of 2009: Convergences et alternative (currently Écologistes), Gauche unitaire (Communistes), Gauche anticapitaliste (Socialistes). Put the three, and Ensemble which merges them, in the lane of the NPA's lineage (Trotskystes) when the article gives no ecological or socialist position, otherwise in the lane the article names. Write the quote used in `famille_decision.csv`.
F2. Centre parties (R10, 3 B3): Union des démocrates et des écologistes, Front démocrate, Mouvement des progressistes (and the second "UDE 2020" bar). Read each French article. Display only the ones whose position is left or centre-left, or which are the ancestor of a displayed organisation (with a note). The others go to `hors_perimetre.csv`. Report the position quoted for each.
F3. Parti communiste (France, 1919): the anarchist-communist group that became the Union anarchiste in 1920. Keep it in Anarchistes, but remove its affiliation to the Communist International unless a quote says that this very organisation joined it (R7), and name it "Parti communiste (anarchiste, 1919)" in the tag.
F4. Gauche prolétarienne and UJC(ml): keep them as dead branches. In `liens_candidats_a_lire.csv`, put first the candidate links UEC to UJC(ml) and UJC(ml) to PCMLF, with their quotes, so that I can answer `decision`.

G. VERIFIER (extend, fail on any non-zero)
G1. Bars with no visible name: 0. Tags beyond the end of their bar, tabs included: 0.
G2. Composante links counted in R1: 0 headless or dotted links.
G3. Key content: every Succession and Scissions line has a typed relation and a verbatim quote in `cle_internationales.csv`: 0 without.
G4. Duplicated International (same identifier or same sigle and same dates): 0.
G5. Text on hatching without a solid label box: 0.
G6. Every organisation with the `sans-ancetre` bracket lives in the "Sans généalogie documentée" lane and the lane's count equals the number drawn: 0 mismatch.
G7. Centre or centre-right organisations displayed without being an ancestor: 0.
G8. After the run, write PNG crops of: the Internationals lane, the SFIO to PCF area, the NPA scissions (GU, C&A, GA, Ensemble), the "Sans généalogie" lane, the PG/LFI area, and show them to me before saying the stage is done.

STAGES
This addendum belongs to Stage 2 (sections A to D, F1 to F3 are data and layout), except E, F2 and F4 which belong to Stage 1 (data). Redo Stage 1 for these, show the summary, wait for my confirmation, then redo Stage 2. The poster (Stage 3) is not started before I confirm Stage 2.
