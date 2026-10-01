#include "xziel/audio_scene.hpp"

#include <algorithm>
#include <cmath>

namespace xziel {

namespace {

float clamp01(float value) noexcept {
    if (!std::isfinite(value)) {
        return 0.0f;
    }
    return std::clamp(value, 0.0f, 1.0f);
}

float attenuation(float distanceMeters) noexcept {
    const float d = std::max(0.0f, distanceMeters);
    return 1.0f / (1.0f + 0.085f * d + 0.018f * d * d);
}

} // namespace

std::size_t AudioScenePlanner::plan(
    const AudioSource* sources,
    std::size_t sourceCount,
    const RenderWorkload& workload,
    AudioVoiceDecision* destination,
    std::size_t destinationCapacity) const noexcept {
    if (sources == nullptr ||
        destination == nullptr ||
        destinationCapacity == 0) {
        return 0;
    }

    const std::size_t count =
        std::min(sourceCount, destinationCapacity);
    const std::uint32_t budget =
        std::min<std::uint32_t>(
            voiceBudget(workload.quality),
            static_cast<std::uint32_t>(count));

    // Start with all sources virtualized, then select the strongest voices.
    for (std::size_t i = 0; i < count; ++i) {
        const auto& source = sources[i];
        auto& out = destination[i];

        const float occ = clamp01(source.occlusion);
        out = {};
        out.id = source.id;
        out.audible = false;
        out.virtualized = source.looping;
        out.gain =
            clamp01(source.baseGain) *
            attenuation(source.distanceMeters) *
            (1.0f - occ * 0.55f);
        out.lowPassHz =
            20000.0f - occ * 17800.0f;
        out.reverbSend =
            clamp01(source.reverbZoneSend) *
            (0.35f + 0.65f * attenuation(source.distanceMeters));
    }

    for (std::uint32_t rank = 0; rank < budget; ++rank) {
        std::size_t bestIndex = count;
        float bestScore = -1.0f;

        for (std::size_t i = 0; i < count; ++i) {
            if (destination[i].audible) {
                continue;
            }

            const float candidateScore = score(sources[i]);
            if (candidateScore > bestScore) {
                bestScore = candidateScore;
                bestIndex = i;
            }
        }

        if (bestIndex >= count || bestScore <= 0.001f) {
            break;
        }

        destination[bestIndex].audible = true;
        destination[bestIndex].virtualized = false;
        destination[bestIndex].priorityRank = rank;
    }

    return count;
}

float AudioScenePlanner::score(
    const AudioSource& source) noexcept {
    float kindBoost = 1.0f;

    switch (source.kind) {
        case AudioSourceKind::PlayerWeapon:
            kindBoost = 4.0f;
            break;
        case AudioSourceKind::HorrorStinger:
            kindBoost = 3.8f;
            break;
        case AudioSourceKind::Advertisement:
            kindBoost = 0.75f;
            break;
        case AudioSourceKind::UI:
            kindBoost = 3.4f;
            break;
        case AudioSourceKind::ZombieVoice:
            kindBoost = 2.5f;
            break;
        case AudioSourceKind::ZombieFootstep:
            kindBoost = 2.1f;
            break;
        case AudioSourceKind::Environment:
            kindBoost = 1.5f;
            break;
        case AudioSourceKind::Ambience:
            kindBoost = 1.2f;
            break;
        case AudioSourceKind::Music:
            kindBoost = 1.6f;
            break;
    }

    if (source.critical) {
        kindBoost += 4.0f;
    }

    const float occ =
        clamp01(source.occlusion);

    return std::max(0.0f, source.importance) *
        std::max(0.0f, source.baseGain) *
        attenuation(source.distanceMeters) *
        (1.0f - occ * 0.30f) *
        kindBoost;
}

std::uint32_t AudioScenePlanner::voiceBudget(
    RenderQuality quality) noexcept {
    switch (quality) {
        case RenderQuality::Low: return 24;
        case RenderQuality::Medium: return 36;
        case RenderQuality::High: return 48;
        case RenderQuality::Ultra: return 64;
    }
    return 36;
}

} // namespace xziel
