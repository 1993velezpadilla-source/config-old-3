#!/usr/bin/env python3
"""Fail-closed XZIEL Hotstrike asset + Android APK provenance verification.

This checks the actual bytes, not the engine vertex capacity. It cannot
prove visual quality or animation correctness; those require device footage.
No proprietary source asset is committed or published by this script.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from zipfile import ZipFile, BadZipFile

MODEL_IN_GAME = "nzp/models/ai/zfull.mdl"
TEXTURE_IN_GAME = "nzp/models/ai/xziel_zombie_hd_0.png"
RENDERER_BIND_MARKER = b"XZIEL_ZOMBIE_HD: skin="
FORBIDDEN_SYNTHETIC_TRIANGLES = 8284


class ProvenanceError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ProvenanceError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mdl_header(raw):
    require(len(raw) >= 84, "Truncated Quake MDL (header <84 bytes)")
    require(raw[:4] == b"IDPO" and struct.unpack_from("<i", raw, 4)[0] == 6,
            "Converted zombie must be a genuine Quake MDL version 6")
    skin_count, width, height, verts, tris, frames = struct.unpack_from("<6i", raw, 48)
    require(1 <= skin_count <= 16, "Invalid MDL skin count")
    require(1 <= width <= 2048 and 1 <= height <= 2048,
            "MDL skin size exceeds engine safety limit")
    require(1 <= verts <= 16384 and 1 <= tris <= 16384,
            "MDL geometry exceeds Vril 16K limits")
    require(1 <= frames <= 256, "MDL animation count invalid")
    return {"skin_count": skin_count, "skin_width": width, "skin_height": height,
            "vertices": verts, "triangles": tris, "frames": frames}


def verify_author_source(path):
    require(path.is_file(), "Missing original author SZombie.zip: " + str(path))
    with ZipFile(path) as z:
        require(z.testzip() is None, "Corrupt author ZIP")
        names = [n for n in z.namelist() if not n.endswith("/")]
        mesh_sources = [n for n in names if n.lower().endswith((".fbx", ".blend"))]
        images = [n for n in names if n.lower().endswith((".png", ".tga", ".jpg", ".jpeg"))]
        require(mesh_sources, "Source ZIP has no author FBX/Blend mesh")
        require(images, "Source ZIP has no authored PBR textures")
    return {"sha256": sha(path.read_bytes()), "source_meshes": mesh_sources,
            "texture_count": len(images)}


def verify_real_conversion(raw, stock):
    metadata = mdl_header(raw)
    require(metadata["triangles"] != FORBIDDEN_SYNTHETIC_TRIANGLES,
            "REJECTED: 8,284-triangle stock-zombie synthetic benchmark, NOT Hotstrike")
    require(metadata["triangles"] >= 4500 and metadata["vertices"] >= 2000,
            "REJECTED: stock NZ:P low-detail topology, not imported character")
    require(metadata["frames"] >= 100,
            "REJECTED: T-pose / unanimated FBX conversion; QuakeC needs action frames")
    require(raw != stock, "REJECTED: original NZ:P zfull.mdl bytes")
    return metadata


def verify_png(raw):
    require(len(raw) >= 24 and raw[:8] == b"\x89PNG\r\n\x1a\n",
            "New diffuse atlas is not PNG")
    require(raw[12:16] == b"IHDR", "PNG missing IHDR")
    w, h = struct.unpack_from(">II", raw, 16)
    require(1024 <= w <= 2048 and 1024 <= h <= 2048,
            "Zombie texture must be >=1024 and <=2048 pixels each dimension")
    return {"width": w, "height": h, "sha256": sha(raw)}


def archive_payload(apk):
    require(apk.is_file(), "Compiled Android APK missing: " + str(apk))
    with ZipFile(apk) as outer:
        require(outer.testzip() is None, "Broken outer APK archive")
        require("assets/nzp-data.zip" in outer.namelist(),
                "Native NZ:P data archive absent from APK")
        require("lib/arm64-v8a/libmain.so" in outer.namelist(),
                "Compiled Vril ARM64 renderer absent from APK")
        lib = outer.read("lib/arm64-v8a/libmain.so")
        require(RENDERER_BIND_MARKER in lib,
                "No native PNG zombie-renderer binding in ARM64 library")
        payload = outer.read("assets/nzp-data.zip")
    return payload


def verify(source_zip, stock_mdl, converted_mdl, texture, apk):
    authored = verify_author_source(source_zip)
    stock = stock_mdl.read_bytes()
    mdl = converted_mdl.read_bytes()
    diffuse = texture.read_bytes()
    converted = verify_real_conversion(mdl, stock)
    skin = verify_png(diffuse)
    # Verify the *actual delivered APK*, not only an intermediate staging ZIP.
    from io import BytesIO
    with ZipFile(BytesIO(archive_payload(apk))) as game:
        require(game.testzip() is None, "Corrupt nzp-data.zip inside APK")
        require(game.namelist().count(MODEL_IN_GAME) == 1,
                "No unique new zombie model inside APK")
        require(game.namelist().count(TEXTURE_IN_GAME) == 1,
                "No unique HD zombie diffuse atlas inside APK")
        require(game.read(MODEL_IN_GAME) == mdl,
                "APK still embeds old/other zombie: MDL byte mismatch")
        require(game.read(TEXTURE_IN_GAME) == diffuse,
                "APK embeds wrong zombie PNG texture")
    return {"result": "PACKAGING_PROVENANCE_PASS_NOT_DEVICE_GREEN",
            "author_source": authored, "actual_converted_mdl_sha256": sha(mdl),
            "converted_model": converted, "diffuse_png": skin,
            "apk_sha256": sha(apk.read_bytes()),
            "not_verified": ["actual on-device skin binding",
                             "front-facing orientation", "headshot hitbox",
                             "walk/run/attack/death", "Android framerate"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-zip", required=True, type=Path,
                   help="Actual licensed SZombie.zip (never generated Quake subdivisions)")
    p.add_argument("--stock-mdl", required=True, type=Path,
                   help="Original, unmodified NZ:P zfull.mdl to reject the stock model")
    p.add_argument("--converted-mdl", required=True, type=Path,
                   help="Separately retargeted + animated Hotstrike zfull.mdl")
    p.add_argument("--diffuse-png", required=True, type=Path)
    p.add_argument("--apk", required=True, type=Path,
                   help="Final APK, not staging files")
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    try:
        report = verify(a.source_zip, a.stock_mdl, a.converted_mdl,
                        a.diffuse_png, a.apk)
    except (ProvenanceError, BadZipFile, OSError, struct.error) as exc:
        p.exit(1, "XZIEL_REAL_ZOMBIE_IMPORT_BLOCKED: " + str(exc) + "\n")
    result = json.dumps(report, indent=2, sort_keys=True)
    print(result)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(result + "\n", encoding="utf8")


if __name__ == "__main__":
    main()
