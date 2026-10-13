#!/usr/bin/env python3
"""tables/messages.tsv: the game UI's message catalogue, the table at 0xb4b498 that 0x496720
indexes.

The table is 465 records of 0x14 bytes:

    +0x00  char*  the GlobalStrings key (looked up as Lua _G[key] by 0x703bf0)
    +0x04  u32    kind: 0 chat composer 0x49a870(chan), 1 UI_INFO_MESSAGE, 2 UI_ERROR_MESSAGE,
                  3 console sink 0x63cd00
    +0x08  char*  sound cue name, or "NONE" for silence
    +0x0c  u32    type tag: 0x44 plays the +0x08 cue; anything else is an error-speech id
    +0x10  u32    chat type handed to 0x49a870, read on kind 0 only

The table is filled once, by the C static initializer [0x484ca0, 0x488408): one straight-line
block with no branch and no ret before 0x488407, whose only calls are 122 to the five-field
setter 0x488410. ebx, esi and edi are loaded once at its head and never rewritten, so a register
set there is still live 465 rows later. The generator decodes the initializer's bytes directly,
tracking constants through mov, push, pop and xor, and counts every byte it cannot decode.
"""

import sys

from lib import Image, addr, note, parse_args, write_table

INIT_START, INIT_END = 0x484CA0, 0x488408
SETTER = 0x488410
BASE, STRIDE, COUNT = 0xB4B498, 0x14, 465
R = {0: 'eax', 1: 'ecx', 2: 'edx', 3: 'ebx', 4: 'esp', 5: 'ebp', 6: 'esi', 7: 'edi'}


def main():
    args = parse_args(__doc__)
    img = Image(args.exe)
    u8, u32 = img.u8, img.u32

    def cstr(va):
        if not va:
            return ''
        o = va - img.base
        return bytes(img.mem[o:img.mem.index(b'\0', o)]).decode('latin1')

    rows, regs, pushes, unknown = {}, {}, [], []

    def store(a, val):
        if BASE <= a < BASE + COUNT * STRIDE:
            rows.setdefault((a - BASE) // STRIDE, {})[(a - BASE) % STRIDE] = val

    va = INIT_START
    while va < INIT_END:
        b = u8(va)
        if 0xB8 <= b <= 0xBF:                                  # mov r32, imm32
            regs[R[b - 0xB8]] = u32(va + 1)
            va += 5
        elif 0x50 <= b <= 0x57:                                # push r32
            pushes.append(regs.get(R[b - 0x50]))
            va += 1
        elif 0x58 <= b <= 0x5F:                                # pop r32
            regs.pop(R[b - 0x58], None)
            va += 1
        elif b == 0x6A:                                        # push imm8
            pushes.append(u8(va + 1))
            va += 2
        elif b == 0x68:                                        # push imm32
            pushes.append(u32(va + 1))
            va += 5
        elif b == 0x33 and (u8(va + 1) & 0xC0) == 0xC0:        # xor r, r
            m = u8(va + 1)
            regs[R[(m >> 3) & 7]] = 0 if (m & 7) == ((m >> 3) & 7) else None
            va += 2
        elif b == 0xC7 and u8(va + 1) == 0x05:                 # mov [abs32], imm32
            store(u32(va + 2), u32(va + 6))
            va += 10
        elif b == 0xA3:                                        # mov [abs32], eax
            store(u32(va + 1), regs.get('eax'))
            va += 5
        elif b == 0x89 and (u8(va + 1) & 0xC7) == 0x05:        # mov [abs32], r32
            store(u32(va + 2), regs.get(R[(u8(va + 1) >> 3) & 7]))
            va += 6
        elif b == 0xE8:                                        # call
            rel = int.from_bytes(img.bytes(va + 1, 4), 'little', signed=True)
            if ((va + 5 + rel) & 0xFFFFFFFF) == SETTER and len(pushes) >= 5 \
                    and regs.get('ecx') is not None:
                chan, tag, sound, kind, key = pushes[-5:]
                i = (regs['ecx'] - BASE) // STRIDE
                rows[i] = {0x00: key, 0x04: kind, 0x08: sound, 0x0C: tag, 0x10: chan}
            pushes = []
            va += 5
        elif b == 0xC3:
            va += 1
        else:
            unknown.append((va, b))
            va += 1

    out, incomplete = [], 0
    for i in sorted(rows):
        r = rows[i]
        if set(r) != {0x00, 0x04, 0x08, 0x0C, 0x10}:
            incomplete += 1
            continue
        out.append((i, addr(BASE + i * STRIDE), cstr(r[0x00]), r[0x04], cstr(r[0x08]),
                    '0x%02x' % r[0x0C], r[0x10]))
    gaps = [i for i in range(COUNT) if i not in rows]
    note('%d rows, %d incomplete, %d gaps, %d undecoded bytes'
         % (len(out), incomplete, len(gaps), len(unknown)))
    for va, b in unknown[:20]:
        note('undecoded 0x%x: 0x%02x' % (va, b))
    write_table(['id', 'address', 'key', 'kind', 'sound', 'type_tag', 'chat_type'], out, args.out)
    return 1 if (incomplete or gaps or unknown) else 0


if __name__ == '__main__':
    sys.exit(main())
