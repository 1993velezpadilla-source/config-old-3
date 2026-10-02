#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, sys, time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from PIL import Image, ImageFile
from gradio_client import Client, handle_file
from mesh_gate import inspect as inspect_mesh_gate
from rig_gate import inspect as inspect_rig_gate
from texture_gate import inspect as inspect_texture_gate
from trellis2_cloud import generate as generate_trellis2_cloud
from trellis2_preview_recovery import recover as recover_trellis2_preview
from trellis2_preview_normal_hero import build_normal_informed_hero
from triposg_cloud import generate as generate_triposg_cloud
from detailgen3d_cloud import refine as refine_detailgen3d_cloud
from hunyuan3d_cloud import generate_shape as generate_hunyuan3d_shape
from triposr_cpu_cloud import generate as generate_triposr_cpu_cloud
from local_detail_fusion import fuse_local_basecolor
from source_autofix import build_source_autofix
from aaa_policy import assess_aaa_candidate

ImageFile.LOAD_TRUNCATED_IMAGES = True

GEOMETRY = Path(os.environ["HAYUYA_GEOMETRY_INPUT"])
REFERENCE_DIR_RAW = os.environ.get("HAYUYA_REFERENCE_DIR","").strip()
DETAIL_DIR_RAW = os.environ.get("HAYUYA_DETAIL_DIR","").strip()
REFERENCE_DIR = Path(REFERENCE_DIR_RAW) if REFERENCE_DIR_RAW else None
DETAIL_DIR = Path(DETAIL_DIR_RAW) if DETAIL_DIR_RAW else None
OUT = Path(os.environ.get("HAYUYA_OUTPUT_ROOT","out/hayuya-phone-cloud"))
JOB = os.environ.get("HAYUYA_JOB_ID","hayuya-phone")
ASSET_PROFILE = os.environ.get("HAYUYA_ASSET_PROFILE","auto").strip() or "auto"
WEAPON_FAMILY = os.environ.get("HAYUYA_WEAPON_FAMILY","auto").strip() or "auto"
ANIMATION_REQUESTED = os.environ.get("HAYUYA_ANIMATION_REQUESTED","false").strip().lower() in {"1","true","yes","on"}
MOTION_PROFILE = os.environ.get("HAYUYA_MOTION_PROFILE","auto").strip() or "auto"
TEXTURE_QUALITY = os.environ.get("HAYUYA_TEXTURE_QUALITY","standard").strip() or "standard"
TOKEN = os.environ.get("HF_TOKEN","").strip() or None
print(
    "HAYUYA_HF_AUTH",
    json.dumps({"token_present": bool(TOKEN)}, separators=(",",":")),
)
BACKENDS = [
    x.strip().lower()
    for x in os.environ.get(
        "HAYUYA_BACKENDS",
        "triposg,trellis2,trellis,instantmesh,triposr",
    ).split(",")
    if x.strip()
]
TRELLIS2_ENABLED = "trellis2" in BACKENDS
TRIPOSG_CLOUD_ENABLED = "triposg" in BACKENDS
DETAILGEN3D_ENABLED = "detailgen3d" in BACKENDS
HUNYUAN3D_ENABLED = any(
    x in BACKENDS for x in {"hunyuan3d","hunyuan3d_2_1"}
)
CLASSIC_TRELLIS_ENABLED = "trellis" in BACKENDS
TRIPOSR_CPU_ENABLED = "triposr" in BACKENDS
STRICT_TRELLIS2 = BACKENDS == ["trellis2"]
SPACE_URL = os.environ.get("TRELLIS_URL","https://trellis-community-trellis.hf.space")
TRELLIS2_SPACE = os.environ.get("TRELLIS2_SPACE","microsoft/TRELLIS.2")
OUT.mkdir(parents=True, exist_ok=True)
PREP = OUT / "prepared_views"
PREP.mkdir(parents=True, exist_ok=True)
DETAIL_PREP = OUT / "prepared_details"
DETAIL_PREP.mkdir(parents=True, exist_ok=True)

QUALITY_TARGETS={"preview":768,"standard":1024,"high":2048,"ultra":2048}
PREP_TARGET=QUALITY_TARGETS.get(TEXTURE_QUALITY,1024)
IMAGE_EXTS={".png",".jpg",".jpeg",".webp",".bmp"}

def fail(msg):
    try:
        (OUT/"failure_reason.txt").write_text(str(msg).strip()+"\n", encoding="utf-8")
    except Exception:
        pass
    print(f"::error::{msg}")
    raise SystemExit(1)

if not GEOMETRY.is_file():
    fail(f"Missing primary reference: {GEOMETRY}")

# HAYUYA phone/cloud mode accepts a single image or a wide multi-view sheet.
# IMPORTANT: preserve alpha. Some generated PNGs are palette images (P mode) with
# tRNS transparency; converting those directly to RGB turns the transparent area
# into a solid palette color and TRELLIS reconstructs that background as geometry.
def has_useful_alpha(image):
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    lo, hi = image.getchannel("A").getextrema()
    return lo < 250 and hi > 0

def prepare_view(image, dst, *, target=1024):
    rgba = image.convert("RGBA")
    useful_alpha = has_useful_alpha(rgba)

    if useful_alpha:
        alpha = rgba.getchannel("A")
        mask = alpha.point(lambda v: 255 if v > 8 else 0)
        bbox = mask.getbbox()
        if bbox:
            l, t, r, b = bbox
            span = max(r-l, b-t)
            pad = max(8, round(span * 0.06))
            l=max(0,l-pad); t=max(0,t-pad)
            r=min(rgba.width,r+pad); b=min(rgba.height,b+pad)
            rgba = rgba.crop((l,t,r,b))

        # Give the object breathing room and center it on transparent canvas.
        side=max(rgba.width,rgba.height)
        margin=max(8,round(side*0.08))
        canvas=Image.new("RGBA",(side+margin*2,side+margin*2),(0,0,0,0))
        x=(canvas.width-rgba.width)//2
        y=(canvas.height-rgba.height)//2
        canvas.alpha_composite(rgba,(x,y))
        rgba=canvas.resize((target,target),Image.Resampling.LANCZOS)
        rgba.save(dst,"PNG",optimize=True)
    else:
        # No reliable alpha: keep RGB and let TRELLIS/rembg do its own removal.
        rgb=rgba.convert("RGB")
        scale=min(1.0,target/max(rgb.width,rgb.height))
        if scale < 1.0:
            rgb=rgb.resize((max(1,round(rgb.width*scale)),max(1,round(rgb.height*scale))),Image.Resampling.LANCZOS)
        rgb.save(dst,"PNG",optimize=True)

    with Image.open(dst) as check:
        check.load()
        alpha_fraction=None
        if check.mode=="RGBA":
            a=check.getchannel("A")
            hist=a.histogram()
            alpha_fraction=1.0-(hist[255]/float(check.width*check.height))
        print(
            "HAYUYA_VIEW_READY",
            dst.stem,
            dst,
            check.size,
            "mode="+check.mode,
            "alpha_fraction="+("none" if alpha_fraction is None else f"{alpha_fraction:.4f}")
        )
    return dst

with Image.open(GEOMETRY) as source:
    source.load()
    source_mode=source.mode
    source_info=dict(source.info)
    source_rgba=source.convert("RGBA")
    source_had_alpha=has_useful_alpha(source_rgba)
    w,h=source_rgba.size
    print(
        "HAYUYA_SOURCE",
        GEOMETRY,
        "mode="+source_mode,
        "size="+f"{w}x{h}",
        "palette_transparency="+str("transparency" in source_info),
        "useful_alpha="+str(source_had_alpha)
    )

    # Reject a known catastrophic input class before spending GPU quota:
    # palette+tRNS files where one almost-opaque fill color dominates the
    # visible image. This is what produced the Candyland "cross of planes".
    if source_mode == "P" and "transparency" in source_info:
        probe=source_rgba.resize((min(256,w), max(1,round(h*min(256,w)/w))), Image.Resampling.NEAREST)
        visible=[px for px in probe.getdata() if px[3] > 16]
        if visible:
            rgba_count, rgba_n = Counter(visible).most_common(1)[0]
            dominant_ratio = rgba_n / len(visible)
            print("HAYUYA_PALETTE_DIAGNOSTIC", "dominant_ratio="+f"{dominant_ratio:.4f}", "rgba="+str(rgba_count))
            if dominant_ratio > 0.35:
                fail(
                    "Rejected corrupt/suspicious palette+tRNS source before GPU generation: "
                    f"one visible RGBA value occupies {dominant_ratio:.1%} of the foreground. "
                    "Replace the source with the original RGB/RGBA reference."
                )

    if w >= int(h*1.25):
        # Legacy/reference-sheet path: recover the four body panels from the left
        # ~76% of the sheet and preserve transparency inside each crop.
        x0=0
        x1=int(w*0.76)
        y0=int(h*0.08)
        y1=int(h*0.96)
        span=x1-x0
        names=["front","side","back","three_quarter"]
        crops=[]
        for i,name in enumerate(names):
            a=x0+int(span*i/4)
            b=x0+int(span*(i+1)/4)
            pad=int(span*0.025)
            a=max(x0,a-pad); b=min(x1,b+pad)
            crop=source_rgba.crop((a,y0,b,y1))
            dst=PREP/f"{name}.png"
            crops.append(prepare_view(crop,dst,target=PREP_TARGET))
    else:
        dst=PREP/"front.png"
        crops=[prepare_view(source_rgba,dst,target=PREP_TARGET)]

