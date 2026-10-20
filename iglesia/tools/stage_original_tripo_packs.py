#!/usr/bin/env python3
"""Stage the real 104 isolated user-Tripo GLBs recovered in the project's Library.
The exact 8 original ZIPs, NOT synthetic lookalikes, are the source of truth.
No network queries or fabricated models. Original archive stays unchanged.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import struct

PACK_LOCKS = {
    "altar.zip": [
        "427a6cd1cc5f54e4dec0fec72761872955b9d5820cd4761d48b247ea79decd5f",
        9
    ],
    "candleholders.zip": [
        "3627fcd408fdac84594edb4cc40d8c7ce28e5e580e1e6aca4878e31f7c801d6f",
        19
    ],
    "chandeliers.zip": [
        "51343ba8401df1e562a6e6b89730c05a9bb1d74f399418ddda45bd44162792d3",
        11
    ],
    "furniture.zip": [
        "2d26885f668d9bb019c0495d235888d3c1eccc92e941a97f6dc5edc8e08b5ddd",
        12
    ],
    "ruins.zip": [
        "011a889e61bbd5fc4fdbee8aa197aacfe97d15ae6e2d0425350a235bf47a7348",
        29
    ],
    "stained_multi.zip": [
        "c208d73bf2a7a2563237b8a85a49411f185322cb4c681427b375e47cc87622f5",
        11
    ],
    "stained_single.zip": [
        "37248a62c128ae8536809cd91da2c7ba3f98ea569617b323c7fa6444377f33fe",
        1
    ],
    "statues.zip": [
        "35da7f3908a8214ed3a323b21c000116e7089509452b593b9d6177c57c0c64f7",
        12
    ]
}
FOLDERS = ("iglesia/source_tripo_packs", "assets/tripo_packs",
           "iglesia/original_tripo_archives")
# Full 104-object census; current main nave only gets sensible amounts of
# scenery. Original source models are not destroyed to meet mobile budgets.
VISIBLE_IN_MAIN_NAVE = {"chandeliers": (1, 3, 5, 7),
                        "candleholders": (1, 3, 6, 8, 10, 12)}
WALL_MOUNTED_CANDLEHOLDERS = frozenset((1, 3, 6, 8))
CATEGORY_TO_KIND = {"chandeliers": "ceiling_chandelier",
                    "candleholders": "standing_candelabrum"}

def archive_paths(repo: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for base in FOLDERS:
        for name in PACK_LOCKS:
            path = repo / base / name
            if path.is_file():
                if name in found and sha256(path.read_bytes()).digest() != sha256(found[name].read_bytes()).digest():
                    raise RuntimeError("CONFLICTING_TRIPO_PACK_SOURCE " + name)
                found[name] = path
    return found

def _gltf_images(original: bytes) -> list[str]:
    if len(original) < 20 or original[:4] != b"glTF":
        raise ValueError("SPLIT_TRIPO_GLB_BAD_HEADER")
    count = struct.unpack_from("<I", original, 12)[0]
    document = json.loads(original[20:20 + count])
    return [item["uri"] for item in document.get("images", [])
            if "uri" in item and not item["uri"].startswith("data:")]

def stage_archived_tripo(repo: Path, assets: Path, previous_fixtures: list[dict]) -> dict:
    source = archive_paths(repo)
    if not source:
        print("ORIGINAL_TRIPO_104_SOURCE_IN_LIBRARY: packages recovered there, not committed to GitHub")
        return {"packages_found": 0, "models_audited": 0, "assets_staged": 0,
                "visible_fixtures": previous_fixtures, "archive_entries": []}
    # Treat *partial* recovery as a red gate rather than claiming all 104.
    if len(source) != len(PACK_LOCKS):
        missing = sorted(set(PACK_LOCKS) - set(source))
        raise RuntimeError("TRIPO_LIBRARY_PACKS_PARTIAL_NOT_104 " + ",".join(missing))

    # Independently revalidate the *exact original recovered media* so no
    # prettified/stock replacement can be shipped with a misleading label.
    hash_manifest = repo / "iglesia/docs/TRIPO_FIRST_ROOM_SOURCE_SHA256.json"
    expected = json.loads(hash_manifest.read_text(encoding="utf-8"))
    locked_models = expected["first_room_original_glb_sha256"]
    locked_textures = expected["first_room_4096_pbr_sha256"]
    if len(locked_models) != 10 or len(locked_textures) != 6:
        raise RuntimeError("TRIPO_FIRST_ROOM_SOURCE_LOCK_MANIFEST_RED")
    for rel, sha in locked_models.items():
        group, model = rel.split("/", 1)
        with ZipFile(source[group + ".zip"]) as locked_zip:
            actual = sha256(locked_zip.read(group + "/" + model + ".glb")).hexdigest()
        if actual != sha:
            raise RuntimeError("TRIPO_FIRST_ROOM_ORIGINAL_MESH_SHA_RED " + rel)
    for rel, sha in locked_textures.items():
        group, _ = rel.split("/", 1)
        with ZipFile(source[group + ".zip"]) as locked_zip:
            actual = sha256(locked_zip.read(rel)).hexdigest()
        if actual != sha:
            raise RuntimeError("TRIPO_FIRST_ROOM_ORIGINAL_PBR_SHA_RED " + rel)
    print("IGLESIA_USER_ORIGINAL_FIRSTROOM_10_GLB_6_PBR_SOURCE_LOCK_GREEN")
    all_entries: list[dict] = []
    visible: list[dict] = []
    counts: dict[str, int] = {}
    for name, (expected_hash, expected_count) in PACK_LOCKS.items():
        archive = source[name]
        observed_hash = sha256(archive.read_bytes()).hexdigest()
        if observed_hash != expected_hash:
            raise RuntimeError(f"TRIPO_ARCHIVE_SHA256_RED {name} {observed_hash}")
        category = name.removesuffix(".zip")
        stage_category = assets / "tripo" / "fixtures" / category
        with ZipFile(archive) as zf:
            files = sorted(n for n in zf.namelist()
                           if n.startswith(category + "/") and n.endswith(".glb"))
            if len(files) != expected_count:
                raise RuntimeError(f"TRIPO_SPLIT_COUNT_RED {name} {len(files)}/{expected_count}")
            source_members = set(zf.namelist())
            selected = VISIBLE_IN_MAIN_NAVE.get(category, ())
            for member in files:
                original = zf.read(member)
                dependencies = _gltf_images(original)
                for image in dependencies:
                    if ".." in Path(image).parts or image.startswith("/"):
                        raise RuntimeError("TRIPO_TEXTURE_PATH_TRAVERSAL " + image)
                    resolved = category + "/" + image
                    if resolved not in source_members:
                        raise RuntimeError("TRIPO_TEXTURE_MISSING " + resolved)
                model_id = int(Path(member).stem.removeprefix("Model_"))
                active = model_id in selected
                # Preserve GLB bytes and its EXACT relative texture URIs.
                # The 94 inactive models remain in their intact original ZIPs,
                # catalogued for other rooms without bloating current mobile APK.
                if active:
                    stage_category.mkdir(parents=True, exist_ok=True)
                    (stage_category / Path(member).name).write_bytes(original)
                    for image in dependencies:
                        target = stage_category / image
                        target.parent.mkdir(parents=True, exist_ok=True)
                        payload = zf.read(category + "/" + image)
                        if not target.exists():
                            target.write_bytes(payload)
                        elif target.read_bytes() != payload:
                            raise RuntimeError("TRIPO_TEXTURE_HASH_CONFLICT " + image)
                    kind = CATEGORY_TO_KIND[category]
                    if category == "candleholders" and model_id in WALL_MOUNTED_CANDLEHOLDERS:
                        kind = "wall_sconce"
                    visible.append({
                        "kind": kind,
                        "destination": f"res://assets/tripo/fixtures/{category}/{Path(member).name}",
                        "source": f"{archive.name}!/{member}",
                        "source_archive_sha256": observed_hash,
                        "source_model_index": model_id,
                        "source_geometry_unchanged": True,
                    })
                all_entries.append({
                    "category": category,
                    "model": Path(member).stem,
                    "origin_archive": name,
                    "member": member,
                    "bytes": len(original),
                    "runtime_main_nave": active,
                    "shared_pbr_textures": len(dependencies),
                })
            counts[category] = len(files)
    if len(all_entries) != 104:
        raise RuntimeError("TRIPO_104_COMPLETENESS_RED " + str(len(all_entries)))
    return {"packages_found": len(source), "models_audited": len(all_entries),
            "assets_staged": len(visible),
            "visible_fixtures": visible, "archive_entries": all_entries,
            "category_counts": counts, "source": "owner_library_8_split_zips",
            "no_generated_art": True}
