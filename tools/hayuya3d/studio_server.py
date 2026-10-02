#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from email.parser import BytesHeaderParser
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATIC = HERE / "studio"
DEFAULT_JOBS_ROOT = ROOT / "out" / "hayuya3d" / "studio-jobs"
VENDOR_ROOT = ROOT / ".hayuya" / "studio-vendor"
MODEL_VIEWER_VERSION = "4.3.1"
MODEL_VIEWER_URL = f"https://cdn.jsdelivr.net/npm/@google/model-viewer@{MODEL_VIEWER_VERSION}/dist/model-viewer.min.js"
MODEL_VIEWER_FILE = VENDOR_ROOT / f"model-viewer-{MODEL_VIEWER_VERSION}.min.js"

ALLOWED_PROFILES = {"preview", "mobile", "game", "monster", "ultra"}
ALLOWED_MODES = {"auto", "prop", "character", "architecture"}
ALLOWED_TIERS = {"auto", "compatibility", "balanced", "high", "flagship"}

STAGE_PROGRESS = {
    "queued": 0,
    "planning": 4,
    "viewforge": 12,
    "generating": 25,
    "judge": 50,
    "refinement": 60,
    "mesh_doctor": 68,
    "retopo": 74,
    "composite": 80,
    "gameprep": 86,
    "portable": 92,
    "qa": 96,
    "complete": 100,
    "failed": 100,
}


@dataclass
class CandidateState:
    label: str
    path: str
    url: str | None = None
    score: float | None = None
    production_score: float | None = None
    visual_score: float | None = None
    appearance_score: float | None = None
    detail_score: float | None = None
    face_detail_score: float | None = None
    face_detail_min_score: float | None = None
    material_score: float | None = None
    texture_resolution_score: float | None = None
    base_color_max_edge: int | None = None
    base_color_min_edge: int | None = None
    head_region_faces: int | None = None
    head_region_vertices: int | None = None
    head_region_face_fraction: float | None = None
    global_median_edge_normalized: float | None = None
    head_region_median_edge_normalized: float | None = None
    head_region_density_ratio: float | None = None
    head_density_score: float | None = None
    head_texel_density_ratio: float | None = None
    head_texel_density_score: float | None = None
    head_texture_detail_ratio: float | None = None
    head_texture_detail_score: float | None = None
    head_texture_detail_mean: float | None = None
    pbr_channels: list[str] | None = None
    is_champion: bool = False


@dataclass
class JobState:
    id: str
    root: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    command: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    profile: str = "monster"
    mode: str = "auto"
    portable_target: str = "auto"
    candidates: dict[str, CandidateState] = field(default_factory=dict)
    champion: str | None = None
    final_model_url: str | None = None
    final_model_path: str | None = None
    composite_plan: dict | None = None
    composite_details: list[dict] = field(default_factory=list)
    semantic_anatomy: dict | None = None
    portable_pack: dict | None = None
    aaa_acceptance: dict | None = None
    final_qa: dict | None = None
    error: str | None = None
    events: list[dict] = field(default_factory=list)
    _condition: threading.Condition = field(default_factory=threading.Condition, repr=False)

    def public(self) -> dict:
        data = asdict(self)
        data.pop("_condition", None)
        data["candidates"] = [asdict(x) for x in self.candidates.values()]
        data["event_count"] = len(self.events)
        data.pop("events", None)
        return data


JOBS: dict[str, JobState] = {}
JOBS_LOCK = threading.Lock()


def _safe_name(value: str) -> str:
    value = Path(value).name
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:120] or "upload.bin"


def _job_url(job: JobState, path: Path) -> str | None:
    try:
        root = Path(job.root).resolve()
        rel = path.resolve().relative_to(root)
    except Exception:
        return None
    return f"/api/jobs/{job.id}/files/{quote(rel.as_posix())}"


def _viewer_artifact(job: JobState, label: str, path: Path) -> Path | None:
    if not path.is_file():
        return None
    if path.suffix.lower() in {".glb", ".gltf"}:
        return path
    if path.suffix.lower() not in {".obj", ".ply", ".stl"}:
        return None
    try:
        from qa import export_glb
        preview_dir = Path(job.root) / "viewer-previews"
        preview = preview_dir / f"{_safe_name(label)}.glb"
        export_glb(path, preview)
        return preview
    except Exception as exc:
        _emit(job, "viewer_warning", {
            "label": label,
            "message": f"could not normalize {path.suffix} candidate for viewer: {type(exc).__name__}: {exc}",
        })
        return None


