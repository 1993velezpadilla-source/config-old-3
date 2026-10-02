#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gltf_audit import audit_glb
from mesh_doctor import audit_mesh as audit_mesh_structure
from qa import inspect_mesh
from reference_pool import infer_detail_region_hint


@dataclass
class QAPackageResult:
    report: str
    contact_sheet: str | None
    turntable_report: str | None
    turntable_contact_sheet: str | None
    part_map: str | None
    geometry_ready: bool
    material_ready: bool
    texture_resolution_ready: bool
    texture_resolution_score: float | None
    base_color_min_edge: int
    base_color_max_edge: int
    target_texture_size: int | None
    material_rebake_ready: bool
    material_rebaked_channels: list[str]
    material_rebake_pending_channels: list[str]
    rig_ready: bool
    morph_target_count: int
    morph_ready: bool
    morph_deformation_applicable: bool
    morph_deformation_ready: bool
    morph_deformation_poses: int
    morph_deformation_max_displacement_ratio: float | None
    animation_ready: bool
    animation_integrity_ready: bool
    animation_channels: int
    animation_keyframes: int
    deformation_applicable: bool
    deformation_ready: bool
    deformation_frames: int
    deformation_max_displacement_ratio: float | None
    deformation_max_edge_stretch_ratio: float | None
    skin_weights_applicable: bool
    skin_weights_ready: bool
    component_crossing_applicable: bool
    component_crossing_ready: bool
    component_crossing_pairs: int
    self_intersection_applicable: bool
    self_intersection_ready: bool
    self_intersection_pairs: int
    uv_tangent_applicable: bool
    uv_tangent_ready: bool
    uv_missing_primitives: int
    uv_degenerate_triangles: int
    shading_basis_applicable: bool
    shading_basis_ready: bool
    shading_missing_normals: int
    shading_missing_tangents: int
    shading_invalid_handedness: int
    shading_nonorthogonal_tangents: int
    collision_ready: bool
    collision_faces: int
    collision_convexity_ratio: float | None
    collision_bbox_coverage_ready: bool
    composite_attachment_applicable: bool
    composite_attachment_ready: bool
    composite_attachment_components: int
    composite_attachment_accessories: int
    composite_attachment_floating: int
    composite_attachment_oversized_floating: int
    turntable_ready: bool
    turntable_score: float | None
    face_evidence_ready: bool
    face_evidence_score: float | None
    face_evidence_expected: int
    face_evidence_evaluated: int
    face_evidence_missing: list[str]
    face_evidence_min_score: float | None
    face_quality_evidence_ready: bool
    face_quality_evidence_missing: list[str]
    anatomy_evidence_ready: bool
    anatomy_evidence_expected: int
    anatomy_evidence_evaluated: int
    anatomy_evidence_missing: list[str]
    head_density_score: float | None
    head_texel_density_score: float | None
    head_texture_detail_score: float | None
    production_ready: bool
    warnings: list[str]


def _champion_dict(champion: Any) -> dict:
    if isinstance(champion, dict):
        return dict(champion)
    try:
        return asdict(champion)
    except Exception:
        return {}


def unresolved_material_rebakes(gameprep_data: dict | None) -> list[dict]:
    unresolved: list[dict] = []
    for lod in (gameprep_data or {}).get("lods", []) or []:
        channels = sorted({str(x) for x in (lod.get("rebake_required") or []) if x})
        if channels:
            unresolved.append({
                "lod": str(lod.get("name") or lod.get("path") or "unknown"),
                "channels": channels,
            })
    return unresolved


def material_rebake_channel_summary(gameprep_data: dict | None) -> tuple[list[str], list[str]]:
    resolved:set[str]=set()
    pending:set[str]=set()
    for lod in (gameprep_data or {}).get("lods", []) or []:
        resolved.update(str(x) for x in (lod.get("rebaked_channels") or []) if x)
        pending.update(str(x) for x in (lod.get("rebake_required") or []) if x)
    # A channel still pending on any runtime LOD is not globally complete.
    return sorted(resolved-pending),sorted(pending)


def face_reference_evidence(
    detail_images: list[Path],
    champion_data: dict,
) -> tuple[list[Path], int, int, list[str], float | None, float | None, bool]:
    """Require complete Judge coverage for every explicit face reference.

    This intentionally does not invent a visual-quality threshold. It only
    guarantees that a production-ready character cannot claim face evidence
    from an aggregate score while silently skipping one or more supplied face
    close-ups.
    """
    refs=[
        p for p in detail_images
        if infer_detail_region_hint(p)=="head"
    ]
    expected=len(refs)
    if not refs:
        return refs,0,0,[],None,None,True

    raw_score=champion_data.get("appearance_face_detail_score")
    aggregate_score=None
    try:
        value=float(raw_score)
        if math.isfinite(value):
            aggregate_score=value
    except (TypeError,ValueError):
        aggregate_score=None

    candidates=[]
    for item in champion_data.get("appearance_details") or []:
        if not isinstance(item,dict):
            continue
        source=str(item.get("source") or "")
        if not source:
            continue
        region=item.get("region_hint")
        if region is None:
            try:
                region=infer_detail_region_hint(Path(source))
            except Exception:
                region=None
        if region!="head":
            continue
        try:
            score=float(item.get("score"))
        except (TypeError,ValueError):
            continue
        if not math.isfinite(score):
            continue
        candidates.append((source,score))

    consumed=set()
    missing=[]
    evaluated=0
    matched_scores=[]
    for ref in refs:
        ref_text=str(ref)
        match_index=None
        for index,(source,score) in enumerate(candidates):
            if index in consumed:
                continue
            if source==ref_text or Path(source).name==ref.name:
                match_index=index
                break
        if match_index is None:
            missing.append(ref_text)
        else:
            consumed.add(match_index)
            evaluated+=1
            matched_scores.append(float(candidates[match_index][1]))

    min_score=min(matched_scores) if matched_scores else None
    ready=bool(
        aggregate_score is not None
        and evaluated==expected
        and not missing
    )
    return refs,expected,evaluated,missing,aggregate_score,min_score,ready


