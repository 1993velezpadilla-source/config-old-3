from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from PIL import Image, ImageDraw

from turntable_qa import (
    build_turntable_comparison_sheet,
    color_histogram_similarity,
    score_source_to_turntable,
    select_frame,
)
from visual_judge import SourceViewScore


def make_shape(path: Path, *, kind: str, color=(180, 70, 40, 255)) -> None:
    image = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if kind == "tall":
        draw.rectangle((72, 24, 120, 168), fill=color)
    elif kind == "wide":
        draw.rectangle((24, 72, 168, 120), fill=color)
    elif kind == "small":
        draw.ellipse((82, 82, 110, 110), fill=color)
    else:
        raise ValueError(kind)
    image.save(path)


class TurntableQATests(unittest.TestCase):
    def test_selects_orientation_locked_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for index, offset in enumerate(range(0, 360, 45)):
                path = root / f"{index:02d}_{offset:03d}.png"
                make_shape(path, kind="tall")
                frames.append((float(offset), path))

            selected = select_frame(frames, 91.0)
            self.assertIsNotNone(selected)
            self.assertEqual(selected[0], 90.0)
            self.assertLessEqual(selected[2], 1.0)

    def test_comparison_sheet_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_front.png"
            make_shape(source, kind="tall")
            frames = []
            for index, offset in enumerate(range(0, 360, 45)):
                path = root / f"{index:02d}_{offset:03d}.png"
                make_shape(path, kind="tall")
                frames.append(path)

            view = SourceViewScore(
                source=str(source),
                best_score=100.0,
                best_azimuth=0.0,
                best_elevation=0.0,
                best_up_axis="y",
                silhouette_iou=1.0,
                boundary_f1=1.0,
                mask_confidence=1.0,
                mask_method="alpha",
            )
            result = score_source_to_turntable([source], [view], frames)
            sheet = build_turntable_comparison_sheet(
                result,
                root / "comparison.png",
            )
            self.assertTrue(sheet and sheet.is_file())
            self.assertGreater(sheet.stat().st_size, 100)

    def test_matching_source_and_turntable_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_front.png"
            make_shape(source, kind="tall")

            frames = []
            for index, offset in enumerate(range(0, 360, 45)):
                path = root / f"{index:02d}_{offset:03d}.png"
                make_shape(path, kind="tall")
                frames.append(path)

            view = SourceViewScore(
                source=str(source),
                best_score=100.0,
                best_azimuth=15.0,
                best_elevation=0.0,
                best_up_axis="y",
                silhouette_iou=1.0,
                boundary_f1=1.0,
                mask_confidence=1.0,
                mask_method="alpha",
            )
            result = score_source_to_turntable([source], [view], frames)
            self.assertTrue(result.ready)
            self.assertEqual(result.coverage, 1)
            self.assertEqual(result.catastrophic_mismatches, 0)
            self.assertGreater(result.score, 95.0)
            self.assertEqual(result.views[0].selected_offset, 0.0)

    def test_high_confidence_shape_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source_front.png"
            make_shape(source, kind="tall")

            frames = []
            for index, offset in enumerate(range(0, 360, 45)):
                path = root / f"{index:02d}_{offset:03d}.png"
                make_shape(path, kind="wide", color=(20, 200, 80, 255))
                frames.append(path)

            view = SourceViewScore(
                source=str(source),
                best_score=100.0,
                best_azimuth=0.0,
                best_elevation=0.0,
                best_up_axis="y",
                silhouette_iou=1.0,
                boundary_f1=1.0,
                mask_confidence=1.0,
                mask_method="alpha",
            )
            result = score_source_to_turntable([source], [view], frames)
            self.assertFalse(result.ready)
            self.assertEqual(result.catastrophic_mismatches, 1)
            self.assertTrue(result.views[0].catastrophic_mismatch)

    def test_color_histogram_is_high_for_same_foreground_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.png"
            b = root / "b.png"
            make_shape(a, kind="tall", color=(90, 140, 210, 255))
            make_shape(b, kind="wide", color=(90, 140, 210, 255))
            score = color_histogram_similarity(a, b)
            self.assertGreater(score, 99.0)


if __name__ == "__main__":
    unittest.main()
