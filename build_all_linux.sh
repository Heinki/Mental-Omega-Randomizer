#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/build_exe_wine.sh" \
    --output "$script_dir/../MentalOmegaRandomizer.exe"
python3 "$script_dir/Archipelago/build_apworld.py" \
    --output-directory "$script_dir/Archipelago"

test -s "$script_dir/../MentalOmegaRandomizer.exe"
test -s "$script_dir/Archipelago/mental_omega.apworld"

printf 'Built release pair:\n  %s\n  %s\n' \
    "$script_dir/../MentalOmegaRandomizer.exe" \
    "$script_dir/Archipelago/mental_omega.apworld"
