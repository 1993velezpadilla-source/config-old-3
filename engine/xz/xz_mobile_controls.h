#ifndef XZ_MOBILE_CONTROLS_H
#define XZ_MOBILE_CONTROLS_H

#include <SDL.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum XzMobileButton {
    XZ_MOBILE_FIRE = 0,
    XZ_MOBILE_ADS,
    XZ_MOBILE_RELOAD,
    XZ_MOBILE_INTERACT,
    XZ_MOBILE_CROUCH,
    XZ_MOBILE_SPRINT,
    XZ_MOBILE_GRENADE,
    XZ_MOBILE_SWAP,
    XZ_MOBILE_BUTTON_COUNT
} XzMobileButton;

typedef struct XzMobileControls {
    int initialized;
    int screen_width;
    int screen_height;
    SDL_FingerID move_finger;
    SDL_FingerID look_finger;
    int move_active;
    int look_active;
    float move_origin_x;
    float move_origin_y;
    float move_x;
    float move_y;
    float look_last_x;
    float look_last_y;
    float look_dx;
    float look_dy;
    uint32_t buttons_down;
    uint32_t buttons_pressed;
    unsigned int program;
    unsigned int vao;
    unsigned int vbo;
    int u_resolution;
    int u_center;
    int u_radius;
    int u_icon;
    int u_pressed;
    int u_alpha;
} XzMobileControls;

int XzMobileControls_Init(XzMobileControls *controls);
void XzMobileControls_Shutdown(XzMobileControls *controls);
void XzMobileControls_BeginFrame(XzMobileControls *controls);
void XzMobileControls_HandleEvent(
    XzMobileControls *controls,
    const SDL_Event *event);
void XzMobileControls_GetMove(
    const XzMobileControls *controls,
    float *out_x,
    float *out_y);
void XzMobileControls_ConsumeLook(
    XzMobileControls *controls,
    float *out_dx,
    float *out_dy);
int XzMobileControls_ButtonDown(
    const XzMobileControls *controls,
    XzMobileButton button);
int XzMobileControls_ButtonPressed(
    const XzMobileControls *controls,
    XzMobileButton button);
void XzMobileControls_Render(
    XzMobileControls *controls,
    int width,
    int height);

#ifdef __cplusplus
}
#endif

#endif
