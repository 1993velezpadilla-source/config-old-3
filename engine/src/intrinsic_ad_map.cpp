#include "xziel/intrinsic_ad_map.hpp"

#include <algorithm>
#include <bit>
#include <cmath>
#include <cstring>

namespace xziel {

namespace {

class Reader final {
public:
    explicit Reader(
        std::span<const std::byte> bytes) noexcept
        : bytes_(bytes) {}

    [[nodiscard]] std::size_t offset() const noexcept {
        return offset_;
    }

    [[nodiscard]] std::size_t remaining() const noexcept {
        return bytes_.size() - offset_;
    }

    [[nodiscard]] bool readBytes(
        void* destination,
        std::size_t size) noexcept {
        if (destination == nullptr ||
            size > remaining()) {
            return false;
        }

        std::memcpy(
            destination,
            bytes_.data() + offset_,
            size);
        offset_ += size;
        return true;
    }

    [[nodiscard]] bool readU32(
        std::uint32_t& value) noexcept {
        std::array<std::uint8_t, 4> raw{};
        if (!readBytes(raw.data(), raw.size())) {
            return false;
        }

        value =
            static_cast<std::uint32_t>(raw[0]) |
            (static_cast<std::uint32_t>(raw[1]) << 8U) |
            (static_cast<std::uint32_t>(raw[2]) << 16U) |
            (static_cast<std::uint32_t>(raw[3]) << 24U);
        return true;
    }

    [[nodiscard]] bool readU64(
        std::uint64_t& value) noexcept {
        std::uint32_t low = 0U;
        std::uint32_t high = 0U;
        if (!readU32(low) || !readU32(high)) {
            return false;
        }

        value =
            static_cast<std::uint64_t>(low) |
            (static_cast<std::uint64_t>(high) << 32U);
        return true;
    }

