# spell: tables

The three hash indexes over the skill DBCs that `SpellTableInitialize` builds at startup, their lookups, and the container code they instantiate.

The object file opens the spell band, `0x6dd270` to `0x6e0d70` (`layout` has its initializers). It owns
three hash tables in zero-filled `.data`: the race-class index (`0xceab3c`, nodes tagged
`RACECLASSINFO`) over `SkillRaceClassInfo.dbc`, the skill-cost index (`0xceab80`,
`SKILLCOSTSINFO`) over `SkillCostsData.dbc`, and the ability index (`0xceabec`, `SKILLLINEREC`)
over `SkillLineAbility.dbc`, whose nodes come from a block pool at `0xcfa140`. Each table is a
vtable, a list of every node, a fullness counter, a growable array of slot lists and a slot
mask; most of the 73 functions are that container code, compiled once per element type.
`ClientInitializeGame` fills the tables once and `ClientDestroyGame` empties them. The rest of
the client reaches five lookups: a skill line's race-class row (`0x6ddf90`), a spell's ability
row for a race and class (`0x6de040`), a linear ability scan (`0x6de0d0`), and a skill cost and a
tier value (`0x6de110`, `0x6de1c0`). No code outside the object file names the tables.

Roots: `0x6dda50`, `0x6dde30`, `0x6ddf90`, `0x6de040`, `0x6de0d0`, `0x6de110`, `0x6de1c0`, the vtable slots `0x6de240`, `0x6de2c0`, `0x6de9a0`, `0x6de380`, `0x6de440`, `0x6de4c0`, `0x6dea60`, `0x6de580`, `0x6de640`, `0x6de6d0`, `0x6dd9b0`, `0x6de8e0`, `0x6de790`, `0x6de810`, `0x6deb20`, the exit destructors `0x6dd390`, `0x6dd5e0`, `0x6dd840`, `0x6e0870`, and the static initializer `0x6e0830`

## Startup build of the indexes

`SpellTableInitialize` runs once, called from `ClientInitializeGame` (`0x401570`). It walks
`SkillRaceClassInfo.dbc` in row order and adds one race-class node per run of consecutive rows
with equal skill line (`+0x04`): the node's hash is the skill line, `+0x18` the run's first row and
`+0x1c` its length. It does the same over `SkillCostsData.dbc`, keyed by `+0x04`, into the cost
index. Then, for every `CharBaseInfo.dbc` row whose race byte (`+0x00`) is an id `ChrRaces.dbc`
holds, it offers every `SkillLineAbility.dbc` row to `0x6ddbe0` with that race and the row's class
byte (`+0x01`). A key that reappears after another key starts a second node.

Addresses: `0x6dda50`, `0x401634`, `0x6dda8d`, `0x6dda9b`, `0x6ddaa6`, `0x6ddaba`, `0x6ddb0d`, `0x6ddb6a`, `0x6ddb71`, `0x6ddb7f`, `0x6ddbad`, `0xc0d910`, `0xc0d960`, `0xc0df8c`, `0xc0ded8`, `0xc0d94c`, `0x541620`, `0x575280`, `0x5425a0`, `0x5764f0`
Confidence: verified
Proof: one
Test: none

`0x401634` is the only call. Pass one reads rows of `0xc0d910` at stride 0x20; `ecx` holds the
previous key, first -1. On a change (`0x6dda8d`) it calls `0x6debe0(key, 0, 0)` on `0xceab3c`
(`0x6dda9b`) and stores the key at `+0x00`, the byte at `[ebp-0x1]` at `+0x14`, the row at `+0x18`
and 1 at `+0x1c` (`0x6ddaa6` on); else `inc [eax+0x1c]` (`0x6ddaba`). `[ebp-0x4]` is never
written in the frame, so `+0x14` takes an uninitialized byte. Pass two is the same over `0xc0d960`
at stride 0x14 into `0xceab80` through `0x6dee80` (`0x6ddb0d`). Pass three takes rows of `0xc0df8c`
at stride 8 (`0x6ddb6a`), skips a race byte above `[0xc0dee4]` or with a null `[0xc0dee0 + 4·race]`
(`0x6ddb71`, `0x6ddb7f`), and calls `0x6ddbe0` with `ecx` the race, `edx` the class and each row of
`0xc0d94c` at stride 0x3c (`0x6ddbad`). The store identities: the loader `0x541620` reads the path
`0x575280` returns, `DBFilesClient\CharBaseInfo.dbc`, and `0x5425a0` reads `0x5764f0`'s
`DBFilesClient\ChrRaces.dbc` and keys its id map by record `+0x00` (`0x5427b7`).

