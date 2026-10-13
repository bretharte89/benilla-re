#!/usr/bin/env python3
"""tables/events.tsv: the C-to-Lua event names, by id.

The client keeps an array of event-name pointers at 0xbe1198, 0x225 slots of four bytes. It is
not in the file: a startup routine (0x51ab35 onward) fills it with one store per event,

    mov dword [0xbe1198 + 4*id], <address of the name>

or, where the compiler hoisted one name into a register for several slots, `mov [slot], reg`.
UI_Init passes the array to 0x703d90 (`mov edx, 0x225; mov ecx, 0xbe1198; call 0x703d90` at
0x48fea1), which builds the runtime dispatch table at 0xceef68 as table[i].name = strdup(array[i]).
So the id that FrameScript_SignalEvent 0x703e50 and 0x703f50 are given is the slot index.

A register store takes the name from the nearest earlier `mov reg, imm32` in straight-line
code; the generator refuses a store whose register it cannot resolve that way. 419 slots are
written; the other slots are null. Two ids may carry one name (0 and 2 are both UNIT_PET).

The glue screens swap in a second array (0xb41e70, 26 slots) for the in-game one while they run, so
the same integer names a different event there. That array is written by 0x46cc60 and is
tables/glue_events.tsv.
"""

import re
import sys

from lib import Disasm, Image, addr, note, parse_args, write_table

ARRAY, SLOTS = 0xBE1198, 0x225
GLUE_ARRAY, GLUE_SLOTS = 0xB41E70, 26
STORE = re.compile(r'(?:DWORD PTR )?ds:0x([0-9a-f]+),(.+)$')
MOV_IMM = re.compile(r'(e[a-d]x|e[sd]i|ebp),(0x[0-9a-f]+)$')


def array_stores(img, dis, base, slots):
    """(id, name address, store address) for every store into the array."""
    rows, bad = [], []
    for k, (a, _, mn, ops) in enumerate(dis.ins):
        m = STORE.match(ops)
        if mn != 'mov' or not m:
            continue
        t = int(m.group(1), 16)
        if not base <= t < base + 4 * slots:
            continue
        src = m.group(2)
        if src.startswith('0x'):
            val = int(src, 16)
        else:
            val = None
            for j in range(k - 1, max(0, k - 400), -1):
                _, _, pmn, pops = dis.ins[j]
                mm = MOV_IMM.match(pops) if pmn == 'mov' else None
                if mm and mm.group(1) == src:
                    val = int(mm.group(2), 16)
                    break
                if pmn in ('call', 'ret', 'jmp') or pops.split(',')[0] == src:
                    break
            if val is None:
                bad.append(a)
                continue
        rows.append(((t - base) // 4, val, a))
    return rows, bad


def event_rows(img, dis, base, slots):
    rows, bad = array_stores(img, dis, base, slots)
    out = []
    for i, val, a in sorted(rows):
        name = img.cstr(val)
        if name is None:
            bad.append(a)
            continue
        out.append((i, name, addr(val), addr(a)))
    return out, bad


def main():
    args = parse_args(__doc__, disasm=True)
    img, dis = Image(args.exe), Disasm(args.disasm)
    out, bad = event_rows(img, dis, ARRAY, SLOTS)
    for a in bad:
        note('unresolved store at 0x%x' % a)
    ids = [r[0] for r in out]
    assert len(ids) == len(set(ids)), 'a slot is written twice'
    note('%d events, %d distinct names, %d unresolved'
         % (len(out), len({r[1] for r in out}), len(bad)))
    write_table(['id', 'name', 'name_address', 'store'], out, args.out)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
