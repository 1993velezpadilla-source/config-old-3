#!/usr/bin/env python3
"""Resolve a public MediaFire file page and download a PE executable.

Used only by CI probes; the downloaded third-party binary is never committed
or uploaded as an artifact by this repository.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import re
import urllib.request


def fetch(url: str, timeout: int = 120) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("page")
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()

    body, final_url = fetch(args.page)
    if body[:2] == b"MZ":
        payload = body
        resolved = final_url
    else:
        text = html.unescape(
            body.decode("utf-8", "replace")
        ).replace("\\/", "/")
        candidates = re.findall(
            r'https://download[^"\'<> ]+mediafire\.com/[^"\'<> ]+?\.exe',
            text,
            flags=re.I,
        )
        if not candidates:
            candidates = re.findall(
                r'https://download[^"\'<> ]+?\.exe',
                text,
                flags=re.I,
            )
        if not candidates:
            raise SystemExit("Could not resolve MediaFire direct EXE URL")
        payload, resolved = fetch(candidates[0])

    if payload[:2] != b"MZ":
        raise SystemExit(f"resolved payload is not PE/MZ: {resolved}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"resolved={resolved}")
    print(f"bytes={len(payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
