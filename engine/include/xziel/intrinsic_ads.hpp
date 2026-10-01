#pragma once

#include "xziel/audio_scene.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace xziel {

inline constexpr std::size_t kMaxAdSurfaces = 32;
inline constexpr std::size_t kMaxAdAudioEmitters = 16;
inline constexpr std::size_t kMaxLocalAdCreatives = 64;

enum class AdCreativeKind : std::uint8_t {
    Image,
    Video,
    Audio,
};

enum class AdPlacementKind : std::uint8_t {
    Surface,
    AudioEmitter,
};

struct AdCreative {
    std::uint64_t creativeId = 0;
    std::uint64_t assetId = 0;
    AdCreativeKind kind = AdCreativeKind::Image;
    std::uint16_t width = 0;
    std::uint16_t height = 0;
    float durationSeconds = 0.0f;

    [[nodiscard]] bool valid() const noexcept;
};

struct AdRequest {
    std::uint64_t placementId = 0;
    AdPlacementKind placementKind = AdPlacementKind::Surface;
    bool allowImage = false;
    bool allowVideo = false;
    bool allowAudio = false;
};

struct AdVisibilitySample {
    std::uint64_t placementId = 0;
    std::uint64_t creativeId = 0;
    float deltaSeconds = 0.0f;
    float distanceMeters = 0.0f;
    float facingCosine = 0.0f;
    float screenCoverage = 0.0f;
    bool visible = false;
};

struct AdPlaybackSample {
    std::uint64_t placementId = 0;
    std::uint64_t creativeId = 0;
    float deltaSeconds = 0.0f;
    float distanceMeters = 0.0f;
    float gain = 0.0f;
    bool audible = false;
};

class IAdProvider {
public:
    virtual ~IAdProvider() = default;

    [[nodiscard]] virtual bool requestAd(
        const AdRequest& request,
        AdCreative& creative) noexcept = 0;

    virtual void releaseAd(
        std::uint64_t placementId,
        std::uint64_t creativeId) noexcept = 0;

    virtual void reportVisibility(
        const AdVisibilitySample& sample) noexcept = 0;

    virtual void reportPlayback(
        const AdPlaybackSample& sample) noexcept = 0;

    virtual void reportImpression(
        std::uint64_t placementId,
        std::uint64_t creativeId) noexcept = 0;

    virtual void reportCompletion(
        std::uint64_t placementId,
        std::uint64_t creativeId) noexcept = 0;

    virtual void reportError(
        std::uint64_t placementId,
        std::uint32_t errorCode) noexcept = 0;
};

struct LocalAdProviderStats {
    std::uint32_t requests = 0;
    std::uint32_t releases = 0;
    std::uint32_t visibilitySamples = 0;
    std::uint32_t playbackSamples = 0;
    std::uint32_t impressions = 0;
    std::uint32_t completions = 0;
    std::uint32_t errors = 0;

    std::uint64_t lastPlacementId = 0;
    std::uint64_t lastCreativeId = 0;
};

class LocalAdProvider final : public IAdProvider {
public:
    [[nodiscard]] bool setCreative(
        std::uint64_t placementId,
        const AdCreative& creative) noexcept;

    void clear() noexcept;

    [[nodiscard]] bool requestAd(
        const AdRequest& request,
        AdCreative& creative) noexcept override;

    void releaseAd(
        std::uint64_t placementId,
        std::uint64_t creativeId) noexcept override;

    void reportVisibility(
        const AdVisibilitySample& sample) noexcept override;

    void reportPlayback(
        const AdPlaybackSample& sample) noexcept override;

    void reportImpression(
        std::uint64_t placementId,
        std::uint64_t creativeId) noexcept override;

    void reportCompletion(
        std::uint64_t placementId,
        std::uint64_t creativeId) noexcept override;

    void reportError(
        std::uint64_t placementId,
        std::uint32_t errorCode) noexcept override;

    [[nodiscard]] const LocalAdProviderStats& stats() const noexcept;

private:
    struct Entry {
        std::uint64_t placementId = 0;
        AdCreative creative{};
    };

    std::array<Entry, kMaxLocalAdCreatives> entries_{};
    std::size_t entryCount_ = 0;
    LocalAdProviderStats stats_{};
};

struct AdSurfaceDefinition {
    std::uint64_t placementId = 0;
    std::uint64_t meshId = 0;
    std::uint32_t materialSlot = 0;

    float aspectRatio = 1.0f;
    float maxViewDistanceMeters = 30.0f;
    float minimumFacingCosine = 0.25f;
    float minimumScreenCoverage = 0.0008f;
    float impressionViewSeconds = 1.0f;
    float cooldownSeconds = 30.0f;

    std::uint32_t maxImpressionsPerSession = 3;

    bool allowImage = true;
    bool allowVideo = false;
};

