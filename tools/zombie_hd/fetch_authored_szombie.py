#!/usr/bin/env python3
"""Fetch the *free* author ZIP from itch, without paying or publishing it.

Used only as a transient CI input. Prints safe metadata, never a
short-lived itch download token. It does not upload standalone assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from playwright.sync_api import sync_playwright

PURCHASE = "https://hotstrikestudio.itch.io/free-stylized-dark-fantasy-zombie/purchase"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-to", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    args.save_to.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, locale="en-US")
        page = context.new_page()
        page.goto(PURCHASE, wait_until="domcontentloaded", timeout=60000)
        skip = page.get_by_text("No thanks, just take me to the downloads", exact=False)
        if skip.count() < 1:
            raise RuntimeError("Public zero-payment downloads button not found; requires manual source upload")
        skip.first.click(timeout=20000)
        page.wait_for_load_state("domcontentloaded", timeout=60000)
        # On the download page, the file label and its download button
        # are generally siblings within a .upload row, not the same link.
        entry = page.locator(".upload:has-text('SZombie.zip')")
        if entry.count():
            button = entry.first.locator("a[href], button").filter(has_text="Download")
        else:
            button = page.get_by_role("link", name="Download", exact=False)
        if button.count() < 1:
            raise RuntimeError("SZombie.zip download button unavailable; do not fallback to stock assets")
        with page.expect_download(timeout=120000) as event:
            button.first.click()
        download = event.value
        if not download.suggested_filename.lower().endswith(".zip"):
            raise RuntimeError("Author download is not a ZIP: " + download.suggested_filename)
        download.save_as(str(args.save_to))
        browser.close()
    with ZipFile(args.save_to) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError("Corrupt author ZIP")
        paths = [v.filename for v in archive.infolist() if not v.is_dir()]
        meshes = [v for v in paths if v.lower().endswith((".fbx", ".blend"))]
        textures = [v for v in paths if v.lower().endswith((".png", ".jpg", ".jpeg", ".tga"))]
        if not meshes or not textures:
            raise RuntimeError("Missing FBX/Blend or PBR textures: not the author ZIP")
    report = {
        "source": "Hotstrike Studio / itch.io / free-stylized-dark-fantasy-zombie",
        "file": "SZombie.zip",
        "sha256": hashlib.sha256(args.save_to.read_bytes()).hexdigest(),
        "size_bytes": args.save_to.stat().st_size,
        "meshes": meshes,
        "texture_count": len(textures),
        "status": "REAL_SOURCE_ARCHIVE_ACQUIRED_NOT_CONVERTED_OR_ANDROID_TESTED"
    }
    args.manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
