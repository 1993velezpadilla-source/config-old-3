#!/usr/bin/env python3
"""Analyze Vril gl_mesh.c display-list command count BEFORE Android startup.

Quake Vril uses fan/strip packing; numtris<=2048 does NOT guarantee that
commands[8192] is large enough. For 1936-triangle zfull.mdl it creates 8713
ints, provably writing past the original 8192-element static buffer.
This script reproduces greedy fan/strip choices from pinned gl_mesh.c.
"""
from pathlib import Path
import argparse,struct,json
from collections import defaultdict

def read_tris(raw):
    assert raw[:4]==b"IDPO" and struct.unpack_from("<i",raw,4)[0]==6
    skins,w,h,nverts,ntris,nframes,_,_=struct.unpack_from("<8i",raw,48)
    pos=84
    for _ in range(skins):
        typ=struct.unpack_from("<i",raw,pos)[0];pos+=4
        if typ==0:pos+=w*h
        elif typ==1:
            n=struct.unpack_from("<i",raw,pos)[0];pos+=4+4*n+w*h*n
        else:raise ValueError("unsupported skin group")
    pos+=12*nverts
    return [struct.unpack_from("<4i",raw,pos+16*i) for i in range(ntris)]

def gl_command_count(tris):
    n=len(tris)
    edge_lookup=defaultdict(list)
    for j,(front,a,b,c) in enumerate(tris):
        for x,y in ((a,b),(b,c),(c,a)):
            edge_lookup[(front,x,y)].append(j)
    used=bytearray(n)
    commands=1
    order=0
    groups=0
    for i,(front,a,b,c) in enumerate(tris):
        if used[i]:continue
        best=[]
        v=[a,b,c]
        for typ in (0,1):    # fan, strip
            for startv in range(3):
                vv=[v[startv%3],v[(startv+1)%3],v[(startv+2)%3]]
                if typ==0: m1,m2=vv[0],vv[2]
                else: m1,m2=vv[2],vv[1]
                part=[i]
                while True:
                    next_tri=None
                    for j in edge_lookup.get((front,m1,m2),()):
                        if j<=i:continue
                        w=tris[j][1:]
                        for k in range(3):
                            if w[k]==m1 and w[(k+1)%3]==m2:
                                next_tri=j,w[(k+2)%3]
                                break
                        if next_tri:break
                    if next_tri is None:break
                    j,newv=next_tri
                    if used[j] or j in part:break
                    if typ==0:m2=newv
                    elif len(part)&1:m2=newv
                    else:m1=newv
                    part.append(j)
                if len(part)>len(best):best=part
        assert best
        for j in best:used[j]=1
        groups+=1
        order+=len(best)+2
        commands+=1+2*(len(best)+2)
    assert all(used)
    return {"triangles":n,"commands":commands,"vertexorder":order,"strips_or_fans":groups,
            "old_capacity_exceeded":commands>8192,"new_capacity_safe":commands<=16384}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report={}
    for path in sorted(a.models.glob("*.mdl")):
        report[path.name]=gl_command_count(read_tris(path.read_bytes()))
        print("XZIEL_ALIAS_DISPLAYLIST",path.name,report[path.name])
        assert report[path.name]["new_capacity_safe"],"Still exceeds newly guarded array"
        assert report[path.name]["vertexorder"]<=8192,"vertexorder array overflow"
    assert len(report)==10
    assert report["zfull.mdl"]["commands"]>8192,"Expected original GL buffer overflow not reproduced"
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps({"status":"NEW_GL_COMMAND_CAPACITY_VERIFIED","models":report},indent=2)+"\n")
    print("XZIEL_ZOMBIE_ALIAS_COMMAND_OVERFLOW_REPRODUCED_AND_GUARDED")
if __name__=="__main__":main()
