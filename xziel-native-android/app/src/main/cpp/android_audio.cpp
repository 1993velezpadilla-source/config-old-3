#include "android_audio.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <utility>
#include <vector>

namespace xziel::android {

namespace {

constexpr float kPi =
    3.14159265358979323846f;

struct CueProfile {
    float frequency = 220.0f;
    float duration = 0.10f;
    float toneMix = 0.7f;
    float noiseMix = 0.3f;
    float pitchFall = 0.0f;
};

struct FireCueProfile {
    float playbackRate = 1.0f;
    float sampleMix = 0.80f;
    float toneMix = 0.18f;
    float noiseMix = 0.055f;
    float bodySeconds = 0.095f;
    float crackSeconds = 0.018f;
    float transientFrequency = 82.0f;
};

bool isWeaponFireCue(
    AndroidAudioCue cue) noexcept {
    switch (cue) {
        case AndroidAudioCue::FireSidearm:
        case AndroidAudioCue::FireSubmachineGun:
        case AndroidAudioCue::FireAssaultRifle:
        case AndroidAudioCue::FireMarksmanRifle:
        case AndroidAudioCue::FireShotgun:
        case AndroidAudioCue::FireLightMachineGun:
        case AndroidAudioCue::FireSniperRifle:
            return true;
        default:
            return false;
    }
}

FireCueProfile fireProfileFor(
    AndroidAudioCue cue) noexcept {
    switch (cue) {
        case AndroidAudioCue::FireSidearm:
            return {1.16f, 0.66f, 0.10f, 0.095f, 0.055f, 0.012f, 152.0f};
        case AndroidAudioCue::FireSubmachineGun:
            return {1.08f, 0.72f, 0.12f, 0.075f, 0.065f, 0.014f, 126.0f};
        case AndroidAudioCue::FireAssaultRifle:
            return {1.00f, 0.80f, 0.18f, 0.055f, 0.095f, 0.018f, 82.0f};
        case AndroidAudioCue::FireMarksmanRifle:
            return {0.95f, 0.84f, 0.20f, 0.062f, 0.120f, 0.020f, 72.0f};
        case AndroidAudioCue::FireShotgun:
            return {0.86f, 0.90f, 0.28f, 0.120f, 0.160f, 0.028f, 58.0f};
        case AndroidAudioCue::FireLightMachineGun:
            return {0.92f, 0.88f, 0.24f, 0.065f, 0.130f, 0.022f, 64.0f};
        case AndroidAudioCue::FireSniperRifle:
            return {0.82f, 0.92f, 0.32f, 0.100f, 0.180f, 0.030f, 52.0f};
        default:
            return {};
    }
}

CueProfile profileFor(
    AndroidAudioCue cue) noexcept {
    switch (cue) {
        case AndroidAudioCue::FireSidearm:
            return {260.0f, 0.055f, 0.48f, 0.70f, 0.58f};
        case AndroidAudioCue::FireSubmachineGun:
            return {190.0f, 0.065f, 0.42f, 0.78f, 0.64f};
        case AndroidAudioCue::FireAssaultRifle:
            return {118.0f, 0.075f, 0.36f, 0.88f, 0.72f};
        case AndroidAudioCue::FireMarksmanRifle:
            return {92.0f, 0.105f, 0.34f, 0.86f, 0.76f};
        case AndroidAudioCue::FireShotgun:
            return {62.0f, 0.155f, 0.24f, 0.96f, 0.80f};
        case AndroidAudioCue::FireLightMachineGun:
            return {74.0f, 0.125f, 0.30f, 0.90f, 0.78f};
        case AndroidAudioCue::FireSniperRifle:
            return {48.0f, 0.180f, 0.20f, 0.98f, 0.84f};
        case AndroidAudioCue::Hit:
            return {760.0f, 0.055f, 0.92f, 0.08f, 0.18f};
        case AndroidAudioCue::CriticalHit:
            return {1180.0f, 0.085f, 0.92f, 0.12f, 0.24f};
        case AndroidAudioCue::PlayerHit:
            return {92.0f, 0.16f, 0.28f, 0.82f, 0.42f};
        case AndroidAudioCue::ZombieAttack:
            return {74.0f, 0.24f, 0.56f, 0.58f, 0.30f};
        case AndroidAudioCue::Reload:
            return {430.0f, 0.075f, 0.62f, 0.50f, 0.08f};
        case AndroidAudioCue::UiConfirm:
            return {660.0f, 0.075f, 0.94f, 0.02f, 0.0f};
        case AndroidAudioCue::UiError:
            return {170.0f, 0.14f, 0.88f, 0.05f, 0.22f};
        case AndroidAudioCue::Door:
            return {82.0f, 0.26f, 0.32f, 0.76f, 0.34f};
        case AndroidAudioCue::BarricadeBreak:
            return {145.0f, 0.12f, 0.22f, 0.92f, 0.24f};
        case AndroidAudioCue::BarricadeRebuild:
            return {260.0f, 0.10f, 0.45f, 0.68f, 0.08f};
        case AndroidAudioCue::RoundStart:
            return {196.0f, 0.42f, 0.90f, 0.10f, -0.18f};
        case AndroidAudioCue::HorrorStinger:
            return {56.0f, 0.58f, 0.72f, 0.48f, 0.48f};
        case AndroidAudioCue::Thunder:
            return {48.0f, 0.70f, 0.20f, 0.96f, 0.55f};
        case AndroidAudioCue::Advertisement:
            return {220.0f, 0.01f, 0.0f, 0.0f, 0.0f};
    }

    return {};
}

float clampSample(float value) noexcept {
    return std::clamp(value, -0.95f, 0.95f);
}

} // namespace

AndroidAudioCue weaponFireCue(
    xziel::WeaponSoundFamily family) noexcept {
    switch (family) {
        case xziel::WeaponSoundFamily::Sidearm:
            return AndroidAudioCue::FireSidearm;
        case xziel::WeaponSoundFamily::SubmachineGun:
            return AndroidAudioCue::FireSubmachineGun;
        case xziel::WeaponSoundFamily::AssaultRifle:
            return AndroidAudioCue::FireAssaultRifle;
        case xziel::WeaponSoundFamily::MarksmanRifle:
            return AndroidAudioCue::FireMarksmanRifle;
        case xziel::WeaponSoundFamily::Shotgun:
            return AndroidAudioCue::FireShotgun;
        case xziel::WeaponSoundFamily::LightMachineGun:
            return AndroidAudioCue::FireLightMachineGun;
        case xziel::WeaponSoundFamily::SniperRifle:
            return AndroidAudioCue::FireSniperRifle;
    }
    return AndroidAudioCue::FireAssaultRifle;
}

AndroidAudioEngine::~AndroidAudioEngine() {
    shutdown();
}

bool AndroidAudioEngine::initialize(
    AAssetManager* assetManager) noexcept {
    shutdown();

    fireSample_ = {};
    reloadSample_ = {};
    advertisementSample_ = {};
    advertisementEnabled_.store(false, std::memory_order_release);
    advertisementInFlight_.store(false, std::memory_order_release);
    advertisementGain_.store(0.0f, std::memory_order_release);
    advertisementPan_.store(0.0f, std::memory_order_release);

    if (assetManager != nullptr) {
        (void) loadPcm16Wav(
            assetManager,
            "audio/xziel/weapons/standard_rifle_fire.wav",
            fireSample_);

        (void) loadPcm16Wav(
            assetManager,
            "audio/xziel/weapons/standard_rifle_reload.wav",
            reloadSample_);
    }

    voiceSequence_ = 0U;
    disconnected_.store(false, std::memory_order_release);
    return openStream();
}

void AndroidAudioEngine::shutdown() noexcept {
    ready_.store(false, std::memory_order_release);
    advertisementEnabled_.store(false, std::memory_order_release);
    advertisementInFlight_.store(false, std::memory_order_release);

    if (stream_ != nullptr) {
        (void) AAudioStream_requestStop(stream_);
        (void) AAudioStream_close(stream_);
        stream_ = nullptr;
    }

    for (auto& voice : voices_) {
        voice = {};
    }
}

void AndroidAudioEngine::play(
    AndroidAudioCue cue,
    float gain) noexcept {
    Command command{
        .cue = cue,
        .gain = std::clamp(
            std::isfinite(gain) ? gain : 1.0f,
            0.0f,
            1.5f),
    };

    if (!commands_.tryPush(command)) {
        dropped_.fetch_add(1U, std::memory_order_relaxed);
    }
}

bool AndroidAudioEngine::prepareAdvertisement(
    AAssetManager* assetManager,
    const char* assetPath) noexcept {
    if (advertisementInFlight_.load(
            std::memory_order_acquire)) {
        return false;
    }

    SampleBuffer candidate{};
    if (!loadPcm16Wav(
            assetManager,
            assetPath,
            candidate) ||
        candidate.mono.empty() ||
        candidate.sampleRate == 0U) {
        return false;
    }

    advertisementSample_ =
        std::move(candidate);
    return true;
}

bool AndroidAudioEngine::playAdvertisement(
    float gain,
    float pan) noexcept {
    if (!ready() ||
        advertisementSample_.mono.empty() ||
        advertisementSample_.sampleRate == 0U ||
        advertisementInFlight_.exchange(
            true,
            std::memory_order_acq_rel)) {
        return false;
    }

    advertisementGain_.store(
        std::clamp(
            std::isfinite(gain) ? gain : 0.0f,
            0.0f,
            1.0f),
        std::memory_order_release);
    advertisementPan_.store(
        std::clamp(
            std::isfinite(pan) ? pan : 0.0f,
            -1.0f,
            1.0f),
        std::memory_order_release);
    advertisementEnabled_.store(
        true,
        std::memory_order_release);

    Command command{
        .cue = AndroidAudioCue::Advertisement,
        .gain = 1.0f,
    };

    if (!commands_.tryPush(command)) {
        advertisementEnabled_.store(
            false,
            std::memory_order_release);
        advertisementInFlight_.store(
            false,
            std::memory_order_release);
        dropped_.fetch_add(
            1U,
            std::memory_order_relaxed);
        return false;
    }

    return true;
}

void AndroidAudioEngine::updateAdvertisementSpatial(
    float gain,
    float pan,
    bool enabled) noexcept {
    advertisementGain_.store(
        std::clamp(
            std::isfinite(gain) ? gain : 0.0f,
            0.0f,
            1.0f),
        std::memory_order_release);
    advertisementPan_.store(
        std::clamp(
            std::isfinite(pan) ? pan : 0.0f,
            -1.0f,
            1.0f),
        std::memory_order_release);
    advertisementEnabled_.store(
        enabled,
        std::memory_order_release);
}

void AndroidAudioEngine::stopAdvertisement() noexcept {
    advertisementEnabled_.store(
        false,
        std::memory_order_release);
}

bool AndroidAudioEngine::advertisementReady() const noexcept {
    return !advertisementSample_.mono.empty() &&
        advertisementSample_.sampleRate > 0U;
}

bool AndroidAudioEngine::advertisementPlaying() const noexcept {
    return advertisementInFlight_.load(
        std::memory_order_acquire);
}

void AndroidAudioEngine::service() noexcept {
    if (!disconnected_.exchange(
            false,
            std::memory_order_acq_rel)) {
        return;
    }

    shutdown();
    (void) openStream();
}

bool AndroidAudioEngine::ready() const noexcept {
    return ready_.load(std::memory_order_acquire);
}

std::uint64_t AndroidAudioEngine::droppedCueCount() const noexcept {
    return dropped_.load(std::memory_order_relaxed);
}

bool AndroidAudioEngine::realWeaponSamplesReady() const noexcept {
    return !fireSample_.mono.empty() &&
        !reloadSample_.mono.empty();
}

bool AndroidAudioEngine::loadPcm16Wav(
    AAssetManager* assetManager,
    const char* assetPath,
    SampleBuffer& out) noexcept {
    out = {};

    if (assetManager == nullptr ||
        assetPath == nullptr) {
        return false;
    }

    AAsset* asset =
        AAssetManager_open(
            assetManager,
            assetPath,
            AASSET_MODE_STREAMING);

    if (asset == nullptr) {
        return false;
    }

    const off_t length =
        AAsset_getLength(asset);

    if (length < 44 ||
        length > 16 * 1024 * 1024) {
        AAsset_close(asset);
        return false;
    }

    std::vector<std::uint8_t> bytes;
    try {
        bytes.resize(
            static_cast<std::size_t>(length));
    } catch (...) {
        AAsset_close(asset);
        return false;
    }

    const int read =
        AAsset_read(
            asset,
            bytes.data(),
            bytes.size());

    AAsset_close(asset);

    if (read != length ||
        std::memcmp(bytes.data(), "RIFF", 4) != 0 ||
        std::memcmp(bytes.data() + 8, "WAVE", 4) != 0) {
        return false;
    }

    const auto u16 = [&](std::size_t offset) noexcept {
        return static_cast<std::uint16_t>(
            static_cast<std::uint16_t>(bytes[offset]) |
            (static_cast<std::uint16_t>(bytes[offset + 1]) << 8U));
    };

    const auto u32 = [&](std::size_t offset) noexcept {
        return
            static_cast<std::uint32_t>(bytes[offset]) |
            (static_cast<std::uint32_t>(bytes[offset + 1]) << 8U) |
            (static_cast<std::uint32_t>(bytes[offset + 2]) << 16U) |
            (static_cast<std::uint32_t>(bytes[offset + 3]) << 24U);
    };

    std::uint16_t format = 0U;
    std::uint16_t channels = 0U;
    std::uint16_t bits = 0U;
    std::uint16_t blockAlign = 0U;
    std::uint32_t rate = 0U;
    std::size_t dataOffset = 0U;
    std::size_t dataBytes = 0U;

    std::size_t cursor = 12U;
    while (cursor + 8U <= bytes.size()) {
        const std::uint32_t chunkSize =
            u32(cursor + 4U);
        const std::size_t payload =
            cursor + 8U;

        if (payload > bytes.size() ||
            static_cast<std::size_t>(chunkSize) >
                bytes.size() - payload) {
            return false;
        }

        if (std::memcmp(
                bytes.data() + cursor,
                "fmt ",
                4) == 0 &&
            chunkSize >= 16U) {
            format = u16(payload);
            channels = u16(payload + 2U);
            rate = u32(payload + 4U);
            blockAlign = u16(payload + 12U);
            bits = u16(payload + 14U);
        } else if (std::memcmp(
                       bytes.data() + cursor,
                       "data",
                       4) == 0) {
            dataOffset = payload;
            dataBytes = chunkSize;
        }

        cursor =
            payload +
            static_cast<std::size_t>(chunkSize) +
            (chunkSize & 1U);
    }

    if (format != 1U ||
        (channels != 1U && channels != 2U) ||
        bits != 16U ||
        rate < 8000U ||
        rate > 192000U ||
        blockAlign != channels * 2U ||
        dataOffset == 0U ||
        dataBytes < blockAlign) {
        return false;
    }

    const std::size_t frames =
        dataBytes /
        blockAlign;

    try {
        out.mono.resize(frames);
    } catch (...) {
        out = {};
        return false;
    }

    for (std::size_t frame = 0U;
         frame < frames;
         ++frame) {
        float mixed = 0.0f;

        for (std::uint16_t channel = 0U;
             channel < channels;
             ++channel) {
            const std::size_t offset =
                dataOffset +
                frame * blockAlign +
                static_cast<std::size_t>(channel) * 2U;

            const auto raw =
                static_cast<std::uint16_t>(
                    static_cast<std::uint16_t>(bytes[offset]) |
                    (static_cast<std::uint16_t>(bytes[offset + 1U]) << 8U));

            const auto signedSample =
                static_cast<std::int16_t>(raw);

            mixed +=
                static_cast<float>(signedSample) /
                32768.0f;
        }

        out.mono[frame] =
            mixed /
            static_cast<float>(channels);
    }

    out.sampleRate = rate;
    return true;
}

const AndroidAudioEngine::SampleBuffer*
AndroidAudioEngine::sampleFor(
    AndroidAudioCue cue) const noexcept {
    switch (cue) {
        case AndroidAudioCue::FireSidearm:
        case AndroidAudioCue::FireSubmachineGun:
        case AndroidAudioCue::FireAssaultRifle:
        case AndroidAudioCue::FireMarksmanRifle:
        case AndroidAudioCue::FireShotgun:
        case AndroidAudioCue::FireLightMachineGun:
        case AndroidAudioCue::FireSniperRifle:
            return fireSample_.mono.empty()
                ? nullptr
                : &fireSample_;
        case AndroidAudioCue::Reload:
            return reloadSample_.mono.empty()
                ? nullptr
                : &reloadSample_;
        case AndroidAudioCue::Advertisement:
            return advertisementSample_.mono.empty()
                ? nullptr
                : &advertisementSample_;
        default:
            return nullptr;
    }
}

bool AndroidAudioEngine::openStream() noexcept {
    AAudioStreamBuilder* builder = nullptr;

    if (AAudio_createStreamBuilder(&builder) != AAUDIO_OK ||
        builder == nullptr) {
        return false;
    }

    AAudioStreamBuilder_setDirection(
        builder,
        AAUDIO_DIRECTION_OUTPUT);
    AAudioStreamBuilder_setFormat(
        builder,
        AAUDIO_FORMAT_PCM_FLOAT);
    AAudioStreamBuilder_setChannelCount(
        builder,
        2);
    AAudioStreamBuilder_setPerformanceMode(
        builder,
        AAUDIO_PERFORMANCE_MODE_LOW_LATENCY);
    AAudioStreamBuilder_setSharingMode(
        builder,
        AAUDIO_SHARING_MODE_SHARED);
    AAudioStreamBuilder_setUsage(
        builder,
        AAUDIO_USAGE_GAME);
    AAudioStreamBuilder_setContentType(
        builder,
        AAUDIO_CONTENT_TYPE_SONIFICATION);
    AAudioStreamBuilder_setDataCallback(
        builder,
        &AndroidAudioEngine::dataCallback,
        this);
    AAudioStreamBuilder_setErrorCallback(
        builder,
        &AndroidAudioEngine::errorCallback,
        this);

    const aaudio_result_t openResult =
        AAudioStreamBuilder_openStream(
            builder,
            &stream_);

    AAudioStreamBuilder_delete(
        builder);

    if (openResult != AAUDIO_OK ||
        stream_ == nullptr) {
        stream_ = nullptr;
        return false;
    }

    const std::int32_t rate =
        AAudioStream_getSampleRate(
            stream_);

    sampleRate_ =
        rate > 8000
        ? static_cast<float>(rate)
        : 48000.0f;

    const aaudio_result_t startResult =
        AAudioStream_requestStart(
            stream_);

    if (startResult != AAUDIO_OK) {
        (void) AAudioStream_close(stream_);
        stream_ = nullptr;
        return false;
    }

    ready_.store(true, std::memory_order_release);
    return true;
}

void AndroidAudioEngine::startVoice(
    const Command& command) noexcept {
    Voice* slot = nullptr;

    for (auto& voice : voices_) {
        if (!voice.active) {
            slot = &voice;
            break;
        }
    }

    if (slot == nullptr) {
        // Deterministic voice stealing: replace the voice closest to its end.
        slot = &voices_[0];
        float oldestRatio = -1.0f;

        for (auto& voice : voices_) {
            const float ratio =
                voice.durationSeconds > 0.0f
                ? voice.ageSeconds / voice.durationSeconds
                : 1.0f;

            if (ratio > oldestRatio) {
                oldestRatio = ratio;
                slot = &voice;
            }
        }
    }

    const CueProfile profile =
        profileFor(command.cue);

    if (slot->active &&
        slot->spatialAdvertisement) {
        advertisementEnabled_.store(
            false,
            std::memory_order_release);
        advertisementInFlight_.store(
            false,
            std::memory_order_release);
    }

    *slot = {};
    slot->active = true;
    slot->cue = command.cue;
    slot->gain = command.gain;
    slot->spatialAdvertisement =
        command.cue == AndroidAudioCue::Advertisement;

    if (const auto* sample =
            sampleFor(command.cue);
        sample != nullptr &&
        !sample->mono.empty() &&
        sample->sampleRate > 0U) {
        slot->sampled = true;
        slot->samplePosition = 0.0f;

        const std::uint32_t sequence =
            voiceSequence_++;

        if (isWeaponFireCue(
                command.cue)) {
            constexpr std::array<float, 5> kShotRates{
                0.972f,
                0.988f,
                1.000f,
                1.014f,
                1.028f,
            };

            const FireCueProfile fire =
                fireProfileFor(
                    command.cue);

            slot->playbackRate =
                fire.playbackRate *
                kShotRates[
                    sequence %
                    kShotRates.size()];

            slot->phaseIncrement =
                2.0f * kPi *
                (fire.transientFrequency +
                 static_cast<float>(
                     sequence % 4U) *
                     5.0f) /
                std::max(sampleRate_, 8000.0f);

            slot->noiseState =
                0xA511E9B3U ^
                sequence *
                    0x9E3779B9U ^
                static_cast<std::uint32_t>(
                    command.cue) *
                    0x85EBCA6BU;
        }

        slot->durationSeconds =
            static_cast<float>(
                sample->mono.size()) /
            static_cast<float>(
                sample->sampleRate) /
            std::max(
                slot->playbackRate,
                0.25f);
        return;
    }

    slot->durationSeconds =
        std::max(profile.duration, 0.01f);
    slot->phaseIncrement =
        2.0f * kPi *
        profile.frequency /
        std::max(sampleRate_, 8000.0f);
    slot->noiseState =
        0x9E3779B9U ^
        (static_cast<std::uint32_t>(
             command.cue) + 1U) *
            0x85EBCA6BU;
}

float AndroidAudioEngine::renderVoice(
    Voice& voice,
    float sampleRate) noexcept {
    if (!voice.active) {
        return 0.0f;
    }

    if (voice.sampled) {
        if (voice.spatialAdvertisement &&
            !advertisementEnabled_.load(
                std::memory_order_acquire)) {
            voice.active = false;
            advertisementInFlight_.store(
                false,
                std::memory_order_release);
            return 0.0f;
        }

        const auto* sample =
            sampleFor(voice.cue);

        if (sample == nullptr ||
            sample->mono.empty() ||
            sample->sampleRate == 0U) {
            voice.active = false;
            if (voice.spatialAdvertisement) {
                advertisementEnabled_.store(
                    false,
                    std::memory_order_release);
                advertisementInFlight_.store(
                    false,
                    std::memory_order_release);
            }
            return 0.0f;
        }

        const std::size_t index =
            static_cast<std::size_t>(
                std::max(
                    voice.samplePosition,
                    0.0f));

        if (index >= sample->mono.size()) {
            voice.active = false;
            return 0.0f;
        }

        const std::size_t next =
            std::min(
                index + 1U,
                sample->mono.size() - 1U);

        const float fraction =
            std::clamp(
                voice.samplePosition -
                    static_cast<float>(index),
                0.0f,
                1.0f);

        const float value =
            sample->mono[index] +
            (sample->mono[next] -
             sample->mono[index]) *
                fraction;

        const float outputRate =
            std::max(
                sampleRate,
                8000.0f);

        voice.samplePosition +=
            static_cast<float>(
                sample->sampleRate) /
            outputRate *
            std::max(
                voice.playbackRate,
                0.25f);

        voice.ageSeconds +=
            1.0f /
            outputRate;

        float transient = 0.0f;

        FireCueProfile fire{};
        const bool weaponFire =
            isWeaponFireCue(
                voice.cue);

        if (weaponFire) {
            fire =
                fireProfileFor(
                    voice.cue);

            const float bodyEnvelope =
                std::max(
                    0.0f,
                    1.0f -
                        voice.ageSeconds /
                        std::max(
                            fire.bodySeconds,
                            0.001f));

            const float crackEnvelope =
                std::max(
                    0.0f,
                    1.0f -
                        voice.ageSeconds /
                        std::max(
                            fire.crackSeconds,
                            0.001f));

            voice.noiseState =
                voice.noiseState *
                    1664525U +
                1013904223U;

            const float noise =
                static_cast<float>(
                    static_cast<std::int32_t>(
                        voice.noiseState >> 9U) -
                    4194304) /
                4194304.0f;

            transient =
                std::sin(
                    voice.phase) *
                    fire.toneMix *
                    bodyEnvelope +
                noise *
                    fire.noiseMix *
                    crackEnvelope;

            voice.phase +=
                voice.phaseIncrement;

            if (voice.phase >
                2.0f * kPi) {
                voice.phase -=
                    2.0f * kPi;
            }
        }

        if (voice.samplePosition >=
            static_cast<float>(
                sample->mono.size())) {
            voice.active = false;
            if (voice.spatialAdvertisement) {
                advertisementEnabled_.store(
                    false,
                    std::memory_order_release);
                advertisementInFlight_.store(
                    false,
                    std::memory_order_release);
            }
        }

        const float liveGain =
            voice.spatialAdvertisement
            ? advertisementGain_.load(
                  std::memory_order_acquire)
            : voice.gain;

        return (
            value *
                (weaponFire
                    ? fire.sampleMix
                    : 0.80f) +
            transient) *
            liveGain;
    }

    const CueProfile profile =
        profileFor(voice.cue);

    const float progress =
        std::clamp(
            voice.ageSeconds /
                std::max(
                    voice.durationSeconds,
                    0.001f),
            0.0f,
            1.0f);

    const float envelope =
        (1.0f - progress) *
        std::min(
            voice.ageSeconds * 220.0f,
            1.0f);

    voice.noiseState =
        voice.noiseState *
            1664525U +
        1013904223U;

    const float noise =
        static_cast<float>(
            static_cast<std::int32_t>(
                voice.noiseState >> 9U) -
            4194304) /
        4194304.0f;

    const float tone =
        std::sin(
            voice.phase);

    const float pitchMultiplier =
        std::max(
            0.12f,
            1.0f -
                profile.pitchFall *
                    progress);

    voice.phase +=
        voice.phaseIncrement *
        pitchMultiplier;

    if (voice.phase > 2.0f * kPi) {
        voice.phase -= 2.0f * kPi;
    }

    voice.ageSeconds +=
        1.0f /
        std::max(
            sampleRate,
            8000.0f);

    if (voice.ageSeconds >=
        voice.durationSeconds) {
        voice.active = false;
    }

    return (
        tone * profile.toneMix +
        noise * profile.noiseMix) *
        envelope *
        voice.gain *
        0.34f;
}

aaudio_data_callback_result_t
AndroidAudioEngine::dataCallback(
    AAudioStream*,
    void* userData,
    void* audioData,
    std::int32_t numFrames) noexcept {
    auto* engine =
        static_cast<AndroidAudioEngine*>(
            userData);

    if (engine == nullptr ||
        audioData == nullptr ||
        numFrames <= 0) {
        return AAUDIO_CALLBACK_RESULT_CONTINUE;
    }

    return engine->render(
        static_cast<float*>(
            audioData),
        numFrames);
}

void AndroidAudioEngine::errorCallback(
    AAudioStream*,
    void* userData,
    aaudio_result_t error) noexcept {
    auto* engine =
        static_cast<AndroidAudioEngine*>(
            userData);

    if (engine == nullptr) {
        return;
    }

    if (error == AAUDIO_ERROR_DISCONNECTED) {
        engine->ready_.store(
            false,
            std::memory_order_release);
        engine->disconnected_.store(
            true,
            std::memory_order_release);
    }
}

aaudio_data_callback_result_t
AndroidAudioEngine::render(
    float* output,
    std::int32_t numFrames) noexcept {
    Command command{};

    while (commands_.tryPop(command)) {
        startVoice(command);
    }

    for (std::int32_t frame = 0;
         frame < numFrames;
         ++frame) {
        float mixedLeft = 0.0f;
        float mixedRight = 0.0f;

        for (auto& voice : voices_) {
            const float value =
                renderVoice(
                    voice,
                    sampleRate_);

            if (voice.spatialAdvertisement) {
                const float pan =
                    advertisementPan_.load(
                        std::memory_order_acquire);
                const float leftScale =
                    pan > 0.0f
                    ? 1.0f - pan
                    : 1.0f;
                const float rightScale =
                    pan < 0.0f
                    ? 1.0f + pan
                    : 1.0f;

                mixedLeft += value * leftScale;
                mixedRight += value * rightScale;
            } else {
                mixedLeft += value;
                mixedRight += value;
            }
        }

        output[frame * 2] =
            clampSample(mixedLeft);
        output[frame * 2 + 1] =
            clampSample(mixedRight);
    }

    return AAUDIO_CALLBACK_RESULT_CONTINUE;
}

} // namespace xziel::android