# Native multi-image mode: a user/project may provide independent views instead
# of baking them into one contact sheet. Keep the primary geometry reference
# first, then add up to seven extra views. This preserves perspective evidence
# far better than asking a single image to invent the unseen side/back.
if REFERENCE_DIR and REFERENCE_DIR.is_dir():
    extras=[]
    for p in sorted(REFERENCE_DIR.iterdir()):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            with Image.open(p) as im:
                im.load()
                dst=PREP/f"view_{len(extras)+2:02d}.png"
                extras.append(prepare_view(im,dst,target=PREP_TARGET))
        except Exception as exc:
            print(f"::warning::Skipping reference {p}: {type(exc).__name__}: {exc}")
        if len(extras)>=7:
            break
    crops.extend(extras)

# Detail/face/material crops are intentionally NOT mixed into geometry views:
# closeups have incompatible camera scale and can warp the reconstructed body.
# We still normalize/preserve them for the subsequent texture/detail refinement
# stage and expose them in the manifest.
detail_views=[]
source_autofix_result=None
source_autofix_failure=None

# One-photo-first cloud path: derive head/face evidence from the primary source.
# This is auxiliary evidence only; it is never mixed into geometry/multiview input.
if ASSET_PROFILE in {"auto","character.humanoid","character.creature"}:
    try:
        source_autofix_result=build_source_autofix(
            [GEOMETRY],
            OUT/"source_autofix",
            policy="auto",
        )
        for raw in source_autofix_result.derived_detail_sources:
            p=Path(raw)
            if not p.is_file() or len(detail_views)>=12:
                continue
            with Image.open(p) as im:
                im.load()
                dst=DETAIL_PREP/f"detail_{len(detail_views)+1:02d}_auto_head.png"
                detail_views.append(prepare_view(im,dst,target=PREP_TARGET))
        if ASSET_PROFILE == "auto" and source_autofix_result.character_hint:
            ASSET_PROFILE = "character.humanoid"
            print(
                "HAYUYA_CONTENT_CLASSIFICATION",
                "asset_profile=character.humanoid",
                "reason=source_autofix_face_or_pose",
            )
        print(
            "HAYUYA_PHONE_SOURCE_AUTOFIX",
            "derived="+str(len(source_autofix_result.derived_detail_sources)),
            "character_hint="+str(bool(source_autofix_result.character_hint)).lower(),
            "asset_profile="+ASSET_PROFILE,
            "manifest="+str(source_autofix_result.manifest),
        )
    except Exception as exc:
        source_autofix_failure=f"{type(exc).__name__}: {exc}"
        print(f"::warning::HAYUYA phone source autofix failed: {source_autofix_failure}")

# User-supplied closeups remain optional enhancements.
if DETAIL_DIR and DETAIL_DIR.is_dir():
    for p in sorted(DETAIL_DIR.iterdir()):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            with Image.open(p) as im:
                im.load()
                dst=DETAIL_PREP/f"detail_{len(detail_views)+1:02d}.png"
                detail_views.append(prepare_view(im,dst,target=PREP_TARGET))
        except Exception as exc:
            print(f"::warning::Skipping detail reference {p}: {type(exc).__name__}: {exc}")
        if len(detail_views)>=12:
            break

# If only one view exists, TRELLIS runs its true single-image path.
multi=len(crops) >= 2
print("HAYUYA_REFERENCE_SET",
      "geometry_views="+str(len(crops)),
      "detail_views="+str(len(detail_views)),
      "prep_target="+str(PREP_TARGET))

quality_presets={
    # TRELLIS' "simplify" argument is the fraction of triangles REMOVED, not
    # retained. The public UI exposes 0.90..0.98, so even its best visible
    # setting removes 90% of the extracted mesh. HAYUYA keeps a safe fallback
    # but first asks the backend function for a denser master when quality is
    # High/Ultra.
    "preview":{"ss_steps":10,"slat_steps":10,"mesh_simplify":0.95,"texture_size":1024},
    "standard":{"ss_steps":12,"slat_steps":12,"mesh_simplify":0.90,"texture_size":2048},
    "high":{"ss_steps":16,"slat_steps":16,"mesh_simplify":0.70,"texture_size":4096},
    "ultra":{"ss_steps":20,"slat_steps":20,"mesh_simplify":0.40,"texture_size":4096},
}
qp=quality_presets.get(TEXTURE_QUALITY,quality_presets["standard"])

retry_events=[]
client=None
processed=[]
params=[]
args=[]
values={}
endpoint=None

def _transient_cloud_error(exc):
    text=(f"{type(exc).__name__}: {exc}").lower()
    markers=(
        "zerogpu quota",
        "exceeded your zerogpu quota",
        "try again in",
        "rate limit",
        "too many requests",
        "queue full",
        "temporarily unavailable",
        "service unavailable",
        "http 429",
        "status code 429",
    )
    return any(m in text for m in markers)

def _record_retry(stage, attempt, delay, exc):
    event={
        "stage":stage,
        "attempt":attempt,
        "delay_seconds":delay,
        "error":f"{type(exc).__name__}: {exc}",
        "time":time.time(),
    }
    retry_events.append(event)
    try:
        (OUT/"cloud_retry_state.json").write_text(
            json.dumps({
                "schema":1,
                "job_id":JOB,
                "status":"retrying",
                "events":retry_events,
            },indent=2)+"\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    print(
        f"::warning::HAYUYA transient cloud error during {stage}; "
        f"retry {attempt} in {delay}s: {type(exc).__name__}: {exc}"
    )

def resilient_predict(*call_args, api_name, stage, max_attempts=5):
    if client is None:
        raise RuntimeError("classic TRELLIS client is disabled")
    delays=(20,35,55,75)
    for attempt in range(1,max_attempts+1):
        try:
            return client.predict(*call_args,api_name=api_name)
        except Exception as exc:
            if attempt>=max_attempts or not _transient_cloud_error(exc):
                raise
            delay=delays[min(attempt-1,len(delays)-1)]
            _record_retry(stage,attempt,delay,exc)
            time.sleep(delay)
            try:
                client.predict(api_name="/start_session")
            except Exception as session_exc:
                print(
                    f"::warning::TRELLIS session refresh after retry: "
                    f"{type(session_exc).__name__}: {session_exc}"
                )
    raise RuntimeError(f"{stage} exhausted retry loop")

def uploadable(v):
    if isinstance(v,str):
        p=Path(v)
        return handle_file(str(p)) if p.exists() else v
    if isinstance(v,dict):
        p=v.get("path")
        if isinstance(p,str) and Path(p).exists():
            return handle_file(p)
    return v

if CLASSIC_TRELLIS_ENABLED:
    last=None
    for attempt in range(1,6):
        try:
            kwargs={"verbose":True,"httpx_kwargs":{"timeout":120.0}}
            if TOKEN:
                kwargs["token"]=TOKEN
            client=Client(SPACE_URL,**kwargs)
            print("HAYUYA_TRELLIS_CONNECTED",attempt)
            break
        except Exception as e:
            last=e
            print(f"::warning::TRELLIS connect {attempt}/5 failed: {type(e).__name__}: {e}")
            if attempt<5:
                time.sleep(15*attempt)
    if client is None:
        fail(f"Unable to connect to public TRELLIS ZeroGPU: {last}")

    try:
        resilient_predict(api_name="/start_session",stage="start_session",max_attempts=3)
    except Exception as e:
        print(f"::warning::start_session: {type(e).__name__}: {e}")

    if multi:
        try:
            resilient_predict(api_name="/lambda_1",stage="enable_multiimage",max_attempts=4)
            print("HAYUYA_MULTIIMAGE_STATE_ENABLED")
        except Exception as e:
            fail(f"Could not enable multi-image mode: {type(e).__name__}: {e}")

    for p in crops:
        try:
            v=resilient_predict(
                handle_file(str(p)),
                api_name="/preprocess_image",
                stage=f"preprocess:{p.name}",
                max_attempts=4,
            )
            processed.append(uploadable(v))
            print("HAYUYA_PREPROCESS_PASS",p.name)
        except Exception as e:
            fail(f"preprocess failed for {p.name}: {type(e).__name__}: {e}")

    api=client.view_api(print_info=False,return_format="dict")
    named=api.get("named_endpoints",{})
    spec=named.get("/generate_and_extract_glb")
    if not spec:
        key=next((k for k in named if "generate_and_extract_glb" in k),None)
        if key:
            spec=named[key]
        else:
            fail(f"TRELLIS GLB endpoint unavailable: {list(named)}")
        endpoint=key
    else:
        endpoint="/generate_and_extract_glb"

    params=[p.get("parameter_name") for p in spec.get("parameters",[])]
    front=processed[0]
    gallery=[{"image":v,"caption":None} for v in processed]
    values={
        "image":front,
        "multiimages":gallery,
        "seed":1993,
        "ss_guidance_strength":7.5,
        "ss_sampling_steps":qp["ss_steps"],
        "slat_guidance_strength":3.0,
        "slat_sampling_steps":qp["slat_steps"],
        "multiimage_algo":"multidiffusion",
        "mesh_simplify":qp["mesh_simplify"],
        "texture_size":qp["texture_size"],
    }
    missing=[p for p in params if p not in values]
    if missing:
        fail(f"Unhandled TRELLIS parameters: {missing}")
    args=[values[p] for p in params]
    print("HAYUYA_TRELLIS_SUBMIT",JOB,endpoint,params)
