#!/usr/bin/env python3
"""Iglesia ORIGINAL illustrated MP40 + pale bare Nun hands, entirely 2D.

A reproducible SVG ink illustration composed directly as paths, not a
recolored soldier sheet, copied game artwork, 3D gun model or skinned gloves.
This first pass is ART CANDIDATE, never owner-approved release art. CairoSVG
rasterizes transparent 768x512 RGBA PNGs. 24 source poses; runtime picks
12/15/24 frames, preserving full reload arc in each budget.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from PIL import Image
import cairosvg

WIDTH, HEIGHT = 768, 512
COUNTS = {"idle":1,"ads_idle":1,"fire":4,"ads_fire":3,
          "reload":12,"sprint":1,"equip":2}

DEFS = """
<defs>
  <linearGradient id="gun" x1="0" y1="0" x2="1" y2=".8">
    <stop offset="0" stop-color="#a4a3a0"/><stop offset=".12" stop-color="#52545a"/>
    <stop offset=".44" stop-color="#292c36"/><stop offset=".78" stop-color="#4d545d"/>
    <stop offset="1" stop-color="#161922"/>
  </linearGradient>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#e9d9b3"/><stop offset=".28" stop-color="#c1a58c"/>
    <stop offset=".60" stop-color="#80645d"/><stop offset="1" stop-color="#41363d"/>
  </linearGradient>
  <linearGradient id="skin" x1=".1" y1=".1" x2=".9" y2=".8">
    <stop offset="0" stop-color="#f8ead5"/><stop offset=".45" stop-color="#d6b2ac"/>
    <stop offset=".75" stop-color="#b58284"/><stop offset="1" stop-color="#5d3c55"/>
  </linearGradient>
  <linearGradient id="cloth" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#444052"/><stop offset=".22" stop-color="#272530"/>
    <stop offset=".6" stop-color="#14151e"/><stop offset="1" stop-color="#0c0d14"/>
  </linearGradient>
  <pattern id="hatch" width="11" height="11" patternUnits="userSpaceOnUse">
    <path d="M1 11L11 1" stroke="#080a11" stroke-width="2" opacity=".6"/>
  </pattern>
</defs>
"""

# Gun drawn at rest with angled WWII MP40 barrel, receiver and under-fold stock.
# Original ink outlines, 2D faceted metal shades, magazine and fore-sight.
GUN = """
<g stroke="#10121b" stroke-linejoin="round" stroke-linecap="round">
  <!-- front cylindrical barrel and cooling nut -->
  <path d="M374 65L396 66L414 188L373 203L365 185Z" fill="url(#gun)" stroke-width="7"/>
  <path d="M376 80L388 78L402 184L385 193Z" fill="#9a9fa1" opacity=".43"/>
  <path d="M392 86L407 184" fill="none" stroke="#10141b" stroke-width="4"/>
  <path d="M360 52Q373 44 388 49L394 71L374 73Z" fill="#373840" stroke-width="6"/>
  <path d="M362 56L378 52L379 68" fill="none" stroke="#c1b7a8" stroke-width="3"/>
  <path d="M366 45L368 23L377 20L383 46" fill="none" stroke="#131723" stroke-width="7"/>
  <path d="M369 27L378 27" stroke="#ded3b9" stroke-width="2"/>
  <!-- perforated collar -->
  <path d="M362 180L414 170L419 200L370 222Z" fill="#343840" stroke-width="7"/>
  <path d="M371 186L407 179M377 201L412 194" stroke="#aaa399" stroke-width="3" opacity=".55"/>
  <!-- angled top receiver -->
  <path d="M360 210L421 188L493 290L479 359L393 328Z" fill="url(#gun)" stroke-width="9"/>
  <path d="M369 214L423 200L474 288L456 320L407 305Z" fill="#535860" stroke-width="4"/>
  <path d="M383 214L414 209L447 269L413 276Z" fill="#11151d" opacity=".72"/>
  <path d="M392 218L426 267M406 218L437 269" stroke="#b6b7af" stroke-width="2" opacity=".4"/>
  <path d="M447 275L481 296L471 342L441 329Z" fill="#1c202a" stroke-width="6"/>
  <circle cx="460" cy="303" r="8" fill="#b2aba0" stroke-width="4"/>
  <path d="M451 336L480 347L478 362L447 354Z" fill="#c0aa8b" stroke-width="4"/>
  <!-- ribbed underside and lower receiver -->
  <path d="M394 320L466 337L480 365L431 407L388 359Z" fill="#353944" stroke-width="8"/>
  <path d="M396 327L444 344L455 383M408 336L444 392M419 341L437 401" stroke="#7b8084" stroke-width="4" opacity=".65"/>
  <!-- trigger guard and finger opening -->
  <path d="M472 348Q533 356 538 395L509 409Q500 381 469 381Z" fill="#1b1d28" stroke-width="7"/>
  <path d="M477 365Q507 373 516 395" fill="none" stroke="#a6a09a" stroke-width="3"/>
  <!-- pistol grip -->
  <path d="M489 379L524 398L548 491L515 502L467 417Z" fill="#29252b" stroke-width="8"/>
  <path d="M496 390L513 408L535 483L519 483Z" fill="url(#hatch)" opacity=".8"/>
  <path d="M505 420L523 465" stroke="#97928a" stroke-width="3" opacity=".6"/>
  <!-- fold stock -->
  <path d="M478 399L580 443L628 484L610 499L566 471L500 444" fill="none" stroke="#1e242e" stroke-width="11"/>
  <path d="M483 401L577 445L624 489" fill="none" stroke="#b3aca0" stroke-width="3"/>
  <!-- bolt handle and receiver bolts -->
  <path d="M444 269L461 258L479 268L466 278Z" fill="#c2ada0" stroke-width="5"/>
  <path d="M459 264L470 254" stroke="#f3ddbb" stroke-width="4"/>
  <circle cx="433" cy="318" r="4" fill="#e6c9a6"/>
  <circle cx="451" cy="331" r="4" fill="#e6c9a6"/>
