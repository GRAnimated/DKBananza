# Donkey Kong Bananza's Voxel Data

Donkey Kong Bananza uses a Dual Contouring algorithm for voxels. The game builds voxel meshes in two stages:
- CPU: Builds and updates the voxel octree, solves the Hermite-data QEF for contour vertices, and traverses the octree to 
determine which cells connect around crossed edges. It then processes the resulting triangle/quad records into mesh data.
- GPU: A compute pass dispatches shaders named alVoxelCreateVertex and alVoxelCreateIndex to create vertex and index data.

Terrain voxel volumes are stored as a sparse grid of 8x8x8 voxel chunks. The [Formats](#Formats) section explains the game's formats, but in summary:
- `MaterialTable.bin` - The volume's table of material values. Additional entries for merged materials and actors are created at stage init.
- `Info.bin` - Stores the volume's X/Y/Z dimensions in chunks.
- `vhead.bin` - Stores a bitmap of which volumes contain any voxel data.
- `vbody.bin` - Stores ZSTD compressed payloads of voxel chunks.
- `ehead.bin` - Stores a bitmap of which volumes contain any edge data.
- `ebody.bin` - Stores ZSTD compressed payloads of edge records.

Body files must contain the amount of present volumes reported by the bitmap, because bodies are indexed by the bitmap index. Density alone would create smooth meshes, and that's where Dual Contouring comes in to preserve purposefully sharp edges. The cells in 8x8x8 voxel chunks store density (0-255), damage, material ID, and wetness.

Level designers were able to assemble simple primitives and used Boolean operations to add/cut terrain. Nintendo's CEDEC 2026 presentation reports modeling being done in Maya and voxel conversion in Houdini before exporting to binary files.

Here are some good references on the technique:
- [Donkey Kong Bananza's CEDEC 2026 voxel slides (sample)](https://dev.classmethod.jp/en/articles/cedec-2026-voxel/)
- [Jérôme Mahuet's Dual Contouring notes](https://jeromem.dev/Notes/Dual+Contouring)
- [Matt Keeter's QEF Explainer blog post](https://www.mattkeeter.com/projects/qef/)

## File Tree

```
romfs/
├── Voxel/
│   ├── Const/
│   │   ├── <StageScenario>/                    # Example: ForestLevelStageScenario01
│   │   │   ├── MaterialTable.bin
│   │   │   └── <Volume>/                       # Names: <Parts>_Default, <Parts>_Defalt, placement GUID
│   │   │       ├── Info.bin
│   │   │       ├── vhead.bin
│   │   │       ├── vbody.bin
│   │   │       ├── ehead.bin
│   │   │       └── ebody.bin
│   │   ├── Geometry/<Parts>.alsarc.zs          # SARC holding <Parts>.al__gen__VoxelGeometry.bgyml
│   │   ├── VoxelMaterial/<Mat>.vmat.zs         # 736 files; VoxelMaterial + VoxelMaterialShaderType bgyml
│   │   ├── VoxelFieldMaterialResource/*.bgyml
│   │   ├── VoxelMeshLodParam/*.bgyml           # LOD distances/values
│   │   ├── VoxelDepthWetParam/*.bgyml          # wetness params
│   │   └── *.alsarc.zs                         #   VoxelMaterialType, VoxelPartsType,
│   │                                           #   VoxelMaterialPreset, VoxelMaterialPattern,
│   │                                           #   VoxelMaterialNatureList, MaterialSoundType
│   └── ObjectData/Voxel/<Parts>.alsarc.zs      # Actor geometry: <Mat>.vgeob ("VGEOB") and some <Name>.hgeob ("HGEOB")
└── VoxelGeometryMaterialPriorityTable.alsarc.zs
```

## Formats

### MaterialTable.bin

| Offset | Size (in bytes) | Type                      | Field                                         |
| ------ | --------------- | ------------------------- | --------------------------------------------- |
| 0x00   | 2               | u16                       | Version, probably. Always 1 in 1.0.0, anyway. |
| 0x02   | 2               | u16                       | Material Count                                |
| 0x04   | ...             | char[0x40][materialCount] | Fixed length 0x40 material name strings       |


### Info.bin

File size is always 0x24.

| Offset | Size (in bytes) | Type | Field            |
| ------ | --------------- | ---- | ---------------- |
| 0x00   | 4               |      | Magic `'VX\0\0'` |
| 0x04   | 4               |      | unknown          |
| 0x08   | 4               |      | unknown          |
| 0xC    | 4               | u32  | X dimension      |
| 0x10   | 4               | u32  | Y dimension      |
| 0x14   | 4               | u32  | Z dimension      |
| 0x18   | 4               | f32  | X cell size      |
| 0x1C   | 4               | f32  | Y cell size      |
| 0x20   | 4               | f32  | Z cell size      |

### {v,e}head.bin

For every chunk in the volume, this file contains a bitmap indicating whether the chunk contains data in MSB order.

Pseudocode:
```py
info = open('Info.bin')

vx, vy, vz = info.dimensions
voxel_count = vx * vy * vz

# each chunk contains 512 voxels
bx = (vx + 7) // 8
by = (vy + 7) // 8
bz = (vz + 7) // 8
chunk_count = bx * by * bz

head = open('vhead.bin')
bitmap = head.bytes

# to verify the bitmap size:
#   round up the amount of voxels (each chunk contains 512 voxels)
bitmap_size = (chunk_count + 7) // 8

# to convert into a linear index
index = x + y * bx + z * bx * by

# to find the corresponding head bit
byte = index // 8
bit = 7 - (index % 8)

# to check if a chunk exists
if bitmap[byte] & (1 << bit):
    ...
```

### vbody.bin

Contains ZSTD frames of voxel chunks. A chunk can contain 512 8-byte cells, or 512 5-byte cells, and a maximum of 0x1000 bytes maximum per chunk.

| Offset | Size (in bytes) | Type       | Field |
| ------ | --------------- | ---------- | ----- |
| 0x00   |                 | Frame[...] |       |

#### Compressed Frame

| Offset | Size (in bytes) | Type         | Field             |
| ------ | --------------- | ------------ | ----------------- |
| 0x00   | 4               | u32          | Compressed length |
| 0x04   | 4               | ZSTD payload | Compressed frame  |


#### Voxel cells

| Offset  | Size (in bytes) | Type          | Field                                                                                                 |
| ------- | --------------- | ------------- | ----------------------------------------------------------------------------------------------------- |
| 0x0     | 1               | u8            | Density, contour threshold is 127.5. 128-255 are solid.                                               |
| 0x1     | 1               | u8            | Material ID 1                                                                                         |
| 0x2     | 1               | u8            | Material ID 2                                                                                         |
| 0x3     | 1               | u8            | Material blend weight. 0 selects the first, 255 selects the second, in between is a mix between both. |
| 0x4     | bits 0-3        | nibble (0-15) | Damage                                                                                                |
| 0x4     | bit 5           | 5             | Material override flag                                                                                |
| 0x5     | bits 0-3        | nibble (0-15) | Wetness, doesn't exist in the 5-byte cells                                                            |
| 0x5-0x7 | bits 3-20       |               | Unknown, doesn't exist in the 5-byte cells                                                            |

### ebody.bin

Contains hermite edge data. Every edge chunk contains 512 records. Edge records are 9 bytes each. Maximum of 0x1200 bytes per chunk.

Each 9-byte record in `ebody.bin` corresponds to one cell in an 8x8x8 chunk.

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
