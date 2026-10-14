# Sauvegarde des runs de Gecko (ex-EVO)

Cette branche ne contient pas de code. Elle garde une copie des runs d'évolution de référence du projet. Dans les
branches de code, ces runs sont hors git (`runs/` est dans `.gitignore`). Le projet est décrit dans
`docs/PASSATION.md` de la branche `main`.

Depuis le tag `v1.1`, **les runs par défaut sont ceux du chantier D** (graines 0 à 4 depuis la v2 : chaque camp du duel
joue 5 fois) : report dissipatif de la projection, butées des
mains, cône de queue de 15°. Les runs de C2 à 30°, défaut de la v1.0, sont dans `runs/butees_corps_30/S`. Ceux de B2
restent sous leur nom d'origine. Les témoins de la manche 1 de la v2 (évolution à corps figé, `FROZEN_BODY = True`, moteur
D) sont dans `runs/corps_fige/S`.

## Contenu

Chaque archive contient un run de 200 générations × 1 000 créatures :
- les fichiers `gen_0000.npz` à `gen_0200.npz` ;
- `stats.csv`, `config.json`, `audit.csv` ;
- le journal d'entraînement.

Pour C2, D et les témoins s'y ajoute `pip_freeze.txt`, l'environnement du runner GitHub.

| Archive | Contenu de l'archive | Place dans le dépôt depuis la v1.1 | Champion gén. 200 | Taille (octets) | SHA-256 |
|---|---|---|---|---|---|
| `runs_chantier_d_0.tar.gz` | `runs/chantier_d/0`, `runs/train_chantier_d_s0.log` | `runs/0` (défaut) | +30,9 m | 24 719 195 | `77159428c7b698ff81af0e4a94662d875d09d185aa8e17890d329b5e6cc6a1be` |
| `runs_chantier_d_1.tar.gz` | `runs/chantier_d/1`, `runs/train_chantier_d_s1.log` | `runs/1` (défaut) | +40,9 m | 24 916 068 | `30cb901482ed91475d7f236e7aebb2ce71bb728814b6e5ca662f1d2bb5192118` |
| `runs_chantier_d_2.tar.gz` | `runs/chantier_d/2`, `runs/train_chantier_d_s2.log` | `runs/2` (défaut, écrans) | +43,6 m | 24 931 198 | `12cfa917c89dbc02b7c8d5e40a5da9146dcbe8c686b8d73190f31a262efce7fa` |
| `runs_chantier_d_3.tar.gz` | `runs/chantier_d/3`, `runs/train_chantier_d_s3.log` | `runs/3` (défaut, v2) | +33,8 m | 24 044 333 | `55b13ac7901f18a3ad9f1a23fb8f4d9556448ea1b928e2303f6a682fdf386ca0` |
| `runs_chantier_d_4.tar.gz` | `runs/chantier_d/4`, `runs/train_chantier_d_s4.log` | `runs/4` (défaut, v2) | +34,5 m | 24 345 935 | `0080a06b0886bc37d355ef21d46ac210d5445543e7516b57c32d4cb2c033a38d` |
| `runs_corps_fige_0.tar.gz` | `runs/corps_fige/0`, `runs/train_corps_fige_s0.log` | `runs/corps_fige/0` (témoin v2, manche 1) | +36,7 m | 22 408 650 | `dd3174c153d23e0489f94f68f4028ea12d067826f432bfafd74fdc380ba39245` |
| `runs_corps_fige_1.tar.gz` | `runs/corps_fige/1`, `runs/train_corps_fige_s1.log` | `runs/corps_fige/1` (témoin v2, manche 1) | +36,0 m | 22 961 059 | `c937f849b02e8053d3d7edd1b37668ad1ac188ff5664ad6855c2b6a51fd0753f` |
| `runs_corps_fige_2.tar.gz` | `runs/corps_fige/2`, `runs/train_corps_fige_s2.log` | `runs/corps_fige/2` (témoin v2, manche 1) | +38,1 m | 22 163 428 | `0a4a811c5168eef4ca8d1bf6c5583aba6339f7b9556fb15bc337e9197ed87b4b` |
| `runs_corps_fige_3.tar.gz` | `runs/corps_fige/3`, `runs/train_corps_fige_s3.log` | `runs/corps_fige/3` (témoin v2, manche 1) | +37,3 m | 23 002 829 | `03600f8e7cba8c95c702299e915b03993e5749a7b53e96e10fb427866e8c5cc7` |
| `runs_corps_fige_4.tar.gz` | `runs/corps_fige/4`, `runs/train_corps_fige_s4.log` | `runs/corps_fige/4` (témoin v2, manche 1) | +36,5 m | 22 473 196 | `83ee2f9603544f2740161975e97d0834a01ba7fca3641e6f55614c2a50dc2104` |
| `runs_butees_corps_30_0.tar.gz` | `runs/butees_corps_30/0`, `runs/train_butees_corps_30_s0.log` | `runs/butees_corps_30/0` | +39,5 m | 23 976 495 | `76ff29a110fc84350ea6480059e92a0b0c0fbba0205a4db080fda3d9334df21e` |
| `runs_butees_corps_30_1.tar.gz` | `runs/butees_corps_30/1`, `runs/train_butees_corps_30_s1.log` | `runs/butees_corps_30/1` | +37,1 m | 24 302 513 | `626983d2845b66f18956c8e21e42955c0d7e9b720c270bb3385aae1e241edf59` |
| `runs_butees_corps_30_2.tar.gz` | `runs/butees_corps_30/2`, `runs/train_butees_corps_30_s2.log` | `runs/butees_corps_30/2` | +42,8 m | 24 989 159 | `56ffbf7e52f692c0d3b3b87253cfa517e2dee1c9f4f5ff39feffc19aef444fe9` |
| `runs_butees_corps_0.tar.gz` | `runs/butees_corps/0`, `runs/train_butees_corps_s0.log` | `runs/butees_corps/0` | +38,9 m | 25 580 397 | `bf9be312e079e77a085b09b9be42af16ba60f3ed46549a7fb2452bae8346aba0` |
| `runs_butees_corps_1.tar.gz` | `runs/butees_corps/1`, `runs/train_butees_corps_s1.log` | `runs/butees_corps/1` | +33,9 m | 24 831 091 | `174fc06d232e50aa7253d4eb7a208c52a7fa6ea7c7d79ecf39824869d73f35e3` |
| `runs_butees_corps_2.tar.gz` | `runs/butees_corps/2`, `runs/train_butees_corps_s2.log` | `runs/butees_corps/2` | +48,5 m | 24 284 829 | `a3f357f4aaad54b25e3ff0bf96882f3620ddb3ecab312d49d94b717a362780b2` |
| `runs_0.tar.gz` | `runs/0`, `runs/train_s0.log` | `runs/butees_articulaires/0` | +34,2 m | 24 829 993 | `4cfee42c86d3b1f510bb61f5a6cbf99df0a955e3d1e2c9a5279e662f82422e23` |
| `runs_1.tar.gz` | `runs/1`, `runs/train_s1.log` | `runs/butees_articulaires/1` | +33,4 m | 25 132 536 | `93f89aca6b9668bbd7db65ceb7e31a5ef283277d900dc6f4a128eafd913ffb3e` |
| `runs_2.tar.gz` | `runs/2`, `runs/train_s2.log` | `runs/butees_articulaires/2` | +35,3 m | 24 552 780 | `e4a321392f7af91e92d89e05f51157663f299a0a4a3a707e736517ac0107080b` |

