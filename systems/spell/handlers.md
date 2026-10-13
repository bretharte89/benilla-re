# spell: handlers

The server's spell messages: their registration, their fields, the cast bar's events and the cast
result's effect on the cast slots.

`Spell_C::SystemInitialize` (`Spell_C.cpp`) registers 22 message handlers on the world session and
zeroes the cast state; `Spell_C::Destroy` clears the same 22. This topic covers the handlers for the
cast result, the cast delay, the channel start and update, the start and go dispatch with the start
path, and five small messages; the go path is in `go`, and the other handlers the table names belong
to `cooldowns`, `failures` and `records`. The state the handlers read and write is fixed globals of
`Spell_C.cpp`: the in-flight spell id and its caster, the saved slot that holds a cast the in-flight
one displaced, the pending cast record, the auto-repeat spell and the targeting flag word. The cast
bar's events carry the packet's millisecond values unchanged; the client keeps no cast timer of its
own here. The rest of the client reaches this topic through the two lifecycle calls, the network
dispatch, and the hostility classifier, which the object layer calls.

Roots: `0x6e7150`, `0x6e99e0`, `0x6e7330`, `0x6e74f0`, `0x6e7550`, `0x6e75f0`, `0x6e7640`, `0x6e9790`, `0x6e9800`, `0x6e9820`, `0x6e98d0`, `0x6e99d0`, `0x6ea280`

## System initialization and teardown

`0x6e7150` registers 22 opcodes with context 0, each pair in the table's order. It zeroes both
1856-entry spell modifier tables, the flag word, the in-flight and saved slots with their guids, the
auto-repeat spell, the class family and one more spell id, and registers the CVar `autoSelfCast`
(default `"0"`). It registers no Lua function. `0x6e99e0` clears the same 22 opcodes and tail-jumps
to `0x6e9ad0`.

| opcodes | handlers | topic |
|---|---|---|
| `0x130` | `0x6e7330` | `handlers` |
| `0x131`, `0x132` | `0x6e7640` for both | `handlers`, `go` |
| `0x1e2` | `0x6e74f0` | `handlers` |
| `0x139`, `0x13a` | `0x6e7550`, `0x6e75f0` | `handlers` |
| `0x1f3`, `0x29c`, `0x2a7`, `0x2b4`, `0x330` | `0x6e98d0`, `0x6e99d0`, `0x6e9790`, `0x6e9800`, `0x6e9820` | `handlers` |
| `0x133`, `0x138`, `0x173`, `0x2a6` | `0x6e8d80`, `0x6e8eb0`, `0x6e97e0`, `0x6e8e40` | `failures` |
| `0x134`, `0xb0`, `0x1e1` | `0x6e9460`, `0x6e95d0`, `0x6e9730` | `cooldowns` |
| `0x135`, `0x1de` | `0x6e9670` for both | `cooldowns` |
| `0x266`, `0x267` | `0x6e9950` for both | `records` |

Addresses: `0x6e7150`, `0x6e72c4`, `0x6e72d6`, `0x6e731d`, `0x6e99e0`, `0x6e9abc`, `0x5ab650`, `0x5ab670`, `0x63db90`, `0xcead60`, `0xcecb30`, `0xcecac0`, `0xceca88`, `0xcecab0`, `0xcecaa8`, `0xcecb20`, `0xceac30`, `0xcecad8`, `0xcecaac`, `0xceac34`, `0x870dc0`
Confidence: verified
Proof: one
Test: none

Each registration is `push 0; mov edx,handler; mov ecx,opcode; call 0x5ab650` (`0x6e7154` to
`0x6e72af`). Two `rep stos` of `0x740` dwords zero `0xcead60` and `0xcecb30` (`0x6e72c4`,
`0x6e72d6`); 1856 is 64 × 29. Stores of 0 follow: the word `0xcecac0`, and `0xceca88`, `0xcecab0`
with its high half, `0xcecaa8`, `0xcecb20` with its high half, `0xceac30`, `0xcecad8`, `0xcecaac`.
`0x6e731d` is `CVar::Register` with the name `autoSelfCast` (`0x870dc0`, loaded at `0x6e72db`) in `ecx`, 0 in `edx`, and on the stack
0, the default `"0"`, 0, the category 5, 0, 0; `0x6e7323` stores the record at `0xceac34`. The
body has no other call: none to the Lua registrar. `0x6e99e0` is 22 `mov ecx,opcode; call 0x5ab670`
in the same order, then `jmp 0x6e9ad0` (`0x6e9abc`). The in-flight id `0xceca88` has three
writers, this store, the push `0x6e4af8` and the pop `0x6e4b3d`.