else:
    print(
        "HAYUYA_CLASSIC_TRELLIS_SKIPPED",
        "requested_backends="+",".join(BACKENDS),
    )

extraction_fallback=None
actual_mesh_simplify=qp["mesh_simplify"]
actual_texture_size=qp["texture_size"]
selected_generator="trellis-community/TRELLIS"
selected_compute="GitHub-hosted CPU controller + public TRELLIS ZeroGPU"
modern_candidate=None
preview_recovery_candidate=None
preview_normal_hero_report=None
preview_recovery_face_rescue_required=False
preview_recovery_face_rescue_reason=None
hero_master_report=None

# Modern single-image authority. TRELLIS.2 is deliberately not used to replace
# classic TRELLIS native multi-image fusion: with 2+ real geometry views the
# camera evidence is more valuable than forcing a single-image model.
if not multi and TRELLIS2_ENABLED and TEXTURE_QUALITY in {"high","ultra"}:
    try:
        modern_meta=generate_trellis2_cloud(
            crops[0],
            OUT/"trellis2_candidate.glb",
            token=TOKEN,
            quality=TEXTURE_QUALITY,
            seed=1993,
            space=TRELLIS2_SPACE,
        )
        modern_candidate=Path(modern_meta["path"])
        modern_min_texture_edge=4096 if TEXTURE_QUALITY=="ultra" else 2048
        modern_mesh=inspect_mesh_gate(modern_candidate,require_normals=True)
        modern_tex=inspect_texture_gate(
            modern_candidate,min_edge=modern_min_texture_edge
        )
        print("HAYUYA_TRELLIS2_MESH_GATE",json.dumps(asdict(modern_mesh),separators=(",",":")))
        print("HAYUYA_TRELLIS2_TEXTURE_GATE",json.dumps(asdict(modern_tex),separators=(",",":")))
        if not modern_mesh.passed or not modern_tex.passed:
            raise RuntimeError(
                "TRELLIS.2 challenger failed HAYUYA hard gates: "
                +"; ".join(list(modern_mesh.reasons)+list(modern_tex.warnings))
            )

        # Dense-first contract. A syntactically healthy 300k/500k mesh is no
        # longer enough for high-end characters: preserve a Hero Master first,
        # then let later HAYUYA stages retopologize/LOD it for runtime.
        hero_floor=int(modern_meta.get("hero_master_min_faces",0) or 0)
        hero_target=int(
            modern_meta.get("hero_master_target_faces")
            or modern_meta.get("faces_target")
            or 0
        )
        # The official public TRELLIS.2 Space currently caps GLB export at
        # 500k faces. Treat a provider-capped native extraction as a valid coarse
        # high-end candidate, not as the final Hero Master. Open TripoSG and
        # DetailGen3D challengers below are responsible for the dense/refined
        # master before runtime optimization.
        provider_capped=bool(
            modern_meta.get("hero_master_requires_refinement")
            or (hero_floor and int(modern_mesh.faces)<hero_floor)
        )
        hero_master_report={
            "schema":1,
            "policy":"dense-first-fidelity-before-retopo",
            "generator":modern_meta.get("generator"),
            "target_faces":hero_target,
            "minimum_faces":hero_floor,
            "actual_faces":int(modern_mesh.faces),
            "actual_vertices":int(modern_mesh.vertices),
            "dense_master_ready":bool(
                modern_mesh.passed
                and modern_tex.passed
                and not provider_capped
            ),
            "provider_capped":provider_capped,
            "provider_extract_cap_faces":modern_meta.get("provider_extract_cap_faces"),
            "refinement_required":provider_capped,
            "optimization_deferred":True,
            "runtime_optimization_stage":"post-fidelity-gate",
        }
        print(
            "HAYUYA_HERO_MASTER_PROVISIONAL" if provider_capped else "HAYUYA_HERO_MASTER_READY",
            json.dumps(hero_master_report,separators=(",",":")),
        )
        selected_generator=modern_meta["generator"]
        selected_compute="GitHub-hosted CPU controller + official public TRELLIS.2 GPU Space"
        actual_mesh_simplify=None
        actual_texture_size=int(modern_meta["texture_size"])
        result=str(modern_candidate)
        print("HAYUYA_TRELLIS2_PROMOTED",json.dumps(modern_meta,separators=(",",":")))
    except Exception as modern_exc:
        modern_candidate=None
        modern_text=f"{type(modern_exc).__name__}: {modern_exc}"
        quota_blocked=(
            "zerogpu quota" in modern_text.lower()
            or "exceeded your zerogpu quota" in modern_text.lower()
            or ("more quota" in modern_text.lower() and "hugging face token" in modern_text.lower())
        )
        if quota_blocked:
            # Generation already succeeded and the official Space preserved 48
            # static turntable frames (Normal / Clay / Base Color / HDRI). Recover
            # a CPU visual hull from the exact 8 TRELLIS.2 cameras before trying
            # a different generator. The recovered GLB must pass the same mesh and
            # real embedded-texture gates; no gate is relaxed for this path.
            preview_html=OUT/"trellis2_candidate.preview.html"
            if preview_html.is_file():
                try:
                    recovered_meta=recover_trellis2_preview(
                        preview_html,
                        OUT/"trellis2_preview_recovered.glb",
                        grid_resolution=224 if TEXTURE_QUALITY in {"high","ultra"} else 192,
                        texture_size=2048 if TEXTURE_QUALITY in {"high","ultra"} else 1024,
                        face_target=125000 if TEXTURE_QUALITY=="ultra" else 120000,
                    )
                    recovered_candidate=Path(recovered_meta["path"])
                    recovered_mesh_report=inspect_mesh_gate(
                        recovered_candidate,
                        require_normals=False,
                    )
                    recovered_texture_report=inspect_texture_gate(
                        recovered_candidate,
                        min_edge=int(recovered_meta["texture_size"]),
                        min_base_color_edge=int(recovered_meta["texture_size"]),
                    )
                    if not recovered_mesh_report.passed:
                        raise RuntimeError(
                            "TRELLIS.2 preview recovery mesh gate failed: "
                            + json.dumps(asdict(recovered_mesh_report),separators=(",",":"))
                        )
                    if not recovered_texture_report.passed:
                        raise RuntimeError(
                            "TRELLIS.2 preview recovery texture gate failed: "
                            + json.dumps(asdict(recovered_texture_report),separators=(",",":"))
                        )
                    # A preview-recovered visual hull is only an approximation
                    # of TRELLIS.2's static turntable, not the native latent mesh. It
                    # may be used provisionally, but face-critical characters are not
                    # allowed to leave this worker until the downstream seam-limited
                    # head-geometry rescue has actually produced a Judge-ready mesh.
                    modern_candidate=recovered_candidate
                    preview_recovery_candidate=recovered_candidate
                    selected_generator=recovered_meta["generator"]
                    selected_compute=recovered_meta["compute"]
                    actual_mesh_simplify=0.0
                    actual_texture_size=int(recovered_meta["texture_size"])
                    result=str(modern_candidate)
                    is_character_asset=ASSET_PROFILE in {
                        "auto","character.humanoid","character.creature"
                    }
                    if is_character_asset and detail_views:
                        preview_recovery_face_rescue_required=True
                        preview_recovery_face_rescue_reason=(
                            "approximate_visual_hull_requires_face_geometry_rescue"
                        )
                        print(
                            "HAYUYA_TRELLIS2_PREVIEW_RECOVERY_PROVISIONAL",
                            json.dumps({
                                **recovered_meta,
                                "face_rescue_required":True,
                                "reason":preview_recovery_face_rescue_reason,
                                "detail_views":len(detail_views),
                            },separators=(",",":")),
                        )

                        # Ultra characters can recover substantially more of the
                        # native TRELLIS.2 surface than a silhouette hull because
                        # the preserved preview also contains eight exact
                        # camera-space normal renders. Integrate those normals into
                        # visible-surface depth, refine the textured hull, and
                        # subdivide the refined topology to the 2M Hero ceiling.
                        # This remains explicitly non-native and must still pass
                        # downstream visual/anatomy Judge gates.
                        if TEXTURE_QUALITY=="ultra":
                            try:
                                preview_normal_hero_report=build_normal_informed_hero(
                                    preview_html,
                                    recovered_candidate,
                                    OUT/"trellis2_preview_normal_hero.glb",
                                    normal_resolution=256,
                                    subdivision_levels=2,
                                    max_faces=2_000_000,
                                )
                                normal_candidate=Path(
                                    preview_normal_hero_report["path"]
                                )
                                normal_mesh=inspect_mesh_gate(
                                    normal_candidate,
                                    require_normals=False,
                                )
                                normal_texture=inspect_texture_gate(
                                    normal_candidate,
                                    min_edge=4096,
                                    min_base_color_edge=4096,
                                )
                                print(
                                    "HAYUYA_TRELLIS2_PREVIEW_NORMAL_HERO_MESH_GATE",
                                    json.dumps(asdict(normal_mesh),separators=(",",":")),
                                )
                                print(
                                    "HAYUYA_TRELLIS2_PREVIEW_NORMAL_HERO_TEXTURE_GATE",
                                    json.dumps(asdict(normal_texture),separators=(",",":")),
                                )
                                if (
                                    not normal_mesh.passed
                                    or not normal_texture.passed
                                    or int(normal_mesh.faces)<1_000_000
                                    or int(normal_mesh.faces)>2_000_000
                                ):
                                    raise RuntimeError(
                                        "normal-informed Hero failed hard gates: "
                                        +json.dumps({
                                            "mesh":asdict(normal_mesh),
                                            "texture":asdict(normal_texture),
                                        },separators=(",",":"))
                                    )

                                modern_candidate=normal_candidate
                                preview_recovery_candidate=normal_candidate
                                selected_generator=preview_normal_hero_report["generator"]
                                selected_compute=preview_normal_hero_report["compute"]
                                actual_mesh_simplify=0.0
                                actual_texture_size=4096
                                result=str(modern_candidate)
                                preview_recovery_face_rescue_required=False
                                preview_recovery_face_rescue_reason=(
                                    "visible_surface_geometry_recovered_from_exact_"
                                    "trellis2_camera_space_normals"
                                )
                                hero_master_report={
                                    "schema":1,
                                    "policy":"dense-normal-informed-preview-before-retopo",
                                    "generator":selected_generator,
                                    "target_faces":2_000_000,
                                    "minimum_faces":1_000_000,
                                    "actual_faces":int(normal_mesh.faces),
                                    "actual_vertices":int(normal_mesh.vertices),
                                    "dense_master_ready":False,
                                    "candidate_ready_for_judge":True,
                                    "production_eligible":False,
                                    "normal_informed":True,
                                    "native_latent_extraction":False,
                                    "approximation":preview_normal_hero_report.get("approximation"),
                                    "optimization_deferred":True,
                                    "runtime_optimization_stage":"post-Judge-v4",
                                }
                                print(
                                    "HAYUYA_TRELLIS2_PREVIEW_NORMAL_HERO_PROMOTED",
                                    json.dumps(hero_master_report,separators=(",",":")),
                                )
                            except Exception as normal_hero_exc:
                                preview_normal_hero_report={
                                    "passed":False,
                                    "error":(
                                        f"{type(normal_hero_exc).__name__}: "
                                        f"{normal_hero_exc}"
                                    ),
                                }
                                print(
                                    "::warning::TRELLIS.2 normal-informed Hero "
                                    "challenger unavailable/rejected; retaining "
                                    "mandatory face-geometry rescue: "
                                    +preview_normal_hero_report["error"]
                                )
                    else:
                        print(
                            "HAYUYA_TRELLIS2_PREVIEW_RECOVERY_PROMOTED",
                            json.dumps(recovered_meta,separators=(",",":")),
                        )
                except Exception as recovery_exc:
                    print(
                        "::warning::TRELLIS.2 preview recovery failed; "
                        "keeping native generation checkpoint and trying the "
                        "explicit continuity backend: "
                        f"{type(recovery_exc).__name__}: {recovery_exc}"
                    )

            # TRELLIS classic shares the exhausted ZeroGPU quota. TripoSR remains
            # last-resort continuity only when preview recovery was unavailable.
            if modern_candidate is None and TRIPOSR_CPU_ENABLED:
                try:
                    cpu_meta=generate_triposr_cpu_cloud(
                        crops[0],
                        OUT/"triposr_cpu_candidate.glb",
                        token=TOKEN,
                    )
                    modern_candidate=Path(cpu_meta["path"])
                    selected_generator=cpu_meta["generator"]
                    selected_compute=cpu_meta["compute"]
                    actual_mesh_simplify=None
                    actual_texture_size=0
                    result=str(modern_candidate)
                    print(
                        "HAYUYA_TRIPOSR_CPU_CONTINUITY_CANDIDATE",
                        json.dumps(cpu_meta,separators=(",",":")),
                    )
                except Exception as cpu_exc:
                    fail(
                        "TRELLIS.2 generation completed but GLB extraction is "
                        "blocked by Hugging Face ZeroGPU quota. TRELLIS.2 "
                        "checkpoint is preserved, preview recovery failed, and "
                        "the free CPU TripoSR continuity candidate also failed: "
                        f"{type(cpu_exc).__name__}: {cpu_exc}. Provider error: "
                        + modern_text
                    )
            elif modern_candidate is None:
                fail(
                    "TRELLIS.2 generation completed but GLB extraction is blocked "
                    "by Hugging Face ZeroGPU quota. Generation checkpoint preserved "
                    "in outputs; preview recovery did not produce an accepted GLB. "
                    "Provider error: " + modern_text
                )
        if STRICT_TRELLIS2 and modern_candidate is None:
            fail(
                "TRELLIS.2 is the required generator for this job and did not "
                "produce an accepted candidate: "
                + modern_text
            )
        if modern_candidate is None:
            print(
                "::warning::TRELLIS.2 challenger unavailable/rejected; "
                "falling back to classic TRELLIS: "
                + modern_text
            )

