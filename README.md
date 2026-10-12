# Sauvegarde des runs par défaut

Cette branche ne contient pas de code. Elle garde une copie des runs d'évolution par défaut du projet, qui sont
hors git dans les branches de code (`runs/` est dans `.gitignore`). Le projet est décrit dans
`docs/PASSATION.md` de la branche `claude/chantier-c-collisions`.

## Contenu

Une archive par graine. Chacune contient `runs/S/` (201 fichiers `gen_0000.npz` à `gen_0200.npz`, `stats.csv`,
`config.json`, `audit.csv`) et le journal d'entraînement `runs/train_sS.log`.

Ce sont les runs du chantier B2 : 200 générations × 1000 créatures, entraînés avec les butées articulaires
(`JOINT_LIMITS = True` dans leur `config.json`).

| Archive | Graine | Champion de la génération 200 | Taille | SHA-256 |
|---|---|---|---|---|
| `runs_0.tar.gz` | 0 | +34,2 m | 24 829 993 octets | `4cfee42c86d3b1f510bb61f5a6cbf99df0a955e3d1e2c9a5279e662f82422e23` |
| `runs_1.tar.gz` | 1 | +33,4 m | 25 132 536 octets | `93f89aca6b9668bbd7db65ceb7e31a5ef283277d900dc6f4a128eafd913ffb3e` |
| `runs_2.tar.gz` | 2 | +35,3 m (référence des écrans) | 24 552 780 octets | `e4a321392f7af91e92d89e05f51157663f299a0a4a3a707e736517ac0107080b` |

## Restaurer

À la racine d'un clone de la branche de code :

```
git fetch origin sauvegarde-runs
git show origin/sauvegarde-runs:runs_2.tar.gz > runs_2.tar.gz
sha256sum runs_2.tar.gz          # doit égaler la valeur du tableau
tar -xzf runs_2.tar.gz           # recrée runs/2 et runs/train_s2.log
```

Même chose pour les graines 0 et 1. Les archives se téléchargent aussi depuis GitHub, sur cette branche.

## Avec quel code

Ces runs se rejouent au bit près (hauteur rejouée = hauteur stockée) avec le code de
`claude/modest-ritchie-mkwjnd` à partir du commit 2a9b55d, et avec `claude/chantier-c-collisions`. Le test
`tests/test_joint_limits.py::test_local_runs_replay_with_their_own_flag` le vérifie quand les runs sont présents.

## S'ils manquaient

Réentraîner, environ 15 à 18 min par graine sur 4 cœurs :

```
python main.py train --seed S --generations 200 --pop 1000 --set AUDIT_EVERY=10
```

Le run est déterministe, mais l'identité au bit près avec ces archives n'est garantie qu'avec les mêmes versions
du code, de numpy, de numba et de la bibliothèque mathématique du système.
