"""Actual portable IWSK format tests using synthetic glTF joint-weights.

No original commercial gun mesh, animations or graphics in this fixture.
"""
import json,struct,sys,tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_glb_to_iwvm import load_glb
from iw3_glb_to_iwsk import export,HEADER,BONE,VERTEX,BASIS,basis_convert
from test_viril_iw3_glb_converter import example_glb


def synth_skinned_glb():
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"mesh.glb"
        path.write_bytes(example_glb())
        d,old=load_glb(path)
    d["nodes"][0]["skin"]=0
    d["nodes"].append({"name":"tag_weapon","translation":[0.,0.,0.]})
    d["scenes"][0]["nodes"].append(1)
    d["skins"]=[{"joints":[1],"inverseBindMatrices":5}]
    d["meshes"][0]["primitives"][0]["attributes"].update({"JOINTS_0":3,"WEIGHTS_0":4})
    # Original OAT exporter writes u8 four joint indices, float four weights.
    joints=bytes([0,0,0,0]*3)
    weights=struct.pack("<"+"f"*12,*([1.,0.,0.,0.]*3))
    ident=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
    bind=struct.pack("<16f",*ident)
    segments=[joints,weights,bind]
    blob=bytearray(old)
    for offset,(seg,ty,ctype,count) in enumerate(
            zip(segments,("VEC4","VEC4","MAT4"),(5121,5126,5126),(3,3,1))):
        viewidx=len(d["bufferViews"])
        d["bufferViews"].append({"buffer":0,"byteOffset":len(blob),"byteLength":len(seg)})
        d["accessors"].append({"bufferView":viewidx,"componentType":ctype,
                               "count":count,"type":ty})
        blob.extend(seg)
    d["buffers"][0]["byteLength"]=len(blob)
    raw=json.dumps(d,separators=(",",":")).encode()
    raw+=b" "*((-len(raw))%4)
    payload=struct.pack("<I4s",len(raw),b"JSON")+raw+struct.pack("<I4s",len(blob),b"BIN\\0")+blob
    return struct.pack("<4sII",b"glTF",2,12+len(payload))+payload


class OriginalIWSKTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"synthetic.glb"
        self.path.write_bytes(synth_skinned_glb())

    def test_real_native_layout_matches_glb_vertex_count(self):
        data,info=export(self.path)
        self.assertEqual(HEADER.unpack_from(data),(b"IWSK",1,3,1,0))
        self.assertEqual(len(data),HEADER.size+BONE.size+3*VERTEX.size)
        bone=BONE.unpack_from(data,HEADER.size)
        self.assertEqual(bone[0].split(b"\\0",1)[0],b"tag_weapon")
        self.assertEqual(bone[1],-1)
        for offset in range(3):
            x=VERTEX.unpack_from(data,HEADER.size+BONE.size+offset*VERTEX.size)
            self.assertEqual(x[:4],(0,0,0,0))
            self.assertEqual(x[4:],(1.,0.,0.,0.))
        self.assertEqual(info["original_glb_joints"],1)
        self.assertFalse(info["original_reload_skeletal_playback"])

    def test_undeclared_skin_fails(self):
        data,_=load_glb(self.path)
        self.assertTrue(data["skins"])
        self.path.write_bytes(example_glb())
        with self.assertRaisesRegex(ValueError,"one original glTF skin"):
            export(self.path)

    def test_change_of_basis_is_reversible(self):
        ident=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
        self.assertEqual(basis_convert(ident,"gltf_yup_to_quake_zup"),ident)
        x=(1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,3.,4.,5.,1.)
        y=basis_convert(x,"gltf_yup_to_quake_zup")
        self.assertEqual(y[12:15],(-5.,-3.,4.))


if __name__=="__main__":unittest.main()
