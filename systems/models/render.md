# models: drawing

How a scene's sorted elements reach the device: the per-list draw, the texture, lighting, fog and
material state each element sets, the batch draw with its bone palette or software skinning, and
the draw legs of ribbons, particles and custom draws.

The draw lives in M2Scene.cpp (`scene`) with the skinning routines and vertex fills of M2Model.cpp.
`0x708900` draws one list with a 0x335c-byte draw state on the stack; the state remembers the
previous element so unchanged device state is not set again. A batch is a 24-byte record of the
selected view, a submesh a 32-byte record (`shared`). Device calls go through the graphics layer
(`gx`), named here by their state numbers.

Roots: `0x708900`, `0x71a720`, `0x71a9e0`

## List draw

`0x708900(k)` resets the draw state, draws list `k`, and with `k = 0` also the grouped list after
it. A list draw saves the device view, sets an identity view and texture matrix, clears four render
states, and with vertex shaders copies the view into shader constants. It then draws each element
through its kind and copies the element's keys to the previous-element slots; a batched run
(kind 2) advances past the run's length. It ends by restoring the view.

Addresses: `0x708900`, `0x70b0e0`, `0x70b360`, `0x70b728`, `0x70cb30`, `0x70cf70`, `0x70d330`, `0x70d820`, `0x70d8b0`, `0x70d960`, `0x70b330`, `0x70b350`, `0x70dbf0`
Confidence: verified
Proof: one
Test: none

`0x708900` calls `0x70b0e0` on the stack state, then `0x70b360(k, elements, list data, list
count)` with the arrays at scene `+0x54 + 16k` and `+0x50 + 16k`, and again with `+0x44`/`+0x40`
for `k = 0`. `0x70b360` stores the element at `+0x3300`, its kind at `+0x3308`, the instance at
`+0x3310` and dispatches through the six-entry table `0x70b728`: kinds 0 to 5 go to `0x70cb30`,
`0x70cf70`, `0x70d330`, `0x70d820`, `0x70d8b0` and `0x70d960`.

## Texture stages

An element binds up to its batch's texture count of stages. A texture index looked up negative
names a replaceable texture of the instance. Each stage's combine state comes from the table
`0x811f8c` by blend mode (0, 1, 1, 1, 1, 5, 5), the scene float `+0x14` goes to every stage, and
stages past the count are cleared. A stage whose texture unit entry is above 2 gets generated
coordinates; a batch with a texture transform loads the instance's animated texture matrix,
otherwise identity.

Addresses: `0x70b740`, `0x811f8c`
Confidence: verified
Proof: one
Test: none

The texture is `+0xa4[i]` of the instance with `i` from the header's lookup `+0x98` at batch
`+0x10 + k`; the transform index is the lookup `+0xb0` at batch `+0x16 + k`, valid below header
`+0x74`, and selects the 64-byte matrix `+0xb4[i]`. The states are `0x17 + k` (texture),
`0x1f + k` (combine) and `0x27 + k` (the scene float). For a header of version 0x101 the combine
value comes from a per-model table instead of `0x811f8c`.

## Lighting and fog

Lighting is on unless the material has flag 1 or its blend is 5 or 6. Fog is on unless the
material has flag 2 or the lighting record has no fog, and its mode comes from the blend: modes
0 to 2 fog to the record's colour, 3 and 4 to black, 5 to white and 6 to grey 0x808080. The fog
range is the record's start `+0x184` and end `+0x188`. An element straddling the clip plane sets
it as a user clip plane, negated for list 2.

Addresses: `0x70baf0`, `0x811fa8`, `0x811fc4`, `0x70c17c`, `0x70bdeb`
Confidence: verified
Proof: one
Test: none

The tables are `0x811fa8` (1, 1, 1, 1, 1, 0, 0) for lighting and `0x811fc4` (1, 1, 1, 2, 2, 3,
4) for the fog mode, which `0x70bdeb` dispatches through `0x70c17c`. Mode 1 packs the colour at
`+0x190`, each component 0 at or below 0, 255 at or above 1, else `ftol(x·255 + 0.5)`; modes 2, 3
and 4 store 0, 0xffffff and 0x808080. With vertex shaders the fog constants are `−+0x18c` and
`+0x188 · +0x18c`. The clip plane is lighting `+0x1a0`, its four floats negated when `k = 2`.

## Material state

| state | value |
|---|---|
| colour write mask | 0 for a depth-only element, else 0xf |
| blend | the table `0x811fe0` at `7k + blend`; for a depth-only element, 1 when blend is 1 |
| alpha reference | blend 0: 0; blend 1: `ftol(alpha · 224.0)`; otherwise 1 |
| cull | on unless material flag 4 |
| depth test | on unless material flag 8 or instance flag 2 |
| depth write | on unless material flag 0x10 or instance flag 2 |
| normalize | off only for a one-bone submesh whose matrix row has `|len² − 1| ≤ 0.001` or NaN |

The blend table holds 0, 1, 2, 10, 3, 4, 5 for list 0 and 2, 2, 2, 10, 3, 4, 5 for lists 1 and
2. Blend 5 draws with diffuse 0 and emissive 1, blend 6 with emissive 0.5; other blends use the
instance diffuse times the colour animation and the instance emissive, and an unlit material adds
the diffuse into the emissive and zeroes the diffuse.

Addresses: `0x70c190`, `0x811fe0`, `0x70c20f`, `0x70c259`, `0x70c2bc`, `0x70c390`
Confidence: verified
Proof: one
Test: none