**Provenance des runs** :
- **D** (défaut, `CLEAN_PROJECTION = True`, `HAND_LIMITS = True`, `TAIL_CONE_DEG = 15`) : run GitHub Actions
  38411711297 (graines 0 à 2) ; graines 3 et 4 : run 38594982071 (v2, GECKO-10) ;
- **Témoins à corps figé** (v2, manche 1 : moteur D, `FROZEN_BODY = True`) : runs 38591806655 (graines 0 à 2) et
  38594977725 (graines 3 et 4) ;
- **C2 à 30°** (référence de la v1.0, `BODY_LIMITS = True`, `TAIL_CONE_DEG = 30`) : run 38278062446 ;
- **C2 à 6°** (pour le rapport C2) : run 38266975229 ;
- **B2** (butées articulaires seules, `JOINT_LIMITS = True`) : conteneur cloud, chantier B2.

Rapports : `docs/journal_v2.md` (v2), `docs/chantier_d.md`, `docs/chantier_c_c2.md` et `docs/chantier_b_b2.md`.

## Restaurer (dispositions de la v2)

À la racine d'un clone de la branche de code, avec bash (le runner GitHub, Linux, macOS) :

```
git fetch origin sauvegarde-runs
for a in runs_chantier_d_{0..4} runs_corps_fige_{0..4} runs_butees_corps_30_{0..2} runs_butees_corps_{0..2} runs_{0..2}; do
  git show "FETCH_HEAD:$a.tar.gz" > "$a.tar.gz"
done
sha256sum runs_*.tar.gz            # comparer au tableau
mkdir -p runs/butees_articulaires
for s in 0 1 2; do tar -xzf runs_$s.tar.gz && mv runs/$s runs/butees_articulaires/$s; done
for s in 0 1 2 3 4; do tar -xzf runs_chantier_d_$s.tar.gz && mv runs/chantier_d/$s runs/$s; done
for s in 0 1 2 3 4; do tar -xzf runs_corps_fige_$s.tar.gz; done
rmdir runs/chantier_d
for s in 0 1 2; do tar -xzf runs_butees_corps_30_$s.tar.gz; done
for s in 0 1 2; do tar -xzf runs_butees_corps_$s.tar.gz; done
```

