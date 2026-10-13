# ui: visibility, alpha and scale

How a frame is shown and hidden, when its `OnShow` and `OnHide` scripts run, and how alpha and
scale pass from a frame to its children.

A `CSimpleFrame` has two flags: shown (`+0xd0`), what the frame asks for, and visible (`+0xd4`),
whether it is shown and its parent is visible. Only a visible frame is in a level of its stratum
(`strata`), lays itself out, takes input and draws. The frame's slot 0x88 makes it visible and
slot 0x84 makes it invisible; both walk the frame's regions and children. Alpha and scale are
stored per frame and pushed down to the regions and children when they change. All of this is in
`CSimpleFrame.cpp` (`0x769090` to `0x76c4d0`).

Roots: `0x76ae10`, `0x76ad50`, `0x76b260`, `0x76b290`, `0x76a690`, `0x76ac10`, `0x76ac50`, `0x76ac90`

## Showing a frame

Making a frame visible (slot 0x88) requires it to be shown and its parent, if any, to be visible;
otherwise it answers 0 and changes nothing. A frame that is not yet visible then, unless it is
loading, ends the layout deferral of itself and of its title region; becomes visible; joins its
level; shows its regions; makes each child visible in turn, which each child does only if it is
shown itself; raises itself when it is toplevel; and runs its show slot 0x30. It answers 1, also
when it was visible already.

Addresses: `0x76ae10`, `0x76ae13`, `0x76ae23`, `0x76ae2d`, `0x76ae3b`, `0x76ae49`, `0x76ae58`, `0x76ae6c`, `0x76ae7b`, `0x76ae85`, `0x76aeac`, `0x76aed5`, `0x76aee0`, `0x76aeec`, `0x76aef5`, `0x775750`
Confidence: verified
Proof: one
Test: none

`0x76ae10` tests `+0xd0` (`0x76ae13`) and the parent `+0x9c`'s `+0xd4` (`0x76ae23`, `0x76ae2d`),
then `+0xd4` (`0x76ae3b`); with `+0x114` clear it calls `0x768060(0)` on the frame's layout part
and on `+0xa8` (`0x76ae58`, `0x76ae6c`). It stores 1 at `+0xd4` (`0x76ae7b`), calls
`0x764780(frame, 0)` (`0x76ae85`), 0x77fcb0 for each region of `+0x1b8` (`0x76aeac`) and slot
0x88 of each child of `+0x300` (`0x76aed5`), `0x76a5b0` when bit 1 of `+0xb4` is set
(`0x76aee0`), and slot 0x30 (`0x76aef5`). The Lua `Show` (`0x775750`) stores 1 at `+0xd0` and
calls slot 0x88.

## Hiding a frame

Making a frame invisible (slot 0x84) acts only on a visible frame. Unless it is loading, it defers
the layout of itself and its title region; it clears visible, leaves its level, hides its regions,
makes every child invisible, and runs its hide slot 0x34. A child keeps its own shown flag, so it
returns when the parent is shown again. The Lua `Hide` clears shown first.

Addresses: `0x76ad50`, `0x76ad53`, `0x76ad61`, `0x76ad70`, `0x76ad84`, `0x76ad93`, `0x76ad9d`, `0x76adbf`, `0x76adee`, `0x76adfd`, `0x775810`, `0x7758b1`, `0x7758bb`
Confidence: verified
Proof: one
Test: none

`0x76ad50` tests `+0xd4` (`0x76ad53`); with `+0x114` clear it calls `0x768060(1)` on its layout
part and `+0xa8` (`0x76ad70`, `0x76ad84`); it stores 0 at `+0xd4` (`0x76ad93`), calls
`0x764920(frame, 0)` (`0x76ad9d`), 0x77fc60 for each region (`0x76adbf`), slot 0x84 of each
child (`0x76adee`) and slot 0x34 (`0x76adfd`). The Lua `Hide` stores 0 at `+0xd0` (`0x7758b1`)
and calls slot 0x84 (`0x7758bb`).

## Show and hide scripts

The show slot runs the frame's `OnShow` script and the hide slot its `OnHide` script, each only
when the script is set and the frame is not loading. A frame loads from XML with the loading flag
`+0x114` set: shows and hides during the load run no script and leave layout alone. At the end of
the load the flag is cleared, the deferral of the frame, its title region and its regions is
ended, the `OnLoad` script runs, and then, when the frame is visible and still not loading,
`OnShow` runs once.

Addresses: `0x76b260`, `0x76b270`, `0x76b27b`, `0x76b290`, `0x76b2a0`, `0x76b2ab`, `0x769770`, `0x7697c2`, `0x7697cc`, `0x7697e0`, `0x769807`, `0x76a2f0`
Confidence: verified
Proof: one
Test: none

