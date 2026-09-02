#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wine_python="${WINE_PYTHON:-C:\\Python3146\\python.exe}"
builder="$(WINEDEBUG=-all winepath -w "$script_dir/tools/build_windows_exe.py")"

exec env WINEDEBUG=-all wine "$wine_python" "$builder" "$@"
