# Témoins du duel (v2, GECKO-10)

Courbes des deux témoins du duel, recalculées sur le runner GitHub (ubuntu-24.04) : l'évolution (moteur D, corps libre),
l'évolution à corps figé (manche 1) et le hasard pur. Chaque camp joue 5 fois (décision de Tom et Dorian).
Graphique : `courbes_temoins.html` (une figure par manche, moyenne et bande min–max, tableau de valeurs).

## Sources

| Camp | Runs | Entraînement (GitHub Actions) | Courbe (mode analyse) |
|---|---|---|---|
| Évolution, moteur D | `runs/0` à `runs/4` | 38411711297 (graines 0 à 2, v1.1), 38594982071 (3 et 4) | 38591827980, 38591833025, 38591838125, 38602057823, 38602068889 |
| Évolution à corps figé (`FROZEN_BODY = True`) | `runs/corps_fige/0` à `4` | 38591806655 (0 à 2), 38594977725 (3 et 4) | 38599424135, 38599428680, 38599433812, 38602053650, 38602062343 |
| Hasard pur | graines 100 à 104, manches 1 et 2 | — | 38595306742 |

Runs sauvegardés sur `sauvegarde-runs` (`e6ca06d`), SHA-256 vérifiés, restauration vérifiée sur un clone neuf.

**Méthode** (`evo/courbes.py`) :
- évolution : chaque génome évalué par le run est réévalué par l'évaluateur batché, dans l'ordre du run (1 000 à la
  génération 0, puis les 500 enfants de chaque génération : 101 000 évaluations). Garde-fou : hauteur et énergie
  identiques au bit près aux valeurs stockées ; vérifié pour les 505 000 réévaluations des 5 + 5 runs ;
- hasard pur : 200 génomes par tirage, générateur de la génération 0 de l'évolution, manche 1 à corps figé ;
- la courbe est la meilleure hauteur accrochée parmi les n premiers lézards testés.

Fichiers : `<nom>_resume.json` (lectures à 50 et 200, meilleur, paliers), `<nom>_paliers.csv` (chaque nouveau record).
Les évaluations complètes (`<nom>_evaluations.npz`, 22 Mo) sont dans les artefacts des runs ci-dessus.

## Lectures (meilleure hauteur accrochée, moyenne des 5 graines ou tirages ; min à max)

| Lézards testés | Évolution D | Évolution à corps figé | Hasard, manche 1 | Hasard, manche 2 |
|---|---|---|---|---|
| 1 | −5,31 (−6,84 à −3,16) | −3,82 (−6,93 à −0,49) | −2,81 (−6,93 à +0,11) | −2,86 (−6,64 à +0,13) |
| 10 | −0,05 (−2,50 à +1,06) | −0,79 (−3,52 à +0,77) | +0,73 (−0,33 à +1,96) | +0,75 (−0,40 à +2,10) |
| **50** | +1,89 (+0,56 à +3,13) | +1,74 (+0,77 à +2,57) | +1,89 (+0,76 à +3,06) | +2,33 (+1,10 à +3,49) |
| **200** | +3,43 (+3,13 à +3,71) | +3,34 (+2,33 à +5,18) | +2,72 (+1,86 à +3,56) | +2,86 (+2,19 à +3,49) |
| 1 000 | +4,10 (+3,44 à +5,29) | +4,88 (+4,00 à +5,52) | — | — |
| 10 000 | +10,76 (+9,17 à +13,24) | +10,83 (+8,43 à +12,80) | — | — |
| 101 000 | **+36,89** (+30,90 à +43,80) | **+37,19** (+35,98 à +38,96) | — | — |

Jusqu'à 1 000 évaluations, l'évolution n'a encore évalué que sa génération 0, qui est elle-même un tirage au hasard :
évolution et hasard s'y confondent, à la variabilité des graines près.

## Coût de calcul (runner GitHub, Linux, 4 vCPU)

| Camp | Calcul noté par le programme | Durée des jobs |
|---|---|---|
| Évolution D, par graine | 28,7 / 14,2 / 47,9 / 20,5 / 33,2 min (moyenne 28,9 min ; 17,2 ms par évaluation) | 29,6 / 14,8 / 48,8 / 21,3 / 34,2 min |
| Évolution D, 5 graines | 2,41 h | 2,48 h |
| Corps figé, par graine | 49,0 / 23,9 / 14,9 / 34,9 / 45,9 min (moyenne 33,7 min ; 20,0 ms par évaluation) | 50,1 / 24,7 / 15,5 / 35,9 / 46,9 min |
| Corps figé, 5 graines | 2,81 h | 2,88 h |
| Hasard pur, un tirage de 200 | 6,4 à 6,7 s (43,4 s pour le premier du job, compilation numba comprise) | 3,1 min pour les 10 tirages (installation et garde-fou compris) |

- Calcul noté par le programme : somme des `eval_seconds` de `stats.csv` (évaluation et mutations de chaque génération)
  pour l'évolution, temps de l'évaluation pour le hasard ; durée des jobs : `jobs_github.tsv` (API GitHub).
- Le temps d'une graine varie du simple au triple pour la même quantité d'évaluations (101 000) : la cause n'a pas
  été mesurée.