## Race and class mask test

`0x6dddd0` admits a race and a class against a race mask and a class mask, each optionally
complemented first. A mask admits when, after the complement, it is zero or has bit `race - 1`
(`class - 1`) set; both must admit. The shift count is taken mod 32, so race or class 0 tests bit 31.

Addresses: `0x6dddd0`, `0x6ddddd`, `0x6dddea`, `0x6dddf7`, `0x6dde11`
Confidence: verified
Proof: one
Test: none

`__fastcall` with `ecx` the race, `edx` the class, and four stack arguments (`ret 0x10`): race
mask, class mask, complement-race flag, complement-class flag. A nonzero flag applies `not`
(`0x6ddddd`, `0x6dddea`). `dec ecx; mov edi,1; shl edi,cl; test eax,edi` (`0x6dddf1` to `0x6dddf9`)
and `lea ecx,[edx-0x1]; shl eax,cl; test esi,eax` (`0x6dde09` to `0x6dde13`) are the bit tests, each
skipped for a zero mask; a failed test returns 0, else 1.

## Skill line race-class lookup

`0x6ddf90` returns the first `SkillRaceClassInfo.dbc` row of a skill line's run whose race mask
(`+0x08`) and class mask (`+0x0c`) admit the race and class, uncomplemented, or null. It searches
only the first node whose hash equals the skill line in its slot, which is the node added last
(Insertion and growth); with an empty index it returns null.

Addresses: `0x6ddf90`, `0x6ddf9f`, `0x6ddfd9`, `0x6de012`, `0x6de02e`, `0xceab58`, `0xceab60`
Confidence: verified
Proof: one
Test: none

`ecx` race, `edx` class, the skill line on the stack (`ret 4`). A mask of -1 at `0xceab60` returns 0
(`0x6ddf9f`). The slot is `[0xceab58] + 12·(mask & line)`; the walk starts at the slot's `+0x08` and
steps through `[slot + 0] + node + 4`, stopping at a null or bit-0 pointer, until `[node] == line`
(`0x6ddfd9`). It then calls `0x6dddd0(rec+0x08, rec+0x0c, 0, 0)` for each of `+0x1c` rows from
`+0x18` at stride 0x20 (`0x6de012`) and returns the first that passes (`0x6de02e`).

## Spell ability index by race

`0x6ddbe0` adds an ability node for a race, a class and a `SkillLineAbility.dbc` row when
`0x6ddf90` finds a race-class row for the row's skill line (`+0x04`) and `0x6dddd0` admits the race
and class against the row's race mask `+0x0c` and class mask `+0x10`, complemented when `+0x14`
and `+0x18` are nonzero. The node holds the spell (`+0x08`) as hash, the race at `+0x14`, the class
at `+0x15`, the spell's low 16 bits at `+0x16` and the row at `+0x18`. `0x6de040` returns the row
of the first node in the spell's slot matching spell, race, class and low word, or null. A spell
with two admitted rows for one race and class resolves to the later row in file order.

Addresses: `0x6ddbe0`, `0x6ddbf4`, `0x6ddc1c`, `0x6ddc2d`, `0x6ddd76`, `0x6dddb1`, `0x6de040`, `0x6de081`, `0x6de088`, `0x6de08d`, `0x6de092`, `0x6de0ab`
Confidence: verified
Proof: one
Test: none

