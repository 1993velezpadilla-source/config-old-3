# Call of Duty: Warzone Mobile → Xziel Engine Lessons

Research date: 2026-09-21

## Why this title is different

Warzone Mobile attempted something more aggressive than COD Mobile:

take the real unified Call of Duty technology/content ecosystem and adapt it to phones instead of building primarily around a mobile-first Unity stack.

Activision publicly described it as using the real Call of Duty renderer, with console/PC rendering features selectively adapted rather than copied one-for-one.

It also targeted:
- Verdansk-scale world;
- 120 live-player BR;
- shared content/progression;
- mobile-specific renderer work;
- hi-res visual asset streaming.

This makes it useful both as a technical example and as a caution.

## Real renderer, mobile feature selection

Activision's Chris Plummer explained that Warzone Mobile used the real Call of Duty renderer but not every feature one-to-one.

This validates a central Xziel principle:

```
shared content semantics
!= identical renderer workload
```

A weapon/material/map should be authored from a common source, but mobile cook/output can use:
- reduced geometry;
- different material permutation;
- different shadow method;
- baked substitutes;
- different texture resolution;
- different VFX implementation.

## Hi-res asset streaming

Warzone Mobile streamed higher-fidelity graphics while the player played.

Official Call of Duty launch material exposed a setting for hi-res asset streaming and allowed performance to prioritize frame rate or battery.

Activision also acknowledged that this approach could initially show lower fidelity while assets were still arriving.

For Xziel:
- never make essential gameplay readability dependent on network streaming;
- ship a complete low/mid-quality local baseline;
- optional high-resolution packs can improve presentation;
- prefetch before first gameplay whenever possible;
- expose download/storage controls.

## Streaming failure lesson

Post-launch updates specifically adjusted:
- more assets loaded before match start;
- default device graphics/FPS settings;
- thermal behavior;
- asset-streaming efficiency.

The lesson is that streaming must be judged by **time-to-good-image**, not only install-size savings.

Metrics:
- bootstrap texture quality;
- first-room high-res completion time;
- missing-mip count;
- bandwidth use;
- storage cache hit;
- gameplay hitch time.

## Thermal lesson

Activision acknowledged that some devices shipped with FPS defaults too high, producing temperature/performance problems, and adjusted those defaults.

This is exactly why Xziel needs an automatic governor rather than a static phone whitelist.

## 120-player architecture lesson

Publicly confirmed:
- up to 120 live players;
- Activision Demonware backend;
- unified Call of Duty technology.

The exact proprietary replication/prediction/tick implementation is not publicly verified enough to reproduce.

Xziel should take only the architectural lesson:
- network scale is separate from renderer scale;
- interest management is mandatory;
- remote entity presentation needs LOD;
- replication frequency should follow relevance.

Zombies co-op is dramatically smaller, so we can spend more budget per relevant enemy/player than a 120-player BR.

## Product lesson

Warzone Mobile was removed from stores in 2025 and its servers went offline April 17, 2026.

Activision states that although they were proud of authentically bringing Warzone to mobile, it did not meet expectations with mobile-first players in the same way as PC/console audiences.

For Xziel this is an important reminder:
**desktop/console technical authenticity is not automatically mobile product fit.**

Touch ergonomics, install/storage, power, launch speed, thermals and fast readability are first-class design constraints.

## What Xziel should borrow

- shared-content pipeline with mobile-specific cook;
- selective reuse of high-end renderer concepts;
- scalable device profiles;
- hi-res optional content;
- backend/network authority;
- aggressive visual streaming.

## What Xziel should avoid

- requiring network streaming for acceptable first-launch visuals;
- default FPS caps based only on peak benchmarks;
- treating mobile as a smaller-screen PC build;
- assuming console fidelity matters more than thermal stability or touch feel.

## Public references

- Call of Duty official Warzone Mobile announcement
  https://www.callofduty.com/blog/2022/09/call-of-duty-warzone-mobile-battle-royale-free-to-play-rewards
- Call of Duty official launch/settings guide
  https://www.callofduty.com/blog/2024/03/call-of-duty-warzone-mobile-prepare-for-launch-need-to-know
- Activision developer interview
  https://gamesbeat.com/how-activision-designed-call-of-duty-warzone-mobile-chris-plummer-interview/
- Activision interview discussing hi-res visual streaming
  https://mobilematters.gg/news/gaming/warzone-mobile-exclusive-interview
- Official service-change notice
  https://support.activision.com/warzone-mobile/articles/warzone-mobile-service-changes
