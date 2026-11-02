#!/usr/bin/env bash
# Standalone Android build of the safely forked XZIEL/Vril v0.26 gameplay.
# The original Android package com.xziel.nzp remains untouched.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# The original pinned v0.26 source + patches, official assets, QuakeC
# gameplay, HUD and 12 button skins are all assembled by this script.
bash scripts/prepare_android.sh

APP_GRADLE="$ROOT/build/android-project/app/build.gradle"
APP_STRINGS="$ROOT/build/android-project/app/src/main/res/values/strings.xml"
python3 - "$APP_GRADLE" "$APP_STRINGS" <<'PY'
from pathlib import Path
import sys
gradle_path, strings_path = map(Path, sys.argv[1:])
gradle = gradle_path.read_text()
old = 'applicationId "com.xziel.nzp"'
new = 'applicationId "com.xziel.viriliw3"'
assert gradle.count(old) == 1, 'Cannot isolate Viril IW3 Android package'
gradle = gradle.replace(old, new)
assert 'versionName "0.26-online-social-test"' in gradle
gradle = gradle.replace('versionName "0.26-online-social-test"',
                        'versionName "0.26-viril-iw3-baseline"')
gradle_path.write_text(gradle)
strings = strings_path.read_text()
assert 'Xziel: NZP Native' in strings
strings_path.write_text(strings.replace('Xziel: NZP Native', 'Viril IW3'))
PY

# Must ship an entire NZ:P game, not a minimal engine-only shell.
DATA="$ROOT/build/android-project/app/src/main/assets/nzp-data.zip"
test -s "$DATA"
python3 - "$DATA" <<'PY'
import sys, zipfile
path=sys.argv[1]
with zipfile.ZipFile(path) as z:
    names={n.lower().lstrip('/') for n in z.namelist()}
    def require(suffix):
        matches=[name for name in names if name.endswith(suffix)]
        if not matches:
            raise SystemExit('Missing required original NZ:P data: '+suffix)
        print('OK:', suffix, len(matches))
    for rel in (
        'models/weapons/mp40/v_mp40.mdl',
        'gfx/xziel/fire.png',
        'gfx/xziel/ads.png',
        'gfx/xziel/reload.png',
        'progs.dat',
    ):
        require(rel)
    maps=[x for x in names if x.endswith('.bsp')]
    models=[x for x in names if x.endswith('.mdl')]
    print('Bundled game maps (BSP):',len(maps))
    print('Bundled animated models (MDL):',len(models))
    if not maps or len(models)<10:
        raise SystemExit('Incomplete original NZ:P game asset archive')
PY
echo "VIRIL IW3 game data complete; independent application ID applied."
