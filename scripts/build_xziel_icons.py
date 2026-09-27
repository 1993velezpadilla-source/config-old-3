#!/usr/bin/env python3
"""Fetch and rasterize the CC0 HUD icon set used by Xziel mobile.

Upstream: Nieobie/Game-Icon-Pack
License: CC0 1.0 Universal
Pinned revision: b1a5fec8b68c99e7b46484db707610ab2414ad4c
"""
from pathlib import Path
from urllib.request import Request, urlopen
import io
import re
import sys
import zipfile
import cairosvg

REV = "b1a5fec8b68c99e7b46484db707610ab2414ad4c"
BASE = f"https://raw.githubusercontent.com/Nieobie/Game-Icon-Pack/{REV}/svg/no-padding"
ICONS = {
    "fire": "6-buildings/target.svg",
    "ads": "6-buildings/target-02.svg",
    "reload": "8-ui/refresh.svg",
    "use": "6-buildings/open-the-door.svg",
    "jump": "8-ui/arrow-up.svg",
    "knife": "5-food/knife.svg",
    "grenade": "3-gear/bomb.svg",
    "pause": "9-media/pause.svg",
    "sprint": "3-gear/shoe.svg",
    "slide": "8-ui/arrow-down-02.svg",
    "pistol": "3-gear/pistol.svg",
    "weapon": "3-gear/bullet.svg",
    "weapon_wonder": "4-nature/lightning.svg",
    "weapon_launcher": "3-gear/missile.svg",
    "threat": "1-game/skull.svg",
}

def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "Xziel-build/0.18"})
    with urlopen(req, timeout=30) as response:
        return response.read()