Ces commandes recréent :
- `runs/S` : D (graines 0 à 4) ;
- `runs/corps_fige/S` : témoins à corps figé de la v2 (graines 0 à 4) ;
- `runs/butees_corps_30/S` : C2 à 30° ;
- `runs/butees_corps/S` : C2 à 6° ;
- `runs/butees_articulaires/S` : B2.

Les journaux d'entraînement restent dans `runs/`. Le workflow `.github/workflows/train.yml` restaure de la même façon
(`.github/scripts/restaurer_runs.sh`).

Sous Windows (PowerShell 5.1), ne pas rediriger `git show` vers un fichier, car la redirection abîme les octets.
Cloner plutôt cette branche (`git clone --branch sauvegarde-runs --single-branch …`), ou télécharger les archives
depuis GitHub.

## Avec quel code

Ces runs se rejouent au bit près (hauteur rejouée = hauteur stockée) avec le code de `main` à partir du tag `v1.1`, **sur
Linux** (runner GitHub ubuntu-24.04, Python 3.11, numpy 2.4.6, numba 0.67.0). Le test
`tests/test_joint_limits.py::test_local_runs_replay_with_their_own_flag` le vérifie quand les runs sont présents. Chaque
run se rejoue avec sa propre config (`config.json`) : les drapeaux absents d'un run plus ancien valent False.
Sous Windows, la bibliothèque mathématique diffère et les rejeux divergent.

## S'ils manquaient

Réentraîner sur le runner GitHub, en 15 à 49 min par graine pour D :

```
gh workflow run train.yml --ref main -f mode=train -f run_name=<nom> -f generations=200
```

Le run est déterministe sur une même machine. L'identité au bit près avec ces archives n'est garantie qu'avec les
mêmes versions du code, de numpy, de numba et de la bibliothèque mathématique du système.
