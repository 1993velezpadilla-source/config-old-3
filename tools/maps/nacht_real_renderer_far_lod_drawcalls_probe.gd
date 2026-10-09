extends SceneTree
## ACTUAL Godot 4.6.1 RenderingServer draw/primitive counts in real Mesa GL.
## Research geometry-only benchmark: original lossless 10793 MeshInstances,
## no full DDS/textured material pipeline.  NOT mobile Android GPU FPS.
## Native source actors/material IDs never removed. 55m play ring guard.
func _initialize() -> void:
    call_deferred("_go")

func _collect(view: Camera3D, origin: Vector3, target: Vector3) -> Dictionary:
    view.global_position=origin
    view.look_at(target,Vector3.UP)
    for i: int in range(18):
        await process_frame
    var viewport: RID=root.get_viewport_rid()
    var visible_draws: int=RenderingServer.viewport_get_render_info(
        viewport,
        RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,
        RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
    var visible_prims: int=RenderingServer.viewport_get_render_info(
        viewport,
        RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,
        RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
    var shadow_draws: int=RenderingServer.viewport_get_render_info(
        viewport,
        RenderingServer.VIEWPORT_RENDER_INFO_TYPE_SHADOW,
        RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
    var total_calls: int=RenderingServer.get_rendering_info(
        RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
    var total_prims: int=RenderingServer.get_rendering_info(
        RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
    return {
        "visiblePassRealDrawCalls":visible_draws,
        "visiblePassActualRenderedPrimitives":visible_prims,
        "shadowPassActualDrawCalls":shadow_draws,
        "allPassesActualDrawCalls":total_calls,
        "allPassesActualPrimitives":total_prims
    }

func _go() -> void:
    var pol: Variant=JSON.parse_string(FileAccess.get_file_as_string(
        "res://nacht-exterior-visual-policy.json"))
    if not (pol is Dictionary) or int(pol.get("sourceActorCount",0))!=10793:
        push_error("XZOGOT_NACHT_REAL_RENDERER_EXTERIOR_POLICY_NOT_AUTHORITATIVE_RED")
        quit(2)
        return
    var scene: PackedScene=load("res://scenes/main.tscn") as PackedScene
    if scene==null:
        push_error("XZOGOT_NACHT_REAL_RENDERER_GODOT_LOSSLESS_GLTF_MISSING_RED")
        quit(3)
        return
    var w: Node=scene.instantiate()
    root.add_child(w)
    var nodes: Array[Node]=w.find_children("*","MeshInstance3D",true,false)
    if nodes.size()!=10793:
        push_error("XZOGOT_NACHT_REAL_RENDERER_SOURCE_ACTORS_DROPPED_RED")
        quit(4)
        return
    var by_id: Dictionary={}
    var original_meshes: Dictionary={}
    var world_origins: Dictionary={}
    for candidate: Node in nodes:
        var mi: MeshInstance3D=candidate as MeshInstance3D
        var label: String=str(mi.name)
        var part: int=label.find("_native_exact_")
        if part<0:
            push_error("XZOGOT_NACHT_REAL_RENDERER_ORIGINAL_SOURCE_ACTOR_NAME_MISSING_RED")
            quit(5)
            return
        var id: String=label.substr(0,part)
        if by_id.has(id):
            push_error("XZOGOT_NACHT_REAL_RENDERER_ACTOR_DUPLICATE_RED")
            quit(6)
            return
        by_id[id]=mi
        original_meshes[id]=mi.mesh
        world_origins[id]=mi.global_transform
    var cam: Camera3D=Camera3D.new()
    cam.name="ResearchSourceRendererCounterCamera"
    cam.far=900
    cam.fov=72
    cam.near=0.035
    root.add_child(cam)
    cam.current=true
    var views: Array[Dictionary]=[
        {"name":"exterior-night-overview","eye":Vector3(24.66175,37.85322,19.89849),
        "lookingAt":Vector3(-2.494789,3.153206,-7.258049)},
        {"name":"source-playable-spawn6-interior","eye":Vector3(11.61863,1.65,-0.325515),
        "lookingAt":Vector3(4.5,1.6,0.4)},
        {"name":"distant-woodland-diagnostic-not-playable-certification",
        "eye":Vector3(-80.0,8.0,-90.0),
        "lookingAt":Vector3(-2.494789,3.153206,-7.258049)}
    ]
    var before: Array[Dictionary]=[]
    for v: Dictionary in views:
        var m: Dictionary=await _collect(cam,v["eye"],v["lookingAt"])
        m["view"]=v["name"]
        before.append(m)
        print("XZOGOT_NACHT_SOURCE_REAL_GODOT_MESA_DRAW_CALLS_BEFORE",JSON.stringify(m))
    var control_script: Script=load("res://nacht_apply_source_exterior_visual_lod.gd") as Script
    if control_script==null:
        push_error("XZOGOT_NACHT_REAL_RENDERER_SOURCE_AABB_CONTROLLER_MISSING_RED")
        quit(7)
        return
    var opt: RefCounted=control_script.new() as RefCounted
    var applied: Dictionary=opt.call("apply_to_real_source_meshes",pol,by_id) as Dictionary
    if (not (applied.get("errors",[]) as Array).is_empty() or
        int(applied.get("actualFarExteriorGodotActorsOptimized",0))<400 or
        int(applied.get("nearBuildingOriginalActorsProtected",0))<10000):
        push_error("XZOGOT_NACHT_REAL_RENDERER_PLAY_REGION_OR_ORIGINAL_ACTORS_CHANGED_RED "+
            JSON.stringify(applied))
        quit(8)
        return
    var after: Array[Dictionary]=[]
    for v: Dictionary in views:
        var m: Dictionary=await _collect(cam,v["eye"],v["lookingAt"])
        m["view"]=v["name"]
        after.append(m)
        print("XZOGOT_NACHT_SOURCE_REAL_GODOT_MESA_DRAW_CALLS_AFTER",JSON.stringify(m))

    var comparison: Array[Dictionary]=[]
    var checks: Array[String]=[]
    for i: int in range(views.size()):
        var a: Dictionary=before[i]
        var b: Dictionary=after[i]
        if int(a["visiblePassRealDrawCalls"])<=0 or int(b["visiblePassRealDrawCalls"])<=0:
            checks.append("renderer returned no real draw calls in "+str(views[i]["name"]))
        if int(a["visiblePassActualRenderedPrimitives"])<=0:
            checks.append("renderer returned no original geometry primitives in "+str(views[i]["name"]))
        comparison.append({
            "viewName":views[i]["name"],
            "baselineActualGodotRenderer":a,
            "farOnlyLODActualGodotRenderer":b,
            "visibleDrawCallDifferenceCount":int(b["visiblePassRealDrawCalls"])-int(a["visiblePassRealDrawCalls"]),
            "visiblePrimitiveCountDifference":int(b["visiblePassActualRenderedPrimitives"])-int(a["visiblePassActualRenderedPrimitives"]),
            "shadowDrawCallDifferenceCount":int(b["shadowPassActualDrawCalls"])-int(a["shadowPassActualDrawCalls"]),
            "notARealAndroidFrameTime":true
        })
        print("XZOGOT_NACHT_REAL_MESA_GEOMETRY_ONLY_DRAW_CALL_AB",JSON.stringify(comparison[-1]))
    for id_var: Variant in by_id:
        var iid: String=str(id_var)
        var mi: MeshInstance3D=by_id[iid] as MeshInstance3D
        if mi.mesh!=original_meshes[iid] or mi.global_transform!=world_origins[iid]:
            checks.append("native source actor or mesh modified "+iid)
            break
    var result: Dictionary={
        "renderEngine":Engine.get_version_info().get("string",""),
        "renderer":"Godot 4.6.1 gl_compatibility real Mesa OpenGL Xvfb",
        "whatIsAbsent":"Original DDS/material shader graph not staged in this isolated GPU render geometry benchmark",
        "source":"archived Pavlov UE4.21 reconstruction, NOT original BO3 T7",
        "originalMeshNodes":by_id.size(),
        "actualGodotSourceActorVisualController":applied,
        "beforeAfterDrawAndPrimitiveCounts":comparison,
        "measuredRenderingServerNotEstimated":true,
        "runningOnActualAndroidHardware":false,
        "measuredFramesPerSecondOnPhysicalPhone":false,
        "geometryLODTriangleSimplificationMeasured":false,
        "allViewPositionsProvenPlayerReachable":false,
        "errors":checks
    }
    var file: FileAccess=FileAccess.open("res://nacht-real-mesa-source-far-lod-renderer-counters.json",FileAccess.WRITE)
    file.store_string(JSON.stringify(result,"\t"))
    file.close()
    w.queue_free()
    cam.queue_free()
    if not checks.is_empty():
        push_error("XZOGOT_NACHT_REAL_RENDERER_PHYSICAL_GL_NOT_DRAWING_SOURCE_RED "+
            JSON.stringify(result))
        quit(9)
        return
    print("XZOGOT_NACHT_REAL_MESA_3_VIEWS_SOURCE_FAR_LOD_RENDERINGSERVER_COUNTERS_GREEN",
        " actors=10793 measured_true_GL_draws=3",
        " original_GLB_and_near_scene_intact=true",
        " native_Android_FPS_proven=false")
    quit(0)
