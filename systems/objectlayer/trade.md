# objectlayer: trade

The client's half of a player-to-player trade: the messages it sends, the two server messages it
handles, and the globals that hold the trade between them.

The trade code is Trade_C.cpp, `0x5d3f60` to `0x5d4b80`. It keeps no object: every piece of
state is a `.data` global between `0xc4bab8` and `0xc4bedc`, written only by this file's
functions. The interface (the trade frame's script functions and the status dispatcher
`0x4bf720`, system `gameui`) calls the senders and reads the state through small getters; the
status handler passes each status to that dispatcher after updating the globals. The client
start code calls `0x5d4780`, which registers the two handlers, and the world teardown calls
`0x5d4b80`, which clears them. The message names are the server's names for these opcodes, a
lead; the code names none of them.

Roots: `0x5d3f60`, `0x5d3f70`, `0x5d3f80`, `0x5d3fa0`, `0x5d3fb0`, `0x5d4080`, `0x5d40e0`, `0x5d4150`, `0x5d41c0`, `0x5d4230`, `0x5d42a0`, `0x5d4310`, `0x5d4380`, `0x5d4480`, `0x5d4500`, `0x5d45f0`, `0x5d4680`, `0x5d4760`, `0x5d4770`, `0x5d4780`, `0x5d47c0`, `0x5d4990`, `0x5d4b80`

## Trade state

Trade_C keeps its state in these globals; no other code in the image addresses them.

| global | type | holds | written by |
|---|---|---|---|
| `0xc4bec8` | `uint32_t` | 1 while a trade this client asked for is pending | `0x5d3fb0` sets; `0x5d4780` and the status tail clear |
| `0xc4becc` | `uint32_t` | the flag the caller gave `0x5d3fb0` | `0x5d3fb0`, `0x5d4780` |
| `0xc4bed0` | `uint64_t` | the trade partner's GUID | `0x5d3fb0`, status 1, `0x5d4780`, the status tail |
| `0xc4bea8` | `uint32_t` | own offer counter | 1 at status 2; +1 per item or money send |
| `0xc4be70` | `uint32_t[2]` | money offered: own, partner's | the money senders, statuses 2, 3, 8, 12, 13, 22, extended |
| `0xc4be78` | `uint32_t[2]` | the second header dword of each side's last extended status | 1 at status 2, extended |
| `0xc4bed8` | `int32_t[2]` | the third header dword of each side's last extended status | 0 at status 2, extended |
| `0xc4bab8` | `TradeSlot[2][7]` | 64-byte item records: own 0 to 6, partner's 7 to 13 | zeroed at statuses 2, 3, 8, 12, 13; extended |

Addresses: `0xc4bab8`, `0xc4be70`, `0xc4be78`, `0xc4bea8`, `0xc4bec8`, `0xc4becc`, `0xc4bed0`, `0xc4bed8`, `0x5d3f60`, `0x5d3f70`, `0x5d3f80`, `0x5d3fa0`, `0x5d4760`, `0x5d4770`, `0x5d4780`, `0x5d4b80`, `0x5ab650`, `0x5ab670`
Confidence: verified
Proof: one
Test: none

A census of `0xc4bab8` to `0xc4bedf` in `dumps/disasm.txt` finds references only inside
`0x5d3f60` to `0x5d4b80` (control: the same pattern finds the stores to 0xc4ba4c in the object file
below). The getters are `0x5d3f60` (`0xc4bed0` in `edx:eax`), `0x5d3f70`
(`0xc4bec8`), `0x5d3fa0` (`[ecx*4+0xc4bed8]`), `0x5d4760` (`0xc4be70`[0]) and `0x5d4770`
(`0xc4be70`[1]). `0x5d3f80` returns 1 only when `0xc4bec8` and `0xc4becc` are both nonzero, else 0.
`0x5d4780` stores zero in `0xc4bec8`, `0xc4becc` and both halves of `0xc4bed0`, then
registers `0x5d47c0` for `0x120` and `0x5d4990` for `0x121` through `0x5ab650` with context 0;
`0x5d4b80` clears both through `0x5ab670`.
The record table spans 14 records of 64 bytes (`0x380`, the `rep stos` count `0xe0` dwords);
`0x5d4b62` passes the partner's half, `0xc4bab8` + `0x1c0`, to `0x4bf2b0`.