`0x6ddbe0`: `ecx` race, `edx` class, the row on the stack (`ret 4`); it returns 0 at `0x6ddbf4` or
`0x6ddc1c` failures. `0x6ddc2d` to `0x6ddc4a` build the dword `race | class << 8 | (spell & 0xffff)
<< 16` at `[ebp-0x4]`; the node comes from slot 1 of `0xceabec` (`0x6ddd76`), and `0x6dddb1` to
`0x6dddb6` store the spell at `+0x00`, the row at `+0x18` and that dword at `+0x14`. `0x6de040`
takes `ecx` race, `edx` class, the spell on the stack, and compares `[node]` (`0x6de081`), byte
`+0x14` with `cl` (`0x6de088`), byte `+0x15` with `dl` (`0x6de08d`) and word `+0x16` with `si`
(`0x6de092`), returning `+0x18` (`0x6de0ab`). Every node of one spell shares a slot, and new nodes
go to the slot's head.

## Skill costs and tiers

`0x6de110` returns a skill cost: from a race-class row, as `0x6ddf90` returns, it takes the skill line
(`+0x04`), that line's cost-set id (`SkillLine.dbc` `+0x08`), and the cost node for it; for a rank
`r` not above the node's row count it returns the dword at `+0x08 + 4·c` of row `r - 1`, `c` being
the race-class row's `+0x1c`. Neither `r` below 1 nor `c` is bounded. `0x6de1c0` returns the dword at
`+0x04 + 4·i` of the `SkillTiers.dbc` record the race-class row's `+0x18` names, for `i` below 16,
else 0. A missing record, line or node gives 0.

Addresses: `0x6de110`, `0x6de125`, `0x6de13e`, `0x6de190`, `0x6de1a4`, `0x6de1c0`, `0x6de1c5`, `0x6de1de`, `0xc0d924`, `0xc0d8fc`, `0xceab9c`, `0xceaba4`
Confidence: verified
Proof: one
Test: none

`0x6de110`: `ecx` the row, `edx` the rank. It bounds the line by `[0xc0d930]` (`0x6de125`), loads
`[0xc0d92c + 4·line]` and its `+0x08` (`0x6de13e`), walks the slot of `0xceab9c` under the mask
`0xceaba4` as `0x6ddf90` does, and `cmp edx,[ebx+0x1c]; jg` (`0x6de190`, signed) guards the read
`[first + 4·(5·r + c) - 0xc]` (`0x6de1a4`). `0x6de1c0`: `ecx` the row, `edx` the index; zero,
negative or above `[0xc0d908]` ids return 0 (`0x6de1c5` to `0x6de1cf`), `cmp edx,0x10; jae` the
index (`0x6de1de`), then `[rec + 4·i + 4]`.

## Linear ability scan

`0x6de0d0` returns the first `SkillLineAbility.dbc` row in file order whose skill line (`+0x04`)
and spell (`+0x08`) equal its arguments, or null. It reads the store, not the index.

Addresses: `0x6de0d0`, `0x6de0f3`, `0x6de0f8`
Confidence: verified
Proof: one
Test: none

`__fastcall` with `ecx` the line and `edx` the spell, no stack arguments. The loop runs `esi` from
0 below `[0xc0d950]`, rows at stride 0x3c from `[0xc0d94c]`, comparing `+0x04` (`0x6de0f3`) and
`+0x08` (`0x6de0f8`).

## Hash table layout

Each table is 0x28 bytes: `+0x00` vtable; `+0x04` the node list's link offset (0x0c), `+0x08` and
`+0x0c` its end link; `+0x10` the fullness counter; `+0x14` the slot array's capacity, `+0x18` its
count, `+0x1c` its data, `+0x20` its step; `+0x24` the slot mask, -1 with no slots. A slot is a
12-byte list: offset 4, then an end link. A link holds the previous link and the next node; the
last node's next is the end link's address with bit 0 set, and walks stop there or at null. Nodes
carry the hash at `+0x00`, the slot link at `+0x04` and the list link at `+0x0c`. The ability
table's constructor ends with its derived vtable `0x811838`.

Addresses: `0x6dd2c0`, `0x6dd510`, `0x6dd760`, `0x6dd2fd`, `0x6dd35e`, `0x6dd372`, `0x6dd81c`, `0xceab3c`, `0xceab80`, `0xceabec`, `0x811818`, `0x811828`, `0x811838`, `0x811848`, `0x6dd2b0`, `0x6dd500`, `0x6dd750`, `0x827000`
Confidence: verified
Proof: one
Test: none

