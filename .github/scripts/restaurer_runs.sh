#!/usr/bin/env bash
# Restaure les runs de référence depuis la branche sauvegarde-runs (dispositions de la v2), SHA-256 vérifiés :
#   runs/S                      chantier D : report dissipatif, mains, cône de 15° (défaut depuis la v1.1 ; graines 0 à 4)
#   runs/corps_fige/S           v2, témoins de la manche 1 : moteur D à corps figé (graines 0 à 4)
#   runs/butees_corps_30/S      C2, cône de 30° (défaut de la v1.0)
#   runs/butees_articulaires/S  B2 (butées articulaires seules)
#   runs/butees_corps/S         C2, cône de 6° (rapport C2)
set -euo pipefail
git fetch --depth=1 origin sauvegarde-runs
archives=()
for s in 0 1 2; do archives+=("runs_butees_corps_30_$s" "runs_butees_corps_$s" "runs_$s"); done
for s in 0 1 2 3 4; do archives+=("runs_chantier_d_$s" "runs_corps_fige_$s"); done
for a in "${archives[@]}"; do git show "FETCH_HEAD:$a.tar.gz" > "$a.tar.gz"; done
cat > runs.sha256 <<'FIN'
77159428c7b698ff81af0e4a94662d875d09d185aa8e17890d329b5e6cc6a1be  runs_chantier_d_0.tar.gz
30cb901482ed91475d7f236e7aebb2ce71bb728814b6e5ca662f1d2bb5192118  runs_chantier_d_1.tar.gz
12cfa917c89dbc02b7c8d5e40a5da9146dcbe8c686b8d73190f31a262efce7fa  runs_chantier_d_2.tar.gz
55b13ac7901f18a3ad9f1a23fb8f4d9556448ea1b928e2303f6a682fdf386ca0  runs_chantier_d_3.tar.gz
0080a06b0886bc37d355ef21d46ac210d5445543e7516b57c32d4cb2c033a38d  runs_chantier_d_4.tar.gz
dd3174c153d23e0489f94f68f4028ea12d067826f432bfafd74fdc380ba39245  runs_corps_fige_0.tar.gz
c937f849b02e8053d3d7edd1b37668ad1ac188ff5664ad6855c2b6a51fd0753f  runs_corps_fige_1.tar.gz
0a4a811c5168eef4ca8d1bf6c5583aba6339f7b9556fb15bc337e9197ed87b4b  runs_corps_fige_2.tar.gz
03600f8e7cba8c95c702299e915b03993e5749a7b53e96e10fb427866e8c5cc7  runs_corps_fige_3.tar.gz
83ee2f9603544f2740161975e97d0834a01ba7fca3641e6f55614c2a50dc2104  runs_corps_fige_4.tar.gz
76ff29a110fc84350ea6480059e92a0b0c0fbba0205a4db080fda3d9334df21e  runs_butees_corps_30_0.tar.gz
626983d2845b66f18956c8e21e42955c0d7e9b720c270bb3385aae1e241edf59  runs_butees_corps_30_1.tar.gz
56ffbf7e52f692c0d3b3b87253cfa517e2dee1c9f4f5ff39feffc19aef444fe9  runs_butees_corps_30_2.tar.gz
bf9be312e079e77a085b09b9be42af16ba60f3ed46549a7fb2452bae8346aba0  runs_butees_corps_0.tar.gz
174fc06d232e50aa7253d4eb7a208c52a7fa6ea7c7d79ecf39824869d73f35e3  runs_butees_corps_1.tar.gz
a3f357f4aaad54b25e3ff0bf96882f3620ddb3ecab312d49d94b717a362780b2  runs_butees_corps_2.tar.gz
4cfee42c86d3b1f510bb61f5a6cbf99df0a955e3d1e2c9a5279e662f82422e23  runs_0.tar.gz
93f89aca6b9668bbd7db65ceb7e31a5ef283277d900dc6f4a128eafd913ffb3e  runs_1.tar.gz
e4a321392f7af91e92d89e05f51157663f299a0a4a3a707e736517ac0107080b  runs_2.tar.gz
FIN
sha256sum -c runs.sha256
mkdir -p runs/butees_articulaires
for s in 0 1 2; do tar -xzf "runs_$s.tar.gz" && mv "runs/$s" "runs/butees_articulaires/$s"; done
for s in 0 1 2 3 4; do tar -xzf "runs_chantier_d_$s.tar.gz" && mv "runs/chantier_d/$s" "runs/$s"; done
for s in 0 1 2 3 4; do tar -xzf "runs_corps_fige_$s.tar.gz"; done
rmdir runs/chantier_d
for s in 0 1 2; do tar -xzf "runs_butees_corps_30_$s.tar.gz"; done
for s in 0 1 2; do tar -xzf "runs_butees_corps_$s.tar.gz"; done
rm -f runs_*.tar.gz runs.sha256
ls runs
