#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict,dataclass
from pathlib import Path

from PIL import Image,ImageChops,ImageStat

try:
    from glb_images import replace_embedded_images
    from texture_gate import embedded_images,inspect
except ImportError:
    from .glb_images import replace_embedded_images
    from .texture_gate import embedded_images,inspect


@dataclass
class TextureSuperresItem:
    image_index:int
    original_width:int
    original_height:int
    original_edge:int
    requested_scale:int
    generated_width:int
    generated_height:int
    final_width:int
    final_height:int
    model:str
    content_mae:float
    luminance_mean_drift:float
    source_luminance_stddev:float
    reprojected_luminance_stddev:float
    alpha_preserved:bool


@dataclass
class TextureSuperresResult:
    input_glb:str
    output_glb:str
    target_edge:int
    attempted:bool
    ready:bool
    method:str
    items:list[TextureSuperresItem]
    remaining_image_indices:list[int]
    error:str|None=None


def find_realesrgan(explicit:str|Path|None=None)->Path|None:
    raw=explicit or os.environ.get("HAYUYA_REALESRGAN")
    if raw:
        p=Path(raw).expanduser()
        if p.is_file():
            return p.resolve()
        resolved=shutil.which(str(raw))
        if resolved:
            return Path(resolved).resolve()
    for name in ("realesrgan-ncnn-vulkan","realesrgan-ncnn-vulkan.exe"):
        resolved=shutil.which(name)
        if resolved:
            return Path(resolved).resolve()
    runtime_module=None
    try:
        if __package__:
            from . import texture_runtime as runtime_module
        else:
            import texture_runtime as runtime_module
    except ImportError:
        runtime_module=None
    if runtime_module is not None:
        resolved=runtime_module.executable_path()
        if resolved is not None:
            return Path(resolved).resolve()
    return None


def ensure_realesrgan(
    explicit:str|Path|None=None,
    *,
    auto_install:bool=False,
)->Path|None:
    resolved=find_realesrgan(explicit)
    if resolved is not None or explicit is not None or not auto_install:
        return resolved
    try:
        if __package__:
            from . import texture_runtime as runtime_module
        else:
            import texture_runtime as runtime_module
    except ImportError:
        return None
    try:
        return Path(runtime_module.install()).resolve()
    except Exception:
        return None


def required_scale(current_edge:int,target_edge:int)->int:
    if current_edge<=0 or target_edge<=0:
        raise ValueError("texture edges must be positive")
    if current_edge>=target_edge:
        return 1
    ratio=target_edge/current_edge
    for scale in (2,3,4):
        if scale>=ratio-1e-9:
            return scale
    raise ValueError(
        f"required scale exceeds Real-ESRGAN portable range: {current_edge}->{target_edge}"
    )


def build_realesrgan_command(
    executable:Path,
    input_image:Path,
    output_image:Path,
    *,
    scale:int,
    model:str="realesrgan-x4plus",
    tile_size:int=0,
)->list[str]:
    if scale not in (2,3,4):
        raise ValueError(f"unsupported Real-ESRGAN scale: {scale}")
    model_dir=executable.parent/"models"
    return [
        str(executable),
        "-i",str(input_image),
        "-o",str(output_image),
        "-m",str(model_dir),
        "-s",str(scale),
        "-t",str(max(0,int(tile_size))),
        "-n",model,
        "-f","png",
    ]


def _fit_long_edge(image:Image.Image,target_edge:int)->Image.Image:
    edge=max(image.size)
    if edge==target_edge:
        return image
    scale=target_edge/edge
    size=(
        max(1,int(round(image.width*scale))),
        max(1,int(round(image.height*scale))),
    )
    return image.resize(size,Image.Resampling.LANCZOS)


