# collision: replay

Each mover's queue of pending movement events and its replay, in Movement.cpp.

Every `CMovement` keeps the events it has yet to apply in a time-ordered list; spent event nodes
go to one free list the whole client shares. The per-mover step (`mover`) calls `0x615c30` at the
end of each step with the step's end time, and `0x615c30` applies, in order, every event due by
then: a jump table on the event's type runs the matching setter of the shared movement code and
passes the type's opcode, with the event's values, to the unit's move-event handler. The doc also
covers the list helpers the queue and status code share, and the destructor half that releases a
mover's queue.

Roots: `0x617060`

## Event queue and free list

Each mover keeps its pending events at `+0x150`: a list with link offset 0 and the terminator at
`+0x154`, ordered by each event's time at `+0x8`. `0x615820` inserts an event before the first one
whose time is later by signed difference, so equal times keep arrival order. `0x6158e0` returns
the first event or null; `0x6158f0` returns whether there is one. Spent events go to the free list
`0xc4db88`: `0x615910` moves the first event there; `0x6159c0` splices a whole queue onto its end,
with error 0x57 for a null queue, the free list or another link offset.
`0x615a50` empties a queue, spliced when the manager exists, else freed node by node. `0x617060`,
the destructor, runs `0x7c5950` and then `0x615a50` on `+0x150`.

Addresses: `0x615820`, `0x6158e0`, `0x6158f0`, `0x615910`, `0x6159c0`, `0x615a50`, `0x617060`, `0x7c5950`, `0xc4db88`
Confidence: verified
Proof: one
Test: none

`0x61584c sub eax,[ebx+0x8]; js` picks the slot; past the last node `0x615894` links before the
terminator. The head is `[queue+0x8]`, null when odd or zero. `0x615910` unlinks the head and links
it before the free list's terminator (`0x615997` to `0x6159a9`). `0x6159c0` tests `ecx` against 0
and `0xc4db88` and compares link offsets (`0x6159c4` to `0x6159d8`). `0x615a50` tail-jumps to
`0x6159c0` when `0x630a40` is nonzero (`0x615a61`).

## Event replay loop

`0x615c30(t)` applies, in queue order, every event with `t − time ≥ 0`, each in these steps:

| step | action |
|---|---|
| 1 | move the event to the free list |
| 2 | under flag 0x1000, drop it when `0x618030(type)` is 0 (types 0 to 7, 18, 19 and 28) |
| 3 | without byte `+0x4d`, `0x7c6310()` |
| 4 | `F` = the flags; `V = (F & 0x2000) and +0xa0 ≠ 0.0`, NaN counting as unequal |
| 5 | with byte `+0x4c`, flag 0x2000 and the event's flags `+0x30` lacking 0x2000: `0x7c6290()`, a landing |
| 6 | the case for the type at `+0xc` |
| 7 | with `+0x4d`, no message passed on, flags & 0x200f and `F & 0x200f` clear: `0x615b80(t)` |
| 8 | with `+0x4c`, `0x61a770(event)` nonzero and a landing: `0x602d00(t, F, V)` |
| 9 | `0x619030(t)`, then `0x619090(t)` |

It returns 1 when events remain or flags & 0x20ff, else 0.

Addresses: `0x615c30`, `0x615c71`, `0x618030`, `0x7c6310`, `0x61a770`, `0x602d00`, `0x619030`, `0x619090`
Confidence: verified
Proof: one
Test: none

`0x615c63 js` stops at the first event in the future. `0x615c71 test ah,0x10` is the 0x1000 test;
a refusal jumps to `0x616539`, skipping the rest. The table of `0x618030` maps types 8 to 17 and 20
to 27 to 1, and types above 28 return 1. `V` is `fcomp 0.0; test ah,0x44; jp` (`0x615cb1`). Step
7 is `0x615e51` to `0x615e73`, where "passed on" is the case's `ebx`; type 6 without `+0x4d`
enters at `0x615e78`, after it, and type 38 jumps to `0x616539`, past steps 7 to 9. The return
is `0x61654c` to `0x61657a`.

## Replay cases 0 to 19

The jump table at `0x616580` holds 39 cases. A setter runs, and, where stated, its nonzero result
gates the message: `0x60e0a0(t, opcode, +0x4d, a, b)` with `a = b = 0` unless stated. Its result is
"passed on".

| type | setter | opcode |
|---|---|---|
| 0, 1 | `0x7c6ae0(1)`, `0x7c6ae0(0)` | 0xb5, 0xb6, gated |
| 2 | `0x7c6ba0()` | 0xb7, gated |
| 3, 4, 5 | `0x7c6c50(1)`, `0x7c6c50(0)`, `0x7c6d30()` | 0xb8, 0xb9, 0xba, gated |
| 6 | `0x7c61c0()`; on nonzero, `0x602c40` | on nonzero with `+0x4d`, heartbeat `0x600a30(t, 0xee, 0, 0)`, passed on |
| 7 | `0x7c6230(1)` | 0xbb, gated |
| 8, 9, 10 | `0x617c80(1)`, `0x617c80(0)`, `0x7c6dd0()` | 0xbc, 0xbd, 0xbe |
| 11, 12, 13 | `0x7c6df0(1)`, `0x7c6df0(0)`, `0x7c6e30()` | 0xbf, 0xc0, 0xc1 |
| 14, 15 | `0x7c71c0(1)`, `0x7c71c0(0)` | 0xc2, 0xc3 |
| 16 | `0x7c6f30(+0x1c)` | 0xda |
| 17 | `0x615bc0(t, event)` | below |
| 18, 19 | `0x61a230()`, `0x7c6e80()` | 0xca, 0xcb |

