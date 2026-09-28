#include "ctw_config.h"

#if defined(__ANDROID__)
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <jni.h>
#endif

#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum CtwConfigSection {
    SECTION_NONE = 0,
    SECTION_CAMERA,
    SECTION_WORLD,
    SECTION_CHARACTERS,
};

static float clampf_local(float value, float lo, float hi) {
    if (value < lo)
        return lo;
    if (value > hi)
        return hi;
    return value;
}

static char *trim(char *s) {
    while (*s && isspace((unsigned char)*s))
        ++s;
    char *end = s + strlen(s);
    while (end > s && isspace((unsigned char)end[-1]))
        --end;
    *end = '\0';
    return s;
}

static int equal_ci(const char *a, const char *b) {
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b))
            return 0;
        ++a;
        ++b;
    }
    return *a == '\0' && *b == '\0';
}

static int parse_bool(const char *value, int *out) {
    if (equal_ci(value, "1") || equal_ci(value, "true") ||
        equal_ci(value, "yes") || equal_ci(value, "on")) {
        *out = 1;
        return 1;
    }
    if (equal_ci(value, "0") || equal_ci(value, "false") ||
        equal_ci(value, "no") || equal_ci(value, "off")) {
        *out = 0;
        return 1;
    }
    return 0;
}

static int parse_float_value(const char *value, float *out) {
    errno = 0;
    char *end = NULL;
    const float v = strtof(value, &end);
    if (errno != 0 || end == value)
        return 0;
    while (*end && isspace((unsigned char)*end))
        ++end;
    if (*end != '\0')
        return 0;
    *out = v;
    return 1;
}

void ctw_config_set_defaults(Ctw3DConfig *config) {
    if (!config)
        return;

    *config = (Ctw3DConfig){
        .mode = CTW_CAMERA_THIRD_PERSON,

        .camera_enabled = 1,
        .camera_height = 1.35f,
        .camera_distance = 5.8f,
        .camera_pitch_degrees = -7.0f,
        .camera_look_sensitivity_x = 110.0f,
        .camera_look_sensitivity_y = 90.0f,
        .camera_invert_y = 0,
        .camera_min_pitch_degrees = -70.0f,
        .camera_max_pitch_degrees = 35.0f,
        .camera_collision_enabled = 1,
        .camera_collision_margin = 0.18f,
        .fov_degrees = 72.0f,
        .near_clip = 0.05f,
        .disable_cinematic_camera = 1,

        .draw_distance_enabled = 1,
        .far_clip_multiplier = 2.5f,
        .stream_radius_multiplier = 2.5f,
        .forward_streaming_bias_enabled = 0,
        .forward_streaming_bias_sectors = 1.0f,
        .lod_distance_multiplier = 2.0f,
        .vehicle_distance_multiplier = 2.0f,
        .ped_distance_multiplier = 2.0f,

        .character_fix = 1,
        .extended_character_lod = 1,
        .keep_full_player_body = 1,
        .hide_head_in_first_person = 1,
    };
}

