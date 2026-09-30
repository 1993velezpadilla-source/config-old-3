# XZIEL BOZ runtime mod layer

This experiment uses the MIT-licensed loader from `Producdevity/cod-boz-port`
as a clean runtime harness. It does **not** vendor Call of Duty game data into
this repository.

## Gate 1

Patch the loader's S3E file layer so the following directory has absolute
read priority:

```
assets/xziel_mod/
```

When the guest asks for:

```
data-etc/example.group.bin
```

the loader first checks:

```
assets/xziel_mod/data-etc/example.group.bin
```

Only when there is no override does it fall back to the normal loose assets
or the original DTRZ `blackops_*.dz` archive.

The CI test creates a tiny valid DTRZ archive containing a stock asset, then
places an XZIEL asset with the exact same requested name in `xziel_mod`.
The gate is GREEN only when `s3eFileOpen()` returns the XZIEL asset.

## Why this matters

This is the first required proof before touching maps. It establishes that
we can redirect BOZ resource requests to our own files without repacking the
commercial game archive.

## Upstream pin

`Producdevity/cod-boz-port@3b444d6003a78f08694e965509477d13a742ebf1`

License: MIT (upstream source code only).

Game data is intentionally excluded. A later device/runtime test must use a
legally obtained local APK/game-data input and must not commit that data.
