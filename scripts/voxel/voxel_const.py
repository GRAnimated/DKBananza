#!/usr/bin/env python3

from dataclasses import dataclass
from pathlib import Path
import argparse
import struct
import subprocess
import itertools
import numpy as np

# Ubuntu: `sudo apt install python3-openvdb`
try:
    import openvdb as vdb
except ImportError:
    import pyopenvdb as vdb

def zstd_decompress(data: bytes):
    result = subprocess.run(["zstd", "-d", "-c"], input=data, capture_output=True, check=True)
    return result.stdout


# MaterialTable.bin
# Returns a list of material names, ID is index
def unpack_material_table(data):
    version, material_count = struct.unpack_from("<HH", data)
    
    offset = 4
    materials = []
    for i in range(material_count):
        name = data[offset:offset+40].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        materials.append(name)
        offset += 40
    return materials


@dataclass
class Info:
    magic: bytes
    _04: int
    _08: int
    dim_x: int
    dim_y: int
    dim_z: int
    _f0: float
    _f1: float
    _f2: float

# Info.bin
def unpack_info(data):
    if len(data) != 36:
        raise ValueError("Info.bin is not size 0x24! Got size ", hex(len(data)))

    fields = struct.unpack("<4sIIIIIfff", data)
    return Info(*fields)


# {v,e}head.bin
def block_present(data, bx, by, bz, x, y, z):
    index = x + y * bx + z * bx * by
    byte = index // 8
    bit = 7 - (index % 8)
    (byte_val,) = struct.unpack_from("<B", data, byte)
    if byte_val & (1 << bit):
        return True
    return False


# Voxel Cell
@dataclass
class VoxelCell:
    density: int
    material_id_1: int
    material_id_2: int
    material_blend_weight: int
    flags: int
    unknown: bytes

def unpack_voxel_cell(data, offset = 0):
    return VoxelCell(*struct.unpack_from("<BBBBB3s", data, offset))

# returns list[VoxelCell]
def unpack_voxel_block(decompressed_block):
    return [unpack_voxel_cell(decompressed_block, i * 8) for i in range(512)]


# Edge Data
@dataclass
class EdgeRecord:
    crossing_x: int
    crossing_y: int
    crossing_z: int
    x_normal_x: int
    x_normal_z: int
    y_normal_x: int
    y_normal_z: int
    z_normal_x: int
    z_normal_z: int

def unpack_edge_record(data, offset = 0):
    return EdgeRecord(*struct.unpack_from("<BBBbbbbbb", data, offset))

# returns list[EdgeRecord]
def unpack_edge_block(decompressed_block):
    return [unpack_edge_record(decompressed_block, i * 9) for i in range(512)]


def decompress_frames(data):
    offset = 0
    total_len = len(data)
    frames = []
    while offset < total_len:
        (compressed_len,) = struct.unpack_from("<I", data, offset)
        offset += 4
        payload = data[offset:offset + compressed_len]
        offset += compressed_len
        frames.append(zstd_decompress(payload))
    return frames


def iter_blocks(vhead_data, bx, by, bz):
    for x, y, z in itertools.product(range(bx), range(by), range(bz)):
        index = x + y * bx + z * bx * by
        byte = index // 8
        bit = 7 - (index % 8)
        if byte < len(vhead_data) and (vhead_data[byte] & (1 << bit)):
            yield x, y, z

def build_voxel_arrays(vhead_data, vbodies, vx, vy, vz):
    bx = (vx + 7) // 8
    by = (vy + 7) // 8
    bz = (vz + 7) // 8

    density_arr = np.zeros((vx, vy, vz), dtype=np.float32)
    mat1_arr = np.zeros((vx, vy, vz), dtype=np.float32)
    blend_arr = np.zeros((vx, vy, vz), dtype=np.float32)

    cell_dtype = np.dtype([
        ("density", "<u1"),
        ("mat1", "<u1"),
        ("mat2", "<u1"),
        ("blend", "<u1"),
        ("flags", "<u1"),
        ("unknown", "V3"),
    ])

    coords = list(iter_blocks(vhead_data, bx, by, bz))
    
    for (b_x, b_y, b_z), raw in zip(coords, vbodies):
        if len(raw) != 512 * 8:
            print(f"Not a 4096-byte block!!!! Got {len(raw)}, skipping")
            continue
        
        cells = np.frombuffer(raw, dtype=cell_dtype).reshape((8, 8, 8))

        x0, y0, z0 = b_x * 8, b_y * 8, b_z * 8
        x1, y1, z1 = min(x0 + 8, vx), min(y0 + 8, vy), min(z0 + 8, vz)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0

        sub = cells[:sx, :sy, :sz]
        density_arr[x0:x1, y0:y1, z0:z1] = sub["density"].astype(np.float32) / 255.0
        mat1_arr[x0:x1, y0:y1, z0:z1] = sub["mat1"].astype(np.float32)
        blend_arr[x0:x1, y0:y1, z0:z1] = sub["blend"].astype(np.float32) / 255.0

    return density_arr, mat1_arr, blend_arr

