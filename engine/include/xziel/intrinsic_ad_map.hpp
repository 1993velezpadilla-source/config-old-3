#pragma once

#include "xziel/intrinsic_ads.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>

namespace xziel {

inline constexpr std::uint32_t kIntrinsicAdMapVersion = 1U;
inline constexpr std::size_t kIntrinsicAdAssetPathBytes = 96U;

enum IntrinsicAdMapSurfaceFlags : std::uint32_t {
    IntrinsicAdMapSurfaceImage = 1U << 0U,
    IntrinsicAdMapSurfaceVideo = 1U << 1U,
};

struct IntrinsicAdMapSurface {
    std::uint64_t placementId = 0U;
    std::array<char, kIntrinsicAdAssetPathBytes>
        sourceTextureAssetPath{};

    std::array<float, 3> centerMeters{};
    std::array<float, 3> normal{0.0f, 0.0f, 1.0f};

    float widthMeters = 1.0f;
    float heightMeters = 1.0f;
    float maxViewDistanceMeters = 20.0f;
    float minimumFacingCosine = 0.25f;
    float minimumScreenCoverage = 0.0008f;
    float impressionViewSeconds = 1.0f;
    float cooldownSeconds = 30.0f;

    std::uint32_t maxImpressionsPerSession = 3U;
    std::uint32_t flags = IntrinsicAdMapSurfaceImage;
};

struct IntrinsicAdMapAudioEmitter {
    std::uint64_t placementId = 0U;
    std::uint64_t emitterId = 0U;
    std::array<char, kIntrinsicAdAssetPathBytes>
        fallbackAudioAssetPath{};

    std::array<float, 3> centerMeters{};

    float minimumDistanceMeters = 1.0f;
    float maximumDistanceMeters = 12.0f;
    float maximumGain = 0.60f;
    float impressionListenSeconds = 1.0f;
    float cooldownSeconds = 45.0f;

    std::uint32_t maxImpressionsPerSession = 3U;
};

struct IntrinsicAdMap {
    std::array<IntrinsicAdMapSurface, kMaxAdSurfaces>
        surfaces{};
    std::array<
        IntrinsicAdMapAudioEmitter,
        kMaxAdAudioEmitters> audioEmitters{};

    std::size_t surfaceCount = 0U;
    std::size_t audioEmitterCount = 0U;
};

enum class IntrinsicAdMapParseError : std::uint8_t {
    None,
    Truncated,
    InvalidMagic,
    UnsupportedVersion,
    CapacityExceeded,
    InvalidSurface,
    InvalidAudioEmitter,
    DuplicatePlacementId,
    TrailingData,
};

struct IntrinsicAdMapParseResult {
    bool success = false;
    IntrinsicAdMapParseError error =
        IntrinsicAdMapParseError::None;
    std::size_t offset = 0U;
};

[[nodiscard]] IntrinsicAdMapParseResult
parseIntrinsicAdMapXzad(
    std::span<const std::byte> bytes,
    IntrinsicAdMap& destination) noexcept;

[[nodiscard]] std::uint64_t intrinsicAdAssetId(
    std::string_view assetPath) noexcept;

[[nodiscard]] AdSurfaceDefinition
makeAdSurfaceDefinition(
    const IntrinsicAdMapSurface& surface) noexcept;

[[nodiscard]] AdAudioEmitterDefinition
makeAdAudioEmitterDefinition(
    const IntrinsicAdMapAudioEmitter& emitter) noexcept;

[[nodiscard]] std::string_view intrinsicAdAssetPath(
    const std::array<
        char,
        kIntrinsicAdAssetPathBytes>& path) noexcept;

} // namespace xziel
