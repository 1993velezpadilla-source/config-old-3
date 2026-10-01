#include "xziel/intrinsic_ads.hpp"

#include <cassert>

int main() {
    xziel::LocalAdProvider provider;

    assert(provider.setCreative(
        1001,
        {
            .creativeId = 5001,
            .assetId = 9001,
            .kind = xziel::AdCreativeKind::Image,
            .width = 1024,
            .height = 1024,
        }));

    assert(provider.setCreative(
        2001,
        {
            .creativeId = 6001,
            .assetId = 9101,
            .kind = xziel::AdCreativeKind::Audio,
            .durationSeconds = 12.0f,
        }));

    xziel::IntrinsicAdSystem ads(&provider);

    assert(ads.addSurface({
        .placementId = 1001,
        .meshId = 3001,
        .materialSlot = 2,
        .aspectRatio = 1.0f,
        .maxViewDistanceMeters = 20.0f,
        .minimumFacingCosine = 0.4f,
        .minimumScreenCoverage = 0.001f,
        .impressionViewSeconds = 1.0f,
        .cooldownSeconds = 2.0f,
        .maxImpressionsPerSession = 2,
        .allowImage = true,
        .allowVideo = false,
    }));

    assert(ads.addAudioEmitter({
        .placementId = 2001,
        .emitterId = 7001,
        .minimumDistanceMeters = 1.0f,
        .maximumDistanceMeters = 10.0f,
        .maximumGain = 0.60f,
        .impressionListenSeconds = 1.0f,
        .cooldownSeconds = 2.0f,
        .maxImpressionsPerSession = 2,
    }));

    assert(ads.surfaceCount() == 1U);
    assert(ads.audioEmitterCount() == 1U);
    assert(ads.primeAll() == 2U);

    auto surface = ads.stepSurface(
        0,
        {
            .deltaSeconds = 0.5f,
            .distanceMeters = 5.0f,
            .facingCosine = 0.9f,
            .screenCoverage = 0.05f,
            .frustumVisible = true,
            .occluded = false,
        });

    assert(surface.loaded);
    assert(surface.visible);
    assert(!surface.impressionSent);

    surface = ads.stepSurface(
        0,
        {
            .deltaSeconds = 0.5f,
            .distanceMeters = 5.0f,
            .facingCosine = 0.9f,
            .screenCoverage = 0.05f,
            .frustumVisible = true,
            .occluded = false,
        });

    assert(surface.impressionSent);
    assert(surface.sessionImpressions == 1U);
    assert(provider.stats().impressions == 1U);

    surface = ads.stepSurface(
        0,
        {
            .deltaSeconds = 2.1f,
            .distanceMeters = 30.0f,
            .facingCosine = -0.5f,
            .screenCoverage = 0.0f,
            .frustumVisible = false,
            .occluded = true,
        });

    assert(!surface.visible);
    assert(surface.visibleSeconds == 0.0f);
    assert(surface.cooldownRemainingSeconds == 0.0f);
    assert(ads.refreshSurface(0));

    auto audio = ads.stepAudioEmitter(
        0,
        {
            .deltaSeconds = 0.5f,
            .distanceMeters = 2.0f,
            .enabled = true,
        });

    assert(audio.loaded);
    assert(audio.audible);
    assert(audio.gain > 0.0f);
    assert(audio.gain <= 0.60f);
    assert(!audio.impressionSent);

    audio = ads.stepAudioEmitter(
        0,
        {
            .deltaSeconds = 0.5f,
            .distanceMeters = 2.0f,
            .enabled = true,
        });

    assert(audio.impressionSent);
    assert(audio.sessionImpressions == 1U);
    assert(provider.stats().impressions == 2U);

    const auto adVoice = ads.makeAudioSource(
        0,
        {
            .deltaSeconds = 0.0f,
            .distanceMeters = 2.0f,
            .enabled = true,
        });

    assert(adVoice.id == 7001U);
    assert(adVoice.kind == xziel::AudioSourceKind::Advertisement);
    assert(adVoice.baseGain > 0.0f);
    assert(!adVoice.critical);

    const auto surfaceDebug = ads.surfaceDebugSnapshot(0);
    assert(surfaceDebug.placementId == 1001U);
    assert(surfaceDebug.loaded);

    const auto audioDebug = ads.audioDebugSnapshot(0);
    assert(audioDebug.placementId == 2001U);
    assert(audioDebug.loaded);

    assert(provider.stats().visibilitySamples >= 3U);
    assert(provider.stats().playbackSamples >= 2U);

    return 0;
}
