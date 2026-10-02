#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import struct
from dataclasses import asdict,dataclass
from pathlib import Path

from PIL import Image,ImageFilter,ImageStat


@dataclass
class TextureMetric:
    index:int
    mime_type:str
    width:int
    height:int
    megapixels:float
    edge_variance:float
    luminance_stddev:float
    entropy:float
    roles:list[str]


@dataclass
class TextureReport:
    schema:int
    path:str
    image_count:int
    max_edge:int
    max_megapixels:float
    mean_edge_variance:float
    base_color_image_count:int
    base_color_max_edge:int
    base_color_min_edge:int
    base_color_max_megapixels:float
    material_roles:dict[str,list[int]]
    metrics:list[TextureMetric]
    warnings:list[str]
    passed:bool


def chunks(path:Path):
    data=path.read_bytes()
    if len(data)<20 or data[:4]!=b"glTF":
        raise ValueError("not a GLB")
    _,version,total=struct.unpack_from("<4sII",data,0)
    if version!=2 or total>len(data):
        raise ValueError("invalid GLB header")
    off=12
    doc=None
    bin_blob=b""
    while off+8<=total:
        length,kind=struct.unpack_from("<II",data,off)
        off+=8
        payload=data[off:off+length]
        off+=length
        if kind==0x4E4F534A:
            doc=json.loads(payload.decode("utf-8").rstrip("\x00 \t\r\n"))
        elif kind==0x004E4942:
            bin_blob=payload
    if doc is None:
        raise ValueError("missing JSON chunk")
    return doc,bin_blob


def material_image_roles(doc:dict)->dict[int,set[str]]:
    textures=doc.get("textures") or []
    roles:dict[int,set[str]]={}

    def add(texture_info,role:str)->None:
        if not isinstance(texture_info,dict):
            return
        texture_index=texture_info.get("index")
        if not isinstance(texture_index,int) or not (0<=texture_index<len(textures)):
            return
        source=textures[texture_index].get("source")
        if isinstance(source,int):
            roles.setdefault(source,set()).add(role)

    for material in doc.get("materials") or []:
        pbr=material.get("pbrMetallicRoughness") or {}
        add(pbr.get("baseColorTexture"),"baseColor")
        add(pbr.get("metallicRoughnessTexture"),"metallicRoughness")
        add(material.get("normalTexture"),"normal")
        add(material.get("occlusionTexture"),"occlusion")
        add(material.get("emissiveTexture"),"emissive")
    return roles


def embedded_images(path:Path):
    doc,bin_blob=chunks(path)
    views=doc.get("bufferViews") or []
    roles=material_image_roles(doc)
    out=[]
    for idx,img in enumerate(doc.get("images") or []):
        bv=img.get("bufferView")
        if not isinstance(bv,int) or not (0<=bv<len(views)):
            continue
        view=views[bv]
        start=int(view.get("byteOffset",0))
        length=int(view.get("byteLength",0))
        data=bin_blob[start:start+length]
        if data:
            out.append((
                idx,
                str(img.get("mimeType") or "unknown"),
                data,
                sorted(roles.get(idx) or {"unreferenced"}),
            ))
    return out


def metric(idx:int,mime:str,data:bytes,roles:list[str])->TextureMetric:
    with Image.open(io.BytesIO(data)) as image:
        rgb=image.convert("RGB")
        w,h=rgb.size
        # Normalize to a stable analysis size so resolution alone cannot inflate
        # the detail score.
        g=rgb.convert("L")
        g.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        edges=g.filter(ImageFilter.FIND_EDGES)
        edge_var=float(ImageStat.Stat(edges).var[0])
        lum_std=float(ImageStat.Stat(g).stddev[0])
        ent=float(g.entropy())
        return TextureMetric(
            index=idx,mime_type=mime,width=w,height=h,
            megapixels=round((w*h)/1_000_000,4),
            edge_variance=round(edge_var,4),
            luminance_stddev=round(lum_std,4),
            entropy=round(ent,4),
            roles=list(roles),
        )


