#!/usr/bin/env python3
"""Insert a private test-only IPA bootstrap into touchHLE Android MainActivity.

Only modifies MainActivity.smali in a locally unpacked APK. No original
game binary or resources are stored in Git source.
"""
from pathlib import Path
import sys

if len(sys.argv)!=2:
    raise SystemExit("Usage: patch_touchhle_mainactivity.py <apktool-decoded-root>")
root=Path(sys.argv[1])
paths=list(root.glob("smali*/org/touchhle/android/MainActivity.smali"))
assert len(paths)==1, f"Expected one original touchHLE activity, got {paths}"
p=paths[0]
s=p.read_text("utf-8")
assert ".super Lorg/libsdl/app/SDLActivity;" in s
assert "getLibraries()[Ljava/lang/String;" in s
assert ".method protected onCreate(Landroid/os/Bundle;)V" not in s, "Activity already overrides onCreate"
assert "WAW_HD_EMBEDDED" not in s
s+="""
# WAW_HD_EMBEDDED -- call private IPA stage before native SDL initialization.
.method protected onCreate(Landroid/os/Bundle;)V
    .locals 0
    invoke-static {p0}, Lorg/touchhle/android/AndroidIpaBootstrap;->install(Landroid/content/Context;)V
    invoke-super {p0, p1}, Lorg/libsdl/app/SDLActivity;->onCreate(Landroid/os/Bundle;)V
    return-void
.end method
"""
p.write_text(s,"utf-8")
assert "invoke-static {p0}" in p.read_text()
print("WAW_HD_MAINACTIVITY_BOOTSTRAP_PATCH_GREEN",p)