def _render_svg(out: Path, name: str, body: str, size: int = 512) -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
    {body}
    </svg>'''
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(out / f"{name}.png"),
        output_width=size,
        output_height=size,
    )

def build_xziel_modern_surfaces(out: Path) -> None:
    # Original Xziel HUD surfaces. These are generated locally rather than
    # copied from another game's UI, so the mobile HUD can be modern without
    # inheriting proprietary art.
    idle = '''
      <circle cx="256" cy="256" r="220" fill="#05080B" fill-opacity=".38"/>
      <circle cx="256" cy="256" r="220" fill="none" stroke="#F2F6FA" stroke-opacity=".58" stroke-width="14"/>
      <circle cx="256" cy="256" r="190" fill="none" stroke="#F2F6FA" stroke-opacity=".10" stroke-width="4"/>
      <path d="M256 22v28M256 462v28M22 256h28M462 256h28" stroke="#F2F6FA" stroke-opacity=".78" stroke-width="10" stroke-linecap="round"/>
    '''
    pressed = '''
      <circle cx="256" cy="256" r="224" fill="#15130B" fill-opacity=".78"/>
      <circle cx="256" cy="256" r="220" fill="none" stroke="#F4C83D" stroke-opacity=".96" stroke-width="18"/>
      <circle cx="256" cy="256" r="184" fill="none" stroke="#F4C83D" stroke-opacity=".24" stroke-width="7"/>
      <path d="M256 18v34M256 460v34M18 256h34M460 256h34" stroke="#FFF7D7" stroke-width="11" stroke-linecap="round"/>
    '''
    editor = '''
      <circle cx="256" cy="256" r="220" fill="#071018" fill-opacity=".52"/>
      <circle cx="256" cy="256" r="220" fill="none" stroke="#EAF8FF" stroke-opacity=".82" stroke-width="14"/>
      <circle cx="256" cy="256" r="188" fill="none" stroke="#EAF8FF" stroke-opacity=".16" stroke-width="5"/>
      <path d="M256 18v34M256 460v34M18 256h34M460 256h34" stroke="#EAF8FF" stroke-opacity=".92" stroke-width="10" stroke-linecap="round"/>
    '''
    joy_ring = '''
      <circle cx="256" cy="256" r="220" fill="#020609" fill-opacity=".22"/>
      <circle cx="256" cy="256" r="216" fill="none" stroke="#F1F6FA" stroke-opacity=".28" stroke-width="12"/>
      <circle cx="256" cy="256" r="150" fill="none" stroke="#F1F6FA" stroke-opacity=".09" stroke-width="5"/>
      <path d="M256 20v50M256 442v50M20 256h50M442 256h50" stroke="#F1F6FA" stroke-opacity=".58" stroke-width="12" stroke-linecap="round"/>
      <path d="M222 72l34-36 34 36" fill="none" stroke="#F4C83D" stroke-opacity=".74" stroke-width="11" stroke-linejoin="round"/>
    '''
    joy_knob = '''
      <circle cx="256" cy="256" r="190" fill="#10161B" fill-opacity=".78"/>
      <circle cx="256" cy="256" r="188" fill="none" stroke="#F1F6FA" stroke-opacity=".62" stroke-width="16"/>
      <circle cx="256" cy="256" r="86" fill="#F1F6FA" fill-opacity=".13"/>
    '''
    joy_knob_active = '''
      <circle cx="256" cy="256" r="194" fill="#16150E" fill-opacity=".90"/>
      <circle cx="256" cy="256" r="190" fill="none" stroke="#F4C83D" stroke-opacity=".98" stroke-width="18"/>
      <circle cx="256" cy="256" r="88" fill="#FFF7D7" fill-opacity=".19"/>
    '''
    for name, body in {
        "touch_idle": idle,
        "touch_pressed": pressed,
        "touch_editor": editor,
        "joystick_ring": joy_ring,
        "joystick_knob": joy_knob,
        "joystick_knob_active": joy_knob_active,
    }.items():
        _render_svg(out, name, body)

    # Recognisable, original silhouette set matched to NZ:P's actual weapon
    # families. PaP variants map back to the same physical silhouette.
    silhouettes = {
      "weapon_colt": '''
        <path d="M95 205h242v62H215l-22 145h-72l28-145H95z"/>
        <path d="M326 211h96v25h-96z"/><rect x="145" y="176" width="94" height="30" rx="8"/>
      ''',
      "weapon_revolver": '''
        <rect x="95" y="214" width="230" height="54" rx="10"/><circle cx="235" cy="241" r="55"/>
        <path d="M181 264h72l-22 145h-68z"/><rect x="322" y="224" width="110" height="20"/>
      ''',
      "weapon_kar": '''
        <path d="M42 252l82-52h210l67 26 70 6v24l-137 8H126l-84 45z"/>
        <rect x="248" y="247" width="20" height="92"/><rect x="371" y="218" width="105" height="14"/>
      ''',
      "weapon_kar_scope": '''
        <path d="M34 260l90-52h214l62 28 76 5v24l-140 8H126l-92 44z"/>
        <rect x="244" y="255" width="20" height="88"/>
        <rect x="206" y="176" width="150" height="26" rx="12"/><circle cx="210" cy="189" r="24"/><circle cx="350" cy="189" r="24"/>
      ''',
      "weapon_thompson": '''
        <path d="M42 252l82-58h78v33h155v58H191l-68 44-81-17z"/>
        <rect x="354" y="241" width="116" height="19"/><rect x="200" y="282" width="28" height="106"/>
        <circle cx="278" cy="307" r="52"/>
      ''',
      "weapon_bar": '''
        <path d="M35 258l94-58h182l68 36h99v25h-164l-69 22H130l-95 46z"/>
        <path d="M247 278h43l-9 106h-46z"/><rect x="370" y="228" width="108" height="12"/>
      ''',
      "weapon_ballistic": '''
        <path d="M72 263l260-68 91 20-83 35-268 55z"/><path d="M321 203l90-90 29 17-55 101z"/>
      ''',
      "weapon_browning": '''
        <path d="M28 250l81-47h237l50 29h92v30h-142l-54 35H111l-83 35z"/>
        <rect x="225" y="286" width="44" height="115"/><rect x="351" y="221" width="137" height="13"/>
        <path d="M388 262l-36 120h12l48-120z"/>
      ''',
      "weapon_doublebarrel": '''
        <path d="M28 270l96-60h151v61H126l-98 45z"/>
        <rect x="270" y="217" width="210" height="17"/><rect x="270" y="246" width="210" height="17"/>
      ''',
      "weapon_sawnoff": '''
        <path d="M72 273l76-48h139v58H146l-74 35z"/>
        <rect x="280" y="232" width="128" height="15"/><rect x="280" y="256" width="128" height="15"/>
      ''',
      "weapon_fg42": '''
        <path d="M35 258l82-49h204l51 31h103v24H320l-58 31H120l-85 38z"/>
        <path d="M205 287h42l23 95h-45z"/><rect x="333" y="225" width="141" height="12"/>
      ''',
      "weapon_gewehr": '''
        <path d="M32 260l92-55h198l70 31h88v24l-153 12-62 28H125l-93 39z"/>
        <path d="M242 286h38l18 91h-42z"/>
      ''',
      "weapon_m1": '''
        <path d="M30 260l98-58h205l54 33h91v25l-146 10-69 27H126l-96 42z"/>
        <rect x="241" y="280" width="22" height="72"/>
      ''',
      "weapon_m1a1": '''
        <path d="M55 258l74-45h176l60 31h107v24H306l-58 28H130l-75 38z"/>
        <path d="M238 287h35l12 88h-40z"/>
      ''',
      "weapon_flamer": '''
        <path d="M52 255l68-40h192l55 30h111v25H302l-49 30H122l-70 33z"/>
        <rect x="194" y="289" width="34" height="100"/><circle cx="274" cy="337" r="41"/>
        <rect x="346" y="228" width="132" height="13"/>
      ''',
      "weapon_mp40": '''
        <path d="M63 250l67-38h180l50 31h108v28H306l-55 25H130l-67 32z"/>
        <path d="M222 289h34l4 114h-39z"/><path d="M93 250L38 190l9-8 72 54z" fill="none" stroke="#fff" stroke-width="13"/>
      ''',
      "weapon_mg42": '''
        <path d="M24 250l88-46h222l58 30h95v29H333l-61 34H113l-89 35z"/>
        <rect x="356" y="220" width="132" height="14"/>
        <path d="M384 266l-51 118h12l61-118zM420 266l53 118h-12l-63-118z"/>
      ''',
      "weapon_panzer": '''
        <rect x="52" y="222" width="384" height="86" rx="38"/><rect x="20" y="240" width="66" height="50" rx="18"/>
        <path d="M195 305h62l-8 93h-55z"/><rect x="427" y="238" width="65" height="54" rx="15"/>
      ''',
      "weapon_ppsh": '''
        <path d="M45 254l78-46h186l62 31h107v28H308l-58 28H125l-80 38z"/>
        <circle cx="278" cy="319" r="55"/><rect x="351" y="226" width="127" height="13"/>
      ''',
      "weapon_ptrs": '''
        <path d="M18 260l101-59h221l70 32h84v26l-154 12-78 29H120l-102 43z"/>
        <rect x="210" y="175" width="156" height="22" rx="10"/>
        <path d="M367 270l-48 115h12l58-115z"/>
      ''',
      "weapon_ray": '''
        <path d="M105 217h190l91 58-52 56H210l-18 103h-73l28-115-42-32z"/>
        <circle cx="292" cy="274" r="62"/><rect x="321" y="191" width="99" height="38" rx="18"/>
      ''',
      "weapon_raymk2": '''
        <path d="M56 245l78-47h224l76 45-43 58H227l-15 105h-63l18-105H82z"/>
        <circle cx="332" cy="253" r="42"/><rect x="355" y="198" width="115" height="23" rx="10"/>
      ''',
      "weapon_stg": '''
        <path d="M36 258l86-52h198l66 34h91v26H319l-61 30H123l-87 39z"/>
        <path d="M242 288h46l-11 105h-50z"/><rect x="365" y="228" width="112" height="12"/>
      ''',
      "weapon_trench": '''
        <path d="M32 263l92-55h197l57 32h101v26H320l-58 27H125l-93 41z"/>
        <rect x="323" y="225" width="157" height="14"/><rect x="309" y="273" width="93" height="18" rx="8"/>
      ''',
      "weapon_type100": '''
        <path d="M55 255l72-42h183l57 31h103v27H306l-55 25H128l-73 35z"/>
        <path d="M226 288h34l-8 105h-39z"/><rect x="347" y="228" width="124" height="12"/>
      ''',
      "weapon_mp5": '''
        <path d="M75 247l51-31h191l50 29h100v31H315l-53 26H128l-53 28z"/>
        <path d="M228 294h35l11 103h-39z"/><path d="M105 250L51 201" fill="none" stroke="#fff" stroke-width="12"/>
      ''',
      "weapon_tesla": '''
        <path d="M72 250l64-40h176l52 34h95v28H309l-54 30H134l-62 35z"/>
        <path d="M215 291h40l-4 101h-44z"/>
        <circle cx="345" cy="236" r="28" fill="none" stroke="#fff" stroke-width="12"/>
        <circle cx="402" cy="236" r="28" fill="none" stroke="#fff" stroke-width="12"/>
        <path d="M353 236h41" stroke="#fff" stroke-width="14"/>
      ''',
      "weapon_springfield": '''
        <path d="M28 260l97-56h204l62 31h88v25l-151 11-67 28H126l-98 40z"/>
        <rect x="242" y="281" width="21" height="70"/><rect x="365" y="226" width="114" height="12"/>
      ''',
    }
    for name, body in silhouettes.items():
        _render_svg(out, name, f'<g fill="#FFFFFF">{body}</g>', 512)


def build_xziel_v023_surfaces(out: Path) -> None:
    """Original Xziel mobile FPS surfaces inspired by modern touch shooters."""
    # A clean cartridge icon for the right-fire control.
    fire = '''
      <g transform="rotate(-36 256 256)" fill="#FFFFFF">
        <path d="M218 58h76v70l-12 20v214l-26 86-26-86V148l-12-20z"/>
        <rect x="210" y="58" width="92" height="36" rx="6"/>
        <path d="M230 362h52l-9 44-17 54-17-54z"/>
      </g>
    '''
    # Crisp optic reticle for dedicated ADS.
    ads = '''
      <g fill="none" stroke="#FFFFFF" stroke-linecap="round">
        <circle cx="256" cy="256" r="112" stroke-width="24"/>
        <path d="M256 74v80M256 358v80M74 256h80M358 256h80" stroke-width="22"/>
        <circle cx="256" cy="256" r="12" fill="#FFFFFF" stroke="none"/>
      </g>
    '''
    # ADS+fire is deliberately distinct: optic with a small cartridge mark.
    adsfire = '''
      <g fill="none" stroke="#FFFFFF" stroke-linecap="round">
        <circle cx="228" cy="228" r="108" stroke-width="22"/>
        <path d="M228 52v72M228 332v72M52 228h72M332 228h72" stroke-width="21"/>
        <circle cx="228" cy="228" r="11" fill="#FFFFFF" stroke="none"/>
      </g>
      <!-- Large cartridge sits clearly in front of the reticle. -->
      <g transform="rotate(-36 346 354)" fill="#FFFFFF">
        <path d="M320 250h54v52l-9 16v108l-18 50-18-50V318l-9-16z"/>
        <rect x="314" y="250" width="66" height="28" rx="4"/>
      </g>
    '''
    reload = '''
      <g fill="none" stroke="#FFFFFF" stroke-width="22" stroke-linecap="round" stroke-linejoin="round">
        <path d="M385 182a154 154 0 1 1-35-54"/>
        <path d="M351 83l46 97-104-18"/>
      </g>
      <g fill="#FFFFFF">
        <path d="M180 207h34v122h-34z"/><path d="M176 191h42v22h-42z"/>
        <path d="M239 184h34v145h-34z"/><path d="M235 168h42v22h-42z"/>
        <path d="M298 207h34v122h-34z"/><path d="M294 191h42v22h-42z"/>
      </g>
    '''
    small_idle = '''
      <circle cx="256" cy="256" r="218" fill="#05080B" fill-opacity=".44"/>
      <circle cx="256" cy="256" r="218" fill="none" stroke="#EEEB24" stroke-opacity=".88" stroke-width="13"/>
      <circle cx="256" cy="256" r="188" fill="none" stroke="#EAF0F4" stroke-opacity=".08" stroke-width="3"/>
    '''
    small_pressed = '''
      <circle cx="256" cy="256" r="220" fill="#090B0D" fill-opacity=".72"/>
      <circle cx="256" cy="256" r="218" fill="none" stroke="#F4C83D" stroke-opacity=".90" stroke-width="15"/>
      <circle cx="256" cy="256" r="184" fill="none" stroke="#F4C83D" stroke-opacity=".18" stroke-width="5"/>
    '''
    fire_idle = '''
      <circle cx="256" cy="256" r="226" fill="#050607" fill-opacity=".48"/>
      <circle cx="256" cy="256" r="222" fill="none" stroke="#EEEB24" stroke-opacity=".94" stroke-width="15"/>
      <circle cx="256" cy="256" r="188" fill="none" stroke="#F4F6F7" stroke-opacity=".10" stroke-width="4"/>
    '''
    fire_pressed = '''
      <circle cx="256" cy="256" r="228" fill="#0A0905" fill-opacity=".72"/>
      <circle cx="256" cy="256" r="223" fill="none" stroke="#F4C83D" stroke-width="19"/>
      <circle cx="256" cy="256" r="184" fill="none" stroke="#F4C83D" stroke-opacity=".24" stroke-width="7"/>
    '''
    ads_idle = '''
      <circle cx="256" cy="256" r="218" fill="#05080B" fill-opacity=".40"/>
      <circle cx="256" cy="256" r="216" fill="none" stroke="#EEEB24" stroke-opacity=".88" stroke-width="12"/>
      <path d="M256 25v46M256 441v46M25 256h46M441 256h46" stroke="#EEF3F6" stroke-opacity=".56" stroke-width="9" stroke-linecap="round"/>
    '''
    ads_pressed = '''
      <circle cx="256" cy="256" r="220" fill="#080A0C" fill-opacity=".70"/>
      <circle cx="256" cy="256" r="216" fill="none" stroke="#F4C83D" stroke-opacity=".92" stroke-width="15"/>
      <path d="M256 22v50M256 440v50M22 256h50M440 256h50" stroke="#FFF5C9" stroke-width="10" stroke-linecap="round"/>
    '''
    adsfire_idle = '''
      <circle cx="256" cy="256" r="226" fill="#050607" fill-opacity=".47"/>
      <circle cx="256" cy="256" r="222" fill="none" stroke="#EEEB24" stroke-opacity=".94" stroke-width="15"/>
      <circle cx="256" cy="256" r="184" fill="none" stroke="#F1F5F7" stroke-opacity=".08" stroke-width="4"/>
      <path d="M256 20v33M256 459v33M20 256h33M459 256h33" stroke="#F4C83D" stroke-opacity=".70" stroke-width="8" stroke-linecap="round"/>
    '''
    adsfire_pressed = '''
      <circle cx="256" cy="256" r="228" fill="#0B0A06" fill-opacity=".76"/>
      <circle cx="256" cy="256" r="223" fill="none" stroke="#F4C83D" stroke-width="19"/>
      <circle cx="256" cy="256" r="181" fill="none" stroke="#FFF2B0" stroke-opacity=".18" stroke-width="6"/>
    '''
    minimap_ring = '''
      <circle cx="256" cy="256" r="231" fill="#030507" fill-opacity=".58"/>
      <circle cx="256" cy="256" r="229" fill="none" stroke="#E7ECEF" stroke-opacity=".70" stroke-width="12"/>
      <circle cx="256" cy="256" r="190" fill="none" stroke="#E7ECEF" stroke-opacity=".11" stroke-width="4"/>
      <path d="M256 27v24M256 461v24M27 256h24M461 256h24" stroke="#E7ECEF" stroke-opacity=".70" stroke-width="8" stroke-linecap="round"/>
    '''
    minimap_player = '''
      <path d="M256 58l95 326-95-58-95 58z" fill="#F4C83D"/>
      <path d="M256 93l61 236-61-37-61 37z" fill="#FFF5C9" fill-opacity=".58"/>
    '''
    for name, body in {
        "fire": fire,
        "ads": ads,
        "adsfire": adsfire,
        "reload": reload,
        "touch_small_idle": small_idle,
        "touch_small_pressed": small_pressed,
        "touch_fire_idle": fire_idle,
        "touch_fire_pressed": fire_pressed,
        "touch_ads_idle": ads_idle,
        "touch_ads_pressed": ads_pressed,
        "touch_adsfire_idle": adsfire_idle,
        "touch_adsfire_pressed": adsfire_pressed,
        "minimap_ring": minimap_ring,
        "minimap_player": minimap_player,
    }.items():
        _render_svg(out, name, body, 512)

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_xziel_icons.py <output-dir>")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    build_xziel_modern_surfaces(out)
    for name, rel in ICONS.items():
        svg = fetch(f"{BASE}/{rel}").replace(b"currentColor", b"#FFFFFF")
        cairosvg.svg2png(
            bytestring=svg,
            write_to=str(out / f"{name}.png"),
            output_width=256,
            output_height=256,
        )
    build_xziel_v023_surfaces(out)

    # Weapon cards use actual CC0 gun artwork rather than a hand-drawn glyph.
    # Kay Lousberg's pack is CC0, transparent PNG, and explicitly includes
    # pistol/revolver/shotgun/sniper/SMG/assault-rifle artwork.
    # OpenGameArt canonical page:
    # https://opengameart.org/content/2d-guns
    try:
        weapon_zip = fetch("https://opengameart.org/sites/default/files/guns_gameassets.zip")
        with zipfile.ZipFile(io.BytesIO(weapon_zip)) as archive:
            names = [
                n for n in archive.namelist()
                if n.lower().endswith(".png")
                and "__macosx" not in n.lower()
                and "spritesheet" not in n.lower()
            ]

            def pick(keyword: str) -> str | None:
                choices = []
                for name in names:
                    base = Path(name).stem.lower()
                    if keyword not in base:
                        continue
                    if any(bad in base for bad in ("magazine", "bullet", "ammo", "box")):
                        continue
                    score = 0
                    if "@2x" in base or "2x" in base:
                        score += 5
                    if "separate" in name.lower() or "individual" in name.lower():
                        score += 3
                    if "alternate" not in name.lower() and "alt" not in base:
                        score += 1
                    choices.append((score, len(name), name))
                if not choices:
                    return None
                choices.sort(key=lambda x: (-x[0], x[1], x[2]))
                return choices[0][2]

            categories = {
                "weapon_pistol.png": "pistol",
                "weapon_revolver.png": "revolver",
                "weapon_shotgun.png": "shotgun",
                "weapon_sniper.png": "sniper",
                "weapon_smg.png": "smg",
                "weapon_assault.png": "assault",
            }
            picked = {}
            for filename, keyword in categories.items():
                selected = pick(keyword)
                if selected:
                    payload = archive.read(selected)
                    (out / filename).write_bytes(payload)
                    picked[keyword] = filename

            # Preserve legacy names used by older checkpoints.
            if "pistol" in picked:
                (out / "pistol.png").write_bytes((out / picked["pistol"]).read_bytes())
            if "assault" in picked:
                (out / "weapon.png").write_bytes((out / picked["assault"]).read_bytes())
    except Exception as exc:
        # The Nieobie CC0 pistol/bullet icons remain a deterministic fallback
        # if OpenGameArt is temporarily unavailable during CI.
        print(f"warning: Kay Lousberg weapon art unavailable: {exc}", file=sys.stderr)

    # CI must always produce every HUD path even when OpenGameArt is down or
    # the upstream archive changes a filename. The fallback images are also
    # CC0 from the already-pinned Nieobie pack.
    fallback_map = {
        "weapon_pistol.png": "pistol.png",
        "weapon_revolver.png": "pistol.png",
        "weapon_shotgun.png": "weapon.png",
        "weapon_sniper.png": "weapon.png",
        "weapon_smg.png": "weapon.png",
        "weapon_assault.png": "weapon.png",
    }
    for dst, src in fallback_map.items():
        target = out / dst
        if not target.exists():
            target.write_bytes((out / src).read_bytes())

    (out / "LICENSE-CC0.txt").write_text(
        "Xziel mobile HUD assets are CC0/public-domain.\n"
        "Touch/action icons: Nieobie/Game-Icon-Pack, CC0 1.0 Universal.\n"
        f"Source revision: {REV}\nhttps://github.com/Nieobie/Game-Icon-Pack\n"
        "Weapon card art: Kay Lousberg, 2D Guns, CC0.\n"
        "https://opengameart.org/content/2d-guns\n",
        encoding="utf-8",
    )

if __name__ == "__main__":
    main()