current_aaa_eligibility = assess_aaa_candidate(
    generator=selected_generator,
    hero_master=hero_master_report,
    texture_quality=TEXTURE_QUALITY,
)
hosted_refinement_needed = not current_aaa_eligibility.eligible
# Ultra/High hosted refinement without an authenticated HF identity has proven
# unreliable (ZeroGPU quota / duration failures). Never wait on anonymous
# hosted retries once a diagnostic candidate already exists; either an
# authenticated native/model candidate replaces it or HAYUYA fails closed.
hosted_vast_allowed = bool(TOKEN)
if not hosted_vast_allowed and (
    TRIPOSG_CLOUD_ENABLED or DETAILGEN3D_ENABLED
):
    print(
        "HAYUYA_HOSTED_VAST_SKIPPED",
        json.dumps(
            {
                "reason":"2m_judge_candidate_ready_and_hf_token_absent",
                "triposg_requested":TRIPOSG_CLOUD_ENABLED,
                "detailgen3d_requested":DETAILGEN3D_ENABLED,
            },
            separators=(",",":"),
        ),
    )

# Hunyuan3D-2.1 is a true model-generated shape candidate. It may enter
# fidelity/anatomy Judge even when below the nominal 2M Ultra density target;
# polygon count is telemetry, not a substitute for shape quality. For now its
# public model license remains a separate distribution gate, so technical Judge
# success does not automatically imply production redistribution approval.
if (
    not multi
    and HUNYUAN3D_ENABLED
    and TEXTURE_QUALITY in {"high","ultra"}
):
    try:
        hunyuan_meta=generate_hunyuan3d_shape(
            crops[0],
            OUT/"hunyuan3d_native_geometry.glb",
            token=TOKEN,
            seed=1993,
            steps=30,
            guidance_scale=5.0,
            # Native Hunyuan 512 is validated on Monja at ~1.58M faces and
            # preserves coherent topology. Ultra uses the model's real decode
            # resolution instead of manufacturing density by subdivision.
            octree_resolution=512 if TEXTURE_QUALITY=="ultra" else 384,
            num_chunks=8000,
        )
        hunyuan_geometry=Path(hunyuan_meta["path"])
        hunyuan_candidate=hunyuan_geometry
        material_bridge_report=None

        # Hunyuan's public shape endpoint is geometry-only. Reuse trustworthy
        # material evidence from the best existing source-derived candidate
        # without altering Hunyuan geometry.
        if modern_candidate is not None:
            from material_bridge import transfer_best_material
            bridged=OUT/"hunyuan3d_native_candidate.glb"

            # Never force the Material Bridge to repack the 2M diagnostic Hero
            # merely to reuse its atlas. The normal-informed builder already
            # emits a compact material-source GLB carrying the exact same 4K
            # source-derived material evidence. Using that donor preserves the
            # texture evidence while avoiding million-vertex atlas packing.
            material_donor=modern_candidate
            if isinstance(preview_normal_hero_report,dict):
                compact_source=preview_normal_hero_report.get("material_source_glb")
                if compact_source and Path(compact_source).is_file():
                    material_donor=Path(compact_source)
            print(
                "HAYUYA_HUNYUAN3D_MATERIAL_DONOR",
                json.dumps({
                    "path":str(material_donor),
                    "bytes":int(Path(material_donor).stat().st_size),
                    "compact":bool(Path(material_donor)!=Path(modern_candidate)),
                },separators=(",",":")),
            )
            bridge=transfer_best_material(
                material_donor,
                hunyuan_geometry,
                bridged,
                total_samples=500_000,
                max_texture_size=4096 if TEXTURE_QUALITY=="ultra" else 2048,
            )
            hunyuan_candidate=bridged
            material_bridge_report=asdict(bridge)
            print(
                "HAYUYA_HUNYUAN3D_MATERIAL_BRIDGE_PASS",
                json.dumps(material_bridge_report,separators=(",",":")),
            )

        hunyuan_mesh=inspect_mesh_gate(hunyuan_candidate,require_normals=False)
        print(
            "HAYUYA_HUNYUAN3D_NATIVE_MESH_GATE",
            json.dumps(asdict(hunyuan_mesh),separators=(",",":")),
        )
        if not hunyuan_mesh.passed:
            raise RuntimeError(
                "Hunyuan3D native candidate failed mesh gate: "
                +"; ".join(hunyuan_mesh.reasons)
            )

        hunyuan_tex=None
        if material_bridge_report is not None:
            hunyuan_tex=inspect_texture_gate(
                hunyuan_candidate,
                min_edge=4096 if TEXTURE_QUALITY=="ultra" else 2048,
            )
            print(
                "HAYUYA_HUNYUAN3D_NATIVE_TEXTURE_GATE",
                json.dumps(asdict(hunyuan_tex),separators=(",",":")),
            )
            if not hunyuan_tex.passed:
                raise RuntimeError(
                    "Hunyuan3D native material bridge failed texture gate: "
                    +"; ".join(hunyuan_tex.warnings)
                )

        if material_bridge_report is not None:
            modern_candidate=hunyuan_candidate
            result=str(modern_candidate)
            selected_generator="tencent/Hunyuan3D-2.1"
            selected_compute="public Hunyuan3D-2.1 model-generated geometry + HAYUYA material bridge"
            actual_mesh_simplify=0.0
            actual_texture_size=4096 if TEXTURE_QUALITY=="ultra" else 2048
            hero_target=2_000_000 if TEXTURE_QUALITY=="ultra" else 1_250_000
            hero_floor=1_000_000 if TEXTURE_QUALITY=="ultra" else 650_000
            hero_master_report={
                "schema":1,
                "policy":"native-model-generated-fidelity-before-density",
                "generator":selected_generator,
                "target_faces":hero_target,
                "minimum_faces":hero_floor,
                "actual_faces":int(hunyuan_mesh.faces),
                "actual_vertices":int(hunyuan_mesh.vertices),
                "dense_master_ready":True,
                "density_target_met":bool(int(hunyuan_mesh.faces)>=hero_floor),
                "provider_capped":False,
                "refinement_required":False,
                "native_model_generated_geometry":True,
                "material_bridge":material_bridge_report,
                "optimization_deferred":True,
                "runtime_optimization_stage":"post-Judge-v4",
                "license_review_required":True,
                "distribution_eligible":False,
                "license_note":hunyuan_meta.get("license_policy"),
            }
            print(
                "HAYUYA_HUNYUAN3D_NATIVE_PROMOTED_TO_JUDGE",
                json.dumps(hero_master_report,separators=(",",":")),
            )
        else:
            print(
                "::warning::Hunyuan3D native geometry generated but no material "
                "source was available; preserving it as geometry evidence only."
            )
    except Exception as hunyuan_exc:
        print(
            "::warning::Hunyuan3D native challenger unavailable/rejected: "
            f"{type(hunyuan_exc).__name__}: {hunyuan_exc}"
        )