## Handler calling convention

Every handler here is `fastcall(context, opcode, time, store)` and returns 1 with `ret 8`; none reads
the time. Fields are read from the data store with fixed-width little-endian readers: a byte, a
16-bit word, a 32-bit dword (three readers, identical in width), a 64-bit guid, and a packed guid,
which is a mask byte followed by one byte for each set bit, low bit first, filling that byte of the
guid. A reader that finds fewer bytes left than its width writes nothing and moves the cursor past
the end, so the destination keeps whatever it held.

Addresses: `0x418cb0`, `0x418db0`, `0x418e30`, `0x418e3f`, `0x418eb0`, `0x418fb0`, `0x4190b0`, `0x642ed0`
Confidence: verified
Proof: one
Test: none

The readers test cursor `+0x14` plus 1, 2, 4, 4, 4 and 8 against the size (`0x418cbc`, `0x418dbc`,
`0x418e3c`, `0x418ebc`, `0x418fbc`, `0x4190bc`) and advance by the same. In `0x418e30`, `cmp edx,ecx; jbe` on cursor + 4 against the size
`+0x10` (`0x418e3f`) falls to `inc ecx; mov [esi+0x14],ecx` without a store. `0x642ed0` zeroes the
guid, reads the mask, and for bit `k` of 0 to 7 that is set reads a byte, shifts it left by `8k`
(`0x642f13`) and ORs it in. The handlers' `ret 8` and their reads of `[ebp+0xc]` as the store fix the
convention; `dispatch` passes the time and the store.

## Cast result

`SMSG_CAST_RESULT` (`0x130`): a dword spell id, a status byte, and for status 2 a reason byte and up
to two dwords. Each dword is read only when at least one byte remains, and is -1 otherwise or when
fewer than four remain. For status 2 the handler calls `0x6e1a00` (spell id, reason, first dword,
second dword, 1); then, unless the reason is `0x3c`, a spell whose record has bit 25 of the dword
at `+0x18` gets `0x6e3050` (spell id, 0, 0, 1) on the player's cooldown list (`cooldowns`). Any
other status skips both. Every status then goes on to the slot handling (In-flight cast reply).

Addresses: `0x6e7330`, `0x6e7356`, `0x6e735a`, `0x6e736e`, `0x6e737a`, `0x6e73ac`, `0x6e73cc`, `0x6e73d6`, `0x6e73e6`, `0x6e73eb`, `0x6e1a00`, `0x6e3050`, `0xc0d780`
Confidence: verified
Proof: one
Test: none

`0x6e7346` reads the id, then the status into `[ebp+0xf]`, the high byte of the store argument, so
a packet that ends there leaves that byte. `0x6e7356 cmp byte [ebp+0xf],2; jne 0x6e73eb`. The
reason goes to `[ebp-0x1]`, zeroed first. `0x6e736e` sets both locals to -1; `cmp eax,ecx; jae` on
cursor and size (`0x6e737a`, `0x6e738c`) skips each read. `0x6e73ac` calls `0x6e1a00` with the id in
`ecx`, the reason in `dl` and the pushes 1, second, first. The record is the Spell store's id map
(`+0x08`, bounded by `+0x0c`); `0x6e73cc cmp reason,0x3c; je`, `0x6e73d6 test [eax+0x18],0x2000000`,
then `0x6e73e6` with the record's id in `ecx`, `edx` 0, pushes 1 and 0. `0x6e3050` passes them to
`0x6e1790` on the list `0xcecaec + 0x18·0`.

## In-flight cast reply

