extends RefCounted
## RESEARCH: make ONLY 26 original hard-architecture source materials opaque.
## Never touch foliage, translucent/glass, decals or other 548 materials.
## No original resource mutation; strict two-pass validation + full rollback.

var _saved: Array[Dictionary]=[]
var _applied: bool=false
var _clones: Dictionary={}

func apply_source_architecture_opaque_research(
        policy: Dictionary,authority: Dictionary,by_actor: Dictionary) -> Dictionary:
    var errors: Array[String]=[]
    if _applied or not _saved.is_empty():
        return {"errors":["research architecture override already active"]}
    if (int(policy.get("originalActorCount",-1))!=10793
        or int(policy.get("hardArchitecturalCandidateMaterials",-1))!=26
        or int(policy.get("hardArchitecturalSourceBindings",-1))!=1262
        or bool(policy.get("productionEnabled",true))
        or int(authority.get("sourceActorCount",-1))!=10793
        or int(authority.get("originalSourceSurfaceBindings",-1))!=16595
        or by_actor.size()!=10793):
        return {"errors":["original source actor/architecture policy counts mismatch"]}
    var permitted: Dictionary={}
    for candidate_any: Variant in policy.get("candidates",[]):
        var candidate: Dictionary=candidate_any as Dictionary
        var path: String=str(candidate.get("materialPath",""))
        if permitted.has(path) or not path.contains("/CoD_nacht/materials/"):
            return {"errors":["invalid or duplicate original architecture material path"]}
        permitted[path]=true
    if permitted.size()!=26:
        return {"errors":["exact 26 original material names required"]}
    var stage: Array[Dictionary]=[]
    var observed_bindings: int=0
    var target_bindings: int=0
    for actor_any: Variant in authority.get("actors",[]):
        var row: Dictionary=actor_any as Dictionary
        var id: String=str(row.get("actorId",""))
        var mi: MeshInstance3D=by_actor.get(id,null) as MeshInstance3D
        if mi==null or mi.mesh==null:
            errors.append("source actor missing "+id)
            break
        var paths: Array=row.get("sourceMaterialPaths",[]) as Array
        if mi.mesh.get_surface_count()!=paths.size():
            errors.append("source exact mesh surface count changed "+id)
            break
        observed_bindings+=paths.size()
        for index: int in range(paths.size()):
            var path: String=str(paths[index])
            if not permitted.has(path):
                continue
            var original: StandardMaterial3D=mi.get_surface_override_material(index) as StandardMaterial3D
            if original==null or original.albedo_texture==null or original.transparency!=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                errors.append("candidate original texture/mask unavailable "+id+" "+path)
                break
            target_bindings+=1
            stage.append({"node":mi,"surface":index,"original":original,
                          "materialPath":path})
        if not errors.is_empty():
            break
    if observed_bindings!=16595 or target_bindings!=1262 or stage.size()!=1262:
        errors.append("original material-stage binding count changed "+
            str([observed_bindings,target_bindings,stage.size()]))
    if not errors.is_empty():
        return {"errors":errors,"sourceMaterialsChanged":0}
    # Only after every original mesh/material guard passed, modify research
    # per-instance overrides. Never call change on cached original resources.
    for entry: Dictionary in stage:
        var original: StandardMaterial3D=entry["original"] as StandardMaterial3D
        var key: int=original.get_instance_id()
        if not _clones.has(key):
            var clone: StandardMaterial3D=original.duplicate(false) as StandardMaterial3D
            clone.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
            if (clone.albedo_texture!=original.albedo_texture
                or clone.normal_texture!=original.normal_texture
                or clone.cull_mode!=original.cull_mode):
                return {"errors":["cloned candidate accidentally changed original DDS/normal or backface policy"]}
            _clones[key]=clone
        (entry["node"] as MeshInstance3D).set_surface_override_material(
            int(entry["surface"]),_clones[key] as Material)
    _saved=stage
    _applied=true
    return {
        "errors":[],
        "sourceOriginalActorsStillPresent":by_actor.size(),
        "originalSourceBindingsCount":observed_bindings,
        "architecturalSourceMaterialsChanged":permitted.size(),
        "architecturalSourceSurfaceOverridesChanged":target_bindings,
        "allOtherOriginalMaterialsAndTransparentTypesUntouched":true,
        "originalDDSNormalAndCullResourcesPreserved":true,
        "originalMeshOrCollidersDeleted":0,
        "shippedToProduction":false
    }

func restore_original_source_architecture() -> Dictionary:
    if not _applied or _saved.size()!=1262:
        return {"errors":["no complete active 1262-surface architecture research override"]}
    for entry: Dictionary in _saved:
        var node: MeshInstance3D=entry["node"] as MeshInstance3D
        var index: int=int(entry["surface"])
        node.set_surface_override_material(index,entry["original"] as Material)
        if node.get_surface_override_material(index)!=entry["original"]:
            return {"errors":["original source material pointer restoration failed"]}
    var restored: int=_saved.size()
    _saved.clear()
    _clones.clear()
    _applied=false
    return {"errors":[],"exactOriginalSurfacePointersRestored":restored,
            "originalSourceNodesDeleted":0,
            "reversibleResearchOnly":true}
