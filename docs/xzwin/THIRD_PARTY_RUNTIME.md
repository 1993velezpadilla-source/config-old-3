# XZWin experimental runtime provenance

XZWin is an XZIEL compatibility layer. It does not present or reuse the
Winlator user interface.

The experimental runtime packaging workflow currently obtains compatibility
components from the public Winlator 11.2 source tree only as a reproducible
upstream source for the Android test:

- Winlator source/runtime assembly: LGPL-2.1
- Wine: LGPL-2.1-or-later
- Box64: MIT
- Mesa/Turnip and other rootfs components: their respective upstream licenses

Upstream source:
https://github.com/brunodev85/winlator-app

Pinned inputs in the CI experiment:

- Winlator commit: 3981d86efa4f333b2a34a7da8b6521476cd8c8b9
- rootfs.tzst blob: 3276da2f280707ccfded5dd76181e7bf7a53ec6e
- Box64 0.4.4 archive blob: c505bc89a765f1e259491730f3064772bfb5e00f

Before distributing XZWin as a production APK, XZIEL must ship the complete
third-party notices/source or relinking materials required by every component
actually included in the final runtime. Removing Winlator branding from the
boot UI does not remove these license obligations.