</g>"""

MAG = """
<g stroke="#11141d" stroke-width="7" stroke-linejoin="round">
 <path d="M386 308L421 318L386 494L344 484Z" fill="url(#gun)"/>
 <path d="M385 320L411 327L375 480L352 474Z" fill="#292e3b" stroke-width="2"/>
 <path d="M369 350L400 356M363 378L392 385M357 408L387 415M350 439L379 447" fill="none" stroke="#9f9994" stroke-width="3" opacity=".62"/>
 <path d="M342 486L386 497L387 509L343 503Z" fill="#22252d" stroke-width="5"/>
</g>"""

# Curved hands are original drawn SVG anatomy, not recolored military gloves.
# 5 explicit fingers via Bézier silhouettes; stained glass palette skin/ink.
LEFT_HAND = """
<g stroke="#342934" stroke-linejoin="round" stroke-linecap="round">
  <path d="M110 552L165 429Q210 390 244 377L293 379L293 431Q254 460 239 525L207 562Z"
        fill="url(#cloth)" stroke-width="11"/>
  <path d="M132 525L171 448L226 410L271 405M159 545L190 475L238 442"
        fill="none" stroke="#77707b" stroke-width="5" opacity=".5"/>
  <path d="M237 391L267 373L274 395L251 418" fill="none" stroke="#8b6d71" stroke-width="5"/>
  <path d="M238 387L279 356Q303 338 318 338L344 351L345 382L322 419L289 434L260 427Z"
        fill="url(#skin)" stroke-width="8"/>
  <!-- articulated pale thumb -->
  <path d="M287 380Q294 361 321 356Q335 355 338 372Q337 384 322 385L304 398Z"
        fill="#efd8c6" stroke-width="5"/>
  <path d="M291 384L324 378" stroke="#81545f" stroke-width="2" fill="none"/>
  <!-- curled fingers around left magazine hand -->
  <path d="M308 352Q320 333 335 343L352 356Q361 369 350 379L339 379L320 366Z"
        fill="url(#skin)" stroke-width="5"/>
  <path d="M317 367Q333 348 345 365L353 380Q350 396 336 396L319 389Z"
        fill="url(#skin)" stroke-width="4"/>
  <path d="M314 392Q330 377 344 392L350 407Q345 421 334 420L313 411Z"
        fill="url(#skin)" stroke-width="4"/>
  <path d="M311 415Q329 403 339 421L335 434Q323 445 313 433Z"
        fill="#ba8990" stroke-width="4"/>
  <path d="M302 349L315 351M314 390L329 395M313 415L329 423" stroke="#f8e4d3" stroke-width="2.5"/>
  <!-- torn sleeve hem -->
  <path d="M231 414L247 397L261 419L280 414L273 432L254 428L247 446L230 427Z"
        fill="#1a1922" stroke="#554957" stroke-width="5"/>
  <path d="M237 425L253 430M242 419L254 423" stroke="#ad8a8c" stroke-width="2"/>
</g>"""

RIGHT_HAND = """
<g stroke="#322634" stroke-linejoin="round" stroke-linecap="round">
  <!-- right sleeve black habit with torn cuff -->
  <path d="M721 565L663 439L601 408L566 420L579 465L635 546L656 578Z"
        fill="url(#cloth)" stroke-width="11"/>
  <path d="M706 536L652 450L608 433M676 552L640 479L607 457"
        fill="none" stroke="#6d6575" stroke-width="5" opacity=".52"/>
  <path d="M574 431L571 401L553 391L542 410L548 444L568 455Z"
        fill="#1d1a26" stroke="#73616f" stroke-width="5"/>
  <!-- palm wraps curved stock/grip -->
  <path d="M569 433L539 410L513 404L503 422L518 447L544 472L581 472L591 455Z"
        fill="url(#skin)" stroke-width="7"/>
  <!-- articulated exposed index around trigger, rounded tip -->
  <path d="M521 411Q507 389 496 378Q483 372 473 380Q468 391 480 397L497 414L510 431Z"
        fill="#eed1c3" stroke-width="5"/>
  <path d="M482 391L498 396M515 420L532 434" stroke="#8f626a" stroke-width="2"/>
  <!-- gripping fingers along handle -->
  <path d="M530 431L510 445Q503 458 512 465L529 470L547 451Z" fill="url(#skin)" stroke-width="4"/>
  <path d="M539 445L525 459Q517 470 526 478L546 482L561 461Z" fill="url(#skin)" stroke-width="4"/>
  <path d="M555 454L544 470Q539 484 549 492L572 483L577 469Z" fill="#b9858c" stroke-width="4"/>
  <path d="M518 452L532 458M532 469L548 473M550 481L565 476" stroke="#f5ddd1" stroke-width="2"/>
  <!-- inked torn cuff and seam -->
  <path d="M581 452L585 423L595 440L610 433L599 465L578 478L562 468Z"
        fill="#161621" stroke="#746475" stroke-width="5"/>
  <path d="M591 443L590 459M602 447L598 460" stroke="#ae8585" stroke-width="2"/>
