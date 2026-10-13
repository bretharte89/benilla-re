# models: the instance

A model instance, `CM2Model`: what the rest of the client holds for each model it shows. This doc
covers its construction, the calls it defers until its file is loaded, its transform, geosets,
textures, attachments, events and bounds. Its animation is `animation`, its lighting `lights`.

An instance is 0x428 bytes, allocated by a scene (`scene`) and bound to a shared model
(`shared`); M2Model.cpp holds its code from `0x70dc60` through `0x71b070`. Every public call that
needs the shared model either waits for it, through `0x710520`, or queues itself until the load
ends. The fixed-up header of the shared model is `md`.

Roots: `0x710330`, `0x710350`, `0x710370`, `0x710390`, `0x7103a0`, `0x7103d0`, `0x710450`, `0x7105a0`, `0x7105c0`, `0x7105d0`, `0x710600`, `0x710620`, `0x710650`, `0x7106c0`, `0x710b80`, `0x710b90`, `0x710bf0`, `0x710c00`, `0x710c50`, `0x710c90`, `0x710ca0`, `0x710cb0`, `0x710cf0`, `0x710d40`, `0x710db0`, `0x710de0`, `0x710e00`, `0x710e20`, `0x710e50`, `0x710ec0`, `0x7110d0`, `0x711230`, `0x711960`, `0x711a20`, `0x711bb0`, `0x711d20`, `0x711f10`, `0x711fe0`, `0x712090`, `0x712150`, `0x712910`, `0x712b00`, `0x712cb0`, `0x712cf0`, `0x712d50`, `0x712de0`, `0x712ed0`, `0x712ee0`, `0x712ef0`, `0x712f00`, `0x712f30`, `0x712f70`, `0x713020`, `0x713070`, `0x7130a0`, `0x7130e0`, `0x7131b0`, `0x7133a0`, `0x7134b0`, `0x7134d0`, `0x713540`, `0x713590`, `0x7135c0`, `0x713640`, `0x713680`, `0x713700`, `0x7137c0`, `0x713cb0`, `0x718910`

## Instance object

The constructor sets the reference count to 1, the base, world and transport matrices to
identity, the diffuse multiplier to (1, 1, 1), the depth-fill flag and the two loaded-children
flags to 1, and picks the skinning routine. `Initialize` links the instance to its scene, adds a
reference to the shared model and, for a copy, to the source instance, and attaches a new instance
of each of the source's children at the same attachment id.

| offset | holds |
|---|---|
| `+0x010`, `+0x014` | loaded, textures loaded |
| `+0x02c`, `+0x030`, `+0x034` | scene, shared model, copy source |
| `+0x038`, `+0x03c` | deferred call queue: head, address of the tail link |
| `+0x040` | frame of the last animation |
| `+0x090`, `+0x094` | bone states (0x118 each), bone matrices (64 bytes each) |
| `+0x0bc`, `+0x0fc`, `+0x13c` | base matrix, world matrix, transport matrix |
| `+0x180`, `+0x184`, `+0x190` | alpha, diffuse multiplier, emissive colour |
| `+0x1cc`, `+0x1d0`, `+0x1d4` | parent, attachment id, attachment index in the parent |
| `+0x1dc`, `+0x1e4` | first child, next sibling |
| `+0x3b8` | lighting record in use |

Addresses: `0x70dd70`, `0x70ea00`, `0x70e170`, `0x710390`, `0x7103a0`
Confidence: verified
Proof: one
Test: none

The identity stores are 1.0 on the diagonals of `+0xbc`, `+0xfc` and `+0x13c`; `+0x1c4`,
`+0x1e8` and `+0x1ec` get 1. `0x70ea00(scene, shared, source, flags)` stores the scene at `+0x2c`,
calls `0x71d430` on the shared model and stores it at `+0x30`, stores `+0x40 = scene+0x10 − 1`,
and for each child of the source creates `0x707400(child, 0)` and attaches it at child `+0x1d0`.
`0x7103a0` decrements `+0x0` and at zero runs `0x70e170` and frees the instance.

## Deferred calls