# VAST's public TripoSG Space exposes the same open model family we already
# vendor locally, but its UI permits simplification to be disabled completely.
# Use it as a dense Hero challenger instead of forcing TRELLIS.2 past its 500k
# public extraction ceiling.
if (
    not multi
    and TRIPOSG_CLOUD_ENABLED
    and hosted_vast_allowed
    and TEXTURE_QUALITY in {"high","ultra"}
):
    try:
        triposg_meta=generate_triposg_cloud(
            crops[0],
            OUT/"triposg_hero_candidate.glb",
            token=TOKEN,
            seed=1993,
            apply_texture=True,
        )
        triposg_candidate=Path(triposg_meta["path"])
        if not triposg_meta.get("textured") and modern_candidate is not None:
            try:
                from material_bridge import transfer_best_material
                bridged=OUT/"triposg_hero_candidate_material_bridge.glb"
                bridge=transfer_best_material(
                    modern_candidate,
                    triposg_candidate,
                    bridged,
                    total_samples=300_000,
                    max_texture_size=4096 if TEXTURE_QUALITY=="ultra" else 2048,
                )
                triposg_candidate=bridged
                triposg_meta["hayuya_material_bridge"]=asdict(bridge)
                triposg_meta["textured_via_hayuya_bridge"]=True
                print(
                    "HAYUYA_TRIPOSG_MATERIAL_BRIDGE_PASS",
                    json.dumps(triposg_meta["hayuya_material_bridge"],separators=(",",":")),
                )
            except Exception as bridge_exc:
                print(
                    "::warning::TripoSG raw Hero material bridge unavailable: "
                    f"{type(bridge_exc).__name__}: {bridge_exc}"
                )
        triposg_mesh=inspect_mesh_gate(triposg_candidate,require_normals=False)
        triposg_tex=inspect_texture_gate(
            triposg_candidate,
            min_edge=4096 if TEXTURE_QUALITY=="ultra" else 2048,
        )
        print(
            "HAYUYA_TRIPOSG_HERO_MESH_GATE",
            json.dumps(asdict(triposg_mesh),separators=(",",":")),
        )
        print(
            "HAYUYA_TRIPOSG_HERO_TEXTURE_GATE",
            json.dumps(asdict(triposg_tex),separators=(",",":")),
        )
        if not triposg_mesh.passed or not triposg_tex.passed:
            raise RuntimeError(
                "TripoSG Hero challenger failed HAYUYA hard gates: "
                +"; ".join(list(triposg_mesh.reasons)+list(triposg_tex.warnings))
            )

        current_faces=0
        if hero_master_report:
            current_faces=int(hero_master_report.get("actual_faces") or 0)
        # The open TripoSG candidate is unsimplified. Prefer it whenever it is
        # denser than the provider-capped TRELLIS.2 extraction, or whenever no
        # modern candidate survived at all.
        if modern_candidate is None or int(triposg_mesh.faces)>current_faces:
            modern_candidate=triposg_candidate
            result=str(modern_candidate)
            selected_generator=triposg_meta["generator"]
            selected_compute=triposg_meta["compute"]
            actual_mesh_simplify=0.0
            actual_texture_size=(
                4096 if triposg_meta.get("textured") or triposg_meta.get("textured_via_hayuya_bridge")
                else 0
            )
            hero_target=2_000_000 if TEXTURE_QUALITY=="ultra" else 1_250_000
            hero_floor=1_000_000 if TEXTURE_QUALITY=="ultra" else 650_000
            hero_master_report={
                "schema":1,
                "policy":"dense-first-fidelity-before-retopo",
                "generator":triposg_meta["generator"],
                "target_faces":hero_target,
                "minimum_faces":hero_floor,
                "actual_faces":int(triposg_mesh.faces),
                "actual_vertices":int(triposg_mesh.vertices),
                "dense_master_ready":bool(
                    int(triposg_mesh.faces)>=hero_floor
                    and triposg_mesh.passed
                    and triposg_tex.passed
                ),
                "provider_capped":False,
                "refinement_required":int(triposg_mesh.faces)<hero_floor,
                "simplified":False,
                "optimization_deferred":True,
                "runtime_optimization_stage":"post-fidelity-gate",
            }
            print(
                "HAYUYA_TRIPOSG_HERO_PROMOTED",
                json.dumps(hero_master_report,separators=(",",":")),
            )
    except Exception as triposg_exc:
        print(
            "::warning::TripoSG dense Hero challenger unavailable/rejected: "
            f"{type(triposg_exc).__name__}: {triposg_exc}"
        )