def base_color_resolution_ok(base_edges:list[int],required_edge:int)->bool:
    """Require every bound baseColor atlas to meet the requested floor.

    Using only the largest atlas lets one high-resolution accessory texture hide a
    low-resolution face/body atlas. The production gate must represent the weakest
    visible baseColor binding, while max-edge telemetry remains useful for diagnosis.
    """
    return bool(base_edges) and min(base_edges)>=required_edge


def texture_resolution_ok(image_edges:list[int],base_edges:list[int],min_edge:int,required_base_edge:int)->bool:
    """Production texture QA requires real visible color evidence, not just maps.

    A large normal/ORM/emissive image must never let a model with no embedded
    baseColor texture pass the resolution gate.
    """
    return (
        bool(image_edges)
        and max(image_edges)>=min_edge
        and base_color_resolution_ok(base_edges,required_base_edge)
    )


def inspect(
    path:Path,
    min_edge:int=1024,
    min_base_color_edge:int|None=None,
)->TextureReport:
    metrics=[metric(i,m,d,roles) for i,m,d,roles in embedded_images(path)]
    warnings=[]
    image_edges=[max(x.width,x.height) for x in metrics]
    max_edge=max(image_edges,default=0)
    max_mp=max((x.megapixels for x in metrics),default=0.0)
    mean_edge=sum(x.edge_variance for x in metrics)/len(metrics) if metrics else 0.0

    base=[x for x in metrics if "baseColor" in x.roles]
    base_edges=[max(x.width,x.height) for x in base]
    base_color_max_edge=max(base_edges,default=0)
    base_color_min_edge=min(base_edges,default=0)
    base_color_max_mp=max((x.megapixels for x in base),default=0.0)
    role_map={}
    for item in metrics:
        for role in item.roles:
            role_map.setdefault(role,[]).append(item.index)
    role_map={k:sorted(set(v)) for k,v in sorted(role_map.items())}

    required_base_edge=int(min_base_color_edge if min_base_color_edge is not None else min_edge)
    if not metrics:
        warnings.append("no_embedded_texture_images")
    if max_edge and max_edge<min_edge:
        warnings.append(f"low_texture_resolution:{max_edge}<{min_edge}")
    if base and not base_color_resolution_ok(base_edges,required_base_edge):
        warnings.append(
            f"low_base_color_resolution:{base_color_min_edge}<{required_base_edge}"
        )
    if metrics and not base:
        warnings.append("no_embedded_base_color_texture")
    # Calibration signal only. Do not hard-fail creative/stylized textures based
    # on an arbitrary sharpness threshold; the source-vs-render Judge owns fidelity.
    if metrics and mean_edge<25:
        warnings.append(f"low_high_frequency_detail:{mean_edge:.3f}")

    passed=texture_resolution_ok(image_edges,base_edges,min_edge,required_base_edge)

    return TextureReport(
        schema=2,path=str(path),image_count=len(metrics),max_edge=max_edge,
        max_megapixels=round(max_mp,4),mean_edge_variance=round(mean_edge,4),
        base_color_image_count=len(base),
        base_color_max_edge=base_color_max_edge,
        base_color_min_edge=base_color_min_edge,
        base_color_max_megapixels=round(base_color_max_mp,4),
        material_roles=role_map,
        metrics=metrics,warnings=warnings,passed=passed
    )


def main()->int:
    p=argparse.ArgumentParser(description="Inspect embedded GLB texture resolution and clarity telemetry.")
    p.add_argument("glb",type=Path)
    p.add_argument("--min-edge",type=int,default=1024)
    p.add_argument(
        "--min-base-color-edge",
        type=int,
        help="minimum edge for every texture bound to baseColor; defaults to --min-edge",
    )
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    try:
        report=inspect(a.glb,a.min_edge,a.min_base_color_edge)
        payload=json.dumps(asdict(report),indent=2)
        print(payload)
        if a.json:
            a.json.parent.mkdir(parents=True,exist_ok=True)
            a.json.write_text(payload+"\n",encoding="utf-8")
        return 0 if report.passed else 2
    except Exception as exc:
        payload={"schema":1,"path":str(a.glb),"passed":False,"warnings":[f"{type(exc).__name__}:{exc}"]}
        print(json.dumps(payload,indent=2))
        if a.json:
            a.json.parent.mkdir(parents=True,exist_ok=True)
            a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