`0x615bc0` calls `0x7c6f70(+0x20)`: on 0 it passes 0xdb on; else with `+0x4d` it sends the
heartbeat and returns 1, without it returns 0.

Addresses: `0x616580`, `0x60e0a0`, `0x615bc0`, `0x7c6ae0`, `0x7c6ba0`, `0x7c6c50`, `0x7c6d30`, `0x7c61c0`, `0x602c40`, `0x7c6230`, `0x615eba`, `0x615ec5`, `0x615ed1`, `0x617c80`, `0x7c6dd0`, `0x7c6df0`, `0x7c6e30`, `0x7c71c0`, `0x7c6f30`, `0x615fc6`, `0x7c6f70`, `0x61a230`, `0x7c6e80`
Confidence: verified
Proof: one
Test: none

`0x615cf4 cmp eax,0x26; ja 0x615e51` sends other types to no case; `0x615cfd` jumps through
`0x616580`, read as raw dwords: 0x615d04, 0x615d3a, 0x615d70, 0x615d93, 0x615dc9, 0x615df8,
0x615e17, 0x615eba, 0x615edb, 0x615f09, 0x615f37, 0x616038, 0x616066, 0x616094, 0x615f52,
0x615f80, 0x615fae, 0x615fde, 0x615ff1, 0x61601d for types 0 to 19. Type 7: `0x615eba push 1`, the
gate `0x615ec5 je`, `0x615ed1 push 0xbb`. Type 16 pushes 0xda at `0x615fc6`. The gated cases test
`eax` and jump to `0x615e51` on 0. The heartbeat of type 6 is the call at `0x615e47`; `0x615e4c` sets `ebx` to 1.

## Replay cases 20 to 38

The table continues: 0x616129, 0x61614c, 0x616180, 0x6161b4, 0x6161d7, 0x61620b, 0x6160af, 0x6160ec,
0x61623f, 0x616279, 0x61628d, 0x6162cf, 0x616320, 0x61636b, 0x61637f, 0x6163db, 0x61643f,
0x615e51, 0x6164db. `x` is 1 without `+0x4d`, else whether the unit is the active mover.

| type | action | opcode, a, b |
|---|---|---|
| 20 to 25 | `0x7c7030`, `0x7c7080`, `0x7c70d0`, `0x7c7120`, `0x7c7170`, `0x7c6ff0` with `+0x38` | 0xe3, 0xe5, 0x2db, 0xe7, 0x2dd, 0x2df; `+0x38`, `+0x48` |
| 26, 27 | `0x7c7240(1)`, `0x7c7240(0)`; on nonzero `0x619aa0()` | 0x2ad, gated |
| 28 | `0x6179c0(&+0x38, +0x40, +0x44)` | 0xf0; 0, `+0x48` |
| 29, 30 | `0x7c72e0(1)`, `0x7c72e0(0)`; after the message `0x7c72b0()`, `0x602c40` | 0x2cf; 1.0 or 0.0, `+0x48` |
| 31, 32 | `0x61a580(1, x)`, `0x61a580(0, x)` | 0xf6; 1.0 or 0.0, `+0x48` |
| 33, 34 | `0x7c7280(1)`, `0x7c7280(0)`; 34 then `0x7c61c0()` when `x` | 0x2d0; 1.0 or 0.0, `+0x48` |
| 35 | `0x616d30()` for a live spline with `+0x4d`; then `0x619a00()` | 0xe9; 0, `+0x48`; then `0x61a820(t, 0, F, V, 0)` |
| 36 | `0x7c7370(x)` | 0xeb; 0, `+0x48`; then `0x61a820(t, 0, F, V, 0)` |
| 37 | none | none |
| 38 | `0x617e90(T, &+0x10, +0x1c, 1, +0x4d)`, `T` = `+0x28` and `+0x2c` with `+0x4c`, else 0 | 0xc7; 0, `+0x48` |

In 35 and 36, `F` and `V` are taken again before the setter.

Addresses: `0x7c7030`, `0x616142`, `0x7c7080`, `0x7c70d0`, `0x7c7120`, `0x7c7170`, `0x7c6ff0`, `0x7c7240`, `0x619aa0`, `0x6179c0`, `0x61624d`, `0x616261`, `0x7c72e0`, `0x7c72b0`, `0x61a580`, `0x7c7280`, `0x616d30`, `0x619a00`, `0x61a820`, `0x7c7370`, `0x617e90`
Confidence: verified
Proof: one
Test: none

Type 20 pushes 0xe3 at `0x616142`. Type 28 calls `0x6179c0` at `0x61624d` before pushing 0xf0 at
`0x616261`, so the message carries the applied state. 1.0 is pushed as `0x3f800000`. `x` is built
at `0x6162cf` to `0x6162fd` and its copies. Types 35 and 36 retake `F` and `V` at `0x6163f9` and
`0x61643f`; 36's `V` takes 0 from `ecx`, cleared at `0x615cf0`. Type 38 jumps to `0x616539` after
its message.
