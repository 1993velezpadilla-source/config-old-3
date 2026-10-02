#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

GLTF_TRANSFORM_PIN = "4.5.0"
KTX_SOFTWARE_PIN = "4.4.2"


@dataclass
class TextureToolchain:
    ready: bool
    gltf_transform: str | None
    gltf_transform_version: str | None
    ktx: str | None
    ktx_version: str | None
    reasons: list[str]


@dataclass
class KTX2Artifact:
    source: str
    output: str
    max_texture_size: int
    valid_glb: bool
    uses_khr_texture_basisu: bool
    texture_count: int
    ktx2_image_count: int
    all_textures_basisu: bool
    all_images_ktx2: bool
    source_bytes: int
    output_bytes: int
    toolchain: dict


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _parse_semver(text: str) -> str | None:
    match = re.search(r"(\d+\.\d+\.\d+)", text or "")
    return match.group(1) if match else None


def _at_least(version: str | None, minimum: str) -> bool:
    if version is None:
        return False
    def parts(v: str) -> tuple[int, int, int]:
        a, b, c = v.split(".", 2)
        return int(a), int(b), int(c)
    return parts(version) >= parts(minimum)


def detect_toolchain() -> TextureToolchain:
    reasons: list[str] = []
    gltf_transform = os.environ.get("HAYUYA_GLTF_TRANSFORM") or shutil.which("gltf-transform")
    ktx = os.environ.get("HAYUYA_KTX") or shutil.which("ktx")

    gt_version = None
    ktx_version = None

    if gltf_transform:
        proc = _run([gltf_transform, "--version"])
        gt_version = _parse_semver(proc.stdout + "\n" + proc.stderr)
        if proc.returncode != 0:
            reasons.append("gltf-transform --version failed")
        elif not _at_least(gt_version, GLTF_TRANSFORM_PIN):
            reasons.append(
                f"gltf-transform {gt_version or 'unknown'} is older than supported {GLTF_TRANSFORM_PIN}"
            )
    else:
        reasons.append("gltf-transform not found")

    if ktx:
        proc = _run([ktx, "--version"])
        ktx_version = _parse_semver(proc.stdout + "\n" + proc.stderr)
        if proc.returncode != 0:
            reasons.append("ktx --version failed")
        elif not _at_least(ktx_version, KTX_SOFTWARE_PIN):
            reasons.append(
                f"KTX-Software {ktx_version or 'unknown'} is older than supported {KTX_SOFTWARE_PIN}"
            )
    else:
        reasons.append("ktx not found")

    return TextureToolchain(
        ready=not reasons,
        gltf_transform=gltf_transform,
        gltf_transform_version=gt_version,
        ktx=ktx,
        ktx_version=ktx_version,
        reasons=reasons,
    )


