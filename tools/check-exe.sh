#!/usr/bin/env bash
# Sourced by the other tools: finds the repo root and refuses any WoW.exe but build 5875.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXE="$ROOT/WoW/WoW.exe"
EXE_SIZE=4775986
EXE_SHA256=b4756d38ef207c02ed651f4952bd89a70b4857b73a33413339e1b285b28d2dc7

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

check_exe() {
  [ -f "$EXE" ] || { echo "error: $EXE not found; copy your 1.12.1 WoW.exe there (CONTRIBUTING.md, Setup)" >&2; return 1; }
  local size sum
  size=$(wc -c < "$EXE" | tr -d ' ')
  if [ "$size" != "$EXE_SIZE" ]; then
    echo "error: WoW/WoW.exe is $size bytes, build 5875 is $EXE_SIZE; the addresses here do not apply to it" >&2; return 1
  fi
  sum=$(sha256_of "$EXE")
  if [ "$sum" != "$EXE_SHA256" ]; then
    echo "error: WoW/WoW.exe has SHA-256 $sum, build 5875 is $EXE_SHA256; the addresses here do not apply to it" >&2; return 1
  fi
}
