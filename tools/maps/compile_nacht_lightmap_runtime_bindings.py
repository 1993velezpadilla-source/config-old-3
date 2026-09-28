#!/usr/bin/env python3
"""Compile exact Nacht per-instance baked-lighting metadata into XZLB v1."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from collections import Counter
from pathlib import Path

MAGIC = b"XZLB"
VERSION = 1
HEADER = struct.Struct("<4s7I")
HEADER_BYTES = HEADER.size
RECORD_BYTES = 256
EXPECTED_INSTANCES = 10791
EXPECTED_MAPPED = 10786
EXPECTED_MISSING = 5
NO_TEXTURE = 0xFFFFFFFF

FLAG_MAPPED = 1 << 0
FLAG_RUNTIME_READY = 1 << 1
FLAG_SHADOW_TEXTURE = 1 << 2
FLAG_SKY_OCCLUSION = 1 << 3
FLAG_AO_MASK = 1 << 4
FLAG_SHADOW_PARAMS = 1 << 5
FLAG_MESH_CONSENSUS = 1 << 6

RESOLUTION_NONE = 0
RESOLUTION_AUTHORED = 1
RESOLUTION_MESH_CONSENSUS = 2


def finite_vector(value: object, count: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != count:
        raise SystemExit(f"{label}: expected {count} floats")
    out = [float(x) for x in value]
    if not all(math.isfinite(x) for x in out):
        raise SystemExit(f"{label}: non-finite value")
    return out


def optional_vector(value: object, count: int, label: str) -> list[float]:
    if value is None:
        return [0.0] * count
    return finite_vector(value, count, label)


def vector_matrix(value: object, rows: int, cols: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != rows:
        raise SystemExit(f"{label}: expected {rows} rows")
    flat: list[float] = []
    for row_index, row in enumerate(value):
        flat.extend(
            finite_vector(row, cols, f"{label}[{row_index}]")
        )
    return flat


def bool_mask(value: object, label: str) -> int:
    if value is None:
        return 0
    if not isinstance(value, list) or len(value) != 4:
        raise SystemExit(f"{label}: expected 4 bools")
    mask = 0
    for index, item in enumerate(value):
        if not isinstance(item, bool):
            raise SystemExit(f"{label}[{index}]: expected bool")
        if item:
            mask |= 1 << index
    return mask


def guid_bytes(value: object) -> bytes:
    if not isinstance(value, str):
        return bytes(16)
    hex_text = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(hex_text) != 32:
        raise SystemExit(f"invalid MapBuildDataId {value!r}")
    return bytes.fromhex(hex_text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    bindings_doc = json.loads(
        args.bindings.read_text(encoding="utf-8")
    )
    texture_doc = json.loads(
        args.textures.read_text(encoding="utf-8")
    )

    if bindings_doc.get("schemaVersion") != 2:
        raise SystemExit("bindings schemaVersion != 2")
    if (
        bindings_doc.get("format")
        != "xziel_nacht_lightmap_instance_payload_v2"
    ):
        raise SystemExit("unexpected bindings format")
    if texture_doc.get("format") != "XZLT":
        raise SystemExit("unexpected texture pack report format")

    records = bindings_doc.get("instanceBindings")
    if not isinstance(records, list) or len(records) != EXPECTED_INSTANCES:
        raise SystemExit(
            f"expected {EXPECTED_INSTANCES} instance bindings"
        )

    texture_rows = texture_doc.get("textures")
    if not isinstance(texture_rows, list):
        raise SystemExit("texture report has no texture rows")

    texture_index_by_path: dict[str, int] = {}
    for row in texture_rows:
        if not isinstance(row, dict):
            raise SystemExit("invalid texture row")
        path = row.get("sourcePath")
        index = row.get("textureIndex")
        if not isinstance(path, str) or not isinstance(index, int):
            raise SystemExit("texture row missing sourcePath/index")
        if path in texture_index_by_path:
            raise SystemExit(f"duplicate texture path {path}")
        texture_index_by_path[path] = index

    texture_count = len(texture_index_by_path)
    if texture_count != 188:
        raise SystemExit(f"expected 188 XZLT textures, got {texture_count}")

    output = bytearray(
        HEADER_BYTES + EXPECTED_INSTANCES * RECORD_BYTES
    )

    mapped_count = 0
    missing_count = 0
    ready_count = 0
    consensus_count = 0
    lightmap_texture_indices: set[int] = set()
    shadow_texture_indices: set[int] = set()
    sky_texture_indices: set[int] = set()
    ao_texture_indices: set[int] = set()
    uv_counts: Counter[int] = Counter()
    shadow_path_count = 0
    shadow_params_count = 0
    shadow_texture_mapped_count = 0
    sky_path_count = 0
    sky_texture_mapped_count = 0
    ao_path_count = 0
    ao_texture_mapped_count = 0

    for expected_index, row in enumerate(records):
        if not isinstance(row, dict):
            raise SystemExit(f"record {expected_index}: not an object")
        if row.get("instanceIndex") != expected_index:
            raise SystemExit(
                f"record ordering drift at {expected_index}"
            )

        base = HEADER_BYTES + expected_index * RECORD_BYTES
        status = row.get("status")
        component_index = row.get("componentExportIndex")
        if not isinstance(component_index, int) or component_index < 0:
            raise SystemExit(
                f"record {expected_index}: bad componentExportIndex"
            )

        flags = 0
        uv_channel = NO_TEXTURE
        light0 = NO_TEXTURE
        light1 = NO_TEXTURE
        shadow_index = NO_TEXTURE
        sky_index = NO_TEXTURE
        ao_index = NO_TEXTURE
        resolution_code = RESOLUTION_NONE
        coord_scale = [0.0, 0.0]
        coord_bias = [0.0, 0.0]
        scale_vectors = [0.0] * 16
        add_vectors = [0.0] * 16
        light_shadow_mask = 0
        light_inv_penumbra = [0.0] * 4
        shadow_coord_scale = [0.0, 0.0]
        shadow_coord_bias = [0.0, 0.0]
        shadow_channel_mask = 0
        shadow_inv_penumbra = [0.0] * 4
        build_guid = bytes(16)

        if status == "missing":
            missing_count += 1
            if row.get("binding") is not None:
                raise SystemExit(
                    f"record {expected_index}: missing row has binding"
                )
        elif status == "mapped":
            binding = row.get("binding")
            if not isinstance(binding, dict):
                raise SystemExit(
                    f"record {expected_index}: mapped row lacks binding"
                )

            mapped_count += 1
            flags |= FLAG_MAPPED

            if binding.get("runtimePayloadReady") is not True:
                raise SystemExit(
                    f"record {expected_index}: runtime payload not ready"
                )
            flags |= FLAG_RUNTIME_READY
            ready_count += 1

            uv_channel_value = binding.get(
                "effectiveLightMapCoordinateIndex"
            )
            if (
                not isinstance(uv_channel_value, int)
                or uv_channel_value < 0
                or uv_channel_value > 3
            ):
                raise SystemExit(
                    f"record {expected_index}: invalid UV channel"
                )
            uv_channel = uv_channel_value
            uv_counts[uv_channel] += 1

            resolution = binding.get("coordinateIndexResolution")
            if resolution == "authored":
                resolution_code = RESOLUTION_AUTHORED
            elif resolution == "meshConsensus":
                resolution_code = RESOLUTION_MESH_CONSENSUS
                flags |= FLAG_MESH_CONSENSUS
                consensus_count += 1
            else:
                raise SystemExit(
                    f"record {expected_index}: bad UV resolution {resolution}"
                )

            light_textures = binding.get("lightTextures")
            if (
                not isinstance(light_textures, list)
                or len(light_textures) != 2
            ):
                raise SystemExit(
                    f"record {expected_index}: expected 2 lightmaps"
                )

            resolved_light_indices: list[int] = []
            for texture_path in light_textures:
                if not isinstance(texture_path, str):
                    raise SystemExit(
                        f"record {expected_index}: bad lightmap path"
                    )
                if texture_path not in texture_index_by_path:
                    raise SystemExit(
                        f"record {expected_index}: lightmap not in XZLT: "
                        f"{texture_path}"
                    )
                texture_index = texture_index_by_path[texture_path]
                resolved_light_indices.append(texture_index)
                lightmap_texture_indices.add(texture_index)

            light0, light1 = resolved_light_indices

            coord_scale = finite_vector(
                binding.get("lightMapCoordinateScale"),
                2,
                f"record {expected_index} lightMapCoordinateScale",
            )
            coord_bias = finite_vector(
                binding.get("lightMapCoordinateBias"),
                2,
                f"record {expected_index} lightMapCoordinateBias",
            )
            scale_vectors = vector_matrix(
                binding.get("lightMapScaleVectors"),
                4,
                4,
                f"record {expected_index} lightMapScaleVectors",
            )
            add_vectors = vector_matrix(
                binding.get("lightMapAddVectors"),
                4,
                4,
                f"record {expected_index} lightMapAddVectors",
            )
            light_shadow_mask = bool_mask(
                binding.get("lightMapShadowChannelValid"),
                f"record {expected_index} lightMapShadowChannelValid",
            )
            light_inv_penumbra = optional_vector(
                binding.get("lightMapInvUniformPenumbraSize"),
                4,
                f"record {expected_index} lightMapInvUniformPenumbraSize",
            )

            shadow_path = binding.get("shadowTexture")
            if isinstance(shadow_path, str) and shadow_path:
                flags |= FLAG_SHADOW_TEXTURE
                shadow_path_count += 1
                mapped_shadow = texture_index_by_path.get(shadow_path)
                if mapped_shadow is not None:
                    shadow_index = mapped_shadow
                    shadow_texture_indices.add(mapped_shadow)
                    shadow_texture_mapped_count += 1

            sky_path = binding.get("skyOcclusionTexture")
            if isinstance(sky_path, str) and sky_path:
                flags |= FLAG_SKY_OCCLUSION
                sky_path_count += 1
                mapped_sky = texture_index_by_path.get(sky_path)
                if mapped_sky is not None:
                    sky_index = mapped_sky
                    sky_texture_indices.add(mapped_sky)
                    sky_texture_mapped_count += 1

            ao_path = binding.get("aoMaskTexture")
            if isinstance(ao_path, str) and ao_path:
                flags |= FLAG_AO_MASK
                ao_path_count += 1
                mapped_ao = texture_index_by_path.get(ao_path)
                if mapped_ao is not None:
                    ao_index = mapped_ao
                    ao_texture_indices.add(mapped_ao)
                    ao_texture_mapped_count += 1

            shadow_scale_value = binding.get(
                "shadowMapCoordinateScale"
            )
            shadow_bias_value = binding.get(
                "shadowMapCoordinateBias"
            )
            if shadow_scale_value is not None or shadow_bias_value is not None:
                flags |= FLAG_SHADOW_PARAMS
                shadow_params_count += 1
                shadow_coord_scale = finite_vector(
                    shadow_scale_value,
                    2,
                    f"record {expected_index} shadowMapCoordinateScale",
                )
                shadow_coord_bias = finite_vector(
                    shadow_bias_value,
                    2,
                    f"record {expected_index} shadowMapCoordinateBias",
                )
                shadow_channel_mask = bool_mask(
                    binding.get("shadowMapChannelValid"),
                    f"record {expected_index} shadowMapChannelValid",
                )
                shadow_inv_penumbra = optional_vector(
                    binding.get("shadowMapInvUniformPenumbraSize"),
                    4,
                    f"record {expected_index} shadowMapInvUniformPenumbraSize",
                )

            build_guid = guid_bytes(
                binding.get("mapBuildDataId")
            )
            if build_guid == bytes(16):
                raise SystemExit(
                    f"record {expected_index}: zero MapBuildDataId"
                )
        else:
            raise SystemExit(
                f"record {expected_index}: unsupported status {status!r}"
            )

        struct.pack_into(
            "<8I",
            output,
            base,
            flags,
            uv_channel,
            light0,
            light1,
            shadow_index,
            sky_index,
            ao_index,
            component_index,
        )
        struct.pack_into("<2f", output, base + 32, *coord_scale)
        struct.pack_into("<2f", output, base + 40, *coord_bias)
        struct.pack_into("<16f", output, base + 48, *scale_vectors)
        struct.pack_into("<16f", output, base + 112, *add_vectors)
        struct.pack_into(
            "<2I",
            output,
            base + 176,
            light_shadow_mask,
            resolution_code,
        )
        struct.pack_into(
            "<4f",
            output,
            base + 184,
            *light_inv_penumbra,
        )
        struct.pack_into(
            "<2f",
            output,
            base + 200,
            *shadow_coord_scale,
        )
        struct.pack_into(
            "<2f",
            output,
            base + 208,
            *shadow_coord_bias,
        )
        struct.pack_into(
            "<2I",
            output,
            base + 216,
            shadow_channel_mask,
            0,
        )
        struct.pack_into(
            "<4f",
            output,
            base + 224,
            *shadow_inv_penumbra,
        )
        output[base + 240 : base + 256] = build_guid

    if mapped_count != EXPECTED_MAPPED:
        raise SystemExit(
            f"mapped count drift {mapped_count} != {EXPECTED_MAPPED}"
        )
    if missing_count != EXPECTED_MISSING:
        raise SystemExit(
            f"missing count drift {missing_count} != {EXPECTED_MISSING}"
        )
    if ready_count != EXPECTED_MAPPED:
        raise SystemExit(
            f"ready count drift {ready_count} != {EXPECTED_MAPPED}"
        )

    header_flags = 1  # records are instance-index aligned
    HEADER.pack_into(
        output,
        0,
        MAGIC,
        VERSION,
        EXPECTED_INSTANCES,
        RECORD_BYTES,
        mapped_count,
        texture_count,
        header_flags,
        0,
    )

    expected_bytes = HEADER_BYTES + EXPECTED_INSTANCES * RECORD_BYTES
    if len(output) != expected_bytes:
        raise SystemExit("XZLB size drift")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)

    report = {
        "schemaVersion": 1,
        "format": "XZLB",
        "version": VERSION,
        "instanceCount": EXPECTED_INSTANCES,
        "recordBytes": RECORD_BYTES,
        "fileBytes": len(output),
        "mappedCount": mapped_count,
        "missingCount": missing_count,
        "runtimeReadyCount": ready_count,
        "textureCount": texture_count,
        "uniqueLightmapTextureIndices": len(lightmap_texture_indices),
        "uvChannelCounts": {
            str(key): value
            for key, value in sorted(uv_counts.items())
        },
        "meshConsensusCount": consensus_count,
        "shadowTexturePathCount": shadow_path_count,
        "shadowTextureMappedCount": shadow_texture_mapped_count,
        "uniqueMappedShadowTextureIndices": len(shadow_texture_indices),
        "shadowParamsCount": shadow_params_count,
        "skyOcclusionPathCount": sky_path_count,
        "skyOcclusionMappedCount": sky_texture_mapped_count,
        "uniqueMappedSkyOcclusionIndices": len(sky_texture_indices),
        "aoMaskPathCount": ao_path_count,
        "aoMaskMappedCount": ao_texture_mapped_count,
        "uniqueMappedAoMaskIndices": len(ao_texture_indices),
        "instanceAligned": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_XZLB_OK",
        json.dumps(report, sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