def _emit(job: JobState, kind: str, payload: dict) -> None:
    event = {
        "seq": len(job.events),
        "time": time.time(),
        "kind": kind,
        **payload,
    }
    with job._condition:
        job.events.append(event)
        job.updated_at = time.time()
        job._condition.notify_all()


def _set_stage(job: JobState, stage: str, *, status: str | None = None) -> None:
    job.stage = stage
    job.progress = STAGE_PROGRESS.get(stage, job.progress)
    if status:
        job.status = status
    _emit(job, "stage", {"stage": job.stage, "progress": job.progress, "status": job.status})


def parse_pipeline_line(job: JobState, line: str) -> None:
    line = line.strip()
    if not line:
        return
    _emit(job, "log", {"line": line})

    if line.startswith("HAYUYA_VIEWFORGE"):
        _set_stage(job, "viewforge")
    elif line.startswith("HAYUYA_CANDIDATE_READY"):
        _set_stage(job, "generating")
        parts = line.split()
        match = re.match(
            r"^HAYUYA_CANDIDATE_READY\s+(\S+)\s+(.+?)(?:\s+(?:source|sources|real_sources)=|$)",
            line,
        )
        if match:
            label = match.group(1)
            path = match.group(2).strip()
            viewer_path = _viewer_artifact(job, label, Path(path))
            candidate = CandidateState(label=label, path=path)
            candidate.url = _job_url(job, viewer_path) if viewer_path is not None else None
            job.candidates[label] = candidate
            _emit(job, "candidate", asdict(candidate))
    elif line.startswith("HAYUYA_JUDGE_SCORE"):
        _set_stage(job, "judge")
        match = re.search(
            r"backend=([^\s]+)\s+score=([0-9.]+)\s+valid=([^\s]+)\s+rank=(\d+)\s+pass=(\d+)",
            line,
        )
        if match:
            label = match.group(1)
            score = float(match.group(2))
            valid = match.group(3).lower() == "true"
            rank = int(match.group(4))
            ranking_pass = int(match.group(5))
            if label in job.candidates:
                job.candidates[label].score = score
            _emit(job, "judge_score", {
                "label": label,
                "score": score,
                "valid": valid,
                "rank": rank,
                "pass": ranking_pass,
            })
    elif line.startswith("HAYUYA_JUDGE_METRICS "):
        _set_stage(job, "judge")
        payload = line.removeprefix("HAYUYA_JUDGE_METRICS ").strip()
        try:
            item = json.loads(payload)
            if isinstance(item, dict):
                hydrate_candidate_ranking(job, [item])
                label = str(item.get("backend", ""))
                candidate = job.candidates.get(label)
                if candidate is not None:
                    _emit(job, "judge_metrics", {
                        "label": label,
                        "candidate": asdict(candidate),
                    })
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    elif line.startswith("HAYUYA_REFINEMENT"):
        _set_stage(job, "refinement")
    elif line.startswith("HAYUYA_TEXTURE_SUPERRES"):
        _set_stage(job, "refinement")
    elif line.startswith("HAYUYA_MESH_DOCTOR"):
        _set_stage(job, "mesh_doctor")
    elif line.startswith("HAYUYA_RETOPO"):
        _set_stage(job, "retopo")
    elif line.startswith("HAYUYA_COMPOSITE_PLAN_READY"):
        _set_stage(job, "composite")
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        plan_raw = values.get("plan")
        plan_data = None
        if plan_raw:
            try:
                plan_path = Path(plan_raw).resolve()
                job_root = Path(job.root).resolve()
                if plan_path.is_file() and plan_path.is_relative_to(job_root):
                    loaded = json.loads(plan_path.read_text(encoding="utf-8"))
                    if isinstance(loaded,dict):
                        plan_data = loaded
            except (OSError,ValueError,json.JSONDecodeError):
                plan_data = None
        if plan_data is None:
            plan_data = {
                "base_backend": values.get("base"),
                "composite_required": values.get("required","false").lower()=="true",
                "finalist_backends": [],
                "donors": [],
                "executable_now": [],
                "deferred_transfers": [],
            }
        job.composite_plan = plan_data
        _emit(job, "composite_plan", {"plan": dict(plan_data)})
    elif line.startswith("HAYUYA_COMPOSITE_DETAIL_READY"):
        _set_stage(job, "composite")
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        def _float_value(name: str) -> float | None:
            raw=values.get(name)
            if not raw or raw.lower()=="none":
                return None
            try:
                return float(raw)
            except ValueError:
                return None
        def _int_value(name: str) -> int | None:
            raw=values.get(name)
            if not raw or raw.lower()=="none":
                return None
            try:
                return int(raw)
            except ValueError:
                return None
        def _bool_value(name: str) -> bool | None:
            raw=values.get(name)
            if not raw or raw.lower()=="none":
                return None
            token=raw.lower()
            if token=="true":
                return True
            if token=="false":
                return False
            return None
        item={
            "label":values.get("label"),
            "base":values.get("base"),
            "donor":values.get("donor"),
            "region":values.get("region"),
            "source":values.get("source"),
            "strategy":values.get("strategy"),
            "changed_fraction":_float_value("changed"),
            "seam_p95":_float_value("seam_p95"),
            "seam_max":_float_value("seam_max"),
            "accessory_confidence":_float_value("accessory_confidence"),
            "changed_vertices":_int_value("changed_vertices"),
            "inserted_vertices":_int_value("inserted_vertices"),
            "inserted_faces":_int_value("inserted_faces"),
            "inserted_primitives":_int_value("inserted_primitives"),
            "material_groups":_int_value("material_groups"),
            "weight_transfer_vertices":_int_value("weight_transfer_vertices"),
            "weight_source_max":_float_value("weight_source_max"),
            "surface_transfer":values.get("surface_transfer"),
            "surface_fallback_vertices":_int_value(
                "surface_fallback_vertices"
            ),
            "surface_search_triangles":_int_value(
                "surface_search_triangles"
            ),
            "surface_bvh_nodes":_int_value("surface_bvh_nodes"),
            "surface_ambiguous_vertices":_int_value(
                "surface_ambiguous_vertices"
            ),
            "surface_skin_gap":_float_value("surface_skin_gap"),
            "surface_skin_l1":_float_value("surface_skin_l1"),
            "morph_targets_transferred":_int_value("morph_targets_transferred"),
            "geometry_ready":_bool_value("geometry_ready"),
            "legacy_preserved":_bool_value("legacy_preserved"),
            "runtime_preserved":_bool_value("runtime_preserved"),
            "rig_ready":_bool_value("rig_ready"),
            "skin_weights_ready":_bool_value("skin_weights_ready"),
            "morph_deformation_ready":_bool_value("morph_deformation_ready"),
            "animation_ready":_bool_value("animation_ready"),
            "deformation_ready":_bool_value("deformation_ready"),
            "attachment_ready":_bool_value("attachment_ready"),
            "material_ready":_bool_value("material_ready"),
            "uv_ready":_bool_value("uv_ready"),
            "uv_tangent_ready":_bool_value("uv_tangent_ready"),
            "production_ready":_bool_value("production_ready"),
            "material_channels":[
                x for x in values.get("material_channels","").split(",")
                if x and x!="none"
            ],
            "rebake_ready":_bool_value("rebake_ready"),
            "path":values.get("path"),
            "status":"challenger",
        }
        job.composite_details.append(item)
        _emit(job,"composite_detail",{"detail":dict(item)})
    elif line.startswith("HAYUYA_COMPOSITE_DETAIL_GUARD_PASS"):
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        label=values.get("label")
        for item in reversed(job.composite_details):
            if item.get("label")==label:
                item["status"]="accepted"
                break
        _emit(job,"composite_detail_state",{
            "label":label,
            "status":"accepted",
            "source":values.get("source"),
        })
    elif line.startswith("HAYUYA_COMPOSITE_DETAIL_REJECTED"):
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        label=values.get("label")
        for item in reversed(job.composite_details):
            if item.get("label")==label:
                item["status"]="rejected"
                item["reason"]=values.get("reason")
                break
        _emit(job,"composite_detail_state",{
            "label":label,
            "status":"rejected",
            "source":values.get("source"),
            "reason":values.get("reason"),
        })
    elif line.startswith("HAYUYA_SEMANTIC_ANATOMY_READY"):
        _set_stage(job, "qa")
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        semantic_data = None
        report_raw = values.get("report")
        if report_raw and report_raw.lower()!="none":
            try:
                report_path = Path(report_raw).resolve()
                job_root = Path(job.root).resolve()
                if report_path.is_file() and report_path.is_relative_to(job_root):
                    loaded = json.loads(report_path.read_text(encoding="utf-8"))
                    if isinstance(loaded,dict):
                        semantic_data = {
                            "required": True,
                            "attempted": values.get("attempted","false").lower()=="true",
                            "ready": values.get("ready","false").lower()=="true",
                            "critical_targets": [
                                x for x in values.get("targets","").split(",")
                                if x and x!="none"
                            ],
                            "rendered_views": [None] * int(values.get("views") or 0),
                            "aggregate": loaded,
                            "report": str(report_path),
                            "error": (
                                None
                                if values.get("error") in (None,"","none")
                                else values.get("error")
                            ),
                        }
            except (OSError,ValueError,json.JSONDecodeError):
                semantic_data = None
        if semantic_data is None:
            semantic_data = {
                "required": True,
                "attempted": values.get("attempted","false").lower()=="true",
                "ready": values.get("ready","false").lower()=="true",
                "critical_targets": [
                    x for x in values.get("targets","").split(",")
                    if x and x!="none"
                ],
                "rendered_views": [None] * int(values.get("views") or 0),
                "aggregate": None,
                "report": None,
                "error": (
                    None
                    if values.get("error") in (None,"","none")
                    else values.get("error")
                ),
            }
        job.semantic_anatomy = semantic_data
        _emit(job,"semantic_anatomy",{"semantic":dict(semantic_data)})
    elif line.startswith("HAYUYA_GAMEPREP"):
        _set_stage(job, "gameprep")
    elif line.startswith("HAYUYA_PORTABLE_PACK_READY"):
        _set_stage(job, "portable")
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        manifest_data = None
        manifest_raw = values.get("manifest")
        if manifest_raw:
            try:
                manifest_path = Path(manifest_raw).resolve()
                job_root = Path(job.root).resolve()
                if manifest_path.is_file() and manifest_path.is_relative_to(job_root):
                    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if isinstance(loaded,dict):
                        manifest_data = loaded
            except (OSError,ValueError,json.JSONDecodeError):
                manifest_data = None
        if manifest_data is None:
            manifest_data = {
                "complete_lod_chain": values.get("complete_lods","false").lower()=="true",
                "lod_parity_ready": values.get("lod_parity_ready","false").lower()=="true",
                "runtime_budget_ready": values.get("runtime_budget_ready","false").lower()=="true",
                "tiers": [],
            }
        job.portable_pack = manifest_data
        _emit(job,"portable_pack",{"pack":dict(manifest_data)})
    elif line.startswith("HAYUYA_PORTABLE_PACK"):
        _set_stage(job, "portable")
    elif line.startswith("HAYUYA_AAA_READY"):
        _set_stage(job, "qa")
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        report_data = None
        report_raw = values.get("report")
        if report_raw:
            try:
                report_path = Path(report_raw).resolve()
                job_root = Path(job.root).resolve()
                if report_path.is_file() and report_path.is_relative_to(job_root):
                    loaded = json.loads(report_path.read_text(encoding="utf-8"))
                    if isinstance(loaded,dict):
                        report_data = loaded
            except (OSError,ValueError,json.JSONDecodeError):
                report_data = None
        if report_data is None:
            report_data = {
                "ready": values.get("ready","false").lower()=="true",
                "passed_required": int(values.get("passed") or 0),
                "total_required": int(values.get("total") or 0),
                "blockers": [],
                "gates": [],
            }
        job.aaa_acceptance = report_data
        _emit(job, "aaa_ready", {"aaa": dict(report_data)})
    elif line.startswith("HAYUYA_QA_READY"):
        _set_stage(job, "qa")
        values = dict(re.findall(r"(\w+)=([^\s]+)", line))
        def _bool(name: str) -> bool:
            return values.get(name, "").lower() == "true"
        raw_face = values.get("face_score")
        face_score = None
        if raw_face and raw_face.lower() != "none":
            try:
                face_score = float(raw_face)
            except ValueError:
                face_score = None
        def _float_or_none(key: str) -> float | None:
            raw = values.get(key)
            if not raw or raw.lower() == "none":
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        def _int_or_none(key: str) -> int | None:
            raw = values.get(key)
            if not raw or raw.lower() == "none":
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        raw_facemesh = values.get("facemesh_score")
        facemesh_score = None
        if raw_facemesh and raw_facemesh.lower() != "none":
            try:
                facemesh_score = float(raw_facemesh)
            except ValueError:
                facemesh_score = None
        raw_facetex = values.get("facetex_score")
        facetex_score = None
        if raw_facetex and raw_facetex.lower() != "none":
            try:
                facetex_score = float(raw_facetex)
            except ValueError:
                facetex_score = None
        raw_facedetail = values.get("facedetail_score")
        facedetail_score = None
        if raw_facedetail and raw_facedetail.lower() != "none":
            try:
                facedetail_score = float(raw_facedetail)
            except ValueError:
                facedetail_score = None
        job.final_qa = {
            "production_ready": _bool("production_ready"),
            "material_ready": _bool("material_ready"),
            "texture_ready": _bool("texture_ready"),
            "texture_score": _float_or_none("texture_score"),
            "basecolor_min": _int_or_none("basecolor_min"),
            "basecolor_max": _int_or_none("basecolor_max"),
            "texture_target": _int_or_none("texture_target"),
            "rebake_ready": _bool("rebake_ready"),
            "rebaked_channels": (
                [] if values.get("rebaked") in (None,"","none")
                else [x for x in values["rebaked"].split(",") if x]
            ),
            "rebake_pending_channels": (
                [] if values.get("rebake_pending") in (None,"","none")
                else [x for x in values["rebake_pending"].split(",") if x]
            ),
            "rig_ready": _bool("rig_ready"),
            "morph_ready": _bool("morph_ready"),
            "morph_targets": _int_or_none("morph_targets"),
            "morph_deformation_ready": _bool("morph_deformation_ready"),
            "morph_deformation_poses": _int_or_none("morph_deformation_poses"),
            "morph_deformation_max_disp": _float_or_none("morph_deformation_max_disp"),
            "crossing_ready": _bool("crossing_ready"),
            "crossing_pairs": _int_or_none("crossing_pairs"),
            "self_intersection_ready": _bool("self_intersection_ready"),
            "self_intersection_pairs": _int_or_none("self_intersection_pairs"),
            "composite_attachment_ready": _bool("composite_attachment_ready"),
            "composite_components": _int_or_none("composite_components"),
            "composite_accessories": _int_or_none("composite_accessories"),
            "composite_floating": _int_or_none("composite_floating"),
            "composite_oversized_floating": _int_or_none("composite_oversized_floating"),
            "uv_tangent_ready": _bool("uv_tangent_ready"),
            "uv_missing": _int_or_none("uv_missing"),
            "uv_degenerate": _int_or_none("uv_degenerate"),
            "shading_basis_ready": _bool("shading_basis_ready"),
            "shading_missing_normals": _int_or_none("shading_missing_normals"),
            "shading_missing_tangents": _int_or_none("shading_missing_tangents"),
            "shading_bad_handedness": _int_or_none("shading_bad_handedness"),
            "shading_nonorthogonal": _int_or_none("shading_nonorthogonal"),
            "skin_weights_ready": _bool("skin_weights_ready"),
            "animation_ready": _bool("animation_ready"),
            "animation_integrity_ready": _bool("animation_integrity_ready"),
            "animation_channels": _int_or_none("animation_channels"),
            "animation_keyframes": _int_or_none("animation_keyframes"),
            "deformation_ready": _bool("deformation_ready"),
            "deformation_frames": _int_or_none("deformation_frames"),
            "deformation_max_disp": _float_or_none("deformation_max_disp"),
            "deformation_max_edge": _float_or_none("deformation_max_edge"),
            "face_ready": _bool("face_ready"),
            "face_quality_ready": _bool("face_quality_ready"),
            "anatomy_ready": _bool("anatomy_ready"),
            "anatomy_expected": _int_or_none("anatomy_expected"),
            "anatomy_evaluated": _int_or_none("anatomy_evaluated"),
            "face_score": face_score,
            "face_min": _float_or_none("face_min"),
            "face_expected": _int_or_none("face_expected"),
            "face_evaluated": _int_or_none("face_evaluated"),
            "facemesh_score": facemesh_score,
            "facetex_score": facetex_score,
            "facedetail_score": facedetail_score,
            "report": values.get("report"),
            "warnings": [],
        }
        report_raw = values.get("report")
        if report_raw:
            try:
                report_path = Path(report_raw).resolve()
                job_root = Path(job.root).resolve()
                if report_path.is_file() and report_path.is_relative_to(job_root):
                    report_data = json.loads(report_path.read_text(encoding="utf-8"))
                    warnings = report_data.get("warnings") or []
                    if isinstance(warnings, list):
                        job.final_qa["warnings"] = [
                            str(item) for item in warnings if str(item).strip()
                        ][:12]
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        _emit(job, "qa_ready", {"qa": dict(job.final_qa)})
    elif line.startswith("HAYUYA_QA"):
        _set_stage(job, "qa")
    elif line.startswith("HAYUYA_MONSTER_READY"):
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            path = Path(parts[1])
            job.final_model_path = str(path)
            job.final_model_url = _job_url(job, path)
            _emit(job, "model", {"path": str(path), "url": job.final_model_url})
    elif line.startswith("HAYUYA_CHAMPION"):
        match = re.search(r"backend=([^\s]+).*score=([0-9.]+)", line)
        if match:
            label = match.group(1)
            score = float(match.group(2))
            job.champion = label
            if label in job.candidates:
                job.candidates[label].score = score
                job.candidates[label].is_champion = True
            _emit(job, "champion", {"label": label, "score": score})
    elif "Judge" in line or "ranking" in line.lower():
        if job.progress < STAGE_PROGRESS["judge"]:
            _set_stage(job, "judge")


