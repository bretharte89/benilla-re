#!/bin/sh
# Regenerate every table in tables/ from your own WoW.exe (build 5875) at WoW/WoW.exe.
# The generators that read instructions use dumps/disasm.txt; tools/disasm.sh writes it if it is
# missing, the listing the findings cite.
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
exe=WoW/WoW.exe
[ -f "$exe" ] || { echo "regen: $exe not found; see CONTRIBUTING.md, Setup" >&2; exit 1; }
[ -f dumps/disasm.txt ] || tools/disasm.sh
mkdir -p tables
for name in opcodes messages events glue_events event_sites cvars dbc_stores dbc_schemas bindings; do
    python3 "tools/tables/$name.py" -o "tables/$name.tsv"
done
