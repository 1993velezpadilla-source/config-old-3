#pragma once

#include <aaudio/AAudio.h>
#include <android/asset_manager.h>

#include "xziel/spsc_queue.hpp"
#include "xziel/weapon_catalog.hpp"

#include <array>
#include <atomic>
#include <cstdint>
#include <vector>

namespace xziel::android {

enum class AndroidAudioCue : std::uint8_t {
    FireSidearm,
    FireSubmachineGun,
    FireAssaultRifle,
    FireMarksmanRifle,
    FireShotgun,
    FireLightMachineGun,
    FireSniperRifle,
    Hit,
    CriticalHit,
    PlayerHit,
    ZombieAttack,
    Reload,
    UiConfirm,
    UiError,
    Door,
    BarricadeBreak,
    BarricadeRebuild,
    RoundStart,
    HorrorStinger,
    Thunder,
    Advertisement,
};

[[nodiscard]] AndroidAudioCue weaponFireCue(
    xziel::WeaponSoundFamily family) noexcept;

class AndroidAudioEngine final {
public:
    AndroidAudioEngine() = default;
    ~AndroidAudioEngine();

    AndroidAudioEngine(const AndroidAudioEngine&) = delete;
    AndroidAudioEngine& operator=(const AndroidAudioEngine&) = delete;

    [[nodiscard]] bool initialize(
        AAssetManager* assetManager) noexcept;
    void shutdown() noexcept;

    // Called from the Android/game thread. This never blocks on the audio
    // callback and drops excess one-shot cues rather than allocating.
    void play(
        AndroidAudioCue cue,
        float gain = 1.0f) noexcept;

    [[nodiscard]] bool prepareAdvertisement(
        AAssetManager* assetManager,
        const char* assetPath) noexcept;

    [[nodiscard]] bool playAdvertisement(
        float gain,
        float pan = 0.0f) noexcept;

    void updateAdvertisementSpatial(
        float gain,
        float pan,
        bool enabled = true) noexcept;

    void stopAdvertisement() noexcept;

    [[nodiscard]] bool advertisementReady() const noexcept;
    [[nodiscard]] bool advertisementPlaying() const noexcept;

    // Reopens an AAudio stream after AAUDIO_ERROR_DISCONNECTED. Call from the
    // game thread; the real-time callback never performs lifecycle work.
    void service() noexcept;

    [[nodiscard]] bool ready() const noexcept;
    [[nodiscard]] std::uint64_t droppedCueCount() const noexcept;
    [[nodiscard]] bool realWeaponSamplesReady() const noexcept;

private:
    struct Command {
        AndroidAudioCue cue = AndroidAudioCue::FireAssaultRifle;
        float gain = 1.0f;
    };

    struct Voice {
        bool active = false;
        AndroidAudioCue cue = AndroidAudioCue::FireAssaultRifle;
        float phase = 0.0f;
        float phaseIncrement = 0.0f;
        float gain = 0.0f;
        float ageSeconds = 0.0f;
        float durationSeconds = 0.0f;
        float samplePosition = 0.0f;
        float playbackRate = 1.0f;
        std::uint32_t noiseState = 1U;
        bool sampled = false;
        bool spatialAdvertisement = false;
    };

    struct SampleBuffer {
        std::vector<float> mono{};
        std::uint32_t sampleRate = 0U;
    };

    [[nodiscard]] bool loadPcm16Wav(
        AAssetManager* assetManager,
        const char* assetPath,
        SampleBuffer& out) noexcept;
    [[nodiscard]] const SampleBuffer* sampleFor(
        AndroidAudioCue cue) const noexcept;

    [[nodiscard]] bool openStream() noexcept;
    void startVoice(const Command& command) noexcept;
    [[nodiscard]] float renderVoice(
        Voice& voice,
        float sampleRate) noexcept;

    static aaudio_data_callback_result_t dataCallback(
        AAudioStream* stream,
        void* userData,
        void* audioData,
        std::int32_t numFrames) noexcept;

    static void errorCallback(
        AAudioStream* stream,
        void* userData,
        aaudio_result_t error) noexcept;

    aaudio_data_callback_result_t render(
        float* output,
        std::int32_t numFrames) noexcept;

    xziel::SpscQueue<Command, 64> commands_{};
    std::array<Voice, 24> voices_{};
    SampleBuffer fireSample_{};
    SampleBuffer reloadSample_{};
    SampleBuffer advertisementSample_{};

    AAudioStream* stream_ = nullptr;
    float sampleRate_ = 48000.0f;

    std::atomic<bool> disconnected_{false};
    std::atomic<bool> ready_{false};
    std::atomic<bool> advertisementEnabled_{false};
    std::atomic<bool> advertisementInFlight_{false};
    std::atomic<float> advertisementGain_{0.0f};
    std::atomic<float> advertisementPan_{0.0f};
    std::atomic<std::uint64_t> dropped_{0};
    std::uint32_t voiceSequence_ = 0U;
};

} // namespace xziel::android
