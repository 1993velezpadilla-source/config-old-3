extends RefCounted
## NON-SHIPPING, actual source actor IDs. Research-only source-preserving
## 32m spatial MultiMesh A/B. Every original actor remains in the scene.
## No claims of Android FPS or per-instance culling equivalence.

static func dist_aabb_xz(anchor: Vector2, box: AABB) -> float:
    var x: float=clampf(anchor.x,box.position.x,box.end.x)
    var z: float=clampf(anchor.y,box.position.z,box.end.z)
    return anchor.distance_to(Vector2(x,z))

func apply_original_vista_instance_batching(vista: Dictionary, policy: Dictionary,
        by_actor: Dictionary, parent: Node3D, cell_m: float=32.0) -> Dictionary:
    var errors: Array[String]=[]
    if (int(vista.get("originalSourceActors",0))!=10793
        or (vista.get("actorDetails",[]) as Array).size()!=340
        or int(policy.get("sourceActorCount",0))!=10793
        or by_actor.size()!=10793 or cell_m<12.0 or cell_m>64.0):
        return {"errors":["invalid original 10793 actor / 340 Vista authority"]}
    var policies: Dictionary={}
    for row_any: Variant in policy["actors"]:
        var row: Dictionary=row_any as Dictionary
        var id: String=str(row["actorId"])
        if policies.has(id):
            return {"errors":["duplicate source policy actor "+id]}
        policies[id]=row
    var groups: Dictionary={}
    var ids: Dictionary={}
    var anchor: Vector2=Vector2(-2.494789,-7.258049)
    for datum_any: Variant in vista["actorDetails"]:
        var datum: Dictionary=datum_any as Dictionary
        var id: String=str(datum["originalActorID"])
        if ids.has(id) or not policies.has(id) or not by_actor.has(id):
            errors.append("unknown/repeated native source Vista actor "+id)
            break
        ids[id]=true
        var src: Dictionary=policies[id] as Dictionary
        var mi: MeshInstance3D=by_actor[id] as MeshInstance3D
        if (mi==null or mi.mesh==null or not (mi.mesh is ArrayMesh)
            or not mi.visible or str(src["authoredAssetClass"])!="tree_silhouette"
            or int(src["nativeSourceMeshIndex"])!=int(datum["sourceNativeMeshType"])):
            errors.append("Vista source mesh/class/visibility mismatch "+id)
            break
        if dist_aabb_xz(anchor,mi.global_transform*mi.mesh.get_aabb())<=55.0:
            errors.append("protected 55m building native world AABB "+id)
            break
        var materials: Array[Material]=[]
        var mat_ids: Array[String]=[]
        for surface: int in range(mi.mesh.get_surface_count()):
            var mat: Material=mi.get_surface_override_material(surface)
            if mat==null:
                mat=mi.mesh.surface_get_material(surface)
            if mat==null:
                errors.append("no original material on native source actor "+id)
                break
            materials.append(mat)
            mat_ids.append(str(mat.get_instance_id()))
        if not errors.is_empty():
            break
        var original_root: Array=src["originalOriginXZ"]
        if original_root.size()!=2:
            errors.append("native Vista XZ source absent "+id)
            break
        var cell_x: int=floori(float(original_root[0])/cell_m)
        var cell_z: int=floori(float(original_root[1])/cell_m)
        var key: String=JSON.stringify([
            int(datum["sourceNativeMeshType"]),str(mi.mesh.get_instance_id()),
            mat_ids,cell_x,cell_z,int(mi.cast_shadow),int(mi.layers),
            mi.lod_bias,mi.visibility_range_end,mi.visibility_range_end_margin,
            int(mi.gi_mode),str(mi.material_override),str(mi.material_overlay)
        ])
        if not groups.has(key):
            groups[key]={"actors":[],"materials":materials}
        (groups[key]["actors"] as Array).append(mi)
    if not errors.is_empty() or ids.size()!=340:
        return {"errors":errors if not errors.is_empty() else ["incomplete 340 actor sample"],
                "originalSourceActorsStillPresent":by_actor.size(),
                "originalActorsTemporarilyHidden":0}
    var batch_parent: Node3D=Node3D.new()
    batch_parent.name="NONSHIPPING_OriginalVistaSpatialMultimesh"
    parent.add_child(batch_parent)
    var multimesh_nodes: int=0
    var originals_hidden: int=0
    var original_surfaces: int=0
    var batch_surfaces: int=0
    for key_any: Variant in groups:
        var group: Dictionary=groups[key_any] as Dictionary
        var actors: Array=group["actors"] as Array
        if actors.size()<2:
            continue
        var prototype: MeshInstance3D=actors[0] as MeshInstance3D
        var mesh: ArrayMesh=prototype.mesh.duplicate(true) as ArrayMesh
        if mesh==null:
            errors.append("cannot copy original GLB mesh in nonshipping research")
            break
        var materials: Array=group["materials"] as Array
        for s: int in range(mesh.get_surface_count()):
            mesh.surface_set_material(s,materials[s] as Material)
        var mm: MultiMesh=MultiMesh.new()
        mm.transform_format=MultiMesh.TRANSFORM_3D
        mm.mesh=mesh
        mm.instance_count=actors.size()
        for i: int in range(actors.size()):
            mm.set_instance_transform(i,(actors[i] as MeshInstance3D).global_transform)
        var batched: MultiMeshInstance3D=MultiMeshInstance3D.new()
        batched.name="OriginalVistaSourceSpatialBatch_"+str(multimesh_nodes)
        batched.multimesh=mm
        batched.cast_shadow=prototype.cast_shadow
        batched.layers=prototype.layers
        batched.lod_bias=prototype.lod_bias
        batched.visibility_range_end=prototype.visibility_range_end
        batched.visibility_range_end_margin=prototype.visibility_range_end_margin
        batched.gi_mode=prototype.gi_mode
        batched.material_override=prototype.material_override
        batched.material_overlay=prototype.material_overlay
        batch_parent.add_child(batched)
        for original_any: Variant in actors:
            var original: MeshInstance3D=original_any as MeshInstance3D
            original.visible=false
            originals_hidden+=1
            original_surfaces+=original.mesh.get_surface_count()
        batch_surfaces+=prototype.mesh.get_surface_count()
        multimesh_nodes+=1
    if not errors.is_empty() or originals_hidden<100 or multimesh_nodes<10:
        for group_any: Variant in groups.values():
            for actor_any: Variant in (group_any as Dictionary)["actors"]:
                (actor_any as MeshInstance3D).visible=true
        batch_parent.queue_free()
        return {"errors":errors if not errors.is_empty() else ["real source instance identity could not be safely shared"],
                "originalActorsTemporarilyHidden":0,
                "originalSourceActorsStillPresent":by_actor.size()}
    return {
        "errors":[],
        "originalSourceActorsStillPresent":by_actor.size(),
        "originalVistaActorIDsVerified":ids.size(),
        "originalActorsTemporarilyHidden":originals_hidden,
        "originalVistaActorsLeftIndividual":340-originals_hidden,
        "actualOriginalSourceMultimeshNodes":multimesh_nodes,
        "originalSourceSurfaceSlotsReplacedForResearch":original_surfaces,
        "theoreticalBatchSurfaceSlots":batch_surfaces,
        "originalMeshTransformsPreserved":true,
        "originalCollisionNavigationChanged":false,
        "actualGPUCallsNotYetMeasured":true,
        "batchedCullingMayIncreaseTriangles":true,
        "androidFPSNotMeasured":true,
        "approvedForShipping":false,
        "cellSizeMeters":cell_m
    }
