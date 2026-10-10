extends RefCounted
## Research-only reversible spatial Vista renderer rollback.
## Operates ONLY on source actors in the verified authored 340-actor Vista
## list and the research-generated MultiMesh subtree, not on production assets.

func restore_original_vista_multimesh(vista: Dictionary, by_actor: Dictionary,
        research_parent: Node3D) -> Dictionary:
    var errors: Array[String]=[]
    if (int(vista.get("originalSourceActors",-1))!=10793
        or (vista.get("actorDetails",[]) as Array).size()!=340
        or by_actor.size()!=10793 or research_parent==null):
        return {"errors":["original source 10793 actor / 340 Vista authority missing"]}
    var batch_root: Node3D=research_parent.get_node_or_null(
        "NONSHIPPING_OriginalVistaSpatialMultimesh") as Node3D
    if batch_root==null:
        return {"errors":["no original-source research batch subtree to reverse"]}
    var grouped: Array[Node]=batch_root.find_children(
        "*","MultiMeshInstance3D",true,false)
    if grouped.size()<10:
        return {"errors":["original Vista research group count unexpectedly small"]}
    var source_ids: Dictionary={}
    var hidden_originals: Array[MeshInstance3D]=[]
    for row_any: Variant in vista["actorDetails"]:
        var row: Dictionary=row_any as Dictionary
        var source_id: String=str(row["originalActorID"])
        if source_ids.has(source_id) or not by_actor.has(source_id):
            errors.append("missing or duplicate original Vista source ID "+source_id)
            break
        source_ids[source_id]=true
        var mi: MeshInstance3D=by_actor[source_id] as MeshInstance3D
        if mi==null or mi.mesh==null:
            errors.append("original native GLB actor not retained "+source_id)
            break
        if not mi.visible:
            hidden_originals.append(mi)
    if (not errors.is_empty() or source_ids.size()!=340
        or hidden_originals.size()<100):
        return {"errors":errors if not errors.is_empty()
                else ["no proven original 340 Vista batch to roll back"],
                "originalSourceActorsDeleted":0}
    # Disable the replacement BEFORE reinstating the original source meshes.
    # The queue_free() is deferred; visibility=false makes duplicate renders
    # impossible even when rendering occurs before SceneTree flushes frees.
    batch_root.visible=false
    for mi: MeshInstance3D in hidden_originals:
        mi.visible=true
    batch_root.queue_free()
    return {
        "errors":[],
        "originalSourceActorsStillPresent":by_actor.size(),
        "originalVistaActorIDsVerified":source_ids.size(),
        "originalSourceActorsRestored":hidden_originals.size(),
        "originalActorsDeleted":0,
        "originalMeshGeometryOrMatricesMutated":false,
        "originalCollisionNavigationMutated":false,
        "originalVistasRemainingIntentionallyIndividual":340-hidden_originals.size(),
        "researchBatchDetachedAndQueuedForDeletionOfREPLACEMENTONLY":true,
        "androidFPSOrPlayable360Proven":false,
        "approvedForShipping":false
    }
