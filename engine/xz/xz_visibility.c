#include "xz_visibility.h"

#include <string.h>

#define XZ_VISIBILITY_NEAR_KEEP_SQ (160.0f * 160.0f)
#define XZ_VISIBILITY_EDGE_MARGIN 96.0f
#define XZ_VISIBILITY_BACK_MARGIN 128.0f

static float XzDot3(
    const float a[3],
    const float b[3])
{
    return a[0] * b[0] +
           a[1] * b[1] +
           a[2] * b[2];
}

static float XzHalfFovTangent(float degrees)
{
    static const float tangent_half[] = {
        0.176327f, 0.267949f, 0.363970f, 0.466308f,
        0.577350f, 0.700208f, 0.839100f, 1.000000f,
        1.191754f, 1.428148f, 1.732051f, 2.144507f,
        2.747477f, 3.732051f, 5.671282f, 11.430052f
    };
    float clamped = degrees;
    float scaled;
    unsigned int index;
    float fraction;

    if (clamped < 20.0f)
        clamped = 20.0f;
    if (clamped > 170.0f)
        clamped = 170.0f;

    scaled = (clamped - 20.0f) / 10.0f;
    index = (unsigned int)scaled;
    if (index >= 15u)
        return tangent_half[15];

    fraction = scaled - (float)index;
    return tangent_half[index] +
        (tangent_half[index + 1u] - tangent_half[index]) *
        fraction;
}

void XzVisibility_Classify(
    const XzPresentFrame *frame,
    const XzPresentEntity *entity,
    XzVisibilityResult *result)
{
    float delta[3];
    float tan_x;
    float tan_y;
    float limit_x;
    float limit_y;
    float abs_right;
    float abs_up;
    int critical;

    if (!result)
        return;

    memset(result, 0, sizeof(*result));
    result->visibility_class =
        XZ_VISIBILITY_CULLED;

    if (!frame || !entity)
        return;

    delta[0] =
        entity->origin[0] - frame->camera_origin[0];
    delta[1] =
        entity->origin[1] - frame->camera_origin[1];
    delta[2] =
        entity->origin[2] - frame->camera_origin[2];

    result->view_forward =
        XzDot3(delta, frame->camera_forward);
    result->view_right =
        XzDot3(delta, frame->camera_right);
    result->view_up =
        XzDot3(delta, frame->camera_up);

    critical =
        entity->priority_class >= 3u ||
        entity->effects != 0u ||
        entity->distance_sq <=
            XZ_VISIBILITY_NEAR_KEEP_SQ;

    /*
     * The source visibility set has already passed XZIEL spatial visibility.
     * This stage remains deliberately conservative: critical/effect/near
     * entities are never removed, while clearly-behind or well-outside-frustum
     * background entities can be rejected from presentation.
     */
    if (critical) {
        result->admitted = 1;
        result->visibility_class =
            result->view_forward >= 0.0f
                ? XZ_VISIBILITY_FRONT
                : XZ_VISIBILITY_BEHIND;
        return;
    }

    if (!frame->camera_basis_valid ||
        frame->fov_x <= 0.0f ||
        frame->fov_y <= 0.0f) {
        result->admitted = 1;
        result->visibility_class =
            XZ_VISIBILITY_FRONT;
        return;
    }

    if (result->view_forward <=
        -XZ_VISIBILITY_BACK_MARGIN) {
        result->admitted = 0;
        result->visibility_class =
            XZ_VISIBILITY_CULLED;
        return;
    }

    if (result->view_forward <= 1.0f) {
        result->admitted = 1;
        result->visibility_class =
            XZ_VISIBILITY_BEHIND;
        return;
    }

    tan_x = XzHalfFovTangent(frame->fov_x);
    tan_y = XzHalfFovTangent(frame->fov_y);

    limit_x =
        result->view_forward * tan_x +
        XZ_VISIBILITY_EDGE_MARGIN;
    limit_y =
        result->view_forward * tan_y +
        XZ_VISIBILITY_EDGE_MARGIN;

    abs_right = result->view_right < 0.0f
        ? -result->view_right
        : result->view_right;
    abs_up = result->view_up < 0.0f
        ? -result->view_up
        : result->view_up;

    if (abs_right > limit_x ||
        abs_up > limit_y) {
        result->admitted = 0;
        result->visibility_class =
            XZ_VISIBILITY_CULLED;
        return;
    }

    result->admitted = 1;

    if (abs_right >
            result->view_forward * tan_x * 0.82f ||
        abs_up >
            result->view_forward * tan_y * 0.82f) {
        result->visibility_class =
            XZ_VISIBILITY_EDGE;
    } else {
        result->visibility_class =
            XZ_VISIBILITY_FRONT;
    }

    result->projected_radius =
        64.0f /
        (result->view_forward > 1.0f
            ? result->view_forward
            : 1.0f);
}

int XzVisibility_SelfTest(void)
{
    XzPresentFrame frame;
    XzPresentEntity entity;
    XzVisibilityResult result;

    memset(&frame, 0, sizeof(frame));
    memset(&entity, 0, sizeof(entity));

    frame.camera_basis_valid = 1;
    frame.camera_forward[0] = 1.0f;
    frame.camera_right[1] = 1.0f;
    frame.camera_up[2] = 1.0f;
    frame.fov_x = 90.0f;
    frame.fov_y = 60.0f;

    entity.origin[0] = 512.0f;
    entity.distance_sq = 512.0f * 512.0f;
    XzVisibility_Classify(
        &frame, &entity, &result);
    if (!result.admitted ||
        result.visibility_class !=
            XZ_VISIBILITY_FRONT)
        return 0;

    entity.origin[1] = 2000.0f;
    XzVisibility_Classify(
        &frame, &entity, &result);
    if (result.admitted ||
        result.visibility_class !=
            XZ_VISIBILITY_CULLED)
        return 0;

    memset(&entity, 0, sizeof(entity));
    entity.origin[0] = -512.0f;
    entity.distance_sq = 512.0f * 512.0f;
    XzVisibility_Classify(
        &frame, &entity, &result);
    if (result.admitted)
        return 0;

    entity.priority_class = 3u;
    XzVisibility_Classify(
        &frame, &entity, &result);
    if (!result.admitted ||
        result.visibility_class !=
            XZ_VISIBILITY_BEHIND)
        return 0;

    return 1;
}