</g>"""

MUZZLE = """
<g stroke="#482b20" stroke-linejoin="round">
 <path d="M371 22L334 -1L351 24L313 14L351 45L328 65L370 52L399 73L394 45L430 22L393 26L393 0Z"
       fill="#f8d38b" stroke-width="7"/>
 <path d="M372 25L356 10L366 35L346 29L369 46L385 59L386 39L408 24L384 32Z"
       fill="#fff3ca" stroke-width="3"/>
</g>"""

def svg_for(role: str, frame: int) -> str:
    # All positions come from the same original ink drawing, so there is no
    # discontinuous scale or conflicting style between frames.
    ads = role.startswith("ads")
    fire = role in ("fire","ads_fire")
    reload = role == "reload"
    sprint = role == "sprint"
    equip = role == "equip"
    recoil = (0, 16, 9, 3)[frame] if role == "fire" else ((0, 18, 6)[frame] if role == "ads_fire" else 0)
    shift = -18 if ads else (80 if sprint else (65 if equip and frame==0 else 0))
    dx = -35 if ads else 0
    scale = 1.12 if ads else (0.95 if sprint else 1)
    roll = -7 if sprint else (-12 if equip and frame==0 else 0)
    # Twelve frame reload: magazine exits downward and returns correctly.
    eject = 0.0
    reinsert = 0.0
    hand_drop = 0.0
    if reload:
        phase = frame / 11.0
        if phase < .24:
            eject = 0.0
            hand_drop = phase * 130
        elif phase < .51:
            eject = (phase - .24)/.27 * 135
            hand_drop = 24+(phase-.24)*60
        elif phase < .72:
            eject = 135-(phase-.51)/.21*120
            hand_drop = 38-(phase-.51)*60
        else:
            eject = 15*(1-(phase-.72)/.28)
            hand_drop = max(0, 24*(1-(phase-.72)/.28))
    # No object is borrowed from the rejected sprite source sheet.
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 768 512">',
           DEFS, '<rect width="768" height="512" fill="none"/>']
    parts.append(f'<g transform="translate({dx} {shift+recoil}) translate(384 265) rotate({roll}) scale({scale}) translate(-384 -265)">')
    # weapon/barrel body and magazine made from distinct grouped ink shapes
    parts.append(GUN)
    parts.append(f'<g transform="translate({eject*-.28:.2f} {eject:.2f})">{MAG}</g>')
    parts.append(f'<g transform="translate({-hand_drop*.24:.2f} {hand_drop:.2f})">{LEFT_HAND}</g>')
    parts.append(RIGHT_HAND)
    if fire and frame in (0,1):
        parts.append(MUZZLE)
    parts.append('</g></svg>')
    return ''.join(parts)

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,default=Path("iglesia/assets/weapons/mp40_nun_2d"))
    a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    record={"schema":1,"source":"new-original-ink-svg-mp40-with-bare-nun-hands",
            "style":"2D gothic comic candidate, NOT final owner signoff",
            "old_marine_assets_used":False,"runtime_gun_3d":False,
            "canvas":[WIDTH,HEIGHT],"role_counts":COUNTS,"frames":{}}
    for role,count in COUNTS.items():
        for i in range(count):
            path=a.output/f"{role}_{i:02d}.png"
            cairosvg.svg2png(bytestring=svg_for(role,i).encode("utf-8"),write_to=str(path),
                            output_width=WIDTH,output_height=HEIGHT)
            with Image.open(path) as image:
                rgba=image.convert("RGBA")
                alpha=rgba.getchannel("A")
                if rgba.size!=(WIDTH,HEIGHT) or alpha.getbbox() is None or alpha.getextrema()[0]>=255:
                    raise ValueError("MP40_2D_INK_TRANSPARENCY_RED "+path.name)
            record["frames"][path.name]=path.stat().st_size
            print("IGLESIA_ORIGINAL_2D_NUN_MP40_FRAME",path.name,path.stat().st_size)
    (a.output/"INK_SOURCE_MANIFEST.json").write_text(json.dumps(record,indent=2)+"\n")
    print("IGLESIA_NEW_NUN_MP40_24_INK_SOURCE_FRAMES_READY_CANDIDATE")

if __name__=="__main__":
    main()
