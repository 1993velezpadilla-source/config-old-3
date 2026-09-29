#!/usr/bin/env python3
import argparse
import json
import struct
from pathlib import Path

MAGIC = b"XZMI"
VERSION = 1
HEADER_BYTES = 48
INSTANCE_RECORD_BYTES = 8
BINDING_RECORD_BYTES = 4
NO_MATERIAL = 0xFFFFFFFF


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def override_slot(row):
    return int(row.get("slotIndex", row.get("SlotIndex")))


def override_material(row):
    return row.get("materialPath", row.get("ObjectPath", row.get("objectPath")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    scene = load(args.scene)
    manifest = load(args.manifest)

    if manifest.get("format") != "xziel_ue_material_binding_manifest_v1":
        raise SystemExit("unsupported material binding manifest format")

    material_paths = sorted(
        row["materialPath"]
        for row in manifest["materials"]
    )
    material_index = {
        path: index
        for index, path in enumerate(material_paths)
    }

    mesh_rows = {
        int(row["sceneMeshIndex"]): row
        for row in manifest["meshes"]
    }

    overrides_by_instance = {}
    for row in manifest.get("instanceOverrides", []):
        source_instance_index = int(row["sourceInstanceIndex"])
        if source_instance_index in overrides_by_instance:
            raise SystemExit(
                f"duplicate override record for source instance "
                f"{source_instance_index}"
            )
        overrides_by_instance[source_instance_index] = {
            int(item["slotIndex"]): item["materialPath"]
            for item in row.get("slotOverrides", [])
        }

    instance_records = []
    bindings = []
    no_material_count = 0
    overridden_binding_count = 0
    referenced_materials = set()

    for source_instance_index, instance in enumerate(scene["instances"]):
        mesh_index = int(instance["meshIndex"])
        mesh = mesh_rows.get(mesh_index)
        if mesh is None:
            raise SystemExit(
                f"scene instance {source_instance_index} references "
                f"missing material mesh {mesh_index}"
            )

        overrides = overrides_by_instance.get(
            source_instance_index,
            {},
        )

        first_binding = len(bindings)

        for section in mesh["sections"]:
            slot_index = int(section["slotIndex"])
            material_path = section.get("baseMaterialPath")

            if slot_index in overrides:
                material_path = overrides[slot_index]
                overridden_binding_count += 1

            if material_path is None:
                bindings.append(NO_MATERIAL)
                no_material_count += 1
                continue

            index = material_index.get(material_path)
            if index is None:
                raise SystemExit(
                    f"material {material_path!r} missing from library"
                )

            bindings.append(index)
            referenced_materials.add(material_path)

        binding_count = len(bindings) - first_binding
        if binding_count <= 0:
            raise SystemExit(
                f"instance {source_instance_index} has no submesh bindings"
            )

        instance_records.append(
            (first_binding, binding_count)
        )

    expected_override_bindings = int(
        manifest["summary"]["effectiveOverrideSubmeshCount"]
    )

    if overridden_binding_count != expected_override_bindings:
        raise SystemExit(
            "override binding count mismatch: "
            f"{overridden_binding_count} != {expected_override_bindings}"
        )

    if len(instance_records) != len(scene["instances"]):
        raise SystemExit("instance record count mismatch")

    if not material_paths:
        raise SystemExit("material library is empty")

    binding_table_offset = (
        HEADER_BYTES
        + len(instance_records) * INSTANCE_RECORD_BYTES
    )
    file_bytes = (
        binding_table_offset
        + len(bindings) * BINDING_RECORD_BYTES
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("wb") as stream:
        stream.write(MAGIC)
        stream.write(struct.pack(
            "<11I",
            VERSION,
            len(instance_records),
            len(material_paths),
            len(bindings),
            INSTANCE_RECORD_BYTES,
            BINDING_RECORD_BYTES,
            0,
            HEADER_BYTES,
            binding_table_offset,
            0,
            0,
        ))

        for first_binding, binding_count in instance_records:
            stream.write(
                struct.pack(
                    "<2I",
                    first_binding,
                    binding_count,
                )
            )

        for value in bindings:
            stream.write(struct.pack("<I", value))

    if out.stat().st_size != file_bytes:
        raise SystemExit(
            f"XZMI file size mismatch "
            f"{out.stat().st_size} != {file_bytes}"
        )

    unique_material_indices = {
        value
        for value in bindings
        if value != NO_MATERIAL
    }

    report = {
        "schemaVersion": 1,
        "format": "XZMI",
        "version": VERSION,
        "fileBytes": file_bytes,
        "instanceCount": len(instance_records),
        "materialCount": len(material_paths),
        "bindingCount": len(bindings),
        "noMaterialBindingCount": no_material_count,
        "overriddenBindingCount": overridden_binding_count,
        "referencedMaterialCount": len(unique_material_indices),
        "unreferencedMaterialCount":
            len(material_paths) - len(unique_material_indices),
        "materialPaths": material_paths,
        "ready": (
            len(instance_records) > 0
            and len(material_paths) > 0
            and len(bindings) > 0
            and overridden_binding_count
                == expected_override_bindings
        ),
    }

    Path(args.report).write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("XZIEL_XZMI_BUILD", {
        "instances": report["instanceCount"],
        "materials": report["materialCount"],
        "bindings": report["bindingCount"],
        "noMaterial": report["noMaterialBindingCount"],
        "overridden": report["overriddenBindingCount"],
        "referencedMaterials": report["referencedMaterialCount"],
        "fileBytes": report["fileBytes"],
        "ready": report["ready"],
    })

    if not report["ready"]:
        print("XZIEL_XZMI_BUILD_FAILURE")
        return 5

    print("XZIEL_XZMI_BUILD_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
