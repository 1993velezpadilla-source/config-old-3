extends SceneTree
## VISUAL PARITY synthetic Godot Mesa, original MeshInstance3D vs 32m native
## spatial MultiMesh. Two original DDS-like material surfaces and 340 instances.
## NOT full Pavlov UE4.21 source, NOT Android GPU, NOT certified for shipping.

func _initialize() -> void:
    call_deferred("_run")

func _snap(label: String) -> Image:
    for frame: int in range(5):
        await process_frame
    await create_timer(0.4).timeout
    for frame: int in range(4):
        await process_frame
    var img: Image=root.get_texture().get_image()
    img.convert(Image.FORMAT_RGBA8)
    var path: String="res://"+label+".png"
    img.save_png(path)
    return img

func _make_tree_mesh() -> ArrayMesh:
    var mesh: ArrayMesh=ArrayMesh.new()
    for surf: int in range(2):
        var arrays: Array=[]
        arrays.resize(Mesh.ARRAY_MAX)
        var size: float=1.4 if surf==0 else 0.25
        var height: float=3.0 if surf==0 else 1.3
        var y_offset: float=0.7 if surf==0 else 0.0
        arrays[Mesh.ARRAY_VERTEX]=PackedVector3Array([
            Vector3(-size,y_offset,0),Vector3(size,y_offset,0),
            Vector3(0,y_offset+height,0)])
        arrays[Mesh.ARRAY_INDEX]=PackedInt32Array([0,1,2])
        arrays[Mesh.ARRAY_NORMAL]=PackedVector3Array([
            Vector3(0,0,1),Vector3(0,0,1),Vector3(0,0,1)])
        arrays[Mesh.ARRAY_TEX_UV]=PackedVector2Array([
            Vector2(0,1),Vector2(1,1),Vector2(0.5,0)])
        mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
        var mat: StandardMaterial3D=StandardMaterial3D.new()
        mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
        mat.cull_mode=BaseMaterial3D.CULL_DISABLED
        mat.albedo_color=Color(0.25,0.52,0.32,1.0) if surf==0 else Color(0.32,0.20,0.10,1.0)
        mesh.surface_set_material(surf,mat)
    return mesh

