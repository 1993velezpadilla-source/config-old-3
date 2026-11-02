/* VIRIL IW3 experimental renderer-side weapon pose bridge.
 * Source-reimplemented IW3 first-person position semantics under GPL-3.0.
 * No Windows/D3D/32-bit ABI dependencies.
 */
#ifndef VIRIL_IW3_WEAPON_POSE_H
#define VIRIL_IW3_WEAPON_POSE_H
#ifdef __cplusplus
extern "C" {
#endif
typedef struct iw3_weapon_pose_s {
    const char *viewmodel;  /* already converted Vril MDL pathname */
    float stand_move[3];    /* forward/right/up, IW3 WeaponDef semantics */
    float stand_rot[3];     /* pitch/yaw/roll */
    float ducked_ofs[3];
    float prone_ofs[3];
    float ads_aim_pitch;
    float pos_move_rate;
} iw3_weapon_pose_t;

/* Generated from legitimate local .weapon definitions, empty unless supplied.
 * Never claim the official CoD4 gun data is present without actual assets. */
const iw3_weapon_pose_t *IW3_WeaponFindPose(const char *viril_model);

/* Calculate additive position and rotation only; no source tree global state.
 * basis 0=forward, 1=right, 2=up in Vril world coordinates.
 * stance: 0=standing, 1=crouched, 2=prone. speed_norm and ads in [0,1]. */
void IW3_WeaponPoseDelta(const iw3_weapon_pose_t *pose,
                         const float basis[3][3], int stance,
                         float speed_norm, float ads_frac,
                         float delta_xyz[3], float delta_pyr[3]);
#ifdef __cplusplus
}
#endif
#endif
