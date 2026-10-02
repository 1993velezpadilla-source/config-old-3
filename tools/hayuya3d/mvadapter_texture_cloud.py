#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from gradio_client import Client, handle_file


def _named_endpoints(client):
    api = client.view_api(print_info=False, return_format="dict")
    return api.get("named_endpoints", {})


def _parameter_names(spec):
    return [p.get("parameter_name") for p in spec.get("parameters", [])]


def _find_endpoint(named, required):
    ranked=[]
    for name,spec in named.items():
        params=_parameter_names(spec)
        pset=set(params)
        if not set(required).issubset(pset):
            continue
        score=len(required)*10
        lname=name.lower()
        for token in ("texture","adapter","generate","run"):
            if token in lname:
                score+=1
        ranked.append((score,name,spec))
    if not ranked:
        raise RuntimeError(f"endpoint not found for {required}: {list(named)}")
    ranked.sort(reverse=True,key=lambda x:x[0])
    return ranked[0][1],ranked[0][2]


def _path_value(value):
    if isinstance(value,str):
        return value
    if isinstance(value,dict):
        for key in ("path","name"):
            raw=value.get(key)
            if isinstance(raw,str):
                return raw
    raw=getattr(value,"path",None)
    if isinstance(raw,str):
        return raw
    return None


def _retry(call,stage,attempts=3):
    delays=(25,50)
    last=None
    for i in range(attempts):
        try:
            return call()
        except Exception as exc:
            last=exc
            print(f"::warning::MVAdapter {stage} attempt {i+1}/{attempts}: {type(exc).__name__}: {exc}")
            if i+1<attempts:
                time.sleep(delays[min(i,len(delays)-1)])
    raise RuntimeError(f"MVAdapter {stage} failed: {last}")


def _gallery_input(value):
    if isinstance(value,tuple):
        value=list(value)
    if isinstance(value,list):
        out=[]
        for item in value:
            if isinstance(item,(list,tuple)) and item:
                item=item[0]
            raw=_path_value(item)
            if raw and Path(raw).is_file():
                out.append(handle_file(raw))
            else:
                out.append(item)
        return out
    return value


def texture(mesh:Path,image:Path,output:Path,*,space:str,seed:int,guidance:float,steps:int,reference_scale:float,uv_size:int):
    kwargs={"verbose":True,"httpx_kwargs":{"timeout":300.0}}
    token=os.environ.get("HF_TOKEN","").strip()
    if token:
        kwargs["token"]=token
    client=Client(space,**kwargs)
    named=_named_endpoints(client)

    mv_name,mv_spec=_find_endpoint(
        named,
        ["mesh_path","prompt","image","seed","guidance_scale","num_inference_steps","reference_conditioning_scale"],
    )
    mv_params=_parameter_names(mv_spec)
    mv_values={
        "mesh_path":handle_file(str(mesh.resolve())),
        "prompt":"high quality photorealistic game character texture, preserve reference clothing and face",
        "image":handle_file(str(image.resolve())),
        "seed":int(seed),
        "guidance_scale":float(guidance),
        "num_inference_steps":int(steps),
        "reference_conditioning_scale":float(reference_scale),
        "negative_prompt":"watermark, ugly, deformed, noisy, blurry, low contrast, plastic, clay, monochrome, low detail",
    }
    mv_args=[]
    for p in mv_params:
        if p not in mv_values:
            raise RuntimeError(f"unhandled MVAdapter parameter {p} for {mv_name}")
        mv_args.append(mv_values[p])
    mv_result=_retry(lambda:client.predict(*mv_args,api_name=mv_name),"multiview",attempts=3)
    if isinstance(mv_result,(list,tuple)) and len(mv_result)>=1:
        gallery=mv_result[0]
    else:
        gallery=mv_result
    gallery=_gallery_input(gallery)

    tx_name,tx_spec=_find_endpoint(
        named,
        ["mesh_path","mv_images","uv_unwarp","preprocess_mesh","uv_size"],
    )
    tx_params=_parameter_names(tx_spec)
    tx_values={
        "mesh_path":handle_file(str(mesh.resolve())),
        "mv_images":gallery,
        "uv_unwarp":True,
        "preprocess_mesh":False,
        "uv_size":int(uv_size),
    }
    tx_args=[]
    for p in tx_params:
        if p not in tx_values:
            raise RuntimeError(f"unhandled texture parameter {p} for {tx_name}")
        tx_args.append(tx_values[p])
    tx_result=_retry(lambda:client.predict(*tx_args,api_name=tx_name),"texture_bake",attempts=3)
    raw=None
    if isinstance(tx_result,(list,tuple)):
        for item in tx_result:
            raw=_path_value(item)
            if raw:
                break
    else:
        raw=_path_value(tx_result)
    if not raw or not Path(raw).is_file():
        raise RuntimeError(f"MVAdapter returned no textured GLB: {tx_result!r}")
    data=Path(raw).read_bytes()
    if len(data)<1024 or data[:4]!=b"glTF":
        raise RuntimeError(f"MVAdapter output is not a valid GLB: {raw}")
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(raw,output)
    payload={
        "schema":1,
        "space":space,
        "multiview_endpoint":mv_name,
        "texture_endpoint":tx_name,
        "source_mesh":str(mesh),
        "reference_image":str(image),
        "output":str(output),
        "seed":int(seed),
        "guidance_scale":float(guidance),
        "steps":int(steps),
        "reference_conditioning_scale":float(reference_scale),
        "uv_size":int(uv_size),
    }
    output.with_suffix(".texture.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_TEXTURE_RESULT",json.dumps(payload,separators=(",",":")))


def main()->int:
    p=argparse.ArgumentParser(description="Reference-conditioned 4K texture stage for HAYUYA generated characters.")
    p.add_argument("--mesh",type=Path,required=True)
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--space",default="VAST-AI/MV-Adapter-Img2Texture")
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--guidance-scale",type=float,default=3.5)
    p.add_argument("--steps",type=int,default=30)
    p.add_argument("--reference-conditioning-scale",type=float,default=1.4)
    p.add_argument("--uv-size",type=int,default=4096)
    a=p.parse_args()
    texture(a.mesh,a.image,a.output,space=a.space,seed=a.seed,guidance=a.guidance_scale,steps=a.steps,reference_scale=a.reference_conditioning_scale,uv_size=a.uv_size)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
