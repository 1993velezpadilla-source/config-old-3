#include "ctw_character.h"

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
