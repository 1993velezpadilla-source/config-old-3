#include "ctw_character.h"

#include <assert.h>
#include <stdlib.h>

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

    {
        const int16_t original[3] = { 4096, 0, 321 };
        int16_t out[3] = { 0, 0, 0 };
        assert(
            ctw_character_camera_facing_forward(
                0, 0, 0, 4096, original, out
            ) == 1
        );
        assert(abs(out[0]) <= 1);
        assert(out[1] >= 4095);
        assert(out[2] == 321);

        assert(
            ctw_character_camera_facing_forward(
                100, 200, 100, 200, original, out
            ) == 0
        );
        assert(out[0] == original[0]);
        assert(out[1] == original[1]);
        assert(out[2] == original[2]);
    }

    cfg.character_fix = 1;
    cfg.hide_head_in_first_person = 1;
    assert(
        ctw_character_hide_body_type(
            &cfg, CTW_CAMERA_FIRST_PERSON, 1, 0
        ) == 1
    );
    assert(
        ctw_character_hide_body_type(
            &cfg, CTW_CAMERA_FIRST_PERSON, 1, 1
        ) == 0
    );
    assert(
        ctw_character_hide_body_type(
            &cfg, CTW_CAMERA_FIRST_PERSON, 0, 0
        ) == 0
    );
    assert(
        ctw_character_hide_body_type(
            &cfg, CTW_CAMERA_THIRD_PERSON, 1, 0
        ) == 0
    );

    {
        int16_t forward[3] = { 0, 4096, 77 };
        ctw_character_precompensate_forward(
            forward,
            (int16_t)0x4000
        );
        assert(forward[0] <= -4095);
        assert(abs(forward[1]) <= 1);
        assert(forward[2] == 77);
    }

    return 0;
}
