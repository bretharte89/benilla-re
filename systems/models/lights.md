# models: lights

The model lights and the lighting record each instance draws with: a light's type, colours and
position, its link into the scene, how a record keeps the four nearest point lights and sums the
rest into ambient and spherical harmonic terms, the fog it carries, and how it reaches the device.

The code is the object file after M2Model.cpp, from `0x71b090` through `0x71ccf0`; it also holds
the bone and track state constructors the instance uses. A light is a 0x6c-byte record that model
lights, the world and the interface's model frames all use. A lighting record is 0x1b4 bytes; an
instance builds one each frame (`0x7192b0`) unless it borrows its parent's.

Roots: `0x71b4a0`, `0x71b610`, `0x71b620`, `0x71b650`, `0x71b6a0`, `0x71b780`, `0x71b7c0`, `0x71bc30`, `0x71bc70`, `0x71bce0`, `0x71bf90`, `0x71c110`, `0x71c730`

## Light object

`0x71b4a0` initializes a light: type 1 (point), zero position, direction and colours, attenuation
0.7 at `+0x58` and 0.03 at `+0x5c`, disabled and unlinked. A light belongs to a scene (`+0x0`,
with the scene's frame minus one at `+0x4`); setting its type or position relinks an enabled
point light, and enabling links it.

| offset | holds |
|---|---|
| `+0x008` | type: 1 point, other values directional |
| `+0x00c` | position |
| `+0x024` | direction, normalized when longer than 2.384186e-7 |
| `+0x030`, `+0x03c`, `+0x048` | ambient, diffuse and third colour |
| `+0x060` | enabled |
| `+0x064`, `+0x068` | link: address of the previous link, next light |

Addresses: `0x71b4a0`, `0x71b5f0`, `0x71b620`, `0x71b650`, `0x71b6a0`, `0x71b780`, `0x71b610`, `0x71bb30`, `0x71bb60`
Confidence: verified
Proof: one
Test: none

`0x71b4a0` stores 1 at `+0x8` and the bits 0x3f333333 and 0x3cf5c28f at `+0x58` and `+0x5c`.
`0x71b6a0` copies the direction, computes `sqrt((x·x + y·y) + z·z)` and multiplies each component
by its reciprocal when the length's magnitude exceeds 2.384186e-7. `0x71b780` links through
`0x71bb60` when enabling and unlinks through `0x71bb30` when disabling, only for a light with a scene.

## Scene light grid

An enabled point light links into one of the scene's 64×64 grid cells, `floor(x·s) & 63` by
`floor(y·s) & 63` with the scene scale `s`; any other light links into the scene's global list.
The grid is allocated on the first point light. Adding a point's lights to a record takes every
global light and every light of the cells its radius covers, and disables a grid light whose
frame stamp is stale instead of adding it.

Addresses: `0x71bb60`, `0x70a0f0`, `0xceffec`, `0x71bf90`
Confidence: verified
Proof: one
Test: none

`0x71bb60` allocates 0x4000 bytes at scene `+0x1c` with line 0xf0, multiplies x and y by
`0xceffec`, floors them with `0x73ff3f`, truncates with `__ftol` and indexes `cell = 64·yi + xi`.
`0x70a0f0` adds the list at scene `+0x18`, then covers `floor((p − r)·s − 0.5) & 63` through
`floor((p + r)·s + 0.5) & 63` on both axes; a light whose `+0x4` differs from the scene frame
`+0x10` is passed to `0x71b780(light, 0)`.

## Lighting record

`0x71bc30(scene, position)` zeroes a record and stores its scene and position. The record holds
up to four point lights with their squared distances, the summed ambient and directional colours,
27 spherical harmonic terms (nine per channel), the fog and the clip plane.

| offset | holds |
|---|---|
| `+0x004` | position |
| `+0x054` | ambient sum |
| `+0x084`, `+0x0a8`, `+0x0cc` | spherical harmonic terms for red, green, blue |
| `+0x160`, `+0x170`, `+0x180` | nearest point lights, their squared distances, their count |
| `+0x184`, `+0x188`, `+0x18c` | fog start, fog end, `1/(end − start)` |
| `+0x190` | fog colour |
| `+0x19c`, `+0x1a0` | clip plane flag, plane |

Addresses: `0x71bc30`, `0x71c110`
Confidence: verified
Proof: one
Test: none

`0x71bc30` clears 0x6d dwords, stores the scene at `+0x0` and four dwords of the position from
`+0x4`. `0x71c110(colour, start, end)` stores the start, the end, `1.0/(end − start)` as a float
and the three colour floats.

## Adding a light

`LightingAddLight` ignores a disabled light. A point light competes for the four nearest slots by
`(dz² + dy²) + dx²` from the record's position, kept as a max-heap: below four it is inserted, at
four it replaces the farthest when it is strictly nearer. The comparisons use the unrounded sum and
the slot stores it as a float. A NaN distance sifts up past every parent, is dropped when the heap
is full, and on a sift down moves below every child. Any other light adds its ambient colour, its
diffuse colour along its direction, and its third colour into the record's sums.

Addresses: `0x71bf90`, `0x71bfdf`, `0x71c009`, `0x71c04f`, `0x71c08e`, `0x71bc70`, `0x71bce0`, `0x71bf60`
Confidence: verified
Proof: one
Test: none

`0x71bfdf` squares the z difference, adds the y square, then the x square, at the FPU's 53-bit
precision (control word 0x027F), and the sum stays on the stack until `fstp` into `+0x170`.
Insertion sifts up past the parent at `(i − 1) >> 1` unless `fcom` at `0x71c009` sets exactly one
of C0 and C3 (smaller or equal); replacement at `0x71c04f` needs C0 alone; the sift down takes the
first child when it is strictly larger, else the second, and moves it up while `fcom` at `0x71c08e`
sets C0 (smaller, or NaN). The other branch calls `0x71bc70(+0x30)`,
`0x71bce0(+0x3c, +0x24)` and `0x71bf60(+0x48)`.

## Spherical harmonic terms

An ambient colour adds to the ambient sum and `2·sqrt(π)` (3.5449078) times itself to each
channel's constant term. A directional colour, its direction taken through the scene matrix, adds
`colour · direction` per channel and the luminance `0.212671·r + 0.71516·g + 0.072169·b` along
the direction. The terms become shader constants with the irradiance weights 0.282095, 0.325735,
0.273137, 0.236544, 0.136569 and 0.078848.

Addresses: `0x71bc70`, `0x71bce0`, `0x71c4e0`, `0x81207c`
Confidence: inferred
Proof: none
Test: none

`0x71bc70` multiplies by the float at `0x81207c`. The higher-order terms of `0x71bce0` and the
constant layout of `0x71c4e0` were read for their constants only.

## Reaching the device

With vertex shaders, the record's terms and nearest lights become constants. Without, the record
derives a dominant direction from its directional sums, or (0, 0, −1) when they are under 1e-5,
and sets fixed-function lights from it and its nearest point lights; the nearest lights and the
clip plane are first taken into view space.

Addresses: `0x71c160`, `0x71c2f0`, `0x71c730`, `0x71ca80`, `0x71b7c0`
Confidence: inferred
Proof: none
Test: none

`0x71c2f0` normalizes the sum at `+0x3c` into `+0x78`, with colours scaled by 0.25 and 1.25.
`0x71ca80` packs a colour divided by its largest component. `0x71b7c0` fills a device light from a
light for the world.