def write_vdb(output_path, density_arr, mat1_arr, blend_arr, voxel_size = 1.0):
    transform = vdb.createLinearTransform(voxelSize=voxel_size)

    density_grid = vdb.FloatGrid()
    density_grid.name = "density"
    density_grid.transform = transform
    density_grid.copyFromArray(density_arr)

    mat1_grid = vdb.FloatGrid()
    mat1_grid.name = "material_id_1"
    mat1_grid.transform = transform
    mat1_grid.copyFromArray(mat1_arr)

    blend_grid = vdb.FloatGrid()
    blend_grid.name = "material_blend"
    blend_grid.transform = transform
    blend_grid.copyFromArray(blend_arr)

    vdb.write(str(output_path), grids=[density_grid, mat1_grid, blend_grid])

def parse_folder(path, args):
    print(path.name + ":")

    info_path = path / "Info.bin"
    ebody_path = path / "ebody.bin"
    vbody_path = path / "vbody.bin"
    ehead_path = path / "ehead.bin"
    vhead_path = path / "vhead.bin"

    info = unpack_info(info_path.read_bytes())

    # ehead_data = ehead_path.read_bytes()
    # ebody_data = ebody_path.read_bytes()
    # ebodies = decompress_frames(ebody_data)

    vhead_data = vhead_path.read_bytes()
    vbody_data = vbody_path.read_bytes()
    vbodies = decompress_frames(vbody_data)

    vx = info.dim_x
    vy = info.dim_y
    vz = info.dim_z
    voxel_count = vx * vy * vz

    bx = (vx + 7) // 8
    by = (vy + 7) // 8
    bz = (vz + 7) // 8
    block_count = bx * by * bz

    print(f"  Voxel dimensions: {vx, vy, vz}, total count {voxel_count}")
    print(f"  Block dimensions: {bx, by, bz}, total count {block_count}")

    if args.vdb is not None:
        output = args.output
        if output is None:
            output = Path.cwd()
        density_arr, mat1_arr, blend_arr = build_voxel_arrays(vhead_data, vbodies, vx, vy, vz)
        write_vdb((output / path.name).with_suffix(".vdb"), density_arr, mat1_arr, blend_arr)

    # print("  ebody.bin:")
    # for x, y, z in itertools.product(range(bx), range(by), range(bz)):
    #     if block_present(ehead_data, bx, by, bz, x, y, z):
    #         print(f"    {x}, {y}, {z}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", help="Volume directory (containing bin folders)")
    parser.add_argument("--folder", help="folder name to parse, otherwise all of them")
    parser.add_argument("--block", type=int, nargs=3, metavar=("X", "Y", "Z"), help="decoded bytes for a block")
    parser.add_argument("--vdb", action="store_true", help="Convert to .vdb")
    parser.add_argument("-o", "--output", type=Path, help="Output path")
    args = parser.parse_args()

    print(f"Parsing {args.path}:\n")

    material_table_path = args.path / "MaterialTable.bin"
    if material_table_path.is_file():
        print("MaterialTable.bin:")
        material_table_data = material_table_path.read_bytes()
        materials = unpack_material_table(material_table_data)
        for i in range(len(materials)):
            material = materials[i]
            print(f"  {i}: {material}")
        print()

    if args.folder is None:
        # parse all folders
        folders = [f for f in args.path.iterdir() if f.is_dir()]
        for folder_path in folders:
            parse_folder(folder_path, args)
    else:
        parse_folder(args.path / args.folder, args)

if __name__ == "__main__":
    main()
