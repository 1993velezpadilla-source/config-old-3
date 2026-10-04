from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/"assets/audio/cc0_horror_library"
OUT=ROOT/"xogot/assets/audio/church"

FILES={
 "ambient_horror_techiew/ambient_horror.ogg":"ambience/horror_bed.ogg",
 "ambient_loops_rubberduck/rain.ogg":"ambience/rain.ogg",
 "general_sfx_rubberduck_01/bell_01.ogg":"world/church_bell.ogg",
 "general_sfx_rubberduck_01/door_open.ogg":"world/door_open.ogg",
 "general_sfx_rubberduck_01/switch_01.ogg":"world/power_switch.ogg",
 "general_sfx_rubberduck_01/machine_03.ogg":"world/machine_use.ogg",
 "ambient_loops_rubberduck/machine_06.ogg":"world/machine_loop.ogg",
 "general_sfx_rubberduck_01/wooded_box_open.ogg":"world/mystery_open.ogg",
 "breaking_falling_hits/bfh1_wood_breaking_01.ogg":"world/wood_break_01.ogg",
 "breaking_falling_hits/bfh1_wood_breaking_03.ogg":"world/wood_break_02.ogg",
 "breaking_falling_hits/bfh1_wood_hit_01.ogg":"world/wood_repair.ogg",
 "creature_rubberduck_02/monster_08.ogg":"zombie/moan_01.ogg",
 "creature_rubberduck_02/monster_12.ogg":"zombie/moan_02.ogg",
 "creature_rubberduck_02/grunt_06.ogg":"zombie/moan_03.ogg",
 "creature_rubberduck_02/attack_02.ogg":"zombie/attack_01.ogg",
 "creature_rubberduck_02/attack_04.ogg":"zombie/attack_02.ogg",
 "creature_rubberduck_02/die_02.ogg":"zombie/death_01.ogg",
 "creature_rubberduck_02/die_04.ogg":"zombie/death_02.ogg",
}
for src_rel,dst_rel in FILES.items():
    src=SRC/src_rel
    dst=OUT/dst_rel
    if not src.is_file():
        raise SystemExit(f"missing source {src}")
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
(OUT/"README.txt").write_text(
    "Curated from the repository CC0 horror library.\n"
    "Environmental/zombie audio only; weapon-specific MapMod audio remains separate.\n",
    encoding="utf-8",
)
count=len(list(OUT.rglob("*.ogg")))
if count != 18:
    raise SystemExit(f"expected 18 ogg, got {count}")
print("XZOGOT_CHURCH_AUDIO_STAGE_GREEN",count)
