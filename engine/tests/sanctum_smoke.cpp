#include "xziel/audio_scene.hpp"
#include "xziel/sanctum.hpp"

#include <array>
#include <cassert>

int main() {
    const auto profile =
        xziel::makeSanctumGameplayProfile();

    assert(profile.vitals.maxHealth == 68.0f);
    assert(!profile.vitals.autoRespawn);
    assert(profile.horde.interRoundDelaySeconds >= 5.0f);
    assert(profile.score.startingPoints == 500U);
    assert(profile.survival.perkLimit == 4U);
    assert(profile.survival.randomWeaponBaseCost == 950U);
    assert(profile.survival.weaponUpgradeBaseCost == 5000U);
    assert(profile.survival.maxWeaponUpgradeTier == 3U);
    assert(profile.survival.powerUpLifetimeSeconds == 12.0f);
    assert(profile.horror.stingerCooldownSeconds >= 18.0f);
    assert(!profile.showQuestChecklistHud);
    assert(!profile.showPassivePresenceMarkers);
    assert(!profile.autoRevealSecrets);

    xziel::SanctumSurvivalAnchors survivalAnchors{};
    survivalAnchors.wallWeapon = {1.0f, 0.0f, 0.0f};
    survivalAnchors.randomArsenal = {2.0f, 0.0f, 0.0f};
    survivalAnchors.reliquary = {3.0f, 0.0f, 0.0f};
    survivalAnchors.weaponUpgrade = {4.0f, 0.0f, 0.0f};
    survivalAnchors.votive = {5.0f, 0.0f, 0.0f};
    survivalAnchors.hasWallWeapon = true;
    survivalAnchors.hasRandomArsenal = true;
    survivalAnchors.hasReliquary = true;
    survivalAnchors.hasWeaponUpgrade = true;
    survivalAnchors.hasVotive = true;

    const auto survivalContent =
        xziel::makeSanctumSurvivalContent(
            survivalAnchors);

    assert(survivalContent.perkCount == 8U);
    assert(survivalContent.weaponPoolCount == 7U);
    assert(survivalContent.consumableCount == 2U);
    assert(survivalContent.stationCount == 5U);

    xziel::SurvivalRuntime survival;
    assert(survival.load(survivalContent));

    xziel::InteractionSystem survivalInteractions;
    assert(
        survival.registerInteractions(
            survivalInteractions));
    assert(
        survivalInteractions.targetCount() ==
        survivalContent.stationCount);

    xziel::ScoreSystem verticalSliceScore{
        profile.score};
    assert(
        verticalSliceScore.awardUtility(1000U).total ==
        1500U);

    const auto wallPurchase =
        survival.purchaseWallWeapon(
            xziel::kSanctumWallWeaponStationId,
            verticalSliceScore);
    assert(wallPurchase.success);
    assert(
        wallPurchase.contentId ==
        xziel::kSanctumWeaponSubmachineGunId);
    assert(
        verticalSliceScore.frame().total ==
        600U);

    xziel::PlayerVitals vulnerablePlayer{
        profile.vitals};

    assert(
        vulnerablePlayer.applyDamage(
            xziel::ZombieConfig{}.attackDamage));
    assert(vulnerablePlayer.frame().alive);
    assert(
        vulnerablePlayer.applyDamage(
            xziel::ZombieConfig{}.attackDamage));
    assert(!vulnerablePlayer.frame().alive);

    xziel::AcousticGraph acoustics;
    assert(
        xziel::SanctumAtmosphere::
            configureAcoustics(acoustics));
    assert(acoustics.roomCount() == 10U);
    assert(acoustics.portalCount() == 9U);

    xziel::SanctumAtmosphere atmosphere;
    atmosphere.reset(0x12345678U);

    xziel::SanctumListener listener{
        .position = {0.0f, 0.0f, 0.0f},
        .zone = xziel::SanctumZone::Nave,
    };

    std::array<xziel::SanctumPresence, 2> presences{{
        {
            .id = 9001U,
            .kind = xziel::SanctumPresenceKind::Llorona,
            .position = {34.0f, 3.0f, 0.0f},
            .zone = xziel::SanctumZone::TowerTop,
            .intensity = 0.35f,
            .active = true,
            .hostile = false,
        },
        {
            .id = 9002U,
            .kind = xziel::SanctumPresenceKind::Nun,
            .position = {8.0f, 0.0f, 2.0f},
            .zone = xziel::SanctumZone::Nave,
            .intensity = 0.20f,
            .active = true,
            .hostile = false,
        },
    }};

    unsigned int lloronaCues = 0U;
    unsigned int nunCues = 0U;
    bool sawDistantLloronaBed = false;
    bool sawOccludedLloronaCue = false;

    xziel::RenderWorkload workload{};
    workload.quality =
        xziel::RenderQuality::Low;

    xziel::AudioScenePlanner planner;

    for (int frameIndex = 0;
         frameIndex < 60 * 60;
         ++frameIndex) {
        const auto frame =
            atmosphere.advance(
                1.0f / 60.0f,
                listener,
                presences.data(),
                presences.size(),
                acoustics);

        assert(frame.passiveBedCount == 2U);

        std::array<
            xziel::AudioVoiceDecision,
            4> decisions{};

        const auto decisionCount =
            planner.plan(
                frame.passiveBeds.data(),
                frame.passiveBedCount,
                workload,
                decisions.data(),
                decisions.size());

        assert(decisionCount == 2U);

        for (std::size_t i = 0;
             i < frame.passiveBedCount;
             ++i) {
            if (frame.passiveBeds[i].id ==
                    (9001U ^
                     0xA51E000000000000ULL)) {
                sawDistantLloronaBed = true;
                assert(
                    frame.passiveBeds[i].
                        distanceMeters > 30.0f);
                assert(
                    frame.passiveBeds[i].
                        occlusion > 0.0f);
            }
        }

        for (std::size_t i = 0;
             i < frame.cueEventCount;
             ++i) {
            const auto& event =
                frame.cueEvents[i];

            assert(event.gain > 0.0f);
            assert(event.gain <= 1.0f);
            assert(event.reverbSend >= 0.0f);
            assert(event.reverbSend <= 1.0f);

            if (event.presence ==
                xziel::SanctumPresenceKind::Llorona) {
                ++lloronaCues;
                if (event.distanceMeters > 30.0f &&
                    event.lowPassHz < 20000.0f) {
                    sawOccludedLloronaCue = true;
                }
            } else {
                ++nunCues;
            }
        }
    }

    // Passive mode is intentionally sparse: presence is audible, but
    // discrete cries/prayers cannot turn into repetitive audio spam.
    assert(lloronaCues >= 2U);
    assert(lloronaCues <= 5U);
    assert(nunCues >= 1U);
    assert(nunCues <= 4U);

    assert(sawDistantLloronaBed);
    assert(sawOccludedLloronaCue);

    // Closing the nave-to-tower path should naturally block the distant
    // presence rather than playing a fake global 2D scream.
    assert(
        acoustics.setPortalOpenness(
            1005U,
            0.0f));

    const auto blocked =
        atmosphere.advance(
            1.0f / 60.0f,
            listener,
            presences.data(),
            1U,
            acoustics);

    assert(blocked.passiveBedCount == 0U);
    assert(blocked.cueEventCount == 0U);

    return 0;
}