def hydrate_candidate_ranking(job: JobState, ranking: list[dict]) -> None:
    for item in ranking:
        label = str(item.get("backend", ""))
        candidate = job.candidates.get(label)
        if candidate is None:
            continue
        if item.get("score") is not None:
            candidate.score = float(item["score"])
        if item.get("production_score") is not None:
            candidate.production_score = float(item["production_score"])
        if item.get("visual_score") is not None:
            candidate.visual_score = float(item["visual_score"])
        if item.get("appearance_score") is not None:
            candidate.appearance_score = float(item["appearance_score"])
        if item.get("appearance_detail_score") is not None:
            candidate.detail_score = float(item["appearance_detail_score"])
        if item.get("appearance_face_detail_score") is not None:
            candidate.face_detail_score = float(item["appearance_face_detail_score"])
        if item.get("appearance_face_detail_min_score") is not None:
            candidate.face_detail_min_score = float(
                item["appearance_face_detail_min_score"]
            )
        if item.get("material_score") is not None:
            candidate.material_score = float(item["material_score"])
        if item.get("texture_resolution_score") is not None:
            candidate.texture_resolution_score = float(item["texture_resolution_score"])
        if item.get("base_color_max_edge") is not None:
            candidate.base_color_max_edge = int(item["base_color_max_edge"])
        if item.get("base_color_min_edge") is not None:
            candidate.base_color_min_edge = int(item["base_color_min_edge"])
        if item.get("head_region_faces") is not None:
            candidate.head_region_faces = int(item["head_region_faces"])
        if item.get("head_region_vertices") is not None:
            candidate.head_region_vertices = int(item["head_region_vertices"])
        if item.get("head_region_face_fraction") is not None:
            candidate.head_region_face_fraction = float(item["head_region_face_fraction"])
        if item.get("global_median_edge_normalized") is not None:
            candidate.global_median_edge_normalized = float(
                item["global_median_edge_normalized"]
            )
        if item.get("head_region_median_edge_normalized") is not None:
            candidate.head_region_median_edge_normalized = float(
                item["head_region_median_edge_normalized"]
            )
        if item.get("head_region_density_ratio") is not None:
            candidate.head_region_density_ratio = float(
                item["head_region_density_ratio"]
            )
        if item.get("head_density_score") is not None:
            candidate.head_density_score = float(item["head_density_score"])
        if item.get("head_texel_density_ratio") is not None:
            candidate.head_texel_density_ratio = float(item["head_texel_density_ratio"])
        if item.get("head_texel_density_score") is not None:
            candidate.head_texel_density_score = float(item["head_texel_density_score"])
        if item.get("head_texture_detail_ratio") is not None:
            candidate.head_texture_detail_ratio = float(item["head_texture_detail_ratio"])
        if item.get("head_texture_detail_score") is not None:
            candidate.head_texture_detail_score = float(item["head_texture_detail_score"])
        if item.get("head_texture_detail_mean") is not None:
            candidate.head_texture_detail_mean = float(item["head_texture_detail_mean"])
        channels = item.get("pbr_channels")
        if isinstance(channels, list):
            candidate.pbr_channels = [str(x) for x in channels]


