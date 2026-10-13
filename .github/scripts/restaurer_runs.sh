#!/usr/bin/env bash
# Restaure les runs de référence depuis la branche sauvegarde-runs (dispositions de la v1), SHA-256 vérifiés :
#   runs/S                      C2, cône de 30° (runs par défaut depuis la v1)
#   runs/butees_articulaires/S  B2 (butées articulaires seules)
#   runs/butees_corps/S         C2, cône de 6° (rapport C2)
set -euo pipefail
git fetch --depth=1 origin sauvegarde-runs
archives=()
for s in 0 1 2; do archives+=("runs_butees_corps_30_$s" "runs_butees_corps_$s" "runs_$s"); done
for a in "${archives[@]}"; do git show "FETCH_HEAD:$a.tar.gz" > "$a.tar.gz"; done
cat > runs.sha256 <<'FIN'
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
for s in 0 1 2; do tar -xzf "runs_butees_corps_30_$s.tar.gz" && mv "runs/butees_corps_30/$s" "runs/$s"; done
rmdir runs/butees_corps_30
for s in 0 1 2; do tar -xzf "runs_butees_corps_$s.tar.gz"; done
rm -f runs_*.tar.gz runs.sha256
ls runs
