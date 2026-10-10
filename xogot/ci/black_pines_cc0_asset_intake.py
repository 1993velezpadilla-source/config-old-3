#!/usr/bin/env python3
"""Review-only: download and audit 16 individual free CC0 hospital GLBs.

No unreviewed models added to gameplay or APK. No third-party textures
or unknown URLs are trusted. This runs inside GitHub Actions CI only.
"""
import argparse
import hashlib
import json
import pathlib
import struct
import time
import urllib.request
from urllib.error import URLError, HTTPError

MANIFEST='https://3dassets.dev/api/v1/packs/hospital-wards-and-clinic-operations'
BASE='https://cdn.3dassets.dev/assets/'
CANDIDATES=[
    ('ward_bed','23588','patients'),
    ('bedside_cabinet','23593','patients'),
    ('iv_stand','23594','patients'),
    ('wheelchair','23600','patients'),
    ('patient_trolley','23598','triage'),
    ('privacy_screen','23599','isolation'),
    ('operating_table','23610','surgery'),
    ('surgical_lamp','23611','surgery'),
    ('anaesthesia_machine','23612','surgery'),
    ('instrument_trolley','23613','surgery'),
    ('medicine_fridge','23620','cafeteria'),
    ('reception_desk','23627','triage'),
    ('waiting_bench','23629','triage'),
    ('cleaning_cart','23645','security'),
    ('records_shelving','23650','security'),
    ('ambulance_comparison','23651','yard'),
]
EXTENSIONS={'KHR_mesh_quantization','KHR_materials_unlit','KHR_texture_transform',
            'KHR_materials_emissive_strength','KHR_materials_ior','KHR_materials_specular'}
def download(url,limit):
    if not url.startswith('https://'):
        raise ValueError('HTTPS only')
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'BlackPines-CC0-ArtQA/1.0'})
            with urllib.request.urlopen(req,timeout=30) as r:
                data=r.read(limit+1)
                if len(data)>limit:
                    raise ValueError('file too large')
                return data
        except (TimeoutError,URLError,HTTPError):
            if attempt==2:
                raise
            time.sleep(2+attempt*3)
    raise RuntimeError('download failed')
def inspect_glb(data):
    if len(data)<20:
        raise ValueError('missing GLB header')
    magic,version,size=struct.unpack_from('<4sII',data,0)
    if (magic,version,size)!=(b'glTF',2,len(data)):
        raise ValueError('corrupt GLB header')
    offset=12
    doc=None
    binary=0
    while offset<len(data):
        if offset+8>len(data):
            raise ValueError('truncated chunk')
        length,kind=struct.unpack_from('<I4s',data,offset)
        offset+=8
        if offset+length>len(data):
            raise ValueError('truncated data')
        raw=data[offset:offset+length]
        if kind==b'JSON':
            if doc is not None:
                raise ValueError('extra JSON chunk')
            doc=json.loads(raw.decode('utf8').rstrip(' \r\n\x00\t'))
        elif kind==b'BIN\x00':
            binary+=len(raw)
        offset+=length
    if not isinstance(doc,dict) or not str(doc.get('asset',{}).get('version','')).startswith('2.'):
        raise ValueError('invalid GLTF2 JSON')
    if not doc.get('meshes') or binary<=0:
        raise ValueError('no drawable geometry')
    required=set(doc.get('extensionsRequired',[]))
    if not required.issubset(EXTENSIONS):
        raise ValueError('unsupported required GLB extension '+str(required-EXTENSIONS))
    for child in doc.get('buffers',[])+doc.get('images',[]):
        if child.get('uri'):
            raise ValueError('no external GLB dependencies allowed')
    triangles=0
    for mesh in doc['meshes']:
        for prim in mesh.get('primitives',[]):
            if prim.get('mode',4)!=4:
                raise ValueError('nontriangle primitive')
            accessor=prim.get('indices',prim.get('attributes',{}).get('POSITION'))
            if accessor is None:
                raise ValueError('no primitive indices/positions')
            triangles+=int(doc['accessors'][accessor]['count'])//3
    return {'triangles':triangles,'meshes':len(doc['meshes']),
            'materials':len(doc.get('materials',[])),
            'requiredExtensions':sorted(required),'binBytes':binary}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True)
    opt=ap.parse_args()
    out=pathlib.Path(opt.out)
    out.mkdir(parents=True,exist_ok=True)
    response=json.loads(download(MANIFEST,3_000_000))
    pack=response.get('data',{})
    if (pack.get('id')!=142 or pack.get('assetCount')!=80
            or pack.get('licenseLabel')!='CC0 1.0 Universal'):
        raise ValueError('CC0 pack metadata/identity changed')
    assets={str(asset['id']):asset for asset in pack['assets']}
    results=[]
    total_tri=total_bytes=0
    for label,asset_id,room in CANDIDATES:
        a=assets.get(asset_id)
        if a is None or a.get('license',{}).get('slug')!='cc0-1.0':
            raise ValueError('missing/non-CC0 source '+asset_id)
        if a['license'].get('attributionRequired') is not False:
            raise ValueError('unapproved attribution rule '+asset_id)
        url=BASE+asset_id+'/v1/model.glb'
        if a.get('cdnUrl')!=url:
            raise ValueError('unexpected source CDN '+asset_id)
        metadata=a.get('stats',{})
        if not 0<int(metadata.get('triangles',0))<=3000:
            raise ValueError('polygon cap exceeded '+label)
        binary=download(url,250_000)
        info=inspect_glb(binary)
        if info['triangles']!=int(metadata['triangles']):
            raise ValueError('GLB/manifest triangles differ '+label+
                             ' remote='+str(info['triangles'])+
                             ' stated='+str(metadata['triangles']))
        if len(binary)!=int(metadata['fileSize']):
            raise ValueError('source file size drift '+label)
        total_tri+=info['triangles']
        total_bytes+=len(binary)
        if total_tri>14_000 or total_bytes>1_400_000:
            raise ValueError('audition mobile budget exceeded')
        filename=label+'.glb'
        (out/filename).write_bytes(binary)
        results.append({
            'id':asset_id,'label':label,'targetRoom':room,'filename':filename,
            'originalTitle':a['title'],'sourcePage':a['url'],'cdnUrl':url,
            'license':'CC0 1.0 Universal','attributionRequired':False,
            'aiGenerated':bool(a.get('aiGenerated')),
            'sha256':hashlib.sha256(binary).hexdigest(),
            'bytes':len(binary),'stats':info,
            'artReviewRequired':True,'notIncludedInProductionAPK':True
        })
        print('BLACK_PINES_CC0_REAL_GLB_GREEN',label,asset_id,
              info['triangles'],'triangles',len(binary),'bytes')
    report={'sourceManifest':MANIFEST,'packName':pack['title'],
            'packLicense':'CC0 1.0 Universal',
            'packAIOriginDisclosed':bool(pack.get('aiGenerated')),
            'stage':'REVIEW_ONLY_NOT_SHIPPED','assetCount':len(results),
            'totalTriangles':total_tri,'totalBytes':total_bytes,
            'assets':results,'humanArtApprovalRequired':True,
            'rightsDisclaimer':'Author declares CC0; independently review provenance before public release'}
    (out/'cc0-intake-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    if len(results)!=16:
        raise AssertionError('expected 16 curated medical props')
    print('BLACK_PINES_CC0_16_REAL_DOWNLOADS_GREEN',
          ' files=',len(results),' triangles=',total_tri,
          ' bytes=',total_bytes,' shipped_to_game=false')
if __name__=='__main__':
    main()
