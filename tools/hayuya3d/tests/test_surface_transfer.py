from __future__ import annotations

import unittest

import numpy as np

from tools.hayuya3d.surface_transfer import (
    _closest_point_barycentric,
    blend_joint_weights_from_relation,
    build_surface_transfer_index,
    build_surface_transfer_relation,
    interpolate_vertex_values,
    query_surface_transfer,
)


class SurfaceTransferTests(unittest.TestCase):
    def setUp(self):
        self.vertices=np.asarray([
            [0.0,0.0,0.0],
            [1.0,0.0,0.0],
            [0.0,1.0,0.0],
        ],dtype=np.float64)
        self.faces=np.asarray([[0,1,2]],dtype=np.int64)

    def test_inside_triangle_uses_true_barycentric_coordinates(self):
        target=np.asarray([[0.25,0.25,0.0]],dtype=np.float64)
        relation=build_surface_transfer_relation(
            self.vertices,
            self.faces,
            target,
        )
        self.assertEqual(relation.fallback_vertices,0)
        self.assertTrue(np.array_equal(
            relation.triangle_vertex_ids[0],
            np.asarray([0,1,2],dtype=np.int64),
        ))
        self.assertTrue(np.allclose(
            relation.barycentric[0],
            np.asarray([0.5,0.25,0.25]),
            atol=1e-8,
        ))
        self.assertAlmostEqual(
            float(relation.surface_distance[0]),
            0.0,
            places=8,
        )

    def test_joint_weights_follow_triangle_barycentrics(self):
        target=np.asarray([[1.0/3.0,1.0/3.0,0.0]],dtype=np.float64)
        relation=build_surface_transfer_relation(
            self.vertices,
            self.faces,
            target,
        )
        joints=np.asarray([
            [0,0,0,0],
            [1,0,0,0],
            [2,0,0,0],
        ],dtype=np.int64)
        weights=np.asarray([
            [1.0,0.0,0.0,0.0],
            [1.0,0.0,0.0,0.0],
            [1.0,0.0,0.0,0.0],
        ],dtype=np.float64)
        out_joints,out_weights=blend_joint_weights_from_relation(
            joints,
            weights,
            relation,
        )
        active={
            int(joint):float(weight)
            for joint,weight in zip(out_joints[0],out_weights[0])
            if float(weight)>1e-7
        }
        self.assertEqual(set(active),{0,1,2})
        self.assertAlmostEqual(active[0],1.0/3.0,places=6)
        self.assertAlmostEqual(active[1],1.0/3.0,places=6)
        self.assertAlmostEqual(active[2],1.0/3.0,places=6)
        self.assertAlmostEqual(float(np.sum(out_weights[0])),1.0,places=7)

    def test_morph_delta_uses_same_surface_relation(self):
        target=np.asarray([[0.25,0.25,0.0]],dtype=np.float64)
        relation=build_surface_transfer_relation(
            self.vertices,
            self.faces,
            target,
        )
        deltas=np.asarray([
            [0.0,0.0,0.0],
            [0.0,0.0,1.0],
            [0.0,0.0,2.0],
        ],dtype=np.float64)
        out=interpolate_vertex_values(deltas,relation)
        self.assertEqual(out.shape,(1,3))
        self.assertTrue(np.allclose(
            out[0],
            np.asarray([0.0,0.0,0.75]),
            atol=1e-8,
        ))

    def test_outside_triangle_clamps_to_nearest_edge(self):
        target=np.asarray([[0.75,0.75,0.0]],dtype=np.float64)
        relation=build_surface_transfer_relation(
            self.vertices,
            self.faces,
            target,
        )
        bary=relation.barycentric[0]
        self.assertTrue(np.all(bary>=-1e-10))
        self.assertAlmostEqual(float(np.sum(bary)),1.0,places=8)
        self.assertAlmostEqual(float(bary[0]),0.0,places=7)
        self.assertAlmostEqual(float(bary[1]),0.5,places=7)
        self.assertAlmostEqual(float(bary[2]),0.5,places=7)
        self.assertAlmostEqual(
            float(relation.surface_distance[0]),
            np.sqrt(0.125),
            places=7,
        )

    def test_progressive_search_finds_large_triangle_with_far_centroid(self):
        vertices=[
            [-100.0,-100.0,0.0],
            [100.0,-100.0,0.0],
            [0.0,100.0,0.0],
        ]
        faces=[[0,1,2]]

        # Forty tiny distractor triangles have centroids and vertices much
        # closer to the target than the giant triangle's centroid/vertices,
        # but their surfaces sit above z=0. The exact search must expand past
        # the initial KD shortlist and recover the giant zero-distance face.
        for index in range(40):
            angle=2.0*np.pi*float(index)/40.0
            cx=0.25*np.cos(angle)
            cy=0.25*np.sin(angle)
            base=len(vertices)
            vertices.extend([
                [cx-0.01,cy-0.01,0.05],
                [cx+0.01,cy-0.01,0.05],
                [cx,cy+0.01,0.05],
            ])
            faces.append([base,base+1,base+2])

        relation=build_surface_transfer_relation(
            np.asarray(vertices,dtype=np.float64),
            np.asarray(faces,dtype=np.int64),
            np.asarray([[0.0,0.0,0.0]],dtype=np.float64),
            candidate_triangles=4,
        )
        self.assertEqual(relation.fallback_vertices,0)
        self.assertAlmostEqual(
            float(relation.surface_distance[0]),
            0.0,
            places=8,
        )
        self.assertEqual(
            set(int(x) for x in relation.triangle_vertex_ids[0]),
            {0,1,2},
        )
        self.assertEqual(
            relation.method,
            "hayuya-surface-transfer-bvh-barycentric-exact-v2",
        )
        self.assertGreater(relation.max_examined_triangles,0)
        self.assertLess(relation.max_examined_triangles,len(faces))
        self.assertGreater(relation.max_visited_bvh_nodes,0)

    def test_bvh_matches_bruteforce_on_random_mesh_queries(self):
        rng=np.random.default_rng(12345)
        vertices=rng.normal(size=(90,3)).astype(np.float64)
        faces=[]
        for _ in range(180):
            tri=rng.choice(len(vertices),size=3,replace=False)
            faces.append(tri.tolist())
        faces=np.asarray(faces,dtype=np.int64)
        targets=rng.normal(size=(25,3)).astype(np.float64)

        relation=build_surface_transfer_relation(
            vertices,
            faces,
            targets,
            bvh_leaf_size=6,
        )

        for row,point in enumerate(targets):
            best=None
            for tri_ids in faces:
                result=_closest_point_barycentric(
                    point,
                    vertices[int(tri_ids[0])],
                    vertices[int(tri_ids[1])],
                    vertices[int(tri_ids[2])],
                )
                if result is None:
                    continue
                closest,bary=result
                distance=float(np.linalg.norm(point-closest))
                if best is None or distance<best[0]:
                    best=(distance,np.asarray(tri_ids),np.asarray(bary))
            self.assertIsNotNone(best)
            self.assertAlmostEqual(
                float(relation.surface_distance[row]),
                float(best[0]),
                places=9,
            )
            reconstructed=np.sum(
                vertices[relation.triangle_vertex_ids[row]]
                * relation.barycentric[row][:,None],
                axis=0,
            )
            self.assertAlmostEqual(
                float(np.linalg.norm(point-reconstructed)),
                float(best[0]),
                places=9,
            )

    def test_dense_grid_prunes_triangle_work(self):
        size=70
        vertices=[]
        for y in range(size):
            for x in range(size):
                vertices.append([
                    float(x)/(size-1),
                    float(y)/(size-1),
                    0.0,
                ])
        faces=[]
        for y in range(size-1):
            for x in range(size-1):
                a=y*size+x
                b=a+1
                c=a+size
                d=c+1
                faces.append([a,b,d])
                faces.append([a,d,c])
        vertices=np.asarray(vertices,dtype=np.float64)
        faces=np.asarray(faces,dtype=np.int64)
        targets=np.asarray([
            [0.503,0.497,0.01],
            [0.123,0.876,0.02],
            [0.932,0.071,0.015],
        ],dtype=np.float64)

        relation=build_surface_transfer_relation(
            vertices,
            faces,
            targets,
            bvh_leaf_size=8,
        )
        self.assertEqual(relation.fallback_vertices,0)
        self.assertTrue(np.allclose(
            relation.surface_distance,
            np.asarray([0.01,0.02,0.015]),
            atol=1e-9,
        ))
        self.assertLess(
            relation.max_examined_triangles,
            max(64,len(faces)//20),
        )
        self.assertLess(
            relation.max_visited_bvh_nodes,
            max(128,len(faces)//10),
        )

    def test_surface_index_reuses_one_bvh_for_multiple_target_batches(self):
        index=build_surface_transfer_index(
            self.vertices,
            self.faces,
            bvh_leaf_size=2,
        )
        first=query_surface_transfer(
            index,
            np.asarray([[0.2,0.2,0.1]],dtype=np.float64),
        )
        second=query_surface_transfer(
            index,
            np.asarray([[0.6,0.2,0.2]],dtype=np.float64),
        )
        direct_first=build_surface_transfer_relation(
            self.vertices,
            self.faces,
            np.asarray([[0.2,0.2,0.1]],dtype=np.float64),
            bvh_leaf_size=2,
        )
        direct_second=build_surface_transfer_relation(
            self.vertices,
            self.faces,
            np.asarray([[0.6,0.2,0.2]],dtype=np.float64),
            bvh_leaf_size=2,
        )
        self.assertTrue(np.allclose(
            first.surface_distance,
            direct_first.surface_distance,
            atol=1e-12,
        ))
        self.assertTrue(np.allclose(
            second.surface_distance,
            direct_second.surface_distance,
            atol=1e-12,
        ))
        self.assertTrue(np.array_equal(
            first.triangle_vertex_ids,
            direct_first.triangle_vertex_ids,
        ))
        self.assertTrue(np.array_equal(
            second.triangle_vertex_ids,
            direct_second.triangle_vertex_ids,
        ))
        self.assertEqual(
            index.method,
            "hayuya-surface-transfer-index-bvh-v1",
        )

    def test_degenerate_triangle_falls_back_to_nearest_vertex(self):
        vertices=np.asarray([
            [0.0,0.0,0.0],
            [1.0,0.0,0.0],
            [2.0,0.0,0.0],
        ],dtype=np.float64)
        target=np.asarray([[0.9,0.2,0.0]],dtype=np.float64)
        relation=build_surface_transfer_relation(
            vertices,
            self.faces,
            target,
        )
        self.assertEqual(relation.fallback_vertices,1)
        self.assertTrue(np.array_equal(
            relation.triangle_vertex_ids[0],
            np.asarray([1,1,1],dtype=np.int64),
        ))
        self.assertTrue(np.allclose(
            relation.barycentric[0],
            np.asarray([1.0,0.0,0.0]),
        ))


if __name__=="__main__":
    unittest.main()