static int apply_pair(
    Ctw3DConfig *config,
    enum CtwConfigSection section,
    const char *key,
    const char *value
) {
    int b = 0;
    float f = 0.0f;

    if (section == SECTION_CAMERA) {
        if (equal_ci(key, "Enabled") && parse_bool(value, &b)) {
            config->camera_enabled = b;
            return 1;
        }
        if (equal_ci(key, "Height") && parse_float_value(value, &f)) {
            config->camera_height = clampf_local(f, 0.30f, 4.0f);
            return 1;
        }
        if (equal_ci(key, "Distance") && parse_float_value(value, &f)) {
            config->camera_distance = clampf_local(f, 1.0f, 20.0f);
            return 1;
        }
        if (equal_ci(key, "Pitch") && parse_float_value(value, &f)) {
            config->camera_pitch_degrees = clampf_local(f, -85.0f, 85.0f);
            return 1;
        }
        if (equal_ci(key, "LookSensitivityX") && parse_float_value(value, &f)) {
            config->camera_look_sensitivity_x = clampf_local(f, 10.0f, 720.0f);
            return 1;
        }
        if (equal_ci(key, "LookSensitivityY") && parse_float_value(value, &f)) {
            config->camera_look_sensitivity_y = clampf_local(f, 10.0f, 720.0f);
            return 1;
        }
        if (equal_ci(key, "InvertY") && parse_bool(value, &b)) {
            config->camera_invert_y = b;
            return 1;
        }
        if (equal_ci(key, "MinPitch") && parse_float_value(value, &f)) {
            config->camera_min_pitch_degrees = clampf_local(f, -89.0f, 89.0f);
            return 1;
        }
        if (equal_ci(key, "MaxPitch") && parse_float_value(value, &f)) {
            config->camera_max_pitch_degrees = clampf_local(f, -89.0f, 89.0f);
            return 1;
        }
        if (equal_ci(key, "Collision") && parse_bool(value, &b)) {
            config->camera_collision_enabled = b;
            return 1;
        }
        if (equal_ci(key, "CollisionMargin") && parse_float_value(value, &f)) {
            config->camera_collision_margin = clampf_local(f, 0.0f, 2.0f);
            return 1;
        }
        if (equal_ci(key, "FOV") && parse_float_value(value, &f)) {
            config->fov_degrees = clampf_local(f, 40.0f, 110.0f);
            return 1;
        }
        if (equal_ci(key, "NearClip") && parse_float_value(value, &f)) {
            config->near_clip = clampf_local(f, 0.01f, 1.0f);
            return 1;
        }
        if (equal_ci(key, "DisableCineCam") && parse_bool(value, &b)) {
            config->disable_cinematic_camera = b;
            return 1;
        }
    } else if (section == SECTION_WORLD) {
        if (equal_ci(key, "Enabled") && parse_bool(value, &b)) {
            config->draw_distance_enabled = b;
            return 1;
        }
        if (equal_ci(key, "DrawDistance") && parse_float_value(value, &f)) {
            f = clampf_local(f, 1.0f, 5.0f);
            config->far_clip_multiplier = f;
            config->stream_radius_multiplier = f;
            config->lod_distance_multiplier = f;
            return 1;
        }
        if (equal_ci(key, "FarClip") && parse_float_value(value, &f)) {
            config->far_clip_multiplier = clampf_local(f, 1.0f, 5.0f);
            return 1;
        }
        if (equal_ci(key, "StreamRadius") && parse_float_value(value, &f)) {
            config->stream_radius_multiplier = clampf_local(f, 1.0f, 5.0f);
            return 1;
        }
        if (equal_ci(key, "ForwardBias") && parse_bool(value, &b)) {
            config->forward_streaming_bias_enabled = b;
            return 1;
        }
        if (equal_ci(key, "ForwardBiasSectors") &&
            parse_float_value(value, &f)) {
            config->forward_streaming_bias_sectors =
                clampf_local(f, 0.0f, 1.0f);
            return 1;
        }
        if (equal_ci(key, "LODDistance") && parse_float_value(value, &f)) {
            config->lod_distance_multiplier = clampf_local(f, 1.0f, 5.0f);
            return 1;
        }
        if (equal_ci(key, "VehicleDistance") && parse_float_value(value, &f)) {
            config->vehicle_distance_multiplier = clampf_local(f, 1.0f, 4.0f);
            return 1;
        }
        if (equal_ci(key, "PedDistance") && parse_float_value(value, &f)) {
            config->ped_distance_multiplier = clampf_local(f, 1.0f, 4.0f);
            return 1;
        }
    } else if (section == SECTION_CHARACTERS) {
        if (equal_ci(key, "FixBillboards") && parse_bool(value, &b)) {
            config->character_fix = b;
            return 1;
        }
        if (equal_ci(key, "ExtendedLOD") && parse_bool(value, &b)) {
            config->extended_character_lod = b;
            return 1;
        }
        if (equal_ci(key, "KeepFullBody") && parse_bool(value, &b)) {
            config->keep_full_player_body = b;
            return 1;
        }
        if (equal_ci(key, "HideHeadFirstPerson") && parse_bool(value, &b)) {
            config->hide_head_in_first_person = b;
            return 1;
        }
    }

    return 0;
}

