#pragma once

#include "ctw_patch.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CTW_CHARACTER_PART_HEAD = 0,
    CTW_CHARACTER_PART_FACE = 1,
    CTW_CHARACTER_PART_TORSO = 2,
    CTW_CHARACTER_PART_ARMS = 3,
    CTW_CHARACTER_PART_LEGS = 4,
    CTW_CHARACTER_PART_WEAPON = 5,
    CTW_CHARACTER_PART_OTHER = 6,
} CtwCharacterPart;

typedef enum {
    CTW_VISIBILITY_PRESERVE = -1,
    CTW_VISIBILITY_HIDE = 0,
    CTW_VISIBILITY_SHOW = 1,
} CtwVisibilityOverride;

/*
 * Returns a visibility override for the local player's render part.
 * PRESERVE means the stock engine decision should be left untouched.
 */
CtwVisibilityOverride ctw_character_visibility_override(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    CtwCharacterPart part
);

#ifdef __cplusplus
}
#endif