`0x6dd2c0` stores 0xdddddddd at `+0x04`, `self | 1` at `+0x0c`, zeros at `+0x10` to `+0x20`, the
vtable `0x811818` (`0x6dd2fd`), unlinks any node of the empty list, then stores 0x0c at `+0x04`
(`0x6dd35e`), `self` at `+0x08` and -1 at `+0x24` (`0x6dd372`). `0x6dd510` and `0x6dd760` are the
same code for `0xceab80` with `0x811828` and `0xceabec` with `0x811848`; `0x6dd760` then stores
`0x811838` (`0x6dd81c`). The thunks `0x6dd2b0`, `0x6dd500`, `0x6dd750` sit in consecutive
initializer slots `0x82cf88` to `0x82cf90` of the table at `0x827000`. The slot offset 4 is stored
at `0x6dec44`; the slot walks of `0x6ddf90` read it.

## Insertion and growth

Adding a node never searches for an equal key. A table with mask -1 first gets four slots
(mask 3). While the mask is below 0x1fff, the fullness counter drops by 3 (floor 0), then rises by
one per node already in the target slot `hash & mask`; once it passes 13 the table resizes to
`2·(mask + 1)` slots and the counter resets. Vtable slot 1 makes the node at the slot's head, and
the node joins the tail of the node list. A resize moves the nodes, slot by slot from each head,
into a temporary list and appends each to the tail of its new slot, so equal hashes keep their
order. Callers store the hash.

Addresses: `0x6debe0`, `0x6dee80`, `0x6debf6`, `0x6dec6e`, `0x6dec7d`, `0x6decb4`, `0x6decdd`, `0x6decfe`, `0x6ded38`, `0x6ddc4f`, `0x6ddcbe`, `0x6ddd15`, `0x6ddd4d`, `0x6df410`, `0x6df860`, `0x6dfc80`, `0x6df4b2`, `0x6df5b7`, `0x6df5d7`
Confidence: verified
Proof: one
Test: none

`0x6debe0(hash, size, flags)` on `ecx`: `0x6debf6` stores mask 3, then `0x6df6f0(4)` and a loop
re-form each slot; `cmp eax,0x1fff; jae` (`0x6dec6e`); `add eax,-3` or 0 (`0x6dec7d`); `inc` per
node, `cmp ecx,0xd; ja` (`0x6decb4`) into `0x6df410(2·mask + 2)` (`0x6decdd`); `call [eax+0x4]` with
the slot, size and flags (`0x6decfe`); the tail append at `0x6ded38`. `0x6dee80` is the same code for
the cost table; `0x6ddbe0` inlines it for the ability table (`0x6ddc4f`, `0x6ddcbe`, `0x6ddd15`,
`0x6ddd4d`). In `0x6df410` (`0x6df860`, `0x6dfc80` alike) the temporary list's tail pointer is
`[ebp-0x14]` (`0x6df4b2`); the second pass takes `[node] & mask` (`0x6df5b7`) and links at the slot's
end link `+0x04` (`0x6df5d7`). Growth stops at 0x2000 slots.

## Node vtables

Each table has a four-slot vtable: delete a node, make a node, the deleting destructor, and clear.
Only slots 0 and 1 are called: slot 1 by the insertions, slot 0 by the teardown. The ability table
holds the base vtable `0x811848` only inside its constructor and exit destructor, and `0x811838`,
which draws nodes from the pool, in between. Delete unlinks both links and frees; make allocates
the node, clears its links and key bytes, and links it at the slot's head.

| slot | `0x811818` | `0x811828` | `0x811848` | `0x811838` |
|---|---|---|---|---|
| 0 delete | `0x6de240` | `0x6de440` | `0x6de790` | `0x6de640` |
| 1 make | `0x6de2c0` | `0x6de4c0` | `0x6de810` | `0x6de6d0` |
| 2 destroy | `0x6de9a0` | `0x6dea60` | `0x6deb20` | `0x6dd9b0` |
| 3 clear | `0x6de380` | `0x6de580` | `0x6de8e0` | `0x6de8e0` |

Addresses: `0x6de240`, `0x6de2c0`, `0x6de380`, `0x6de9a0`, `0x6de6d0`, `0x6de640`, `0x6ddd76`, `0x6decfe`, `0x6def9e`, `0x6dde8d`, `0x6ddef3`, `0x6ddf5d`, `0x6462e0`, `0x646430`
Confidence: verified
Proof: one
Test: none

