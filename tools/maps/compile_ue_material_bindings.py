#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


CANONICAL_TEXTURE_KEYS = {
    "diffuse": "PM_Diffuse",
    "normal": "PM_Normals",
    "specular_masks": "PM_SpecularMasks",
    "emissive": "PM_Emissive",
}

UE_DEFAULT_SURFACE_MATERIAL = "xziel://ue/default-surface"
UE_ENGINE_DEFAULT_SURFACE_PATHS = (
    "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial",
    "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial",
)


def canonical_ue_path(value):
    if value is None:
        return None
    text = str(value).strip().replace("\\", "/")
    if "'" in text and text.endswith("'"):
        first = text.find("'")
        if first >= 0:
            text = text[first + 1:-1]
    lower = text.lower()
    content_at = lower.find("/content/")
    if content_at >= 0 and not lower.startswith("/game/"):
        text = "/Game/" + text[content_at + len("/content/"):]
    elif lower.startswith("content/"):
        text = "/Game/" + text[len("Content/"):]
    elif lower.startswith("game/"):
        text = "/" + text
    elif not text.startswith("/") and "/" in text:
        # CUE4Parse source package/object paths are game-content relative.
        text = "/Game/" + text
    return text.lower()


def iter_package_index_paths(value):
    if isinstance(value, dict):
        if value.get("kind") == "FPackageIndex":
            path = value.get("path")
            if path:
                yield path
        for child in value.values():
            yield from iter_package_index_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_package_index_paths(child)


def build_canonical_lookup(rows, field):
    lookup = {}
    for row in rows:
        raw = row.get(field)
        key = canonical_ue_path(raw)
        if not key:
            continue
        previous = lookup.get(key)
        if previous is not None and previous != row:
            raise SystemExit(
                f"canonical path collision for {raw!r}: "
                f"{previous.get(field)!r}"
            )
        lookup[key] = row
    return lookup



def material_family_key(value):
    text = str(value or "").replace("\\", "/")
    name = text.rsplit("/", 1)[-1].split(".", 1)[0].lower()
    # Numbered authored siblings such as foo_01/foo_02/foo_03 share a family.
    # This does not assign semantics by filename alone; it is only a grouping
    # key for explicit semantic parameters recovered from sibling materials.
    return re.sub(r"(?<=_)\d+$", "#", name)


def exact_texture_parameter(material, parameter_name):
    matches = []
    for row in material.get("textures", []):
        if str(row.get("parameter", "")).lower() != parameter_name.lower():
            continue
        object_path = row.get("objectPath")
        if object_path:
            matches.append(object_path)
    normalized = {}
    for value in matches:
        normalized[canonical_ue_path(value)] = value
    if len(normalized) != 1:
        return None
    return next(iter(normalized.values()))


def sibling_parameter_consensus(materials, target_path, target_textures, parameter_name):
    family = material_family_key(target_path)
    if not family or "#" not in family:
        return None

    sibling_values = []
    sibling_count = 0
    for candidate in materials:
        candidate_path = candidate.get("objectPath")
        if not candidate_path or canonical_ue_path(candidate_path) == canonical_ue_path(target_path):
            continue
        if material_family_key(candidate_path) != family:
            continue
        value = exact_texture_parameter(candidate, parameter_name)
        if not value:
            continue
        sibling_count += 1
        sibling_values.append(value)

    # Require multiple source-authored siblings before using family consensus.
    if sibling_count < 2:
        return None

    target_by_canonical = {
        canonical_ue_path(value): value
        for value in target_textures
        if value
    }
    intersections = {
        canonical_ue_path(value)
        for value in sibling_values
        if canonical_ue_path(value) in target_by_canonical
    }
    if len(intersections) != 1:
        return None
    key = next(iter(intersections))
    return target_by_canonical[key]


