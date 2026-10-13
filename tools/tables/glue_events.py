#!/usr/bin/env python3
"""tables/glue_events.tsv: the event names of the glue screens, by id.

The glue builder 0x46a7b0 hands a second name array, 26 slots at 0xb41e70, to 0x703d90
(`mov edx, 0x1a; mov ecx, 0xb41e70; call 0x703d90` at 0x46a885) in place of the in-game array at
0xbe1198, which rebuilds the dispatch table wholesale. While the glue screens run these 26 are the
only events, and the integer FrameScript_SignalEvent is given indexes this table. The array is
filled the way the in-game one is, by one store per slot from 0x46cc60 (see events.py).
"""

import sys

from lib import Disasm, Image, note, parse_args, write_table
import events


def main():
    args = parse_args(__doc__, disasm=True)
    img, dis = Image(args.exe), Disasm(args.disasm)
    out, bad = events.event_rows(img, dis, events.GLUE_ARRAY, events.GLUE_SLOTS)
    note('%d glue events, %d unresolved' % (len(out), len(bad)))
    write_table(['id', 'name', 'name_address', 'store'], out, args.out)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