## Outgoing trade messages

Each sender builds a data store on its stack, puts the opcode as a `uint32` and the body below,
sends it through `0x5ab630`, and frees the store's buffer. None checks that a trade is open.

| opcode | sender | body | precondition and effect |
|---|---|---|---|
| `0x116` | `0x5d3fb0` | u64 GUID | see Initiating a trade |
| `0x117` | `0x5d40e0` | none | |
| `0x118` | `0x5d4150` | none | |
| `0x119` | `0x5d41c0` | none | |
| `0x11a` | `0x5d4230` | u32 `0xc4be78`[1] | |
| `0x11b` | `0x5d42a0` | none | |
| `0x11c` | `0x5d4310` | none | |
| `0x11d` | `0x5d4380` | u8 trade slot, u8 container index, u8 slot | the active player and the item must exist; counter +1 |
| `0x11e` | `0x5d4480` | u8 trade slot | counter +1 |
| `0x11f` | money senders | u32 copper | see Offering money |

Addresses: `0x5d40e0`, `0x5d4150`, `0x5d41c0`, `0x5d4230`, `0x5d4260`, `0x5d42a0`, `0x5d4310`, `0x5d4380`, `0x5d43af`, `0x5d43da`, `0x5d43f1`, `0x5d4442`, `0x5d4480`, `0x5d44bc`, `0x5ab630`, `0x418190`, `0x418070`, `0x5e13b0`
Confidence: verified
Proof: one
Test: none

Each opens with `push opcode` and `call 0x418190` on a stack data store; the
puts are `0x418190` (four bytes), `0x418070` (one byte) and `0x418370` (eight bytes). `0x5d4260`
loads `0xc4be78` + 4, the partner's entry. `0x5d4380` takes the bag-relative slot in
`ecx`, the trade slot in `edx`, then the item's GUID and a container's GUID on the stack
(`ret 0x10`). It returns 0 with no active player (mask `0x10`, `0x5d43af`) or no item of that
GUID (mask 2, `0x5d43da`); otherwise the second byte is `0x5e13b0(container GUID)` on the
player, the index of that GUID in the player's list at `+0x1d3c` (count `+0x1d38`), or `0xff`
when absent. It puts `edx`, that index, then `ecx`, increments `0xc4bea8` (`0x5d4442`) and
returns 1. `0x5d4480` puts `ecx`'s byte and increments the counter (`0x5d44bc`).

## Initiating a trade

`0x5d3fb0` sends `0x116` with the target's GUID, then stores the GUID in `0xc4bed0`, 1 in
`0xc4bec8` and its `ecx` argument in `0xc4becc`, in that order after the send. It then asks the
player name cache for the target's name with `0x5d4080` as the callback: a cached name
is shown at once as interface error `0xb9` with the name; otherwise the callback, when the name
query answers with its success byte set, looks the name up again without a callback and shows
the same error when it is found.

Addresses: `0x5d3fb0`, `0x5d3ff9`, `0x5d4010`, `0x5d4021`, `0x5d402b`, `0x5d4031`, `0x5d4042`, `0x5d4080`, `0x5d40a0`, `0x5d40ca`, `0x55f080`, `0x496720`
Confidence: verified
Proof: one
Test: none

`0x5d3ff9` sends; `0x5d4010` and `0x5d401c` store the GUID, `0x5d4021` stores 1 and `0x5d402b`
stores the saved `ecx`. The pushes for `0x55f080` are the GUID, a pointer to it, `0x5d4080`, 0
and 0; `0x55f080` copies the eight bytes the pointer names into its pending node
(`0x55f18e` to `0x55f199`), so the pointer is not kept. A nonzero return calls `0x496720(0xb9,
name)` (`0x5d4042`). The callback reads its second stack argument's byte (`0x5d4096`), skips on
zero (`0x5d40a0`), and repeats the lookup with a null callback from the GUID `edx` points to
(`0x5d40bb`), showing `0xb9` on a hit (`0x5d40ca`); `ret 8`. The three callers, in interface
code, pass `ecx` 0 or 1.