`0x76b260` tests the `OnShow` slot `+0x130` and `+0x114` (`0x76b270`) before `0x702690`
(`0x76b27b`); `0x76b290` does the same with `+0x138`. The load's first step `0x769770` stores 1 at
`+0x114` (`0x7697c2`) and defers the frame, `+0xa8` and each region of `+0x1b8` through
`0x768060(1)` (`0x7697cc` to `0x769807`). The last step `0x76a2f0` stores 0 at `+0x114`, ends
the deferrals when `+0xd4` is set, loads the child frames, runs `+0x118` (`OnLoad`) and then
`+0x130` when `+0xd4` is set and `+0x114` is still 0.

## Alpha

A frame's alpha is a byte at `+0xc8`, 255 at construction. Setting it stores the byte and, when
it changed, refreshes each region and sets every child's alpha to the same byte, recursively: a
parent's alpha replaces its children's, it does not multiply them. The Lua `SetAlpha` clamps its
number to 0 to 1, NaN going to 1, multiplies by 255 and truncates.

Addresses: `0x76a690`, `0x76a69a`, `0x76a6a2`, `0x76a6d0`, `0x76a702`, `0x774e90`, `0x774f32`, `0x774f49`, `0x774f5e`, `0x774f66`, `0x774f6e`, `0x7ffe58`
Confidence: verified
Proof: one
Test: none

`0x76a690` compares the byte with `+0xc8` and returns when equal (`0x76a69a`), stores it
(`0x76a6a2`), calls slot 0x20 of each region with 0 (`0x76a6d0`) and slot 0x28, itself in
`0x81c498`, of each child with the same byte (`0x76a702`). `0x774e90` loads the number,
`fcom 0.0; test ah,0x5; jp` replaces a value below 0 with 0.0 (`0x774f32`), `fcom 1.0; test
ah,0x5; jnp` keeps a value below 1 and replaces the rest, NaN included, with 1.0 (`0x774f49`),
then `fmul [0x7ffe58]` (255.0) and `__ftol` (`0x774f5e`, `0x774f66`) before slot 0x28.

## Scale

A frame keeps its own scale at `+0xb8` and its parent's effective scale at `+0xbc`, both 1.0 at
construction. Setting either ignores a change below 2⁻²² unless forced, then recomputes the
effective scale, `+0xbc · +0xb8` rounded to a float. When that differs from the layout scale by
2⁻²² or more, or when forced, it becomes the layout scale of the frame, is passed as the layout
scale of each region, and as the parent scale of each child.

Addresses: `0x76ac10`, `0x76ac1a`, `0x76ac3b`, `0x76ac44`, `0x76ac50`, `0x76ac7b`, `0x76ac90`, `0x76ac97`, `0x76aca2`, `0x76aca8`, `0x76acad`, `0x76acd5`, `0x76ad06`, `0x76ad31`, `0x775140`
Confidence: verified
Proof: one
Test: none

`0x76ac10` compares the new scale with `+0xb8` (`0x76ac1a`), stores it (`0x76ac3b`) and calls slot
0x8c, `0x76ac90`, with the force byte (`0x76ac44`); `0x76ac50` does the same with `+0xbc`.
`0x76ac90` computes `fld [esi+0xbc]; fmul [esi+0xb8]; fstp` (`0x76ac97` to `0x76aca8`), compares
it with the layout scale `+0x7c` (`0x76acad`), calls `0x768360(scale, force)` (`0x76acd5`), slot
0x10 of each region's layout part (`0x76ad06`) and `0x76ac50(scale, force)` for each child
(`0x76ad31`). The Lua `SetScale` refuses a scale that is not above 0.

## Parent change

Giving a frame a new parent first leaves the old parent's children and, when visible, makes the
frame invisible. The frame then takes the parent's stratum, level plus one and effective scale,
or stratum 3, level 0 and scale 1.0 without a parent, and the parent's draw-itself bit; it joins
the parent's children; and, when it was visible and the parent is visible or absent, it is made
visible again.

Addresses: `0x76ab10`, `0x76aa20`, `0x76aab0`, `0x76a400`
Confidence: verified
Proof: one
Test: none

`0x76ab10` returns when `+0x9c` already holds the parent; it calls `0x76aab0` on the old parent,
slot 0x84 when `+0xd4` was set, stores `+0x9c`, then `0x76a470`, `0x76a4f0(level + 1, 0)` and
`0x76ac50(parent+0x7c, 0)`, or 3, 0 and 1.0; `0x76a400(bit 0xd of the parent's +0xb4, -1)`;
`0x76aa20` on the parent; and slot 0x88 under the stated condition. `0x76aa20` links a 0xc-byte
node tagged `.?AUSIMPLEFRAMENODE@@` holding the child into `+0x2fc`; `0x76aab0` frees the node of
a child. `0x76a400(a, b)` sets or clears bit 0x2000 by `a` and, when `b` is not negative, bit
0x4000 by `b`; when `a` is set it marks the frame's own five layers in `+0x1f8` through `0x76b530`;
then it calls itself with `(a, -1)` on each child.