# DetailGen3D is an image-conditioned geometry enhancement model from the same
# public VAST research ecosystem. Run it on the best surviving high-end mesh,
# then reproject the source candidate's material evidence onto the new topology.
# Judge v4 remains the authority; this challenger is never accepted on topology
# count alone.
if (
    not multi
    and DETAILGEN3D_ENABLED
    and hosted_vast_allowed
    and modern_candidate is not None
    and TEXTURE_QUALITY in {"high","ultra"}
):
    try:
        from material_bridge import transfer_best_material

        detailgen_meta=refine_detailgen3d_cloud(
            crops[0],
            modern_candidate,
            OUT/"detailgen3d_refined_geometry.glb",
            token=TOKEN,
            seed=1993,
            num_inference_steps=50,
            guidance_scale=10.0,
        )
        detailgen_geometry=Path(detailgen_meta["path"])
        detailgen_textured=OUT/"detailgen3d_hero_candidate.glb"
        bridge=transfer_best_material(
            modern_candidate,
            detailgen_geometry,
            detailgen_textured,
            total_samples=300_000,
            max_texture_size=max(2048,int(actual_texture_size or 0)),
        )
        detailgen_mesh=inspect_mesh_gate(detailgen_textured,require_normals=False)
        detailgen_tex=inspect_texture_gate(
            detailgen_textured,
            min_edge=2048,
        )
        print(
            "HAYUYA_DETAILGEN3D_HERO_MESH_GATE",
            json.dumps(asdict(detailgen_mesh),separators=(",",":")),
        )
        print(
            "HAYUYA_DETAILGEN3D_HERO_TEXTURE_GATE",
            json.dumps(asdict(detailgen_tex),separators=(",",":")),
        )
        if not detailgen_mesh.passed or not detailgen_tex.passed:
            raise RuntimeError(
                "DetailGen3D Hero challenger failed HAYUYA hard gates: "
                +"; ".join(list(detailgen_mesh.reasons)+list(detailgen_tex.warnings))
            )

        # DetailGen3D is explicitly image-conditioned geometry refinement.
        # Promote it for the face/cloth Judge even when marching-cubes topology
        # is not numerically denser than the input; Judge v4 will fail closed on
        # visual/anatomical regression.
        modern_candidate=detailgen_textured
        result=str(modern_candidate)
        selected_generator="VAST-AI/TripoSG+DetailGen3D"
        selected_compute=(
            selected_compute
            +" + public VAST DetailGen3D ZeroGPU + CPU material reprojection"
        )
        actual_mesh_simplify=0.0
        if not actual_texture_size:
            actual_texture_size=2048
        hero_target=2_000_000 if TEXTURE_QUALITY=="ultra" else 1_250_000
        hero_floor=1_000_000 if TEXTURE_QUALITY=="ultra" else 650_000
        hero_master_report={
            "schema":1,
            "policy":"dense-first-image-conditioned-refine-before-retopo",
            "generator":selected_generator,
            "target_faces":hero_target,
            "minimum_faces":hero_floor,
            "actual_faces":int(detailgen_mesh.faces),
            "actual_vertices":int(detailgen_mesh.vertices),
            "dense_master_ready":bool(
                detailgen_mesh.passed and detailgen_tex.passed
            ),
            "density_target_met":bool(int(detailgen_mesh.faces)>=hero_floor),
            "image_conditioned_refinement":True,
            "material_bridge":asdict(bridge),
            "detailgen3d":detailgen_meta,
            "optimization_deferred":True,
            "runtime_optimization_stage":"post-Judge-v4",
        }
        print(
            "HAYUYA_DETAILGEN3D_HERO_PROMOTED",
            json.dumps(hero_master_report,separators=(",",":")),
        )
    except Exception as detailgen_exc:
        print(
            "::warning::DetailGen3D Hero refinement unavailable/rejected; "
            "keeping previous high-end candidate: "
            f"{type(detailgen_exc).__name__}: {detailgen_exc}"
        )

aaa_eligibility = assess_aaa_candidate(
    generator=selected_generator,
    hero_master=hero_master_report,
    texture_quality=TEXTURE_QUALITY,
)
if modern_candidate is not None and not aaa_eligibility.eligible:
    diagnostic_glb=OUT/"hayuya_diagnostic_candidate.glb"
    shutil.copy2(modern_candidate,diagnostic_glb)
    diagnostic_payload={
        "schema":1,
        "generator":selected_generator,
        "texture_quality":TEXTURE_QUALITY,
        "reasons":list(aaa_eligibility.reasons),
        "diagnostic_only":bool(aaa_eligibility.diagnostic_only),
        "hero_master":hero_master_report,
    "aaa_eligibility":(
        {
            "eligible":aaa_eligibility.eligible,
            "generator":aaa_eligibility.generator,
            "reasons":list(aaa_eligibility.reasons),
            "diagnostic_only":aaa_eligibility.diagnostic_only,
        }
        if "aaa_eligibility" in globals() else None
    ),
        "glb":diagnostic_glb.name,
        "user_facing_result":False,
        "note":(
            "This mesh is preserved for engineering evidence only. HAYUYA 3D "
            "must replace it with native/model-generated geometry before Judge "
            "or Hub result promotion."
        ),
    }
    (OUT/"aaa_candidate_rejection.json").write_text(
        json.dumps(diagnostic_payload,indent=2)+"\n",
        encoding="utf-8",
    )
    print(
        "HAYUYA_AAA_CANDIDATE_REJECTED",
        json.dumps(diagnostic_payload,separators=(",",":")),
    )
    fail(
        "HAYUYA AAA native/model-generated geometry required; diagnostic "
        "preview reconstruction was preserved but cannot become a Hero Master. "
        +"reasons="+",".join(aaa_eligibility.reasons)
    )

if modern_candidate is None:
    if not CLASSIC_TRELLIS_ENABLED:
        fail(
            "No permitted generator produced a model. "
            f"requested_backends={BACKENDS}; multi_image={multi}; "
            f"texture_quality={TEXTURE_QUALITY}"
        )
    try:
        result=resilient_predict(*args,api_name=endpoint,stage="trellis_generation",max_attempts=5)
    except Exception as e:
        # Gradio's public UI currently constrains Simplify to >=0.90 and Texture
        # Size to <=2048, even though TRELLIS' underlying to_glb() accepts numeric
        # arguments. If server-side component validation enforces those UI bounds,
        # retry at the best officially exposed extraction quality rather than fail
        # the whole phone workflow.
        if qp["mesh_simplify"] < 0.90 or qp["texture_size"] > 2048:
            extraction_fallback={
                "requested_mesh_simplify":qp["mesh_simplify"],
                "requested_texture_size":qp["texture_size"],
                "fallback_mesh_simplify":0.90,
                "fallback_texture_size":2048,
                "reason":f"{type(e).__name__}: {e}",
            }
            values["mesh_simplify"]=0.90
            values["texture_size"]=2048
            actual_mesh_simplify=0.90
            actual_texture_size=2048
            args=[values[p] for p in params]
            print("::warning::HAYUYA dense extraction override rejected; retrying official max-quality bounds")
            try:
                result=resilient_predict(*args,api_name=endpoint,stage="trellis_generation_fallback",max_attempts=5)
            except Exception as fallback_exc:
                fail(f"TRELLIS generation failed after quality fallback: {type(fallback_exc).__name__}: {fallback_exc}")
        else:
            fail(f"TRELLIS generation failed after transient retries: {type(e).__name__}: {e}")

(OUT/"trellis_result.txt").write_text(repr(result),encoding="utf-8")
candidates=[]
def walk(x):
    if isinstance(x,str):
        yield x
    elif isinstance(x,dict):
        for v in x.values(): yield from walk(v)
    elif isinstance(x,(list,tuple)):
        for v in x: yield from walk(v)
    else:
        for attr in ("path","url"):
            v=getattr(x,attr,None)
            if isinstance(v,str): yield v

for s in walk(result):
    if s.lower().endswith(".glb") and Path(s).exists():
        candidates.append(Path(s))
if not candidates:
    fail(f"No downloaded GLB in TRELLIS result: {result!r}")

src=candidates[-1]
dst=OUT/"hayuya_final.glb"
shutil.copy2(src,dst)
data=dst.read_bytes()
if data[:4] != b"glTF" or len(data)<1024:
    fail("Invalid GLB output")

require_final_normals=STRICT_TRELLIS2 and TEXTURE_QUALITY in {"high","ultra"}
final_texture_min_edge=(
    4096
    if STRICT_TRELLIS2 and TEXTURE_QUALITY in {"high","ultra"}
    else 1024
)
detail_fusion_payload=None
head_geometry_fusion_payload=None
source_material_rescue_payload=None

