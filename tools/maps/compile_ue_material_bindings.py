#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


CANONICAL_TEXTURE_KEYS = {
    "diffuse": "PM_Diffuse",
    "normal": "PM_Normals",
    "specular_masks": "PM_SpecularMasks",
    "emissive": "PM_Emissive",
}


def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def override_slot(row):
    if "SlotIndex" in row:
        return int(row["SlotIndex"])
    return int(row["slotIndex"])


def override_path(row):
    if "ObjectPath" in row:
        return row["ObjectPath"]
    return row["objectPath"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--xzms", required=True)
    parser.add_argument("--materials", required=True)
    parser.add_argument("--xztx", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    scene = load(args.scene)
    xzms = load(args.xzms)
    materials = load(args.materials)
    xztx = load(args.xztx)

    mesh_by_path = {
        row["objectPath"]: row
        for row in xzms["meshes"]
    }
    material_by_path = {
        row["objectPath"]: row
        for row in materials["materials"]
    }
    texture_by_path = {
        row["objectPath"]: row
        for row in xztx["textures"]
    }

    unresolved_meshes = []
    invalid_material_slots = []
    unresolved_materials = []
    unresolved_textures = []
    used_material_paths = set()

    scene_mesh_bindings = []
    total_submeshes = 0
    null_base_material_bindings = 0

    for scene_mesh in scene["meshes"]:
        mesh_path = scene_mesh["sourceObjectPath"]
        mesh = mesh_by_path.get(mesh_path)
        if mesh is None:
            unresolved_meshes.append(mesh_path)
            continue

        materials_by_slot = {
            int(row["index"]): row
            for row in mesh.get("sourceMaterials", [])
        }
        section_slots = [
            int(value)
            for value in mesh.get(
                "sourceSectionMaterialIndices",
                [],
            )
        ]

        if len(section_slots) != int(mesh["submeshCount"]):
            invalid_material_slots.append({
                "mesh": mesh_path,
                "error": "section/submesh count mismatch",
                "sections": len(section_slots),
                "submeshes": int(mesh["submeshCount"]),
            })

        section_rows = []
        for submesh_index, slot_index in enumerate(section_slots):
            total_submeshes += 1
            material_slot = materials_by_slot.get(slot_index)

            if slot_index < 0 or material_slot is None:
                invalid_material_slots.append({
                    "mesh": mesh_path,
                    "submeshIndex": submesh_index,
                    "slotIndex": slot_index,
                    "error": "material slot missing",
                })
                material_path = None
            else:
                material_path = material_slot.get("objectPath")

            if material_path:
                used_material_paths.add(material_path)
                if material_path not in material_by_path:
                    unresolved_materials.append({
                        "mesh": mesh_path,
                        "submeshIndex": submesh_index,
                        "slotIndex": slot_index,
                        "materialPath": material_path,
                        "source": "mesh_base",
                    })
            else:
                null_base_material_bindings += 1

            section_rows.append({
                "submeshIndex": submesh_index,
                "slotIndex": slot_index,
                "baseMaterialPath": material_path,
            })

        scene_mesh_bindings.append({
            "sceneMeshIndex": int(scene_mesh["index"]),
            "sourceMeshPath": mesh_path,
            "runtimeFile": scene_mesh["runtimeFile"],
            "submeshCount": len(section_rows),
            "sections": section_rows,
        })

    instance_override_rows = []
    effective_override_slots = 0
    effective_override_submeshes = 0

    scene_mesh_by_index = {
        int(row["sceneMeshIndex"]): row
        for row in scene_mesh_bindings
    }

    for source_instance_index, instance in enumerate(scene["instances"]):
        overrides = instance.get("materialOverrides", [])
        if not overrides:
            continue

        scene_mesh_index = int(instance["meshIndex"])
        mesh_binding = scene_mesh_by_index.get(scene_mesh_index)
        if mesh_binding is None:
            unresolved_meshes.append(
                f"instance:{source_instance_index}:mesh:{scene_mesh_index}"
            )
            continue

        by_slot = {}
        for override in overrides:
            slot_index = override_slot(override)
            material_path = override_path(override)
            by_slot[slot_index] = material_path
            effective_override_slots += 1

            if material_path:
                used_material_paths.add(material_path)
                if material_path not in material_by_path:
                    unresolved_materials.append({
                        "sourceInstanceIndex": source_instance_index,
                        "sceneMeshIndex": scene_mesh_index,
                        "slotIndex": slot_index,
                        "materialPath": material_path,
                        "source": "component_override",
                    })

        affected_submeshes = [
            int(section["submeshIndex"])
            for section in mesh_binding["sections"]
            if int(section["slotIndex"]) in by_slot
        ]
        effective_override_submeshes += len(affected_submeshes)

        instance_override_rows.append({
            "sourceInstanceIndex": source_instance_index,
            "instanceId": instance["instanceId"],
            "sceneMeshIndex": scene_mesh_index,
            "slotOverrides": [
                {
                    "slotIndex": slot,
                    "materialPath": by_slot[slot],
                }
                for slot in sorted(by_slot)
            ],
            "affectedSubmeshes": affected_submeshes,
        })

    material_library = []
    native_texture_references = 0

    for material_path in sorted(used_material_paths):
        material = material_by_path.get(material_path)
        if material is None:
            continue

        texture_rows = []
        textures_by_parameter = {}

        for texture in material.get("textures", []):
            parameter = texture["parameter"]
            object_path = texture.get("objectPath")
            native = (
                texture_by_path.get(object_path)
                if object_path
                else None
            )

            if object_path and native is None:
                unresolved_textures.append({
                    "materialPath": material_path,
                    "parameter": parameter,
                    "texturePath": object_path,
                    "exportType": texture.get("exportType"),
                })
            elif native is not None:
                native_texture_references += 1

            native_row = None
            if native is not None:
                native_row = {
                    "nativeIndex": int(native["index"]),
                    "runtimeFile": native["file"],
                    "format": native["format"],
                    "srgb": bool(native["srgb"]),
                    "width": int(native["width"]),
                    "height": int(native["height"]),
                    "mipCount": int(native["mipCount"]),
                }

            resolved = {
                "parameter": parameter,
                "texturePath": object_path,
                "native": native_row,
            }
            texture_rows.append(resolved)
            textures_by_parameter[parameter] = resolved

        canonical = {}
        for channel, key in CANONICAL_TEXTURE_KEYS.items():
            row = textures_by_parameter.get(key)
            canonical[channel] = (
                row["texturePath"]
                if row is not None
                else None
            )

        material_library.append({
            "materialPath": material_path,
            "exportType": material["exportType"],
            "blendMode": material["blendMode"],
            "shadingModel": material["shadingModel"],
            "canonicalTextures": canonical,
            "textures": texture_rows,
            "scalars": material.get("scalars", []),
            "colors": material.get("colors", []),
            "switches": material.get("switches", []),
            "rawPropertyKeys": material.get(
                "rawPropertyKeys",
                [],
            ),
        })

    # De-duplicate error rows while keeping deterministic JSON.
    def unique_rows(rows):
        seen = set()
        result = []
        for row in rows:
            key = json.dumps(row, sort_keys=True)
            if key not in seen:
                seen.add(key)
                result.append(row)
        return result

    unresolved_meshes = sorted(set(unresolved_meshes))
    invalid_material_slots = unique_rows(invalid_material_slots)
    unresolved_materials = unique_rows(unresolved_materials)
    unresolved_textures = unique_rows(unresolved_textures)

    expected_scene_submeshes = sum(
        int(row["submeshCount"])
        for row in scene_mesh_bindings
    )

    summary = {
        "sceneMeshCount": len(scene_mesh_bindings),
        "sceneInstanceCount": len(scene["instances"]),
        "baseSubmeshBindingCount": total_submeshes,
        "expectedSceneSubmeshes": expected_scene_submeshes,
        "nullBaseMaterialBindingCount":
            null_base_material_bindings,
        "instanceOverrideRecordCount":
            len(instance_override_rows),
        "effectiveOverrideSlotCount":
            effective_override_slots,
        "effectiveOverrideSubmeshCount":
            effective_override_submeshes,
        "usedMaterialCount": len(material_library),
        "nativeTextureReferenceCount":
            native_texture_references,
        "unresolvedMeshCount": len(unresolved_meshes),
        "invalidMaterialSlotCount":
            len(invalid_material_slots),
        "unresolvedMaterialCount":
            len(unresolved_materials),
        "unresolvedTextureCount":
            len(unresolved_textures),
    }

    summary["ready"] = (
        summary["sceneMeshCount"] == len(scene["meshes"])
        and summary["baseSubmeshBindingCount"]
            == summary["expectedSceneSubmeshes"]
        and summary["unresolvedMeshCount"] == 0
        and summary["invalidMaterialSlotCount"] == 0
        and summary["unresolvedMaterialCount"] == 0
        and summary["unresolvedTextureCount"] == 0
    )

    output = {
        "schemaVersion": 1,
        "format": "xziel_ue_material_binding_manifest_v1",
        "canonicalTextureKeys": CANONICAL_TEXTURE_KEYS,
        "summary": summary,
        "meshes": scene_mesh_bindings,
        "instanceOverrides": instance_override_rows,
        "materials": material_library,
        "unresolvedMeshes": unresolved_meshes,
        "invalidMaterialSlots": invalid_material_slots,
        "unresolvedMaterials": unresolved_materials,
        "unresolvedTextures": unresolved_textures,
    }

    Path(args.output).write_text(
        json.dumps(output, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("XZIEL_UE_MATERIAL_BINDING_MANIFEST", summary)

    for row in invalid_material_slots[:40]:
        print("XZIEL_UE_MATERIAL_BINDING_SLOT_FAILURE", row)
    for row in unresolved_materials[:40]:
        print("XZIEL_UE_MATERIAL_BINDING_MATERIAL_FAILURE", row)
    for row in unresolved_textures[:40]:
        print("XZIEL_UE_MATERIAL_BINDING_TEXTURE_FAILURE", row)

    if not summary["ready"]:
        print("XZIEL_UE_MATERIAL_BINDING_MANIFEST_FAILURE")
        return 5

    print("XZIEL_UE_MATERIAL_BINDING_MANIFEST_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