def source_raw_property_names(material):
    """Return property names proven present in the cooked UObject.

    CMaterialParams2.Properties is useful semantic authority but it is not a
    complete reflection of UMaterial's serialized property holder. In
    particular, UE4.21 particle masters can expose BlendMode in
    rawMaterialProperties while omitting it from rawPropertyKeys. Constructor
    defaults must only be synthesized when neither source view contains the
    property.
    """
    names = {
        str(name)
        for name in material.get("rawPropertyKeys", [])
        if name
    }
    for row in material.get("rawMaterialProperties", []):
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if name:
            names.add(str(name))
    return names


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
    parser.add_argument("--particle-graphs")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    scene = load(args.scene)
    xzms = load(args.xzms)
    materials = load(args.materials)
    xztx = load(args.xztx)
    particle_graphs = load(args.particle_graphs) if args.particle_graphs else {}

    mesh_by_path = {
        row["objectPath"]: row
        for row in xzms["meshes"]
    }
    material_by_path = build_canonical_lookup(
        materials["materials"],
        "objectPath",
    )
    texture_by_path = build_canonical_lookup(
        xztx["textures"],
        "objectPath",
    )

    unresolved_meshes = []
    invalid_material_slots = []
    unresolved_materials = []
    unresolved_textures = []
    used_material_paths = set()

    scene_mesh_bindings = []
    total_submeshes = 0
    null_base_material_bindings = 0
    null_base_material_binding_rows = []
    resolved_engine_default_surface_path = None
    for candidate in UE_ENGINE_DEFAULT_SURFACE_PATHS:
        resolved = material_by_path.get(canonical_ue_path(candidate))
        if resolved is not None:
            resolved_engine_default_surface_path = resolved["objectPath"]
            break

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
                material_key = canonical_ue_path(material_path)
                resolved_material = material_by_path.get(material_key)
                if resolved_material is None:
                    unresolved_materials.append({
                        "mesh": mesh_path,
                        "submeshIndex": submesh_index,
                        "slotIndex": slot_index,
                        "materialPath": material_path,
                        "canonicalMaterialPath": material_key,
                        "source": "mesh_base",
                    })
                else:
                    material_path = resolved_material["objectPath"]
                    used_material_paths.add(material_path)
            else:
                null_base_material_bindings += 1
                null_base_material_binding_rows.append({
                    "sceneMeshIndex": int(scene_mesh["index"]),
                    "sourceMeshPath": mesh_path,
                    "runtimeFile": scene_mesh["runtimeFile"],
                    "submeshIndex": submesh_index,
                    "slotIndex": slot_index,
                })
                material_path = (
                    resolved_engine_default_surface_path
                    or UE_DEFAULT_SURFACE_MATERIAL
                )
                used_material_paths.add(material_path)

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
                material_key = canonical_ue_path(material_path)
                resolved_material = material_by_path.get(material_key)
                if resolved_material is None:
                    unresolved_materials.append({
                        "sourceInstanceIndex": source_instance_index,
                        "sceneMeshIndex": scene_mesh_index,
                        "slotIndex": slot_index,
                        "materialPath": material_path,
                        "canonicalMaterialPath": material_key,
                        "source": "component_override",
                    })
                else:
                    material_path = resolved_material["objectPath"]
                    by_slot[slot_index] = material_path
                    used_material_paths.add(material_path)

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

    # Particle render materials are source-visible dependencies too. The
    # Cascade extractor already records every FPackageIndex reference, so use
    # exact graph references and intersect them with the material authority.
    # This adds no filename/name guessing and keeps static-mesh binding logic
    # unchanged.
    particle_emitter_material_references = set()
    for system in particle_graphs.get("systems", []):
        for node in system.get("nodes", []):
            export_type = node.get("exportType")
            wanted = (
                {"Material"}
                if export_type == "ParticleModuleRequired"
                else {"MeshMaterials"}
                if export_type == "ParticleModuleMeshMaterial"
                else set()
            )
            if not wanted:
                continue
            for prop in node.get("properties", []):
                if prop.get("name") in wanted:
                    particle_emitter_material_references.update(
                        iter_package_index_paths(prop.get("value"))
                    )

    particle_emitter_unresolved_material_references = sorted(
        ref
        for ref in particle_emitter_material_references
        if canonical_ue_path(ref) not in material_by_path
    )

    particle_material_paths = set()
    for system in particle_graphs.get("systems", []):
        refs = list(system.get("references", []))
        for node in system.get("nodes", []):
            refs.extend(node.get("references", []))
            # Some Cascade material dependencies, notably
            # ParticleModuleMeshMaterial.MeshMaterials, are encoded only as
            # nested FPackageIndex values inside decoded properties and are
            # absent from the node's top-level references list. Walk those
            # decoded source properties too, then still require a match in the
            # extracted material authority before accepting the dependency.
            refs.extend(iter_package_index_paths(node.get("properties", [])))
        for ref in refs:
            resolved = material_by_path.get(canonical_ue_path(ref))
            if resolved is None:
                continue
            material_path = resolved["objectPath"]
            particle_material_paths.add(material_path)
            used_material_paths.add(material_path)

    material_library = []
    native_texture_references = 0
    explicit_blend_mode_preserved_count = 0
    explicit_blend_mode_mismatches = []

    for material_path in sorted(used_material_paths):
        if material_path == UE_DEFAULT_SURFACE_MATERIAL:
            material_library.append({
                "materialPath": material_path,
                "exportType": "SyntheticDefaultSurface",
                "blendMode": "BLEND_Opaque",
                "shadingModel": "MSM_DefaultLit",
                "opacityMaskClipValue": 0.333,
                "twoSided": False,
                "disableDepthTest": False,
                "isMasked": False,
                "canonicalTextures": {
                    channel: None
                    for channel in CANONICAL_TEXTURE_KEYS
                },
                "textures": [],
                "scalars": [],
                "colors": [],
                "switches": [],
                "rawPropertyKeys": [],
                "runtimeSemantics":
                    "UE null material -> UMaterial::GetDefaultMaterial(MD_Surface)",
            })
            continue

        material = material_by_path.get(canonical_ue_path(material_path))
        if material is None:
            continue

        texture_rows = []
        textures_by_parameter = {}

        for texture in material.get("textures", []):
            parameter = texture["parameter"]
            object_path = texture.get("objectPath")
            native = (
                texture_by_path.get(canonical_ue_path(object_path))
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

        # Some UE4.21 cooked base Materials retain all TextureSample inputs but
        # lose the semantic PM_* parameter names. Recover only when multiple
        # numbered siblings expose an explicit semantic parameter and exactly
        # one of those source paths is also present in this target's own graph.
        # This is source-family consensus, never a guessed filename binding.
        target_texture_paths = [
            row.get("texturePath")
            for row in texture_rows
            if row.get("texturePath")
        ]
        sibling_semantic_bindings = {}
        if not canonical.get("diffuse"):
            sibling_diffuse = sibling_parameter_consensus(
                materials.get("materials", []),
                material_path,
                target_texture_paths,
                "AlbedoTexture",
            )
            if sibling_diffuse:
                canonical["diffuse"] = sibling_diffuse
                sibling_semantic_bindings["diffuse"] = sibling_diffuse
        if not canonical.get("normal"):
            sibling_normal = sibling_parameter_consensus(
                materials.get("materials", []),
                material_path,
                target_texture_paths,
                "NormalTexture",
            )
            if sibling_normal:
                canonical["normal"] = sibling_normal
                sibling_semantic_bindings["normal"] = sibling_normal

        # CUE4Parse's UMaterial model initializes ShadingModel to Unlit,
        # but UE4.21.2's UMaterial constructor initializes it to DefaultLit.
        # Cooked packages omit properties that equal the engine constructor
        # default, so an absent ShadingModel property is positive source
        # authority for MSM_DefaultLit, not MSM_Unlit. Apply the same rule
        # through MaterialInstance inheritance unless that instance explicitly
        # overrides the property.
        raw_property_keys = material.get("rawPropertyKeys", [])
        base_path = material.get("semanticBaseMaterialPath") or material_path
        base_material = material_by_path.get(
            canonical_ue_path(base_path),
            material,
        )
        base_source_property_names = source_raw_property_names(base_material)

        runtime_blend_mode = material["blendMode"]
        runtime_shading_model = material["shadingModel"]
        runtime_opacity_mask_clip = material.get(
            "opacityMaskClipValue",
        )
        runtime_two_sided = material.get("twoSided")
        runtime_disable_depth_test = material.get(
            "disableDepthTest",
        )
        runtime_default_sources = []

        if (
            base_material.get("exportType") == "Material"
            and not material.get("semanticShadingOverride", False)
            and "ShadingModel" not in base_source_property_names
        ):
            runtime_shading_model = "MSM_DefaultLit"
            runtime_default_sources.append(
                "UE4.21.2 UMaterial ctor ShadingModel=MSM_DefaultLit"
            )

        if (
            base_material.get("exportType") == "Material"
            and not material.get("semanticBlendOverride", False)
            and "BlendMode" not in base_source_property_names
        ):
            runtime_blend_mode = "BLEND_Opaque"
            runtime_default_sources.append(
                "UE4.21.2 UMaterial ctor BlendMode=BLEND_Opaque"
            )

        if (
            base_material.get("exportType") == "Material"
            and not material.get("semanticOpacityMaskOverride", False)
            and "OpacityMaskClipValue" not in base_source_property_names
        ):
            runtime_opacity_mask_clip = 0.3333
            runtime_default_sources.append(
                "UE4.21.2 UMaterial ctor OpacityMaskClipValue=0.3333"
            )

        if (
            base_material.get("exportType") == "Material"
            and not material.get("semanticTwoSidedOverride", False)
            and "TwoSided" not in base_source_property_names
        ):
            runtime_two_sided = False
            runtime_default_sources.append(
                "UE4.21.2 UMaterial ctor TwoSided=false"
            )

        if (
            base_material.get("exportType") == "Material"
            and "bDisableDepthTest" not in base_source_property_names
        ):
            runtime_disable_depth_test = False
            runtime_default_sources.append(
                "UE4.21.2 UMaterial ctor bDisableDepthTest=false"
            )

        # If the cooked base UMaterial explicitly serialized BlendMode in
        # either raw source view, that value is source authority and must never
        # be replaced by the UE constructor default. This catches particle
        # masters whose rawPropertyKeys omit BlendMode while
        # rawMaterialProperties still contains it.
        if "BlendMode" in base_source_property_names:
            if runtime_blend_mode == material["blendMode"]:
                explicit_blend_mode_preserved_count += 1
            else:
                explicit_blend_mode_mismatches.append({
                    "materialPath": material_path,
                    "baseMaterialPath": base_path,
                    "sourceBlendMode": material["blendMode"],
                    "runtimeBlendMode": runtime_blend_mode,
                })

        material_library.append({
            "materialPath": material_path,
            "exportType": material["exportType"],
            "blendMode": runtime_blend_mode,
            "shadingModel": runtime_shading_model,
            "opacityMaskClipValue": runtime_opacity_mask_clip,
            "twoSided": runtime_two_sided,
            "disableDepthTest": runtime_disable_depth_test,
            "isMasked": runtime_blend_mode == "BLEND_Masked",
            "canonicalTextures": canonical,
            "textures": texture_rows,
            "scalars": material.get("scalars", []),
            "colors": material.get("colors", []),
            "switches": material.get("switches", []),
            "rawPropertyKeys": raw_property_keys,
            "sourceRawPropertyNames": sorted(source_raw_property_names(material)),
            "baseSourceRawPropertyNames": sorted(base_source_property_names),
            "auditBlendMode": material.get("blendMode"),
            "auditShadingModel": material.get("shadingModel"),
            "semanticBaseMaterialPath": base_path,
            "runtimeEngineDefaults": runtime_default_sources,
            "sourceSiblingSemanticBindings": sibling_semantic_bindings,
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
        "defaultSurfaceBindingCount":
            null_base_material_bindings,
        "engineDefaultSurfaceResolved":
            resolved_engine_default_surface_path is not None,
        "engineDefaultSurfacePath":
            resolved_engine_default_surface_path,
        "nullBaseMaterialBindings":
            null_base_material_binding_rows,
        "instanceOverrideRecordCount":
            len(instance_override_rows),
        "effectiveOverrideSlotCount":
            effective_override_slots,
        "effectiveOverrideSubmeshCount":
            effective_override_submeshes,
        "usedMaterialCount": len(material_library),
        "particleGraphMaterialCount": len(particle_material_paths),
        "particleEmitterMaterialReferenceCount":
            len(particle_emitter_material_references),
        "particleEmitterUnresolvedMaterialReferenceCount":
            len(particle_emitter_unresolved_material_references),
        "particleEmitterUnresolvedMaterialReferences":
            particle_emitter_unresolved_material_references,
        "nativeTextureReferenceCount":
            native_texture_references,
        "unresolvedMeshCount": len(unresolved_meshes),
        "invalidMaterialSlotCount":
            len(invalid_material_slots),
        "unresolvedMaterialCount":
            len(unresolved_materials),
        "unresolvedTextureCount":
            len(unresolved_textures),
        "explicitBlendModePreservedCount":
            explicit_blend_mode_preserved_count,
        "explicitBlendModeMismatchCount":
            len(explicit_blend_mode_mismatches),
        "explicitBlendModeMismatches":
            explicit_blend_mode_mismatches,
    }

    summary["ready"] = (
        summary["sceneMeshCount"] == len(scene["meshes"])
        and summary["baseSubmeshBindingCount"]
            == summary["expectedSceneSubmeshes"]
        and summary["unresolvedMeshCount"] == 0
        and summary["invalidMaterialSlotCount"] == 0
        and summary["unresolvedMaterialCount"] == 0
        and summary["unresolvedTextureCount"] == 0
        and summary["explicitBlendModeMismatchCount"] == 0
    )

    output = {
        "schemaVersion": 1,
        "format": "xziel_ue_material_binding_manifest_v1",
        "canonicalTextureKeys": CANONICAL_TEXTURE_KEYS,
        "ueDefaultSurfaceMaterial":
            UE_DEFAULT_SURFACE_MATERIAL,
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
    for row in null_base_material_binding_rows:
        print("XZIEL_UE_DEFAULT_SURFACE_BINDING", row)

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
