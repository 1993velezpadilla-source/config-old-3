import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

GLB=Path(os.environ.get("SANCTUM_REFERENCE_SCORE_GLB","sanctum-hero-altar-probe/sanctum-hero-altar.glb"))
PROFILE=Path(os.environ.get("SANCTUM_REFERENCE_SILHOUETTES","docs/sanctum-reference-silhouettes.v1.json"))
OUT=Path(os.environ.get("SANCTUM_REFERENCE_SCORE_OUT","sanctum-hero-altar-probe/reference-score"))
OUT.mkdir(parents=True,exist_ok=True)

def fail(msg):
    raise SystemExit("SANCTUM_REFERENCE_SCORE_FAIL: "+msg)

if not GLB.is_file():
    fail(f"missing GLB {GLB}")
if not PROFILE.is_file():
    fail(f"missing profile {PROFILE}")

profiles=json.loads(PROFILE.read_text(encoding="utf-8"))
altar=profiles["altar"]
body_dims=altar["body_dimensions_m"]

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(GLB))

exclude=("CANDLE","BOOK","TOP_CROSS","APSE_RUIN")
body=[
    o for o in bpy.context.scene.objects
    if o.type=="MESH"
    and o.name.startswith("SANCTUM_HERO_ALTAR_")
    and not any(t in o.name for t in exclude)
]
if not body:
    fail("no altar body objects found in GLB")

for o in bpy.context.scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in body
        o.hide_viewport=False

pts=[]
for o in body:
    pts.extend(o.matrix_world @ v.co for v in o.data.vertices)
mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
size=mx-mn
center=(mn+mx)*0.5

scene=bpy.context.scene
scene.render.engine="BLENDER_WORKBENCH"
scene.render.resolution_x=512
scene.render.resolution_y=512
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.render.film_transparent=True
scene.display.shading.light="FLAT"
scene.display.shading.color_type="SINGLE"
scene.display.shading.single_color=(1.0,1.0,1.0)
scene.display.shading.show_shadows=False
scene.display.shading.show_cavity=False
scene.display.shading.show_specular_highlight=False

cam_data=bpy.data.cameras.new("SANCTUM_REFERENCE_SCORE_CAMERA_DATA")
cam=bpy.data.objects.new("SANCTUM_REFERENCE_SCORE_CAMERA",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.type="ORTHO"
cam.data.clip_start=0.01
cam.data.clip_end=1000.0

def point_camera(pos,target):
    cam.location=Vector(pos)
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render_alpha(name,view):
    # Frame generously; mask is later normalized to its own tight bbox so the
    # IoU score measures silhouette shape rather than arbitrary camera padding.
    margin=1.12
    if view=="front":
        cam.data.ortho_scale=max(size.x,size.z)*margin
        point_camera((center.x,mn.y-max(size.y*2.5,6.0),center.z),center)
    elif view=="side":
        cam.data.ortho_scale=max(size.y,size.z)*margin
        point_camera((mn.x-max(size.x*2.5,6.0),center.y,center.z),center)
    else:
        fail(f"unknown view {view}")
    path=OUT/f"{name}.png"
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    img=bpy.data.images.get("Render Result")
    if img is None:
        fail("Render Result missing")
    w,h=img.size
    px=list(img.pixels[:])
    alpha=[px[i*4+3] for i in range(w*h)]
    return w,h,alpha,path

def bbox_mask(w,h,alpha,threshold=0.10):
    xs=[]; ys=[]
    for y in range(h):
        row=y*w
        for x in range(w):
            if alpha[row+x]>threshold:
                xs.append(x); ys.append(y)
    if not xs:
        fail("empty rendered silhouette")
    return min(xs),min(ys),max(xs),max(ys)

def point_in_poly(x,y,poly):
    inside=False
    j=len(poly)-1
    for i in range(len(poly)):
        xi,yi=poly[i]; xj,yj=poly[j]
        cross=((yi>y)!=(yj>y))
        if cross:
            x_at=(xj-xi)*(y-yi)/(yj-yi+1e-20)+xi
            if x < x_at:
                inside=not inside
        j=i
    return inside

def normalized_actual_mask(w,h,alpha,n=256):
    x0,y0,x1,y1=bbox_mask(w,h,alpha)
    bw=max(1,x1-x0+1)
    bh=max(1,y1-y0+1)
    out=[False]*(n*n)
    for oy in range(n):
        sy=y0+min(bh-1,int((oy+0.5)*bh/n))
        for ox in range(n):
            sx=x0+min(bw-1,int((ox+0.5)*bw/n))
            out[oy*n+ox]=alpha[sy*w+sx]>0.10
    return out,(x0,y0,x1,y1)

def polygon_mask(poly,n=256):
    out=[False]*(n*n)
    for y in range(n):
        py=(y+0.5)/n
        for x in range(n):
            px=(x+0.5)/n
            out[y*n+x]=point_in_poly(px,py,poly)
    return out

def iou(a,b):
    inter=sum(1 for x,y in zip(a,b) if x and y)
    union=sum(1 for x,y in zip(a,b) if x or y)
    return (inter/union if union else 0.0),inter,union

def width_profile(mask,n=256,bands=16):
    out=[]
    for bi in range(bands):
        y=min(n-1,max(0,int((bi+0.5)*n/bands)))
        xs=[x for x in range(n) if mask[y*n+x]]
        if xs:
            out.append((max(xs)-min(xs)+1)/n)
        else:
            out.append(0.0)
    return out

def profile_error(actual,ref):
    errs=[abs(a-b) for a,b in zip(actual,ref)]
    return {
        "mean_abs_error":sum(errs)/len(errs) if errs else 1.0,
        "max_abs_error":max(errs) if errs else 1.0,
        "bands":len(errs),
        "actual":actual,
        "reference":ref,
        "errors":errs,
    }

results={}
for view,key in (("front","front_body"),("side","side_left")):
    w,h,alpha,path=render_alpha(f"altar-{view}-mask",view)
    actual,bbox=normalized_actual_mask(w,h,alpha)
    ref=polygon_mask(altar[key]["points"])
    score,inter,union=iou(actual,ref)
    actual_profile=width_profile(actual)
    ref_profile=width_profile(ref)
    width_err=profile_error(actual_profile,ref_profile)
    results[view]={
        "iou":score,
        "intersection_pixels":inter,
        "union_pixels":union,
        "render_bbox_px":list(bbox),
        "render":path.name,
        "reference_points":len(altar[key]["points"]),
        "width_profile":width_err,
    }

target=Vector((float(body_dims["width"]),float(body_dims["depth"]),float(body_dims["height"])))
dim_ratio=Vector((size.x/target.x,size.y/target.y,size.z/target.z))
dim_error_pct=[
    abs(size.x-target.x)/target.x*100.0,
    abs(size.y-target.y)/target.y*100.0,
    abs(size.z-target.z)/target.z*100.0,
]
report={
    "status":"PASS",
    "glb":str(GLB),
    "body_objects":[o.name for o in body],
    "body_object_count":len(body),
    "measured_size_m":[float(size.x),float(size.y),float(size.z)],
    "target_body_dimensions_m":body_dims,
    "dimension_ratio":[float(dim_ratio.x),float(dim_ratio.y),float(dim_ratio.z)],
    "dimension_error_pct":dim_error_pct,
    "front":results["front"],
    "side":results["side"],
    "mean_iou":(results["front"]["iou"]+results["side"]["iou"])*0.5,
}
(OUT/"reference-score.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_REFERENCE_SCORE_PASS")
print(json.dumps(report,indent=2))
