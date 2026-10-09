extends SceneTree
## Synthetic Godot 4.6.1 parser/source-actor preservation probe, NOT real GPU FPS.
func _initialize() -> void:
    call_deferred("_run")

func _run() -> void:
    var script: Script=load("res://nacht_apply_vista_spatial_multimesh_research.gd") as Script
    if script==null:
        push_error("XZOGOT_NACHT_MULTIMESH_SYNTHETIC_GDSCRIPT_PARSE_RED")
        quit(2)
        return
    var batcher: RefCounted=script.new() as RefCounted
    var world: Node3D=Node3D.new()
    root.add_child(world)
    var mesh: ArrayMesh=ArrayMesh.new()
    var arr: Array=[]
    arr.resize(Mesh.ARRAY_MAX)
    arr[Mesh.ARRAY_VERTEX]=PackedVector3Array([
        Vector3(-0.1,0,0),Vector3(0.1,0,0),Vector3(0,0.2,0)
    ])
    arr[Mesh.ARRAY_INDEX]=PackedInt32Array([0,1,2])
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arr)
    var material: StandardMaterial3D=StandardMaterial3D.new()
    mesh.surface_set_material(0,material)
    var lookup: Dictionary={}
    for i: int in range(10793):
        lookup["ue_instance_%06d"%i]=null
    var candidates: Array=[]
    var originals: Array[MeshInstance3D]=[]
    var policies: Array=[]
    var transforms: Array[Transform3D]=[]
    for i: int in range(340):
        var original_id: String="ue_instance_%06d"%i
        var instance: MeshInstance3D=MeshInstance3D.new()
        instance.name="FixtureNativeActor_"+str(i)
        instance.mesh=mesh
        instance.position=Vector3(100.0+float(i%20)*32.0+float(i/20)*0.1,0.0,100.0)
        world.add_child(instance)
        originals.append(instance)
        transforms.append(instance.global_transform)
        lookup[original_id]=instance
        candidates.append({"originalActorID":original_id,"sourceNativeMeshType":145})
        policies.append({
            "actorId":original_id,
            "authoredAssetClass":"tree_silhouette",
            "nativeSourceMeshIndex":145,
            "originalOriginXZ":[instance.position.x,instance.position.z]
        })
    var vista: Dictionary={"originalSourceActors":10793,"actorDetails":candidates}
    var policy: Dictionary={"sourceActorCount":10793,"actors":policies}
    var report: Dictionary=batcher.call("apply_original_vista_instance_batching",
        vista,policy,lookup,world,32.0) as Dictionary
    if (not (report.get("errors",[]) as Array).is_empty()
        or int(report.get("originalSourceActorsStillPresent",0))!=10793
        or int(report.get("originalActorsTemporarilyHidden",0))!=340
        or int(report.get("actualOriginalSourceMultimeshNodes",0))<10):
        push_error("XZOGOT_NACHT_SYNTHETIC_MULTIMESH_SOURCE_ID_TEST_RED "+JSON.stringify(report))
        quit(3)
        return
    for i: int in range(originals.size()):
        if originals[i].visible or originals[i].global_transform!=transforms[i]:
            push_error("XZOGOT_NACHT_SYNTHETIC_SOURCE_ACTOR_WAS_MUTATED_RED")
            quit(4)
            return
    var batch_nodes: Array[Node]=world.find_children("*","MultiMeshInstance3D",true,false)
    if batch_nodes.size()!=int(report["actualOriginalSourceMultimeshNodes"]):
        push_error("XZOGOT_NACHT_SYNTHETIC_MULTIMESH_GROUP_MISSING_RED")
        quit(5)
        return
    print("XZOGOT_NACHT_GODOT461_SYNTHETIC_ORIGINAL_VISTA_MULTIMESH_GRAPH_GREEN ",JSON.stringify(report))
    quit(0)