Next, a result for the saved slot's spell clears that slot. One for the in-flight spell restores
the saved slot into the in-flight slot through `0x6e4940`, which sends no cancel and fires `SPELLCAST_STOP` (338) when the pending cast's caster is the player. The record's
dword `+0x98` (column 38) names a next spell: the running auto-repeat spell re-arms the
pending cast record, any other is cast at once through `0x6e5a90`. Another spell's result fires
`SPELLCAST_STOP` when nothing is in flight and the status is not 2. A failure's `0x6e1a00` has
already restored the slots at `0x6e2218` unless it returned earlier, so a failed in-flight spell
chains its next spell only then, or when the saved slot held the same spell.

Addresses: `0x6e73ee`, `0x6e73f6`, `0x6e7408`, `0x6e741a`, `0x6e7447`, `0x6e7455`, `0x6e745b`, `0x6e745d`, `0x6e746a`, `0x6e74a6`, `0x6e74aa`, `0x6e74bc`, `0x6e74cb`, `0x6e4940`, `0x6e4ad0`, `0x6e5a90`, `0x6e4b60`, `0x6e3d30`, `0x6e2201`, `0x6e2218`, `0xceac48`, `0xceac50`, `0xceac58`
Confidence: verified
Proof: one
Test: none

`0x6e73ee` compares with `0xcecaa8` and zeroes it, `0xcecb20` and its high half. `0x6e7408` compares
with `0xceca88`; `0x6e741a` calls `0x6e4940` with `cl` and `dl` 0 and the push `0x1c`. There
`0x6e4ad0(0, 0)` copies `0xcecaa8` into `0xceca88` and `0xcecb20` into `0xcecab0`, and `0x6e4a50`
fires 338 for `cl` 0 when `0xceac50` equals the active player, then clears it. `0x6e7447` loads
`+0x98`; `0x6e7455` compares it with `0xceac30`. Equal: `rep stos` of 64 dwords at `0xceac48`
(`0x6e746a`), the spell at `0xceac58`, the player's guid at `0xceac48` and `0xceac50`. Otherwise
`0x6e74aa` calls `0x6e5a90` with the spell in `ecx`, `edx` 0 and two zero pushes (`0x6e74a6`); it calls
`0x6e4b60` for the active player. `0x6e74bc` calls `0x6e3d30`, which is `[0xceca88] != 0`; `0x6e74c5`
skips status 2; `0x6e74cb` signals `0x152`. In `0x6e1a00`, `0x6e2201` compares its spell with
`0xceca88` and `0x6e2218` calls `0x6e4940(1, arg3 == 0, reason)`; reason `0x17` exits before it
(`0x6e1ce4`, `0x6e1cfa`).

## Cast delayed

`SMSG_SPELL_DELAYED` (`0x1e2`): a 64-bit guid and a dword. When the guid is the active player's, the
client fires `SPELLCAST_DELAYED` (341) with the dword as its one argument (`%d`), the delay in
milliseconds as the server sent it. No state changes; another unit's delay is ignored.

Addresses: `0x6e74f0`, `0x6e7500`, `0x6e750b`, `0x6e7518`, `0x6e7532`, `0x468550`, `0x703f50`
Confidence: verified
Proof: one
Test: none

`0x6e7500` reads 8 bytes, `0x6e750b` 4 bytes into `[ebp+0xc]`. `0x468550` returns the player's guid
in `edx:eax`; `0x6e7518` and `0x6e7520` compare both halves. `0x6e7532` calls `0x703f50` with `0x155`,
the format `%d` and the dword.

## Channel start and update

`MSG_CHANNEL_START` (`0x139`): a dword spell id and a dword duration. With a duration above 0 as a
signed value, a record, and bit 13 of the record's dword `+0x24` clear, the client fires
`SPELLCAST_CHANNEL_START` (342) with the duration and a name (`%d%s`): the spell's localized name
when bit 29 of the dword `+0x1c` is set, else the localized `CHANNELING` text. `MSG_CHANNEL_UPDATE`
(`0x13a`): a dword; nonzero fires `SPELLCAST_CHANNEL_UPDATE` (343) with it (`%d`), zero fires
`SPELLCAST_CHANNEL_STOP` (344). Neither checks the caster or writes state.

Addresses: `0x6e7550`, `0x6e7574`, `0x6e7590`, `0x6e7595`, `0x6e759a`, `0x6e75a1`, `0x6e75a9`, `0x6e75bc`, `0x6e75d0`, `0x6e75f0`, `0x6e7604`, `0x6e7611`, `0x6e7627`, `0x703bf0`, `0xc0e080`
Confidence: verified
Proof: one
Test: none

