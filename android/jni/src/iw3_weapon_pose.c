#include "iw3_weapon_pose.h"
#include <math.h>
#include <string.h>
#include "iw3_weapon_profiles_generated.h"

static float iw3_clamp01(float x)
{
    if (!isfinite(x) || x <= 0.0f) return 0.0f;
    if (x >= 1.0f) return 1.0f;
    return x;
}

const iw3_weapon_pose_t *IW3_WeaponFindPose(const char *model)
{
    unsigned i;
    if (!model || !*model) return 0;
    for (i = 0; i != IW3_POSE_TABLE_SIZE; ++i) {
        if (iw3_pose_table[i].viewmodel &&
            strcmp(iw3_pose_table[i].viewmodel, model) == 0)
            return &iw3_pose_table[i];
    }
    return 0;
}

void IW3_WeaponPoseDelta(const iw3_weapon_pose_t *p,
                         const float basis[3][3], int stance,
                         float speed_norm, float ads_frac,
                         float dxyz[3], float dpyr[3])
{
    float local[3], aim, moving;
    int i,j;
    if (!dxyz || !dpyr) return;
    for (i = 0; i < 3; ++i) { dxyz[i] = 0.0f; dpyr[i] = 0.0f; }
    if (!p || !basis || stance < 0 || stance > 2) return;
    aim = iw3_clamp01(ads_frac);
    moving = iw3_clamp01(speed_norm);
    /* Mirrors the fade of movement offsets in KisakCOD:
     * CalculateWeaponPosition_BasePosition_movement (0..50% ADS).
     * The original XAnim tree, hands, sway and recoil remain separate. */
    moving *= fmaxf(0.0f, 1.0f - 2.0f*aim);
    for (i=0; i<3; ++i) {
        local[i] = p->stand_move[i] * moving;
        if (stance==1) local[i] += p->ducked_ofs[i] * (1.0f-aim);
        if (stance==2) local[i] += p->prone_ofs[i] * (1.0f-aim);
        dpyr[i] = p->stand_rot[i] * moving;
    }
    dpyr[0] += p->ads_aim_pitch * aim;
    for (j=0; j<3; ++j)
        for (i=0; i<3; ++i)
            dxyz[j] += basis[i][j] * local[i];
}
