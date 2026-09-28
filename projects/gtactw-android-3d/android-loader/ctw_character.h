#pragma once

#include "ctw_patch.h"

#include <stdint.h>

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

/*
 * Build a horizontal fixed-point forward vector that faces an in-world ped
 * sprite toward the active 3D camera. Returns 1 when adjusted, 0 when the
 * camera is too close and the stock forward vector should be preserved.
 */
int ctw_character_camera_facing_forward(
    int32_t ped_x,
    int32_t ped_y,
    int32_t camera_x,
    int32_t camera_y,
    const int16_t original_forward[3],
    int16_t out_forward[3]
);

/*
 * CTW's four ped BodyType buckets have fixed Z anchors 2.0, 1.5, 1.0, 0.5.
 * BodyType 0 is therefore the highest/head layer. Only suppress it for the
 * local player in first-person; never suppress it for world NPCs.
 */
int ctw_character_hide_body_type(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    int is_local_player_sprite,
    unsigned body_type
);

/*
 * cPedSprite::ModifyForward applies the animation's angle/rotation after the
 * Render() input vector. Pre-rotate by the inverse so the final billboard
 * remains camera-facing without discarding the selected directional frame.
 */
void ctw_character_precompensate_forward(
    int16_t forward[3],
    int16_t engine_adjustment
);

#ifdef __cplusplus
}
#endif
