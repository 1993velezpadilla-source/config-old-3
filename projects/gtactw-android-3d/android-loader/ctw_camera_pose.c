#include "ctw_camera_pose.h"

#include <math.h>
#include <string.h>

#define CTW_PI 3.14159265358979323846f

static CtwVec3 vadd(CtwVec3 a, CtwVec3 b) {
    return (CtwVec3){a.x + b.x, a.y + b.y, a.z + b.z};
}

static CtwVec3 vscale(CtwVec3 a, float s) {
    return (CtwVec3){a.x * s, a.y * s, a.z * s};
}

static float vdot(CtwVec3 a, CtwVec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

static CtwVec3 vnormalize(CtwVec3 v) {
    const float len2 = vdot(v, v);
    if (len2 <= 0.0000001f)
        return (CtwVec3){0.0f, 0.0f, 0.0f};
    return vscale(v, 1.0f / sqrtf(len2));
}

static int valid_basis(const CtwPlayerCameraBasis *p) {
    if (!p)
        return 0;

    const CtwVec3 f = vnormalize(p->forward);
    const CtwVec3 r = vnormalize(p->right);
    const CtwVec3 u = vnormalize(p->up);

    if (vdot(f, f) < 0.9f ||
        vdot(r, r) < 0.9f ||
        vdot(u, u) < 0.9f) {
        return 0;
    }

    /* Basis does not need to be perfect, but must not collapse axes. */
    if (fabsf(vdot(f, r)) > 0.25f ||
        fabsf(vdot(f, u)) > 0.25f ||
        fabsf(vdot(r, u)) > 0.25f) {
        return 0;
    }

    return 1;
}

int ctw_camera_build_pose(
    const Ctw3DConfig *config,
    CtwCameraOrbitState orbit,
    CtwCameraMode mode,
    const CtwPlayerCameraBasis *player,
    CtwCameraPose *out
) {
    if (!config || !player || !out)
        return -1;

    memset(out, 0, sizeof(*out));

    if (!config->camera_enabled || mode == CTW_CAMERA_STOCK)
        return 0;

    if (!valid_basis(player))
        return -2;

    const CtwVec3 base_forward = vnormalize(player->forward);
    const CtwVec3 base_right = vnormalize(player->right);
    const CtwVec3 up = vnormalize(player->up);

    const float yaw = orbit.yaw_degrees * (CTW_PI / 180.0f);
    const float pitch = orbit.pitch_degrees * (CTW_PI / 180.0f);

    const CtwVec3 horizontal = vnormalize(vadd(
        vscale(base_forward, cosf(yaw)),
        vscale(base_right, sinf(yaw))
    ));

    const CtwVec3 look = vnormalize(vadd(
        vscale(horizontal, cosf(pitch)),
        vscale(up, sinf(pitch))
    ));

    const CtwVec3 anchor = vadd(
        player->position,
        vscale(up, config->camera_height)
    );

    out->override_camera = 1;
    out->forward = look;
    out->up = up;

    if (mode == CTW_CAMERA_FIRST_PERSON) {
        out->position = anchor;
        out->target = vadd(anchor, look);
        return 1;
    }

    if (mode == CTW_CAMERA_THIRD_PERSON) {
        out->target = anchor;
        out->position = vadd(
            anchor,
            vscale(look, -config->camera_distance)
        );
        return 1;
    }

    return 0;
}