A call that changes animation state while the shared model is loading appends an 80-byte record:
its kind, the scene clock at the time, and its arguments. When the load ends, the instance builds
its state, plays its default animation, and replays the queue in order with the scene clock set back
to each record's time.

| kind | call |
|---|---|
| 0 | `SetReplaceableTexture` |
| 1 | `SetGeosetRange` |
| 2 | `BuildBatches` |
| 3 | `SetKeyBoneFlags` |
| 4 | `PlayAnimation` |
| 5, 6 | `SetKeyBoneAnimTime`, `SetKeyBoneAnimSpeed` |
| 7 | `SetKeyBoneOverride` |
| 8 | `SetLightEnabled` |
| 9 | `Update` |

Addresses: `0x70ebd0`, `0x7101c5`, `0x7102e8`, `0x70dd40`, `0x70dd50`, `0x710ec0`, `0x7110d0`, `0x711230`, `0x711f10`, `0x7121a0`, `0x7127f0`, `0x712910`, `0x712b00`, `0x713430`, `0x719370`
Confidence: verified
Proof: one
Test: none

Each deferring function allocates the record with its own line number, runs `0x70dd40` on it, then
stores the kind at `+0x0`, 0 at `+0x4`, scene `+0xc` at `+0x8` and its arguments from `+0xc`, and
links it through `+0x3c`. The replay at the end of `0x70ebd0` saves the scene clock, and for each
record stores `+0x8` into scene `+0xc` and jumps through the ten-entry table `0x7102e8` at
`0x7101c5`; after each call it runs `0x70dd50` and frees the record. The default animation is
`PlayAnimation(−1, id, 0, 0, 1.0, 0, 1)` with the id from `0x711bf0`.

## Load state

`IsLoaded(wait, recursive)` returns whether the shared model is loaded, waiting for it first when
asked, and with `recursive` also whether every child is; the first success latches a flag.
`IsReady` also requires every texture of the instance and its children to be loaded. The loaded
callback runs once the instance is loaded, then the instance's parent's, up the chain.

Addresses: `0x7103d0`, `0x710450`, `0x710520`, `0x710560`, `0x7105a0`, `0x8732ac`
Confidence: verified
Proof: one
Test: none

