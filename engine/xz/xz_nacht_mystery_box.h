#ifndef XZ_NACHT_MYSTERY_BOX_H
#define XZ_NACHT_MYSTERY_BOX_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_NACHT_MYSTERY_BOX_COST 950u
#define XZ_NACHT_MYSTERY_BOX_POOL_COUNT 34u
#define XZ_NACHT_MYSTERY_BOX_MOVABLE 0

typedef struct XzNachtMysteryBoxEntry {
    const char *weapon_id;
    const char *upgrade_id;
    uint8_t source_is_limited;
    uint8_t quota_defined;
    uint32_t quota;
} XzNachtMysteryBoxEntry;

typedef uint32_t (*XzNachtMysteryBoxRandomBelowFn)(
    void *context,
    uint32_t upper_exclusive);

typedef int (*XzNachtMysteryBoxWeaponPredicateFn)(
    void *context,
    const char *weapon_id);

typedef uint32_t (*XzNachtMysteryBoxLimitedCountFn)(
    void *context,
    const char *weapon_id);

typedef struct XzNachtMysteryBoxSelectionContext {
    void *user_context;
    XzNachtMysteryBoxRandomBelowFn random_below;
    XzNachtMysteryBoxWeaponPredicateFn owns_weapon_or_upgrade;
    XzNachtMysteryBoxLimitedCountFn limited_occupancy;
    XzNachtMysteryBoxWeaponPredicateFn content_allowed;
    XzNachtMysteryBoxWeaponPredicateFn special_allowed;
    XzNachtMysteryBoxWeaponPredicateFn native_ready;
    int require_native_ready;
} XzNachtMysteryBoxSelectionContext;

typedef struct XzNachtMysteryBoxSelection {
    const XzNachtMysteryBoxEntry *entry;
    uint8_t used_unfiltered_fallback;
} XzNachtMysteryBoxSelection;

typedef struct XzNachtMysteryBoxState {
    uint32_t completed_uses;
    uint8_t busy;
} XzNachtMysteryBoxState;

typedef enum XzNachtMysteryBoxResult {
    XZ_NACHT_MYSTERY_BOX_OK = 0,
    XZ_NACHT_MYSTERY_BOX_INVALID_ARGUMENT,
    XZ_NACHT_MYSTERY_BOX_RNG_OUT_OF_RANGE,
    XZ_NACHT_MYSTERY_BOX_INSUFFICIENT_POINTS,
    XZ_NACHT_MYSTERY_BOX_BUSY,
    XZ_NACHT_MYSTERY_BOX_NO_ELIGIBLE_NATIVE_WEAPON
} XzNachtMysteryBoxResult;

size_t XzNachtMysteryBox_Count(void);

const XzNachtMysteryBoxEntry *XzNachtMysteryBox_Get(
    size_t index);

int XzNachtMysteryBox_IsEligible(
    const XzNachtMysteryBoxEntry *entry,
    const XzNachtMysteryBoxSelectionContext *context);

XzNachtMysteryBoxResult XzNachtMysteryBox_Select(
    const XzNachtMysteryBoxSelectionContext *context,
    XzNachtMysteryBoxSelection *selection_out);

void XzNachtMysteryBox_Reset(
    XzNachtMysteryBoxState *state);

XzNachtMysteryBoxResult XzNachtMysteryBox_TryRoll(
    XzNachtMysteryBoxState *state,
    uint32_t *player_points,
    const XzNachtMysteryBoxSelectionContext *context,
    XzNachtMysteryBoxSelection *selection_out);

void XzNachtMysteryBox_CompleteRoll(
    XzNachtMysteryBoxState *state);

int XzNachtMysteryBox_SelfTest(void);

const char *XzNachtMysteryBox_ResultName(
    XzNachtMysteryBoxResult result);

#ifdef __cplusplus
}
#endif

#endif