# Textureless native fallbacks (notably public CPU TripoSR continuity meshes)
# are still useful geometry. Do not relax the texture gate and do not promote
# the old front-projection proxy. Instead, use that projection only as a
# temporary material donor, bridge the material back onto the original native
# mesh, then re-run the normal native/volume/texture gates.
initial_texture_gate=inspect_texture_gate(
    dst,
    min_edge=final_texture_min_edge,
    min_base_color_edge=final_texture_min_edge,
)
if initial_texture_gate.base_color_image_count==0:
    try:
        from source_material_rescue import rescue_source_material

        rescued=OUT/"hayuya_source_material_rescued.glb"
        rescue_edge=(
            4096
            if TEXTURE_QUALITY=="ultra"
            else 2048
            if TEXTURE_QUALITY in {"high","standard"}
            else 1024
        )
        rescue=rescue_source_material(
            crops[0],
            dst,
            rescued,
            texture_edge=rescue_edge,
            min_texture_edge=final_texture_min_edge,
            total_samples=250_000,
        )
        source_material_rescue_payload=asdict(rescue)
        shutil.copy2(rescued,dst)
        data=dst.read_bytes()
        actual_texture_size=max(
            int(actual_texture_size or 0),
            int(rescue.texture_edge),
        )
        selected_compute=(
            selected_compute
            +" + HAYUYA source-derived native material rescue"
        )
        print(
            "HAYUYA_SOURCE_MATERIAL_RESCUE_PASS",
            json.dumps(
                source_material_rescue_payload,
                separators=(",",":"),
            ),
        )
    except Exception as rescue_exc:
        source_material_rescue_payload={
            "attempted":True,
            "promoted":False,
            "error":f"{type(rescue_exc).__name__}: {rescue_exc}",
            "reason":"missing_embedded_base_color",
        }
        print(
            "::warning::HAYUYA source material rescue unavailable; "
            "keeping native geometry for downstream hard texture gate: "
            +source_material_rescue_payload["error"]
        )

# TRELLIS.2 preview recovery is intentionally only an approximate visual hull.
# For face-critical characters, do not rely on texture paint to hide a weak head
# surface. Build a second full-body TripoSR hypothesis from the SAME real source
# and use only its upper-head geometry as a seam-limited challenger on the
# preview-recovered topology. The existing regional-fusion guard preserves the
# base UV/material payload and limits neck/bounds drift. Judge v4 remains the
# final authority after this worker; this stage only gives it real face geometry
# to evaluate instead of a texture-only repair.
if (
    detail_views
    and TRIPOSR_CPU_ENABLED
    and ASSET_PROFILE in {"auto","character.humanoid","character.creature"}
    and selected_generator=="microsoft/TRELLIS.2-preview-recovery"
):
    try:
        from regional_fusion import prepare_head_wrap_challenger

        geometry_donor_meta=generate_triposr_cpu_cloud(
            crops[0],
            OUT/"head_geometry_donor_fullbody.glb",
            token=TOKEN,
        )
        geometry_donor=Path(geometry_donor_meta["path"])
        head_wrap=prepare_head_wrap_challenger(
            dst,
            geometry_donor,
            OUT/"head_geometry_wrap",
            texture_size=max(1024,int(actual_texture_size or 0)),
            require_rebake=True,
            up_axis="y",
        )
        head_geometry_fusion_payload={
            "attempted":True,
            "reason":"preview_recovery_face_geometry_guard",
            "donor":geometry_donor_meta,
            "fusion":asdict(head_wrap),
            "promoted":False,
        }
        print(
            "HAYUYA_HEAD_GEOMETRY_FUSION",
            json.dumps(head_geometry_fusion_payload,separators=(",",":")),
        )
        if head_wrap.ready_for_judge and head_wrap.output_glb:
            wrapped=Path(head_wrap.output_glb)
            wrapped_mesh=inspect_mesh_gate(
                wrapped,
                require_normals=require_final_normals,
            )
            wrapped_texture=inspect_texture_gate(
                wrapped,
                min_edge=final_texture_min_edge,
            )
            head_geometry_fusion_payload["mesh_gate"]=asdict(wrapped_mesh)
            head_geometry_fusion_payload["texture_gate"]=asdict(wrapped_texture)
            if wrapped_mesh.passed and wrapped_texture.passed:
                shutil.copy2(wrapped,dst)
                data=dst.read_bytes()
                head_geometry_fusion_payload["promoted"]=True
                selected_compute=(
                    selected_compute
                    +" + CPU full-body TripoSR seam-limited head geometry fusion"
                )
                print(
                    "HAYUYA_HEAD_GEOMETRY_FUSION_PROMOTED",
                    json.dumps(head_geometry_fusion_payload,separators=(",",":")),
                )
            else:
                head_geometry_fusion_payload["rejected_reason"]="post_wrap_gate"
                print(
                    "::warning::Head-geometry fusion challenger rejected by hard gates"
                )
        else:
            head_geometry_fusion_payload["rejected_reason"]=(
                head_wrap.error or "regional_fusion_not_judge_ready"
            )
            print(
                "::warning::Head-geometry fusion not Judge-ready: "
                +str(head_geometry_fusion_payload["rejected_reason"])
            )
    except Exception as head_geometry_exc:
        head_geometry_fusion_payload={
            "attempted":True,
            "reason":"preview_recovery_face_geometry_guard",
            "promoted":False,
            "error":f"{type(head_geometry_exc).__name__}: {head_geometry_exc}",
        }
        print(
            "::warning::HAYUYA head-geometry fusion unavailable; "
            "keeping preview-recovered base for downstream Judge v4: "
            +head_geometry_fusion_payload["error"]
        )

# A face-critical preview visual hull cannot be finalized merely because its
# topology and texture are valid. The geometry rescue above is mandatory; if it
# could not produce a safe Judge-ready challenger, fail closed instead of letting
# a texture-only face paint reach Judge v4 as the master.
if preview_recovery_face_rescue_required and not (
    head_geometry_fusion_payload
    and head_geometry_fusion_payload.get("promoted")
):
    fail(
        "TRELLIS.2 preview recovery refused final promotion: "
        "source-derived face evidence exists but the seam-limited head geometry "
        "rescue did not produce a Judge-ready candidate."
    )

# Real head/detail evidence must affect the final character instead of only
# being written to the manifest. Build a CPU TripoSR donor from the tight
# source-derived head crop, align that donor to the semantic head region, and
# transfer only its baseColor evidence. Geometry/runtime payload stays byte-safe.
# This is a challenger: failure never downgrades a valid TRELLIS result.
if (
    detail_views
    and TRIPOSR_CPU_ENABLED
    and ASSET_PROFILE in {"auto","character.humanoid","character.creature"}
    and selected_generator!="stabilityai/TripoSR"
):
    try:
        detail_donor_meta=generate_triposr_cpu_cloud(
            detail_views[0],
            OUT/"detail_head_donor.glb",
            token=TOKEN,
        )
        detail_donor=Path(detail_donor_meta["path"])
        detail_fused=OUT/"hayuya_head_detail_fused.glb"
        fusion=fuse_local_basecolor(
            dst,
            detail_donor,
            detail_fused,
            region="head",
            up_axis="y",
            donor_samples=80_000,
            max_alignment_p95_ratio=0.30,
            donor_scope="region",
        )
        detail_fusion_payload={
            "attempted":True,
            "source_detail":detail_views[0].name,
            "donor":detail_donor_meta,
            "fusion":asdict(fusion),
            "promoted":False,
        }
        print(
            "HAYUYA_HEAD_DETAIL_FUSION",
            json.dumps(detail_fusion_payload,separators=(",",":")),
        )
        if fusion.ready:
            fused_mesh=inspect_mesh_gate(
                detail_fused,
                require_normals=require_final_normals,
            )
            fused_texture=inspect_texture_gate(
                detail_fused,
                min_edge=final_texture_min_edge,
            )
            if fused_mesh.passed and fused_texture.passed:
                shutil.copy2(detail_fused,dst)
                data=dst.read_bytes()
                detail_fusion_payload["promoted"]=True
                detail_fusion_payload["mesh_gate"]=asdict(fused_mesh)
                detail_fusion_payload["texture_gate"]=asdict(fused_texture)
                selected_compute=selected_compute+" + CPU semantic head-detail fusion"
                print(
                    "HAYUYA_HEAD_DETAIL_FUSION_PROMOTED",
                    json.dumps(detail_fusion_payload,separators=(",",":")),
                )
            else:
                detail_fusion_payload["mesh_gate"]=asdict(fused_mesh)
                detail_fusion_payload["texture_gate"]=asdict(fused_texture)
                detail_fusion_payload["rejected_reason"]="post_fusion_gate"
                print(
                    "::warning::Head-detail fusion challenger rejected by hard gates"
                )
    except Exception as detail_exc:
        detail_fusion_payload={
            "attempted":True,
            "source_detail":detail_views[0].name if detail_views else None,
            "promoted":False,
            "error":f"{type(detail_exc).__name__}: {detail_exc}",
        }
        print(
            "::warning::HAYUYA head-detail fusion unavailable; "
            "keeping base model: "
            +detail_fusion_payload["error"]
        )