## Offering money

Three senders put the own money offer, each as `0x11f` with the new total as a u32, then add 1
to `0xc4bea8` and store the total in `0xc4be70`. `0x5d4500` adds its argument to the offer;
`0x5d4680` sets the offer to its argument; both first require an active player whose money
(player field 1176) is at least the new total, and return 1 when sent, 0 when not. `0x5d4500`
with 0 sends nothing and returns 1. `0x5d45f0` subtracts its argument and sends nothing when
the argument is 0 or above the offer; it checks no money and returns nothing.

Addresses: `0x5d4500`, `0x5d4520`, `0x5d4562`, `0x5d4570`, `0x5d45a5`, `0x5d45b1`, `0x5d45f0`, `0x5d4602`, `0x5d4607`, `0x5d4680`, `0x5d46cf`, `0x5d46dd`, `0x5d471e`
Confidence: verified
Proof: one
Test: none

`0x5d4520` is `lea edi,[eax+ecx]` on `[0xc4be70]` (the add wraps modulo 2^32); `0x5d4562` reads
`[[player+0xe68]+0xf70]`, field 188 + `0xf70`/4 = 1176, after confirming the masked lookup's
GUID equals `0x468550`'s; a mismatch compares 0 instead. `0x5d4570` is `cmp eax,edi; jb` to the
`al = 0` exit, so money equal to the total passes. `0x5d45a5` increments the counter and
`0x5d45b1` stores `edi`; the send follows. `0x5d45f0` jumps out at `je` on `ecx == 0` and at `ja`
when `ecx > [0xc4be70]` (`0x5d4602`), then `sub eax,ecx` (`0x5d4607`). `0x5d4680` repeats
`0x5d4500`'s check against its argument (`0x5d46cf`, `0x5d46dd`) with no zero test, and stores at
`0x5d471e`.

## Trade status message

The handler `0x5d47c0` reads a u32 status. Statuses 0 to 22 then read and do as the table says;
other statuses read nothing and change nothing. "Cleared" means the record table and both money
offers are zeroed. After that, it calls the dispatcher `0x4bf720` with the status in `ecx`, A in
`edx`, then on the stack the byte B != 0, C and D (0 where unread). Last, for the statuses marked
"tail", it zeroes `0xc4bec8` and `0xc4bed0`. It returns 1.

| status | body | effect before the dispatcher | tail |
|---|---|---|---|
| 0, 5, 6, 10, 11, 14 to 21 | none | none | yes |
| 1 | u64 GUID | GUID to `0xc4bed0` | no |
| 2 | none | `0xc4bea8` and both `0xc4be78` to 1; cleared; both `0xc4bed8` to 0 | no |
| 3, 13 | none | cleared; event 200 | yes |
| 4, 7, 9 | none | none | no |
| 8 | none | cleared | yes |
| 12 | i32 A, u8 B, i32 C | cleared | yes |
| 22 | u8 D | `0xff` zeroes the own offer `0xc4be70` | no |

Addresses: `0x5d47c0`, `0x5d47de`, `0x5d47f6`, `0x5d47fd`, `0x5d4804`, `0x5d4825`, `0x5d4864`, `0x5d4884`, `0x5d48a8`, `0x5d48af`, `0x5d48eb`, `0x5d4905`, `0x5d490a`, `0x5d4923`, `0x5d4931`, `0x703e50`, `0x4bf720`
Confidence: verified
Proof: one
Test: none

