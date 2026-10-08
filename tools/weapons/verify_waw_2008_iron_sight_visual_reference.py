#!/usr/bin/env python3
"""Static provenance guard for original 2008 CoD WaW sight/scope comparisons.

Success here means the right ORIGINAL screen references are indexed; it must
never be relabeled a visual-match or true gun-geometry GREEN.
"""
from __future__ import annotations

import json
from pathlib import Path

SRC = Path("xogot/data/waw_2008_iron_sight_visual_reference.json")
FIREARMS = {
    "colt","walther","nambu","tt33","357","mp40","thompson",
    "ppsh","type100","stg","m1","m1a1","gewehr","svt40",
    "arisaka","kar98k","springfield","mosin","ptrs","trench",
    "doublebarrel","sawnoff","bar","fg42","mg42","browning",
    "dp28","type99",
}
EXPECTED_IMAGE = {
    "colt":5,"walther":28,"nambu":12,"tt33":22,"357":17,
    "mp40":None,"thompson":51,"ppsh":41,"type100":59,"stg":167,
    "m1":127,"m1a1":120,"gewehr":102,"svt40":175,"arisaka":83,
    "kar98k":110,"springfield":157,"mosin":138,"ptrs":152,"trench":77,
    "doublebarrel":64,"sawnoff":72,"bar":184,"fg42":93,
    "mg42":214,"browning":192,"dp28":204,"type99":221,
}
SCOPED_ALTERNATES = {"arisaka":88,"kar98k":116,"springfield":163,"mosin":147}


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    assert data["schema"] == 1, "Unexpected original sight reference schema"
    assert data["weapon_count"] == len(FIREARMS) == 28
    records = data["weapons"]
    assert set(records) == FIREARMS
    assert "2008" in data["authority"]
    assert "Final Fronts" in data["authority"], "Explicitly exclude alternate game engines"
    for wid, record in records.items():
        assert record["original_2008_imfdb_ads_image_number"] == EXPECTED_IMAGE[wid], wid
        assert record["original_2008_imfdb_hip_image_number"] is not None, wid
        assert record["source_url"].startswith("https://www.imfdb.org/wiki/Call_of_Duty"), wid
        assert record["qa_state"] == "external_reference_identified_not_pixel_matched", wid
        assert len(record["source_section"]) > 4, wid
    for wid, num in SCOPED_ALTERNATES.items():
        assert records[wid]["alternate_ads_image_number"] == num, wid
    assert records["ptrs"]["aim_view"] == "sniper_scope_not_iron_sight"
    assert records["trench"]["aim_view"] == "front_bead_only"
    assert records["sawnoff"]["aim_view"] == "shotgun_bead"
    assert "counterclockwise" in records["type100"]["visual_truth"].lower()
    assert "offset" in records["nambu"]["visual_truth"].lower()
    assert "magwell" in records["mp40"]["visual_truth"].lower()
    assert "28" in str(data["weapon_count"])
    print("XZOGOT_ORIGINAL_WAW_2008_28_ADS_REFERENCE_INDEX_GREEN indexed=28")
    print("XZOGOT_ORIGINAL_WAW_2008_VISUAL_MATCH_UNVERIFIED 28")


if __name__ == "__main__":
    main()