struct AdAudioEmitterDefinition {
    std::uint64_t placementId = 0;
    std::uint64_t emitterId = 0;

    float minimumDistanceMeters = 1.0f;
    float maximumDistanceMeters = 12.0f;
    float maximumGain = 0.65f;
    float impressionListenSeconds = 1.0f;
    float cooldownSeconds = 45.0f;

    std::uint32_t maxImpressionsPerSession = 3;
};

struct AdSurfaceInput {
    float deltaSeconds = 0.0f;
    float distanceMeters = 0.0f;
    float facingCosine = 0.0f;
    float screenCoverage = 0.0f;

    bool frustumVisible = false;
    bool occluded = false;
};

struct AdAudioEmitterInput {
    float deltaSeconds = 0.0f;
    float distanceMeters = 0.0f;
    bool enabled = true;
};

struct AdSurfaceFrame {
    AdCreative creative{};

    bool loaded = false;
    bool active = false;
    bool visible = false;
    bool impressionSent = false;

    float visibleSeconds = 0.0f;
    float cooldownRemainingSeconds = 0.0f;
    std::uint32_t sessionImpressions = 0;
};

struct AdAudioEmitterFrame {
    AdCreative creative{};

    bool loaded = false;
    bool active = false;
    bool audible = false;
    bool impressionSent = false;

    float gain = 0.0f;
    float listenedSeconds = 0.0f;
    float cooldownRemainingSeconds = 0.0f;
    std::uint32_t sessionImpressions = 0;
};

struct AdDebugSnapshot {
    std::uint64_t placementId = 0;
    std::uint64_t creativeId = 0;
    AdPlacementKind placementKind = AdPlacementKind::Surface;

    bool loaded = false;
    bool active = false;
    bool visibleOrAudible = false;
    bool impressionSent = false;

    float distanceMeters = 0.0f;
    float facingCosine = 0.0f;
    float accumulatedSeconds = 0.0f;
    float cooldownRemainingSeconds = 0.0f;
    std::uint32_t sessionImpressions = 0;
};

class IntrinsicAdSystem final {
public:
    explicit IntrinsicAdSystem(IAdProvider* provider = nullptr) noexcept;

    void setProvider(IAdProvider* provider) noexcept;
    void clear() noexcept;
    void beginSession() noexcept;

    [[nodiscard]] bool addSurface(
        const AdSurfaceDefinition& definition) noexcept;

    [[nodiscard]] bool addAudioEmitter(
        const AdAudioEmitterDefinition& definition) noexcept;

    [[nodiscard]] bool primeSurface(std::size_t index) noexcept;
    [[nodiscard]] bool primeAudioEmitter(std::size_t index) noexcept;
    [[nodiscard]] std::size_t primeAll() noexcept;

    [[nodiscard]] bool refreshSurface(std::size_t index) noexcept;
    [[nodiscard]] bool refreshAudioEmitter(std::size_t index) noexcept;

    [[nodiscard]] AdSurfaceFrame stepSurface(
        std::size_t index,
        const AdSurfaceInput& input) noexcept;

    [[nodiscard]] AdAudioEmitterFrame stepAudioEmitter(
        std::size_t index,
        const AdAudioEmitterInput& input) noexcept;

    [[nodiscard]] AudioSource makeAudioSource(
        std::size_t index,
        const AdAudioEmitterInput& input) const noexcept;

    [[nodiscard]] AdDebugSnapshot surfaceDebugSnapshot(
        std::size_t index) const noexcept;

    [[nodiscard]] AdDebugSnapshot audioDebugSnapshot(
        std::size_t index) const noexcept;

    [[nodiscard]] std::size_t surfaceCount() const noexcept;
    [[nodiscard]] std::size_t audioEmitterCount() const noexcept;

private:
    struct SurfaceState {
        AdSurfaceDefinition definition{};
        AdSurfaceFrame frame{};
        float lastDistanceMeters = 0.0f;
        float lastFacingCosine = 0.0f;
    };

    struct AudioState {
        AdAudioEmitterDefinition definition{};
        AdAudioEmitterFrame frame{};
        float lastDistanceMeters = 0.0f;
    };

    [[nodiscard]] bool requestSurface(SurfaceState& state) noexcept;
    [[nodiscard]] bool requestAudio(AudioState& state) noexcept;

    void releaseSurface(SurfaceState& state) noexcept;
    void releaseAudio(AudioState& state) noexcept;

    IAdProvider* provider_ = nullptr;
    std::array<SurfaceState, kMaxAdSurfaces> surfaces_{};
    std::array<AudioState, kMaxAdAudioEmitters> audioEmitters_{};
    std::size_t surfaceCount_ = 0;
    std::size_t audioEmitterCount_ = 0;
};

[[nodiscard]] bool intrinsicAdDebugEnabled() noexcept;

} // namespace xziel