The table is the dwords at `0x811818` to `0x811854`. `0x6de2c0` calls `0x6462e0(size + 0x20, tag,
-2, flags | 8)` and `0x6de810` with `+ 0x1c`, the tags `0x86f914`, `0x86f930` and `0x86f8f8`;
`0x6de6d0` calls `0x760450` on the pool with zero-fill 1, tag `0x86f8f8`, ignoring size and flags. Deletes free with
`0x646430` or `0x7604f0`. The vtable stores are at `0x6dd2fd`, `0x6dd394`, `0x6de9ab` and their
siblings, and only this object file holds the tables' addresses: a byte scan for every dword from
`0xceab3c` to `0xceac13` finds none outside it (control: `0xceab3c` five times inside). Its indirect
calls are the six listed. Slot 2 unlinks every node without freeing it, destroys the slot array and
frees the table on bit 0; slot 3 unlinks, sets the mask to -1 and frees the slot array.

## Ability node pool

The ability nodes come from a block pool at `0xcfa140`: 28-byte elements, 4681 to a block, so one
`0x6462e0` call of 131072 bytes per block. The initializer `0x6e0830` builds it once under bit 0 of
`0xcfa128` and registers `0x6e0870`, which empties it once under bit 0 of `0xceab2c`.

Addresses: `0x6e0830`, `0x6e083e`, `0x6e0857`, `0x6e0870`, `0x6e0889`, `0xcfa140`, `0xcfa128`, `0xceab2c`, `0x760390`, `0x760400`, `0x760450`, `0x7604f0`, `0x7603f0`, `0x6e0860`, `0x82cf94`
Confidence: verified
Proof: one
Test: none

`0x6e0830` sits at `0x82cf94` of the initializer table. Unless bit 0 of `0xcfa128` is set it sets it
and calls `0x760390(0x1c, 0x1249)` (`0x6e083e`), which stores the element size (at least 4) at
`+0x00`, the count (at least 1) at `+0x04` and zeros `+0x08` to `+0x10`; either way it jumps to
`0x6e0860` (`0x6e0857`), which registers `0x6e0870` with `_atexit`. `0x760450` pops the free list at
`+0x10`, first allocating `size · count + 4` bytes and threading them, zero-fills on its first
argument and counts in `+0x08`; `0x7604f0` pushes back. `0x6e0870` tail-jumps to `0x7603f0`
(`0x6e0889`), which frees every block through `0x760400`.

## Teardown at shutdown

`0x6dde30`, called from `ClientDestroyGame` (`0x401ee0`), deletes every node: for the ability table, then the
race-class and cost tables, it zeroes the counter, unlinks the node list, and deletes each slot's
nodes through vtable slot 0. It then frees every pool block with the `SKILLLINEREC` tag. The slot
arrays and masks stay. At exit, `0x6dd390`, `0x6dd5e0` and `0x6dd840` unlink what is left, destroy
each slot list, and free the slot arrays; they free no node.

Addresses: `0x6dde30`, `0x401fe4`, `0x6dde8d`, `0x6ddef3`, `0x6ddf5d`, `0x6ddf7c`, `0x6dd390`, `0x6dd5e0`, `0x6dd840`, `0x6dd92c`, `0x6dd9b0`, `0x6dd380`, `0x409aef`, `0x427180`
Confidence: verified
Proof: one
Test: none

`0x401fe4` is the only call. `call [edx]` with the slot's first node on `0xceabec`, `0xceab3c` and
`0xceab80` (`0x6dde8d`, `0x6ddef3`, `0x6ddf5d`); `0x760400(tag, -2, 1)` on `0xcfa140`
(`0x6ddf7c`). `0x6dd380` and its two siblings pass the exit destructors to `0x409aef`. Each stores the
base vtable, zeroes the counter, unlinks the node list and every slot's members, calls the list
destructor on each slot, frees the data with the `TSExplicitList` tag of its element type, then
unlinks the node list's end link. `0x6dd840` tests the end with `0x427180` (`0x6dd92c`) where the
others inline it. `0x6dd9b0` is slot 2 of `0x811838` and takes the same steps as `0x6deb20`.

