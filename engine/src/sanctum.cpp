#include "xziel/sanctum.hpp"

#include <algorithm>
#include <cmath>

namespace xziel {

SanctumGameplayProfile
makeSanctumGameplayProfile() noexcept {
    SanctumGameplayProfile profile{};

    // Early-game danger: two default 34-damage zombie hits can down an
    // unupgraded player. Regeneration still exists, but only after a real
    // escape window; later upgrades may deliberately change this contract.
    profile.vitals.maxHealth = 68.0f;
    profile.vitals.regenerationDelaySeconds = 5.0f;
    profile.vitals.regenerationPerSecond = 24.0f;
    profile.vitals.respawnDelaySeconds = 3.0f;
    profile.vitals.respawnInvulnerabilitySeconds = 0.75f;
    profile.vitals.autoRespawn = false;

    // Rounds should breathe. A longer inter-round gap restores the
    // silence -> anticipation -> chaos -> relief rhythm instead of making the
    // director feel like a continuous objective arena.
    profile.horde.startingRound = 1U;
    profile.horde.baseZombiesPerRound = 5U;
    profile.horde.zombiesAddedPerRound = 2U;
    profile.horde.maxActive = 10U;
    profile.horde.spawnIntervalSeconds = 0.88f;
    profile.horde.interRoundDelaySeconds = 5.5f;
    profile.horde.baseHealth = 100.0f;
    profile.horde.healthAddedPerRound = 18.0f;
    profile.horde.baseMoveSpeed = 0.68f;
    profile.horde.moveSpeedAddedPerRound = 0.035f;
    profile.horde.maximumMoveSpeed = 1.45f;

    // Start poor enough that wall buys/doors matter immediately.
    profile.score.startingPoints = 500U;
    profile.score.limbHitPoints = 5U;
    profile.score.torsoHitPoints = 10U;
    profile.score.headHitPoints = 20U;
    profile.score.killPoints = 60U;
    profile.score.headshotKillBonus = 40U;
    profile.score.roundClearBasePoints = 100U;
    profile.score.roundClearPerRound = 15U;

    // Shared survival-economy rules: recognizable risk/reward pacing, but
    // content, presentation and naming remain original to Xziel/Sanctum.
    profile.survival.perkLimit = 4U;
    profile.survival.randomWeaponBaseCost = 950U;
    profile.survival.weaponUpgradeBaseCost = 5000U;
    profile.survival.weaponUpgradeCostMultiplier = 2.0f;
    profile.survival.consumableDrawCostStep = 500U;
    profile.survival.maxWeaponUpgradeTier = 3U;
    profile.survival.powerUpLifetimeSeconds = 12.0f;
    profile.survival.timedPowerUpSeconds = 30.0f;
    profile.survival.dropBaseChance = 0.035f;
    profile.survival.dropPityKills = 28U;
    profile.survival.dropCooldownSeconds = 8.0f;

    // Horror supports gameplay tension rather than shouting over it.
    profile.horror.tensionAttackPerSecond = 1.05f;
    profile.horror.tensionReleasePerSecond = 0.24f;
    profile.horror.adrenalineAttackPerSecond = 1.90f;
    profile.horror.adrenalineReleasePerSecond = 0.62f;
    profile.horror.stingerThreshold = 0.82f;
    profile.horror.stingerCooldownSeconds = 18.0f;
    profile.horror.minimumScareGapSeconds = 8.0f;
    profile.horror.maxVignette = 0.20f;
    profile.horror.maxExposureDropEv = 0.34f;
    profile.horror.maxCameraBreathing = 0.10f;
    profile.horror.maxLightFlicker = 0.14f;
    profile.horror.maxFogBoost = 0.16f;
    profile.horror.maxFlickerHz = 2.2f;

    profile.showQuestChecklistHud = false;
    profile.showPassivePresenceMarkers = false;
    profile.autoRevealSecrets = false;

    return profile;
}

SurvivalContentDefinition
makeSanctumSurvivalContent(
    const SanctumSurvivalAnchors& anchors) noexcept {
    SurvivalContentDefinition content{};
    content.rules =
        makeSanctumGameplayProfile().survival;

    content.perks[0] = {
        .id = kSanctumPerkFortitudeId,
        .effect = SurvivalPerkEffect::Fortitude,
        .cost = 2500U,
        .magnitude = 1.5f,
    };
    content.perks[1] = {
        .id = kSanctumPerkQuickHandsId,
        .effect = SurvivalPerkEffect::QuickHands,
        .cost = 3000U,
        .magnitude = 0.72f,
    };
    content.perks[2] = {
        .id = kSanctumPerkEnduranceId,
        .effect = SurvivalPerkEffect::Endurance,
        .cost = 2000U,
        .magnitude = 1.12f,
    };
    content.perks[3] = {
        .id = kSanctumPerkSecondChanceId,
        .effect = SurvivalPerkEffect::SecondChance,
        .cost = 1500U,
        .magnitude = 0.70f,
    };
    content.perks[4] = {
        .id = kSanctumPerkRapidFireId,
        .effect = SurvivalPerkEffect::RapidFire,
        .cost = 3000U,
        .magnitude = 0.86f,
    };
    content.perks[5] = {
        .id = kSanctumPerkPrecisionId,
        .effect = SurvivalPerkEffect::Precision,
        .cost = 2500U,
        .magnitude = 1.35f,
    };
    content.perks[6] = {
        .id = kSanctumPerkArsenalId,
        .effect = SurvivalPerkEffect::Arsenal,
        .cost = 3500U,
        .magnitude = 1.0f,
    };
    content.perks[7] = {
        .id = kSanctumPerkBlastGuardId,
        .effect = SurvivalPerkEffect::BlastGuard,
        .cost = 2000U,
        .magnitude = 0.55f,
    };
    content.perkCount = 8U;

    content.weaponPool[0] = {
        .weaponId = kSanctumWeaponSidearmId,
        .weight = 10U,
        .minimumRound = 1U,
    };
    content.weaponPool[1] = {
        .weaponId = kSanctumWeaponSubmachineGunId,
        .weight = 18U,
        .minimumRound = 1U,
    };
    content.weaponPool[2] = {
        .weaponId = kSanctumWeaponAssaultRifleId,
        .weight = 16U,
        .minimumRound = 1U,
    };
    content.weaponPool[3] = {
        .weaponId = kSanctumWeaponShotgunId,
        .weight = 14U,
        .minimumRound = 1U,
    };
    content.weaponPool[4] = {
        .weaponId = kSanctumWeaponMarksmanRifleId,
        .weight = 10U,
        .minimumRound = 3U,
    };
    content.weaponPool[5] = {
        .weaponId = kSanctumWeaponLightMachineGunId,
        .weight = 7U,
        .minimumRound = 5U,
    };
    content.weaponPool[6] = {
        .weaponId = kSanctumWeaponSniperRifleId,
        .weight = 5U,
        .minimumRound = 6U,
    };
    content.weaponPoolCount = 7U;

    content.consumables[0] = {
        .id = kSanctumConsumableFullAmmoId,
        .effect = SurvivalConsumableEffect::GrantPowerUp,
        .powerUp = SurvivalPowerUpKind::FullAmmo,
        .durationSeconds = 0.0f,
        .weight = 3U,
    };
    content.consumables[1] = {
        .id = kSanctumConsumableDoubleScoreId,
        .effect = SurvivalConsumableEffect::GrantPowerUp,
        .powerUp = SurvivalPowerUpKind::DoubleScore,
        .durationSeconds = 30.0f,
        .weight = 2U,
    };
    content.consumableCount = 2U;

    const auto addStation =
        [&](std::uint32_t id,
            SurvivalStationKind kind,
            Vec3 position,
            std::uint32_t cost,
            std::uint32_t contentId) noexcept {
            if (content.stationCount >=
                content.stations.size()) {
                return;
            }

            content.stations[
                content.stationCount++] = {
                .id = id,
                .kind = kind,
                .position = position,
                .cost = cost,
                .contentId = contentId,
                .maximumDistance = 1.75f,
                .minimumFacingDot = 0.12f,
                .priority = 1.20f,
                .holdSeconds = 0.16f,
                .enabled = true,
            };
        };

    if (anchors.hasWallWeapon) {
        addStation(
            kSanctumWallWeaponStationId,
            SurvivalStationKind::WallWeapon,
            anchors.wallWeapon,
            900U,
            kSanctumWeaponSubmachineGunId);
    }

    if (anchors.hasRandomArsenal) {
        addStation(
            kSanctumRandomArsenalStationId,
            SurvivalStationKind::RandomWeapon,
            anchors.randomArsenal,
            0U,
            0U);
    }

    if (anchors.hasReliquary) {
        addStation(
            kSanctumReliquaryStationId,
            SurvivalStationKind::Perk,
            anchors.reliquary,
            0U,
            kSanctumPerkFortitudeId);
    }

    if (anchors.hasWeaponUpgrade) {
        addStation(
            kSanctumWeaponUpgradeStationId,
            SurvivalStationKind::WeaponUpgrade,
            anchors.weaponUpgrade,
            0U,
            0U);
    }

    if (anchors.hasVotive) {
        addStation(
            kSanctumVotiveStationId,
            SurvivalStationKind::Consumable,
            anchors.votive,
            500U,
            0U);
    }

    return content;
}

namespace {

constexpr std::size_t presenceIndex(
    SanctumPresenceKind kind) noexcept {
    return static_cast<std::size_t>(kind);
}

float clamp01(float value) noexcept {
    if (!std::isfinite(value)) {
        return 0.0f;
    }
    return std::clamp(value, 0.0f, 1.0f);
}

float distanceMeters(
    const SanctumPoint& a,
    const SanctumPoint& b) noexcept {
    const float dx = a.x - b.x;
    const float dy = a.y - b.y;
    const float dz = a.z - b.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

float passiveRadius(
    SanctumPresenceKind kind) noexcept {
    switch (kind) {
        case SanctumPresenceKind::Llorona:
            return 58.0f;
        case SanctumPresenceKind::Nun:
            return 46.0f;
    }
    return 40.0f;
}

float passiveBedGain(
    SanctumPresenceKind kind,
    bool hostile,
    float intensity) noexcept {
    const float shaped =
        0.70f + 0.30f * clamp01(intensity);

    switch (kind) {
        case SanctumPresenceKind::Llorona:
            return (hostile ? 0.86f : 0.62f) * shaped;
        case SanctumPresenceKind::Nun:
            return (hostile ? 0.66f : 0.42f) * shaped;
    }
    return 0.0f;
}

float eventDistanceGain(
    float distance,
    float radius) noexcept {
    if (radius <= 0.0f || distance >= radius) {
        return 0.0f;
    }

    const float normalized =
        clamp01(distance / radius);

    // Keep distant passive sounds barely present, but never let them become
    // louder than a nearby source. The final mixer still applies occlusion.
    const float shaped =
        1.0f - normalized * normalized;

    return 0.08f + 0.92f * shaped;
}

SanctumPassiveCue chooseCue(
    SanctumPresenceKind kind,
    std::uint32_t state) noexcept {
    const bool alternate = (state & 1U) != 0U;

    if (kind == SanctumPresenceKind::Llorona) {
        return alternate
            ? SanctumPassiveCue::LloronaBreath
            : SanctumPassiveCue::LloronaDistantCry;
    }

    return alternate
        ? SanctumPassiveCue::NunWhisper
        : SanctumPassiveCue::NunPrayer;
}

bool addRoom(
    AcousticGraph& graph,
    SanctumZone zone,
    ReverbPreset preset,
    float reverb,
    float damping,
    float absorption) noexcept {
    return graph.addRoom({
        .id = static_cast<std::uint32_t>(zone),
        .preset = preset,
        .reverbAmount = reverb,
        .damping = damping,
        .occlusionAbsorption = absorption,
    });
}

bool addPortal(
    AcousticGraph& graph,
    std::uint32_t id,
    SanctumZone a,
    SanctumZone b,
    float openness,
    float absorption) noexcept {
    return graph.addPortal({
        .id = id,
        .roomA = static_cast<std::uint32_t>(a),
        .roomB = static_cast<std::uint32_t>(b),
        .openness = openness,
        .absorption = absorption,
    });
}

} // namespace

void SanctumAtmosphere::reset(
    std::uint32_t seed) noexcept {
    randomState_ =
        seed != 0U
        ? seed
        : 0x53A7C7U;

    initialized_ = true;

    cueCountdown_[
        presenceIndex(
            SanctumPresenceKind::Llorona)] =
        5.0f + random01() * 5.0f;

    cueCountdown_[
        presenceIndex(
            SanctumPresenceKind::Nun)] =
        8.0f + random01() * 6.0f;
}

bool SanctumAtmosphere::configureAcoustics(
    AcousticGraph& graph) noexcept {
    graph.reset();

    const bool roomsReady =
        addRoom(
            graph,
            SanctumZone::Courtyard,
            ReverbPreset::Exterior,
            0.12f,
            0.22f,
            0.18f) &&
        addRoom(
            graph,
            SanctumZone::Nave,
            ReverbPreset::Hall,
            0.76f,
            0.34f,
            0.30f) &&
        addRoom(
            graph,
            SanctumZone::Office,
            ReverbPreset::SmallRoom,
            0.30f,
            0.48f,
            0.48f) &&
        addRoom(
            graph,
            SanctumZone::OfficeCorridor,
            ReverbPreset::ConcreteRoom,
            0.38f,
            0.48f,
            0.52f) &&
        addRoom(
            graph,
            SanctumZone::BoilerRoom,
            ReverbPreset::MetalChamber,
            0.54f,
            0.42f,
            0.58f) &&
        addRoom(
            graph,
            SanctumZone::TowerStairs,
            ReverbPreset::Tunnel,
            0.48f,
            0.44f,
            0.52f) &&
        addRoom(
            graph,
            SanctumZone::RingingChamber,
            ReverbPreset::Hall,
            0.82f,
            0.30f,
            0.32f) &&
        addRoom(
            graph,
            SanctumZone::ClockChamber,
            ReverbPreset::MetalChamber,
            0.62f,
            0.38f,
            0.44f) &&
        addRoom(
            graph,
            SanctumZone::RoofChamber,
            ReverbPreset::ConcreteRoom,
            0.34f,
            0.40f,
            0.38f) &&
        addRoom(
            graph,
            SanctumZone::TowerTop,
            ReverbPreset::Exterior,
            0.18f,
            0.18f,
            0.16f);

    if (!roomsReady) {
        graph.reset();
        return false;
    }

    const bool portalsReady =
        addPortal(
            graph, 1001U,
            SanctumZone::Courtyard,
            SanctumZone::Nave,
            1.0f, 0.10f) &&
        addPortal(
            graph, 1002U,
            SanctumZone::Nave,
            SanctumZone::Office,
            0.92f, 0.18f) &&
        addPortal(
            graph, 1003U,
            SanctumZone::Office,
            SanctumZone::OfficeCorridor,
            0.92f, 0.16f) &&
        addPortal(
            graph, 1004U,
            SanctumZone::OfficeCorridor,
            SanctumZone::BoilerRoom,
            0.84f, 0.22f) &&
        addPortal(
            graph, 1005U,
            SanctumZone::Nave,
            SanctumZone::TowerStairs,
            0.84f, 0.20f) &&
        addPortal(
            graph, 1006U,
            SanctumZone::TowerStairs,
            SanctumZone::RingingChamber,
            0.88f, 0.18f) &&
        addPortal(
            graph, 1007U,
            SanctumZone::RingingChamber,
            SanctumZone::ClockChamber,
            0.86f, 0.16f) &&
        addPortal(
            graph, 1008U,
            SanctumZone::ClockChamber,
            SanctumZone::RoofChamber,
            0.82f, 0.20f) &&
        addPortal(
            graph, 1009U,
            SanctumZone::RoofChamber,
            SanctumZone::TowerTop,
            0.94f, 0.08f);

    if (!portalsReady) {
        graph.reset();
        return false;
    }

    return true;
}

SanctumAtmosphereFrame SanctumAtmosphere::advance(
    float deltaSeconds,
    const SanctumListener& listener,
    const SanctumPresence* presences,
    std::size_t presenceCount,
    const AcousticGraph& acoustics) noexcept {
    SanctumAtmosphereFrame frame{};

    if (!initialized_) {
        reset();
    }

    const float dt =
        std::clamp(
            std::isfinite(deltaSeconds)
                ? deltaSeconds
                : 0.0f,
            0.0f,
            0.25f);

    for (std::size_t i = 0;
         i < cueCountdown_.size();
         ++i) {
        cueCountdown_[i] =
            std::max(
                0.0f,
                cueCountdown_[i] - dt);
    }

    if (presences == nullptr) {
        return frame;
    }

    for (std::size_t i = 0;
         i < presenceCount;
         ++i) {
        const auto& presence = presences[i];

        if (!presence.active ||
            presence.id == 0U ||
            presence.zone == SanctumZone::Unknown) {
            continue;
        }

        const float distance =
            distanceMeters(
                listener.position,
                presence.position);

        const float radius =
            passiveRadius(
                presence.kind);

        if (distance > radius) {
            continue;
        }

        const auto acoustic =
            acoustics.query({
                .sourceRoom =
                    static_cast<std::uint32_t>(
                        presence.zone),
                .listenerRoom =
                    static_cast<std::uint32_t>(
                        listener.zone),
                .directDistanceMeters =
                    distance,
                .sourceImportance =
                    1.0f,
            });

        if (!acoustic.connected) {
            continue;
        }

        if (frame.passiveBedCount <
            frame.passiveBeds.size()) {
            auto& bed =
                frame.passiveBeds[
                    frame.passiveBedCount++];

            bed.id =
                presence.id ^
                0xA51E000000000000ULL;
            bed.kind =
                AudioSourceKind::Ambience;
            bed.distanceMeters =
                distance;
            bed.baseGain =
                passiveBedGain(
                    presence.kind,
                    presence.hostile,
                    presence.intensity);
            bed.importance =
                presence.hostile
                ? 0.90f
                : 0.42f;
            bed.occlusion =
                acoustic.occlusion;
            bed.reverbZoneSend =
                std::max(
                    acoustic.sourceRoomReverbSend,
                    acoustic.listenerRoomReverbSend);
            bed.looping = true;
            bed.critical = false;
        }

        const std::size_t slot =
            presenceIndex(
                presence.kind);

        if (slot >= cueCountdown_.size() ||
            cueCountdown_[slot] > 0.0f ||
            frame.cueEventCount >=
                frame.cueEvents.size()) {
            continue;
        }

        const float occlusionGain =
            1.0f -
            clamp01(
                acoustic.occlusion) *
                0.62f;

        auto& event =
            frame.cueEvents[
                frame.cueEventCount++];

        event.sourceId =
            presence.id;
        event.presence =
            presence.kind;
        event.cue =
            chooseCue(
                presence.kind,
                randomState_);
        event.distanceMeters =
            distance;
        event.gain =
            passiveBedGain(
                presence.kind,
                presence.hostile,
                presence.intensity) *
            eventDistanceGain(
                distance,
                radius) *
            occlusionGain;
        event.lowPassHz =
            acoustic.lowPassHz;
        event.reverbSend =
            std::max(
                acoustic.sourceRoomReverbSend,
                acoustic.listenerRoomReverbSend);

        cueCountdown_[slot] =
            nextDelay(
                presence.kind,
                presence.hostile);
    }

    return frame;
}

float SanctumAtmosphere::random01() noexcept {
    std::uint32_t x =
        randomState_;

    x ^= x << 13U;
    x ^= x >> 17U;
    x ^= x << 5U;

    randomState_ =
        x != 0U
        ? x
        : 0x53A7C7U;

    return static_cast<float>(
        randomState_ & 0x00FFFFFFU) /
        static_cast<float>(
            0x01000000U);
}

float SanctumAtmosphere::nextDelay(
    SanctumPresenceKind kind,
    bool hostile) noexcept {
    const float t =
        random01();

    if (kind ==
        SanctumPresenceKind::Llorona) {
        return hostile
            ? 5.0f + t * 4.0f
            : 12.0f + t * 10.0f;
    }

    return hostile
        ? 7.0f + t * 5.0f
        : 18.0f + t * 14.0f;
}

const char* sanctumZoneName(
    SanctumZone zone) noexcept {
    switch (zone) {
        case SanctumZone::Courtyard:
            return "Fallen Courtyard";
        case SanctumZone::Nave:
            return "Nave";
        case SanctumZone::Office:
            return "Office";
        case SanctumZone::OfficeCorridor:
            return "Office Corridor";
        case SanctumZone::BoilerRoom:
            return "Boiler Room";
        case SanctumZone::TowerStairs:
            return "Tower Stairs";
        case SanctumZone::RingingChamber:
            return "Ringing Chamber";
        case SanctumZone::ClockChamber:
            return "Clock Chamber";
        case SanctumZone::RoofChamber:
            return "Roof Chamber";
        case SanctumZone::TowerTop:
            return "Tower Top";
        case SanctumZone::Unknown:
            break;
    }

    return "Unknown";
}

} // namespace xziel