`0x6e7574` is `jle` on the duration. `0x6e7590` skips a null record. `0x6e7595 test ch,0x20` on
`+0x24`; `0x6e759a test [eax+0x1c],0x20000000`. The name is `[rec + 4·[0xc0e080] + 0x1e0]`
(`0x6e75a9`), or `0x703bf0("CHANNELING", -1, 0)` (`0x6e75bc`). `0x6e75d0` pushes the name, then the
duration, so the format's order is duration, name. `0x6e7604` tests the update's dword: `0x6e7611`
signals `0x157`, `0x6e7627` signals `0x158` with `0x703e50`.

## Start and go dispatch

`0x6e7640` handles `SMSG_SPELL_START` (`0x131`) and `SMSG_SPELL_GO` (`0x132`). Both begin with a packed
guid, a second packed guid and a dword spell id. It calls the start path `0x6e7700` or the go path
`0x6e7a70` with pointers to copies of the two guids and the spell id and store on the stack. The
first guid is the cast's source, an item when an item casts, and the second the casting unit.

Addresses: `0x6e7640`, `0x6e7665`, `0x6e766f`, `0x6e767a`, `0x6e7681`, `0x6e76ae`, `0x6e76e6`
Confidence: verified
Proof: one
Test: none

`0x6e7665` and `0x6e766f` call `0x642ed0` into `[ebp-0x18]` and `[ebp-0x10]`; `0x6e767a` reads the
id. `0x6e7681 sub eax,0x131` on the opcode in `edx`. Both calls pass `ecx` = the copy of the first
guid and `edx` = the copy of the second (`0x6e76a5`, `0x6e76a8`). The start path looks the unit up
by the second guid (`0x6e7892`), the go path compares the two to tell an item cast (`go`).

## Target block

The start and go messages carry a target block after their own fields: a 16-bit mask, then a
packed guid when the mask has any of `0x8a02`, a packed guid when it has `0x1010`, three floats
(source point) for `0x20`, three floats (destination point) for `0x40`, and a string into a
128-byte field for `0x2000`, in that order. The reader stores them at `+0x14`, `+0x18`, `+0x20`,
`+0x30`, `+0x3c` and `+0x70` of a record whose first 0x14 bytes the caller fills with the two guids
and the spell id.

Addresses: `0x7e4ed0`, `0x7e4ee8`, `0x7e4f05`, `0x7e4f22`, `0x7e4f48`, `0x7e4f6e`
Confidence: verified
Proof: one
Test: none

`0x7e4ed0` reads the word at `+0x14`, then tests `0x8a02` (`0x7e4ee8`), `0x1010` (`0x7e4f05`), the
byte `0x20` (`0x7e4f22`), `0x40` (`0x7e4f48`) and `0x20` in the high byte (`0x7e4f6e`), with three
4-byte reads into `+0x30` to `+0x38` and `+0x3c` to `+0x44` and a string read of at most 0x80 into
`+0x70`. The callers zero the record first (`0x6e7771` onwards, `0x6e7bef` onwards).

## Spell start

`SMSG_SPELL_START`: the common fields, a 16-bit cast flags word, a dword cast time, the target
block, and two dwords (ammo display id, ammo inventory type) when the flags have `0x20`, else
zeros. Nothing happens without a record or a casting unit. A ranged spell (bit 5 of `+0x20` or bit
1 of `+0x18`) passes the display id to `0x60ba30`, for any caster. For another unit's cast the
client calls `0x611cf0` (2, 1, 1) for a ranged spell, starts the cast visual `0x6ec220` unless flag
bit 0 is set, and targets the caster through `0x493540` when the unit target is the player, the
caster cannot assist the player and the player has no target. No event fires for another unit.

Addresses: `0x6e7700`, `0x6e772c`, `0x6e7737`, `0x6e77f8`, `0x6e781f`, `0x6e7876`, `0x6e7892`, `0x6e78a1`, `0x6e78b6`, `0x6e78d6`, `0x6e78f3`, `0x6e78f8`, `0x6e7901`, `0x6e790d`, `0x6e7973`, `0x6e7980`, `0x6e799c`, `0x60ba30`, `0x611cf0`, `0x6ec220`, `0x6066f0`, `0x493540`, `0x468460`, `0xb4e2d8`
Confidence: verified
Proof: one
Test: none