# Catastrophic geometry gate: a backend returning a syntactically valid GLB is
# not enough. Reject billboard crosses, fragmented texture planes, collapsed
# bounds, and other obvious non-model outputs before the Hub ever says DONE.
gate=inspect_mesh_gate(dst,require_normals=require_final_normals)
gate_payload=asdict(gate)
(OUT/"quality_gate.json").write_text(json.dumps(gate_payload,indent=2),encoding="utf-8")
print("HAYUYA_MESH_GATE", json.dumps(gate_payload, separators=(",",":")))
if not gate.passed:
    fail("HAYUYA mesh quality gate rejected output: " + "; ".join(gate.reasons))

# Texture gate prevents the old failure mode where a geometrically valid model
# reaches DONE with no usable embedded texture or only a tiny texture. Blur is
# reported as telemetry first; fidelity refinement owns the stricter judgment.
texture_gate=inspect_texture_gate(dst, min_edge=final_texture_min_edge)
texture_payload=asdict(texture_gate)
(OUT/"texture_gate.json").write_text(json.dumps(texture_payload,indent=2),encoding="utf-8")
print("HAYUYA_TEXTURE_GATE", json.dumps(texture_payload,separators=(",",":")))
if not texture_gate.passed:
    fail("HAYUYA texture gate rejected output: " + "; ".join(texture_gate.warnings))

# Animation readiness is profile-specific. Humanoids use skeletal rig QA;
# weapons/vehicles/mechanical props require part/pivot mechanics; foliage uses
# runtime wind/vertex motion. Never force a humanoid skeleton onto arbitrary
# assets just to make the "animation ready" badge turn green.
character_payload=None
if ASSET_PROFILE in {"auto","character.humanoid","character.creature"}:
    rig=inspect_rig_gate(dst, Path("hayuya/standards/hayuya_humanoid_v1.json"))
    rig_payload=asdict(rig)
    (OUT/"rig_gate.json").write_text(json.dumps(rig_payload,indent=2),encoding="utf-8")
    print("HAYUYA_RIG_GATE", json.dumps(rig_payload, separators=(",",":")))
    character_payload={
        "skeleton_type":rig_payload["skeleton_type"],
        "preview_pack":"hayuya_preview_pack_v1",
        "rig_ready":rig_payload["rig_ready"],
        "animation_ready":rig_payload["animation_ready"],
        "preview_animation_ready":rig_payload["preview_animation_ready"],
        "animation_clips":rig_payload["animation_clips"],
        "facial":rig_payload["facial"],
        "secondary_motion":rig_payload["secondary_motion"],
        "warnings":rig_payload["warnings"],
    }

profile_systems={
    "character.humanoid":["skeletal","morph_targets","secondary_motion"],
    "character.creature":["skeletal","morph_targets","secondary_motion"],
    "weapon.firearm":["mechanical_skeleton","transform_channels"],
    "weapon.melee":["transform_channels","optional_skeletal"],
    "prop.mechanical":["mechanical_skeleton","transform_channels"],
    "vehicle":["mechanical_skeleton","transform_channels","suspension_rig"],
    "foliage.grass":["vertex_wind","transform_channels"],
    "foliage.tree":["vertex_wind","skeletal_foliage"],
    "prop.static":["optional_transform_channels","optional_morph_targets"],
    "environment.modular":["optional_transform_channels","optional_vertex_animation"],
    "auto":[],
}
asset_payload={
    "profile":ASSET_PROFILE,
    "weapon_family":WEAPON_FAMILY if ASSET_PROFILE=="weapon.firearm" else "auto",
    "animation_requested":ANIMATION_REQUESTED,
    "motion_profile":MOTION_PROFILE,
    "animation_systems":profile_systems.get(ASSET_PROFILE,[]),
    "mechanical_rig_ready":False,
    "procedural_motion_ready":ASSET_PROFILE in {"foliage.grass","foliage.tree"},
    "requires_profile_postprocess":ASSET_PROFILE not in {"auto","character.humanoid","character.creature","prop.static"},
}

manifest={
    "schema":2,
    "engine":"HAYUYA PHONE CLOUD",
    "job_id":JOB,
    "asset_profile":ASSET_PROFILE,
    "weapon_family":WEAPON_FAMILY if ASSET_PROFILE=="weapon.firearm" else "auto",
    "animation_requested":ANIMATION_REQUESTED,
    "motion_profile":MOTION_PROFILE,
    "texture_quality":TEXTURE_QUALITY,
    "compute":selected_compute,
    "phone_only":True,
    "source":str(GEOMETRY),
    "prepared_views":[p.name for p in crops],
    "prepared_detail_views":[p.name for p in detail_views],
    "head_geometry_fusion":head_geometry_fusion_payload,
    "detail_fusion":detail_fusion_payload,
    "source_material_rescue":source_material_rescue_payload,
    "source_autofix":(
        asdict(source_autofix_result)
        if source_autofix_result is not None else None
    ),
    "source_autofix_failure":source_autofix_failure,
    "manual_face_closeup_required":False,
    "single_photo_first":True,
    "reference_dir":str(REFERENCE_DIR) if REFERENCE_DIR else "",
    "detail_dir":str(DETAIL_DIR) if DETAIL_DIR else "",
    "prep_target":PREP_TARGET,
    "multi_image":multi,
    "generator":selected_generator,
    "preview_recovery_candidate":(
        str(preview_recovery_candidate)
        if preview_recovery_candidate is not None else None
    ),
    "preview_recovery_face_rescue_required":preview_recovery_face_rescue_required,
    "preview_recovery_face_rescue_reason":preview_recovery_face_rescue_reason,
    "preview_normal_hero":preview_normal_hero_report,
    "hero_master":hero_master_report,
    "preview_recovery_promoted":bool(
        selected_generator in {
            "microsoft/TRELLIS.2-preview-recovery",
            "microsoft/TRELLIS.2-preview-normal-hero",
        }
        and (
            not preview_recovery_face_rescue_required
            or bool(
                head_geometry_fusion_payload
                and head_geometry_fusion_payload.get("promoted")
            )
        )
    ),
    "requested_backends":BACKENDS,
    "strict_trellis2":STRICT_TRELLIS2,
    "texture_size":actual_texture_size,
    "requested_texture_target":qp["texture_size"],
    "native_texture_target":actual_texture_size,
    "texture_refinement_pending":actual_texture_size < qp["texture_size"],
    "quality_profile":{
        "ss_sampling_steps":qp["ss_steps"],
        "slat_sampling_steps":qp["slat_steps"],
        "requested_mesh_simplify":qp["mesh_simplify"],
        "actual_mesh_simplify":actual_mesh_simplify,
        "requested_texture_size":qp["texture_size"],
        "actual_texture_size":actual_texture_size,
        "public_ui_simplify_floor":0.90,
        "public_ui_texture_ceiling":4096 if selected_generator=="microsoft/TRELLIS.2-4B" else 2048,
        "dense_extraction_override_attempted":(
            False if selected_generator=="microsoft/TRELLIS.2-4B"
            else qp["mesh_simplify"]<0.90 or qp["texture_size"]>2048
        ),
        "extraction_fallback":extraction_fallback,
        "detail_reference_count":len(detail_views),
        "note":(
            "TRELLIS.2 official Space full-PBR extraction; classic TRELLIS remains fallback/multi-image authority."
            if selected_generator=="microsoft/TRELLIS.2-4B"
            else "TRELLIS simplify is triangle-removal ratio. HAYUYA reports requested and actual extraction quality separately."
        )
    },
    "glb":dst.name,
    "glb_bytes":len(data),
    "authenticated_hf":bool(TOKEN),
    "cloud_retry_count":len(retry_events),
    "cloud_retries":retry_events,
    "source_mode":source_mode,
    "source_had_alpha":source_had_alpha,
    "alpha_preserved":True,
    "quality_gate":gate_payload,
    "texture_gate":texture_payload,
    "asset":asset_payload,
}
if character_payload is not None:
    manifest["character"]=character_payload
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
if retry_events:
    (OUT/"cloud_retry_state.json").write_text(
        json.dumps({
            "schema":1,
            "job_id":JOB,
            "status":"recovered",
            "events":retry_events,
        },indent=2)+"\n",
        encoding="utf-8",
    )
print("HAYUYA_PHONE_CLOUD_PASS")
print(json.dumps(manifest,indent=2))