def _run_job(job: JobState) -> None:
    _set_stage(job, "planning", status="running")
    log_path = Path(job.root) / "studio.log"
    try:
        with log_path.open("w", encoding="utf-8", buffering=1) as log:
            proc = subprocess.Popen(
                job.command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for raw in proc.stdout:
                log.write(raw)
                parse_pipeline_line(job, raw)
            code = proc.wait()

        for ranking_path in sorted(Path(job.root).glob("output/**/ranking.json")):
            try:
                ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
                hydrate_candidate_ranking(job, ranking)
                _emit(job, "ranking", {
                    "candidates": [asdict(x) for x in job.candidates.values()]
                })
            except Exception:
                pass

        if code != 0:
            job.error = f"Hayuya exited with code {code}"
            _set_stage(job, "failed", status="failed")
            _emit(job, "error", {"message": job.error})
            return
        _set_stage(job, "complete", status="complete")
    except Exception as exc:
        job.error = f"{type(exc).__name__}: {exc}"
        _set_stage(job, "failed", status="failed")
        _emit(job, "error", {"message": job.error})


def _parse_content_disposition(value: str) -> tuple[str | None, str | None]:
    name = re.search(r'(?:^|;)\s*name="([^"]*)"', value)
    filename = re.search(r'(?:^|;)\s*filename="([^"]*)"', value)
    return (name.group(1) if name else None, filename.group(1) if filename else None)


def parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], list[tuple[str, str, bytes]]]:
    match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type)
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = (match.group(1) or match.group(2)).encode("utf-8")
    token = b"--" + boundary

    fields: dict[str, str] = {}
    files: list[tuple[str, str, bytes]] = []
    parser = BytesHeaderParser()
    for block in body.split(token):
        block = block.strip(b"\r\n")
        if not block or block == b"--":
            continue
        if block.endswith(b"--"):
            block = block[:-2].rstrip(b"\r\n")
        head, sep, payload = block.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = parser.parsebytes(head + b"\r\n")
        disposition = headers.get("Content-Disposition", "")
        name, filename = _parse_content_disposition(disposition)
        if not name:
            continue
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        if filename is not None:
            files.append((name, _safe_name(filename), payload))
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields, files


