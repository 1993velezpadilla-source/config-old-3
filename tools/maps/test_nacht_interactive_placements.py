#!/usr/bin/env python3
"""Regression test: UMAP placement coverage is not live gameplay readiness."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from compile_nacht_interactive_placements import CATEGORIES, REQUIRED


class SourceInteractiveCoverageTest(unittest.TestCase):
    def test_source_property_coverage_preserves_missing_gameplay_contracts(self) -> None:
        anchors = []
        for category in REQUIRED:
            props = {"AuthoredFixtureKey": "test-only"} if category == "buyable_door" else {}
            anchors.append({
                "className": CATEGORIES[category][0],
                "objectPath": f"Fixture.PersistentLevel.{category}_0",
                "rootComponentPath": "Root",
                "matrixRowMajor": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
                "sourceGameplayProperties": props,
            })

        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            scene = base / "scene.json"
            output = base / "placements.json"
            scene.write_text(json.dumps({
                "format": "xziel_visual_scene_v1",
                "actorAnchors": anchors,
            }), encoding="utf-8")
            compiler = Path(__file__).with_name("compile_nacht_interactive_placements.py")
            result = subprocess.run(
                [sys.executable, str(compiler), "--scene", str(scene), "--output", str(output)],
                capture_output=True, text=True, check=True,
            )
            compiled = json.loads(output.read_text(encoding="utf-8"))
            coverage = compiled["sourceGameplayPropertyCoverage"]
            self.assertIn("XZOGOT_NACHT_SOURCE_PROPERTY_COVERAGE", result.stdout)
            self.assertTrue(compiled["ready"])  # Placement census only.
            self.assertEqual(compiled["counts"]["power_switch"], 0)
            self.assertEqual(compiled["sourceAbsentCategories"], ["power_switch"])
            self.assertEqual(coverage["buyable_door"]["actorsWithGameplayProperties"], 1)
            self.assertEqual(
                coverage["buyable_door"]["propertyKeyCounts"], {"AuthoredFixtureKey": 1}
            )
            self.assertEqual(coverage["gumball_machine"]["actorsWithGameplayProperties"], 0)
            self.assertNotIn("nacht_interactable_gameplay_ready", compiled)
            print("XZOGOT_NACHT_SOURCE_PROPERTY_COVERAGE_TEST_GREEN")


if __name__ == "__main__":
    unittest.main()
