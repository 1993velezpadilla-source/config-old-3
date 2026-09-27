#!/usr/bin/env python3
"""Add a stable XZIEL semantic bridge for BO3-style perk/power-up systems.

Higher-level XZIEL systems (Wunderfizz, GobbleGum, scripted rewards) should call
these helpers rather than depend directly on NZ:P's internal numeric IDs.

This bridge reuses upstream primitives where they exist and adds bounded XZIEL
logic primitives where safe. Widow's Wine and Death Machine remain unsupported.
Fire Sale receives a logic-only timer/cost primitive here; its pickup model,
jingle and multi-location presentation remain separately gated.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_quakec_xziel_zombies_runtime_bridge.py <quakec-root>")

root = Path(sys.argv[1])
custom_path = root / "source/server/defs/custom.qc"
power_path = root / "source/server/entities/powerups.qc"
perk_path = root / "source/server/entities/perk_a_cola.qc"

custom = custom_path.read_text(encoding="utf-8")
power = power_path.read_text(encoding="utf-8")
perk = perk_path.read_text(encoding="utf-8")

if "// XZIEL_GOBBLEGUM_PLAYER_STATE_BEGIN" not in custom:
    custom += r'''

// XZIEL_GOBBLEGUM_PLAYER_STATE_BEGIN
// Shared semantic power-up IDs live in defs because perk_a_cola.qc is compiled
// before powerups.qc in upstream ssqc.src.
#define XZIEL_PU_NUKE          1
#define XZIEL_PU_INSTAKILL     2
#define XZIEL_PU_DOUBLEPOINTS  3
#define XZIEL_PU_CARPENTER     4
#define XZIEL_PU_MAXAMMO       5
#define XZIEL_PU_RANDOMPERK    6
#define XZIEL_PU_BONUSPOINTS   7
#define XZIEL_PU_FIRESALE      8
#define XZIEL_PU_DEATHMACHINE  9

// Forward declarations for the later-compiled powerups.qc bridge.
float() XZIEL_FireSaleLogicActive;
float(vector where, float semantic_id) XZIEL_SpawnCorePowerup;

.float xziel_gum_round;
.float xziel_gum_uses_this_round;
.float xziel_gum_bag_mask;
.float xziel_gum_held_identity;
.float xziel_gum_held_uses_remaining;
.float xziel_gum_slot1;
.float xziel_gum_slot2;
.float xziel_gum_slot3;
.float xziel_gum_slot4;
.float xziel_gum_slot5;
// XZIEL_GOBBLEGUM_PLAYER_STATE_END
'''

power_marker = "// XZIEL_ZOMBIES_POWERUP_BRIDGE_BEGIN"
if power_marker not in power:
    power += r'''

// XZIEL_ZOMBIES_POWERUP_BRIDGE_BEGIN
// Stable semantic IDs are declared in defs/custom.qc so earlier-compiled
// perk/GobbleGum code can reference them safely.

float(float semantic_id) XZIEL_CorePowerupSupported =
{
    switch (semantic_id) {
        case XZIEL_PU_NUKE:
        case XZIEL_PU_INSTAKILL:
        case XZIEL_PU_DOUBLEPOINTS:
        case XZIEL_PU_CARPENTER:
        case XZIEL_PU_MAXAMMO:
        case XZIEL_PU_RANDOMPERK:
        case XZIEL_PU_BONUSPOINTS:
        case XZIEL_PU_FIRESALE:
            return true;
        default:
            return false;
    }
};

float(float semantic_id) XZIEL_CorePowerupNativeId =
{
    switch (semantic_id) {
        case XZIEL_PU_NUKE: return PU_NUKE;
        case XZIEL_PU_INSTAKILL: return PU_INSTAKILL;
        case XZIEL_PU_DOUBLEPOINTS: return PU_DOUBLEPTS;
        case XZIEL_PU_CARPENTER: return PU_CARPENTER;
        case XZIEL_PU_MAXAMMO: return PU_MAXAMMO;
        case XZIEL_PU_RANDOMPERK: return PU_FREEPERK;
        case XZIEL_PU_BONUSPOINTS: return PU_BONUSPOINTS;
        default: return -1;
    }
};

float(vector where, float semantic_id) XZIEL_SpawnCorePowerup =
{
    float native_id = XZIEL_CorePowerupNativeId(semantic_id);
    if (native_id < 0)
        return false;

    Spawn_Powerup(where, native_id);
    return true;
};

// XZIEL Fire Sale logic primitive. BO3 behavior is a 30 second sale with
// Mystery Box rolls costing 10 points. Presentation/all-spawn behavior is
// intentionally not claimed by this logic-only helper.
float xziel_fire_sale_finished;
float xziel_fire_sale_restore_cost;

void() XZIEL_FireSaleWatcher =
{
    if (time < xziel_fire_sale_finished) {
        mystery_box_cost = 10;
        self.nextthink = time + 0.10;
        return;
    }

    if (xziel_fire_sale_restore_cost > 0)
        mystery_box_cost = xziel_fire_sale_restore_cost;
    else
        mystery_box_cost = 950;

    xziel_fire_sale_finished = 0;
    xziel_fire_sale_restore_cost = 0;
    remove(self);
};

float() XZIEL_StartFireSaleLogic =
{
    if (xziel_fire_sale_finished <= time) {
        xziel_fire_sale_restore_cost = mystery_box_cost;
        if (xziel_fire_sale_restore_cost <= 0)
            xziel_fire_sale_restore_cost = 950;
    }

    xziel_fire_sale_finished = time + 30;
    mystery_box_cost = 10;

    entity watcher = find(world, classname, "xziel_fire_sale_watcher");
    if (watcher == world) {
        watcher = spawn();
        watcher.classname = "xziel_fire_sale_watcher";
        watcher.think = XZIEL_FireSaleWatcher;
        watcher.nextthink = time + 0.10;
    }

    return true;
};

float() XZIEL_FireSaleLogicActive =
{
    return xziel_fire_sale_finished > time;
};

float() XZIEL_PackAPunchGrantPrimitiveSupported =
{
    return true;
};

float(vector where) XZIEL_SpawnPackAPunchGrant =
{
    Spawn_Powerup(where, PU_UPGRADEWEAPON);
    return true;
};
// XZIEL_ZOMBIES_POWERUP_BRIDGE_END
'''

perk_marker = "// XZIEL_ZOMBIES_PERK_BRIDGE_BEGIN"
if perk_marker not in perk:
    perk += r'''

// XZIEL_ZOMBIES_PERK_BRIDGE_BEGIN
#define XZIEL_PERK_MULEKICK    1
#define XZIEL_PERK_JUGGERNOG   2
#define XZIEL_PERK_QUICKREVIVE 3
#define XZIEL_PERK_SPEEDCOLA   4
#define XZIEL_PERK_DOUBLETAP2  5
#define XZIEL_PERK_STAMINUP    6
#define XZIEL_PERK_DEADSHOT    7
#define XZIEL_PERK_WIDOWSWINE  8

float(float semantic_id) XZIEL_PerkSupported =
{
    switch (semantic_id) {
        case XZIEL_PERK_MULEKICK:
        case XZIEL_PERK_JUGGERNOG:
        case XZIEL_PERK_QUICKREVIVE:
        case XZIEL_PERK_SPEEDCOLA:
        case XZIEL_PERK_DOUBLETAP2:
        case XZIEL_PERK_STAMINUP:
        case XZIEL_PERK_DEADSHOT:
            return true;
        default:
            return false;
    }
};

float(float semantic_id) XZIEL_PerkNativeBit =
{
    switch (semantic_id) {
        case XZIEL_PERK_MULEKICK: return P_MULE;
        case XZIEL_PERK_JUGGERNOG: return P_JUG;
        case XZIEL_PERK_QUICKREVIVE: return P_REVIVE;
        case XZIEL_PERK_SPEEDCOLA: return P_SPEED;
        case XZIEL_PERK_DOUBLETAP2: return P_DOUBLE;
        case XZIEL_PERK_STAMINUP: return P_STAMIN;
        case XZIEL_PERK_DEADSHOT: return P_DEAD;
        default: return 0;
    }
};

float(entity player, float semantic_id) XZIEL_PlayerHasPerk =
{
    float perk_bit = XZIEL_PerkNativeBit(semantic_id);
    if (!perk_bit)
        return false;
    return (player.perks & perk_bit) != 0;
};

// Logic-only grant used by scripted reward systems. Presentation-aware systems
// should still route through the drink/machine sequence before calling this.
float(entity player, float semantic_id) XZIEL_GrantPerkLogic =
{
    float perk_bit = XZIEL_PerkNativeBit(semantic_id);
    if (!perk_bit || player == world || player.classname != "player")
        return false;
    if (player.perks & perk_bit)
        return false;

    entity old_self = self;
    self = player;
    GivePerk(perk_bit);
    self = old_self;
    return true;
};
float(entity player) XZIEL_WunderfizzEligiblePerkCount =
{
    if (player == world || player.classname != "player")
        return 0;
    if (Player_GetNumPerks(player) >= game_modifiers.gameplay.perksacola.perk_purchase_limit)
        return 0;

    float count = 0;
    // BO3 Nacht Wunderfizz pool excludes standalone Mule Kick.
    for (float semantic_id = XZIEL_PERK_JUGGERNOG; semantic_id <= XZIEL_PERK_WIDOWSWINE; semantic_id++) {
        if (XZIEL_PerkSupported(semantic_id) && !XZIEL_PlayerHasPerk(player, semantic_id))
            count++;
    }
    return count;
};

float(entity player) XZIEL_WunderfizzPickSupportedPerk =
{
    float eligible = XZIEL_WunderfizzEligiblePerkCount(player);
    if (eligible <= 0)
        return 0;

    float target = floor(random() * eligible);
    if (target >= eligible)
        target = eligible - 1;

    float seen = 0;
    for (float semantic_id = XZIEL_PERK_JUGGERNOG; semantic_id <= XZIEL_PERK_WIDOWSWINE; semantic_id++) {
        if (!XZIEL_PerkSupported(semantic_id) || XZIEL_PlayerHasPerk(player, semantic_id))
            continue;
        if (seen == target)
            return semantic_id;
        seen++;
    }
    return 0;
};

float(entity player) XZIEL_WunderfizzGrantLogic =
{
    float semantic_id = XZIEL_WunderfizzPickSupportedPerk(player);
    if (!semantic_id)
        return false;
    return XZIEL_GrantPerkLogic(player, semantic_id);
};

// Gameplay-first BO3 Nacht Wunderfizz machine. This intentionally has no
// presentation model yet: the visual/material phase owns that independently.
// It charges only after a supported perk grant succeeds, preventing point loss
// while Widow's Wine remains gated behind its missing native feature.
void() XZIEL_WunderfizzTouch =
{
    float price;
    float semantic_id;

    if (other.classname != "player" || other.downed || other.isBuying == true || !PlayerIsLooking(other, self))
        return;

    if (Player_GetNumPerks(other) >= game_modifiers.gameplay.perksacola.perk_purchase_limit)
        return;

    price = floor(self.cost * game_modifiers.gameplay.global.all_items_cost_multiplier);
    other.useprint_touch = self.name;
    Player_UseprintWithWait(other, self, self.useprint_index_1, price);

    if (!Player_UseButtonPressed(other, self) || (other.semi_actions & SEMIACTION_USE))
        return;

    other.semi_actions |= SEMIACTION_USE;

    if (other.points < price) {
        centerprint(other, STR_NOTENOUGHPOINTS);
        Sound_PlaySound(other, "sounds/misc/denybuy.wav", SOUND_TYPE_ENV_CHING, SOUND_PRIORITY_PLAYALWAYS);
        return;
    }

    semantic_id = XZIEL_WunderfizzPickSupportedPerk(other);
    if (!semantic_id) {
        centerprint(other, "No supported Wunderfizz perks remain");
        Sound_PlaySound(other, "sounds/misc/denybuy.wav", SOUND_TYPE_ENV_CHING, SOUND_PRIORITY_PLAYALWAYS);
        return;
    }

    if (!XZIEL_GrantPerkLogic(other, semantic_id))
        return;

    Player_RemoveScore(other, price);
    Sound_PlaySound(self, "sounds/machines/vend.wav", SOUND_TYPE_ENV_CHING, SOUND_PRIORITY_PLAYALWAYS);
};

void() xziel_wunderfizz =
{
    if (!self.name)
        self.name = "Der Wunderfizz";
    if (!self.cost)
        self.cost = 1500;
    if (!self.useprint_string_1)
        self.useprint_string_1 = "Hold %b for Der Wunderfizz";

    precache_sound("sounds/machines/vend.wav");
    precache_sound("sounds/misc/denybuy.wav");

    self.movetype = MOVETYPE_NONE;
    self.solid = SOLID_TRIGGER;
    setorigin(self, self.origin);
    setsize(self, VEC_HULL2_MIN, VEC_HULL2_MAX);
    self.classname = "xziel_wunderfizz";
    self.touch = XZIEL_WunderfizzTouch;
    self.useprint_index_1 = Useprint_Register(self.useprint_string_1, self.useprint_color_1);
};


#define XZIEL_GOBBLEGUM_IDENTITY_COUNT 63
#define XZIEL_GOBBLEGUM_PACK_SIZE      5
#define XZIEL_GOBBLEGUM_MAX_ROLLS      3

void(entity player) XZIEL_GobbleGumSyncRound =
{
    if (player.xziel_gum_round != rounds) {
        player.xziel_gum_round = rounds;
        player.xziel_gum_uses_this_round = 0;
    }
};

float(float round_number) XZIEL_GobbleGumSecondUseBasePrice =
{
    // Zombies Chronicles online-era schedule:
    // R1-9 1500, R10-19 2500, ... capped at R100+ 1,024,500.
    float tier = floor(round_number / 10);
    if (tier < 0)
        tier = 0;
    if (tier > 10)
        tier = 10;

    float price = 1500;
    for (float i = 0; i < tier; i++)
        price = (price * 2) - 500;

    return price;
};

float(entity player) XZIEL_GobbleGumCurrentPrice =
{
    if (player == world || player.classname != "player")
        return -1;

    XZIEL_GobbleGumSyncRound(player);

    if (player.xziel_gum_uses_this_round >= XZIEL_GOBBLEGUM_MAX_ROLLS)
        return -1;

    float price = 0;
    if (player.xziel_gum_uses_this_round == 1)
        price = XZIEL_GobbleGumSecondUseBasePrice(rounds);
    else if (player.xziel_gum_uses_this_round == 2)
        price = XZIEL_GobbleGumSecondUseBasePrice(rounds) * 2;

    // BO3 Fire Sale reduces GobbleGum machine prices by 490, clamped at zero.
    if (XZIEL_FireSaleLogicActive()) {
        price -= 490;
        if (price < 0)
            price = 0;
    }

    return price;
};

float(entity player, float a, float b, float c, float d, float e) XZIEL_GobbleGumConfigureLoadout =
{
    if (player == world || player.classname != "player")
        return false;

    if (a < 1 || a > XZIEL_GOBBLEGUM_IDENTITY_COUNT ||
        b < 1 || b > XZIEL_GOBBLEGUM_IDENTITY_COUNT ||
        c < 1 || c > XZIEL_GOBBLEGUM_IDENTITY_COUNT ||
        d < 1 || d > XZIEL_GOBBLEGUM_IDENTITY_COUNT ||
        e < 1 || e > XZIEL_GOBBLEGUM_IDENTITY_COUNT)
        return false;

    if (a == b || a == c || a == d || a == e ||
        b == c || b == d || b == e ||
        c == d || c == e || d == e)
        return false;

    player.xziel_gum_slot1 = a;
    player.xziel_gum_slot2 = b;
    player.xziel_gum_slot3 = c;
    player.xziel_gum_slot4 = d;
    player.xziel_gum_slot5 = e;
    player.xziel_gum_bag_mask = 0;
    player.xziel_gum_held_identity = 0;
    player.xziel_gum_held_uses_remaining = 0;
    player.xziel_gum_round = rounds;
    player.xziel_gum_uses_this_round = 0;
    return true;
};

float(entity player, float slot) XZIEL_GobbleGumIdentityAtSlot =
{
    switch (slot) {
        case 0: return player.xziel_gum_slot1;
        case 1: return player.xziel_gum_slot2;
        case 2: return player.xziel_gum_slot3;
        case 3: return player.xziel_gum_slot4;
        case 4: return player.xziel_gum_slot5;
    }
    return 0;
};

float(float slot) XZIEL_GobbleGumSlotMask =
{
    switch (slot) {
        case 0: return 1;
        case 1: return 2;
        case 2: return 4;
        case 3: return 8;
        case 4: return 16;
    }
    return 0;
};

float(entity player) XZIEL_GobbleGumRollIdentity =
{
    if (player == world || player.classname != "player")
        return 0;

    XZIEL_GobbleGumSyncRound(player);
    if (player.xziel_gum_uses_this_round >= XZIEL_GOBBLEGUM_MAX_ROLLS)
        return 0;

    // All five configured identities must be valid before the machine can roll.
    for (float slot = 0; slot < XZIEL_GOBBLEGUM_PACK_SIZE; slot++) {
        float identity = XZIEL_GobbleGumIdentityAtSlot(player, slot);
        if (identity < 1 || identity > XZIEL_GOBBLEGUM_IDENTITY_COUNT)
            return 0;
    }

    // Five-entry shuffle bag: consume every configured gum once before repeats.
    if (player.xziel_gum_bag_mask >= 31)
        player.xziel_gum_bag_mask = 0;

    float available = 0;
    for (float slot = 0; slot < XZIEL_GOBBLEGUM_PACK_SIZE; slot++) {
        float mask = XZIEL_GobbleGumSlotMask(slot);
        if (!(player.xziel_gum_bag_mask & mask))
            available++;
    }
    if (available <= 0)
        return 0;

    float target = floor(random() * available);
    if (target >= available)
        target = available - 1;

    float seen = 0;
    for (float slot = 0; slot < XZIEL_GOBBLEGUM_PACK_SIZE; slot++) {
        float mask = XZIEL_GobbleGumSlotMask(slot);
        if (player.xziel_gum_bag_mask & mask)
            continue;

        if (seen == target) {
            float identity = XZIEL_GobbleGumIdentityAtSlot(player, slot);
            player.xziel_gum_bag_mask = player.xziel_gum_bag_mask | mask;
            player.xziel_gum_uses_this_round++;
            player.xziel_gum_held_identity = identity;
            player.xziel_gum_held_uses_remaining = 0;
            return identity;
        }
        seen++;
    }

    return 0;
};

float(entity player) XZIEL_GobbleGumRollsRemaining =
{
    XZIEL_GobbleGumSyncRound(player);
    float remaining = XZIEL_GOBBLEGUM_MAX_ROLLS - player.xziel_gum_uses_this_round;
    if (remaining < 0)
        remaining = 0;
    return remaining;
};

// First BO3 GobbleGum effect primitives that map directly to existing
// XZIEL/NZ:P power-up pickups. Identity numbers match the committed 63-entry
// GobbleGum catalog and remain stable.
#define XZIEL_GUM_CACHE_BACK              12
#define XZIEL_GUM_DEAD_NUCLEAR_WINTER     17
#define XZIEL_GUM_KILL_JOY                 32
#define XZIEL_GUM_LICENSED_CONTRACTOR      34
#define XZIEL_GUM_ON_THE_HOUSE             40
#define XZIEL_GUM_WHOS_KEEPING_SCORE       63

float(float gum_identity) XZIEL_GobbleGumMappedPowerupSemantic =
{
    switch (gum_identity) {
        case XZIEL_GUM_CACHE_BACK: return XZIEL_PU_MAXAMMO;
        case XZIEL_GUM_DEAD_NUCLEAR_WINTER: return XZIEL_PU_NUKE;
        case XZIEL_GUM_KILL_JOY: return XZIEL_PU_INSTAKILL;
        case XZIEL_GUM_LICENSED_CONTRACTOR: return XZIEL_PU_CARPENTER;
        case XZIEL_GUM_ON_THE_HOUSE: return XZIEL_PU_RANDOMPERK;
        case XZIEL_GUM_WHOS_KEEPING_SCORE: return XZIEL_PU_DOUBLEPOINTS;
        default: return 0;
    }
};

float(float gum_identity) XZIEL_GobbleGumMappedActivationCount =
{
    switch (gum_identity) {
        case XZIEL_GUM_CACHE_BACK: return 1;
        case XZIEL_GUM_DEAD_NUCLEAR_WINTER: return 2;
        case XZIEL_GUM_KILL_JOY: return 2;
        case XZIEL_GUM_LICENSED_CONTRACTOR: return 3;
        case XZIEL_GUM_ON_THE_HOUSE: return 1;
        case XZIEL_GUM_WHOS_KEEPING_SCORE: return 2;
        default: return 0;
    }
};

float(entity player, float gum_identity) XZIEL_GobbleGumSpawnMappedPowerup =
{
    if (player == world || player.classname != "player")
        return false;

    float semantic_id = XZIEL_GobbleGumMappedPowerupSemantic(gum_identity);
    if (!semantic_id)
        return false;

    return XZIEL_SpawnCorePowerup(player.origin, semantic_id);
};

float(entity player) XZIEL_GobbleGumActivateHeldMappedPowerup =
{
    if (player == world || player.classname != "player")
        return false;

    float gum_identity = player.xziel_gum_held_identity;
    if (!gum_identity)
        return false;

    float max_uses = XZIEL_GobbleGumMappedActivationCount(gum_identity);
    if (max_uses <= 0)
        return false;

    if (player.xziel_gum_held_uses_remaining <= 0)
        player.xziel_gum_held_uses_remaining = max_uses;

    if (!XZIEL_GobbleGumSpawnMappedPowerup(player, gum_identity))
        return false;

    player.xziel_gum_held_uses_remaining--;

    if (player.xziel_gum_held_uses_remaining <= 0) {
        player.xziel_gum_held_uses_remaining = 0;
        player.xziel_gum_held_identity = 0;
    }

    return true;
};

float(entity player) XZIEL_GobbleGumHeldUsesRemaining =
{
    if (player == world || player.classname != "player")
        return 0;

    if (!player.xziel_gum_held_identity)
        return 0;

    if (player.xziel_gum_held_uses_remaining > 0)
        return player.xziel_gum_held_uses_remaining;

    return XZIEL_GobbleGumMappedActivationCount(player.xziel_gum_held_identity);
};

// XZIEL_ZOMBIES_PERK_BRIDGE_END
'''

for text, begin, end in (
    (power, power_marker, "// XZIEL_ZOMBIES_POWERUP_BRIDGE_END"),
    (perk, perk_marker, "// XZIEL_ZOMBIES_PERK_BRIDGE_END"),
):
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit(f"runtime bridge marker mismatch: {begin}")

required_power = [
    "XZIEL_CorePowerupSupported",
    "XZIEL_CorePowerupNativeId",
    "XZIEL_SpawnCorePowerup",
    "XZIEL_SpawnPackAPunchGrant",
    "XZIEL_StartFireSaleLogic",
    "XZIEL_FireSaleLogicActive",
]
for token in required_power:
    if power.count(token) < 1:
        raise SystemExit(f"missing power-up bridge token: {token}")

required_perk = [
    "XZIEL_PerkSupported",
    "XZIEL_PerkNativeBit",
    "XZIEL_PlayerHasPerk",
    "XZIEL_GrantPerkLogic",
    "XZIEL_WunderfizzEligiblePerkCount",
    "XZIEL_WunderfizzPickSupportedPerk",
    "XZIEL_WunderfizzGrantLogic",
    "XZIEL_WunderfizzTouch",
    "void() xziel_wunderfizz",
    "XZIEL_GobbleGumSecondUseBasePrice",
    "XZIEL_GobbleGumCurrentPrice",
    "XZIEL_GobbleGumConfigureLoadout",
    "XZIEL_GobbleGumRollIdentity",
    "XZIEL_GobbleGumRollsRemaining",
    "XZIEL_GobbleGumMappedPowerupSemantic",
    "XZIEL_GobbleGumMappedActivationCount",
    "XZIEL_GobbleGumSpawnMappedPowerup",
    "XZIEL_GobbleGumActivateHeldMappedPowerup",
    "XZIEL_GobbleGumHeldUsesRemaining",
]
for token in required_perk:
    if perk.count(token) < 1:
        raise SystemExit(f"missing perk bridge token: {token}")

if custom.count("// XZIEL_GOBBLEGUM_PLAYER_STATE_BEGIN") != 1 or custom.count("// XZIEL_GOBBLEGUM_PLAYER_STATE_END") != 1:
    raise SystemExit("GobbleGum player-state marker mismatch")

custom_path.write_text(custom, encoding="utf-8")
power_path.write_text(power, encoding="utf-8")
perk_path.write_text(perk, encoding="utf-8")
print("Applied XZIEL Zombies bridge (7 perks, Wunderfizz trigger, 7 upstream power-ups, Fire Sale logic, PaP grant, GobbleGum economy/bag core).")
