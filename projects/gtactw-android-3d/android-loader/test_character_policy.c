#include "ctw_character.h"

#include <assert.h>

int main(void) {
    Ctw3DConfig cfg = {0};
    cfg.character_fix = 1;
    cfg.keep_full_player_body = 1;
    cfg.hide_head_in_first_person = 1;

    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_STOCK,
            CTW_CHARACTER_PART_TORSO
        ) == CTW_VISIBILITY_PRESERVE
    );

    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_THIRD_PERSON,
            CTW_CHARACTER_PART_HEAD
        ) == CTW_VISIBILITY_SHOW
    );
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_THIRD_PERSON,
            CTW_CHARACTER_PART_WEAPON
        ) == CTW_VISIBILITY_SHOW
    );

    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_HEAD
        ) == CTW_VISIBILITY_HIDE
    );
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_FACE
        ) == CTW_VISIBILITY_HIDE
    );
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_TORSO
        ) == CTW_VISIBILITY_SHOW
    );
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_ARMS
        ) == CTW_VISIBILITY_SHOW
    );
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_WEAPON
        ) == CTW_VISIBILITY_SHOW
    );
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_OTHER
        ) == CTW_VISIBILITY_PRESERVE
    );

    cfg.hide_head_in_first_person = 0;
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_HEAD
        ) == CTW_VISIBILITY_SHOW
    );

    cfg.keep_full_player_body = 0;
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_THIRD_PERSON,
            CTW_CHARACTER_PART_LEGS
        ) == CTW_VISIBILITY_PRESERVE
    );

    cfg.character_fix = 0;
    assert(
        ctw_character_visibility_override(
            &cfg,
            CTW_CAMERA_FIRST_PERSON,
            CTW_CHARACTER_PART_HEAD
        ) == CTW_VISIBILITY_PRESERVE
    );

    return 0;
}
