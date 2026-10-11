#!/usr/bin/env python3
"""Regenerate the distinctive dark/smoky/yellow-rim mobile control skins.

This only runs in the isolated native single-map prototype and leaves the
existing gameplay input maps and user's HUD editor/preferences functional.
"""
from pathlib import Path
import sys
import cairosvg

if len(sys.argv) != 2:
    raise SystemExit("usage: skin_vril_touch_controls.py <nzp/gfx/xziel>")
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

def image(name, shapes):
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"
    viewBox="0 0 512 512"><defs>
    <radialGradient id="glass" cx=".35" cy=".25">
      <stop offset="0" stop-color="#4C5159" stop-opacity=".64"/>
      <stop offset=".65" stop-color="#23272D" stop-opacity=".52"/>
      <stop offset="1" stop-color="#050609" stop-opacity=".72"/>
    </radialGradient>
    <linearGradient id="yellow" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#FFF1A7"/><stop offset=".45" stop-color="#EFC829"/>
      <stop offset="1" stop-color="#A77B08"/>
    </linearGradient></defs>""" + shapes + "</svg>"
    cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                    write_to=str(out / (name + ".png")),
                    output_width=512, output_height=512)

# Dark circular buttons with a distinct golden radial rim, smoky transparent
# centre and no retro cross-hair ticks or scanline effects.
image("touch_idle", """
  <circle cx="256" cy="256" r="222" fill="url(#glass)" />
  <circle cx="256" cy="256" r="218" fill="none" stroke="url(#yellow)" stroke-width="15" stroke-opacity=".83"/>
  <circle cx="256" cy="256" r="192" fill="#070809" fill-opacity=".32"/>
  <circle cx="256" cy="256" r="192" fill="none" stroke="#F6E9A5" stroke-width="4" stroke-opacity=".18"/>
""")
image("touch_pressed", """
  <circle cx="256" cy="256" r="222" fill="#170A0A" fill-opacity=".68"/>
  <circle cx="256" cy="256" r="218" fill="none" stroke="#EF4D3F" stroke-width="19" stroke-opacity=".96"/>
  <circle cx="256" cy="256" r="188" fill="#E02D23" fill-opacity=".19"/>
  <circle cx="256" cy="256" r="187" fill="none" stroke="#FFF1CC" stroke-width="6" stroke-opacity=".38"/>
""")
image("touch_editor", """
  <circle cx="256" cy="256" r="222" fill="#09141B" fill-opacity=".58"/>
  <circle cx="256" cy="256" r="216" fill="none" stroke="#FBE16B" stroke-width="20"/>
  <circle cx="256" cy="256" r="181" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-opacity=".3"/>
""")
image("joystick_ring", """
  <circle cx="256" cy="256" r="220" fill="#080A0D" fill-opacity=".23"/>
  <circle cx="256" cy="256" r="217" fill="none" stroke="#E9BF22" stroke-width="14" stroke-opacity=".70"/>
  <circle cx="256" cy="256" r="177" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-opacity=".11"/>
""")
image("joystick_knob", """
  <circle cx="256" cy="256" r="192" fill="#0F141A" fill-opacity=".66"/>
  <circle cx="256" cy="256" r="186" fill="none" stroke="#D4D7DB" stroke-width="15" stroke-opacity=".55"/>
  <circle cx="256" cy="256" r="102" fill="#D6D9DC" fill-opacity=".11"/>
""")
image("joystick_knob_active", """
  <circle cx="256" cy="256" r="192" fill="#12130D" fill-opacity=".80"/>
  <circle cx="256" cy="256" r="186" fill="none" stroke="#F2CB3A" stroke-width="17" stroke-opacity=".9"/>
  <circle cx="256" cy="256" r="102" fill="#FADE7F" fill-opacity=".14"/>
""")
(out / "skin_native_dev.txt").write_text("XZIEL_NATIVE_TOUCH_YELLOW_SMOKE_V1\n", encoding="utf-8")
print("Native single-map control skins: gold rim, dark smoky transparent fill, red pressed state.")
