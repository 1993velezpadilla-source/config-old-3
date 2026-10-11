#!/usr/bin/env python3
"""Local, deterministic single-map packager contract tests (stdlib only)."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

pruner = Path(__file__).with_name("prune_nzp_single_map.py")

def fixture(base):
    root = base / "nzp"
    (root / "maps").mkdir(parents=True)
    (root / "models/weapons/mp40").mkdir(parents=True)
    (root / "sounds/weapons/mp40").mkdir(parents=True)
    for relative in ("maps/ndu.bsp", "maps/ndu.nsz", "maps/warehouse.bsp",
                     "maps/warehouse.nsz", "maps/warehouse.txt",
                     "models/weapons/mp40/v_mp40.mdl",
                     "models/weapons/mp40/g_mp40.mdl",
                     "sounds/weapons/mp40/magout.wav"):
        (root / relative).write_bytes(relative.encode())
    return root

with TemporaryDirectory() as td:
    root = fixture(Path(td))
    result = subprocess.run([sys.executable, str(pruner), str(root), "ndu"],
                            capture_output=True, text=True, check=True)
    assert "BSPs_remaining=1" in result.stdout
    assert (root / "maps/ndu.bsp").is_file()
    assert (root / "maps/ndu.nsz").is_file()
    assert not (root / "maps/warehouse.bsp").exists()
    assert not (root / "maps/warehouse.nsz").exists()
    assert not (root / "maps/warehouse.txt").exists()
    assert (root / "models/weapons/mp40/v_mp40.mdl").is_file()
    assert (root / "models/weapons/mp40/g_mp40.mdl").is_file()
    assert (root / "sounds/weapons/mp40/magout.wav").is_file()

with TemporaryDirectory() as td:
    root = fixture(Path(td))
    missing = subprocess.run([sys.executable, str(pruner), str(root), "no_such_map"],
                             capture_output=True, text=True)
    assert missing.returncode != 0
    assert (root / "maps/warehouse.bsp").exists(), "Failure should never prune maps"

with TemporaryDirectory() as td:
    root = fixture(Path(td))
    (root / "models/weapons/mp40/v_mp40.mdl").unlink()
    missing = subprocess.run([sys.executable, str(pruner), str(root), "ndu"],
                             capture_output=True, text=True)
    assert missing.returncode != 0, "Missing MP40 must be a failing build"
print("PASS: exactly one BSP, kept source MP40, preserved shared audio, failed safely on no map")