`0x5d47de` bounds the status with `cmp eax,0x16; ja 0x5d490a`. The byte table at `0x5d496c`
reads `0 1 2 3 7 0 0 7 4 7 0 0 5 3 0 0 0 0 0 0 0 0 6` and the jump table at `0x5d494c` reads
`0x5d4905 0x5d4804 0x5d4825 0x5d4884 0x5d48eb 0x5d48af 0x5d4864 0x5d490a`. Case 0 (`0x5d4905`)
sets `esi`, the tail flag; cases 3, 4 and 5 set it too; 1, 2, 6 and 7 do not. Case 3 calls
`0x703e50` with `ecx = 0xc8` (`0x5d48a8`). Case 6 compares the byte with `0xff` (`0x5d486f`).
The locals A (`[ebp-0xc]`), C (`[ebp-0x8]`) and the byte B are zeroed first; D is only the low
byte of `[ebp-0x4]` (`0x5d47ed`), and the push at `0x5d490a` takes the whole dword. `0x5d4923`
calls the dispatcher; `0x5d4931` to `0x5d493d` clear the globals when `esi` is set.

## Trade extended status message

The handler `0x5d4990` reads a u8 side (0 own, 1 partner) and a u32 sequence. An own-side
message whose sequence is below `0xc4bea8` is dropped. Otherwise it reads u32 into
`0xc4be78[side]`, u32 money into `0xc4be70[side]`, i32 into `0xc4bed8[side]`, then slot
records to the end. Each record, a u8 slot and 60 bytes, is stored as
a 64-byte record at `0xc4bab8 + (side * 7 + slot) * 64`. Slots 0 to 6 the message omitted are
zeroed. On the own side, a slot whose stored item word was nonzero calls `0x4bfbd0(slot)` when
it arrives with item 0 or is omitted. Last it calls `0x4bf2b0` with the partner's records. It
returns 1; side and slot are not bounded.

| order | type | record offset |
|---|---|---|
| 1 to 3 | u32 each (item, display, count by the server's layout) | `+0x00`, `+0x04`, `+0x08` |
| 4 | i32 | `+0x18` |
| 5 | u64 | `+0x20` |
| 6 | u32 | `+0x0c` |
| 7 | u64 | `+0x10` |
| 8 to 13 | i32, i32, u32, i32, u32, u32 | `+0x28` to `+0x3c` |

Addresses: `0x5d4990`, `0x5d49b5`, `0x5d49ba`, `0x5d49ca`, `0x5d49de`, `0x5d49fa`, `0x5d4a0c`, `0x5d4a18`, `0x5d4a23`, `0x5d4aad`, `0x5d4ab7`, `0x5d4ad3`, `0x5d4af8`, `0x5d4afd`, `0x5d4b05`, `0x5d4b20`, `0x5d4b33`, `0x5d4b53`, `0x5d4b67`, `0x4bfbd0`, `0x4bf2b0`
Confidence: verified
Proof: one
Test: none

`0x5d49ba` is `cmp edx,[0xc4bea8]; jb` to the return, reached only with side 0 (`0x5d49b5`). The
loop runs while `[store+0x14] < [store+0x10]` (`0x5d4a0c`, `0x5d4b02`). After the slot (`0x5d4a18`), the reads from `0x5d4a23` to `0x5d4aad`, 60 bytes, go to
`[ebp-0x54]`, `-0x50`, `-0x4c`, `-0x3c`, `-0x34`, `-0x48`, `-0x44`, `-0x2c`, `-0x28`, `-0x24`,
`-0x20`, `-0x1c`, `-0x18`; `rep movs` of 16 dwords from `[ebp-0x54]` (`0x5d4af8`) copies them,
with `+0x1c` (`[ebp-0x38]`) never written: that word is stack left over. `0x5d4afd` marks
`[ebp-0x14+slot]` in a seven-byte array zeroed at `0x5d49f3` to `0x5d4a01`, so a slot above 6
writes past it. The sweep (`0x5d4b20`) zeroes each unmarked record (`0x5d4b53`) and tests
`[0xc4bab8 + slot * 64]` only for side 0 (`0x5d4b28`). A record cut short by the end of the message
leaves its later fields as the previous record's (stack contents for the first).
