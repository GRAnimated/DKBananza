## VoxelConst

The `VoxelConst` folder contains a folder for every stage with voxel geometry. Inside, it contains several folders containing the stage's voxel geometry. It's not yet identified how the game uses which geometry folder.

## Rundown

```
RubberAthleticStage:
- MaterialTable.bin
- 3c5935ba-9b5f-456e-a7f0-2c495c67a000:
    - ebody.bin
    - ehead.bin
    - Info.bin
    - vbody.bin
    - vhead.bin
- RubberAthleticParts00_Default:
    - ebody.bin
    - ehead.bin
    - Info.bin
    - vbody.bin
    - vhead.bin
```

`v` files contain voxel cell data. `e` files contain hermite edge data.

### Voxel Blocks

The vbody files contain voxel cell data. Every voxel block contains 512 8-byte cells.

4096 (0x1000) bytes maximum per block.

#### Voxel cells

| Offset  | Size (in bytes) | Type | Field                               |
| ------- | --------------- | ---- | ----------------------------------- |
| 0x0     | 1               | u8   | Density, contour threshold is 127.5 |
| 0x1     | 1               | u8   | Material ID 1                       |
| 0x2     | 1               | u8   | Material ID 2                       |
| 0x3     | 1               | u8   | Material blend weight               |
| 0x4     | 1               | u8   | Flags                               |
| 0x5-0x7 |                 |      | Unknown                             |

### Edge Blocks

The ebody files contain hermite edge data. Every edge block contains 512 records.
Edge records are 9 bytes each. 4608 (0x1200) bytes maximum per block.

#### Hermite Edge Data

Each 9-byte record in `ebody.bin` corresponds to one cell in an 8x8x8 block and stores Hermite data.

| Offset | Size (in bytes) | Type | Field      |
| ------ | --------------- | ---- | ---------- |
| 0x0    | 1               | u8   | X crossing |
| 0x1    | 1               | u8   | Y crossing |
| 0x2    | 1               | u8   | Z crossing |
| 0x3    | 1               | s8   | X normal X |
| 0x4    | 1               | s8   | X normal Z |
| 0x5    | 1               | s8   | Y normal X |
| 0x6    | 1               | s8   | Y normal Z |
| 0x7    | 1               | s8   | Z normal X |
| 0x8    | 1               | s8   | Z normal Z |

Crossings:
- X crossing: Intersection along the edge from $(x, y, z)$ to $(x+1, y, z)$
- Y crossing: Intersection along the edge from $(x, y, z)$ to $(x, y+1, z)$
- Z crossing: Intersection along the edge from $(x, y, z)$ to $(x, y, z+1)$

| Bits | Field                                    |
| ---- | ---------------------------------------- |
| 0    | Sign of the surface normal's Y component |
| 1-7  | Fractional crossing position             |

Pseudocode:
```py
cell = # X,Y,Z crossing, X[2],Y[2],Z[2] normals
crossing = cell.crossing[axis]

# to decode an edge's position and normal:
    start =  # vec3
    end =    # vec3

    if code <= 1:
        return None

    float t  = ((crossing >> 1) - 1) / 126.0
    pos = start + t * (end - start)

    nx = cell.normal_x / 127.0
    nz = cell.normal_z / 127.0
    ny = sqrtf(1.0 - nx * nx - nz * nz)
    if code & 1:
        ny = -ny
    
    normal = normalize({nx, ny, nz})
    return (pos, normal)
```

## Formats

### MaterialTable.bin

| Offset | Size (in bytes) | Type                      | Field                                        |
| ------ | --------------- | ------------------------- | -------------------------------------------- |
| 0x00   | 2               | u16                       | Version, probably. Always 1 in 1.0.0, anyway |
| 0x02   | 2               | u16                       | Material Count                               |
| 0x04   | ...             | char[0x40][materialCount] | Fixed length 0x40 material name strings      |


### Info.bin

File size is always 0x24.

| Offset | Size (in bytes) | Type | Field            |
| ------ | --------------- | ---- | ---------------- |
| 0x00   | 4               |      | Magic `'VX\0\0'` |
| 0x04   | 4               | unk  |                  |
| 0x08   | 4               | unk  |                  |
| 0xC    | 4               | u32  | X dimension      |
| 0x10   | 4               | u32  | Y dimension      |
| 0x14   | 4               | u32  | Z dimension      |
| 0x18   | 4               | f32  | unknown float    |
| 0x1C   | 4               | f32  | unknown float    |
| 0x20   | 4               | f32  | unknown float    |

### {v,e}head.bin

For every block in the volume, this file contains a bitmap 
indicating whether the block contains data in MSB order.

Pseudocode:
```py
info = open('Info.bin')

vx, vy, vz = info.dimensions
voxel_count = vx * vy * vz

# each block contains 512 voxels
bx = (vx + 7) // 8
by = (vy + 7) // 8
bz = (vz + 7) // 8
block_count = bx * by * bz

head = open('vhead.bin')
bitmap = head.bytes

# to verify the bitmap size:
#   round up the amount of voxels (each block contains 512 voxels)
bitmap_size = (block_count + 7) // 8

# to convert into a linear index
index = x + y * bx + z * bx * by

# to find the corresponding head bit
byte = index // 8
bit = 7 - (index % 8)

# to check if a block exists
if bitmap[byte] & (1 << bit):
    ...
```

### vbody.bin

This file contains ZSTD frames of voxel blocks.

| Offset | Size (in bytes) | Type       | Field |
| ------ | --------------- | ---------- | ----- |
| 0x00   |                 | Frame[...] |       |

#### Compressed Frame

| Offset | Size (in bytes) | Type         | Field             |
| ------ | --------------- | ------------ | ----------------- |
| 0x00   | 4               | u32          | Compressed length |
| 0x04   | 4               | ZSTD payload | Compressed frame  |