`0x6e772c` reads the word, `0x6e7737` the cast time, `0x6e77f8` the block; `0x6e781f` tests flag
`0x20`, else `0x6e784e` zeroes both. `0x6e7876` and `0x6e789b` exit on a null record or unit; the
unit is `0x468460` with type mask 8 on the second guid. `0x6e78a1 test [eax+0x20],0x20`, `test
[eax+0x18],2`, `0x6e78b6` calls `0x60ba30(display)`. `0x6e78d6` takes the player branch when the
unit's guid equals the player's. Otherwise `0x6e78f3` pushes 1, 1, 2; `0x6e78f8 test flags,1`;
`0x6e7908` calls `0x6ec220(spell, &record, unit)`. `0x6e790d` needs mask bit 1 (0x2) and a target guid
equal to the player's; `0x6e7973` calls `0x6066f0(unit, player)`; a zero result and a zero
`0xb4e2d8` reach `0x6e799c`, `0x493540(unit guid)`.

## Player cast start

For the player's own start, the client starts the cast visual unless the spell is the pending
cast's, calls `0x60c9b0` on the unit, and for a spell with bit 22 of `+0x18` calls `0x60fed0` with
the packet's unit target, or the current target when the mask lacks bit 1 (0x2) or the guid is 0. Then,
when the cast time is nonzero and bit 1 of `+0x18` is clear, it fires `SPELLCAST_START` (337) with
a name and the cast time in milliseconds (`%s%d`): the spell's localized name, or `""` when bit 2
of `+0x24` is set. A spell with no record never reaches this.

Addresses: `0x6e79ac`, `0x6e79af`, `0x6e79be`, `0x6e79c5`, `0x6e79d0`, `0x6e79fb`, `0x6e7a18`, `0x6e7a1d`, `0x6e7a27`, `0x6e7a2d`, `0x6e7a33`, `0x6e7a40`, `0x6e7a53`, `0x60c9b0`, `0x60fed0`
Confidence: verified
Proof: one
Test: none

`0x6e79af cmp ecx,[0xceac58]; je` skips `0x6e79be`, `0x6ec220`. `0x6e79c5` calls `0x60c9b0`.
`0x6e79d0` keeps bit 22 with `and eax`; the packet's guid needs mask bit 1 (`test [ebp-0x10c],0x2`) and a nonzero guid,
else `0x6e79fb` loads `0xb4e2d8`; `0x6e7a18` calls `0x60fed0(&guid, 0)` when the bit was set.
`0x6e7a1d` tests the cast time with `jbe`, `0x6e7a27` bit 1 of `+0x18`, `0x6e7a2d` bit 2 of `+0x24`
to the empty string (`0x6e7a33`), else `[rec + 4·[0xc0e080] + 0x1e0]` (`0x6e7a40`). `0x6e7a53`
signals `0x151` with the format `%s%d`, the name, then the time.

## Small spell handlers

`0x2a7`: a 64-bit guid; a game object of that guid gets `0x5f8c00`, which passes its descriptor
dword `+0x20` past `+0x110` to the state setter `0x5f8bd0`. `0x2b4`: no fields; shows the
UI error 421, `ERR_FEIGN_DEATH_RESISTED`. `0x330`: a 64-bit guid, a dword spell id, a dword count and
that many 64-bit guids; a unit of the first guid gets `0x605710` (the list, the spell id), which
refills its chain-target array. `0x1f3` (`SMSG_PLAY_SPELL_VISUAL`): a 64-bit guid and a dword kit
id; with a SpellVisualKit record and a unit, `0x60edf0` (0, the kit, 0, 0). `0x29c`: no fields;
calls the auto-repeat stop `0x6ea080` (`cast`).

Addresses: `0x6e9790`, `0x6e97c4`, `0x6e9800`, `0x6e9805`, `0x6e9820`, `0x6e984d`, `0x6e9862`, `0x6e98b0`, `0x6e98d0`, `0x6e98f0`, `0x6e9935`, `0x6e99d0`, `0x6ea080`, `0x5f8c00`, `0x5f8bd0`, `0x496720`, `0x605710`, `0x605780`, `0x60edf0`, `0x40a280`, `0xc0d744`
Confidence: verified
Proof: one
Test: none

