extends SceneTree
## Godot 4.6.1 source-preserving rollback unit; 340 candidates in 10793 ID census.
## Synthetic fixture ONLY: neither original Nacht camera nor Android test.
func _initialize() -> void:
    call_deferred("_run")

func _run() -> void:
    var batching_script: Script=load("res://nacht_apply_vista_spatial_multimesh_research.gd") as Script
    var restore_script: Script=load("res://nacht_revert_vista_spatial_multimesh_research.gd") as Script
    if batching_script==null or restore_script==null:
        push_error("XZOGOT_NACHT_VISTA_MULTIMESH_REVERT_GODOT_SCRIPTS_MISSING_RED")
        quit(2)
        return
    var world: Node3D=Node3D.new()
    root.add_child(world)
    var staging: Node3D=Node3D.new()
    world.add_child(staging)
    var original_mesh: ArrayMesh=ArrayMesh.new()
    var arrays: Array=[]
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX]=PackedVector3Array([
        Vector3(-0.12,0.0,0.0),Vector3(0.12,0.0,0.0),Vector3(0,0.3,0)])
    arrays[Mesh.ARRAY_INDEX]=PackedInt32Array([0,1,2])
    original_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
    original_mesh.surface_set_material(0,StandardMaterial3D.new())
    var original_lookup: Dictionary={}
    for i: int in range(10793):
        original_lookup["ue_instance_%06d"%i]=null
    var details: Array=[]
    var policies: Array=[]
    var originals: Array[MeshInstance3D]=[]
    var transforms: Array[Transform3D]=[]
    for i: int in range(340):
        var id: String="ue_instance_%06d"%i
        var node: MeshInstance3D=MeshInstance3D.new()
        node.mesh=original_mesh
        node.position=Vector3(100.0+float(i%20)*32.0+float(i/20)*0.1,0,100)
        world.add_child(node)
        original_lookup[id]=node
        originals.append(node)
        transforms.append(node.global_transform)
        details.append({"originalActorID":id,"sourceNativeMeshType":145})
        policies.append({"actorId":id,"authoredAssetClass":"tree_silhouette",
            "nativeSourceMeshIndex":145,
            "originalOriginXZ":[node.position.x,node.position.z]})
    var vista: Dictionary={"originalSourceActors":10793,"actorDetails":details}
    var policy: Dictionary={"sourceActorCount":10793,"actors":policies}
    var result: Dictionary=(batching_script.new() as RefCounted).call(
        "apply_original_vista_instance_batching",vista,policy,original_lookup,staging,32.0) as Dictionary
    if (not (result.get("errors",[]) as Array).is_empty()
        or int(result.get("originalActorsTemporarilyHidden",-1))!=340
        or int(result.get("actualOriginalSourceMultimeshNodes",0))<10):
        push_error("XZOGOT_NACHT_ROLLBACK_SET_UP_PROTECTED_BATCH_RED "+JSON.stringify(result))
        quit(3)
        return
    var rollback: Dictionary=(restore_script.new() as RefCounted).call(
        "restore_original_vista_multimesh",vista,original_lookup,staging) as Dictionary
    if (not (rollback.get("errors",[]) as Array).is_empty()
        or int(rollback.get("originalSourceActorsRestored",-1))!=340
        or int(rollback.get("originalSourceActorsStillPresent",-1))!=10793
        or not rollback.get("researchBatchDetachedAndQueuedForDeletionOfREPLACEMENTONLY",false)):
        push_error("XZOGOT_NACHT_ROLLBACK_ORIGINAL_SOURCE_VISTA_RESTORE_RED "+JSON.stringify(rollback))
        quit(4)
        return
    for i: int in range(originals.size()):
        var node: MeshInstance3D=originals[i]
        if not node.visible or node.global_transform!=transforms[i] or node.mesh!=original_mesh:
            push_error("XZOGOT_NACHT_ROLLBACK_CHANGED_NATIVE_SOURCE_MESH_RED actor="+str(i))
            quit(5)
            return
    # Fallback idempotence must be fail-closed; no second mutation.
    var twice: Dictionary=(restore_script.new() as RefCounted).call(
        "restore_original_vista_multimesh",vista,original_lookup,staging) as Dictionary
    if (twice.get("errors",[]) as Array).is_empty():
        push_error("XZOGOT_NACHT_ROLLBACK_DOUBLE_APPLY_NOT_REJECTED_RED")
        quit(6)
        return
    print("XZOGOT_NACHT_GODOT461_RESEARCH_VISTA_MULTIMESH_REAL_SOURCE_NODE_RESTORE_GREEN")
    quit(0)
