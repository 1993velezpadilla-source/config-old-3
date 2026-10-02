#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DETAIL_DIR_TOKENS = {
    "detail",
    "details",
    "closeup",
    "closeups",
    "macro",
    "texture",
    "textures",
    "material",
    "materials",
    "surface",
    "surfaces",
}

DETAIL_TOKENS = (
    "detail",
    "closeup",
    "close_up",
    "macro",
    "face_close",
    "face_detail",
    "hand_detail",
    "hair_detail",
    "dress_detail",
    "cloth_detail",
    "fabric",
    "texture",
    "material",
    "surface",
    "torso_detail",
    "hem_detail",
    "accessory_detail",
    "logo_detail",
    "inscription_detail",
    "tattoo_detail",
    "wound_detail",
)

VIEW_RULES = [
    (("front_45_right", "front45right", "front_right_45"), 45.0),
    (("back_45_right", "back45right", "back_right_45"), 135.0),
    (("back_45_left", "back45left", "back_left_45"), 225.0),
    (("front_45_left", "front45left", "front_left_45"), 315.0),
    (("right_side", "_right", "right_"), 90.0),
    (("left_side", "_left", "left_"), 270.0),
    (("back", "rear"), 180.0),
    (("front",), 0.0),
]

COVERAGE_PRIORITY = [90.0, 180.0, 270.0, 45.0, 135.0, 225.0, 315.0, 0.0]


DETAIL_REGION_RULES = [
    (("face", "head", "hair", "eye", "eyes", "mouth", "teeth"), "head"),
    (("torso", "chest", "logo", "inscription", "tattoo", "wound"), "middle"),
    (("hem", "foot", "feet", "shoe", "shoes"), "lower"),
    (("hand", "hands", "accessory", "rosary", "weapon", "prop"), "local"),
]


def infer_detail_region_hint(path: Path) -> str | None:
    """
    Infer only coarse image-space regions from explicit detail naming.

    This is intentionally conservative: it never claims geometry semantics from an
    unnamed image. The hint constrains local patch retrieval, not mesh generation.
    """
    name = path.stem.lower().replace("-", "_").replace(" ", "_")
    parent_parts = {
        part.lower().replace("-", "_").replace(" ", "_")
        for part in path.parts[:-1]
    }
    haystack = "_".join([*sorted(parent_parts), name])
    for tokens, region in DETAIL_REGION_RULES:
        if any(token in haystack for token in tokens):
            return region
    return None


def infer_view_hint(path: Path) -> float | None:
    name = path.stem.lower().replace("-", "_").replace(" ", "_")
    for needles, angle in VIEW_RULES:
        if any(n in name for n in needles):
            return angle
    return None


def order_for_multiview_coverage(paths: list[Path]) -> list[Path]:
    """Prefer broad canonical-angle coverage before redundant same-angle references."""
    indexed = list(enumerate(paths))
    priority = {angle: i for i, angle in enumerate(COVERAGE_PRIORITY)}

    def key(item):
        original_index, path = item
        hint = infer_view_hint(path)
        if hint is None:
            return (1, original_index, original_index)
        return (0, priority.get(hint, len(priority)), original_index)

    return [path for _, path in sorted(indexed, key=key)]


@dataclass(frozen=True)
class ReferenceRoles:
    geometry: list[Path]
    detail: list[Path]


def classify_reference(path: Path) -> str:
    """Conservatively infer whether a reference is geometry or local-detail evidence."""
    name = path.stem.lower().replace("-", "_").replace(" ", "_")
    parent_parts = {
        part.lower().replace("-", "_").replace(" ", "_")
        for part in path.parts[:-1]
    }
    if parent_parts & DETAIL_DIR_TOKENS:
        return "detail"
    if any(token in name for token in DETAIL_TOKENS):
        return "detail"
    return "geometry"


def split_reference_roles(paths: list[Path]) -> ReferenceRoles:
    geometry: list[Path] = []
    detail: list[Path] = []

    for path in paths:
        if classify_reference(path) == "detail":
            detail.append(path)
        else:
            geometry.append(path)

    if not geometry and paths:
        geometry = list(paths)
        detail = []

    return ReferenceRoles(geometry=geometry, detail=detail)
