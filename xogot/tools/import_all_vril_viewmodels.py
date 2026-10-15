#!/usr/bin/env python3
"""Loss-aware Quake MDL (NZ:P/Vril viewmodels) -> Godot glTF 2.0 GLB.

Reads ALL v_*.mdl from nzp-team/assets/common/models/weapons. No FPS-template
stand-ins and no recreated animations: every actual MDL vertex frame becomes
a glTF morph target and a STEP key in the original-frame timeline. Quake's
MDL format does not contain bones; this intentionally preserves its baked
hand/weapon motion rather than fabricating an armature.

This is a conversion tool, not an FPS renderer. Its output is a preview set.
"""
from __future__ import annotations
import argparse
import io
import json
import math
import re
import struct
from pathlib import Path

MAGIC = b"IDPO"
MAX_VERTICES = 20000
MAX_TRIANGLES = 40000
MAX_FRAMES = 600
MAX_SKIN_PIXELS = 16_777_216


class Reader:
    def __init__(self, blob):
        self.data = blob
        self.pos = 0

    def read(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError(f"truncated MDL at byte {self.pos} (+{count})")
        chunk = self.data[self.pos:self.pos + count]
        self.pos += count
        return chunk

    def unpack(self, fmt):
        return struct.unpack("<" + fmt, self.read(struct.calcsize("<" + fmt)))

    def skip(self, count):
        self.read(count)


def read_frame(reader, numverts, scale, translate):
    reader.skip(8)  # bboxmin, bboxmax (trivertx_t)
    name = reader.read(16).split(b"\0", 1)[0].decode("ascii", "replace")
    packed = reader.read(numverts * 4)
    vertices = []
    for offset in range(0, len(packed), 4):
        x, y, z = packed[offset:offset + 3]
        qx = x * scale[0] + translate[0]
        qy = y * scale[1] + translate[1]
        qz = z * scale[2] + translate[2]
        # Quake: +X forward, +Y left, +Z up.
        # Godot/glTF: -Z forward, +X right, +Y up. 64 Quake units = 1 m.
        vertices.append((-qy / 64.0, qz / 64.0, -qx / 64.0))
    return name, vertices


def parse_mdl(path):
    reader = Reader(path.read_bytes())
    if reader.read(4) != MAGIC:
        raise ValueError("not Quake IDPO MDL (magic mismatch)")
    (version,) = reader.unpack("i")
    if version != 6:
        raise ValueError(f"Quake MDL version {version}, expected 6")
    scale = reader.unpack("3f")
    translate = reader.unpack("3f")
    reader.skip(4 + 12)  # radius and eye position
    skins, skin_w, skin_h, nverts, ntris, nframes, synctype, flags = reader.unpack("8i")
    reader.skip(4)  # bounding box size
    if not (0 <= skins <= 64 and 1 <= skin_w <= 4096 and 1 <= skin_h <= 4096):
        raise ValueError("invalid skin counts or dimensions")
    if skin_w * skin_h > MAX_SKIN_PIXELS:
        raise ValueError("skin exceeds safety limit")
    if not (3 <= nverts <= MAX_VERTICES and 1 <= ntris <= MAX_TRIANGLES and 1 <= nframes <= MAX_FRAMES):
        raise ValueError(f"implausible mesh/frame header: {nverts}, {ntris}, {nframes}")
    for _ in range(skins):
        (skin_type,) = reader.unpack("i")
        if skin_type == 0:
            reader.skip(skin_w * skin_h)
        elif skin_type == 1:
            (count,) = reader.unpack("i")
            if not 1 <= count <= 100:
                raise ValueError("bad grouped skin count")
            reader.skip(count * 4 + count * skin_w * skin_h)
        else:
            raise ValueError(f"unknown skin type {skin_type}")
    texcoords = [reader.unpack("3i") for _ in range(nverts)]
    triangles = [reader.unpack("4i") for _ in range(ntris)]
    for front, a, b, c in triangles:
        if min(a, b, c) < 0 or max(a, b, c) >= nverts:
            raise ValueError("triangle vertex outside vertex table")
    frames = []
    names = []
    for _ in range(nframes):
        (frame_type,) = reader.unpack("i")
        if frame_type == 0:
            name, positions = read_frame(reader, nverts, scale, translate)
            names.append(name)
            frames.append(positions)
        elif frame_type == 1:
            (count,) = reader.unpack("i")
            if not 1 <= count <= MAX_FRAMES or len(frames) + count > MAX_FRAMES:
                raise ValueError("grouped frame count exceeds safety limit")
            reader.skip(8 + 4 * count)  # bbox and float frame intervals
            for _ in range(count):
                name, positions = read_frame(reader, nverts, scale, translate)
                names.append(name)
                frames.append(positions)
        else:
            raise ValueError(f"unknown frame type {frame_type}")
    corners = []
    uv = []
    for front, *vertex_ids in triangles:
        for index in vertex_ids:
            onseam, s, t = texcoords[index]
            u = s + (skin_w * 0.5 if onseam and not front else 0.0)
            corners.append(index)
            uv.extend(((u + 0.5) / skin_w, (t + 0.5) / skin_h))
    return {"skin_size": [skin_w, skin_h], "faces": ntris,
            "vertices": nverts, "frames": frames, "names": names,
            "corners": corners, "uv": uv}


class BufferBuilder:
    def __init__(self):
        self.buffer = bytearray()
        self.views = []
        self.accessors = []

    def view(self, raw, target=None):
        while len(self.buffer) % 4:
            self.buffer.append(0)
        offset = len(self.buffer)
        self.buffer.extend(raw)
        item = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target is not None:
            item["target"] = target
        self.views.append(item)
        return len(self.views) - 1

    def accessor(self, raw, kind, size, component=5126, target=None, bounds=False):
        view = self.view(raw, target)
        entry = {"bufferView": view, "componentType": component,
                 "count": len(raw) // (size * (4 if component in (5125, 5126) else 2)),
                 "type": kind}
        if bounds and raw:
            vals = struct.unpack("<" + "f" * (len(raw) // 4), raw)
            entry["min"] = [min(vals[i::size]) for i in range(size)]
            entry["max"] = [max(vals[i::size]) for i in range(size)]
        self.accessors.append(entry)
        return len(self.accessors) - 1


def floats(values):
    values = list(values)
    return struct.pack("<" + "f" * len(values), *values)


def make_glb(data, png_bytes, output, fps):
    # Duplicate UV seam vertices as required by glTF's per-corner UV topology.
    corners = data["corners"]
    frames = data["frames"]
    first = [coord for i in corners for coord in frames[0][i]]
    builder = BufferBuilder()
    pos = builder.accessor(floats(first), "VEC3", 3, target=34962, bounds=True)
    tex = builder.accessor(floats(data["uv"]), "VEC2", 2, target=34962)
    indices = list(range(len(corners)))
    idx = builder.accessor(struct.pack("<" + "I" * len(indices), *indices),
                           "SCALAR", 1, component=5125, target=34963)
    targets = []
    for frame in frames[1:]:
        delta = (frame[i][j] - frames[0][i][j] for i in corners for j in range(3))
        target = builder.accessor(floats(delta), "VEC3", 3, target=34962)
        targets.append({"POSITION": target})
    primitive = {"attributes": {"POSITION": pos, "TEXCOORD_0": tex},
                 "indices": idx, "mode": 4}
    if targets:
        primitive["targets"] = targets
    gltf = {"asset": {"version": "2.0", "generator": "XZIEL exact Quake MDL frame importer"},
            "scenes": [{"nodes": [0]}], "scene": 0,
            "nodes": [{"name": output.stem, "mesh": 0}],
            "meshes": [{"name": output.stem, "primitives": [primitive],
                        **({"weights": [0.0] * len(targets)} if targets else {})}],
            "buffers": [{}]}
    if png_bytes:
        image_view = builder.view(png_bytes)
        gltf["images"] = [{"bufferView": image_view, "mimeType": "image/png"}]
        gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        gltf["textures"] = [{"source": 0, "sampler": 0}]
        gltf["materials"] = [{"name": "original_NZP_skin", "doubleSided": True,
                               "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                        "metallicFactor": 0.0, "roughnessFactor": 0.85}}]
        primitive["material"] = 0
    else:
        gltf["materials"] = [{"doubleSided": True,
                               "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0}}]
        primitive["material"] = 0
    if targets:
        times = [i / fps for i in range(len(frames))]
        weights = []
        for i in range(len(frames)):
            weights.extend(1.0 if j == i - 1 else 0.0 for j in range(len(targets)))
        timeline = builder.accessor(floats(times), "SCALAR", 1, bounds=True)
        weight_stream = builder.accessor(floats(weights), "SCALAR", 1)
        gltf["animations"] = [{
            "name": "original_frames",
            "samplers": [{"input": timeline, "output": weight_stream, "interpolation": "STEP"}],
            "channels": [{"sampler": 0, "target": {"node": 0, "path": "weights"}}]}]
    gltf["bufferViews"] = builder.views
    gltf["accessors"] = builder.accessors
    gltf["buffers"][0]["byteLength"] = len(builder.buffer)
    json_data = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_data += b" " * ((-len(json_data)) % 4)
    binary = bytes(builder.buffer) + b"\0" * ((-len(builder.buffer)) % 4)
    total = 12 + 8 + len(json_data) + 8 + len(binary)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as file:
        file.write(struct.pack("<4sII", b"glTF", 2, total))
        file.write(struct.pack("<I4s", len(json_data), b"JSON"))
        file.write(json_data)
        file.write(struct.pack("<I4s", len(binary), b"BIN\0"))
        file.write(binary)


def png_for(path):
    matches = sorted(path.parent.glob(path.name + "_*.pcx"))
    if not matches:
        return None
    try:
        from PIL import Image
        with Image.open(matches[0]) as img:
            output = io.BytesIO()
            img.convert("RGBA").save(output, format="PNG")
            return output.getvalue()
    except Exception as exc:
        raise RuntimeError(f"PCX decoding failed for {matches[0]}: {exc}") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True,
                        help="Official NZ:P assets checkout, root directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=10.0)
    args = parser.parse_args()
    if not 1 <= args.fps <= 120:
        parser.error("fps must be between 1 and 120")
    source = args.assets / "common/models/weapons"
    if not source.is_dir():
        parser.error(f"Missing official source {source}")
    weapons = sorted(source.rglob("v_*.mdl"))
    if not weapons:
        parser.error("No first-person v_*.mdl sources in assets")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    catalog = {"source": "nzp-team/assets common/models/weapons",
               "license": "See upstream nzp-team/assets/LICENSE.md (CC BY-SA)",
               "coordinate_scale": 64, "fps": args.fps, "weapons": [], "failed": []}
    for weapon in weapons:
        relative = weapon.relative_to(source)
        glb = out / relative.with_suffix(".glb")
        try:
            md = parse_mdl(weapon)
            make_glb(md, png_for(weapon), glb, args.fps)
            catalog["weapons"].append({
                "name": weapon.stem, "source": relative.as_posix(),
                "resource": glb.relative_to(out).as_posix(),
                "frames": len(md["frames"]), "frame_names": md["names"],
                "triangles": md["faces"], "original_vertices": md["vertices"],
                "hands": "as baked in original viewmodel (not inferred)",
                "animation": "original_frames",
            })
            print(f"IMPORT_OK {relative} frames={len(md['frames'])} faces={md['faces']}")
        except Exception as exc:
            catalog["failed"].append({"source": relative.as_posix(), "error": str(exc)})
            print(f"IMPORT_FAILED {relative}: {exc}")
    (out / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"CONVERSION_REPORT: {len(catalog['weapons'])}/{len(weapons)} converted")
    if catalog["failed"]:
        raise SystemExit(f"RED: {len(catalog['failed'])} original viewmodels not converted")


if __name__ == "__main__":
    main()