func _run() -> void:
    var script: Script=load("res://nacht_apply_vista_spatial_multimesh_research.gd") as Script
    if script==null:
        push_error("XZOGOT_NACHT_VISUAL_BATCH_SCRIPT_NOT_LOADABLE_RED")
        quit(2)
        return
    var world: Node3D=Node3D.new()
    root.add_child(world)
    var environment: WorldEnvironment=WorldEnvironment.new()
    environment.environment=Environment.new()
    environment.environment.background_mode=Environment.BG_COLOR
    environment.environment.background_color=Color(0.04,0.055,0.08)
    world.add_child(environment)
    var camera: Camera3D=Camera3D.new()
    camera.fov=64.0
    camera.near=0.05
    camera.far=1000.0
    world.add_child(camera)
    camera.global_position=Vector3(104.0,3.0,30.0)
    camera.look_at(Vector3(104.0,1.0,100.0),Vector3.UP)
    camera.current=true
    var mesh: ArrayMesh=_make_tree_mesh()
    var lookup: Dictionary={}
    for i: int in range(10793):
        lookup["ue_instance_%06d"%i]=null
    var vista_rows: Array=[]
    var policy_rows: Array=[]
    var originals: Array[MeshInstance3D]=[]
    var transforms: Array[Transform3D]=[]
    for i: int in range(340):
        var id: String="ue_instance_%06d"%i
        var instance: MeshInstance3D=MeshInstance3D.new()
        instance.mesh=mesh
        # All 20 spatial cells carry 17 ORIGINAL actors each; no actor
        # moved by the optimizer, no per-instance invented pivot correction.
        var cell: int=i/17
        var ix: int=i%17
        instance.position=Vector3(100.0+float(cell)*32.0+float(ix%6)*0.8,
            0.0,100.0+float(ix/6)*0.6)
        world.add_child(instance)
        originals.append(instance)
        transforms.append(instance.global_transform)
        lookup[id]=instance
        vista_rows.append({"originalActorID":id,"sourceNativeMeshType":145})
        policy_rows.append({
            "actorId":id,"authoredAssetClass":"tree_silhouette",
            "nativeSourceMeshIndex":145,
            "originalOriginXZ":[instance.position.x,instance.position.z]})
    var original: Image=await _snap("synthetic-original-original-meshinstances")
    var batcher: RefCounted=script.new() as RefCounted
    var result: Dictionary=batcher.call("apply_original_vista_instance_batching",
        {"originalSourceActors":10793,"actorDetails":vista_rows},
        {"sourceActorCount":10793,"actors":policy_rows},lookup,world,32.0) as Dictionary
    if (not (result.get("errors",[]) as Array).is_empty()
        or int(result.get("originalActorsTemporarilyHidden",0))!=340
        or int(result.get("actualOriginalSourceMultimeshNodes",0))!=20):
        push_error("XZOGOT_NACHT_SYNTHETIC_RENDER_BATCH_FAILED_RED "+JSON.stringify(result))
        quit(3)
        return
    for i: int in range(originals.size()):
        if originals[i].visible or originals[i].global_transform!=transforms[i]:
            push_error("XZOGOT_NACHT_SYNTHETIC_RENDER_ORIGINAL_MESH_MUTATED_RED")
            quit(4)
            return
    var batched: Image=await _snap("synthetic-after-32m-multimesh")
    if batched.get_size()!=original.get_size():
        push_error("XZOGOT_NACHT_SYNTHETIC_RENDER_WRONG_CAMERA_RESOLUTION_RED")
        quit(5)
        return
    var total: float=0.0
    var maxc: float=0.0
    var changed: int=0
    var pixel_count: int=original.get_width()*original.get_height()
    for y: int in range(original.get_height()):
        for x: int in range(original.get_width()):
            var a: Color=original.get_pixel(x,y)
            var b: Color=batched.get_pixel(x,y)
            var diff: float=(absf(a.r-b.r)+absf(a.g-b.g)+absf(a.b-b.b))/3.0
            total+=diff
            maxc=maxf(maxc,diff)
            if diff>0.03:
                changed+=1
    var mean_percent: float=100.0*total/float(pixel_count)
    var changed_percent: float=100.0*float(changed)/float(pixel_count)
    var audit: Dictionary={
        "source":"SYNTHETIC 340 tree instances only, NOT authentic source Nacht",
        "mesaRenderer":RenderingServer.get_rendering_device()==null,
        "syntheticOriginalActorInstances":340,
        "nativeSourceActorIDsPreservedInSyntheticIndex":10793,
        "groupedCellMeters":32,
        "originalHidden":result["originalActorsTemporarilyHidden"],
        "actualSyntheticMultiMeshGroups":result["actualOriginalSourceMultimeshNodes"],
        "renderPixelWidth":original.get_width(),"renderPixelHeight":original.get_height(),
        "meanRGBDifferencePercent":mean_percent,
        "changedRGBPixelsOver3Percent":changed,
        "changedRGBPixelPercent":changed_percent,
        "maximumRGBPixelDifference":maxc,
        "physicalAndroidFPSProven":false,
        "fullOriginalNachtVisualParityProven":false,
        "approvedForShipping":false
    }
    var f: FileAccess=FileAccess.open("res://synthetic-render-parity-audit.json",FileAccess.WRITE)
    f.store_string(JSON.stringify(audit,"\t"))
    f.close()
    if mean_percent>0.30 or changed_percent>1.50:
        push_error("XZOGOT_NACHT_SYNTHETIC_VISUAL_MULTIMESH_PIXEL_PARITY_RED "+JSON.stringify(audit))
        quit(6)
        return
    print("XZOGOT_NACHT_GODOT461_SYNTHETIC_MESA_MULTI_VISUAL_PIXEL_PARITY_GREEN ",JSON.stringify(audit))
    quit(0)