`0x70c1f1` compares the blend word with 1 for an element with `+0x8` set; `0x70c20f` reads
`[ecx*4+0x811fe0]` with `ecx = 7k + blend`. The alpha reference multiplies element `+0x10` by
224.0 (`0x812034`) and truncates with `__ftol`. The cull state is `(~flags >> 2) & 1`; depth test
and write test material bits 8 and 0x10 and instance `+0x4` bit 2. The normalize test squares
row 0 of the bone matrix, subtracts 1.0, takes `fabs` and compares with 0.001 (`0x801360`). The
colour states pack each channel clamped to [0, 1] as `x·255 + 0.5`.

## Batch draw

A batch element binds its textures, lighting and material. With vertex shaders it loads the
submesh's bones as a palette of 4×3 matrices and selects the batch's shaders; otherwise it fills a
vertex buffer by skinning the submesh on the CPU. It draws the submesh's triangles as an indexed
triangle list, from the instance's own index buffer when the instance builds its own batches.

Addresses: `0x70cb30`, `0x719930`, `0x719ac0`, `0x719b20`, `0x71dab0`, `0x71dc80`
Confidence: verified
Proof: one
Test: none

The palette takes header `+0x90` lookups from submesh `+0xe` for `+0xc` bones, each a transposed
4×3 of the instance's bone matrix. The vertex shader is cache `+0x102c[elem+0x38]`, the pixel
shader `+0x1030[elem+0x3c]` when it is not −1. Without shaders, a batch with two distinct texture
coordinate sets fills through `0x719ac0`, others through `0x719b20`. The draw passes the start
index `+0x8` and count `+0xa` of the submesh.

## Software skinning

A vertex is 48 bytes: position, four weight bytes, four bone index bytes, normal and texture
coordinates. Its matrix is the bone matrices summed by weight `w/255`, starting from the first
weight and stopping at the first zero weight; a vertex with the same weights and indices as the
previous one reuses its matrix. The output is 32 bytes: position, normal and the texture coordinates
copied. Two routines do this, and the processor picks one when the first instance is built: on a
processor with MMX and SSE, every one the client runs on today, the SSE routine `0x71a9e0`; else
the x87 routine `0x71a720`, which the SSE routine also calls for an output buffer not 16-byte
aligned.

| routine | arithmetic | position, per column | normal, per column |
|---|---|---|---|
| SSE `0x71a9e0` | single precision, `mulps`/`addps` | `((x·m0 + m3) + y·m1) + z·m2` | `(nx·m0 + ny·m1) + nz·m2` |
| x87 `0x71a720` | the FPU's 53-bit precision, partial sums stored as floats | `((m20·z + m10·y) + m00·x) + m30` | `(m00·nx + m20·nz) + m10·ny` |

Addresses: `0x71a720`, `0x71a9e0`, `0x71a460`, `0xcf04c8`, `0x70dd70`, `0x8026c8`, `0x71aaa6`, `0x71aabc`, `0x71aba1`, `0x71abcd`, `0x429bfc`, `0x429c06`
Confidence: verified
Proof: one
Test: none

The constructor `0x70dd70` stores `0x71a720` in `0xcf04c8` and replaces it with `0x71a9e0` when
`OsGetCpuCapabilities()` has bits 2 and 4, which `0x429b90` sets from CPUID leaf 1 EDX bits 23
(MMX, `0x429bfc`) and 25 (SSE, `0x429c06`). `0x71a9e0` widens the weight bytes with `punpcklbw`,
converts them with `cvtpi2ps` (`0x71aaa6`) and multiplies by 1/255 (`0x71aabc`); each bone's four
rows are scaled with `mulps` and added in weight order. The position starts as `x·row0 + row3`
(`0x71aba1`), the normal as `nx·row0` (`0x71abcd`), and the results are written with `movntps`.
`0x71a720` scales by `fild` of the byte times 1/255 (`0x8026c8`) and accumulates the twelve used
entries of each 64-byte bone matrix. `0x71a460` writes 40-byte vertices with a second coordinate set
on the x87 path.

## Ribbon, particle and custom draws

A ribbon, particle or custom element sets its material state, offsets the view to the emitter's
frame, draws, and restores the view and texture matrix. A particle element's material takes its
blend from the emitter record and the flags 4, plus 1 when the record's flag 1 is set, plus 2 when
its flag 8 is set, plus 0x10 when its blend is above 1.

Addresses: `0x70ca50`, `0x70cb10`, `0x70d820`, `0x70d8b0`, `0x70d960`, `0x7b80c0`, `0x7b4b40`
Confidence: verified
Proof: one
Test: none

`0x70ca50` runs the texture, lighting and material setup, adds `R·offset` to the view's translation
(`((m20·oz + m10·oy) + m00·ox) + m30` per column) and sets it. `0x70d820` draws
`0x7b80c0(ribbon, reference frame)`, `0x70d8b0` draws `0x7b4b40(emitter, reference frame)` after
building the material from the record's `+0x4` flags and `+0x28` blend, and `0x70d960` calls the
instance's draw callback `+0x1b8`. `0x70cb10` ends each.

## Grouped and projected draws

A batched run draws several instances of one shared model with one state setup, loading each
instance's palette into constants. A special batch builds a texture matrix from its skinned depth
range widened by 6.0 at each end and calls the scene's special callback around its draw.

Addresses: `0x70d330`, `0x70cf70`, `0x719c20`, `0x71dfa0`
Confidence: inferred
Proof: none
Test: none

`0x70cf70` calls `0x719c20` for the submesh bounds, subtracts 6.0 from the minimum z and adds it
to the maximum, and calls scene `+0x11c`. The per-instance constant layout of `0x70d330` was not
transcribed.