def _source_consistency_metrics(
    source:Image.Image,
    challenger:Image.Image,
)->dict[str,float]:
    """Measure whether SR preserved the source's low-frequency identity.

    The challenger is projected back to source resolution before comparison so
    added high-frequency detail is allowed, while catastrophic color/structure
    drift remains visible.
    """
    source_rgb=source.convert("RGB")
    projected=challenger.convert("RGB").resize(
        source_rgb.size,
        Image.Resampling.LANCZOS,
    )
    diff=ImageChops.difference(source_rgb,projected)
    mae=sum(float(x) for x in ImageStat.Stat(diff).mean)/3.0

    source_luma=source_rgb.convert("L")
    projected_luma=projected.convert("L")
    source_stats=ImageStat.Stat(source_luma)
    projected_stats=ImageStat.Stat(projected_luma)
    source_mean=float(source_stats.mean[0])
    projected_mean=float(projected_stats.mean[0])
    return {
        "content_mae":round(mae,4),
        "luminance_mean_drift":round(abs(source_mean-projected_mean),4),
        "source_luminance_stddev":round(float(source_stats.stddev[0]),4),
        "reprojected_luminance_stddev":round(float(projected_stats.stddev[0]),4),
    }


def _assert_source_consistency(
    image_index:int,
    source:Image.Image,
    challenger:Image.Image,
    metrics:dict[str,float],
)->None:
    """Fail closed on outputs that are high-resolution but visually corrupted."""
    mae=float(metrics["content_mae"])
    mean_drift=float(metrics["luminance_mean_drift"])
    source_std=float(metrics["source_luminance_stddev"])
    challenger_std=float(metrics["reprojected_luminance_stddev"])

    reasons=[]
    if mae>56.0:
        reasons.append(f"rgb_mae={mae:.3f}>56")
    # This is intentionally a catastrophic-corruption guard, not the fine
    # fidelity judge. Real-ESRGAN may legitimately rebalance luminance on tiny
    # inputs; source-vs-render reranking decides whether that aesthetic change
    # is actually an improvement on production assets.
    if mean_drift>64.0:
        reasons.append(f"luma_mean_drift={mean_drift:.3f}>64")
    if source_std>=8.0 and challenger_std<max(1.0,source_std*0.15):
        reasons.append(
            "luma_structure_collapsed:"
            f"{source_std:.3f}->{challenger_std:.3f}"
        )
    if reasons:
        raise RuntimeError(
            "super-resolution content drift: "
            f"image={image_index} " + ";".join(reasons)
        )


