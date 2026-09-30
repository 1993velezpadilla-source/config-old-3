#pragma once

#include "xziel/acoustics.hpp"
#include "xziel/audio_scene.hpp"
#include "xziel/horde_director.hpp"
#include "xziel/horror.hpp"
#include "xziel/player_vitals.hpp"
#include "xziel/score.hpp"
#include "xziel/survival_systems.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace xziel {

struct SanctumGameplayProfile {
    PlayerVitalsConfig vitals{};
    HordeConfig horde{};
    ScoreConfig score{};
    SurvivalRules survival{};
    HorrorConfig horror{};

    // Content/UI rules are explicit so future Android presentation does not
    // quietly drift back toward objective-marker or scare-spam design.
    bool showQuestChecklistHud = false;
    bool showPassivePresenceMarkers = false;
    bool autoRevealSecrets = false;
};

[[nodiscard]] SanctumGameplayProfile
makeSanctumGameplayProfile() noexcept;

// Stable gameplay IDs. Art/presentation names may evolve without invalidating
// saved runs, authored map anchors or telemetry.
inline constexpr std::uint32_t kSanctumWeaponSidearmId = 2101U;
inline constexpr std::uint32_t kSanctumWeaponSubmachineGunId = 2102U;
inline constexpr std::uint32_t kSanctumWeaponAssaultRifleId = 2103U;
inline constexpr std::uint32_t kSanctumWeaponMarksmanRifleId = 2104U;
inline constexpr std::uint32_t kSanctumWeaponShotgunId = 2105U;
inline constexpr std::uint32_t kSanctumWeaponLightMachineGunId = 2106U;
inline constexpr std::uint32_t kSanctumWeaponSniperRifleId = 2107U;

inline constexpr std::uint32_t kSanctumPerkFortitudeId = 3101U;
inline constexpr std::uint32_t kSanctumPerkQuickHandsId = 3102U;
inline constexpr std::uint32_t kSanctumPerkEnduranceId = 3103U;
inline constexpr std::uint32_t kSanctumPerkSecondChanceId = 3104U;
inline constexpr std::uint32_t kSanctumPerkRapidFireId = 3105U;
inline constexpr std::uint32_t kSanctumPerkPrecisionId = 3106U;
inline constexpr std::uint32_t kSanctumPerkArsenalId = 3107U;
inline constexpr std::uint32_t kSanctumPerkBlastGuardId = 3108U;

inline constexpr std::uint32_t kSanctumWallWeaponStationId = 4101U;
inline constexpr std::uint32_t kSanctumRandomArsenalStationId = 4102U;
inline constexpr std::uint32_t kSanctumReliquaryStationId = 4103U;
inline constexpr std::uint32_t kSanctumWeaponUpgradeStationId = 4104U;
inline constexpr std::uint32_t kSanctumVotiveStationId = 4105U;

inline constexpr std::uint32_t kSanctumConsumableFullAmmoId = 5101U;
inline constexpr std::uint32_t kSanctumConsumableDoubleScoreId = 5102U;

struct SanctumSurvivalAnchors {
    Vec3 wallWeapon{};
    Vec3 randomArsenal{};
    Vec3 reliquary{};
    Vec3 weaponUpgrade{};
    Vec3 votive{};

    bool hasWallWeapon = false;
    bool hasRandomArsenal = false;
    bool hasReliquary = false;
    bool hasWeaponUpgrade = false;
    bool hasVotive = false;
};

// Gameplay catalog is native Xziel. Spatial placement remains authored by the
// map/Blender pipeline: only anchors explicitly supplied by the map become
// interaction stations. This prevents temporary floating machines from becoming
// shipping geometry authority.
[[nodiscard]] SurvivalContentDefinition
makeSanctumSurvivalContent(
    const SanctumSurvivalAnchors& anchors = {}) noexcept;

enum class SanctumZone : std::uint32_t {
    Unknown = 0,
    Courtyard = 1,
    Nave = 2,
    Office = 3,
    OfficeCorridor = 4,
    BoilerRoom = 5,
    TowerStairs = 6,
    RingingChamber = 7,
    ClockChamber = 8,
    RoofChamber = 9,
    TowerTop = 10,
};

enum class SanctumPresenceKind : std::uint8_t {
    Llorona = 0,
    Nun = 1,
};

enum class SanctumPassiveCue : std::uint8_t {
    LloronaDistantCry,
    LloronaBreath,
    NunPrayer,
    NunWhisper,
};

struct SanctumPoint {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct SanctumListener {
    SanctumPoint position{};
    SanctumZone zone = SanctumZone::Unknown;
};

struct SanctumPresence {
    std::uint64_t id = 0;
    SanctumPresenceKind kind = SanctumPresenceKind::Llorona;
    SanctumPoint position{};
    SanctumZone zone = SanctumZone::Unknown;
    float intensity = 0.0f;
    bool active = false;
    bool hostile = false;
};

struct SanctumPassiveCueEvent {
    std::uint64_t sourceId = 0;
    SanctumPresenceKind presence =
        SanctumPresenceKind::Llorona;
    SanctumPassiveCue cue =
        SanctumPassiveCue::LloronaDistantCry;

    float distanceMeters = 0.0f;
    float gain = 0.0f;
    float lowPassHz = 20000.0f;
    float reverbSend = 0.0f;
};

struct SanctumAtmosphereFrame {
    std::array<AudioSource, 4> passiveBeds{};
    std::size_t passiveBedCount = 0;

    std::array<SanctumPassiveCueEvent, 4> cueEvents{};
    std::size_t cueEventCount = 0;
};

class SanctumAtmosphere final {
public:
    void reset(std::uint32_t seed = 0x53A7C7U) noexcept;

    [[nodiscard]] static bool configureAcoustics(
        AcousticGraph& graph) noexcept;

    [[nodiscard]] SanctumAtmosphereFrame advance(
        float deltaSeconds,
        const SanctumListener& listener,
        const SanctumPresence* presences,
        std::size_t presenceCount,
        const AcousticGraph& acoustics) noexcept;

private:
    [[nodiscard]] float random01() noexcept;
    [[nodiscard]] float nextDelay(
        SanctumPresenceKind kind,
        bool hostile) noexcept;

    std::array<float, 2> cueCountdown_{};
    std::uint32_t randomState_ = 0x53A7C7U;
    bool initialized_ = false;
};

[[nodiscard]] const char* sanctumZoneName(
    SanctumZone zone) noexcept;

} // namespace xziel
