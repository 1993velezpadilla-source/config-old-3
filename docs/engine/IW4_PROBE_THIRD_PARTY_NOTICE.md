# Xziel IW4 Probe third-party notice

The experimental APK build uses the public Winlator application source solely
as the Windows/x86-on-Android compatibility host.

- Upstream: `brunodev85/winlator-app`
- Pinned source commit: `90390783d955c75ca8ca153353cf3c5b9ca6d6a1`
- Upstream license: LGPL-2.1
- Local patch source: `tools/iw4_android_spike/patch_winlator_probe.py`

The build does not contain, download, or redistribute Call of Duty: Modern
Warfare 2 executables, fastfiles, IWD files, models, textures, audio, or other
game payload. A user-supplied installation remains external to the APK.

The launcher looks for a compatibility-host shortcut named `XZIEL_IW4`. If it
does not exist, the app opens the normal Winlator setup interface. Once the
shortcut exists, reopening Xziel IW4 Probe jumps directly to the internal game
display activity using the shortcut's container ID and path.

This is an experimental feasibility build, not the shipping Xziel engine.
