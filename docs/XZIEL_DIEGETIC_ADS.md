# XZIEL Diegetic Advertising Runtime v1

Goal: monetize without pausing the match, covering the HUD, or turning the Zombies loop into an ad break.

## Runtime model

XZIEL owns world-space ad surfaces. A map exports a sidecar manifest describing:
- surface ID;
- world transform;
- physical dimensions;
- media capability;
- viewability state;
- audio radius/cooldown where relevant;
- zone and map context.

The rendering path remains native Vulkan. Ads are textures/video/audio attached to authored world objects, never gameplay-blocking UI.

## Provider modes

### 1. House / direct-sponsor mode — baseline

This is the default implementation target because XZIEL controls the creative, delivery URL, caching, fallback image and audio behavior.

Use cases:
- house promotion;
- directly sold sponsor campaign;
- static poster/frame;
- silent looping creative;
- licensed spatial radio spot.

No external ad SDK assumptions are required.

### 2. Intrinsic in-game provider adapter — candidate

Anzu is the first provider candidate to evaluate because its current developer material explicitly describes non-interruptive in-game placements on mobile and support for custom-built engines.

Provider integration is a replaceable adapter. Map files must never contain provider-specific IDs as geometry authority.

### 3. Conventional mobile ad SDKs — separate surface

Do not render Google Mobile Ads native creatives into XZIEL 3D textures. Google's Android native-ad implementation uses NativeAdView/ViewGroup assets and SDK-managed click/impression behavior. If a conventional SDK is ever added, it must use its supported UI format separately.

Interstitials are intentionally not part of the normal Zombies match. Google's own guidance places them at natural transitions and warns against surprising a user during active gameplay.

## Non-interruption contract

Every XZIEL diegetic placement must satisfy:
- gameplay never pauses;
- HUD is never covered;
- no forced fullscreen;
- no forced click/tap;
- no ad is placed over an interactable gameplay prompt;
- quest/combat VO outranks sponsor audio;
- audio ads are spatial and range-limited;
- one sponsor audio voice maximum at a time;
- leaving the room attenuates naturally;
- cooldown is enforced per placement and globally;
- missing network/creative silently falls back to authored world art;
- offline gameplay remains fully functional.

## Sanctum v1 placements

1. `ad_frame_nave_west`
   - framed wall surface;
   - static image or silent video;
   - no audio.

2. `ad_frame_gallery_east`
   - upper-gallery framed surface;
   - static image or silent video;
   - no audio.

3. `radio_ad_undercroft`
   - spatial radio;
   - audio only;
   - 7.5 m maximum radius;
   - 2.5 m full-volume radius;
   - 15 s maximum creative;
   - 480 s minimum cooldown;
   - ducks below enemy and quest VO.

The authoritative per-build placement transforms are emitted in `sanctum-ad-surfaces.json`.

## Provider-policy gate

No third-party creative is enabled merely because an SDK can technically deliver it. Before enabling a provider adapter:
1. validate current placement/rendering rules;
2. validate click/impression/viewability requirements;
3. validate age/privacy/consent requirements for the target storefronts;
4. use provider test creatives during development;
5. verify that the provider explicitly supports the rendered in-world format.

Until those gates are green, Sanctum uses house/direct-sponsor creatives only.

## Current research basis (2026-10-01)

- Google Mobile Ads Android Native Ads documentation: NativeAd assets are displayed inside NativeAdView and the SDK manages registered asset interactions.
- Google AdMob interstitial guidance: interstitials belong at natural transition points and should not unexpectedly interrupt active use/gameplay.
- Anzu mobile/developer material: intrinsic ads are positioned as non-interruptive in-game placements and the company states support for major and custom-built game engines.

These are implementation constraints, not an endorsement or commitment to any provider.
