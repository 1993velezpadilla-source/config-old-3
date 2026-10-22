#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "build_launch_profile.py"
spec = importlib.util.spec_from_file_location("build_launch_profile", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def fixture(map_present: bool = True) -> dict:
    return {
        "schema": 1,
        "runtime": "IW4",
        "gameRoot": "/storage/emulated/0/Games/MW2",
        "executable": {
            "name": "iw4mp.exe",
            "machineName": "x86",
            "peKind": "PE32",
        },
        "iw4xPresent": True,
        "churchMapName": "xziel_sanctum",
        "churchMapPresent": map_present,
    }


def main() -> int:
    winlator = module.build_profile(fixture(), "winlator", True)
    assert winlator["backend"] == "winlator"
    assert winlator["graphics"]["guestApi"] == "Direct3D9"
    assert winlator["graphics"]["translation"] == "DXVK"
    assert winlator["graphics"]["hostApi"] == "Vulkan"
    assert winlator["game"]["arguments"][-2:] == ["+map", "xziel_sanctum"]
    assert winlator["acceptance"]["requireMapLoad"] is True
    assert winlator["redistributeGamePayload"] is False

    hangover = module.build_profile(fixture(), "hangover", False)
    assert hangover["backend"] == "hangover"
    assert hangover["game"]["map"] is None
    assert "+map" not in hangover["game"]["arguments"]

    redacted = module.redact_profile(winlator)
    encoded = json.dumps(redacted)
    assert "/storage/emulated/0/Games/MW2" not in encoded
    assert "<OWNED_MW2_ROOT>" in encoded

    try:
        module.build_profile(fixture(False), "winlator", True)
    except ValueError as exc:
        assert "usermap" in str(exc)
    else:
        raise AssertionError("direct-map must fail when usermap is absent")

    bad = fixture()
    bad["executable"]["machineName"] = "x86_64"
    try:
        module.build_profile(bad, "winlator", False)
    except ValueError as exc:
        assert "PE32/x86" in str(exc)
    else:
        raise AssertionError("unexpected architecture must fail")

    print("IW4 Android launch profile gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
