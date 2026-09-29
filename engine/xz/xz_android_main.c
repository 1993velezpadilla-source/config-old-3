#include "xz_android_runtime.h"
#include "xz_file_io.h"
#include "xz_mobile_controls.h"

#include <SDL.h>
#include <SDL_system.h>

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define XZ_CAMERA_UNITS_PER_METER 39.3700787402f
#define XZ_CAMERA_PI 3.14159265358979323846f

static const char *XzArgValue(
    int argc,
    char **argv,
    const char *name,
    const char *fallback)
{
    int i;
    for (i = 1; i + 1 < argc; ++i) {
        if (strcmp(argv[i], name) == 0)
            return argv[i + 1];
    }
    return fallback;
}

static int XzParseFloat3(
    const char *text,
    float value[3])
{
    char *end = NULL;
    int i;

    if (!text || !value)
        return 0;

    for (i = 0; i < 3; ++i) {
        float parsed;

        parsed = strtof(text, &end);
        if (end == text ||
            !isfinite(parsed))
            return 0;

        value[i] = parsed;

        if (i < 2) {
            if (*end != ',')
                return 0;
            text = end + 1;
        } else if (*end != '\0') {
            return 0;
        }
    }

    return 1;
}

static float XzDot3(
    const float a[3],
    const float b[3])
{
    return
        a[0] * b[0] +
        a[1] * b[1] +
        a[2] * b[2];
}

static void XzCross3(
    const float a[3],
    const float b[3],
    float output[3])
{
    output[0] =
        a[1] * b[2] -
        a[2] * b[1];
    output[1] =
        a[2] * b[0] -
        a[0] * b[2];
    output[2] =
        a[0] * b[1] -
        a[1] * b[0];
}

static int XzNormalize3(float value[3])
{
    float length;

    if (!value)
        return 0;

    length = sqrtf(XzDot3(value, value));
    if (!isfinite(length) ||
        length <= 1.0e-6f)
        return 0;

    value[0] /= length;
    value[1] /= length;
    value[2] /= length;
    return 1;
}

static int XzBuildView(
    const float eye_meters[3],
    const float forward_input[3],
    const float up_input[3],
    float output[16])
{
    float eye[3];
    float forward[3];
    float up_seed[3];
    float side[3];
    float up[3];

    if (!eye_meters ||
        !forward_input ||
        !up_input ||
        !output)
        return 0;

    eye[0] =
        eye_meters[0] *
        XZ_CAMERA_UNITS_PER_METER;
    eye[1] =
        eye_meters[1] *
        XZ_CAMERA_UNITS_PER_METER;
    eye[2] =
        eye_meters[2] *
        XZ_CAMERA_UNITS_PER_METER;

    memcpy(
        forward,
        forward_input,
        sizeof(forward));
    memcpy(
        up_seed,
        up_input,
        sizeof(up_seed));

    if (!XzNormalize3(forward) ||
        !XzNormalize3(up_seed))
        return 0;

    XzCross3(
        forward,
        up_seed,
        side);
    if (!XzNormalize3(side))
        return 0;

    XzCross3(
        side,
        forward,
        up);
    if (!XzNormalize3(up))
        return 0;

    memset(
        output,
        0,
        sizeof(float) * 16u);

    output[0] = side[0];
    output[1] = up[0];
    output[2] = -forward[0];

    output[4] = side[1];
    output[5] = up[1];
    output[6] = -forward[1];

    output[8] = side[2];
    output[9] = up[2];
    output[10] = -forward[2];

    output[12] = -XzDot3(side, eye);
    output[13] = -XzDot3(up, eye);
    output[14] = XzDot3(forward, eye);
    output[15] = 1.0f;
    return 1;
}