int ctw_config_parse_text(Ctw3DConfig *config, const char *text) {
    if (!config || !text)
        return -1;

    const size_t n = strlen(text);
    char *copy = (char *)malloc(n + 1);
    if (!copy)
        return -2;
    memcpy(copy, text, n + 1);

    enum CtwConfigSection section = SECTION_NONE;
    int applied = 0;

    char *cursor = copy;
    while (*cursor) {
        char *line = cursor;
        char *newline = strchr(cursor, '\n');
        if (newline) {
            *newline = '\0';
            cursor = newline + 1;
        } else {
            cursor += strlen(cursor);
        }

        char *s = trim(line);
        if (!*s || *s == ';' || *s == '#')
            continue;

        const size_t len = strlen(s);
        if (s[0] == '[' && len >= 3 && s[len - 1] == ']') {
            s[len - 1] = '\0';
            const char *name = trim(s + 1);
            if (equal_ci(name, "Camera"))
                section = SECTION_CAMERA;
            else if (equal_ci(name, "World"))
                section = SECTION_WORLD;
            else if (equal_ci(name, "Characters"))
                section = SECTION_CHARACTERS;
            else
                section = SECTION_NONE;
            continue;
        }

        char *eq = strchr(s, '=');
        if (!eq)
            continue;
        *eq = '\0';
        char *key = trim(s);
        char *value = trim(eq + 1);
        applied += apply_pair(config, section, key, value);
    }

    if (config->camera_min_pitch_degrees > config->camera_max_pitch_degrees) {
        const float tmp = config->camera_min_pitch_degrees;
        config->camera_min_pitch_degrees = config->camera_max_pitch_degrees;
        config->camera_max_pitch_degrees = tmp;
    }
    config->camera_pitch_degrees = clampf_local(
        config->camera_pitch_degrees,
        config->camera_min_pitch_degrees,
        config->camera_max_pitch_degrees
    );

    if (!config->camera_enabled)
        config->mode = CTW_CAMERA_STOCK;

    free(copy);
    return applied;
}

int ctw_config_load_file(Ctw3DConfig *config, const char *path) {
    if (!config || !path)
        return -1;

    FILE *fp = fopen(path, "rb");
    if (!fp)
        return -2;

    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return -3;
    }
    const long size = ftell(fp);
    if (size < 0 || size > 1024 * 1024) {
        fclose(fp);
        return -4;
    }
    rewind(fp);

    char *buffer = (char *)malloc((size_t)size + 1);
    if (!buffer) {
        fclose(fp);
        return -5;
    }

    const size_t got = fread(buffer, 1, (size_t)size, fp);
    fclose(fp);
    if (got != (size_t)size) {
        free(buffer);
        return -6;
    }
    buffer[got] = '\0';

    const int rc = ctw_config_parse_text(config, buffer);
    free(buffer);
    return rc;
}


int ctw_config_load_android_asset(
    Ctw3DConfig *config,
    void *jni_env,
    void *asset_manager_object
) {
#if defined(__ANDROID__)
    if (!config || !jni_env || !asset_manager_object)
        return -1;

    JNIEnv *env = (JNIEnv *)jni_env;
    jobject asset_object = (jobject)asset_manager_object;
    AAssetManager *manager = AAssetManager_fromJava(env, asset_object);
    if (!manager)
        return -2;

    AAsset *asset = AAssetManager_open(
        manager,
        "ctw_modhub.ini",
        AASSET_MODE_BUFFER
    );
    if (!asset)
        return 0; /* Optional asset: defaults remain active. */

    const off_t length = AAsset_getLength(asset);
    if (length < 0 || length > 1024 * 1024) {
        AAsset_close(asset);
        return -3;
    }

    char *buffer = (char *)malloc((size_t)length + 1);
    if (!buffer) {
        AAsset_close(asset);
        return -4;
    }

    const int got = AAsset_read(asset, buffer, (size_t)length);
    AAsset_close(asset);
    if (got < 0 || (off_t)got != length) {
        free(buffer);
        return -5;
    }

    buffer[length] = '\0';
    const int rc = ctw_config_parse_text(config, buffer);
    free(buffer);
    return rc;
#else
    (void)config;
    (void)jni_env;
    (void)asset_manager_object;
    return 0;
#endif
}
