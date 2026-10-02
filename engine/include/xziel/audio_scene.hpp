#pragma once

#include "xziel/environment.hpp"
#include "xziel/performance.hpp"

#include <cstddef>
#include <cstdint>

namespace xziel {

enum class AudioSourceKind : std::uint8_t {
    PlayerWeapon,
    ZombieVoice,
    ZombieFootstep,
    Environment,
    Ambience,
    Music,
    HorrorStinger,
    Advertisement,
    UI,
};

struct AudioSource {
    std::uint64_t id = 0;
    AudioSourceKind kind = AudioSourceKind::Environment;

    float distanceMeters = 0.0f;
    float baseGain = 1.0f;
    float importance = 1.0f;
    float occlusion = 0.0f;
    float reverbZoneSend = 0.0f;

    bool looping = false;
    bool critical = false;
};

struct AudioVoiceDecision {
    std::uint64_t id = 0;
    bool audible = false;
    bool virtualized = false;

    float gain = 0.0f;
    float lowPassHz = 20000.0f;
    float reverbSend = 0.0f;

    std::uint32_t priorityRank = 0;
};

class AudioScenePlanner final {
public:
    [[nodiscard]] std::size_t plan(
        const AudioSource* sources,
        std::size_t sourceCount,
        const RenderWorkload& workload,
        AudioVoiceDecision* destination,
        std::size_t destinationCapacity) const noexcept;

private:
    [[nodiscard]] static float score(
        const AudioSource& source) noexcept;

    [[nodiscard]] static std::uint32_t voiceBudget(
        RenderQuality quality) noexcept;
};

} // namespace xziel