    [[nodiscard]] bool readF32(
        float& value) noexcept {
        std::uint32_t bits = 0U;
        if (!readU32(bits)) {
            return false;
        }

        value = std::bit_cast<float>(bits);
        return std::isfinite(value);
    }

private:
    std::span<const std::byte> bytes_{};
    std::size_t offset_ = 0U;
};

IntrinsicAdMapParseResult failure(
    IntrinsicAdMapParseError error,
    std::size_t offset,
    IntrinsicAdMap& destination) noexcept {
    destination = {};
    return {
        .success = false,
        .error = error,
        .offset = offset,
    };
}

bool pathValid(
    const std::array<
        char,
        kIntrinsicAdAssetPathBytes>& path) noexcept {
    if (path[0] == '\0') {
        return false;
    }

    return std::find(
        path.begin(),
        path.end(),
        '\0') != path.end();
}

bool placementIdSeen(
    const IntrinsicAdMap& map,
    std::uint64_t placementId) noexcept {
    for (std::size_t i = 0U;
         i < map.surfaceCount;
         ++i) {
        if (map.surfaces[i].placementId ==
            placementId) {
            return true;
        }
    }

    for (std::size_t i = 0U;
         i < map.audioEmitterCount;
         ++i) {
        if (map.audioEmitters[i].placementId ==
            placementId) {
            return true;
        }
    }

    return false;
}

bool vectorFinite(
    const std::array<float, 3>& values) noexcept {
    return std::all_of(
        values.begin(),
        values.end(),
        [](float value) noexcept {
            return std::isfinite(value);
        });
}

} // namespace

IntrinsicAdMapParseResult
parseIntrinsicAdMapXzad(
    std::span<const std::byte> bytes,
    IntrinsicAdMap& destination) noexcept {
    destination = {};

    Reader reader(bytes);
    std::array<char, 4> magic{};
    std::uint32_t version = 0U;
    std::uint32_t surfaceCount = 0U;
    std::uint32_t audioEmitterCount = 0U;

    if (!reader.readBytes(
            magic.data(),
            magic.size()) ||
        !reader.readU32(version) ||
        !reader.readU32(surfaceCount) ||
        !reader.readU32(audioEmitterCount)) {
        return failure(
            IntrinsicAdMapParseError::Truncated,
            reader.offset(),
            destination);
    }

    if (magic !=
        std::array<char, 4>{'X', 'Z', 'A', 'D'}) {
        return failure(
            IntrinsicAdMapParseError::InvalidMagic,
            0U,
            destination);
    }

    if (version != kIntrinsicAdMapVersion) {
        return failure(
            IntrinsicAdMapParseError::UnsupportedVersion,
            4U,
            destination);
    }

    if (surfaceCount > kMaxAdSurfaces ||
        audioEmitterCount > kMaxAdAudioEmitters) {
        return failure(
            IntrinsicAdMapParseError::CapacityExceeded,
            reader.offset(),
            destination);
    }

    for (std::uint32_t i = 0U;
         i < surfaceCount;
         ++i) {
        IntrinsicAdMapSurface surface{};

        if (!reader.readU64(surface.placementId) ||
            !reader.readBytes(
                surface.sourceTextureAssetPath.data(),
                surface.sourceTextureAssetPath.size())) {
            return failure(
                IntrinsicAdMapParseError::Truncated,
                reader.offset(),
                destination);
        }

        for (float& value : surface.centerMeters) {
            if (!reader.readF32(value)) {
                return failure(
                    IntrinsicAdMapParseError::Truncated,
                    reader.offset(),
                    destination);
            }
        }

        for (float& value : surface.normal) {
            if (!reader.readF32(value)) {
                return failure(
                    IntrinsicAdMapParseError::Truncated,
                    reader.offset(),
                    destination);
            }
        }

        if (!reader.readF32(surface.widthMeters) ||
            !reader.readF32(surface.heightMeters) ||
            !reader.readF32(
                surface.maxViewDistanceMeters) ||
            !reader.readF32(
                surface.minimumFacingCosine) ||
            !reader.readF32(
                surface.minimumScreenCoverage) ||
            !reader.readF32(
                surface.impressionViewSeconds) ||
            !reader.readF32(
                surface.cooldownSeconds) ||
            !reader.readU32(
                surface.maxImpressionsPerSession) ||
            !reader.readU32(surface.flags)) {
            return failure(
                IntrinsicAdMapParseError::Truncated,
                reader.offset(),
                destination);
        }

        const float normalLengthSquared =
            surface.normal[0] * surface.normal[0] +
            surface.normal[1] * surface.normal[1] +
            surface.normal[2] * surface.normal[2];

        const std::uint32_t knownFlags =
            IntrinsicAdMapSurfaceImage |
            IntrinsicAdMapSurfaceVideo;

        if (surface.placementId == 0U ||
            placementIdSeen(
                destination,
                surface.placementId) ||
            !pathValid(
                surface.sourceTextureAssetPath) ||
            !vectorFinite(surface.centerMeters) ||
            !vectorFinite(surface.normal) ||
            normalLengthSquared < 0.25f ||
            normalLengthSquared > 2.25f ||
            surface.widthMeters <= 0.0f ||
            surface.heightMeters <= 0.0f ||
            surface.maxViewDistanceMeters <= 0.0f ||
            surface.minimumFacingCosine < -1.0f ||
            surface.minimumFacingCosine > 1.0f ||
            surface.minimumScreenCoverage < 0.0f ||
            surface.impressionViewSeconds <= 0.0f ||
            surface.cooldownSeconds < 0.0f ||
            surface.maxImpressionsPerSession == 0U ||
            (surface.flags & knownFlags) == 0U ||
            (surface.flags & ~knownFlags) != 0U) {
            return failure(
                placementIdSeen(
                    destination,
                    surface.placementId)
                    ? IntrinsicAdMapParseError::
                          DuplicatePlacementId
                    : IntrinsicAdMapParseError::
                          InvalidSurface,
                reader.offset(),
                destination);
        }

        destination.surfaces[
            destination.surfaceCount++] =
                surface;
    }

    for (std::uint32_t i = 0U;
         i < audioEmitterCount;
         ++i) {
        IntrinsicAdMapAudioEmitter emitter{};

        if (!reader.readU64(emitter.placementId) ||
            !reader.readU64(emitter.emitterId) ||
            !reader.readBytes(
                emitter.fallbackAudioAssetPath.data(),
                emitter.fallbackAudioAssetPath.size())) {
            return failure(
                IntrinsicAdMapParseError::Truncated,
                reader.offset(),
                destination);
        }

        for (float& value : emitter.centerMeters) {
            if (!reader.readF32(value)) {
                return failure(
                    IntrinsicAdMapParseError::Truncated,
                    reader.offset(),
                    destination);
            }
        }

        if (!reader.readF32(
                emitter.minimumDistanceMeters) ||
            !reader.readF32(
                emitter.maximumDistanceMeters) ||
            !reader.readF32(emitter.maximumGain) ||
            !reader.readF32(
                emitter.impressionListenSeconds) ||
            !reader.readF32(
                emitter.cooldownSeconds) ||
            !reader.readU32(
                emitter.maxImpressionsPerSession)) {
            return failure(
                IntrinsicAdMapParseError::Truncated,
                reader.offset(),
                destination);
        }

        const bool duplicate =
            placementIdSeen(
                destination,
                emitter.placementId);

        if (emitter.placementId == 0U ||
            emitter.emitterId == 0U ||
            duplicate ||
            !pathValid(
                emitter.fallbackAudioAssetPath) ||
            !vectorFinite(emitter.centerMeters) ||
            emitter.minimumDistanceMeters < 0.0f ||
            emitter.maximumDistanceMeters <=
                emitter.minimumDistanceMeters ||
            emitter.maximumGain < 0.0f ||
            emitter.maximumGain > 1.0f ||
            emitter.impressionListenSeconds <= 0.0f ||
            emitter.cooldownSeconds < 0.0f ||
            emitter.maxImpressionsPerSession == 0U) {
            return failure(
                duplicate
                    ? IntrinsicAdMapParseError::
                          DuplicatePlacementId
                    : IntrinsicAdMapParseError::
                          InvalidAudioEmitter,
                reader.offset(),
                destination);
        }

        destination.audioEmitters[
            destination.audioEmitterCount++] =
                emitter;
    }

    if (reader.remaining() != 0U) {
        return failure(
            IntrinsicAdMapParseError::TrailingData,
            reader.offset(),
            destination);
    }

    return {
        .success = true,
        .error = IntrinsicAdMapParseError::None,
        .offset = reader.offset(),
    };
}

std::uint64_t intrinsicAdAssetId(
    std::string_view assetPath) noexcept {
    constexpr std::uint64_t kOffset =
        1469598103934665603ULL;
    constexpr std::uint64_t kPrime =
        1099511628211ULL;

    std::uint64_t hash = kOffset;
    for (const char character : assetPath) {
        hash ^=
            static_cast<std::uint8_t>(
                character);
        hash *= kPrime;
    }

    return hash == 0U ? 1U : hash;
}

AdSurfaceDefinition
makeAdSurfaceDefinition(
    const IntrinsicAdMapSurface& surface) noexcept {
    const auto path =
        intrinsicAdAssetPath(
            surface.sourceTextureAssetPath);

    return {
        .placementId = surface.placementId,
        .meshId = intrinsicAdAssetId(path),
        .materialSlot = 0U,
        .aspectRatio =
            surface.heightMeters > 0.0f
            ? surface.widthMeters /
                surface.heightMeters
            : 1.0f,
        .maxViewDistanceMeters =
            surface.maxViewDistanceMeters,
        .minimumFacingCosine =
            surface.minimumFacingCosine,
        .minimumScreenCoverage =
            surface.minimumScreenCoverage,
        .impressionViewSeconds =
            surface.impressionViewSeconds,
        .cooldownSeconds =
            surface.cooldownSeconds,
        .maxImpressionsPerSession =
            surface.maxImpressionsPerSession,
        .allowImage =
            (surface.flags &
             IntrinsicAdMapSurfaceImage) != 0U,
        .allowVideo =
            (surface.flags &
             IntrinsicAdMapSurfaceVideo) != 0U,
    };
}

AdAudioEmitterDefinition
makeAdAudioEmitterDefinition(
    const IntrinsicAdMapAudioEmitter& emitter) noexcept {
    return {
        .placementId = emitter.placementId,
        .emitterId = emitter.emitterId,
        .minimumDistanceMeters =
            emitter.minimumDistanceMeters,
        .maximumDistanceMeters =
            emitter.maximumDistanceMeters,
        .maximumGain = emitter.maximumGain,
        .impressionListenSeconds =
            emitter.impressionListenSeconds,
        .cooldownSeconds =
            emitter.cooldownSeconds,
        .maxImpressionsPerSession =
            emitter.maxImpressionsPerSession,
    };
}

std::string_view intrinsicAdAssetPath(
    const std::array<
        char,
        kIntrinsicAdAssetPathBytes>& path) noexcept {
    const auto end =
        std::find(
            path.begin(),
            path.end(),
            '\0');

    return std::string_view(
        path.data(),
        static_cast<std::size_t>(
            end - path.begin()));
}

} // namespace xziel