`0x6e979d` reads 8 bytes; `0x468460` with type mask `0x20`; `0x5f8c06` loads `+0x20`. `0x6e9800` is `push 0x1a5; call
0x496720`. `0x6e9820` reads 8, 4, 4 bytes; `0x6e9862` allocates count × 8 on the stack with
`__alloca_probe`, a `jbe` loop reads the guids, and `0x6e98b0` calls `0x605710` with the
count-and-pointer pair and the spell; `0x605710` calls `0x605780` (`0x605767`). `0x6e98f0` bounds
the kit by the SpellVisualKit store's `+0x0c`; `0x6e9935` pushes 0, 0, the kit, 0. `0x6e99d0` is
`call 0x6ea080; mov eax,1; ret 8`.

## Hostility classifier

`0x6ea280` classifies a spell record as 2 (harmful), 1 (helpful) or 0. The targets dword `+0x34`
decides first: bit 8 gives 1, bit 7 gives 2. Then for each effect slot 0 to 2, implicit target A
(`+0x148`) or B (`+0x154`) in {2, 6, 15, 16, 24, 28, 53, 54} gives 2. Then for each slot, A or B in
{3, 4, 5, 7, 8, 20, 21, 27, 29, 30, 31, 33, 34, 35, 45, 56, 57, 58, 59, 61, 62} gives 1, and A or B
equal to 1 gives 1 unless the slot's dword at `+0x16c` is 4. Anything else is 0.

Addresses: `0x6ea280`, `0x6ea283`, `0x6ea290`, `0x6ea2ae`, `0x6ea2c6`, `0x6ea2ee`, `0x6ea2fc`, `0x6ea30a`, `0x6ea318`, `0x6ea330`, `0x6ea338`, `0x6ea370`, `0x6ea378`, `0x6ea3b0`, `0x6ea3bc`, `0x6ea3fc`, `0x6ea408`
Confidence: verified
Proof: one
Test: none

`0x6ea283 test ah,1` and `0x6ea290 test al,al; jns` on `+0x34`. The first loop indexes the byte
tables `0x6ea338` and `0x6ea378` by A − 2 and B − 2 for values 2 to 54 (`ja` otherwise) into the
two-entry jump tables `0x6ea330` and `0x6ea370`; entry 0 is the return of 2 for the eight values
listed. The second loop indexes `0x6ea3bc` and `0x6ea408` by A − 1 and B − 1 for 1 to 62 into the
three-entry tables `0x6ea3b0` and `0x6ea3fc`: entry 1 returns 1 for the 21 values, entry 0 is value
1's `cmp [eax],4; jne` to the return of 1 (`0x6ea2fc`, `0x6ea318`), entry 2 goes on. The tables'
bytes were read and grouped by entry. Five calls in the object layer reach it, and `go`'s impact
legs test for 2.

## History list link

`0x6ea450` links a node into the cooldown history list, the list of `.?AUSPELLHISTORY@@` records:
it first unlinks the node if linked, then with mode 1 inserts it after the given neighbour, else
before it; a null neighbour means the list's end link, so mode 1 inserts at the head and any other
mode at the tail. Its one caller, `0x6e12c0`, appends with mode 2.

Addresses: `0x6ea450`, `0x6ea462`, `0x6ea4a5`, `0x6ea4bd`, `0x6e12c0`
Confidence: verified
Proof: one
Test: none

`this` is the list: a link offset at `+0`, the end link at `+4`. A link is the previous link at `+0`
and the next node at `+4`, bit 0 marking the end. `0x6ea462` to `0x6ea490` unlink the node's link
and zero it. `0x6ea4a5 dec esi; je` takes mode 1 to `0x6ea4bd`: node's previous is the neighbour,
its next the neighbour's next, the next link's previous points back, and the neighbour's next is
the node. Otherwise the node takes the neighbour's previous link and that link's next, and both
are pointed at the node; `ret 0xc`. `0x6e1395` pushes 0, 2 and the node, allocated with the tag
`.?AUSPELLHISTORY@@`.