`0x710520(name)` waits on the shared model's read request and logs `Model2: CM2Model::%s
stalled: %s` (`0x8732ac`) with the file name. `0x7103d0` latches `+0x1e8`, `0x710450` latches
`+0x14` and `+0x1ec`; textures are tested with `0x44acf0(texture, wait, 0)`. `0x710560` calls
`+0x24(ecx=instance, edx=+0x28)`, clears `+0x24`, and moves to `+0x1cc`.

## Base transform

`0x710650` builds the base matrix as identity, translated, rotated by an angle about an axis, and
scaled. `0x7106c0` does the same with a ground normal: for header flag mode 1 it rebuilds the
rotation's rows so the third row is the normal, for mode 3 it does so through `0x710a80`, and while
a key bone plays an animation with flags 2, 4 or 8 it blends the conformed rotation with the plain
one by the animation's progress.

Addresses: `0x710650`, `0x7106c0`, `0x710a80`, `0x711fe0`
Confidence: inferred
Proof: none
Test: none

`0x710a80` sets row 1 to `n × row0` normalized when its length exceeds 2.384186e-7, row 0 to
`row1 × n`, and row 2 to `n`. The blend weight in `0x7106c0` reads the state from `0x711fe0`; its
exact time arithmetic was not transcribed.

## Geosets and own batches

`SetGeosetRange(min, max, visible)` shows or hides every submesh of the selected view whose geoset
id lies in the range, and rebuilds the instance's own batches when anything changed. The own batch
table copies the visible submeshes' batches into an instance index buffer, merging neighbours whose
colour, material, textures, transparency, texture transform and bones match.

Addresses: `0x7110d0`, `0x711230`, `0x711780`, `0x711880`, `0x719930`
Confidence: inferred
Proof: none
Test: none

The visibility words live at `+0x98`, one per submesh. `0x711780` compares batch words `+0x8`,
`+0xa`, `+0x10`, `+0x14`, `+0x16` and submesh `+0xe`.

## Replaceable textures

`SetReplaceableTexture(type, texture)` binds the texture to every model texture of that
replaceable type, to the ribbons and particle emitters that use one, and marks the textures not
loaded when the new texture is not. `GetReplaceableTexture` returns the texture of an id through
the header's replaceable lookup.

Addresses: `0x710ec0`, `0x710e50`, `0x7b7950`, `0x7b4d20`
Confidence: verified
Proof: one
Test: none

The texture records are 16 bytes at header `+0x60` with the type at `+0x0`; each match closes
`+0xa4[i]` and stores the new handle with a reference. Ribbons get `0x7b7950(ribbon, type,
texture)`, emitters `0x7b4d20`. `0x710e50` looks the id up in header `+0x7c` with `0x710310`.

## Attachments

`Attach(parent, id)` takes an instance off the animate list, stores the parent and id, resolves
the id to the parent's attachment index (0xffff while the parent loads) and links it first among
the parent's children. An attached instance animates through its parent. `GetAttachmentPosition`
transforms the attachment's offset by its bone matrix and the scene matrix.

Addresses: `0x712f70`, `0x713020`, `0x713070`, `0x7130a0`, `0x712cb0`, `0x712cf0`, `0x712d50`, `0x712de0`, `0x712f00`
Confidence: verified
Proof: one
Test: none

Attachments are 48-byte records at header `+0x108`, counted at `+0x104`, with the bone at `+0x4` and the offset at
`+0x8`, looked up through header `+0x10c`. `0x712f70` calls `0x710b90(0)` and stores `+0x1cc`,
`+0x1d0`, `+0x1d4`, `+0x1d8 = 1`. `0x712de0` adds `R·offset` to the bone matrix's translation and
multiplies by the scene matrix. `0x713020` unlinks, clears the parent and sets the id to −1.

## Events

`HasEvent(id)` searches the header's 44-byte events for an id. `GetEventPosition` transforms an
event's offset by its bone and the scene matrix, or returns zero for a missing id.

Addresses: `0x7130e0`, `0x7131b0`, `0x713260`, `0x713130`, `0x7133a0`
Confidence: verified
Proof: one
Test: none

The events are at header `+0x118` with count `+0x114`: id `+0x0`, bone `+0x8`, offset `+0xc`.
`0x7131b0` runs `0x714000` before reading the bone matrix. `0x7133a0` stores the event callback
and its arguments at `+0x1f4`, `+0x1f8`, `+0x1fc`.

## Bounds

`GetBoundingSphere` returns the centre of the header's bounding box and its radius: x and y are
`(min + max)·0.5` from a sum at the FPU's 53-bit precision, z rounds the sum to a float first. The radius is
header `+0xcc`. `GetBoundingBox` and `GetCollisionBox` copy the six floats at `+0xb4` and `+0xd0`.

Addresses: `0x713680`, `0x713640`, `0x713700`, `0x713740`
Confidence: verified
Proof: one
Test: none

`0x713680`: `fld +0xb4; fadd +0xc0` and `fld +0xc4; fadd +0xb8` stay on the stack, `fld +0xc8;
fadd +0xbc; fstp` rounds, then each is multiplied by 0.5 and stored. The radius is `+0xcc`.

## Collision facets

`GatherCollisionFacets(box, matrix, facets)` transforms the header's collision vertices by a
matrix once into a cached array, gives each an outcode against the box, and emits each collision
triangle whose vertices do not share an outside side.

Addresses: `0x7137c0`
Confidence: inferred
Proof: none
Test: none

The caches are `+0x3e4` (vertices) and `+0x3e8` (outcodes), allocated on first use. The outcode
bits are 1 and 2 for x, 4 and 8 for y, 0x10 and 0x20 for z.

## Hit-test mode

`SetHitTestMode(mode, a, b)` links the instance into the scene's hit-test list when `mode` is
nonzero and stores the mode and its two arguments.

Addresses: `0x713cb0`, `0x713c80`
Confidence: verified
Proof: one
Test: none

`0x713cb0` links through `+0x414`/`+0x418` into scene `+0x130` and stores `+0x410`, `+0x420`,
`+0x41c`.
