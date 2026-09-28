from pathlib import Path
p=Path("tools/blender/build_cathedral_roster.py")
s=p.read_text(encoding="utf-8")
a=s.index("def sister_boot_pair(body,rig,h,mats):")
b=s.index("\ndef nun_coif_cap(",a)
new='''def sister_boot_pair(body,rig,h,mats):
    """Pass 38 shaped closed shoes from ring sections."""
    leather=mat("M_SisterShoeLeather","#171516",.82,0,noise=True)
    sole_mat=mat("M_SisterShoeSole","#0B0A0B",.92,0,noise=True)
    out=[]
    for sign,label in ((-1,"L"),(1,"R")):
        pts=[v.co.copy() for v in body.data.vertices if v.co.z/h<.075 and v.co.x*sign>.010*h]
        cx=(sum(q.x for q in pts)/len(pts)) if pts else sign*.047*h
        cy=(sum(q.y for q in pts)/len(pts)) if pts else -.018*h
        sections=[(-.050,.022,.026),(-.026,.025,.029),(.004,.029,.027),(.034,.030,.021),(.054,.024,.014)]
        seg=28; vs=[]; fs=[]
        for yi,hw,hz in sections:
            for j in range(seg):
                ang=2*math.pi*j/seg
                vs.append((cx+hw*h*math.cos(ang),cy+yi*h,.010*h+hz*h*(.15+.85*max(0.0,math.sin(ang)))))
        for r in range(len(sections)-1):
            for j in range(seg):
                k=(j+1)%seg; fs.append((r*seg+j,r*seg+k,(r+1)*seg+k,(r+1)*seg+j))
        me=bpy.data.meshes.new("SisterShoe_"+label+"Mesh"); me.from_pydata(vs,[],fs); me.update()
        upper=bpy.data.objects.new("SisterShoe_"+label,me); bpy.context.collection.objects.link(upper); assign(upper,leather)
        bev=upper.modifiers.new("ShoeEdgeSoft","BEVEL"); bev.width=.0018*h; bev.segments=3
        sub=upper.modifiers.new("ShoeSmooth","SUBSURF"); sub.subdivision_type="CATMULL_CLARK"; sub.levels=1; sub.render_levels=1
        out.append(upper)
        out.append(cube("SisterSole_"+label,(cx,cy+.002*h,.006*h),(.030*h,.054*h,.0035*h),sole_mat,.0025*h))
    return out
'''
s=s[:a]+new+s[b:]
a=s.index('def priority_head_cover(body,h,style,mats):')
b=s.index('\ndef eye_socket_rings(',a)
old=s[a:b]
start=old.index('        out.extend(sister_fitted_wimple(body,h,mats))')
end=old.index('    elif style=="stained_shade":')
replacement='''        out.extend(sister_fitted_wimple(body,h,mats))
        out.append(drape_open("NunUnderWimpleCape",h,ivory,[
            (.826,.074,.046),(.808,.086,.052),(.786,.102,.059),(.760,.122,.066),(.735,.142,.073)
        ],segments=128,theta_max=2.28,tatter=.010,phase=.18,subdiv=2))
        out.append(drape_open("NunBackVeil",h,blue,[
            (.946,.060,.052),(.918,.066,.058),(.884,.073,.064),(.848,.082,.071),
            (.812,.092,.079),(.780,.104,.087),(.750,.116,.095),(.724,.128,.101)
        ],segments=128,theta_max=2.42,tatter=.040,phase=.41,subdiv=2))
'''
old=old[:start]+replacement+old[end:]
s=s[:a]+old+s[b:]
s=s.replace("Sister of Ash pass 35 — continuous fitted U-wimple, compact closed shoes without toe spheres, full crown coverage and layered habit retained","Sister of Ash pass 38 — shaped closed shoes, continuous under-wimple cape, softened fitted veil, crown coverage retained")
p.write_text(s,encoding="utf-8")
print("Applied Sister of Ash pass 38 production correction")
