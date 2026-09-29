#!/usr/bin/env python3
"""Validate the XZIEL BO3 Nacht full-completion contract.

This is intentionally stricter than the current gameplay harness:
- every weapon in the global catalog must be tracked;
- every required weapon lane must be explicit;
- every required map/system lane must be explicit;
- releaseCandidate=true is forbidden until all required lanes are ready or
  explicitly not_applicable.

The validator does not pretend pending work is complete. It exists to make
silent omissions impossible.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "assets/nacht_reference/bo3_nacht_completion_contract_v1.json"
CATALOG = ROOT / "assets/weapons/xziel_weapon_catalog_v1.json"
BOX = ROOT / "assets/weapons/xziel_mystery_box_pool_v1.json"
RUNTIME = ROOT / "assets/nacht_reference/runtime_reference_v1.json"
BEHAVIOR_SPECS = ROOT / "assets/nacht_reference/bo3_weapon_specs_v1.json"
GOBBLEGUM_CATALOG = ROOT / "assets/nacht_reference/bo3_gobblegum_catalog_v1.json"
SYSTEM_PLACEMENTS = ROOT / "assets/nacht_reference/bo3_system_placements_v1.json"
PERK_CATALOG = ROOT / "assets/nacht_reference/bo3_perk_catalog_v1.json"
POWERUP_CATALOG = ROOT / "assets/nacht_reference/bo3_powerup_catalog_v1.json"
WEAPON_ID_REGISTRY = ROOT / "assets/weapons/xziel_weapon_id_registry_v1.json"
RUNTIME_BOX_POOL = ROOT / "assets/weapons/xziel_mystery_box_runtime_pool_v1.json"
RUNTIME_CAPABILITIES = ROOT / "assets/nacht_reference/xziel_zombies_runtime_capabilities_v1.json"
DEATH_MACHINE_SPEC = ROOT / "assets/nacht_reference/bo3_death_machine_spec_v1.json"
PAP_CATALOG = ROOT / "assets/weapons/bo3_pack_a_punch_catalog_v1.json"

ALLOWED_STATES = {
    "pending",
    "partial",
    "cataloged",
    "logic_only",
    "ready",
    "not_applicable",
}
COMPLETE_STATES = {"ready", "not_applicable"}

REQUIRED_SYSTEMS = {
    "map_topology_and_collision",
    "doors_and_zone_unlocks",
    "barricades_repair_points",
    "zombie_spawns_pathing_ai",
    "wall_buys_and_ammo_refills",
    "mystery_box_full_pool_and_teddy_flow",
    "gobblegum_machines_and_full_effect_runtime",
    "der_wunderfizz_and_perk_randomization",
    "mule_kick_and_weapon_slot_semantics",
    "powerup_drop_pool_and_effects",
    "pack_a_punch_weapon_variants",
    "points_economy_scoring",
    "all_interactions_zero_dead_prompts",
    "weapon_models_audio_fx_animations",
    "multiplayer_1_to_4_gameplay",
    "android_touch_hud_and_controls",
    "android_visual_parity",
    "horde_stress_and_round_100_soak",
    "crash_memory_leak_watch",
}


def fail(message: str) -> None:
    raise SystemExit(f"NACHT_COMPLETION_CONTRACT_FAIL: {message}")


def load(path: Path):
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    contract = load(CONTRACT)
    catalog = load(CATALOG)
    box = load(BOX)
    runtime = load(RUNTIME)
    behavior_specs = load(BEHAVIOR_SPECS)
    gobblegum_catalog = load(GOBBLEGUM_CATALOG)
    system_placements = load(SYSTEM_PLACEMENTS)
    perk_catalog = load(PERK_CATALOG)
    powerup_catalog = load(POWERUP_CATALOG)
    weapon_id_registry = load(WEAPON_ID_REGISTRY)
    runtime_box_pool = load(RUNTIME_BOX_POOL)
    runtime_capabilities = load(RUNTIME_CAPABILITIES)
    death_machine_spec = load(DEATH_MACHINE_SPEC)
    pap_catalog = load(PAP_CATALOG)

    if contract.get("schemaVersion") != 1:
        fail("schemaVersion must be 1")
    if contract.get("contractId") != "bo3_nacht_android_one_to_one_v1":
        fail("unexpected contractId")
    if not isinstance(contract.get("releaseCandidate"), bool):
        fail("releaseCandidate must be boolean")

    weapons = catalog.get("weapons")
    if not isinstance(weapons, list) or not weapons:
        fail("weapon catalog is empty or invalid")

    catalog_ids = [w.get("weaponId") for w in weapons]
    if any(not isinstance(x, str) or not x for x in catalog_ids):
        fail("catalog contains invalid weaponId")
    if len(catalog_ids) != len(set(catalog_ids)):
        fail("catalog contains duplicate weaponId values")

    tracked = contract.get("weapons")
    if not isinstance(tracked, dict):
        fail("contract weapons must be an object")

    tracked_ids = set(tracked)
    catalog_set = set(catalog_ids)
    missing = sorted(catalog_set - tracked_ids)
    extra = sorted(tracked_ids - catalog_set)
    if missing:
        fail(f"catalog weapons missing from completion contract: {missing}")
    if extra:
        fail(f"completion contract contains unknown weapons: {extra}")

    baseline = contract.get("baseline", {})
    spec_rows = behavior_specs.get("weapons", [])
    if not isinstance(spec_rows, list):
        fail("BO3 behavior specs weapons must be a list")
    spec_ids = [row.get("logicalItemId") for row in spec_rows]
    if any(not isinstance(x, str) or not x for x in spec_ids):
        fail("BO3 behavior specs contains invalid logicalItemId")
    if len(spec_ids) != len(set(spec_ids)):
        fail("BO3 behavior specs contains duplicate logicalItemId values")
    if not set(spec_ids).issubset(catalog_set):
        fail(f"BO3 behavior specs contains unknown catalog IDs: {sorted(set(spec_ids)-catalog_set)}")
    if baseline.get("bo3StructuredBehaviorSpecCount") != len(spec_rows):
        fail(
            f"bo3StructuredBehaviorSpecCount={baseline.get('bo3StructuredBehaviorSpecCount')} "
            f"does not match behavior specs={len(spec_rows)}"
        )

    gum_entries = gobblegum_catalog.get("entries", [])
    if not isinstance(gum_entries, list):
        fail("GobbleGum catalog entries must be a list")
    gum_ids = [row.get("id") for row in gum_entries]
    if len(gum_entries) != 63 or len(gum_ids) != len(set(gum_ids)):
        fail("GobbleGum identity catalog must contain exactly 63 unique entries")
    if baseline.get("gobbleGumIdentityCount") != len(gum_entries):
        fail("gobbleGumIdentityCount drift")

    gum_core = gobblegum_catalog.get("runtimeCore", {})
    if gum_core.get("status") != "logic_ready":
        fail("GobbleGum runtime core must remain logic_ready once landed")
    if gum_core.get("loadoutSize") != 5 or baseline.get("gobbleGumLoadoutSize") != 5:
        fail("GobbleGum loadout size drift")
    if gum_core.get("maxRollsPerRound") != 3 or baseline.get("gobbleGumMaxRollsPerRound") != 3:
        fail("GobbleGum max rolls per round drift")
    if gum_core.get("firstRollFree") is not True:
        fail("Chronicles GobbleGum first roll must be free")
    expected_second_prices = {
        "1-9": 1500,
        "10-19": 2500,
        "20-29": 4500,
        "30-39": 8500,
        "40-49": 16500,
        "50-59": 32500,
        "60-69": 64500,
        "70-79": 128500,
        "80-89": 256500,
        "90-99": 512500,
        "100+": 1024500,
    }
    if gum_core.get("secondRollBaseByRoundTier") != expected_second_prices:
        fail("GobbleGum round-tier price schedule drift")
    if gum_core.get("thirdRollMultiplier") != 2:
        fail("GobbleGum third-roll multiplier drift")
    if gum_core.get("fireSalePriceReduction") != 490:
        fail("GobbleGum Fire Sale price reduction drift")
    if gum_core.get("selectionPolicy") != "five_entry_shuffle_bag_before_repeat":
        fail("GobbleGum selection policy drift")

    expected_mapped_gums = {
        "cache_back": ("spawn_max_ammo", 1, "XZIEL_PU_MAXAMMO"),
        "dead_of_nuclear_winter": ("spawn_nuke", 2, "XZIEL_PU_NUKE"),
        "kill_joy": ("spawn_insta_kill", 2, "XZIEL_PU_INSTAKILL"),
        "licensed_contractor": ("spawn_carpenter", 3, "XZIEL_PU_CARPENTER"),
        "on_the_house": ("spawn_random_perk", 1, "XZIEL_PU_RANDOMPERK"),
        "whos_keeping_score": ("spawn_double_points", 2, "XZIEL_PU_DOUBLEPOINTS"),
    }
    gum_by_id = {row["id"]: row for row in gum_entries}
    logic_ready_effects = 0
    for gum_id, (effect_type, activations, semantic) in expected_mapped_gums.items():
        row = gum_by_id[gum_id]
        if row.get("effectSpecStatus") != "verified":
            fail(f"{gum_id} effect spec must be verified")
        if row.get("effectSpec") != {"type": effect_type, "activations": activations}:
            fail(f"{gum_id} effect spec drift")
        primitive = row.get("runtimePrimitive", {})
        if primitive.get("status") != "logic_ready":
            fail(f"{gum_id} runtime primitive must be logic_ready")
        if primitive.get("powerupSemantic") != semantic:
            fail(f"{gum_id} power-up semantic drift")
        if row.get("runtimeStatus") != "pending":
            fail(f"{gum_id} must remain pending until full machine/consumption/presentation runtime is complete")
        logic_ready_effects += 1

    if logic_ready_effects != 6:
        fail("expected exactly six mapped GobbleGum effect primitives")
    if gobblegum_catalog.get("validation", {}).get("effectSpecsVerified") != 10:
        fail("GobbleGum verified effect-spec count drift")
    if gobblegum_catalog.get("validation", {}).get("effectPrimitivesLogicReady") != 6:
        fail("GobbleGum logic-ready effect primitive count drift")

    if gobblegum_catalog.get("validation", {}).get("effectDispatchLogicReady") != 6:
        fail("GobbleGum logic-ready effect dispatch count drift")
    for gum_id in expected_mapped_gums:
        primitive = gum_by_id[gum_id].get("runtimePrimitive", {})
        if primitive.get("dispatchStatus") != "logic_ready":
            fail(f"{gum_id} effect dispatch must be logic_ready")
        if primitive.get("activationFunction") != "XZIEL_GobbleGumActivateHeldMappedPowerup":
            fail(f"{gum_id} activation function drift")
        if primitive.get("chargeStateFunction") != "XZIEL_GobbleGumHeldUsesRemaining":
            fail(f"{gum_id} charge-state function drift")

    expected_pap_gums = {
        "wall_power": {
            "status": "logic_ready_dormant",
            "resolveFunction": "XZIEL_GobbleGumResolveWallPowerWeapon",
            "source": ("scripts/zm/bgbs/_zm_bgb_wall_power.gsc", "7c5e47f2e7e1574c7057b39d4abfddb6a9fb4cde"),
        },
        "crate_power": {
            "status": "logic_ready_dormant",
            "resolveFunction": "XZIEL_GobbleGumResolveCratePowerWeapon",
            "source": ("scripts/zm/bgbs/_zm_bgb_crate_power.gsc", "b3683e2da10edf0dcb208eb10e353172f37e8fcf"),
        },
        "ephemeral_enhancement": {
            "status": "logic_ready_dormant",
            "source": ("scripts/zm/bgbs/_zm_bgb_ephemeral_enhancement.gsc", "d9dd26127ac48e7b39ec0705b05faf14e8a42999"),
        },
        "disorderly_combat": {
            "status": "rotation_backend_logic_ready_dormant_aat_blocked",
            "source": ("scripts/zm/bgbs/_zm_bgb_disorderly_combat.gsc", "a66e8287ba98702aa75e62213fa1f49ee39f9c45"),
        },
    }
    for gum_id, expected in expected_pap_gums.items():
        row = gum_by_id[gum_id]
        if row.get("effectSpecStatus") != "verified":
            fail(f"{gum_id} PaP-dependent effect spec must be verified")
        if row.get("runtimeStatus") != "pending":
            fail(f"{gum_id} must remain pending until full runtime/presentation is complete")
        primitive = row.get("runtimePrimitive", {})
        if primitive.get("status") != expected["status"]:
            fail(f"{gum_id} runtime primitive status drift")
        if gum_id in {"wall_power", "crate_power"}:
            if primitive.get("activationFunction") != "XZIEL_GobbleGumActivatePapEvent":
                fail(f"{gum_id} event activation function drift")
            if primitive.get("resolveFunction") != expected["resolveFunction"]:
                fail(f"{gum_id} event resolve function drift")
            if primitive.get("readinessGate") != "XZIEL_PackAPunchRuntimeReady":
                fail(f"{gum_id} readiness gate drift")
            if primitive.get("exposedUpgradeCount") != 0:
                fail(f"{gum_id} must expose zero PaP rewards while runtime-ready count is zero")
        if gum_id == "disorderly_combat":
            if primitive.get("canActivateFunction") != "XZIEL_GobbleGumDisorderlyCanActivateFull":
                fail("Disorderly Combat full activation validator drift")
            if primitive.get("activationFunction") != "XZIEL_GobbleGumActivateDisorderlyCombat":
                fail("Disorderly Combat activation function drift")
            if primitive.get("tickFunction") != "XZIEL_GobbleGumDisorderlyTick":
                fail("Disorderly Combat tick function drift")
            if primitive.get("restoreFunction") != "XZIEL_GobbleGumDisorderlyRestore":
                fail("Disorderly Combat restore function drift")
            if primitive.get("poolResolverFunction") != "XZIEL_GobbleGumDisorderlyWeaponAtIndex":
                fail("Disorderly Combat pool resolver drift")
            if primitive.get("baseReadinessFunction") != "XZIEL_GobbleGumDisorderlyReadyBaseCount":
                fail("Disorderly Combat base readiness function drift")
            if primitive.get("papReadinessFunction") != "XZIEL_GobbleGumDisorderlyReadyPapCount":
                fail("Disorderly Combat PaP readiness function drift")
            if primitive.get("poolReadinessGate") != "XZIEL_GobbleGumDisorderlyPoolRuntimeReady":
                fail("Disorderly Combat pool readiness gate drift")
            if primitive.get("aatReadinessFunction") != "XZIEL_GobbleGumDisorderlyAATRuntimeReady":
                fail("Disorderly Combat AAT readiness function drift")
            if primitive.get("timerRotationInventoryRuntime") != "logic_ready_dormant":
                fail("Disorderly Combat rotation runtime status drift")
            if primitive.get("durationSeconds") != 300:
                fail("Disorderly Combat duration drift")
            if primitive.get("switchIntervalSeconds") != 10:
                fail("Disorderly Combat switch interval drift")
            if primitive.get("warningSecondsBeforeSwitch") != 5:
                fail("Disorderly Combat warning interval drift")
            if primitive.get("inputLock") != {
                "weaponCycling": "logic_ready",
                "offhand": "logic_ready",
            }:
                fail("Disorderly Combat input-lock status drift")
            if primitive.get("originalWeaponRestore") != "logic_ready":
                fail("Disorderly Combat original-weapon restore drift")
            if primitive.get("papStatePreservation") != "logic_ready":
                fail("Disorderly Combat PaP-state preservation drift")
            if primitive.get("aatPreservation") != "pending":
                fail("Disorderly Combat AAT preservation must remain pending")
            if primitive.get("warningPresentation") != "pending":
                fail("Disorderly Combat warning presentation must remain pending")
            if primitive.get("requiredPoolCount") != 26:
                fail("Disorderly Combat required pool count drift")
            if primitive.get("readyPoolCount") != 0:
                fail("Disorderly Combat ready pool count must remain zero")
            if primitive.get("activationAllowed") is not False:
                fail("Disorderly Combat activation must remain blocked")

        if gum_id == "ephemeral_enhancement":
            if primitive.get("canActivateFunction") != "XZIEL_GobbleGumEphemeralCanActivate":
                fail("Ephemeral Enhancement activation validator drift")
            if primitive.get("activationFunction") != "XZIEL_GobbleGumActivateEphemeralEnhancement":
                fail("Ephemeral Enhancement activation function drift")
            if primitive.get("tickFunction") != "XZIEL_GobbleGumEphemeralTick":
                fail("Ephemeral Enhancement tick function drift")
            if primitive.get("restoreFunction") != "XZIEL_GobbleGumEphemeralRestore":
                fail("Ephemeral Enhancement restore function drift")
            if primitive.get("readinessGate") != "XZIEL_PackAPunchRuntimeReady":
                fail("Ephemeral Enhancement readiness gate drift")
            if primitive.get("durationSeconds") != 60:
                fail("Ephemeral Enhancement duration drift")
            if primitive.get("downedExpiry") != "defer restore until revive":
                fail("Ephemeral Enhancement downed-expiry semantics drift")
            if primitive.get("replacedWeapon") != "clear effect without recreating original":
                fail("Ephemeral Enhancement replaced-weapon semantics drift")
            if primitive.get("exposedUpgradeCount") != 0:
                fail("Ephemeral Enhancement must expose zero upgrades while PaP runtime-ready count is zero")
        sources = row.get("sourceAuthority", [])
        if not any(
            src.get("path") == expected["source"][0]
            and src.get("blobSha") == expected["source"][1]
            for src in sources
        ):
            fail(f"{gum_id} source provenance drift")

    gum_validation = gobblegum_catalog.get("validation", {})
    if gum_validation.get("papDependentEffectSpecsVerified") != 4:
        fail("PaP-dependent GobbleGum verified spec count drift")
    if gum_validation.get("papEventPlumbingLogicReady") != 2:
        fail("Wall/Crate Power event plumbing count drift")
    if gum_validation.get("papTimedEffectLogicReady") != 1:
        fail("Ephemeral Enhancement timed PaP backend count drift")
    if gum_validation.get("papDependentRuntimeLogicReady") != 4:
        fail("PaP-dependent GobbleGum runtime logic-ready count drift")
    if gum_validation.get("disorderlyCombatPoolVerified") is not True:
        fail("Disorderly Combat pool verification flag drift")
    if gum_validation.get("disorderlyCombatEligiblePoolCount") != 26:
        fail("Disorderly Combat eligible pool count drift")
    if gum_validation.get("disorderlyCombatPoolBackendLogicReady") is not True:
        fail("Disorderly Combat pool backend readiness flag drift")
    if gum_validation.get("disorderlyCombatRotationBackendLogicReady") is not True:
        fail("Disorderly Combat rotation backend readiness flag drift")
    if gum_validation.get("disorderlyCombatAATBridgeReady") is not False:
        fail("Disorderly Combat AAT bridge must remain blocked")
    if gum_validation.get("disorderlyCombatActivationAllowed") is not False:
        fail("Disorderly Combat activation flag must remain false")
    if gum_validation.get("papRuntimeRewardsExposed") != 0:
        fail("PaP GobbleGums must expose zero runtime rewards while PaP variants are pending")

    placement_rows = system_placements.get("entities", [])
    if not isinstance(placement_rows, list):
        fail("system placements entities must be a list")
    type_counts = {}
    for row in placement_rows:
        t = row.get("type")
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts.get("gobblegum_machine", 0) != baseline.get("gobbleGumMachinePlacements"):
        fail("GobbleGum machine placement count drift")
    if type_counts.get("der_wunderfizz", 0) != baseline.get("wunderfizzMachinePlacements"):
        fail("Wunderfizz placement count drift")
    if type_counts.get("mystery_box", 0) != baseline.get("mysteryBoxAnchors"):
        fail("Mystery Box anchor count drift")

    perk_entries = perk_catalog.get("entries", [])
    if not isinstance(perk_entries, list):
        fail("perk catalog entries must be a list")
    perk_ids = [row.get("id") for row in perk_entries]
    if len(perk_entries) != 8 or len(perk_ids) != len(set(perk_ids)):
        fail("BO3 Nacht perk catalog must contain exactly 8 unique identities")
    if baseline.get("canonicalPerkIdentityCount") != len(perk_entries):
        fail("canonicalPerkIdentityCount drift")
    wf_pool = [row for row in perk_entries if row.get("wunderfizzEligible") is True]
    if len(wf_pool) != 7 or baseline.get("wunderfizzPoolIdentityCount") != len(wf_pool):
        fail("Wunderfizz perk pool identity count drift")

    power_entries = powerup_catalog.get("entries", [])
    if not isinstance(power_entries, list):
        fail("power-up catalog entries must be a list")
    power_ids = [row.get("id") for row in power_entries]
    if len(power_entries) != 9 or len(power_ids) != len(set(power_ids)):
        fail("BO3 core power-up catalog must contain exactly 9 unique identities")
    if baseline.get("corePowerupIdentityCount") != len(power_entries):
        fail("corePowerupIdentityCount drift")
    natural_power = [row for row in power_entries if row.get("nachtNaturalDrop") is True]
    if len(natural_power) != 6 or baseline.get("nachtNaturalPowerupIdentityCount") != len(natural_power):
        fail("Nacht natural power-up identity count drift")

    capability_perks = runtime_capabilities.get("perks", [])
    capability_powerups = runtime_capabilities.get("powerups", [])
    if len(capability_perks) != len(perk_entries):
        fail("runtime perk capability coverage drift")
    if len(capability_powerups) != len(power_entries):
        fail("runtime power-up capability coverage drift")

    reusable_perks = [row for row in capability_perks if row.get("primitiveAvailable") is True]
    reusable_powerups = [row for row in capability_powerups if row.get("primitiveAvailable") is True]
    missing_perks = sorted(row["id"] for row in capability_perks if row.get("primitiveAvailable") is not True)
    missing_powerups = sorted(row["id"] for row in capability_powerups if row.get("primitiveAvailable") is not True)

    if len(reusable_perks) != 7 or baseline.get("reusablePerkPrimitiveCount") != 7:
        fail("reusable perk primitive count drift")
    if len(reusable_powerups) != 7 or baseline.get("reusablePowerupPrimitiveCount") != 7:
        fail("reusable power-up primitive count drift")
    if missing_perks != ["widows_wine"]:
        fail(f"unexpected missing perk primitives: {missing_perks}")
    if missing_powerups != ["death_machine", "fire_sale"]:
        fail(f"unexpected missing power-up primitives: {missing_powerups}")

    xziel_logic_powerups = [
        row for row in capability_powerups
        if row.get("primitiveAvailable") is True or row.get("xzielLogicAvailable") is True
    ]
    missing_logic_powerups = sorted(
        row["id"] for row in capability_powerups
        if row.get("primitiveAvailable") is not True
        and row.get("xzielLogicAvailable") is not True
    )
    if len(xziel_logic_powerups) != 8:
        fail(f"expected 8 XZIEL power-up logic primitives, got {len(xziel_logic_powerups)}")
    if baseline.get("xzielPowerupLogicPrimitiveCount") != len(xziel_logic_powerups):
        fail("xzielPowerupLogicPrimitiveCount drift")
    if missing_logic_powerups != ["death_machine"]:
        fail(f"unexpected missing XZIEL power-up logic primitives: {missing_logic_powerups}")

    perk_cap_by_id = {row["id"]: row for row in capability_perks}
    for row in perk_entries:
        primitive = row.get("runtimePrimitive", {})
        expected = perk_cap_by_id[row["id"]].get("primitiveAvailable") is True
        if primitive.get("available") is not expected:
            fail(f"perk runtime primitive drift for {row['id']}")

    power_cap_by_id = {row["id"]: row for row in capability_powerups}
    for row in power_entries:
        primitive = row.get("runtimePrimitive", {})
        expected = power_cap_by_id[row["id"]].get("primitiveAvailable") is True
        if primitive.get("available") is not expected:
            fail(f"power-up runtime primitive drift for {row['id']}")

    if death_machine_spec.get("logicalItemId") != "special_death_machine":
        fail("Death Machine special behavior spec identity drift")
    if death_machine_spec.get("durationSeconds") != 30:
        fail("Death Machine duration contract drift")
    if death_machine_spec.get("packAPunchEligible") is not False:
        fail("Death Machine must remain non-Pack-a-Punchable")
    dm_source = death_machine_spec.get("sourceAuthority", {})
    dm_impl = dm_source.get("implementationSource", {})
    dm_generic = dm_source.get("genericPowerupWeaponSource", {})
    if dm_impl.get("repository") != "ate47/bo3-source":
        fail("Death Machine implementation source repository drift")
    if dm_impl.get("path") != "scripts/zm/_zm_powerup_weapon_minigun.gsc":
        fail("Death Machine implementation source path drift")
    if dm_impl.get("blobSha") != "9d3f0cbe0d1dd9ac72289cad9531d91a46eccaf8":
        fail("Death Machine implementation source blob drift")
    if dm_generic.get("path") != "scripts/zm/_zm_powerups.gsc":
        fail("Death Machine generic power-up source path drift")
    if dm_generic.get("blobSha") != "8965a32e1d9f426f94f24e83c095fda8b9c00512":
        fail("Death Machine generic power-up source blob drift")

    dm_damage = death_machine_spec.get("damage", {})
    if dm_damage.get("exactFormulaStatus") != "verified_from_bo3_source":
        fail("Death Machine damage formula verification status drift")
    if dm_damage.get("randomLowerInclusive") != 0.34:
        fail("Death Machine damage lower fraction drift")
    if dm_damage.get("randomUpperExclusive") != 0.75:
        fail("Death Machine damage upper fraction drift")
    if dm_damage.get("formula") != (
        "finalDamage = baseDamage + victimCurrentHealth * random(0.34, 0.75)"
    ):
        fail("Death Machine damage formula drift")
    if dm_damage.get("implementationAllowed") is not True:
        fail("Death Machine source-backed damage hook must remain implementation-allowed")
    if baseline.get("specialWeaponBehaviorSpecCount") != 1:
        fail("specialWeaponBehaviorSpecCount drift")

    pap_variants = pap_catalog.get("variants", [])
    if not isinstance(pap_variants, list):
        fail("Pack-a-Punch catalog variants must be a list")
    if len(pap_variants) != 36:
        fail(f"Pack-a-Punch catalog must contain exactly 36 variants, got {len(pap_variants)}")

    pap_base_ids = [row.get("baseWeaponId") for row in pap_variants]
    pap_upgrade_ids = [row.get("upgradeWeaponId") for row in pap_variants]
    if len(pap_base_ids) != len(set(pap_base_ids)):
        fail("Pack-a-Punch catalog contains duplicate base weapon IDs")
    if len(pap_upgrade_ids) != len(set(pap_upgrade_ids)):
        fail("Pack-a-Punch catalog contains duplicate upgrade weapon IDs")
    if not set(pap_base_ids).issubset(catalog_set):
        fail(
            "Pack-a-Punch catalog contains unknown base weapon IDs: "
            f"{sorted(set(pap_base_ids)-catalog_set)}"
        )

    pap_counts = pap_catalog.get("counts", {})
    expected_pap_counts = {
        "upgradeIdentities": 36,
        "statstableRows": 30,
        "attachmentMappingRows": 26,
        "specialEvidenceVariants": 6,
        "ballisticUpgradeStatsReady": 0,
        "nativeRuntimeReady": 0,
        "dedicatedNativeUpgradeIds": 35,
        "reusedCatalogUpgradeIds": 1,
    }
    if pap_counts != expected_pap_counts:
        fail(f"Pack-a-Punch count drift: {pap_counts} != {expected_pap_counts}")

    if baseline.get("packAPunchUpgradeIdentityCount") != 36:
        fail("packAPunchUpgradeIdentityCount drift")
    if baseline.get("packAPunchStatstableCoverage") != 30:
        fail("packAPunchStatstableCoverage drift")
    if baseline.get("packAPunchAttachmentMappingCoverage") != 26:
        fail("packAPunchAttachmentMappingCoverage drift")
    if baseline.get("packAPunchBallisticStatsReady") != 0:
        fail("packAPunchBallisticStatsReady must remain 0 until source-backed values land")
    if baseline.get("packAPunchNativeRuntimeReady") != 0:
        fail("packAPunchNativeRuntimeReady must remain 0 until native runtime lands")

    pap_system = contract.get("requiredSystems", {}).get(
        "pack_a_punch_weapon_variants", {}
    )
    if pap_system.get("state") != "partial":
        fail("Pack-a-Punch system must remain partial")
    if pap_system.get("upgradeIdentityCount") != 36:
        fail("Pack-a-Punch system identity count drift")
    if pap_system.get("identityStatus") != "ready":
        fail("Pack-a-Punch identity layer must be ready")
    if pap_system.get("ballisticUpgradeStatsReady") != 0:
        fail("Pack-a-Punch ballistic stats must not be promoted prematurely")
    if pap_system.get("nativeRuntimeReady") != 0:
        fail("Pack-a-Punch runtime must not be promoted prematurely")
    if pap_system.get("nativeLegacyHelperBridgeStatus") != "ready":
        fail("Pack-a-Punch native legacy-helper bridge must remain ready")
    if pap_system.get("nativeLegacyHelperBridgeScope") != "xziel_*":
        fail("Pack-a-Punch legacy-helper bridge scope drift")
    if pap_system.get("legacyMapIsolation") is not True:
        fail("Pack-a-Punch legacy map isolation must remain enabled")
    if pap_system.get("equalPapExposureRequiresRuntimeReady") is not True:
        fail("EqualPapWeapon must remain gated by PaP runtime readiness")
    expected_legacy_bridge_functions = [
        "IsPapWeapon",
        "EqualNonPapWeapon",
        "EqualPapWeapon",
    ]
    if pap_system.get("nativeLegacyHelperBridgeFunctions") != expected_legacy_bridge_functions:
        fail("Pack-a-Punch legacy-helper bridge function list drift")
    if baseline.get("packAPunchLegacyBridgeFunctions") != 3:
        fail("packAPunchLegacyBridgeFunctions drift")
    if pap_system.get("nativeIdentityResolverStatus") != "ready":
        fail("Pack-a-Punch native identity resolver must remain ready")
    if pap_system.get("nativeIdentityResolverPairs") != 36:
        fail("Pack-a-Punch native identity resolver pair count drift")
    if baseline.get("packAPunchNativeIdentityResolverPairs") != 36:
        fail("packAPunchNativeIdentityResolverPairs drift")
    if pap_system.get("physicalMachinePresentOnNacht") is not False:
        fail("Nacht Chronicles must not claim a physical Pack-a-Punch machine")

    pap_base_set = set(pap_base_ids)

    if baseline.get("catalogWeaponCount") != len(weapons):
        fail(
            f"catalogWeaponCount={baseline.get('catalogWeaponCount')} "
            f"does not match catalog={len(weapons)}"
        )

    required_lanes = contract.get("requiredWeaponLanes")
    if not isinstance(required_lanes, list) or not required_lanes:
        fail("requiredWeaponLanes must be a non-empty list")
    if len(required_lanes) != len(set(required_lanes)):
        fail("requiredWeaponLanes contains duplicates")
    required_lane_set = set(required_lanes)

    for weapon in weapons:
        wid = weapon["weaponId"]
        row = tracked[wid]
        if row.get("displayName") != weapon.get("displayName"):
            fail(f"displayName drift for {wid}")

        lanes = row.get("lanes")
        if not isinstance(lanes, dict):
            fail(f"missing lanes object for {wid}")

        lane_keys = set(lanes)
        missing_lanes = sorted(required_lane_set - lane_keys)
        extra_lanes = sorted(lane_keys - required_lane_set)
        if missing_lanes:
            fail(f"{wid} missing lanes: {missing_lanes}")
        if extra_lanes:
            fail(f"{wid} has unknown lanes: {extra_lanes}")

        for lane, state in lanes.items():
            if state not in ALLOWED_STATES:
                fail(f"{wid}.{lane} has invalid state {state!r}")

        has_wall_behavior_spec = wid in set(spec_ids)
        has_special_behavior_spec = (
            wid == death_machine_spec.get("logicalItemId")
            and death_machine_spec.get("specId") == "bo3_death_machine_powerup_weapon_v1"
        )
        if has_wall_behavior_spec or has_special_behavior_spec:
            if lanes["behavior_spec"] not in {"cataloged", "ready"}:
                fail(
                    f"{wid}.behavior_spec={lanes['behavior_spec']!r} "
                    "but a structured BO3 behavior spec exists"
                )
        elif lanes["behavior_spec"] != "pending":
            fail(
                f"{wid}.behavior_spec={lanes['behavior_spec']!r} "
                "but no structured BO3 behavior spec exists"
            )

        if wid in pap_base_set:
            if lanes["pack_a_punch_identity"] != "ready":
                fail(
                    f"{wid}.pack_a_punch_identity={lanes['pack_a_punch_identity']!r} "
                    "but BO3 prototype exposes a verified upgrade identity"
                )
            if lanes["pack_a_punch_runtime"] != "pending":
                fail(
                    f"{wid}.pack_a_punch_runtime={lanes['pack_a_punch_runtime']!r} "
                    "must remain pending until native PaP runtime is complete"
                )
        elif wid == "special_death_machine":
            if lanes["pack_a_punch_identity"] != "not_applicable":
                fail("Death Machine Pack-a-Punch identity must be not_applicable")
            if lanes["pack_a_punch_runtime"] != "not_applicable":
                fail("Death Machine Pack-a-Punch runtime must be not_applicable")

        if weapon.get("mysteryBoxEligible") and lanes["mystery_box"] == "not_applicable":
            fail(f"{wid} is Mystery Box eligible but marked not_applicable")
        if weapon.get("nachtWallBuyId") and lanes["wall_buy"] == "not_applicable":
            fail(f"{wid} has a Nacht wall-buy id but wall_buy is not_applicable")

        catalog_native = weapon.get("nativeBindingStatus")
        contract_native = row.get("catalogNativeStatus")
        if catalog_native != contract_native:
            fail(
                f"{wid} native status drift: catalog={catalog_native!r} "
                f"contract={contract_native!r}"
            )

    pool_ids = box.get("weaponIds")
    if not isinstance(pool_ids, list):
        fail("global mystery box pool weaponIds must be a list")
    expected_box_ids = [w["weaponId"] for w in weapons if w.get("mysteryBoxEligible")]
    if set(pool_ids) != set(expected_box_ids):
        fail("Mystery Box pool no longer matches catalog eligibility")
    if len(pool_ids) != len(set(pool_ids)):
        fail("Mystery Box pool contains duplicate weapons")

    registry_entries = weapon_id_registry.get("entries", [])
    upgrade_registry_entries = weapon_id_registry.get("upgradeEntries", [])
    if not isinstance(registry_entries, list):
        fail("weapon ID registry entries must be a list")
    if not isinstance(upgrade_registry_entries, list):
        fail("weapon ID registry upgradeEntries must be a list")

    registry_ids = [row.get("weaponId") for row in registry_entries]
    if set(registry_ids) != catalog_set:
        fail("weapon ID registry must cover the complete weapon catalog")

    all_registry_rows = registry_entries + upgrade_registry_entries
    native_ids = [row.get("nativeId") for row in all_registry_rows]
    mbox_tokens = [row.get("mboxToken") for row in all_registry_rows]
    defines = [row.get("nativeSymbol") for row in all_registry_rows]
    if len(native_ids) != len(set(native_ids)):
        fail("base + PaP registry contains duplicate native IDs")
    if len(mbox_tokens) != len(set(mbox_tokens)):
        fail("base + PaP registry contains duplicate tokens")
    if len(defines) != len(set(defines)):
        fail("base + PaP registry contains duplicate native symbols")

    registry_by_id = {row["weaponId"]: row for row in registry_entries}
    if registry_by_id.get("pistol_burst", {}).get("nativeId") != 70:
        fail("RK5 stable XZIEL native ID must remain pinned to 70")
    if baseline.get("weaponIdRegistryCount") != len(registry_entries):
        fail("weaponIdRegistryCount drift")

    if len(upgrade_registry_entries) != 35:
        fail(f"expected 35 dedicated PaP registry IDs, got {len(upgrade_registry_entries)}")
    dedicated_upgrade_ids = [row.get("upgradeWeaponId") for row in upgrade_registry_entries]
    expected_dedicated_upgrades = {
        row["upgradeWeaponId"]
        for row in pap_variants
        if row["upgradeWeaponId"] != "cymbal_monkey_upgraded"
    }
    if set(dedicated_upgrade_ids) != expected_dedicated_upgrades:
        fail("dedicated PaP registry identity set drift")
    dedicated_native_ids = sorted(row.get("nativeId") for row in upgrade_registry_entries)
    if dedicated_native_ids != list(range(160, 195)):
        fail(f"dedicated PaP registry ID range drift: {dedicated_native_ids}")
    if baseline.get("packAPunchDedicatedNativeIdCount") != 35:
        fail("packAPunchDedicatedNativeIdCount drift")
    if baseline.get("packAPunchReusedCatalogIdCount") != 1:
        fail("packAPunchReusedCatalogIdCount drift")
    if "cymbal_monkey_upgraded" not in registry_by_id:
        fail("cymbal_monkey_upgraded must remain a reused catalog identity")

    if runtime_box_pool.get("candidateCount") != len(pool_ids):
        fail("runtime Mystery Box candidateCount drift")
    if baseline.get("mysteryBoxCandidateCount") != len(pool_ids):
        fail("mysteryBoxCandidateCount baseline drift")
    capacity = baseline.get("mysteryBoxRuntimeCapacity")
    if not isinstance(capacity, int) or capacity < len(pool_ids) or capacity != 64:
        fail(f"invalid Mystery Box runtime capacity: {capacity!r}")

    active_rows = runtime_box_pool.get("active", [])
    blocked_rows = runtime_box_pool.get("blocked", [])
    if not isinstance(active_rows, list) or not isinstance(blocked_rows, list):
        fail("runtime Mystery Box active/blocked rows must be lists")
    active_ids = [row.get("weaponId") for row in active_rows]
    blocked_ids = [row.get("weaponId") for row in blocked_rows]
    if set(active_ids) & set(blocked_ids):
        fail("runtime Mystery Box weapon cannot be both active and blocked")
    if set(active_ids) | set(blocked_ids) != set(pool_ids):
        fail("runtime Mystery Box active+blocked coverage must equal identity pool")
    if runtime_box_pool.get("activeCount") != len(active_rows):
        fail("runtime Mystery Box activeCount drift")
    if runtime_box_pool.get("blockedCount") != len(blocked_rows):
        fail("runtime Mystery Box blockedCount drift")

    runtime_required_lanes = runtime_box_pool.get("requiredLanes", [])
    if not isinstance(runtime_required_lanes, list) or not runtime_required_lanes:
        fail("runtime Mystery Box requiredLanes must be a non-empty list")

    catalog_by_id = {w["weaponId"]: w for w in weapons}
    expected_active_ids = []
    for wid in pool_ids:
        weapon = catalog_by_id[wid]
        lane_states = tracked[wid]["lanes"]
        native_ready = weapon.get("nativeBindingStatus") == "ready"
        lanes_ready = all(
            lane_states.get(lane) in COMPLETE_STATES
            for lane in runtime_required_lanes
        )
        if native_ready and lanes_ready:
            expected_active_ids.append(wid)

    if active_ids != expected_active_ids:
        fail(
            "runtime Mystery Box active list does not match readiness gates: "
            f"expected={expected_active_ids} actual={active_ids}"
        )

    mystery_system = contract.get("requiredSystems", {}).get(
        "mystery_box_full_pool_and_teddy_flow", {}
    )
    if mystery_system.get("runtimeCapacity") != capacity:
        fail("Mystery Box system runtimeCapacity drift")
    if mystery_system.get("candidateWeaponIdentities") != len(pool_ids):
        fail("Mystery Box system candidate count drift")
    if mystery_system.get("runtimeReadyRewards") != len(active_ids):
        fail("Mystery Box system active reward count drift")

    if baseline.get("runtimePurchases") != len(runtime.get("purchases", [])):
        fail("runtime purchase count drift")
    if baseline.get("doors") != len(runtime.get("doors", [])):
        fail("door count drift")
    if baseline.get("barricades") != len(runtime.get("barricades", [])):
        fail("barricade count drift")
    if baseline.get("zombieSpawns") != len(runtime.get("zombieSpawns", [])):
        fail("zombie spawn count drift")
    if baseline.get("playerSpawns") != len(runtime.get("playerSpawns", [])):
        fail("player spawn count drift")
    if baseline.get("maxPlayers") != runtime.get("runtimePolicy", {}).get("maximumPlayers"):
        fail("maximumPlayers drift")
    if baseline.get("roundSoakTarget") != 100:
        fail("roundSoakTarget must remain 100 for the engine acceptance target")

    systems = contract.get("requiredSystems")
    if not isinstance(systems, dict):
        fail("requiredSystems must be an object")
    if set(systems) != REQUIRED_SYSTEMS:
        missing_systems = sorted(REQUIRED_SYSTEMS - set(systems))
        extra_systems = sorted(set(systems) - REQUIRED_SYSTEMS)
        fail(
            f"requiredSystems mismatch missing={missing_systems} extra={extra_systems}"
        )
    for sid, row in systems.items():
        state = row.get("state") if isinstance(row, dict) else None
        if state not in ALLOWED_STATES:
            fail(f"system {sid} has invalid state {state!r}")

    feature_ref = contract.get("bo3ChroniclesFeatureReference", {})
    if feature_ref.get("mysteryBox") is not True:
        fail("BO3 Nacht must track the Mystery Box")
    if feature_ref.get("gobbleGumMachines") != 2:
        fail("BO3 Nacht contract must track both GobbleGum machines")
    if feature_ref.get("derWunderfizz") is not True:
        fail("BO3 Nacht contract must track Der Wunderfizz")
    if feature_ref.get("muleKick") is not True:
        fail("BO3 Nacht contract must track Mule Kick")
    if feature_ref.get("packAPunchMachinePresent") is not False:
        fail("Nacht must not invent a physical Pack-a-Punch machine")
    if feature_ref.get("packAPunchWeaponVariantsStillRequired") is not True:
        fail("Pack-a-Punch weapon variants must remain tracked")

    if contract["releaseCandidate"]:
        incomplete = []
        for sid, row in systems.items():
            if row["state"] not in COMPLETE_STATES:
                incomplete.append(f"system:{sid}={row['state']}")
        for wid, row in tracked.items():
            for lane, state in row["lanes"].items():
                if state not in COMPLETE_STATES:
                    incomplete.append(f"weapon:{wid}:{lane}={state}")
        if incomplete:
            preview = ", ".join(incomplete[:25])
            suffix = "" if len(incomplete) <= 25 else f" ... +{len(incomplete)-25} more"
            fail(
                "releaseCandidate=true while incomplete work remains: "
                + preview
                + suffix
            )

    states = {}
    for row in tracked.values():
        for state in row["lanes"].values():
            states[state] = states.get(state, 0) + 1

    system_states = {}
    for row in systems.values():
        state = row["state"]
        system_states[state] = system_states.get(state, 0) + 1

    print(
        "NACHT_COMPLETION_CONTRACT_OK",
        {
            "weapons": len(weapons),
            "box": len(pool_ids),
            "runtimeBoxActive": len(active_ids),
            "weaponIdRegistry": len(registry_entries),
            "weaponLaneStates": states,
            "systemStates": system_states,
            "releaseCandidate": contract["releaseCandidate"],
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
