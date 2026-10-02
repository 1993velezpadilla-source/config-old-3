import json
from pathlib import Path
from mathutils import Vector

def load_profiles(path="docs/sanctum-reference-silhouettes.v1.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def scanline_range(points,z):
    """Return outer normalized coordinate range where polygon crosses horizontal z."""
    hits=[]
    n=len(points)
    for i in range(n):
        x0,z0=points[i]
        x1,z1=points[(i+1)%n]
        # Half-open rule prevents double counting vertices.
        if (z0 <= z < z1) or (z1 <= z < z0):
            t=(z-z0)/(z1-z0)
            hits.append(x0+t*(x1-x0))
        elif abs(z-z0)<1e-7 and abs(z1-z0)<1e-7:
            hits.extend((x0,x1))
    if len(hits)<2:
        return None
    return min(hits),max(hits)

def fit_object_to_silhouettes(obj,front_points,side_points,target_dimensions_m):
    """Scale an object to target dimensions then clamp vertices inside front/side visual hull.

    This is a deterministic non-AI equivalent of drawing over the front and side
    orthographic references: every vertex remains inside both traced silhouettes.
    Internal authored detail is preserved instead of replacing the model with a blob.
    """
    if obj.type!="MESH" or not obj.data.vertices:
        return {"changed":0,"vertices":0}

    width=float(target_dimensions_m["width"])
    depth=float(target_dimensions_m["depth"])
    height=float(target_dimensions_m["height"])

    # Normalize current mesh into the requested physical box first.
    coords=[v.co.copy() for v in obj.data.vertices]
    mn=Vector((min(v.x for v in coords),min(v.y for v in coords),min(v.z for v in coords)))
    mx=Vector((max(v.x for v in coords),max(v.y for v in coords),max(v.z for v in coords)))
    size=mx-mn
    if min(size.x,size.y,size.z)<=1e-8:
        raise ValueError(f"degenerate mesh {obj.name}: {size}")

    changed=0
    for v in obj.data.vertices:
        # Map source bbox -> physical reference bbox centered XY and grounded Z.
        x=((v.co.x-mn.x)/size.x-0.5)*width
        y=((v.co.y-mn.y)/size.y-0.5)*depth
        z=((v.co.z-mn.z)/size.z)*height
        zn=max(0.0,min(0.999999,z/height))

        fr=scanline_range(front_points,zn)
        if fr is not None:
            lo=(fr[0]-0.5)*width
            hi=(fr[1]-0.5)*width
            nx=max(lo,min(hi,x))
            changed += int(abs(nx-x)>1e-7)
            x=nx

        sr=scanline_range(side_points,zn)
        if sr is not None:
            lo=(sr[0]-0.5)*depth
            hi=(sr[1]-0.5)*depth
            ny=max(lo,min(hi,y))
            changed += int(abs(ny-y)>1e-7)
            y=ny

        v.co=(x,y,z)

    obj.data.update()
    obj["reference_fit_method"]="dual_silhouette_vertex_clamp"
    obj["reference_fit_changed_components"]=changed
    obj["reference_target_width_m"]=width
    obj["reference_target_depth_m"]=depth
    obj["reference_target_height_m"]=height
    return {"changed":changed,"vertices":len(obj.data.vertices)}
