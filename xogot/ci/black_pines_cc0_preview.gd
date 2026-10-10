extends SceneTree
## Independent REAL Godot visual audition for 16 individually CC0-licensed GLBs.
## Downloads are staged by CI only: NONE are silently added to the original
## playable Black Pines map or a public APK. Never generate fake screenshots.
const MANIFEST: String="res://assets/black_pines/free_cc0_staging/cc0-intake-evidence.json"
const ROOT: String="res://assets/black_pines/free_cc0_staging/"
var _staged: Node3D
var _eye: Camera3D

func _init() -> void:
    call_deferred("_run")

func _require(ok: bool,why: String) -> bool:
    if ok:
        return true
    push_error("BLACK_PINES_FREE_CC0_PREVIEW_RED "+why)
    quit(82)
    return false

func _stage() -> void:
    _staged=Node3D.new()
    _staged.name="CC0ArtReviewOnlyNotInGame"
    root.add_child(_staged)
    var env:=WorldEnvironment.new()
    var atmosphere:=Environment.new()
    atmosphere.background_mode=Environment.BG_COLOR
    atmosphere.background_color=Color(0.065,0.075,0.090)
    atmosphere.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
    atmosphere.ambient_light_color=Color(0.58,0.62,0.65)
    atmosphere.ambient_light_energy=1.15
    env.environment=atmosphere
    _staged.add_child(env)
    var sunlight:=DirectionalLight3D.new()
    sunlight.rotation_degrees=Vector3(-47,-30,0)
    sunlight.light_color=Color(1.0,0.95,0.82)
    sunlight.light_energy=1.45
    sunlight.shadow_enabled=false
    _staged.add_child(sunlight)
    var light:=OmniLight3D.new()
    light.position=Vector3(-2.0,3.7,2.0)
    light.light_energy=1.3
    light.omni_range=18.0
    light.shadow_enabled=false
    _staged.add_child(light)
    var base:=MeshInstance3D.new()
    base.name="ReviewStageFloorNotSourceArtwork"
    var mesh:=BoxMesh.new()
    mesh.size=Vector3(25,.12,25)
    var mat:=StandardMaterial3D.new()
    mat.albedo_color=Color(.16,.18,.20)
    mat.roughness=.87
    mesh.material=mat
    base.mesh=mesh
    base.position=Vector3(0,-.085,0)
    _staged.add_child(base)
    _eye=Camera3D.new()
    _eye.name="TrueGodotFreeAssetPreviewCamera"
    _eye.fov=52.0
    _eye.near=.04
    _eye.far=130.0
    _staged.add_child(_eye)
    _eye.current=true

func _run() -> void:
    var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
    if not _require(raw is Dictionary,"licensed audit manifest not found"):
        return
    var report: Dictionary=raw as Dictionary
    if not _require(str(report.get("packLicense",""))=="CC0 1.0 Universal"
            and str(report.get("stage",""))=="REVIEW_ONLY_NOT_SHIPPED"
            and int(report.get("assetCount",0))==16,
            "staged source license or 16-model count invalid"):
        return
    _stage()
    await process_frame
    var labels: Dictionary={}
    var count: int=0
    var mesh_total: int=0
    for item: Dictionary in report["assets"]:
        var key: String=str(item.get("label",""))
        if not _require(not labels.has(key) and not key.is_empty()
                and str(item.get("license",""))=="CC0 1.0 Universal"
                and bool(item.get("notIncludedInProductionAPK",false)),
                "duplicate, non-CC0, or unapproved shipping candidate "+key):
            return
        labels[key]=true
        var path: String=ROOT+str(item["filename"])
        if not _require(ResourceLoader.exists(path),"Godot did not import "+path):
            return
        var packed: PackedScene=load(path) as PackedScene
        if not _require(packed!=null,"GLB did not become Godot scene "+key):
            return
        var object: Node3D=packed.instantiate() as Node3D
        if not _require(object!=null,"source object not Node3D "+key):
            return
        object.name="FreeCC0Candidate_"+key
        _staged.add_child(object)
        var children: Array[Node]=object.find_children("*","MeshInstance3D",true,false)
        if not _require(not children.is_empty(),"zero Godot meshes "+key):
            return
        mesh_total+=children.size()
        # The staged package records the source metres: camera distance is
        # adapted to 1m furniture AND the 7m-wide ambulance alike.
        var sz: Array=item.get("sizeMeters",[1.5,1.5,1.5]) as Array
        var width: float=maxf(1.0,float(sz[0]))
        var height: float=maxf(.5,float(sz[1]))
        var depth: float=maxf(1.0,float(sz[2]))
        var radius: float=maxf(width,depth)*1.90+1.2
        var target:=Vector3(0,maxf(.40,height*.48),0)
        _eye.global_position=Vector3(radius*.70,
            height*.72+radius*.20+1.0,radius)
        _eye.look_at(target)
        for n in range(11):
            await process_frame
        var frame: Image=root.get_texture().get_image()
        var outfile: String=ProjectSettings.globalize_path(
            "res://cc0-staging-"+key+".png")
        if not _require(frame!=null and frame.get_width()>=900
                and frame.get_height()>=600 and frame.save_png(outfile)==OK,
                "real Godot screenshot missing "+key):
            return
        print("BLACK_PINES_CC0_REAL_GODOT_ASSET_GREEN",key,
              " meshes=",children.size()," source_triangle_count=",
              (item["stats"] as Dictionary).get("triangles",-1))
        count+=1
        object.queue_free()
        await process_frame
    if not _require(count==16 and mesh_total>=16,"not all CC0 meshes imported"):
        return
    print("BLACK_PINES_CC0_16_REAL_GODOT_PREVIEWS_GREEN",
          " samples=16 real_assets=true source_licence=CC0",
          " mounted_game_map=false android_fps_not_certified=true")
    _staged.queue_free()
    await process_frame
    quit(0)
