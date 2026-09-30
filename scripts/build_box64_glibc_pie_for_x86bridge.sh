#!/usr/bin/env bash
set -euo pipefail

# XZIEL x86-bridge: the glibc static-PIE experiment (#83-#85) is rejected
# by Android x86 sh before Wine starts. Keep this workflow entrypoint stable,
# but delegate to the proven Android/Bionic PIE Box64 build. The smoke script
# injects a true x86_64 guest FreeType bundle and forces that library emulated,
# so Box64 no longer needs the incompatible Android libft2 FreeType backend.
ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
echo "XZIEL_BOX64_ENTRYPOINT_MODE=bionic-pie-x86_64-guest-freetype"
exec bash "$ROOT/scripts/build_box64_android_pie_for_x86bridge.sh"