static float XzClampF(float value, float lo, float hi)
{
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

static void XzForwardFromAngles(
    float yaw,
    float pitch,
    float forward[3])
{
    const float cp = cosf(pitch);
    forward[0] = cp * cosf(yaw);
    forward[1] = cp * sinf(yaw);
    forward[2] = sinf(pitch);
}

static void XzAnglesFromForward(
    const float forward[3],
    float *yaw,
    float *pitch)
{
    float temp[3] = {forward[0], forward[1], forward[2]};
    if (!XzNormalize3(temp)) {
        *yaw = 0.0f;
        *pitch = 0.0f;
        return;
    }
    *yaw = atan2f(temp[1], temp[0]);
    *pitch = asinf(XzClampF(temp[2], -1.0f, 1.0f));
}

static int XzBuildPerspective(
    float fov_y_degrees,
    float aspect,
    float near_meters,
    float far_meters,
    float output[16])
{
    float radians;
    float scale;
    float near_units;
    float far_units;

    if (!output ||
        !isfinite(fov_y_degrees) ||
        !isfinite(aspect) ||
        !isfinite(near_meters) ||
        !isfinite(far_meters) ||
        fov_y_degrees <= 1.0f ||
        fov_y_degrees >= 179.0f ||
        aspect <= 0.0f ||
        near_meters <= 0.0f ||
        far_meters <= near_meters)
        return 0;

    radians =
        fov_y_degrees *
        XZ_CAMERA_PI /
        180.0f;
    scale =
        1.0f /
        tanf(radians * 0.5f);

    near_units =
        near_meters *
        XZ_CAMERA_UNITS_PER_METER;
    far_units =
        far_meters *
        XZ_CAMERA_UNITS_PER_METER;

    memset(
        output,
        0,
        sizeof(float) * 16u);

    output[0] = scale / aspect;
    output[5] = scale;
    output[10] =
        (far_units + near_units) /
        (near_units - far_units);
    output[11] = -1.0f;
    output[14] =
        (2.0f * far_units * near_units) /
        (near_units - far_units);
    return 1;
}

int main(int argc, char **argv)
{
    const char *root =
        XzArgValue(argc, argv, "--xziel-root", ".");
    const char *map_id =
        XzArgValue(
            argc,
            argv,
            "--xziel-map",
            NULL);
    const char *eye_text =
        XzArgValue(
            argc,
            argv,
            "--xziel-camera-eye",
            NULL);
    const char *forward_text =
        XzArgValue(
            argc,
            argv,
            "--xziel-camera-forward",
            NULL);
    const char *up_text =
        XzArgValue(
            argc,
            argv,
            "--xziel-camera-up",
            NULL);
    const char *fov_text =
        XzArgValue(
            argc,
            argv,
            "--xziel-camera-fov-y",
            "75");
    float eye[3] = {-0.100192f, 11.940000f, 1.700000f};
    float forward[3] = {1.0f, 0.0f, 0.0f};
    float up[3] = {0.0f, 0.0f, 1.0f};
    float modelview[16];
    float projection[16];
    float fov_y = 75.0f;
    float yaw = 0.0f;
    float pitch = 0.0f;
    float standing_eye_z = 1.70f;
    double previous_now = 0.0;
    int camera_ready = 1;
    XzMobileControls mobile_controls;
    int mobile_controls_ready = 0;
    SDL_Window *window = NULL;
    SDL_GLContext context = NULL;
    int running = 1;

    if (!XzFile_SetRoot(root))
        return 10;

    if (SDL_Init(
            SDL_INIT_VIDEO |
            SDL_INIT_EVENTS |
            SDL_INIT_TIMER |
            SDL_INIT_SENSOR) != 0)
        return 11;

    SDL_GL_SetAttribute(
        SDL_GL_CONTEXT_PROFILE_MASK,
        SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(
        SDL_GL_CONTEXT_MAJOR_VERSION,
        3);
    SDL_GL_SetAttribute(
        SDL_GL_CONTEXT_MINOR_VERSION,
        0);
    SDL_GL_SetAttribute(
        SDL_GL_DEPTH_SIZE,
        24);
    SDL_GL_SetAttribute(
        SDL_GL_DOUBLEBUFFER,
        1);

    window = SDL_CreateWindow(
        "XZIEL",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        1280,
        720,
        SDL_WINDOW_OPENGL |
        SDL_WINDOW_FULLSCREEN_DESKTOP |
        SDL_WINDOW_ALLOW_HIGHDPI);
    if (!window) {
        SDL_Quit();
        return 12;
    }

    context = SDL_GL_CreateContext(window);
    if (!context) {
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 13;
    }

    SDL_GL_SetSwapInterval(1);

    if (eye_text &&
        forward_text &&
        up_text &&
        XzParseFloat3(eye_text, eye) &&
        XzParseFloat3(forward_text, forward) &&
        XzParseFloat3(up_text, up)) {
        char *end = NULL;

        fov_y = strtof(fov_text, &end);
        if (end == fov_text ||
            *end != '\0' ||
            !isfinite(fov_y))
            fov_y = 75.0f;
    }

    standing_eye_z = eye[2];
    XzAnglesFromForward(forward, &yaw, &pitch);
    mobile_controls_ready =
        XzMobileControls_Init(&mobile_controls);

    XzAndroidRuntime_Init(
        256u * 1024u * 1024u);
    XzAndroidRuntime_SetVerifiedMapPackageMode(1);
    if (map_id && map_id[0])
        XzAndroidRuntime_NotifyWorldTransitionNamed(
            map_id);

    while (running) {
        SDL_Event event;
        double now;
        double dt;
        int drawable_width = 0;
        int drawable_height = 0;
        float move_x = 0.0f;
        float move_y = 0.0f;
        float look_dx = 0.0f;
        float look_dy = 0.0f;
        float move_speed = 3.25f;
        float frame_fov = fov_y;

        if (mobile_controls_ready)
            XzMobileControls_BeginFrame(&mobile_controls);

        while (SDL_PollEvent(&event)) {
            if (mobile_controls_ready)
                XzMobileControls_HandleEvent(
                    &mobile_controls,
                    &event);
            if (event.type == SDL_QUIT)
                running = 0;
            if (event.type == SDL_KEYDOWN &&
                event.key.keysym.sym == SDLK_ESCAPE)
                running = 0;
        }

        now =
            (double)SDL_GetPerformanceCounter() /
            (double)SDL_GetPerformanceFrequency();
        dt = previous_now > 0.0 ? now - previous_now : 0.0;
        previous_now = now;
        if (dt < 0.0)
            dt = 0.0;
        if (dt > 0.050)
            dt = 0.050;

        if (mobile_controls_ready) {
            float flat_forward_x;
            float flat_forward_y;
            float right_x;
            float right_y;

            XzMobileControls_GetMove(
                &mobile_controls,
                &move_x,
                &move_y);
            XzMobileControls_ConsumeLook(
                &mobile_controls,
                &look_dx,
                &look_dy);

            yaw += look_dx * 4.80f;
            pitch -= look_dy * 3.80f;
            pitch = XzClampF(pitch, -1.38f, 1.38f);

            if (XzMobileControls_ButtonDown(
                    &mobile_controls,
                    XZ_MOBILE_SPRINT))
                move_speed = 5.25f;

            flat_forward_x = cosf(yaw);
            flat_forward_y = sinf(yaw);
            right_x = -flat_forward_y;
            right_y = flat_forward_x;

            eye[0] +=
                (flat_forward_x * move_y + right_x * move_x) *
                move_speed * (float)dt;
            eye[1] +=
                (flat_forward_y * move_y + right_y * move_x) *
                move_speed * (float)dt;

            if (XzMobileControls_ButtonDown(
                    &mobile_controls,
                    XZ_MOBILE_CROUCH))
                eye[2] = standing_eye_z - 0.40f;
            else
                eye[2] = standing_eye_z;

            if (XzMobileControls_ButtonDown(
                    &mobile_controls,
                    XZ_MOBILE_ADS))
                frame_fov = fov_y > 58.0f ? 58.0f : fov_y;

            if (XzMobileControls_ButtonPressed(
                    &mobile_controls,
                    XZ_MOBILE_INTERACT)) {
                (void)XzAndroidRuntime_NachtTryInteractMeters(
                    eye[0],
                    eye[1],
                    eye[2]);
            }
        }

        XzForwardFromAngles(yaw, pitch, forward);

        XzAndroidRuntime_BeginFrame(now);
        XzAndroidRuntime_EndFrame(now);

        SDL_GL_GetDrawableSize(
            window,
            &drawable_width,
            &drawable_height);

        if (camera_ready &&
            drawable_width > 0 &&
            drawable_height > 0 &&
            XzBuildView(
                eye,
                forward,
                up,
                modelview) &&
            XzBuildPerspective(
                frame_fov,
                (float)drawable_width /
                    (float)drawable_height,
                0.05f,
                1000.0f,
                projection)) {
            (void)XzAndroidRuntime_PresentStaticScene(
                modelview,
                projection,
                (unsigned int)drawable_width,
                (unsigned int)drawable_height);
        }

        if (mobile_controls_ready &&
            drawable_width > 0 &&
            drawable_height > 0) {
            XzMobileControls_Render(
                &mobile_controls,
                drawable_width,
                drawable_height);
        }

        SDL_GL_SwapWindow(window);
        SDL_Delay(1);
    }

    XzAndroidRuntime_Shutdown();
    if (mobile_controls_ready)
        XzMobileControls_Shutdown(&mobile_controls);
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
