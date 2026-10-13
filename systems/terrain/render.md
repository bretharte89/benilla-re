# terrain: render

How a visible chunk's texture layers are drawn: on the fixed-function path, one pass per layer
blended by its alpha texture and then the shadow; on the shader path, one pass whose pixel
shader is chosen by the layer count and reads the combined texture.

The code is the chunk draw object file, `0x6be960` through `0x6c07d0`, and the map render file,
`0x6b34e0` through `0x6b7070`, which also draws the map objects' groups. The layer textures
repeat once per cell: the texture matrix scales chunk-relative positions by 1/sy, sy being the
chunk's column step, the y of vertex 1 (+0x84c).

Roots: none.

## Chunk layer draw

`0x6bef30(batch)` draws a chunk's layers unless its view depth less its radius has reached the
fog end `0xc62964`. With the terrain shader flag, or the second shader flag, and a valid shader
for the chunk's layer count whose stages cover layers + 1, it draws in one pass through
`0x6bf690`; otherwise it draws each layer with its alpha texture, then the shadow texture, with
a texture matrix of scale −(−1/sy) relative to the camera.

Addresses: `0x6bef30`, `0x6bf690`, `0xc62964`, `0xc962cc`, `0xc96088`, `0x6bef52`, `0x6bef8d`, `0x6befb1`, `0x6bf035`
Confidence: inferred
Proof: none
Test: none

`0x6bef52` compares +0x78 − +0x68 with `0xc62964` and returns when it is not below. A layer with
flag 0x80 forces the multipass path. `0x6bef8d` loads the shader `0xc962cc[count]` (or
`0xc96088[count]`) and `0x6befb1` compares count + 1 with the device's stage count.
`0x6bf035` divides −1.0 by +0x84c and the matrix is negated and translated by the position less
the camera (`0xc7cf20`); the passes' blend states are not read here.

## Chunk draw pass

`0x684510` draws the frame's chunk list: per chunk it sets the transform to the chunk position
less the camera, gathers and applies the chunk's lights, draws the mesh through `0x6beb50` and
resets the chunk's idle time.

Addresses: `0x684510`, `0x6beb50`, `0x6af9f0`
Confidence: inferred
Proof: none
Test: none

The pass walks `0xc7cad8`. `0x6af9f0`, the chunk vtable's light slot, feeds the global light and
the chunk's lights to the model lighting. The idle time is the +0xac the chunk step ages (`cull`).
