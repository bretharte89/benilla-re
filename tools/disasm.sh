#!/usr/bin/env bash
# Writes the full disassembly of .text of WoW/WoW.exe (or $BENILLA_RE_WOW_EXE) to dumps/disasm.txt
# (ignored by git).
# Findings cite instruction addresses of this file: GNU objdump, Intel syntax, address and
# instruction, no raw bytes. Usage: tools/disasm.sh   (OBJDUMP=<path> to choose the binary)
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/check-exe.sh"
check_exe

# The listing's expected SHA-256 under GNU binutils 2.46; another version may format a little
# differently, which is reported, not fatal.
DISASM_SHA256=c7467a57910ca096d509d5f731b1698deaa2147d525b46a19de7ba2f928da194

find_objdump() {
  local c
  for c in "${OBJDUMP:-}" i686-w64-mingw32-objdump x86_64-w64-mingw32-objdump gobjdump objdump; do
    [ -n "$c" ] && command -v "$c" >/dev/null 2>&1 || continue
    # Only GNU objdump, and only one built with the PE target.
    "$c" --version 2>&1 | head -1 | grep -q 'GNU' || continue
    "$c" -i 2>&1 | grep -q '^pei-i386' || continue
    command -v "$c"; return 0
  done
  return 1
}

OD=$(find_objdump) || {
  echo "error: no GNU objdump with the pei-i386 target found; see CONTRIBUTING.md, Setup" >&2; exit 1; }
echo "using $("$OD" --version | head -1) at $OD"

mkdir -p "$ROOT/dumps"
OUT="$ROOT/dumps/disasm.txt"
# Run beside the exe so the listing's header names WoW.exe, not a path on this machine.
( cd "$(dirname "$EXE")" && "$OD" -d -M intel --no-show-raw-insn --section=.text "$(basename "$EXE")" ) > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"

sum=$(sha256_of "$OUT")
echo "wrote dumps/disasm.txt: $(wc -l < "$OUT" | tr -d ' ') lines, SHA-256 $sum"
if [ "$sum" != "$DISASM_SHA256" ]; then
  echo "note: this differs from the reference listing ($DISASM_SHA256); another binutils version can" >&2
  echo "      format differently. Citations are instruction addresses, which do not change." >&2
fi
