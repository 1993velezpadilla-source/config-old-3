#!/usr/bin/env python3
"""Build a profile-specific CTW Android ARM64 proxy from verified runtime headers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import emit_runtime_bundle


NDK_VERSION = "27.2.12479018"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_ndk(explicit: Path | None = None) -> Path:
    candidates = []
    if explicit is not None:
        candidates.append(explicit)

    for key in ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value))

    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(key)
        if value:
            root = Path(value) / "ndk"
            candidates.append(root / NDK_VERSION)
            if root.is_dir():
                candidates.extend(
                    sorted(
                        [p for p in root.iterdir() if p.is_dir()],
                        reverse=True,
                    )
                )

    for path in candidates:
        toolchain = path / "build/cmake/android.toolchain.cmake"
        if toolchain.is_file():
            return path

    raise FileNotFoundError(
        "Android NDK not found; pass --ndk or set ANDROID_NDK_HOME"
    )


def build_verified_loader(
    libgame: Path,
    profile: Path,
    catalog: Path,
    source_dir: Path,
    work_dir: Path,
    out_loader: Path,
    *,
    ndk: Path | None = None,
    shadowhook_dir: Path | None = None,
    cmake: str = "cmake",
    run=subprocess.run,
) -> dict:
    ndk_dir = find_ndk(ndk)
    generated_dir = work_dir / "generated"
    build_dir = work_dir / "cmake"

    bundle = emit_runtime_bundle.emit_runtime_bundle(
        libgame,
        profile,
        catalog,
        generated_dir,
    )
    variant = bundle["loader_variant"]

    if variant == "shadowhook":
        if shadowhook_dir is None:
            raise ValueError(
                "verified profile requires ShadowHook; pass --shadowhook-dir"
            )
        shadowhook_dir = shadowhook_dir.resolve()
        if not (
            shadowhook_dir
            / "shadowhook/src/main/cpp/shadowhook.c"
        ).is_file():
            raise FileNotFoundError(
                "invalid ShadowHook source checkout"
            )

    toolchain = ndk_dir / "build/cmake/android.toolchain.cmake"
    configure = [
        cmake,
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
        "-DANDROID_ABI=arm64-v8a",
        "-DANDROID_PLATFORM=android-28",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCTW_GENERATED_DIR={generated_dir}",
        f"-DCTW_USE_SHADOWHOOK={'ON' if variant == 'shadowhook' else 'OFF'}",
    ]
    if variant == "shadowhook":
        configure.append(f"-DCTW_SHADOWHOOK_DIR={shadowhook_dir}")

    run(configure, check=True)
    run([cmake, "--build", str(build_dir), "--parallel"], check=True)

    built = build_dir / "libGame.so"
    if not built.is_file():
        raise FileNotFoundError(
            f"profile-specific loader was not produced: {built}"
        )

    out_loader.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, out_loader)

    report = {
        "ok": True,
        "loader_variant": variant,
        "loader": str(out_loader),
        "loader_sha256": _sha256_file(out_loader),
        "generated_dir": str(generated_dir),
        "profile_header_sha256": bundle["profile_header_sha256"],
        "adapter_header_sha256": bundle["adapter_header_sha256"],
        "binary_fingerprint": bundle["binary_fingerprint"],
        "adapter_count": bundle["adapter_count"],
        "ndk": str(ndk_dir),
        "android_abi": "arm64-v8a",
        "android_platform": 28,
        "note": (
            "This loader was compiled against the exact generated profile and "
            "adapter headers recorded above. Generic template artifacts are not "
            "accepted as substitutes for a verified runtime build."
        ),
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument(
        "--catalog",
        type=Path,
        default=emit_runtime_bundle.adapter_emit_c.DEFAULT_CATALOG,
    )
    ap.add_argument(
        "--source-dir",
        type=Path,
        default=Path(
            "projects/gtactw-android-3d/android-loader"
        ),
    )
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ndk", type=Path)
    ap.add_argument("--shadowhook-dir", type=Path)
    ap.add_argument("--cmake", default="cmake")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        result = build_verified_loader(
            args.libgame,
            args.profile,
            args.catalog,
            args.source_dir,
            args.work_dir,
            args.out,
            ndk=args.ndk,
            shadowhook_dir=args.shadowhook_dir,
            cmake=args.cmake,
        )
    except subprocess.CalledProcessError as exc:
        print(json.dumps({
            "ok": False,
            "stage": "cmake",
            "returncode": exc.returncode,
        }, indent=2))
        return 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
