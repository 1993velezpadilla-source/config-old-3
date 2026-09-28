#!/usr/bin/env python3
"""Infer CTW pedinfos -> model resource links from a user-owned game.pak.

The pedinfos record layout is not assumed.  The probe scores fixed-stride
16-bit fields by whether they consistently reference resources that are proven
CTW model blobs ("MG").  Results are evidence only until a real build is
validated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

import mdl_probe
import pak_inventory


MAX_RECORD_SIZE = 256
MAX_FIELD_SCAN = 96
MIN_RECORDS = 3


def _read_resource(fp, index, rid: int) -> bytes:
    start, end = pak_inventory.resource_span(index, rid)
    fp.seek(start)
    return fp.read(end - start)


def _maintable_ids(fp, index):
    start, end = pak_inventory.resource_span(index, 0)
    fp.seek(start)
    raw = fp.read(min(46, end - start))
    if len(raw) < 46:
        raise ValueError("maintable resource is too small for 23 ids")
    return struct.unpack_from("<23h", raw, 0)


def _model_ids(fp, index) -> set[int]:
    out = set()
    for rid in range(index["resource_count"]):
        start, end = pak_inventory.resource_span(index, rid)
        if end - start < 2:
            continue
        fp.seek(start)
        if fp.read(2) == b"MG":
            out.add(rid)
    return out


def score_layout(
    blob: bytes,
    model_ids: set[int],
    *,
    start: int,
    record_size: int,
    record_count: int,
    field_offset: int,
) -> dict | None:
    if (
        record_size < 2
        or field_offset < 0
        or field_offset + 2 > record_size
        or record_count < MIN_RECORDS
    ):
        return None
    if start + record_size * record_count > len(blob):
        return None

    values = []
    hits = []
    for i in range(record_count):
        off = start + i * record_size + field_offset
        value = struct.unpack_from("<h", blob, off)[0]
        values.append(value)
        if value in model_ids:
            hits.append({"record": i, "model_resource_id": value})

    match_count = len(hits)
    if match_count == 0:
        return None

    unique = sorted({x["model_resource_id"] for x in hits})
    ratio = match_count / record_count

    # High ratio matters most. Multiple distinct real model refs make random
    # collisions less plausible. Penalize implausibly tiny record sizes.
    score = ratio * 100.0
    score += min(len(unique), 16) * 3.0
    if record_size < 8:
        score -= 15.0

    return {
        "start": start,
        "record_size": record_size,
        "record_count": record_count,
        "field_offset": field_offset,
        "match_count": match_count,
        "match_ratio": ratio,
        "unique_model_ids": unique,
        "unique_model_count": len(unique),
        "score": score,
        "hits": hits,
    }


def infer_layout(blob: bytes, model_ids: set[int]) -> dict:
    candidates = []

    # Strong hypothesis: u32 record count followed by a fixed-stride table.
    # Resources are block-aligned in the PAK, so trailing zero padding is
    # allowed and must not be mistaken for record bytes.
    if len(blob) >= 4:
        count = struct.unpack_from("<I", blob, 0)[0]
        payload = len(blob) - 4
        if MIN_RECORDS <= count <= 4096 and payload >= count * 2:
            for record_size in range(8, MAX_RECORD_SIZE + 1, 2):
                used = count * record_size
                if used > payload:
                    break
                tail = blob[4 + used:]
                if tail:
                    nonzero = sum(1 for b in tail if b)
                    zero_ratio = 1.0 - (nonzero / len(tail))
                else:
                    zero_ratio = 1.0

                # A large non-zero tail means this stride probably truncated
                # real records/data. Padding-heavy tails are acceptable.
                if len(tail) > 32 and zero_ratio < 0.95:
                    continue

                for field in range(
                    0,
                    min(record_size, MAX_FIELD_SCAN),
                    2,
                ):
                    item = score_layout(
                        blob,
                        model_ids,
                        start=4,
                        record_size=record_size,
                        record_count=count,
                        field_offset=field,
                    )
                    if item:
                        item["layout_source"] = "u32_count_fixed_stride"
                        item["padding_bytes"] = len(tail)
                        item["padding_zero_ratio"] = zero_ratio
                        item["score"] += 20.0 + zero_ratio * 5.0
                        candidates.append(item)

    # Conservative fallback for builds with a small fixed header or padding.
    for start in (0, 4, 8, 12, 16):
        remaining = len(blob) - start
        if remaining < MIN_RECORDS * 8:
            continue
        for record_size in range(8, MAX_RECORD_SIZE + 1, 2):
            record_count = remaining // record_size
            if record_count < MIN_RECORDS:
                continue
            # Avoid layouts that leave too much unexplained tail data.
            tail = remaining - record_count * record_size
            if tail > min(record_size, 32):
                continue

            for field in range(
                0,
                min(record_size, MAX_FIELD_SCAN),
                2,
            ):
                item = score_layout(
                    blob,
                    model_ids,
                    start=start,
                    record_size=record_size,
                    record_count=record_count,
                    field_offset=field,
                )
                if not item:
                    continue
                if item["match_ratio"] < 0.50:
                    continue
                item["layout_source"] = "fixed_stride_search"
                item["tail_bytes"] = tail
                candidates.append(item)

    candidates.sort(
        key=lambda x: (
            -x["score"],
            -x["match_ratio"],
            -x["unique_model_count"],
            x["record_size"],
            x["field_offset"],
        )
    )

    # Deduplicate equivalent layouts.
    seen = set()
    unique = []
    for item in candidates:
        key = (
            item["start"],
            item["record_size"],
            item["record_count"],
            item["field_offset"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    best = unique[0] if unique else None
    confidence = "none"
    if best:
        if (
            best["match_ratio"] >= 0.90
            and best["unique_model_count"] >= 2
        ):
            confidence = "high"
        elif best["match_ratio"] >= 0.70:
            confidence = "medium"
        else:
            confidence = "low"

    return {
        "best": best,
        "confidence": confidence,
        "candidates": unique[:32],
    }


def _model_summary(fp, index, rid: int) -> dict:
    blob = _read_resource(fp, index, rid)
    out = {
        "resource_id": rid,
        "size": len(blob),
        "signature": blob[:2].decode("ascii", "replace") if len(blob) >= 2 else "",
    }
    try:
        mdl = mdl_probe.parse_mdl_bytes(blob)
        out.update({
            "parsed": True,
            "num_vertices": mdl["num_vertices"],
            "num_matrices": mdl["num_matrices"],
            "num_materials": mdl["num_materials"],
            "num_variances": mdl["num_variances"],
            "bounds": mdl["bounds"],
            "empty_nodes": mdl["empty_nodes"],
            "node_vertex_counts": [
                n["vertex_count"] for n in mdl["nodes"]
            ],
        })
    except Exception as exc:
        out.update({
            "parsed": False,
            "error": str(exc),
        })
    return out


def inspect_ped_models(path: Path) -> dict:
    with path.open("rb") as fp:
        index = pak_inventory.read_index(fp)
        ids = _maintable_ids(fp, index)
        ped_rid = ids[8]
        if not (0 <= ped_rid < index["resource_count"]):
            raise ValueError("maintable slot 8 has no valid pedinfos resource")

        models = _model_ids(fp, index)
        ped_blob = _read_resource(fp, index, ped_rid)
        inference = infer_layout(ped_blob, models)

        linked_model_ids = []
        if inference["best"]:
            linked_model_ids = inference["best"]["unique_model_ids"]

        summaries = [
            _model_summary(fp, index, rid)
            for rid in linked_model_ids
        ]
        summaries.sort(
            key=lambda x: (
                -(x.get("num_matrices") or 0),
                -(x.get("num_vertices") or 0),
                x["resource_id"],
            )
        )

    return {
        "pak": str(path),
        "pedinfos_resource_id": ped_rid,
        "pedinfos_size": len(ped_blob),
        "model_resource_count": len(models),
        "layout_inference": inference,
        "linked_model_count": len(linked_model_ids),
        "linked_models_by_skeleton_complexity": summaries,
        "note": (
            "The pedinfos record layout is inferred from repeated references "
            "to resources proven to be MG models. Do not label a specific "
            "record as Huang/player until the real build is cross-validated."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pak", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        report = inspect_ped_models(args.pak)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = report["layout_inference"]["best"] is not None
    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
