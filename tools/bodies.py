#!/usr/bin/env python3
"""Check every row of symbols/functions.tsv against dumps/disasm.txt (tools/disasm.sh): that the
row starts a function (METHOD.md, Completeness) and that its size is its body's, by the rule in
symbols/README.md. Reads WoW/WoW.exe for jump tables. Prints one line per problem and exits 1 if
there is any."""

import bisect
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINE = re.compile(r'^\s*([0-9a-f]+):\t(.*)$')
DIRECT = re.compile(r'^(j[a-z]+|loop[a-z]*)\s+0x([0-9a-f]+)$')
TABLE = re.compile(r'^jmp\s+DWORD PTR \[e[a-z]{2}\*4\+0x([0-9a-f]+)\]$')
TABLE_READ = re.compile(r'(?:DWORD PTR \[e[a-z]{2}\*4|BYTE PTR \[e[a-z]{2})\+0x([0-9a-f]+)\]')
PADDING = ('nop', 'int3')


def sections(image):
    pe = struct.unpack_from('<I', image, 0x3c)[0]
    count = struct.unpack_from('<H', image, pe + 6)[0]
    optional = struct.unpack_from('<H', image, pe + 20)[0]
    base = struct.unpack_from('<I', image, pe + 52)[0]
    table = pe + 24 + optional
    for i in range(count):
        vsize, va, rawsize, rawptr = struct.unpack_from('<IIII', image, table + 40 * i + 8)
        yield base + va, rawsize, rawptr


def main():
    listing = ROOT / 'dumps' / 'disasm.txt'
    exe = ROOT / 'WoW' / 'WoW.exe'
    if not listing.exists() or not exe.exists():
        print('error: needs dumps/disasm.txt (tools/disasm.sh) and WoW/WoW.exe', file=sys.stderr)
        return 2
    image = exe.read_bytes()
    spans = list(sections(image))

    def dword(va):
        for start, size, raw in spans:
            if start <= va and va + 4 <= start + size:
                return struct.unpack_from('<I', image, raw + va - start)[0]
        return None

    text = {}
    for line in listing.read_text(encoding='utf-8', errors='replace').split('\n'):
        match = LINE.match(line)
        if match:
            text[int(match.group(1), 16)] = ' '.join(match.group(2).split())
    order = sorted(text)

    def following(address):
        i = bisect.bisect_right(order, address)
        return order[i] if i < len(order) else None

    def preceding(address):
        i = bisect.bisect_left(order, address)
        return order[i - 1] if i > 0 else None

    rows = [line.split('\t') for line in
            (ROOT / 'symbols' / 'functions.tsv').read_text(encoding='utf-8').split('\n')[1:] if line]
    starts = {int(r[0], 16) for r in rows}
    jcc_targets, data = set(), set()
    for address, instruction in text.items():
        match = DIRECT.match(instruction)
        if match and match.group(1) != 'jmp':
            jcc_targets.add(int(match.group(2), 16))
        for table in TABLE_READ.findall(instruction):
            if order[0] <= int(table, 16) <= order[-1]:
                data.add(int(table, 16))
    data = sorted(data)

    def after_table(address, entry):
        # A switch's tables sit at the end of its function: what follows one is data, not code.
        i = bisect.bisect_right(data, address)
        return i > 0 and entry - data[i - 1] < 0x400

    def body(entry):
        reached, tables, work = set(), [], [entry]
        while work:
            address = work.pop()
            while address is not None and address in text and address not in reached:
                reached.add(address)
                instruction = text[address]
                if instruction.startswith(('ret', 'int3')):
                    break
                match = DIRECT.match(instruction)
                if match:
                    target = int(match.group(2), 16)
                    if match.group(1) == 'jmp':
                        if target in starts and target != entry:
                            break
                        address = target
                        continue
                    work.append(target)
                elif TABLE.match(instruction):
                    table = int(TABLE.match(instruction).group(1), 16)
                    k = 0
                    while True:
                        value = dword(table + 4 * k)
                        if value is None or not entry <= value < table or value not in text:
                            break
                        work.append(value)
                        k += 1
                    tables.append((table, table + 4 * k))
                    break
                elif instruction.startswith('jmp'):
                    break
                address = following(address)
        return reached, tables

    problems = []
    for row in rows:
        entry, size, name = int(row[0], 16), int(row[1]), row[2]
        where = f'{row[0]} {name}'
        if entry not in text:
            problems.append(f'{where}: not an instruction start in the listing')
            continue
        before = preceding(entry)
        while before is not None and text[before] in PADDING:
            before = preceding(before)
        if (before is not None and not text[before].startswith(('ret', 'jmp', 'int3'))
                and not after_table(before, entry)):
            problems.append(f'{where}: reached by fall-through from {before:#x}, so code of the '
                            'function above')
        if entry in jcc_targets:
            problems.append(f'{where}: a conditional jump lands on it')
        reached, tables = body(entry)
        end = following(max(reached))
        if end - entry != size:
            problems.append(f'{where}: size {size}, body {end - entry}')
        lo = bisect.bisect_left(order, entry)
        for address in order[lo:bisect.bisect_left(order, entry + size)]:
            if address in reached or text[address] in PADDING:
                continue
            if any(start <= address < stop for start, stop in tables):
                continue
            problems.append(f'{where}: {address:#x} lies inside the extent but outside the body')
            break

    for line in problems:
        print(line)
    print(f'{len(rows)} functions: {len(problems)} problems')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
