# models: ribbons

The ribbon emitters a model carries, `CRibbonEmitter`: a trail of edges left behind a moving
bone, each edge a vertex pair above and below the bone, aged out after the ribbon's lifespan and
drawn as a triangle strip.

The class is 0x168 bytes; its code runs from `0x7b6c10` through `0x7b8710`, with its assignment
and frame helpers just before, `0x7b6500` through `0x7b6990`, in the particle object file. A model
creates one ribbon per ribbon record of its header (`0x70ebd0`) and drives it each frame
(`0x718960`); the draw is `render`.

Roots: none

## Ribbon parameters

Each frame the model passes the ribbon its colour and alpha, packed into bytes as `x·255 + 0.5`,
its heights above and below the bone, its texture slot and its visibility, then places it at its
bone and updates it with the elapsed seconds.

Addresses: `0x718960`, `0x7b7a80`, `0x7b7b10`, `0x7b7b90`, `0x7b7ba0`, `0x7b7b70`, `0x7b7b40`, `0x7b76c0`, `0x7b7e60`
Confidence: verified
Proof: one
Test: none

`0x718960` calls the setters only for tracks with more keys than the first-update gate. The
colour packs four floats with `__ftol` after `fmul 255.0; fadd 0.5`; `0x7b7b90` and `0x7b7ba0`
store `+0x15c` and `+0x160`. The placement passes the bone matrix moved to the record's position
and multiplied by the scene matrix, and the instance's reference frame.

## Ribbon update

An update ages the ribbon's edges, drops those older than the lifespan from the ring of vertices,
and emits new edges along the path from the last node to the current one at the ribbon's edge
rate, each with a frame built from the motion.

Addresses: `0x7b7e60`, `0x7b6990`, `0x7b6c30`, `0x7b6f00`, `0x7b73a0`
Confidence: inferred
Proof: none
Test: none

`0x7b73a0` sizes the ring from the edges per second and the lifespan. `0x7b6f00` advances an index
around the ring. The interpolation of new edges was not transcribed.
