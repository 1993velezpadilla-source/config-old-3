from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from judge_v4 import (
    JudgeV4Thresholds,
    _normalized_frame,
    face_proportion_failures,
)


def _report(nose_to_chin: float, nose_eye: float):
    return {
        "face_expected_from_source": True,
        "reference_profile": {
            "nose_to_chin": 1.0,
            "nose_eye_center_offset": 1.0,
        },
        "candidate": [
            {
                "features": {
                    "nose_to_chin": nose_to_chin,
                    "nose_eye_center_offset": nose_eye,
                }
            }
        ],
    }


def test_generic_face_proportions_pass_current_source_relative_shape():
    failures, gate = face_proportion_failures(
        _report(1.10, 0.93),
        JudgeV4Thresholds(),
    )
    assert failures == []
    assert gate["passed"] is True
    assert gate["source_relative"] is True
    assert gate["asset_specific_coordinates"] is False


def test_generic_face_proportions_reject_nose_drift():
    failures, gate = face_proportion_failures(
        _report(1.75, 0.50),
        JudgeV4Thresholds(),
    )
    assert gate["passed"] is False
    assert any("nose_to_chin" in item for item in failures)
    assert any("nose_eye_center_offset" in item for item in failures)


def test_gate_uses_new_source_profile_not_monja_template():
    report = {
        "face_expected_from_source": True,
        "reference_profile": {
            "nose_to_chin": 2.0,
            "nose_eye_center_offset": 0.5,
        },
        "candidate": [
            {
                "features": {
                    "nose_to_chin": 2.1,
                    "nose_eye_center_offset": 0.48,
                }
            }
        ],
    }
    failures, gate = face_proportion_failures(report, JudgeV4Thresholds())
    assert failures == []
    assert gate["ratios"]["nose_to_chin"] == 1.05
    assert gate["ratios"]["nose_eye_center_offset"] == 0.96



def test_dedicated_face_frame_is_resized_without_subject_recrop(tmp_path: Path):
    from PIL import Image, ImageDraw

    source = tmp_path / "face_frame.png"
    output = tmp_path / "normalized.png"
    image = Image.new("RGB", (320, 180), (24, 24, 24))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 45, 30, 135), fill=(255, 0, 0))
    draw.rectangle((289, 45, 319, 135), fill=(0, 0, 255))
    draw.rectangle((120, 20, 200, 160), fill=(210, 190, 170))
    image.save(source)

    _normalized_frame(source, output, size=512)

    result = Image.open(output).convert("RGB")
    pixels = list(result.getdata())
    assert any(r > 240 and g < 20 and b < 20 for r, g, b in pixels)
    assert any(b > 240 and r < 20 and g < 20 for r, g, b in pixels)
