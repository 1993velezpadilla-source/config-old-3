#include "xziel/intrinsic_ads.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>

namespace xziel {

namespace {

float finiteOrZero(float value) noexcept {
    return std::isfinite(value) ? value : 0.0f;
}

float nonNegative(float value) noexcept {
    return std::max(0.0f, finiteOrZero(value));
}

float clamp01(float value) noexcept {
    return std::clamp(finiteOrZero(value), 0.0f, 1.0f);
}

bool creativeAllowed(
    const AdRequest& request,
    const AdCreative& creative) noexcept {
    if (!creative.valid()) {
        return false;
    }

    switch (creative.kind) {
        case AdCreativeKind::Image:
            return request.allowImage;
        case AdCreativeKind::Video:
            return request.allowVideo;
        case AdCreativeKind::Audio:
            return request.allowAudio;
    }

    return false;
}

float requiredSurfaceViewSeconds(
    const AdSurfaceDefinition& definition,
    AdCreativeKind kind) noexcept {
    const float configured = nonNegative(definition.impressionViewSeconds);
    if (kind == AdCreativeKind::Video) {
        return std::max(configured, kIntrinsicAdVideoViewSeconds);
    }
    return std::max(configured, kIntrinsicAdDisplayViewSeconds);
}

float audioGain(
    const AdAudioEmitterDefinition& definition,
    float distanceMeters) noexcept {
    const float minDistance =
        std::max(0.0f, definition.minimumDistanceMeters);
    const float maxDistance =
        std::max(minDistance + 0.001f, definition.maximumDistanceMeters);
    const float distance = nonNegative(distanceMeters);

    if (distance >= maxDistance) {
        return 0.0f;
    }

    if (distance <= minDistance) {
        return clamp01(definition.maximumGain);
    }

    const float normalized =
        (distance - minDistance) / (maxDistance - minDistance);
    const float smooth =
        1.0f - normalized * normalized * (3.0f - 2.0f * normalized);

    return clamp01(definition.maximumGain) * smooth;
}

} // namespace

bool AdCreative::valid() const noexcept {
    if (creativeId == 0U || assetId == 0U) {
        return false;
    }

    if (kind == AdCreativeKind::Audio) {
        return durationSeconds >= 0.0f &&
            std::isfinite(durationSeconds);
    }

    return width > 0U && height > 0U;
}

bool LocalAdProvider::setCreative(
    std::uint64_t placementId,
    const AdCreative& creative) noexcept {
    if (placementId == 0U || !creative.valid()) {
        return false;
    }

    for (std::size_t i = 0; i < entryCount_; ++i) {
        if (entries_[i].placementId == placementId) {
            entries_[i].creative = creative;
            return true;
        }
    }

    if (entryCount_ >= entries_.size()) {
        return false;
    }

    entries_[entryCount_] = {
        .placementId = placementId,
        .creative = creative,
    };
    ++entryCount_;
    return true;
}

void LocalAdProvider::clear() noexcept {
    entries_ = {};
    entryCount_ = 0;
    stats_ = {};
}

bool LocalAdProvider::requestAd(
    const AdRequest& request,
    AdCreative& creative) noexcept {
    ++stats_.requests;
    stats_.lastPlacementId = request.placementId;
    stats_.lastCreativeId = 0;

    for (std::size_t i = 0; i < entryCount_; ++i) {
        if (entries_[i].placementId != request.placementId) {
            continue;
        }

        if (!creativeAllowed(request, entries_[i].creative)) {
            return false;
        }

        creative = entries_[i].creative;
        stats_.lastCreativeId = creative.creativeId;
        return true;
    }

    return false;
}

void LocalAdProvider::releaseAd(
    std::uint64_t placementId,
    std::uint64_t creativeId) noexcept {
    ++stats_.releases;
    stats_.lastPlacementId = placementId;
    stats_.lastCreativeId = creativeId;
}

void LocalAdProvider::reportVisibility(
    const AdVisibilitySample& sample) noexcept {
    ++stats_.visibilitySamples;
    stats_.lastPlacementId = sample.placementId;
    stats_.lastCreativeId = sample.creativeId;
}

void LocalAdProvider::reportPlayback(
    const AdPlaybackSample& sample) noexcept {
    ++stats_.playbackSamples;
    stats_.lastPlacementId = sample.placementId;
    stats_.lastCreativeId = sample.creativeId;
}

void LocalAdProvider::reportImpression(
    std::uint64_t placementId,
    std::uint64_t creativeId) noexcept {
    ++stats_.impressions;
    stats_.lastPlacementId = placementId;
    stats_.lastCreativeId = creativeId;
}

void LocalAdProvider::reportCompletion(
    std::uint64_t placementId,
    std::uint64_t creativeId) noexcept {
    ++stats_.completions;
    stats_.lastPlacementId = placementId;
    stats_.lastCreativeId = creativeId;
}

void LocalAdProvider::reportError(
    std::uint64_t placementId,
    std::uint32_t errorCode) noexcept {
    (void) errorCode;
    ++stats_.errors;
    stats_.lastPlacementId = placementId;
    stats_.lastCreativeId = 0;
}

const LocalAdProviderStats& LocalAdProvider::stats() const noexcept {
    return stats_;
}

IntrinsicAdSystem::IntrinsicAdSystem(
    IAdProvider* provider) noexcept
    : provider_(provider) {}

void IntrinsicAdSystem::setProvider(IAdProvider* provider) noexcept {
    if (provider_ == provider) {
        return;
    }

    clear();
    provider_ = provider;
}

void IntrinsicAdSystem::clear() noexcept {
    for (std::size_t i = 0; i < surfaceCount_; ++i) {
        releaseSurface(surfaces_[i]);
    }
    for (std::size_t i = 0; i < audioEmitterCount_; ++i) {
        releaseAudio(audioEmitters_[i]);
    }

    surfaces_ = {};
    audioEmitters_ = {};
    surfaceCount_ = 0;
    audioEmitterCount_ = 0;
}

void IntrinsicAdSystem::beginSession() noexcept {
    for (std::size_t i = 0; i < surfaceCount_; ++i) {
        auto& frame = surfaces_[i].frame;
        frame.visibleSeconds = 0.0f;
        frame.cooldownRemainingSeconds = 0.0f;
        frame.sessionImpressions = 0;
        frame.impressionSent = false;
    }

    for (std::size_t i = 0; i < audioEmitterCount_; ++i) {
        auto& frame = audioEmitters_[i].frame;
        frame.listenedSeconds = 0.0f;
        frame.cooldownRemainingSeconds = 0.0f;
        frame.sessionImpressions = 0;
        frame.impressionSent = false;
    }
}

bool IntrinsicAdSystem::addSurface(
    const AdSurfaceDefinition& definition) noexcept {
    if (definition.placementId == 0U ||
        definition.meshId == 0U ||
        !std::isfinite(definition.aspectRatio) ||
        definition.aspectRatio <= 0.0f ||
        !std::isfinite(definition.maxViewDistanceMeters) ||
        definition.maxViewDistanceMeters <= 0.0f ||
        !std::isfinite(definition.minimumFacingCosine) ||
        !std::isfinite(definition.minimumScreenCoverage) ||
        !std::isfinite(definition.impressionViewSeconds) ||
        definition.impressionViewSeconds <= 0.0f ||
        !std::isfinite(definition.cooldownSeconds) ||
        definition.cooldownSeconds < 0.0f ||
        definition.maxImpressionsPerSession == 0U ||
        (!definition.allowImage && !definition.allowVideo) ||
        surfaceCount_ >= surfaces_.size()) {
        return false;
    }

    for (std::size_t i = 0; i < surfaceCount_; ++i) {
        if (surfaces_[i].definition.placementId == definition.placementId) {
            return false;
        }
    }

    surfaces_[surfaceCount_].definition = definition;
    ++surfaceCount_;
    return true;
}

bool IntrinsicAdSystem::addAudioEmitter(
    const AdAudioEmitterDefinition& definition) noexcept {
    if (definition.placementId == 0U ||
        definition.emitterId == 0U ||
        !std::isfinite(definition.minimumDistanceMeters) ||
        !std::isfinite(definition.maximumDistanceMeters) ||
        definition.minimumDistanceMeters < 0.0f ||
        definition.maximumDistanceMeters <= definition.minimumDistanceMeters ||
        !std::isfinite(definition.maximumGain) ||
        definition.maximumGain < 0.0f ||
        !std::isfinite(definition.impressionListenSeconds) ||
        definition.impressionListenSeconds <= 0.0f ||
        !std::isfinite(definition.cooldownSeconds) ||
        definition.cooldownSeconds < 0.0f ||
        definition.maxImpressionsPerSession == 0U ||
        audioEmitterCount_ >= audioEmitters_.size()) {
        return false;
    }

    for (std::size_t i = 0; i < audioEmitterCount_; ++i) {
        if (audioEmitters_[i].definition.placementId ==
            definition.placementId) {
            return false;
        }
    }

    audioEmitters_[audioEmitterCount_].definition = definition;
    ++audioEmitterCount_;
    return true;
}

bool IntrinsicAdSystem::primeSurface(std::size_t index) noexcept {
    if (index >= surfaceCount_) {
        return false;
    }
    return requestSurface(surfaces_[index]);
}

bool IntrinsicAdSystem::primeAudioEmitter(std::size_t index) noexcept {
    if (index >= audioEmitterCount_) {
        return false;
    }
    return requestAudio(audioEmitters_[index]);
}

std::size_t IntrinsicAdSystem::primeAll() noexcept {
    std::size_t primed = 0;

    for (std::size_t i = 0; i < surfaceCount_; ++i) {
        if (requestSurface(surfaces_[i])) {
            ++primed;
        }
    }

    for (std::size_t i = 0; i < audioEmitterCount_; ++i) {
        if (requestAudio(audioEmitters_[i])) {
            ++primed;
        }
    }

    return primed;
}

bool IntrinsicAdSystem::refreshSurface(std::size_t index) noexcept {
    if (index >= surfaceCount_) {
        return false;
    }

    auto& state = surfaces_[index];
    if (state.frame.cooldownRemainingSeconds > 0.0f ||
        state.frame.sessionImpressions >=
            state.definition.maxImpressionsPerSession) {
        return false;
    }

    releaseSurface(state);
    return requestSurface(state);
}

bool IntrinsicAdSystem::refreshAudioEmitter(std::size_t index) noexcept {
    if (index >= audioEmitterCount_) {
        return false;
    }

    auto& state = audioEmitters_[index];
    if (state.frame.cooldownRemainingSeconds > 0.0f ||
        state.frame.sessionImpressions >=
            state.definition.maxImpressionsPerSession) {
        return false;
    }

    releaseAudio(state);
    return requestAudio(state);
}

AdSurfaceFrame IntrinsicAdSystem::stepSurface(
    std::size_t index,
    const AdSurfaceInput& input) noexcept {
    if (index >= surfaceCount_) {
        return {};
    }

    auto& state = surfaces_[index];
    auto& frame = state.frame;
    const auto& definition = state.definition;
    const float dt = nonNegative(input.deltaSeconds);

    frame.cooldownRemainingSeconds =
        std::max(0.0f, frame.cooldownRemainingSeconds - dt);

    state.lastDistanceMeters = nonNegative(input.distanceMeters);
    state.lastFacingCosine =
        std::clamp(finiteOrZero(input.facingCosine), -1.0f, 1.0f);

    const bool viewable =
        frame.loaded &&
        frame.active &&
        !frame.impressionSent &&
        frame.sessionImpressions < definition.maxImpressionsPerSession &&
        input.frustumVisible &&
        !input.occluded &&
        state.lastDistanceMeters <= definition.maxViewDistanceMeters &&
        state.lastFacingCosine >=
            std::max(definition.minimumFacingCosine,
                     kIntrinsicAdMinimumFacingCosine) &&
        clamp01(input.visibleCreativeFraction) >=
            kIntrinsicAdMinimumVisibleFraction &&
        nonNegative(input.screenCoverage) >=
            std::max(definition.minimumScreenCoverage,
                     kIntrinsicAdMinimumScreenCoverage);

    frame.visible = viewable;

    if (viewable) {
        frame.visibleSeconds += dt;
    } else {
        frame.visibleSeconds = 0.0f;
    }

    if (provider_ != nullptr && frame.loaded) {
        provider_->reportVisibility({
            .placementId = definition.placementId,
            .creativeId = frame.creative.creativeId,
            .deltaSeconds = dt,
            .distanceMeters = state.lastDistanceMeters,
            .facingCosine = state.lastFacingCosine,
            .screenCoverage = nonNegative(input.screenCoverage),
            .visibleCreativeFraction = clamp01(input.visibleCreativeFraction),
            .visible = frame.visible,
        });
    }

    if (provider_ != nullptr &&
        frame.visible &&
        !frame.impressionSent &&
        frame.cooldownRemainingSeconds <= 0.0f &&
        frame.visibleSeconds >=
            requiredSurfaceViewSeconds(definition, frame.creative.kind)) {
        provider_->reportImpression(
            definition.placementId,
            frame.creative.creativeId);

        frame.impressionSent = true;
        ++frame.sessionImpressions;
        frame.cooldownRemainingSeconds = definition.cooldownSeconds;
    }

    return frame;
}

AdAudioEmitterFrame IntrinsicAdSystem::stepAudioEmitter(
    std::size_t index,
    const AdAudioEmitterInput& input) noexcept {
    if (index >= audioEmitterCount_) {
        return {};
    }

    auto& state = audioEmitters_[index];
    auto& frame = state.frame;
    const auto& definition = state.definition;
    const float dt = nonNegative(input.deltaSeconds);

    frame.cooldownRemainingSeconds =
        std::max(0.0f, frame.cooldownRemainingSeconds - dt);

    state.lastDistanceMeters = nonNegative(input.distanceMeters);
    frame.gain =
        input.enabled && frame.loaded && frame.active
            ? audioGain(definition, state.lastDistanceMeters)
            : 0.0f;

    frame.audible =
        frame.gain > 0.0001f &&
        !frame.impressionSent &&
        frame.sessionImpressions < definition.maxImpressionsPerSession;

    if (frame.audible) {
        frame.listenedSeconds += dt;
    } else {
        frame.listenedSeconds = 0.0f;
    }

    if (provider_ != nullptr && frame.loaded) {
        provider_->reportPlayback({
            .placementId = definition.placementId,
            .creativeId = frame.creative.creativeId,
            .deltaSeconds = dt,
            .distanceMeters = state.lastDistanceMeters,
            .gain = frame.gain,
            .audible = frame.audible,
        });
    }

    if (provider_ != nullptr &&
        frame.audible &&
        !frame.impressionSent &&
        frame.cooldownRemainingSeconds <= 0.0f &&
        frame.listenedSeconds >= definition.impressionListenSeconds) {
        provider_->reportImpression(
            definition.placementId,
            frame.creative.creativeId);

        frame.impressionSent = true;
        ++frame.sessionImpressions;
        frame.cooldownRemainingSeconds = definition.cooldownSeconds;
    }

    return frame;
}

AudioSource IntrinsicAdSystem::makeAudioSource(
    std::size_t index,
    const AdAudioEmitterInput& input) const noexcept {
    if (index >= audioEmitterCount_) {
        return {};
    }

    const auto& state = audioEmitters_[index];
    const float gain =
        input.enabled && state.frame.loaded && state.frame.active
            ? audioGain(state.definition, input.distanceMeters)
            : 0.0f;

    return {
        .id = state.definition.emitterId,
        .kind = AudioSourceKind::Advertisement,
        .distanceMeters = nonNegative(input.distanceMeters),
        .baseGain = gain,
        .importance = 0.35f,
        .occlusion = 0.0f,
        .reverbZoneSend = 0.25f,
        .looping = false,
        .critical = false,
    };
}

AdDebugSnapshot IntrinsicAdSystem::surfaceDebugSnapshot(
    std::size_t index) const noexcept {
    if (index >= surfaceCount_) {
        return {};
    }

    const auto& state = surfaces_[index];
    return {
        .placementId = state.definition.placementId,
        .creativeId = state.frame.creative.creativeId,
        .placementKind = AdPlacementKind::Surface,
        .loaded = state.frame.loaded,
        .active = state.frame.active,
        .visibleOrAudible = state.frame.visible,
        .impressionSent = state.frame.impressionSent,
        .distanceMeters = state.lastDistanceMeters,
        .facingCosine = state.lastFacingCosine,
        .accumulatedSeconds = state.frame.visibleSeconds,
        .cooldownRemainingSeconds =
            state.frame.cooldownRemainingSeconds,
        .sessionImpressions = state.frame.sessionImpressions,
    };
}

AdDebugSnapshot IntrinsicAdSystem::audioDebugSnapshot(
    std::size_t index) const noexcept {
    if (index >= audioEmitterCount_) {
        return {};
    }

    const auto& state = audioEmitters_[index];
    return {
        .placementId = state.definition.placementId,
        .creativeId = state.frame.creative.creativeId,
        .placementKind = AdPlacementKind::AudioEmitter,
        .loaded = state.frame.loaded,
        .active = state.frame.active,
        .visibleOrAudible = state.frame.audible,
        .impressionSent = state.frame.impressionSent,
        .distanceMeters = state.lastDistanceMeters,
        .facingCosine = 0.0f,
        .accumulatedSeconds = state.frame.listenedSeconds,
        .cooldownRemainingSeconds =
            state.frame.cooldownRemainingSeconds,
        .sessionImpressions = state.frame.sessionImpressions,
    };
}

std::size_t IntrinsicAdSystem::surfaceCount() const noexcept {
    return surfaceCount_;
}

std::size_t IntrinsicAdSystem::audioEmitterCount() const noexcept {
    return audioEmitterCount_;
}

bool IntrinsicAdSystem::requestSurface(SurfaceState& state) noexcept {
    if (provider_ == nullptr) {
        return false;
    }

    if (state.frame.loaded) {
        return true;
    }

    AdCreative creative{};
    const AdRequest request{
        .placementId = state.definition.placementId,
        .placementKind = AdPlacementKind::Surface,
        .allowImage = state.definition.allowImage,
        .allowVideo = state.definition.allowVideo,
        .allowAudio = false,
    };

    if (!provider_->requestAd(request, creative) ||
        !creativeAllowed(request, creative)) {
        provider_->reportError(state.definition.placementId, 1U);
        return false;
    }

    state.frame.creative = creative;
    state.frame.loaded = true;
    state.frame.active = true;
    state.frame.visible = false;
    state.frame.visibleSeconds = 0.0f;
    state.frame.impressionSent = false;
    return true;
}

bool IntrinsicAdSystem::requestAudio(AudioState& state) noexcept {
    if (provider_ == nullptr) {
        return false;
    }

    if (state.frame.loaded) {
        return true;
    }

    AdCreative creative{};
    const AdRequest request{
        .placementId = state.definition.placementId,
        .placementKind = AdPlacementKind::AudioEmitter,
        .allowImage = false,
        .allowVideo = false,
        .allowAudio = true,
    };

    if (!provider_->requestAd(request, creative) ||
        !creativeAllowed(request, creative)) {
        provider_->reportError(state.definition.placementId, 2U);
        return false;
    }

    state.frame.creative = creative;
    state.frame.loaded = true;
    state.frame.active = true;
    state.frame.audible = false;
    state.frame.gain = 0.0f;
    state.frame.listenedSeconds = 0.0f;
    state.frame.impressionSent = false;
    return true;
}

void IntrinsicAdSystem::releaseSurface(SurfaceState& state) noexcept {
    if (provider_ != nullptr && state.frame.loaded) {
        provider_->releaseAd(
            state.definition.placementId,
            state.frame.creative.creativeId);
    }

    const std::uint32_t impressions = state.frame.sessionImpressions;
    const float cooldown = state.frame.cooldownRemainingSeconds;
    state.frame = {};
    state.frame.sessionImpressions = impressions;
    state.frame.cooldownRemainingSeconds = cooldown;
}

void IntrinsicAdSystem::releaseAudio(AudioState& state) noexcept {
    if (provider_ != nullptr && state.frame.loaded) {
        provider_->releaseAd(
            state.definition.placementId,
            state.frame.creative.creativeId);
    }

    const std::uint32_t impressions = state.frame.sessionImpressions;
    const float cooldown = state.frame.cooldownRemainingSeconds;
    state.frame = {};
    state.frame.sessionImpressions = impressions;
    state.frame.cooldownRemainingSeconds = cooldown;
}

bool intrinsicAdDebugEnabled() noexcept {
    const char* value = std::getenv("XZIEL_AD_DEBUG");
    return value != nullptr &&
        (std::strcmp(value, "1") == 0 ||
         std::strcmp(value, "true") == 0 ||
         std::strcmp(value, "TRUE") == 0);
}

} // namespace xziel
