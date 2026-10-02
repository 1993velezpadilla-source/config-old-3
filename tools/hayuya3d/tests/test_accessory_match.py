from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trimesh

from tools.hayuya3d.accessory_match import (
    inspect_accessories,
    match_accessories,
)


def write_asset(
    path:Path,
    accessory_centers:list[tuple[float,float,float]],
)->None:
    body=trimesh.creation.icosphere(
        subdivisions=2,
        radius=1.0,
    )
    scene=trimesh.Scene()
    scene.add_geometry(body,node_name="body")
    for index,center in enumerate(accessory_centers):
        accessory=trimesh.creation.box(
            extents=[0.14,0.18,0.12]
        )
        accessory.apply_translation(center)
        scene.add_geometry(
            accessory,
            node_name=f"accessory_{index}",
        )
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(scene)
    )


class AccessoryMatchTests(unittest.TestCase):
    def test_clear_detached_accessory_match_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            write_asset(base,[(1.12,0.18,0.0)])
            write_asset(donor,[(1.15,0.20,0.01)])

            base_candidates=inspect_accessories(
                base,
                mode="prop",
            )
            self.assertEqual(len(base_candidates),1)

            report=match_accessories(
                base,
                donor,
                mode="prop",
            )
            self.assertTrue(report.ready,report.errors)
            ready=[item for item in report.matches if item.ready]
            self.assertEqual(len(ready),1)
            self.assertGreaterEqual(ready[0].confidence,0.55)
            self.assertEqual(
                ready[0].spatial_label,
                base_candidates[0].spatial_label,
            )
            self.assertEqual(report.unmatched_base,[])

    def test_ambiguous_nearly_identical_donors_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            write_asset(base,[(1.12,0.18,0.0)])
            write_asset(
                donor,
                [
                    (1.14,0.19,0.00),
                    (1.15,0.19,0.01),
                ],
            )

            report=match_accessories(
                base,
                donor,
                mode="prop",
                min_ambiguity_margin=0.08,
            )
            self.assertFalse(report.ready)
            self.assertTrue(report.ambiguous_base)
            self.assertTrue(
                any(
                    "ambiguous donor" in blocker
                    for match in report.matches
                    for blocker in match.blockers
                ),
                report.matches,
            )

    def test_far_floating_fragment_is_not_attachment_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            write_asset(base,[(1.12,0.18,0.0)])
            write_asset(donor,[(4.0,0.18,0.0)])

            report=match_accessories(
                base,
                donor,
                mode="prop",
            )
            self.assertFalse(report.ready)
            self.assertTrue(
                any(
                    "too detached" in blocker
                    for match in report.matches
                    for blocker in match.blockers
                ),
                report.matches,
            )

    def test_base_without_accessory_has_nothing_safe_to_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            write_asset(base,[])
            write_asset(donor,[(1.12,0.18,0.0)])

            report=match_accessories(
                base,
                donor,
                mode="prop",
            )
            self.assertFalse(report.ready)
            self.assertEqual(report.base_accessories,0)
            self.assertTrue(
                any("base has no detached accessory" in x for x in report.warnings),
                report.warnings,
            )


if __name__=="__main__":
    unittest.main()
