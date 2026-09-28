#!/usr/bin/env python3
"""Patch a user-owned CTW split-APK set with the CTW3D proxy loader.

Input may be a directory of APK splits or a ZIP-compatible APKM/XAPK/APKS
container. Output is a directory of unsigned split APKs. Every split is
rewritten without stale signing metadata so the complete set can be aligned
and signed with one key before `adb install-multiple`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile

import apkset_probe
from apk_modpack import (
    GAME_SO,
    ORIGINAL_SO,
    CONFIG_ASSET,
    clone_info,
    is_signature_entry,
)

def rewrite_split(
    source: Path,
    destination: Path,
    loader_bytes: bytes,
    patch_game_split: bool,
    config_bytes: bytes | None = None,
) -> dict:
    removed_signatures = 0
    found_game = False

    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(
        destination, "w", allowZip64=True
    ) as dst:
        names = set(src.namelist())

        if patch_game_split and ORIGINAL_SO in names:
            raise ValueError(
                f"{source.name} already contains {ORIGINAL_SO}; refusing double repack"
            )
        if patch_game_split and GAME_SO not in names:
            raise ValueError(
                f"selected native split {source.name} is missing {GAME_SO}"
            )

        for info in src.infolist():
            name = info.filename
            if is_signature_entry(name):
                removed_signatures += 1
                continue
            if config_bytes is not None and name == CONFIG_ASSET:
                continue

            data = src.read(name)
            if patch_game_split and name == GAME_SO:
                found_game = True
                orig_info = clone_info(info, filename=ORIGINAL_SO)
                orig_info.compress_type = zipfile.ZIP_STORED
                dst.writestr(orig_info, data)
                continue

            dst.writestr(clone_info(info), data)

        if patch_game_split:
            loader_info = zipfile.ZipInfo(GAME_SO)
            loader_info.compress_type = zipfile.ZIP_STORED
            loader_info.external_attr = 0o100755 << 16
            dst.writestr(loader_info, loader_bytes)

        if config_bytes is not None:
            config_info = zipfile.ZipInfo(CONFIG_ASSET)
            config_info.compress_type = zipfile.ZIP_DEFLATED
            config_info.external_attr = 0o100644 << 16
            dst.writestr(config_info, config_bytes)

    if patch_game_split and not found_game:
        raise RuntimeError("selected native split did not yield original libGame.so")

    return {
        "removed_signature_entries": removed_signatures,
        "patched_game_split": patch_game_split,
    }


def build_split_modpack(
    source: Path,
    loader_so: Path,
    out_dir: Path,
    config_ini: Path | None = None,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)
    if not loader_so.is_file():
        raise FileNotFoundError(loader_so)

    loader_bytes = loader_so.read_bytes()
    if not loader_bytes.startswith(b"\x7fELF"):
        raise ValueError("loader is not an ELF shared object")

    config_bytes = None
    if config_ini is not None:
        if not config_ini.is_file():
            raise FileNotFoundError(config_ini)
        config_bytes = config_ini.read_bytes()
        if len(config_bytes) > 1024 * 1024:
            raise ValueError("CTW Mod Hub config is larger than 1 MiB")

    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ctw-split-modpack-") as td:
        temp_root = Path(td)
        apks = apkset_probe.collect_apks(source, temp_root)

        game_splits = []
        asset_splits = []
        split_entries = {}
        for display_name, path in apks:
            if not zipfile.is_zipfile(path):
                raise ValueError(f"{display_name} is not a valid APK")
            with zipfile.ZipFile(path, "r") as zf:
                names = set(zf.namelist())
                split_entries[display_name] = names
                if GAME_SO in names:
                    game_splits.append(display_name)
                if "assets/game.pak" in names:
                    asset_splits.append(display_name)

        if len(game_splits) != 1:
            raise ValueError(
                "expected exactly one split containing ARM64 libGame.so, found "
                f"{len(game_splits)}: {game_splits}"
            )

        game_split = game_splits[0]
        if config_bytes is not None and len(asset_splits) != 1:
            raise ValueError(
                "expected exactly one split containing assets/game.pak for config "
                f"injection, found {len(asset_splits)}: {asset_splits}"
            )
        asset_split = asset_splits[0] if asset_splits else None

        outputs = []
        used_names = set()

        for index, (display_name, path) in enumerate(apks):
            base_name = Path(display_name).name
            if base_name in used_names:
                base_name = f"{index:03d}_{base_name}"
            used_names.add(base_name)

            dest = out_dir / base_name
            stats = rewrite_split(
                path,
                dest,
                loader_bytes,
                patch_game_split=(display_name == game_split),
                config_bytes=(
                    config_bytes
                    if config_bytes is not None and display_name == asset_split
                    else None
                ),
            )
            outputs.append({
                "input_split": display_name,
                "output_apk": str(dest),
                **stats,
            })

    # Verify resulting native split layout.
    patched = [x for x in outputs if x["patched_game_split"]]
    if len(patched) != 1:
        raise RuntimeError("internal error: patched split count is not one")

    with zipfile.ZipFile(Path(patched[0]["output_apk"]), "r") as zf:
        names = set(zf.namelist())
        if GAME_SO not in names or ORIGINAL_SO not in names:
            raise RuntimeError("patched native split lacks proxy/original pair")

    if config_bytes is not None:
        config_holders = []
        for item in outputs:
            with zipfile.ZipFile(Path(item["output_apk"]), "r") as zf:
                if CONFIG_ASSET in zf.namelist():
                    config_holders.append(item["input_split"])
        if config_holders != [asset_split]:
            raise RuntimeError(
                "CTW Mod Hub config must exist exactly once in the selected "
                f"asset split; got {config_holders}, expected {[asset_split]}"
            )

    return {
        "source": str(source),
        "out_dir": str(out_dir),
        "split_count": len(outputs),
        "patched_split": game_split,
        "config_split": asset_split if config_bytes is not None else None,
        "outputs": outputs,
        "next_steps": [
            "zipalign every output APK",
            "sign every output APK with the same signing key",
            "verify every APK with apksigner",
            "install the full set together with adb install-multiple",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--loader-so", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--config", type=Path, help="Optional CTW Mod Hub INI to embed")
    args = ap.parse_args()

    try:
        report = build_split_modpack(
            args.source,
            args.loader_so,
            args.out_dir,
            args.config,
        )
    except Exception as exc:
        print(f"error: {exc}")
        return 2

    print(f"split_count: {report['split_count']}")
    print(f"patched_split: {report['patched_split']}")
    print(f"config_split: {report['config_split']}")
    for item in report["outputs"]:
        print(f"output: {item['output_apk']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
