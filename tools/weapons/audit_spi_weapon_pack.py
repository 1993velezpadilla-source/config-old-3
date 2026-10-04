#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin

import requests

START_URL = "https://www.moddb.com/downloads/start/252606"
# ModDB returns 403 to some datacenter IPs on the landing page. This mirror
# route was resolved from that same public page and issues its own current CDN
# redirect. START_URL stays as discovery/fallback.
MIRROR_SEED_URL = "https://www.moddb.com/downloads/mirror/252606/135/713b4e02777c96e9a66c2ecea44fba18"
EXPECTED_NAME = "COD2_SPis_Weapon_Overhaul_Mod_V1.1.zip"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"

WEAPON_TERMS = (
    "thompson", "mp40", "m1garand", "m1_garand", "m1a1", "bar",
    "springfield", "g43", "gewehr", "ppsh", "mp44", "stg",
    "colt", "mg42", "weapon", "viewmodel", "xmodel", "xanim",
)
AUDIO_TERMS = ("sound", "audio", "fire", "reload", "bolt", "clip", "foley")


def digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_zip(out: Path) -> tuple[Path, str, str]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Referer": "https://www.moddb.com/",
        }
    )

    mirrors = [MIRROR_SEED_URL]
    discovery_error = None
    try:
        start = session.get(START_URL, timeout=45)
        if start.ok:
            candidates = re.findall(
                r'href=["\\\']([^"\\\']*/downloads/mirror/252606/[^"\\\']+)["\\\']',
                start.text,
                flags=re.I,
            )
            for candidate in candidates:
                discovered = urljoin(START_URL, candidate)
                if discovered not in mirrors:
                    mirrors.insert(0, discovered)
        else:
            discovery_error = f"start HTTP {start.status_code}"
    except Exception as exc:
        discovery_error = repr(exc)

    errors = []
    for mirror in mirrors:
        try:
            payload = session.get(
                mirror,
                headers={"Referer": START_URL, "User-Agent": USER_AGENT},
                timeout=180,
                stream=True,
                allow_redirects=True,
            )
            payload.raise_for_status()
            content_type = payload.headers.get("content-type", "").lower()
            dst = out / EXPECTED_NAME
            with dst.open("wb") as handle:
                for chunk in payload.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)

            if dst.stat().st_size < 50_000_000 or "text/html" in content_type:
                errors.append(
                    f"{mirror}: suspicious bytes={dst.stat().st_size} type={content_type}"
                )
                dst.unlink(missing_ok=True)
                continue
            return dst, mirror, payload.url
        except Exception as exc:
            errors.append(f"{mirror}: {exc!r}")

    raise RuntimeError(
        "No ModDB mirror succeeded; discovery="
        + str(discovery_error)
        + "; "
        + " | ".join(errors)
    )


def archive_inventory(zip_path: Path, out: Path) -> dict:
    listing = subprocess.run(
        ["7z", "l", "-slt", str(zip_path)],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    (out / "archive-list.txt").write_text(listing, encoding="utf-8")

    paths: list[str] = []
    sizes: dict[str, int] = {}
    current = ""
    for line in listing.splitlines():
        if line.startswith("Path = "):
            current = line[7:].strip().replace("\\", "/")
            paths.append(current)
        elif current and line.startswith("Size = "):
            try:
                sizes[current] = int(line[7:].strip())
            except ValueError:
                pass

    ext = Counter((PurePosixPath(p).suffix.lower() or "<none>") for p in paths)
    weapon_hits = [
        p for p in paths
        if any(term in p.lower() for term in WEAPON_TERMS)
    ]
    audio_hits = [
        p for p in paths
        if any(term in p.lower() for term in AUDIO_TERMS)
    ]
    return {
        "entries": len(paths),
        "extensions": dict(ext.most_common()),
        "weapon_hits": weapon_hits,
        "audio_hits": audio_hits,
        "largest": sorted(
            ({"path": p, "bytes": sizes.get(p, 0)} for p in paths),
            key=lambda x: -x["bytes"],
        )[:200],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    payload, mirror, final_url = fetch_zip(out)
    inv = archive_inventory(payload, out)
    report = {
        "schema": 1,
        "source": {
            "name": "SPi's Weapon Overhaul Mod V1.1",
            "type": "community_modified_weapon_pack",
            "page": "https://www.moddb.com/mods/spis-weapon-overhaul-mod/downloads/spis-weapon-overhaul-mod-v11",
            "start_url": START_URL,
            "mirror_url": mirror,
            "final_host": final_url.split("/", 3)[:3],
            "final_weapon_candidate": True,
            "notes": [
                "Community mod modifies models, textures and animations.",
                "Audit does not mark any Xogot weapon READY until model, animation and audio roles are verified.",
            ],
        },
        "download": {
            "filename": payload.name,
            "bytes": payload.stat().st_size,
            "md5": digest(payload, "md5"),
            "sha256": digest(payload, "sha256"),
        },
        "archive": {
            "entries": inv["entries"],
            "extensions": inv["extensions"],
        },
        "weapon_hits": inv["weapon_hits"],
        "audio_hits": inv["audio_hits"],
        "largest": inv["largest"],
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2)[:60000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