def ensure_model_viewer() -> tuple[Path | None, str | None]:
    if MODEL_VIEWER_FILE.is_file() and MODEL_VIEWER_FILE.stat().st_size > 100_000:
        return MODEL_VIEWER_FILE, None
    VENDOR_ROOT.mkdir(parents=True, exist_ok=True)
    temp = MODEL_VIEWER_FILE.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(MODEL_VIEWER_URL, timeout=25) as response:
            data = response.read()
        if len(data) < 100_000:
            raise RuntimeError(f"download unexpectedly small: {len(data)} bytes")
        temp.write_bytes(data)
        temp.replace(MODEL_VIEWER_FILE)
        return MODEL_VIEWER_FILE, None
    except Exception as exc:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass
        return None, f"{type(exc).__name__}: {exc}"


def local_addresses(port: int) -> list[str]:
    found = {"127.0.0.1"}
    try:
        host = socket.gethostname()
        for item in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = item[4][0]
            if ip and not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    return [f"http://{ip}:{port}" for ip in sorted(found)]


class StudioHandler(BaseHTTPRequestHandler):
    server_version = "HAYUYAStudio/0.1"

    def _json(self, value, status=200):
        data = json.dumps(value, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path: Path):
        if not path.is_file():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        range_header = self.headers.get("Range")
        start, end = 0, max(0, size - 1)

        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self.send_error(416)
                return
            raw_start, raw_end = match.groups()
            if raw_start:
                start = int(raw_start)
                end = int(raw_end) if raw_end else end
            elif raw_end:
                suffix = int(raw_end)
                start = max(0, size - suffix)
            end = min(end, size - 1)
            if start < 0 or start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return

        length = end - start + 1
        self.send_response(206 if range_header else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/vendor/model-viewer.min.js":
            vendor, error = ensure_model_viewer()
            if vendor is None:
                self._json({
                    "error": "model-viewer vendor unavailable",
                    "detail": error,
                    "fallback": MODEL_VIEWER_URL,
                }, 503)
                return
            self._serve_file(vendor)
            return

        if path == "/api/info":
            self._json({
                "name": "HAYUYA Studio",
                "version": 1,
                "addresses": local_addresses(self.server.server_port),
                "mobile_ready": True,
                "viewer_dependency": {
                    "name": "@google/model-viewer",
                    "version": MODEL_VIEWER_VERSION,
                    "served_locally": MODEL_VIEWER_FILE.is_file(),
                },
            })
            return

        if path == "/api/jobs":
            with JOBS_LOCK:
                jobs = sorted(JOBS.values(), key=lambda x: x.created_at, reverse=True)
            self._json([x.public() for x in jobs])
            return

        match = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]+)", path)
        if match:
            job = JOBS.get(match.group(1))
            if not job:
                self.send_error(404)
                return
            self._json(job.public())
            return

        match = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]+)/events", path)
        if match:
            job = JOBS.get(match.group(1))
            if not job:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            index = 0
            try:
                while True:
                    with job._condition:
                        while index >= len(job.events):
                            if job.status in {"complete", "failed"}:
                                break
                            job._condition.wait(timeout=12)
                            if index >= len(job.events):
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                        while index < len(job.events):
                            event = job.events[index]
                            payload = json.dumps(event, separators=(",", ":"))
                            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                            self.wfile.flush()
                            index += 1
                        if job.status in {"complete", "failed"} and index >= len(job.events):
                            break
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        match = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]+)/files/(.+)", path)
        if match:
            job = JOBS.get(match.group(1))
            if not job:
                self.send_error(404)
                return
            rel = Path(unquote(match.group(2)))
            root = Path(job.root).resolve()
            candidate = (root / rel).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                self.send_error(403)
                return
            self._serve_file(candidate)
            return

        if path == "/":
            path = "/index.html"
        static_path = (STATIC / path.lstrip("/")).resolve()
        try:
            static_path.relative_to(STATIC.resolve())
        except ValueError:
            self.send_error(403)
            return
        self._serve_file(static_path)

    def do_POST(self):
        if self.path != "/api/jobs":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 512 * 1024 * 1024:
            self._json({"error": "upload body must be between 1 byte and 512MB"}, 413)
            return
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._json({"error": "multipart/form-data required"}, 400)
            return

        try:
            fields, files = parse_multipart(self.rfile.read(length), content_type)
        except Exception as exc:
            self._json({"error": f"bad upload: {exc}"}, 400)
            return

        image_files = [item for item in files if item[0] == "images"]
        face_files = [item for item in files if item[0] == "face_images"]
        if not image_files:
            self._json({"error": "at least one geometry image is required"}, 400)
            return

        profile = fields.get("profile", "monster")
        mode = fields.get("mode", "auto")
        tier = fields.get("portable_target", "auto")
        if profile not in ALLOWED_PROFILES or mode not in ALLOWED_MODES or tier not in ALLOWED_TIERS:
            self._json({"error": "invalid profile/mode/portable target"}, 400)
            return

        job_id = f"{int(time.time())}-{secrets.token_hex(3)}"
        job_root = (self.server.jobs_root / job_id).resolve()
        inputs_dir = job_root / "inputs"
        face_dir = inputs_dir / "details"
        output_root = job_root / "output"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        face_dir.mkdir(parents=True, exist_ok=True)
        output_root.mkdir(parents=True, exist_ok=True)

        geometry_paths: list[Path] = []
        for index, (_field, filename, payload) in enumerate(image_files):
            ext = Path(filename).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            dst = inputs_dir / f"{index:03d}-{_safe_name(filename)}"
            dst.write_bytes(payload)
            geometry_paths.append(dst)

        face_paths: list[Path] = []
        for index, (_field, filename, payload) in enumerate(face_files):
            ext = Path(filename).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            # Explicit Studio face references are persisted under a recognized
            # detail directory and carry a semantic filename prefix so both
            # role classification and head-region local-patch retrieval remain
            # deterministic even for camera names like IMG_1234.jpg.
            dst = face_dir / f"{index:03d}-face_detail-{_safe_name(filename)}"
            dst.write_bytes(payload)
            face_paths.append(dst)

        if not geometry_paths:
            self._json({"error": "no supported geometry PNG/JPG/WEBP files"}, 400)
            return

        input_paths = [*geometry_paths, *face_paths]

        cmd = [
            sys.executable,
            str(HERE / "hayuya.py"),
            "--profile", profile,
            "--mode", mode,
            "--portable-target", tier,
            "--portable-pack", "auto",
            "--texture-delivery", "auto",
            "--output-root", str(output_root),
            "--execute",
        ]
        for p in input_paths:
            cmd.extend(["--input", str(p)])

        job = JobState(
            id=job_id,
            root=str(job_root),
            command=cmd,
            inputs=[str(p) for p in input_paths],
            profile=profile,
            mode=mode,
            portable_target=tier,
        )
        with JOBS_LOCK:
            JOBS[job_id] = job
        _emit(job, "created", {"job": job.public()})
        threading.Thread(target=_run_job, args=(job,), daemon=True).start()
        self._json(job.public(), 201)

    def log_message(self, fmt, *args):
        sys.stdout.write("[studio] " + (fmt % args) + "\n")


class StudioHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, jobs_root: Path):
        self.jobs_root = jobs_root
        super().__init__(address, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="HAYUYA Studio — live local/LAN UI for the Hayuya pipeline.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--lan", action="store_true", help="listen on 0.0.0.0 so phones/tablets on the same LAN can open Studio")
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_JOBS_ROOT)
    args = parser.parse_args()

    host = "0.0.0.0" if args.lan else args.host
    args.jobs_root.mkdir(parents=True, exist_ok=True)
    vendor, vendor_error = ensure_model_viewer()
    server = StudioHTTPServer((host, args.port), StudioHandler, args.jobs_root.resolve())

    print("HAYUYA_STUDIO_READY")
    if vendor is not None:
        print(f"  viewer: cached {vendor}")
    else:
        print(f"  viewer warning: {vendor_error}")
    for url in local_addresses(args.port):
        if args.lan or "127.0.0.1" in url:
            print(f"  {url}")
    if args.lan:
        print("LAN mode exposes Studio to devices on your local network. Use a trusted network.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