def _finite_metric(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def face_quality_evidence_chain(
    *,
    required: bool,
    identity_required: bool | None = None,
    face_min_score: float | None,
    head_density_score: float | None,
    head_texel_density_score: float | None,
    head_texture_detail_score: float | None,
) -> tuple[bool, list[str]]:
    """Require complete facial QA evidence without inventing quality thresholds.

    When explicit face references exist, production-ready status needs evidence
    for identity, local geometry density, face texel allocation and visible
    texture detail. Numeric acceptance floors stay separate until they are
    calibrated from a larger real-asset corpus.
    """
    if not required:
        return True, []
    if identity_required is None:
        identity_required=required

    metrics={
        "head_density_score":head_density_score,
        "head_texel_density_score":head_texel_density_score,
        "head_texture_detail_score":head_texture_detail_score,
    }
    if identity_required:
        metrics["identity_min_score"]=face_min_score
    missing=[
        name
        for name,value in metrics.items()
        if not _finite_metric(value)
    ]
    return not missing,missing


def _thumbnail(path: Path, size: tuple[int, int]):
    from PIL import Image, ImageOps

    image = Image.open(path).convert("RGB")
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)


def build_contact_sheet(
    *,
    source_images: list[Path],
    turntable_frames: list[Path],
    output: Path,
) -> Path | None:
    from PIL import Image, ImageDraw

    sources = [p for p in source_images if p.is_file()][:8]
    turns = [p for p in turntable_frames if p.is_file()][:12]
    if not sources and not turns:
        return None

    cell = (240, 240)
    columns = 4
    items: list[tuple[str, Path]] = [
        *[(f"SOURCE {i + 1}", p) for i, p in enumerate(sources)],
        *[(
            f"TURN {((i * 15) % 360):03d}",
            p,
        ) for i, p in enumerate(turns)],
    ]
    rows = (len(items) + columns - 1) // columns
    header = 30
    sheet = Image.new("RGB", (columns * cell[0], rows * (cell[1] + header)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)

    for index, (label, path) in enumerate(items):
        col = index % columns
        row = index // columns
        x = col * cell[0]
        y = row * (cell[1] + header)
        thumb = _thumbnail(path, cell)
        sheet.paste(thumb, (x, y + header))
        draw.text((x + 8, y + 7), label, fill=(235, 235, 235))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG")
    return output


def build_qa_package(
    final_glb: Path,
    out_dir: Path,
    *,
    champion: Any,
    mode: str,
    profile: str,
    source_images: list[Path],
    detail_images: list[Path],
    gameprep: Any = None,
    target_faces: int,
    target_texture_size: int | None = None,
) -> QAPackageResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    champion_data = _champion_dict(champion)
    mesh = inspect_mesh(
        final_glb,
        backend=str(champion_data.get("backend", "final")),
        mode=mode,
        target_faces=target_faces,
        target_texture_size=target_texture_size,
    )
    rig = audit_glb(final_glb)
    structure = audit_mesh_structure(final_glb)

    gameprep_data = asdict(gameprep) if gameprep is not None else None

    part_map_result = None
    part_map_path = None
    try:
        from part_map import build_part_map, write_part_map

        visual_views_for_axis = champion_data.get("visual_views") or []
        recovered_up_axis = (
            visual_views_for_axis[0].get("best_up_axis", "y")
            if visual_views_for_axis
            else "y"
        )
        part_map_result = build_part_map(
            final_glb,
            mode=mode,
            up_axis=recovered_up_axis,
        )
        part_map_path = write_part_map(
            part_map_result,
            out_dir / "part_map.json",
        )
    except Exception:
        part_map_result = None
        part_map_path = None

    lods = (gameprep_data or {}).get("lods", [])
    turntable = [Path(p) for p in (gameprep_data or {}).get("turntable_frames", [])]
    collision = (gameprep_data or {}).get("collision")

    warnings: list[str] = []
    warnings.extend(mesh.notes or [])
    warnings.extend(rig.warnings)
    warnings.extend(rig.errors)
    if part_map_result is not None and part_map_result.accessory_component_ids:
        warnings.append(
            "Part Map identified preserved accessory-candidate components: "
            + ",".join(str(x) for x in part_map_result.accessory_component_ids)
        )

    unresolved_structural_defects = bool(
        not structure.valid
        or not structure.finite_vertices
        or structure.duplicate_faces > 0
        or structure.degenerate_faces > 0
        or structure.nonmanifold_edges > 0
        or not structure.winding_consistent
    )

    geometry_ready = bool(
        mesh.valid
        and mesh.faces >= 50
        and mesh.degenerate_ratio <= 0.02
        and mesh.bbox
        and all(x > 1e-9 for x in mesh.bbox)
        and not unresolved_structural_defects
    )

    if unresolved_structural_defects:
        warnings.append(
            "Mesh Doctor reports unresolved structural defects; production-ready geometry is false"
        )
    if structure.boundary_edges > 0 and not structure.watertight:
        warnings.append(
            f"open boundary edges remain: {structure.boundary_edges} "
            "(warning only; may be intentional open geometry)"
        )
    if structure.tiny_components > 0:
        warnings.append(
            f"tiny disconnected components retained intentionally: {structure.tiny_components}"
        )

    component_crossing_audit = None
    component_crossing_applicable = False
    component_crossing_ready = False
    component_crossing_pairs = 0
    try:
        from component_crossing_qa import audit_component_crossings
        component_crossing_audit = audit_component_crossings(final_glb)
        component_crossing_applicable = bool(
            component_crossing_audit.applicable
        )
        component_crossing_ready = bool(
            component_crossing_audit.ready
        )
        component_crossing_pairs = int(
            component_crossing_audit.crossing_triangle_pairs
        )
        warnings.extend(component_crossing_audit.warnings or [])
        warnings.extend(component_crossing_audit.errors or [])
    except Exception as exc:
        component_crossing_ready = False
        warnings.append(
            "component surface-crossing QA unavailable: "
            f"{type(exc).__name__}: {exc}"
        )
    if not component_crossing_ready:
        warnings.append(
            "large-component surface-crossing QA failed; "
            "interpenetrating major surfaces block production-ready status"
        )

    self_intersection_audit = None
    self_intersection_applicable = False
    self_intersection_ready = False
    self_intersection_pairs = 0
    try:
        from self_intersection_qa import audit_self_intersections
        self_intersection_audit = audit_self_intersections(final_glb)
        self_intersection_applicable = bool(
            self_intersection_audit.applicable
        )
        self_intersection_ready = bool(
            self_intersection_audit.ready
        )
        self_intersection_pairs = int(
            self_intersection_audit.crossing_triangle_pairs
        )
        warnings.extend(self_intersection_audit.warnings or [])
        warnings.extend(self_intersection_audit.errors or [])
    except Exception as exc:
        self_intersection_ready = False
        warnings.append(
            "self-intersection QA unavailable: "
            f"{type(exc).__name__}: {exc}"
        )
    if not self_intersection_ready:
        warnings.append(
            "intra-component self-intersection QA failed; "
            "connected surfaces crossing through themselves block "
            "production-ready status"
        )

    uv_tangent_audit = None
    uv_tangent_applicable = False
    uv_tangent_ready = False
    uv_missing_primitives = 0
    uv_degenerate_triangles = 0
    try:
        from uv_tangent_qa import audit_uv_tangents
        uv_tangent_audit = audit_uv_tangents(final_glb)
        uv_tangent_applicable = bool(uv_tangent_audit.applicable)
        uv_tangent_ready = bool(uv_tangent_audit.ready)
        uv_missing_primitives = int(
            uv_tangent_audit.missing_uv_primitives
        )
        uv_degenerate_triangles = int(
            uv_tangent_audit.degenerate_uv_triangles
        )
        warnings.extend(uv_tangent_audit.warnings or [])
        warnings.extend(uv_tangent_audit.errors or [])
    except Exception as exc:
        uv_tangent_ready = False
        warnings.append(
            "UV/tangent mapping QA unavailable: "
            f"{type(exc).__name__}: {exc}"
        )
    if not uv_tangent_ready:
        warnings.append(
            "UV/tangent mapping QA failed; missing/collapsed UVs or "
            "an unusable normal-map tangent basis block production-ready status"
        )

    shading_basis_audit = None
    shading_basis_applicable = False
    shading_basis_ready = True
    shading_missing_normals = 0
    shading_missing_tangents = 0
    shading_invalid_handedness = 0
    shading_nonorthogonal_tangents = 0
    high_end_shading = profile in {"monster","ultra"}
    normal_mapped = "normal" in set(mesh.pbr_channels or [])
    shading_basis_required = bool(high_end_shading and normal_mapped)
    try:
        from shading_basis_qa import audit_shading_basis
        shading_basis_audit = audit_shading_basis(
            final_glb,
            require_explicit_tangents_for_normal_maps=high_end_shading,
        )
        shading_basis_applicable = bool(shading_basis_audit.applicable)
        shading_basis_ready = bool(shading_basis_audit.ready)
        shading_missing_normals = int(shading_basis_audit.missing_normals)
        shading_missing_tangents = int(
            shading_basis_audit.missing_required_tangents
        )
        shading_invalid_handedness = int(
            shading_basis_audit.invalid_handedness
        )
        shading_nonorthogonal_tangents = int(
            shading_basis_audit.nonorthogonal_tangents
        )
        warnings.extend(shading_basis_audit.warnings or [])
        if shading_basis_required:
            warnings.extend(shading_basis_audit.errors or [])
    except Exception as exc:
        if shading_basis_required:
            shading_basis_ready = False
        warnings.append(
            "shading-basis QA unavailable: "
            f"{type(exc).__name__}: {exc}"
        )
    if shading_basis_required and not shading_basis_ready:
        warnings.append(
            "high-end normal-mapped asset lacks a valid explicit "
            "normal/tangent basis; cross-renderer shading is not production-ready"
        )

    base_material_ready = bool(
        mesh.material_score >= 55.0
        or ("baseColor" in set(mesh.pbr_channels or []) and mesh.has_uv)
    )
    texture_resolution_ready = (
        True
        if target_texture_size is None
        else bool(
            mesh.base_color_min_edge
            and mesh.base_color_min_edge >= int(target_texture_size)
        )
    )
    material_ready = bool(base_material_ready and texture_resolution_ready)
    if base_material_ready and not texture_resolution_ready:
        warnings.append(
            f"weakest visible baseColor resolution {mesh.base_color_min_edge}px "
            f"(strongest {mesh.base_color_max_edge}px) is below profile target "
            f"{int(target_texture_size)}px; asset remains inspectable but is not production-ready"
        )

    rig_required = mode == "character"
    rig_ready = bool(rig.rig_ready)
    morph_target_count = int(rig.morph_target_count or 0)
    morph_ready = bool(rig.morph_ready)
    morph_required = bool(
        mode=="character"
        and morph_target_count>0
    )
    if morph_required and not morph_ready:
        warnings.append(
            "character morph/blendshape payload is malformed; "
            "expression-capable assets cannot be production-ready"
        )

    morph_deformation_audit = None
    morph_deformation_applicable = False
    morph_deformation_ready = not morph_required
    morph_deformation_poses = 0
    morph_deformation_max_displacement_ratio = None
    if morph_required and morph_ready:
        try:
            from morph_deformation_qa import audit_morph_deformation
            morph_deformation_audit = audit_morph_deformation(final_glb)
            morph_deformation_applicable = bool(
                morph_deformation_audit.applicable
            )
            morph_deformation_ready = bool(
                morph_deformation_audit.applicable
                and morph_deformation_audit.ready
            )
            morph_deformation_poses = int(
                morph_deformation_audit.sampled_poses
            )
            morph_deformation_max_displacement_ratio = float(
                morph_deformation_audit.max_displacement_ratio
            )
            warnings.extend(
                morph_deformation_audit.warnings or []
            )
            warnings.extend(
                morph_deformation_audit.errors or []
            )
        except Exception as exc:
            morph_deformation_ready = False
            warnings.append(
                "morph-deformation QA unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
    if morph_required and morph_ready and not morph_deformation_ready:
        warnings.append(
            "morph/blendshape wiring is valid but sampled morph deformation "
            "failed; expression-capable character is not production-ready"
        )

    embedded_animation_ready = bool(rig.animation_ready)

    animation_audit = None
    animation_integrity_ready = False
    animation_channels = 0
    animation_keyframes = 0
    if rig_required and rig_ready and embedded_animation_ready:
        try:
            from animation_qa import audit_animation
            animation_audit = audit_animation(final_glb)
            animation_integrity_ready = bool(
                animation_audit.applicable
                and animation_audit.ready
            )
            animation_channels = int(animation_audit.channel_count)
            animation_keyframes = int(animation_audit.total_keyframes)
            warnings.extend(animation_audit.warnings or [])
            warnings.extend(animation_audit.errors or [])
        except Exception as exc:
            warnings.append(
                "animation QA unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
    animation_ready = bool(
        embedded_animation_ready
        and animation_integrity_ready
    )

    skin_weight_audit = None
    skin_weights_applicable = False
    skin_weights_ready = False
    if rig_required and rig_ready:
        try:
            from skin_weight_qa import audit_skin_weights
            skin_weight_audit = audit_skin_weights(final_glb)
            skin_weights_applicable = bool(skin_weight_audit.applicable)
            skin_weights_ready = bool(
                skin_weight_audit.applicable
                and skin_weight_audit.ready
            )
            warnings.extend(skin_weight_audit.warnings or [])
            warnings.extend(skin_weight_audit.errors or [])
        except Exception as exc:
            warnings.append(
                "skin-weight QA unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
    if rig_required and rig_ready and not skin_weights_ready:
        warnings.append(
            "rig exists but JOINTS/WEIGHTS integrity is not production-ready; "
            "skin-weight QA must pass before character production-ready status"
        )

    deformation_audit = None
    deformation_applicable = False
    deformation_ready = False
    deformation_frames = 0
    deformation_max_displacement_ratio = None
    deformation_max_edge_stretch_ratio = None
    if (
        rig_required
        and rig_ready
        and skin_weights_ready
        and animation_integrity_ready
    ):
        try:
            from deformation_qa import audit_deformation
            deformation_audit = audit_deformation(final_glb)
            deformation_applicable = bool(deformation_audit.applicable)
            deformation_ready = bool(
                deformation_audit.applicable
                and deformation_audit.ready
            )
            deformation_frames = int(deformation_audit.sampled_frames)
            deformation_max_displacement_ratio = float(
                deformation_audit.max_displacement_ratio
            )
            deformation_max_edge_stretch_ratio = float(
                deformation_audit.max_edge_stretch_ratio
            )
            warnings.extend(deformation_audit.warnings or [])
            warnings.extend(deformation_audit.errors or [])
        except Exception as exc:
            warnings.append(
                "deformation QA unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
    if (
        rig_required
        and rig_ready
        and skin_weights_ready
        and animation_integrity_ready
        and not deformation_ready
    ):
        warnings.append(
            "rig/weights/animation metadata are valid but sampled Deformation QA "
            "failed; character production-ready status is false"
        )

    if rig_required and not rig_ready:
        warnings.append(
            "character asset is geometrically usable but unrigged; animation/gameplay-ready status is false"
        )
    if rig_ready and not embedded_animation_ready:
        warnings.append(
            "rig is valid but no glTF animation clips are embedded; character production-ready status is false"
        )
    elif rig_required and rig_ready and embedded_animation_ready and not animation_integrity_ready:
        warnings.append(
            "animation clips are embedded but Animation QA failed; "
            "timestamps/samples/rotations/channels must pass before "
            "character production-ready status"
        )
    if mode != "character" and not rig_ready:
        pass

    expected_sources = len(source_images)
    judged_views = champion_data.get("visual_views") or []
    source_coverage = len(judged_views)

    if expected_sources and source_coverage < expected_sources:
        warnings.append(
            f"Judge source coverage {source_coverage}/{expected_sources}; not every geometry reference has a recorded visual view"
        )

    (
        face_detail_refs,
        face_evidence_expected,
        face_evidence_evaluated,
        face_evidence_missing,
        face_evidence_score,
        face_evidence_min_score,
        face_evidence_ready,
    )=face_reference_evidence(detail_images,champion_data)
    face_evidence_required=bool(face_detail_refs)

    from anatomy_reference import critical_anatomy_evidence
    anatomy_evidence=critical_anatomy_evidence(
        detail_images,
        champion_data.get("appearance_details") or [],
    )
    anatomy_evidence_ready=bool(anatomy_evidence.ready)
    anatomy_evidence_expected=int(anatomy_evidence.expected)
    anatomy_evidence_evaluated=int(anatomy_evidence.evaluated)
    anatomy_evidence_missing=list(anatomy_evidence.missing)
    if (
        mode=="character"
        and anatomy_evidence.required
        and not anatomy_evidence_ready
    ):
        warnings.append(
            "critical anatomy reference coverage incomplete: "
            f"{anatomy_evidence_evaluated}/{anatomy_evidence_expected} evaluated; "
            +"missing="+",".join(anatomy_evidence_missing)
        )
    (
        face_quality_evidence_ready,
        face_quality_evidence_missing,
    )=face_quality_evidence_chain(
        required=(mode=="character"),
        identity_required=face_evidence_required,
        face_min_score=face_evidence_min_score,
        head_density_score=mesh.head_density_score,
        head_texel_density_score=mesh.head_texel_density_score,
        head_texture_detail_score=mesh.head_texture_detail_score,
    )
    if mode=="character" and not face_quality_evidence_ready:
        warnings.append(
            "character face-quality evidence chain incomplete: "
            + ",".join(face_quality_evidence_missing)
            + "; identity/geometry/texel/detail evidence must all exist before "
            "a face-referenced character can be production-ready"
        )
    if face_evidence_required and not face_evidence_ready:
        if face_evidence_score is None:
            warnings.append(
                "face references were supplied but no finite face-detail identity "
                "Judge aggregate score was recorded; asset remains inspectable but "
                "is not production-ready"
            )
        if face_evidence_missing:
            warnings.append(
                "face-reference Judge coverage incomplete: "
                f"{face_evidence_evaluated}/{face_evidence_expected} evaluated; "
                "missing="+",".join(face_evidence_missing)
                +"; asset remains inspectable but is not production-ready"
            )

    turntable_qa = None
    turntable_report_path = None
    turntable_contact_path = None
    turntable_ready = expected_sources == 0
    turntable_score = None
    if expected_sources:
        if turntable and source_coverage >= expected_sources:
            try:
                from turntable_qa import (
                    build_turntable_comparison_sheet,
                    score_source_to_turntable,
                    write_turntable_report,
                )

                turntable_qa = score_source_to_turntable(
                    source_images,
                    judged_views[:expected_sources],
                    turntable,
                )
                turntable_ready = bool(turntable_qa.ready)
                turntable_score = float(turntable_qa.score)
                turntable_report_path = write_turntable_report(
                    turntable_qa,
                    out_dir / "source_vs_turntable.json",
                )
                turntable_contact_path = build_turntable_comparison_sheet(
                    turntable_qa,
                    out_dir / "source_vs_turntable.png",
                )
                if not turntable_ready:
                    warnings.append(
                        f"source-vs-turntable QA failed: score={turntable_qa.score:.3f}, "
                        f"catastrophic_mismatches={turntable_qa.catastrophic_mismatches}"
                    )
            except Exception as exc:
                turntable_ready = False
                warnings.append(
                    f"source-vs-turntable QA unavailable: {type(exc).__name__}: {exc}"
                )
        else:
            turntable_ready = False
            warnings.append(
                "source-vs-turntable QA unavailable: turntable or complete Judge orientation evidence missing"
            )

    gameprep_ready = bool(gameprep_data and lods)
    if not gameprep_ready:
        warnings.append("GamePrep package missing")

    collision_audit = None
    collision_ready = False
    collision_faces = 0
    collision_convexity_ratio = None
    collision_bbox_coverage_ready = False
    try:
        from collision_qa import audit_collision
        collision_path=(
            Path(str(collision))
            if collision else None
        )
        collision_audit=audit_collision(
            final_glb,
            collision_path,
        )
        collision_ready=bool(collision_audit.ready)
        collision_faces=int(collision_audit.faces)
        collision_convexity_ratio=(
            float(collision_audit.convexity_ratio)
            if collision_audit.convexity_ratio is not None
            else None
        )
        collision_bbox_coverage_ready=bool(
            collision_audit.bbox_coverage_ready
        )
        warnings.extend(collision_audit.warnings or [])
        warnings.extend(collision_audit.errors or [])
    except Exception as exc:
        collision_ready=False
        warnings.append(
            "collision QA unavailable: "
            f"{type(exc).__name__}: {exc}"
        )
    if gameprep_ready and not collision_ready:
        warnings.append(
            "GamePrep collision proxy is missing or invalid; "
            "production-ready runtime status is false"
        )

    composite_attachment_audit = None
    composite_attachment_applicable = False
    composite_attachment_ready = False
    composite_attachment_components = 0
    composite_attachment_accessories = 0
    composite_attachment_floating = 0
    composite_attachment_oversized_floating = 0
    try:
        from composite_attachment_qa import audit_composite_attachments
        composite_attachment_audit = audit_composite_attachments(
            final_glb,
            mode=mode,
        )
        composite_attachment_applicable = bool(
            composite_attachment_audit.applicable
        )
        composite_attachment_ready = bool(
            composite_attachment_audit.applicable
            and composite_attachment_audit.ready
        )
        composite_attachment_components = int(
            composite_attachment_audit.component_count
        )
        composite_attachment_accessories = int(
            composite_attachment_audit.accessory_candidates
        )
        composite_attachment_floating = int(
            composite_attachment_audit.floating_components
        )
        composite_attachment_oversized_floating = int(
            composite_attachment_audit.oversized_floating_components
        )
        warnings.extend(composite_attachment_audit.warnings or [])
        warnings.extend(composite_attachment_audit.errors or [])
    except Exception as exc:
        composite_attachment_ready = False
        warnings.append(
            "composite attachment QA unavailable: "
            f"{type(exc).__name__}: {exc}"
        )
    if not composite_attachment_ready:
        warnings.append(
            "disconnected accessory/composite attachment QA failed; "
            "floating props or detached donor islands block production-ready status"
        )

    unresolved_rebakes = unresolved_material_rebakes(gameprep_data)
    material_rebaked_channels,material_rebake_pending_channels = (
        material_rebake_channel_summary(gameprep_data)
    )
    material_rebake_ready = not unresolved_rebakes
    if unresolved_rebakes:
        summary = "; ".join(
            f"{item['lod']}:{','.join(item['channels'])}"
            for item in unresolved_rebakes
        )
        warnings.append(
            "runtime LOD material rebake is incomplete: "
            + summary
            + "; asset remains inspectable but is not production-ready"
        )

    production_ready = bool(
        geometry_ready
        and material_ready
        and material_rebake_ready
        and component_crossing_ready
        and self_intersection_ready
        and composite_attachment_ready
        and uv_tangent_ready
        and (shading_basis_ready if shading_basis_required else True)
        and source_coverage >= expected_sources
        and gameprep_ready
        and collision_ready
        and turntable_ready
        and face_evidence_ready
        and face_quality_evidence_ready
        and (anatomy_evidence_ready if mode=="character" else True)
        and (rig_ready if rig_required else True)
        and (morph_ready if morph_required else True)
        and (morph_deformation_ready if morph_required else True)
        and (skin_weights_ready if rig_required and rig_ready else True)
        and (animation_ready if rig_required else True)
        and (deformation_ready if rig_required else True)
    )

    contact_path = build_contact_sheet(
        source_images=source_images,
        turntable_frames=turntable,
        output=out_dir / "qa_contact_sheet.png",
    )

    report = {
        "engine": "HAYUYA QA Package v1",
        "final_glb": str(final_glb),
        "mode": mode,
        "profile": profile,
        "champion": champion_data,
        "geometry": {
            "ready": geometry_ready,
            "vertices": mesh.vertices,
            "faces": mesh.faces,
            "components": mesh.components,
            "watertight": mesh.watertight,
            "degenerate_ratio": mesh.degenerate_ratio,
            "bbox": mesh.bbox,
            "production_score": mesh.production_score,
            "head_region_faces": mesh.head_region_faces,
            "head_region_vertices": mesh.head_region_vertices,
            "head_region_face_fraction": mesh.head_region_face_fraction,
            "global_median_edge_normalized": mesh.global_median_edge_normalized,
            "head_region_median_edge_normalized": mesh.head_region_median_edge_normalized,
            "head_region_density_ratio": mesh.head_region_density_ratio,
            "head_density_score": mesh.head_density_score,
            "head_texel_density_ratio": mesh.head_texel_density_ratio,
            "head_texel_density_score": mesh.head_texel_density_score,
            "head_texture_detail_ratio": mesh.head_texture_detail_ratio,
            "head_texture_detail_score": mesh.head_texture_detail_score,
            "head_texture_detail_mean": mesh.head_texture_detail_mean,
        },
        "structure": asdict(structure),
        "component_crossing": (
            asdict(component_crossing_audit)
            if component_crossing_audit is not None else {
                "applicable": component_crossing_applicable,
                "ready": component_crossing_ready,
                "crossing_triangle_pairs": component_crossing_pairs,
            }
        ),
        "self_intersection": (
            asdict(self_intersection_audit)
            if self_intersection_audit is not None else {
                "applicable": self_intersection_applicable,
                "ready": self_intersection_ready,
                "crossing_triangle_pairs": self_intersection_pairs,
            }
        ),
        "composite_attachment": (
            asdict(composite_attachment_audit)
            if composite_attachment_audit is not None else {
                "applicable": composite_attachment_applicable,
                "ready": composite_attachment_ready,
                "component_count": composite_attachment_components,
                "accessory_candidates": composite_attachment_accessories,
                "floating_components": composite_attachment_floating,
                "oversized_floating_components": (
                    composite_attachment_oversized_floating
                ),
            }
        ),
        "uv_tangent": (
            asdict(uv_tangent_audit)
            if uv_tangent_audit is not None else {
                "applicable": uv_tangent_applicable,
                "ready": uv_tangent_ready,
                "missing_uv_primitives": uv_missing_primitives,
                "degenerate_uv_triangles": uv_degenerate_triangles,
            }
        ),
        "shading_basis": (
            asdict(shading_basis_audit)
            if shading_basis_audit is not None else {
                "applicable": shading_basis_applicable,
                "ready": shading_basis_ready,
                "required": shading_basis_required,
                "missing_normals": shading_missing_normals,
                "missing_required_tangents": shading_missing_tangents,
                "invalid_handedness": shading_invalid_handedness,
                "nonorthogonal_tangents": shading_nonorthogonal_tangents,
            }
        ),
        "material": {
            "ready": material_ready,
            "base_material_ready": base_material_ready,
            "texture_resolution_ready": texture_resolution_ready,
            "material_score": mesh.material_score,
            "has_uv": mesh.has_uv,
            "textured": mesh.textured,
            "channels": mesh.pbr_channels,
            "texture_max_edge": mesh.texture_max_edge,
            "base_color_max_edge": mesh.base_color_max_edge,
            "base_color_min_edge": mesh.base_color_min_edge,
            "texture_resolution_score": mesh.texture_resolution_score,
            "target_texture_size": target_texture_size,
            "rebake_ready": material_rebake_ready,
            "rebaked_channels": material_rebaked_channels,
            "rebake_pending_channels": material_rebake_pending_channels,
            "unresolved_rebakes": unresolved_rebakes,
        },
        "rig": asdict(rig),
        "morph_deformation": (
            asdict(morph_deformation_audit)
            if morph_deformation_audit is not None else {
                "applicable": morph_deformation_applicable,
                "ready": morph_deformation_ready,
                "sampled_poses": morph_deformation_poses,
                "max_displacement_ratio": (
                    morph_deformation_max_displacement_ratio
                ),
            }
        ),
        "animation_qa": (
            asdict(animation_audit)
            if animation_audit is not None else {
                "applicable": bool(embedded_animation_ready),
                "ready": animation_integrity_ready,
                "channel_count": animation_channels,
                "total_keyframes": animation_keyframes,
            }
        ),
        "deformation_qa": (
            asdict(deformation_audit)
            if deformation_audit is not None else {
                "applicable": deformation_applicable,
                "ready": deformation_ready,
                "sampled_frames": deformation_frames,
                "max_displacement_ratio": deformation_max_displacement_ratio,
                "max_edge_stretch_ratio": deformation_max_edge_stretch_ratio,
            }
        ),
        "skin_weights": (
            asdict(skin_weight_audit)
            if skin_weight_audit is not None else {
                "applicable": skin_weights_applicable,
                "ready": skin_weights_ready,
            }
        ),
        "part_map": asdict(part_map_result) if part_map_result is not None else None,
        "judge": {
            "score": champion_data.get("score"),
            "visual_score": champion_data.get("visual_score"),
            "visual_views": judged_views,
            "appearance_score": champion_data.get("appearance_score"),
            "appearance_detail_score": champion_data.get("appearance_detail_score"),
            "appearance_face_detail_score": champion_data.get("appearance_face_detail_score"),
            "appearance_details": champion_data.get("appearance_details"),
            "normal_support_score": champion_data.get("normal_support_score"),
        },
        "gameprep": gameprep_data,
        "collision_qa": (
            asdict(collision_audit)
            if collision_audit is not None else {
                "applicable": False,
                "ready": collision_ready,
                "faces": collision_faces,
                "convexity_ratio": collision_convexity_ratio,
                "bbox_coverage_ready": collision_bbox_coverage_ready,
            }
        ),
        "source_coverage": {
            "expected": expected_sources,
            "judged": source_coverage,
        },
        "critical_anatomy": asdict(anatomy_evidence),
        "face_evidence": {
            "required": face_evidence_required,
            "references": [str(p) for p in face_detail_refs],
            "score": face_evidence_score,
            "min_score": face_evidence_min_score,
            "expected": face_evidence_expected,
            "evaluated": face_evidence_evaluated,
            "missing_references": face_evidence_missing,
            "quality_evidence_required": mode=="character",
            "identity_evidence_required": face_evidence_required,
            "quality_evidence_ready": face_quality_evidence_ready,
            "quality_evidence_missing": face_quality_evidence_missing,
            "ready": face_evidence_ready,
        },
        "turntable_qa": asdict(turntable_qa) if turntable_qa is not None else None,
        "production_ready": production_ready,
        "warnings": warnings,
    }
    report_path = out_dir / "qa_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return QAPackageResult(
        report=str(report_path),
        contact_sheet=str(contact_path) if contact_path else None,
        turntable_report=str(turntable_report_path) if turntable_report_path else None,
        turntable_contact_sheet=str(turntable_contact_path) if turntable_contact_path else None,
        part_map=str(part_map_path) if part_map_path else None,
        geometry_ready=geometry_ready,
        material_ready=material_ready,
        texture_resolution_ready=texture_resolution_ready,
        texture_resolution_score=mesh.texture_resolution_score,
        base_color_min_edge=int(mesh.base_color_min_edge or 0),
        base_color_max_edge=int(mesh.base_color_max_edge or 0),
        target_texture_size=(
            int(target_texture_size) if target_texture_size is not None else None
        ),
        material_rebake_ready=material_rebake_ready,
        material_rebaked_channels=material_rebaked_channels,
        material_rebake_pending_channels=material_rebake_pending_channels,
        rig_ready=rig_ready,
        morph_target_count=morph_target_count,
        morph_ready=morph_ready,
        morph_deformation_applicable=morph_deformation_applicable,
        morph_deformation_ready=morph_deformation_ready,
        morph_deformation_poses=morph_deformation_poses,
        morph_deformation_max_displacement_ratio=(
            morph_deformation_max_displacement_ratio
        ),
        animation_ready=animation_ready,
        animation_integrity_ready=animation_integrity_ready,
        animation_channels=animation_channels,
        animation_keyframes=animation_keyframes,
        deformation_applicable=deformation_applicable,
        deformation_ready=deformation_ready,
        deformation_frames=deformation_frames,
        deformation_max_displacement_ratio=deformation_max_displacement_ratio,
        deformation_max_edge_stretch_ratio=deformation_max_edge_stretch_ratio,
        skin_weights_applicable=skin_weights_applicable,
        skin_weights_ready=skin_weights_ready,
        component_crossing_applicable=component_crossing_applicable,
        component_crossing_ready=component_crossing_ready,
        component_crossing_pairs=component_crossing_pairs,
        self_intersection_applicable=self_intersection_applicable,
        self_intersection_ready=self_intersection_ready,
        self_intersection_pairs=self_intersection_pairs,
        uv_tangent_applicable=uv_tangent_applicable,
        uv_tangent_ready=uv_tangent_ready,
        uv_missing_primitives=uv_missing_primitives,
        uv_degenerate_triangles=uv_degenerate_triangles,
        shading_basis_applicable=shading_basis_applicable,
        shading_basis_ready=shading_basis_ready,
        shading_missing_normals=shading_missing_normals,
        shading_missing_tangents=shading_missing_tangents,
        shading_invalid_handedness=shading_invalid_handedness,
        shading_nonorthogonal_tangents=shading_nonorthogonal_tangents,
        collision_ready=collision_ready,
        collision_faces=collision_faces,
        collision_convexity_ratio=collision_convexity_ratio,
        collision_bbox_coverage_ready=collision_bbox_coverage_ready,
        composite_attachment_applicable=composite_attachment_applicable,
        composite_attachment_ready=composite_attachment_ready,
        composite_attachment_components=composite_attachment_components,
        composite_attachment_accessories=composite_attachment_accessories,
        composite_attachment_floating=composite_attachment_floating,
        composite_attachment_oversized_floating=(
            composite_attachment_oversized_floating
        ),
        turntable_ready=turntable_ready,
        turntable_score=turntable_score,
        face_evidence_ready=face_evidence_ready,
        face_evidence_score=(
            float(face_evidence_score)
            if face_evidence_score is not None else None
        ),
        face_evidence_expected=face_evidence_expected,
        face_evidence_evaluated=face_evidence_evaluated,
        face_evidence_missing=list(face_evidence_missing),
        face_evidence_min_score=(
            float(face_evidence_min_score)
            if face_evidence_min_score is not None else None
        ),
        face_quality_evidence_ready=face_quality_evidence_ready,
        face_quality_evidence_missing=list(face_quality_evidence_missing),
        anatomy_evidence_ready=anatomy_evidence_ready,
        anatomy_evidence_expected=anatomy_evidence_expected,
        anatomy_evidence_evaluated=anatomy_evidence_evaluated,
        anatomy_evidence_missing=list(anatomy_evidence_missing),
        head_density_score=(
            float(mesh.head_density_score)
            if mesh.head_density_score is not None else None
        ),
        head_texel_density_score=(
            float(mesh.head_texel_density_score)
            if mesh.head_texel_density_score is not None else None
        ),
        head_texture_detail_score=(
            float(mesh.head_texture_detail_score)
            if mesh.head_texture_detail_score is not None else None
        ),
        production_ready=production_ready,
        warnings=warnings,
    )