def _read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError(f"not a valid GLB: {path}")
    version, total_length = struct.unpack_from("<II", data, 4)
    if version != 2 or total_length != len(data):
        raise ValueError(f"invalid GLB header: version={version} length={total_length} actual={len(data)}")

    offset = 12
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        payload = data[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:  # JSON
            return json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
    raise ValueError(f"GLB has no JSON chunk: {path}")


def inspect_basisu_glb(path: Path) -> dict:
    doc = _read_glb_json(path)
    textures = doc.get("textures") or []
    images = doc.get("images") or []
    extensions_used = set(doc.get("extensionsUsed") or [])
    extensions_required = set(doc.get("extensionsRequired") or [])

    basisu_count = 0
    for tex in textures:
        ext = (tex.get("extensions") or {}).get("KHR_texture_basisu")
        if isinstance(ext, dict) and isinstance(ext.get("source"), int):
            basisu_count += 1

    ktx2_images = sum(1 for image in images if image.get("mimeType") == "image/ktx2")
    return {
        "valid_glb": True,
        "texture_count": len(textures),
        "image_count": len(images),
        "basisu_texture_count": basisu_count,
        "ktx2_image_count": ktx2_images,
        "uses_khr_texture_basisu": "KHR_texture_basisu" in extensions_used,
        "requires_khr_texture_basisu": "KHR_texture_basisu" in extensions_required,
        "all_textures_basisu": (not textures) or basisu_count == len(textures),
        "all_images_ktx2": (not images) or ktx2_images == len(images),
    }


def transcode_glb_to_ktx2(
    source: Path,
    output: Path,
    *,
    max_texture_size: int,
    toolchain: TextureToolchain | None = None,
) -> KTX2Artifact:
    source = source.resolve()
    output = output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.read_bytes()[:4] != b"glTF":
        raise ValueError(f"source must be GLB: {source}")
    if max_texture_size < 4:
        raise ValueError("max_texture_size must be >= 4")

    toolchain = toolchain or detect_toolchain()
    if not toolchain.ready or not toolchain.gltf_transform:
        raise RuntimeError(
            "KTX2 toolchain unavailable: " + "; ".join(toolchain.reasons)
        )

    env = os.environ.copy()
    if toolchain.ktx:
        ktx_dir = str(Path(toolchain.ktx).resolve().parent)
        env["PATH"] = ktx_dir + os.pathsep + env.get("PATH", "")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hayuya-ktx2-") as tmp:
        tmp_dir = Path(tmp)
        resized = tmp_dir / "01_resized.glb"
        uastc = tmp_dir / "02_uastc.glb"

        steps = [
            [
                toolchain.gltf_transform,
                "resize",
                str(source),
                str(resized),
                "--width",
                str(max_texture_size),
                "--height",
                str(max_texture_size),
            ],
            [
                toolchain.gltf_transform,
                "uastc",
                str(resized),
                str(uastc),
                "--slots",
                "{normalTexture,occlusionTexture,metallicRoughnessTexture}",
                "--level",
                "4",
                "--rdo",
                "--rdo-lambda",
                "4",
                "--zstd",
                "18",
            ],
            [
                toolchain.gltf_transform,
                "etc1s",
                str(uastc),
                str(output),
                "--quality",
                "255",
            ],
        ]

        for cmd in steps:
            proc = _run(cmd, env=env)
            if proc.returncode != 0:
                raise RuntimeError(
                    "texture transcode failed\n"
                    + "command: " + " ".join(cmd) + "\n"
                    + "stdout:\n" + proc.stdout[-6000:] + "\n"
                    + "stderr:\n" + proc.stderr[-6000:]
                )

    audit = inspect_basisu_glb(output)
    if audit["texture_count"] and not audit["all_textures_basisu"]:
        raise RuntimeError(
            f"partial KTX2 conversion: {audit['basisu_texture_count']}/{audit['texture_count']} textures use KHR_texture_basisu"
        )
    if audit["image_count"] and not audit["all_images_ktx2"]:
        raise RuntimeError(
            f"partial KTX2 image conversion: {audit['ktx2_image_count']}/{audit['image_count']} images are image/ktx2"
        )
    if audit["texture_count"] and not audit["requires_khr_texture_basisu"]:
        raise RuntimeError("KHR_texture_basisu is not marked required on transcoded GLB")

    return KTX2Artifact(
        source=str(source),
        output=str(output),
        max_texture_size=int(max_texture_size),
        valid_glb=bool(audit["valid_glb"]),
        uses_khr_texture_basisu=bool(audit["uses_khr_texture_basisu"]),
        texture_count=int(audit["texture_count"]),
        ktx2_image_count=int(audit["ktx2_image_count"]),
        all_textures_basisu=bool(audit["all_textures_basisu"]),
        all_images_ktx2=bool(audit["all_images_ktx2"]),
        source_bytes=source.stat().st_size,
        output_bytes=output.stat().st_size,
        toolchain=asdict(toolchain),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Physically transcode a GLB's textures to KTX2/Basis Universal."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-texture-size", type=int, required=True)
    parser.add_argument("--doctor", action="store_true")
    args = parser.parse_args()

    tools = detect_toolchain()
    if args.doctor:
        print(json.dumps(asdict(tools), indent=2))
        return 0 if tools.ready else 2

    result = transcode_glb_to_ktx2(
        args.input,
        args.output,
        max_texture_size=args.max_texture_size,
        toolchain=tools,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
