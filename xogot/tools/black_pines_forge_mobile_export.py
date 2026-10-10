"""Non-destructive, zone-aware mobile batching for Black Pines Forge.

The source .blend and GUI scene keep every model editable. Export-only copies
are joined by zone+material, which reduces Godot MeshInstance/draw node cost.
When the export is complete, dispose ONLY temp copies, never original source.
Meshes keep their Blender UVs, material slots, and world-space transforms.
"""
from collections import defaultdict
import bpy

MAX_MOBILE_DRAW_NODES=165
MIN_REDUCTION_FRACTION=.55
TEMP_COLLECTION="BP_Forge_Mobile_Export_Temporary"
PRESERVE_PREFIXES=("Forge_Hero_", "Forge_TiledFloor_", "Forge_Sign_")

def _zone(obj, layout):
    # Original Godot layout uses X,Z; Blender native X,-Z,Z.
    p=obj.matrix_world.translation
    world_x=float(p.x)
    world_z=-float(p.y)
    xs=list(map(float,layout["cellBoundaries"]["x"]))
    zs=list(map(float,layout["cellBoundaries"]["z"]))
    for j in range(3):
        for i in range(3):
            if xs[i]<=world_x<xs[i+1] and zs[j]<=world_z<zs[j+1]:
                return "%d%d"%(i,j)
    return "outer"

def _preserved(obj):
    return obj.name.startswith(PRESERVE_PREFIXES)

def _material_key(obj):
    if len(obj.data.materials)==1 and obj.data.materials[0]!=None:
        return obj.data.materials[0].name.replace("BP_","")
    # Multi-material mesh has to be kept untouched (e.g. tiled floors).
    return ""

def _clean(collection):
    if collection is None:
        return
    for obj in tuple(collection.objects):
        if obj.type=="MESH":
            bpy.data.objects.remove(obj,do_unlink=True)
    if bpy.data.collections.get(collection.name)!=None:
        bpy.data.collections.remove(collection)

def build_export_batches(layout):
    """Returns (selected export meshes, report, cleanup_fn).

    Always call cleanup_fn() in a finally block after bpy.ops.export_scene.
    Optimizer never changes the source objects or source blend on disk.
    """
    if bpy.data.collections.get(TEMP_COLLECTION)!=None:
        raise RuntimeError("BLACK_PINES_MOBILE_BATCH_RED prior temporary export leaked")
    source=[obj for obj in bpy.context.scene.objects if obj.type=="MESH"]
    groups=defaultdict(list)
    keep=[]
    for obj in source:
        key=_material_key(obj)
        if _preserved(obj) or not key:
            keep.append(obj)
            continue
        groups[(_zone(obj,layout),key)].append(obj)
    collection=bpy.data.collections.new(TEMP_COLLECTION)
    bpy.context.scene.collection.children.link(collection)
    generated=[]
    covered=0
    try:
        for (zone,material),items in sorted(groups.items()):
            if len(items)==1:
                keep.extend(items)
                continue
            duplicates=[]
            # A clone is required: bpy.ops.object.join mutates/deletes meshes,
            # while Forge GUI must retain source-model editability intact.
            for obj in items:
                clone=obj.copy()
                clone.data=obj.data.copy()
                collection.objects.link(clone)
                duplicates.append(clone)
            bpy.ops.object.select_all(action="DESELECT")
            for obj in duplicates:
                obj.select_set(True)
            bpy.context.view_layer.objects.active=duplicates[0]
            bpy.ops.object.join()
            joined=duplicates[0]
            joined.name="BP_Batch_%s_%s"%(zone,material)
            joined.data.name=joined.name+"_Mesh"
            generated.append(joined)
            covered+=len(items)
        selected=keep+generated
        if not selected:
            raise RuntimeError("BLACK_PINES_MOBILE_BATCH_RED no export geometry")
        # In Blender, GLTF exporter exports only selected MESH (not cameras,
        # area lights, source clones, or editor-only helper empties).
        bpy.ops.object.select_all(action="DESELECT")
        for obj in selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active=selected[0]
        report={
            "originalMeshObjects":len(source),
            "mobileExportMeshObjects":len(selected),
            "joinedBatchCount":len(generated),
            "originalSourceObjectsConsolidated":covered,
            "remainingOriginalNodes":len(keep),
            "reductionFraction":round(1.0-float(len(selected))/max(len(source),1),4),
            "nineHeroMeshesPreserved":sum(1 for obj in selected
                if obj.name.startswith("Forge_Hero_"))==9,
            "nineFloorMeshesPreserved":sum(1 for obj in selected
                if obj.name.startswith("Forge_TiledFloor_"))==9,
            "sourceBlendEditableUntouched":True,
            "mobileFrameratePhysicallyMeasured":False
        }
        if len(selected)>MAX_MOBILE_DRAW_NODES:
            raise RuntimeError("BLACK_PINES_MOBILE_BATCH_RED budget "+str(report))
        if report["reductionFraction"]<MIN_REDUCTION_FRACTION:
            raise RuntimeError("BLACK_PINES_MOBILE_BATCH_RED weak reduction "+str(report))
        if not report["nineHeroMeshesPreserved"] or not report["nineFloorMeshesPreserved"]:
            raise RuntimeError("BLACK_PINES_MOBILE_BATCH_RED lost signature assets "+str(report))
        print("BLACK_PINES_MOBILE_DRAW_BATCH_GREEN",
              "original=",len(source),"exported=",len(selected),
              "saved_pct=",round(report["reductionFraction"]*100,1),
              "materialZoneBatches=",len(generated))
        def clean_up():
            bpy.ops.object.select_all(action="DESELECT")
            _clean(collection)
        return selected,report,clean_up
    except Exception:
        bpy.ops.object.select_all(action="DESELECT")
        _clean(collection)
        raise


def export_glb(filepath, layout):
    _,report,cleanup=build_export_batches(layout)
    try:
        bpy.ops.export_scene.gltf(filepath=str(filepath),
                                  export_format="GLB",
                                  use_selection=True,
                                  export_apply=False)
        return report
    finally:
        cleanup()
