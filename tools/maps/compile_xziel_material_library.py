#!/usr/bin/env python3
import argparse
import json
import struct
from pathlib import Path

MAGIC = b"XZML"
VERSION = 1
HEADER_BYTES = 96
MATERIAL_RECORD_BYTES = 80
TEXTURE_ASSET_RECORD_BYTES = 16
TEXTURE_BINDING_RECORD_BYTES = 12
SCALAR_RECORD_BYTES = 12
COLOR_RECORD_BYTES = 24
SWITCH_RECORD_BYTES = 12
NO_TEXTURE = 0xFFFFFFFF

CANONICAL_ORDER = (
    "diffuse",
    "normal",
    "specular_masks",
    "emissive",
)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Strings:
    def __init__(self):
        self.data = bytearray()
        self.entries = {}

    def add(self, value):
        if not isinstance(value, str) or not value:
            raise ValueError(f"invalid XZML string: {value!r}")

        cached = self.entries.get(value)
        if cached is not None:
            return cached

        encoded = value.encode("utf-8")
        if not encoded:
            raise ValueError("empty XZML string")

        offset = len(self.data)
        self.data.extend(encoded)
        result = (offset, len(encoded))
        self.entries[value] = result
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--xzmi-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    manifest = load(args.manifest)
    xzmi = load(args.xzmi_report)

    if manifest.get("format") != "xziel_ue_material_binding_manifest_v1":
        raise SystemExit("unsupported material binding manifest")
    if xzmi.get("format") != "XZMI" or not xzmi.get("ready"):
        raise SystemExit("XZMI report not ready")

    material_by_path = {
        row["materialPath"]: row
        for row in manifest["materials"]
    }

    material_paths = list(xzmi["materialPaths"])
    if len(material_paths) != int(xzmi["materialCount"]):
        raise SystemExit("XZMI material path/count mismatch")
    if len(material_paths) != len(set(material_paths)):
        raise SystemExit("XZMI material paths are not unique")

    missing_materials = [
        path for path in material_paths
        if path not in material_by_path
    ]
    if missing_materials:
        raise SystemExit(
            "XZMI materials missing from manifest: "
            + repr(missing_materials[:20])
        )

    # Collect only texture assets reachable from the final visible XZMI
    # material set. This keeps runtime payload minimal without altering
    # source resolution, mip chains, pixel formats, or sRGB metadata.
    texture_rows_by_path = {}
    for material_path in material_paths:
        material = material_by_path[material_path]
        for texture in material.get("textures", []):
            source_path = texture.get("texturePath")
            native = texture.get("native")
            if source_path is None:
                continue
            if native is None:
                raise SystemExit(
                    f"material {material_path} texture {source_path} "
                    "has no native XZTX mapping"
                )

            row = {
                "sourcePath": source_path,
                "runtimeFile": native["runtimeFile"],
                "nativeIndex": int(native["nativeIndex"]),
                "format": native["format"],
                "srgb": bool(native["srgb"]),
                "width": int(native["width"]),
                "height": int(native["height"]),
                "mipCount": int(native["mipCount"]),
            }

            previous = texture_rows_by_path.get(source_path)
            if previous is not None and previous != row:
                raise SystemExit(
                    f"texture mapping conflict for {source_path}"
                )
            texture_rows_by_path[source_path] = row

    texture_assets = sorted(
        texture_rows_by_path.values(),
        key=lambda row: (
            row["runtimeFile"],
            row["sourcePath"],
        ),
    )
    texture_index_by_path = {
        row["sourcePath"]: index
        for index, row in enumerate(texture_assets)
    }

    strings = Strings()
    texture_asset_records = []
    for row in texture_assets:
        source_off, source_len = strings.add(row["sourcePath"])
        file_off, file_len = strings.add(row["runtimeFile"])
        texture_asset_records.append(
            (source_off, source_len, file_off, file_len)
        )

    material_records = []
    texture_binding_records = []
    scalar_records = []
    color_records = []
    switch_records = []

    native_texture_bindings = 0
    default_surface_materials = 0

    for material_path in material_paths:
        material = material_by_path[material_path]

        path_ref = strings.add(material_path)
        export_type_ref = strings.add(material["exportType"])
        blend_mode_ref = strings.add(material["blendMode"])
        shading_model_ref = strings.add(material["shadingModel"])

        if material["exportType"] == "SyntheticDefaultSurface":
            default_surface_materials += 1

        first_texture = len(texture_binding_records)
        for texture in sorted(
            material.get("textures", []),
            key=lambda row: row["parameter"],
        ):
            source_path = texture.get("texturePath")
            if source_path is None:
                continue

            native = texture.get("native")
            if native is None:
                raise SystemExit(
                    f"material {material_path} parameter "
                    f"{texture['parameter']} has no XZTX"
                )

            texture_index = texture_index_by_path.get(source_path)
            if texture_index is None:
                raise SystemExit(
                    f"texture asset not indexed: {source_path}"
                )

            name_ref = strings.add(texture["parameter"])
            texture_binding_records.append(
                (name_ref[0], name_ref[1], texture_index)
            )
            native_texture_bindings += 1

        first_scalar = len(scalar_records)

        opacity_mask_clip = material.get(
            "opacityMaskClipValue"
        )
        if opacity_mask_clip is not None:
            name_ref = strings.add(
                "__XZ_OpacityMaskClipValue"
            )
            scalar_records.append(
                (
                    name_ref[0],
                    name_ref[1],
                    float(opacity_mask_clip),
                )
            )

        for scalar in material.get("scalars", []):
            name_ref = strings.add(scalar["name"])
            scalar_records.append(
                (name_ref[0], name_ref[1], float(scalar["value"]))
            )

        first_color = len(color_records)
        for color in material.get("colors", []):
            name_ref = strings.add(color["name"])
            color_records.append(
                (
                    name_ref[0],
                    name_ref[1],
                    float(color["r"]),
                    float(color["g"]),
                    float(color["b"]),
                    float(color["a"]),
                )
            )

        first_switch = len(switch_records)

        for synthetic_name, source_key in (
            ("__XZ_TwoSided", "twoSided"),
            ("__XZ_DisableDepthTest", "disableDepthTest"),
            ("__XZ_IsMasked", "isMasked"),
        ):
            synthetic_value = material.get(source_key)
            if synthetic_value is not None:
                name_ref = strings.add(synthetic_name)
                switch_records.append(
                    (
                        name_ref[0],
                        name_ref[1],
                        1 if bool(synthetic_value) else 0,
                    )
                )

        for switch in material.get("switches", []):
            name_ref = strings.add(switch["name"])
            value = switch["value"]
            if isinstance(value, bool):
                value = 1 if value else 0
            value = int(value)
            if value not in (0, 1):
                raise SystemExit(
                    f"invalid material switch {switch['name']}: {value}"
                )
            switch_records.append(
                (name_ref[0], name_ref[1], value)
            )

        canonical = []
        canonical_map = material.get("canonicalTextures", {})
        for channel in CANONICAL_ORDER:
            source_path = canonical_map.get(channel)
            if source_path is None:
                canonical.append(NO_TEXTURE)
                continue

            texture_index = texture_index_by_path.get(source_path)
            if texture_index is None:
                raise SystemExit(
                    f"canonical {channel} texture not native: "
                    f"{material_path} -> {source_path}"
                )
            canonical.append(texture_index)

        material_records.append(
            (
                *path_ref,
                *export_type_ref,
                *blend_mode_ref,
                *shading_model_ref,
                first_texture,
                len(texture_binding_records) - first_texture,
                first_scalar,
                len(scalar_records) - first_scalar,
                first_color,
                len(color_records) - first_color,
                first_switch,
                len(switch_records) - first_switch,
                *canonical,
            )
        )

    if len(material_records) != int(xzmi["materialCount"]):
        raise SystemExit("final material count mismatch")

    material_table_offset = HEADER_BYTES
    texture_asset_table_offset = (
        material_table_offset
        + len(material_records) * MATERIAL_RECORD_BYTES
    )
    texture_binding_table_offset = (
        texture_asset_table_offset
        + len(texture_asset_records) * TEXTURE_ASSET_RECORD_BYTES
    )
    scalar_table_offset = (
        texture_binding_table_offset
        + len(texture_binding_records) * TEXTURE_BINDING_RECORD_BYTES
    )
    color_table_offset = (
        scalar_table_offset
        + len(scalar_records) * SCALAR_RECORD_BYTES
    )
    switch_table_offset = (
        color_table_offset
        + len(color_records) * COLOR_RECORD_BYTES
    )
    string_table_offset = (
        switch_table_offset
        + len(switch_records) * SWITCH_RECORD_BYTES
    )
    file_bytes = string_table_offset + len(strings.data)

    if file_bytes > 0xFFFFFFFF:
        raise SystemExit("XZML exceeds 32-bit offsets")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("wb") as stream:
        stream.write(MAGIC)
        stream.write(struct.pack(
            "<23I",
            VERSION,
            len(material_records),
            len(texture_asset_records),
            len(texture_binding_records),
            len(scalar_records),
            len(color_records),
            len(switch_records),
            MATERIAL_RECORD_BYTES,
            TEXTURE_ASSET_RECORD_BYTES,
            TEXTURE_BINDING_RECORD_BYTES,
            SCALAR_RECORD_BYTES,
            COLOR_RECORD_BYTES,
            SWITCH_RECORD_BYTES,
            material_table_offset,
            texture_asset_table_offset,
            texture_binding_table_offset,
            scalar_table_offset,
            color_table_offset,
            switch_table_offset,
            string_table_offset,
            len(strings.data),
            0,
            0,
        ))

        for record in material_records:
            stream.write(struct.pack("<20I", *record))

        for record in texture_asset_records:
            stream.write(struct.pack("<4I", *record))

        for name_offset, name_bytes, texture_index in texture_binding_records:
            stream.write(struct.pack(
                "<3I",
                name_offset,
                name_bytes,
                texture_index,
            ))

        for name_offset, name_bytes, value in scalar_records:
            stream.write(struct.pack(
                "<2If",
                name_offset,
                name_bytes,
                value,
            ))

        for record in color_records:
            stream.write(struct.pack(
                "<2I4f",
                record[0],
                record[1],
                record[2],
                record[3],
                record[4],
                record[5],
            ))

        for name_offset, name_bytes, value in switch_records:
            stream.write(struct.pack(
                "<3I",
                name_offset,
                name_bytes,
                value,
            ))

        stream.write(strings.data)

    if out.stat().st_size != file_bytes:
        raise SystemExit(
            f"XZML size mismatch "
            f"{out.stat().st_size} != {file_bytes}"
        )

    formats = {}
    srgb_textures = 0
    total_mips = 0
    for row in texture_assets:
        formats[row["format"]] = formats.get(row["format"], 0) + 1
        srgb_textures += 1 if row["srgb"] else 0
        total_mips += row["mipCount"]

    report = {
        "schemaVersion": 1,
        "format": "XZML",
        "version": VERSION,
        "fileBytes": file_bytes,
        "materialCount": len(material_records),
        "textureAssetCount": len(texture_asset_records),
        "textureBindingCount": len(texture_binding_records),
        "scalarCount": len(scalar_records),
        "colorCount": len(color_records),
        "switchCount": len(switch_records),
        "stringBytes": len(strings.data),
        "defaultSurfaceMaterialCount": default_surface_materials,
        "nativeTextureBindingCount": native_texture_bindings,
        "srgbTextureAssetCount": srgb_textures,
        "linearTextureAssetCount":
            len(texture_assets) - srgb_textures,
        "totalTextureMips": total_mips,
        "formatCounts": dict(sorted(formats.items())),
        "materialPaths": material_paths,
        "textureAssets": texture_assets,
        "ready": (
            len(material_records) == int(xzmi["materialCount"])
            and len(material_records) > 0
        ),
    }

    Path(args.report).write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("XZIEL_XZML_BUILD", {
        key: report[key]
        for key in (
            "materialCount",
            "textureAssetCount",
            "textureBindingCount",
            "scalarCount",
            "colorCount",
            "switchCount",
            "defaultSurfaceMaterialCount",
            "totalTextureMips",
            "formatCounts",
            "fileBytes",
            "ready",
        )
    })

    if not report["ready"]:
        print("XZIEL_XZML_BUILD_FAILURE")
        return 5

    print("XZIEL_XZML_BUILD_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