def superresolve_basecolor_glb(
    input_glb:Path,
    output_glb:Path,
    *,
    target_edge:int,
    executable:str|Path|None=None,
    model:str="realesrgan-x4plus",
    tile_size:int=0,
    auto_install:bool=False,
)->TextureSuperresResult:
    exe=ensure_realesrgan(executable,auto_install=auto_install)
    base_images=[]
    for image_index,mime,data,roles in embedded_images(input_glb):
        if "baseColor" not in roles:
            continue
        with Image.open(io.BytesIO(data)) as image:
            w,h=image.size
        base_images.append((image_index,mime,data,w,h))

    remaining=[
        image_index
        for image_index,_,_,w,h in base_images
        if max(w,h)<target_edge
    ]
    if not remaining:
        if input_glb.resolve()!=output_glb.resolve():
            shutil.copy2(input_glb,output_glb)
        return TextureSuperresResult(
            input_glb=str(input_glb),
            output_glb=str(output_glb),
            target_edge=target_edge,
            attempted=False,
            ready=bool(base_images),
            method="already_at_target",
            items=[],
            remaining_image_indices=[],
        )

    if exe is None:
        if input_glb.resolve()!=output_glb.resolve():
            shutil.copy2(input_glb,output_glb)
        return TextureSuperresResult(
            input_glb=str(input_glb),
            output_glb=str(output_glb),
            target_edge=target_edge,
            attempted=False,
            ready=False,
            method="realesrgan_unavailable",
            items=[],
            remaining_image_indices=remaining,
        )

    replacements={}
    items=[]
    try:
        with tempfile.TemporaryDirectory(prefix="hayuya-sr-") as tmp:
            root=Path(tmp)
            for image_index,mime,data,w,h in base_images:
                edge=max(w,h)
                if edge>=target_edge:
                    continue
                scale=required_scale(edge,target_edge)
                source=root/f"image-{image_index}-input.png"
                generated=root/f"image-{image_index}-sr.png"

                with Image.open(io.BytesIO(data)) as image:
                    source_had_alpha="A" in image.getbands()
                    source_image=(
                        image.convert("RGBA")
                        if source_had_alpha
                        else image.convert("RGB")
                    )
                    source_image.save(source,format="PNG")

                cmd=build_realesrgan_command(
                    exe,source,generated,
                    scale=scale,
                    model=model,
                    tile_size=tile_size,
                )
                subprocess.run(cmd,check=True)
                if not generated.is_file():
                    raise RuntimeError(f"Real-ESRGAN produced no image: {image_index}")

                with Image.open(generated) as image:
                    generated_had_alpha="A" in image.getbands()
                    if source_had_alpha and not generated_had_alpha:
                        raise RuntimeError(
                            f"super-resolution dropped alpha: image={image_index}"
                        )
                    produced=(
                        image.convert("RGBA")
                        if source_had_alpha
                        else image.convert("RGB")
                    )
                    gw,gh=produced.size
                    expected=(w*scale,h*scale)
                    if (gw,gh)!=expected:
                        raise RuntimeError(
                            "super-resolution dimensions unexpected: "
                            f"image={image_index} got={gw}x{gh} "
                            f"expected={expected[0]}x{expected[1]}"
                        )
                    if max(gw,gh)<target_edge:
                        raise RuntimeError(
                            f"super-resolution below target: image={image_index} "
                            f"edge={max(gw,gh)} target={target_edge}"
                        )

                    consistency=_source_consistency_metrics(
                        source_image,
                        produced,
                    )
                    _assert_source_consistency(
                        image_index,
                        source_image,
                        produced,
                        consistency,
                    )

                    final=_fit_long_edge(produced,target_edge)
                    fw,fh=final.size
                    buf=io.BytesIO()
                    final.save(buf,format="PNG",optimize=True)
                    replacements[image_index]=("image/png",buf.getvalue())

                items.append(TextureSuperresItem(
                    image_index=image_index,
                    original_width=w,
                    original_height=h,
                    original_edge=edge,
                    requested_scale=scale,
                    generated_width=gw,
                    generated_height=gh,
                    final_width=fw,
                    final_height=fh,
                    model=model,
                    content_mae=float(consistency["content_mae"]),
                    luminance_mean_drift=float(
                        consistency["luminance_mean_drift"]
                    ),
                    source_luminance_stddev=float(
                        consistency["source_luminance_stddev"]
                    ),
                    reprojected_luminance_stddev=float(
                        consistency["reprojected_luminance_stddev"]
                    ),
                    alpha_preserved=(
                        not source_had_alpha or generated_had_alpha
                    ),
                ))

        replace_embedded_images(input_glb,output_glb,replacements)
        report=inspect(
            output_glb,
            min_edge=1,
            min_base_color_edge=target_edge,
        )
        remaining_after=[
            item.index
            for item in report.metrics
            if "baseColor" in item.roles and max(item.width,item.height)<target_edge
        ]
        ready=bool(report.base_color_image_count) and not remaining_after
        return TextureSuperresResult(
            input_glb=str(input_glb),
            output_glb=str(output_glb),
            target_edge=target_edge,
            attempted=True,
            ready=ready,
            method="realesrgan_ncnn_vulkan_basecolor_v2",
            items=items,
            remaining_image_indices=remaining_after,
            error=None if ready else "baseColor target not met after super-resolution",
        )
    except Exception as exc:
        if input_glb.resolve()!=output_glb.resolve():
            shutil.copy2(input_glb,output_glb)
        return TextureSuperresResult(
            input_glb=str(input_glb),
            output_glb=str(output_glb),
            target_edge=target_edge,
            attempted=True,
            ready=False,
            method="realesrgan_failed",
            items=items,
            remaining_image_indices=remaining,
            error=f"{type(exc).__name__}:{exc}",
        )


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA visible baseColor super-resolution challenger.")
    p.add_argument("input_glb",type=Path)
    p.add_argument("output_glb",type=Path)
    p.add_argument("--target-edge",type=int,required=True)
    p.add_argument("--realesrgan")
    p.add_argument("--model",default="realesrgan-x4plus")
    p.add_argument("--tile-size",type=int,default=0)
    p.add_argument("--auto-install",action="store_true")
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    result=superresolve_basecolor_glb(
        a.input_glb,a.output_glb,
        target_edge=a.target_edge,
        executable=a.realesrgan,
        model=a.model,
        tile_size=a.tile_size,
        auto_install=a.auto_install,
    )
    payload=json.dumps(asdict(result),indent=2)
    print(payload)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True)
        a.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if result.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
