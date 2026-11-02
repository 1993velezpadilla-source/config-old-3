"""The FPS diagnostics must NEVER obscure most of the 3D world again."""
import sys,struct
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_synthetic_mesh_smoke import cube,synthetic_rgba

class SyntheticViewmodelFOVTest(unittest.TestCase):
    def test_offset_is_lower_right_and_vertices_not_fullscreen(self):
        data=cube()
        magic,version,nvertices,nindices=struct.unpack_from("<4sIII",data)
        self.assertEqual((magic,version,nvertices,nindices),(b"IWVM",1,24,36))
        vals=[struct.unpack_from("<5f",data,16+i*20) for i in range(nvertices)]
        self.assertTrue(all(11<=v[0]<=20 for v in vals))
        self.assertTrue(all(-5<=v[1]<=-2 for v in vals))
        self.assertTrue(all(-4<=v[2]<=-2 for v in vals))
        self.assertLess(max(v[1] for v in vals)-min(v[1] for v in vals),2)
        self.assertLess(max(v[2] for v in vals)-min(v[2] for v in vals),1)
        self.assertEqual(set((u,v) for _,_,_,u,v in vals),
                         {(0.,0.),(0.,1.),(1.,0.),(1.,1.)})
        indices=struct.unpack_from("<"+"H"*nindices,data,16+nvertices*20)
        self.assertEqual(max(indices),nvertices-1)
    def test_texture_has_multiple_colors(self):
        data=synthetic_rgba()
        self.assertEqual(struct.unpack_from("<4sIII",data), (b"IWVT",1,2,2))
        self.assertEqual(len(data),32)
        self.assertEqual(len(set(data[16+i*4:20+i*4] for i in range(4))),4)

if __name__=="__main__":
    unittest.main()
