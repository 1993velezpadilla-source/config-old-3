from mathutils import Vector

def scanline_range(points,z):
    hits=[]
    n=len(points)
    for i in range(n):
        x0,z0=points[i]
        x1,z1=points[(i+1)%n]
        if (z0 <= z < z1) or (z1 <= z < z0):
            t=(z-z0)/(z1-z0)
            hits.append(x0+t*(x1-x0))
        elif abs(z-z0)<1e-7 and abs(z1-z0)<1e-7:
            hits.extend((x0,x1))
    if len(hits)<2:
        return None
    return min(hits),max(hits)

def fit_object_group_to_silhouettes(objects,front_points,side_points,target_dimensions_m,anchor_xy=None,ground_z=None):
    """Clamp a multi-object authored assembly into traced front+side silhouettes.

    Objects remain separate, so materials, semantic roles and collision flags survive.
    Every mesh vertex is mapped through one shared group bbox, constrained in image
    space, then written back into its object's local coordinates.
    """
    meshes=[o for o in objects if o and o.type=="MESH" and len(o.data.vertices)]
    if not meshes:
        raise ValueError("empty mesh group")

    world=[]
    for o in meshes:
        for v in o.data.vertices:
            world.append(o.matrix_world @ v.co)

    mn=Vector((min(p.x for p in world),min(p.y for p in world),min(p.z for p in world)))
    mx=Vector((max(p.x for p in world),max(p.y for p in world),max(p.z for p in world)))
    size=mx-mn
    if min(size.x,size.y,size.z)<=1e-8:
        raise ValueError(f"degenerate group bounds: {size}")

    width=float(target_dimensions_m["width"])
    depth=float(target_dimensions_m["depth"])
    height=float(target_dimensions_m["height"])
    cx=float(anchor_xy[0]) if anchor_xy else (mn.x+mx.x)*0.5
    cy=float(anchor_xy[1]) if anchor_xy else (mn.y+mx.y)*0.5
    gz=float(ground_z) if ground_z is not None else mn.z

    changed=0
    total=0
    max_front_violation=0.0
    max_side_violation=0.0

    for o in meshes:
        inv=o.matrix_world.inverted()
        for v in o.data.vertices:
            p=o.matrix_world @ v.co
            xn=(p.x-mn.x)/size.x
            yn=(p.y-mn.y)/size.y
            zn=(p.z-mn.z)/size.z

            x=cx+(xn-0.5)*width
            y=cy+(yn-0.5)*depth
            z=gz+zn*height
            z01=max(0.0,min(0.999999,zn))

            fr=scanline_range(front_points,z01)
            if fr is not None:
                lo=cx+(fr[0]-0.5)*width
                hi=cx+(fr[1]-0.5)*width
                before=x
                x=max(lo,min(hi,x))
                max_front_violation=max(max_front_violation,max(0.0,lo-before,before-hi))

            sr=scanline_range(side_points,z01)
            if sr is not None:
                lo=cy+(sr[0]-0.5)*depth
                hi=cy+(sr[1]-0.5)*depth
                before=y
                y=max(lo,min(hi,y))
                max_side_violation=max(max_side_violation,max(0.0,lo-before,before-hi))

            q=Vector((x,y,z))
            old=p
            if (q-old).length>1e-7:
                changed+=1
            total+=1
            v.co=inv @ q
        o.data.update()
        o["reference_fit_method"]="group_dual_silhouette_vertex_clamp"

    return {
        "objects":len(meshes),
        "vertices":total,
        "changed_vertices":changed,
        "target_dimensions_m":{"width":width,"depth":depth,"height":height},
        "max_preclamp_front_violation_m":max_front_violation,
        "max_preclamp_side_violation_m":max_side_violation,
    }

def count_group_violations(objects,front_points,side_points,target_dimensions_m,anchor_xy,ground_z,tolerance=1e-5):
    width=float(target_dimensions_m["width"])
    depth=float(target_dimensions_m["depth"])
    height=float(target_dimensions_m["height"])
    cx=float(anchor_xy[0]); cy=float(anchor_xy[1]); gz=float(ground_z)
    violations=0
    worst=0.0
    total=0
    for o in objects:
        if not o or o.type!="MESH":
            continue
        for v in o.data.vertices:
            p=o.matrix_world @ v.co
            zn=(p.z-gz)/height
            if zn < -tolerance or zn > 1.0+tolerance:
                violations+=1
                worst=max(worst,max(-zn,zn-1.0)*height)
                continue
            z01=max(0.0,min(0.999999,zn))
            fr=scanline_range(front_points,z01)
            if fr is not None:
                lo=cx+(fr[0]-0.5)*width
                hi=cx+(fr[1]-0.5)*width
                d=max(0.0,lo-p.x,p.x-hi)
                if d>tolerance:
                    violations+=1
                    worst=max(worst,d)
            sr=scanline_range(side_points,z01)
            if sr is not None:
                lo=cy+(sr[0]-0.5)*depth
                hi=cy+(sr[1]-0.5)*depth
                d=max(0.0,lo-p.y,p.y-hi)
                if d>tolerance:
                    violations+=1
                    worst=max(worst,d)
            total+=1
    return {"vertices_checked":total,"violations":violations,"worst_violation_m":worst}
