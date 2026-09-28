#include "ctw_character.h"

#include <math.h>

static int is_body_part(CtwCharacterPart part) {
    return part == CTW_CHARACTER_PART_HEAD ||
           part == CTW_CHARACTER_PART_FACE ||
           part == CTW_CHARACTER_PART_TORSO ||
           part == CTW_CHARACTER_PART_ARMS ||
           part == CTW_CHARACTER_PART_LEGS ||
           part == CTW_CHARACTER_PART_WEAPON;
}

CtwVisibilityOverride ctw_character_visibility_override(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    CtwCharacterPart part
) {
    if (!config || !config->character_fix)
        return CTW_VISIBILITY_PRESERVE;

    if (!is_body_part(part))
        return CTW_VISIBILITY_PRESERVE;

    if (mode == CTW_CAMERA_STOCK)
        return CTW_VISIBILITY_PRESERVE;

    if (mode == CTW_CAMERA_THIRD_PERSON) {
        return config->keep_full_player_body
            ? CTW_VISIBILITY_SHOW
            : CTW_VISIBILITY_PRESERVE;
    }

    if (mode == CTW_CAMERA_FIRST_PERSON) {
        if ((part == CTW_CHARACTER_PART_HEAD ||
             part == CTW_CHARACTER_PART_FACE) &&
            config->hide_head_in_first_person) {
            return CTW_VISIBILITY_HIDE;
        }

        return config->keep_full_player_body
            ? CTW_VISIBILITY_SHOW
            : CTW_VISIBILITY_PRESERVE;
    }

    return CTW_VISIBILITY_PRESERVE;
}

int ctw_character_camera_facing_forward(
    int32_t ped_x,
    int32_t ped_y,
    int32_t camera_x,
    int32_t camera_y,
    const int16_t original_forward[3],
    int16_t out_forward[3]
) {
    if (!original_forward || !out_forward)
        return 0;

    const float dx = (float)(camera_x - ped_x);
    const float dy = (float)(camera_y - ped_y);
    const float length = sqrtf(dx * dx + dy * dy);

    if (!isfinite(length) || length < 1.0f) {
        out_forward[0] = original_forward[0];
        out_forward[1] = original_forward[1];
        out_forward[2] = original_forward[2];
        return 0;
    }

    const float scale = 4096.0f / length;
    float fx = dx * scale;
    float fy = dy * scale;
    if (fx > 4096.0f) fx = 4096.0f;
    if (fx < -4096.0f) fx = -4096.0f;
    if (fy > 4096.0f) fy = 4096.0f;
    if (fy < -4096.0f) fy = -4096.0f;

    out_forward[0] = (int16_t)lrintf(fx);
    out_forward[1] = (int16_t)lrintf(fy);
    out_forward[2] = original_forward[2];
    return 1;
}

int ctw_character_hide_body_type(
    const Ctw3DConfig *config,
    CtwCameraMode mode,
    int is_local_player_sprite,
    unsigned body_type
) {
    if (!config || !config->character_fix)
        return 0;
    if (!is_local_player_sprite)
        return 0;
    if (mode != CTW_CAMERA_FIRST_PERSON)
        return 0;
    if (!config->hide_head_in_first_person)
        return 0;

    return body_type == 0u;
}
