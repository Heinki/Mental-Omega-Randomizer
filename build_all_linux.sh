#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Refresh the shared mission snapshots before the launcher packages them.
python3 "$script_dir/Archipelago/build_apworld.py" \
    --output-directory "$script_dir/Archipelago"
"$script_dir/build_exe_wine.sh" \
    --output "$script_dir/../MentalOmegaRandomizer.exe"

test -s "$script_dir/../MentalOmegaRandomizer.exe"
test -s "$script_dir/Archipelago/mental_omega.apworld"

python3 "$script_dir/tools/write_release_manifest.py" \
    --launcher "$script_dir/../MentalOmegaRandomizer.exe" \
    --apworld "$script_dir/Archipelago/mental_omega.apworld"

printf 'Built release pair:\n  %s\n  %s\n' \
    "$script_dir/../MentalOmegaRandomizer.exe" \
    "$script_dir/Archipelago/mental_omega.apworld"