## List and link primitives

Each element type has its own copy of eight small list routines. The three copies of each shape
are identical but for the callees and the allocation tag, and are listed race-class, cost, ability.

| shape | copies | does |
|---|---|---|
| unlink | `0x6df240`, `0x6df2a0`, `0x6df330` | detaches a link from its neighbours and zeroes it |
| link of node | `0x6df280`, `0x6df2e0`, `0x6df370` | returns `node + offset`, or the end link for null |
| next link | `0x6df3e0`, `0x6df830`, `0x6df300` | returns the next node's link, the offset derived when negative |
| unlink all | `0x6e01e0`, `0x6e0370`, `0x6df390` | unlinks every member of a list |
| end init | `0x6df6e0`, `0x6dfb30`, `0x6dff50` | points the end link at itself, next marked by bit 0 |
| list init | `0x6df600`, `0x6dfa50`, `0x6dfe70` | zeroes and inits the end link, offset 0xdddddddd |
| list destroy | `0x6ded60`, `0x6df000`, `0x6df120` | unlinks every member, then the end link |
| list delete | `0x6df630`, `0x6dfa80`, `0x6dfea0` | list destroy, then frees on bit 0 |

Addresses: `0x6df240`, `0x6df258`, `0x6df280`, `0x6df3e0`, `0x6df3fa`, `0x6e01e0`, `0x6df6e0`, `0x6df600`, `0x6ded60`, `0x6df630`, `0x6df6c9`
Confidence: verified
Proof: one
Test: none

`0x6df240` finds the next node's link as `next + (this - [prev + 4])` (`0x6df258`), or `next & ~1`
for an end, stores the previous link there, then `[prev + 4] = next`. `0x6df280` reads the offset at
the list's `+0x00`, `ret 4`. `0x6df3e0` uses its stack offset when not negative (`0x6df3fa`).
`0x6e01e0` repeats the unlink from the list's `+0x08`. `0x6df6e0` is `lea eax,[ecx+0x4]; mov
[eax],eax; or eax,1; mov [ecx+0x8],eax`. `0x6df630` frees through `0x646430` with the tag `delete`
(`0x6df6c9`).

## Slot array growth

The slot array grows by a step: unless set, the step is the largest power of two not above the
wanted count (1 for 0) when it is below 21, and otherwise becomes 21 and stays; the capacity rounds
up to a multiple of it. Setting a larger count reallocates when it exceeds the capacity and inits
the new lists; a smaller count destroys the lists past it. Reallocation asks `0x646320` with flags
0x10; when that returns null it allocates anew, gives each surviving list an empty copy with its
link offset, unlinks the old members, and frees the old block. Members do not carry over; every caller
empties the slots first.

Addresses: `0x6df6f0`, `0x6dfb40`, `0x6dff60`, `0x6df717`, `0x6df73a`, `0x6df74a`, `0x6e00a0`, `0x6e0230`, `0x6e03c0`, `0x6e0500`, `0x6e0610`, `0x6e0720`, `0x6e014f`, `0x6e0164`, `0x6e01aa`, `0x6dedf0`, `0x6df090`, `0x6df1b0`, `0x646320`
Confidence: verified
Proof: one
Test: none

`0x6df6f0(n)`: `cmp ebx,0x15; jae` (`0x6df717`) stores 21 at `+0x0c` (`0x6df73a`); below, `x & (x - 1)`
clears low bits; `div ecx` and `n + step - n mod step` (`0x6df74a`) feed `0x6e0500`. `0x6e00a0(extra,
round)` reserves `count + extra` the same way, rounding only when `round` is nonzero; `0x6df410`
calls it with 1. Both call `0x646320(old, 12·n, tag, -2, 0x10)` (`0x6e014f`), with the tags
`0x86f840`, `0x86f87c`, `0x86f8bc`; on null, `0x6462e0(12·n, tag, -2, 0)` (`0x6e0164`), and per element copy `+0x00` into a fresh empty list and
call the unlink-all (`0x6e01aa`). `0x6dedf0`, `0x6df090` and `0x6df1b0` destroy every list and free
the data; only slot 2 calls them. The copies per shape are listed race-class, cost, ability.
