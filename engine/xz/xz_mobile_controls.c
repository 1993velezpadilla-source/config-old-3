#include "xz_mobile_controls.h"

#include <GLES3/gl3.h>

#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

typedef struct XzTouchButtonDef {
    float x;
    float y;
    float radius;
    int icon;
} XzTouchButtonDef;

static const XzTouchButtonDef kButtons[XZ_MOBILE_BUTTON_COUNT] = {
    {0.905f, 0.665f, 0.078f, 1},
    {0.790f, 0.610f, 0.064f, 2},
    {0.900f, 0.485f, 0.056f, 3},
    {0.720f, 0.475f, 0.058f, 4},
    {0.840f, 0.835f, 0.055f, 5},
    {0.185f, 0.570f, 0.055f, 6},
    {0.675f, 0.720f, 0.055f, 7},
    {0.755f, 0.835f, 0.052f, 8}
};

static GLuint XzCompileShader(GLenum type, const char *source)
{
    GLuint shader = glCreateShader(type);
    GLint ok = GL_FALSE;

    if (!shader)
        return 0u;

    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (ok != GL_TRUE) {
        glDeleteShader(shader);
        return 0u;
    }
    return shader;
}

static int XzBuildProgram(XzMobileControls *controls)
{
    static const char *vs =
        "#version 300 es\n"
        "layout(location=0) in vec2 aPos;\n"
        "void main(){gl_Position=vec4(aPos,0.0,1.0);}\n";

    static const char *fs =
        "#version 300 es\n"
        "precision mediump float;\n"
        "uniform vec2 uResolution;\n"
        "uniform vec2 uCenter;\n"
        "uniform float uRadius;\n"
        "uniform int uIcon;\n"
        "uniform float uPressed;\n"
        "uniform float uAlpha;\n"
        "out vec4 fragColor;\n"
        "float seg(vec2 p, vec2 a, vec2 b, float w){"
        "vec2 pa=p-a,ba=b-a;"
        "float h=clamp(dot(pa,ba)/max(dot(ba,ba),0.0001),0.0,1.0);"
        "return 1.0-smoothstep(w,w+0.025,length(pa-ba*h));}\n"
        "void main(){"
        "vec2 uv=gl_FragCoord.xy/uResolution;"
        "vec2 p=uv-uCenter;"
        "p.x*=uResolution.x/uResolution.y;"
        "float d=length(p)/uRadius;"
        "if(d>1.06) discard;"
        "float rim=1.0-smoothstep(0.88,1.02,d);"
        "float edge=smoothstep(0.72,0.90,d)*rim;"
        "float fill=(1.0-smoothstep(0.0,0.98,d));"
        "float a=(0.105+0.13*uPressed)*fill+(0.19+0.18*uPressed)*edge;"
        "vec3 base=mix(vec3(0.02,0.02,0.025),vec3(0.10,0.015,0.06),uPressed);"
        "vec2 q=p/uRadius;"
        "float ink=0.0;"
        "if(uIcon==1){"
        "ink=max(seg(q,vec2(-0.28,0.0),vec2(0.28,0.0),0.045),seg(q,vec2(0.0,-0.28),vec2(0.0,0.28),0.045));"
        "ink=max(ink,1.0-smoothstep(0.13,0.19,length(q-vec2(0.30,-0.28))));"
        "}else if(uIcon==2){"
        "float rr=abs(length(q)-0.43);ink=1.0-smoothstep(0.035,0.070,rr);"
        "ink=max(ink,seg(q,vec2(-0.62,0.0),vec2(-0.22,0.0),0.035));"
        "ink=max(ink,seg(q,vec2(0.22,0.0),vec2(0.62,0.0),0.035));"
        "ink=max(ink,seg(q,vec2(0.0,-0.62),vec2(0.0,-0.22),0.035));"
        "ink=max(ink,seg(q,vec2(0.0,0.22),vec2(0.0,0.62),0.035));"
        "}else if(uIcon==3){"
        "float rr=abs(length(q)-0.43);float cut=step(-0.28,q.x+q.y);"
        "ink=(1.0-smoothstep(0.035,0.075,rr))*cut;"
        "ink=max(ink,seg(q,vec2(0.38,0.25),vec2(0.62,0.06),0.045));"
        "}else if(uIcon==4){"
        "ink=max(seg(q,vec2(-0.45,0.0),vec2(0.0,0.42),0.055),seg(q,vec2(0.0,0.42),vec2(0.45,0.0),0.055));"
        "ink=max(ink,seg(q,vec2(-0.45,0.0),vec2(0.0,-0.42),0.055));"
        "ink=max(ink,seg(q,vec2(0.0,-0.42),vec2(0.45,0.0),0.055));"
        "}else if(uIcon==5){"
        "ink=max(seg(q,vec2(-0.45,-0.20),vec2(0.0,0.25),0.065),seg(q,vec2(0.0,0.25),vec2(0.45,-0.20),0.065));"
        "ink=max(ink,seg(q,vec2(-0.30,-0.42),vec2(0.30,-0.42),0.060));"
        "}else if(uIcon==6){"
        "ink=max(seg(q,vec2(-0.48,-0.30),vec2(0.05,0.0),0.065),seg(q,vec2(0.05,0.0),vec2(-0.48,0.30),0.065));"
        "ink=max(ink,max(seg(q,vec2(0.0,-0.30),vec2(0.52,0.0),0.065),seg(q,vec2(0.52,0.0),vec2(0.0,0.30),0.065)));"
        "}else if(uIcon==7){"
        "ink=1.0-smoothstep(0.36,0.43,length(q-vec2(0.0,-0.08)));"
        "ink=max(ink,seg(q,vec2(0.05,0.34),vec2(0.32,0.58),0.055));"
        "}else if(uIcon==8){"
        "ink=max(seg(q,vec2(-0.52,0.22),vec2(0.42,0.22),0.055),seg(q,vec2(0.42,0.22),vec2(0.18,0.45),0.055));"
        "ink=max(ink,seg(q,vec2(0.52,-0.22),vec2(-0.42,-0.22),0.055));"
        "ink=max(ink,seg(q,vec2(-0.42,-0.22),vec2(-0.18,-0.45),0.055));"
        "}"
        "vec3 inkColor=mix(vec3(0.90),vec3(1.0,0.12,0.58),uPressed);"
        "fragColor=vec4(mix(base,inkColor,ink),max(a,ink*(0.74+0.20*uPressed))*uAlpha);"
        "}\n";

    GLuint vert = XzCompileShader(GL_VERTEX_SHADER, vs);
    GLuint frag = XzCompileShader(GL_FRAGMENT_SHADER, fs);
    GLint ok = GL_FALSE;

    if (!vert || !frag) {
        if (vert) glDeleteShader(vert);
        if (frag) glDeleteShader(frag);
        return 0;
    }

    controls->program = glCreateProgram();
    glAttachShader(controls->program, vert);
    glAttachShader(controls->program, frag);
    glLinkProgram(controls->program);
    glDeleteShader(vert);
    glDeleteShader(frag);

    glGetProgramiv(controls->program, GL_LINK_STATUS, &ok);
    if (ok != GL_TRUE)
        return 0;

    controls->u_resolution = glGetUniformLocation(controls->program, "uResolution");
    controls->u_center = glGetUniformLocation(controls->program, "uCenter");
    controls->u_radius = glGetUniformLocation(controls->program, "uRadius");
    controls->u_icon = glGetUniformLocation(controls->program, "uIcon");
    controls->u_pressed = glGetUniformLocation(controls->program, "uPressed");
    controls->u_alpha = glGetUniformLocation(controls->program, "uAlpha");
    return 1;
}

static float XzAspect(const XzMobileControls *controls)
{
    if (controls && controls->screen_width > 0 && controls->screen_height > 0)
        return (float)controls->screen_width / (float)controls->screen_height;
    return 16.0f / 9.0f;
}

static float XzTouchDistance(
    const XzMobileControls *controls,
    float x,
    float y,
    float cx,
    float cy)
{
    float dx = (x - cx) * XzAspect(controls);
    float dy = y - cy;
    return sqrtf(dx * dx + dy * dy);
}

static int XzHitButton(
    const XzMobileControls *controls,
    float x,
    float y)
{
    int i;
    for (i = 0; i < XZ_MOBILE_BUTTON_COUNT; ++i) {
        if (XzTouchDistance(
                controls, x, y,
                kButtons[i].x, kButtons[i].y) <=
            kButtons[i].radius * 1.16f)
            return i;
    }
    return -1;
}

static void XzSetButton(
    XzMobileControls *controls,
    int button,
    int down)
{
    uint32_t mask;
    if (!controls || button < 0 || button >= XZ_MOBILE_BUTTON_COUNT)
        return;
    mask = 1u << (unsigned int)button;
    if (down) {
        if ((controls->buttons_down & mask) == 0u)
            controls->buttons_pressed |= mask;
        controls->buttons_down |= mask;
    } else {
        controls->buttons_down &= ~mask;
    }
}

static void XzReleaseFinger(
    XzMobileControls *controls,
    SDL_FingerID finger,
    float x,
    float y)
{
    int button = XzHitButton(controls, x, y);
    if (button >= 0)
        XzSetButton(controls, button, 0);

    if (controls->move_active && controls->move_finger == finger) {
        controls->move_active = 0;
        controls->move_x = 0.0f;
        controls->move_y = 0.0f;
    }

    if (controls->look_active && controls->look_finger == finger)
        controls->look_active = 0;
}

int XzMobileControls_Init(XzMobileControls *controls)
{
    static const GLfloat quad[] = {
        -1.0f, -1.0f,
         1.0f, -1.0f,
        -1.0f,  1.0f,
         1.0f,  1.0f
    };

    if (!controls)
        return 0;

    memset(controls, 0, sizeof(*controls));
    controls->move_finger = (SDL_FingerID)-1;
    controls->look_finger = (SDL_FingerID)-1;

    if (!XzBuildProgram(controls))
        return 0;

    glGenVertexArrays(1, &controls->vao);
    glGenBuffers(1, &controls->vbo);
    if (!controls->vao || !controls->vbo)
        return 0;

    glBindVertexArray(controls->vao);
    glBindBuffer(GL_ARRAY_BUFFER, controls->vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(quad), quad, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(GLfloat), (const void *)0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glBindVertexArray(0);

    controls->initialized = 1;
    return 1;
}

void XzMobileControls_Shutdown(XzMobileControls *controls)
{
    if (!controls)
        return;
    if (controls->vbo)
        glDeleteBuffers(1, &controls->vbo);
    if (controls->vao)
        glDeleteVertexArrays(1, &controls->vao);
    if (controls->program)
        glDeleteProgram(controls->program);
    memset(controls, 0, sizeof(*controls));
}

void XzMobileControls_BeginFrame(XzMobileControls *controls)
{
    if (!controls)
        return;
    controls->buttons_pressed = 0u;
    controls->look_dx = 0.0f;
    controls->look_dy = 0.0f;
}

void XzMobileControls_HandleEvent(
    XzMobileControls *controls,
    const SDL_Event *event)
{
    float x;
    float y;
    SDL_FingerID finger;
    int button;

    if (!controls || !event)
        return;

    if (event->type != SDL_FINGERDOWN &&
        event->type != SDL_FINGERMOTION &&
        event->type != SDL_FINGERUP)
        return;

    x = event->tfinger.x;
    y = event->tfinger.y;
    finger = event->tfinger.fingerId;

    if (event->type == SDL_FINGERDOWN) {
        button = XzHitButton(controls, x, y);
        if (button >= 0) {
            XzSetButton(controls, button, 1);
            return;
        }

        if (!controls->move_active && x < 0.44f && y > 0.42f) {
            controls->move_active = 1;
            controls->move_finger = finger;
            controls->move_origin_x = x;
            controls->move_origin_y = y;
            controls->move_x = 0.0f;
            controls->move_y = 0.0f;
            return;
        }

        if (!controls->look_active && x >= 0.38f) {
            controls->look_active = 1;
            controls->look_finger = finger;
            controls->look_last_x = x;
            controls->look_last_y = y;
        }
        return;
    }

    if (event->type == SDL_FINGERMOTION) {
        if (controls->move_active && controls->move_finger == finger) {
            const float radius = 0.115f;
            float dx = (x - controls->move_origin_x) * XzAspect(controls);
            float dy = controls->move_origin_y - y;
            float len = sqrtf(dx * dx + dy * dy);
            if (len > radius && len > 0.0001f) {
                dx *= radius / len;
                dy *= radius / len;
            }
            controls->move_x = dx / radius;
            controls->move_y = dy / radius;
            return;
        }

        if (controls->look_active && controls->look_finger == finger) {
            controls->look_dx += x - controls->look_last_x;
            controls->look_dy += y - controls->look_last_y;
            controls->look_last_x = x;
            controls->look_last_y = y;
            return;
        }

        return;
    }

    if (event->type == SDL_FINGERUP)
        XzReleaseFinger(controls, finger, x, y);
}

void XzMobileControls_GetMove(
    const XzMobileControls *controls,
    float *out_x,
    float *out_y)
{
    if (out_x)
        *out_x = controls ? controls->move_x : 0.0f;
    if (out_y)
        *out_y = controls ? controls->move_y : 0.0f;
}

void XzMobileControls_ConsumeLook(
    XzMobileControls *controls,
    float *out_dx,
    float *out_dy)
{
    if (out_dx)
        *out_dx = controls ? controls->look_dx : 0.0f;
    if (out_dy)
        *out_dy = controls ? controls->look_dy : 0.0f;
    if (controls) {
        controls->look_dx = 0.0f;
        controls->look_dy = 0.0f;
    }
}

int XzMobileControls_ButtonDown(
    const XzMobileControls *controls,
    XzMobileButton button)
{
    if (!controls || button < 0 || button >= XZ_MOBILE_BUTTON_COUNT)
        return 0;
    return (controls->buttons_down & (1u << (unsigned int)button)) != 0u;
}

int XzMobileControls_ButtonPressed(
    const XzMobileControls *controls,
    XzMobileButton button)
{
    if (!controls || button < 0 || button >= XZ_MOBILE_BUTTON_COUNT)
        return 0;
    return (controls->buttons_pressed & (1u << (unsigned int)button)) != 0u;
}

static void XzDrawButton(
    XzMobileControls *controls,
    float x,
    float y_top,
    float radius,
    int icon,
    int pressed,
    float alpha)
{
    glUniform2f(controls->u_center, x, 1.0f - y_top);
    glUniform1f(controls->u_radius, radius);
    glUniform1i(controls->u_icon, icon);
    glUniform1f(controls->u_pressed, pressed ? 1.0f : 0.0f);
    glUniform1f(controls->u_alpha, alpha);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
}

void XzMobileControls_Render(
    XzMobileControls *controls,
    int width,
    int height)
{
    int i;
    float joy_x;
    float joy_y;
    float knob_x;
    float knob_y;
    GLint old_program = 0;
    GLint old_vao = 0;
    GLboolean blend_was_enabled;
    GLboolean depth_was_enabled;

    if (!controls || !controls->initialized || width <= 0 || height <= 0)
        return;

    controls->screen_width = width;
    controls->screen_height = height;

    glGetIntegerv(GL_CURRENT_PROGRAM, &old_program);
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &old_vao);
    blend_was_enabled = glIsEnabled(GL_BLEND);
    depth_was_enabled = glIsEnabled(GL_DEPTH_TEST);

    glDisable(GL_DEPTH_TEST);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    glUseProgram(controls->program);
    glBindVertexArray(controls->vao);
    glUniform2f(controls->u_resolution, (float)width, (float)height);

    joy_x = controls->move_active ? controls->move_origin_x : 0.175f;
    joy_y = controls->move_active ? controls->move_origin_y : 0.775f;
    XzDrawButton(controls, joy_x, joy_y, 0.105f, 0, controls->move_active, 0.70f);

    knob_x = joy_x + controls->move_x * 0.040f / XzAspect(controls);
    knob_y = joy_y - controls->move_y * 0.040f;
    XzDrawButton(controls, knob_x, knob_y, 0.038f, 0, controls->move_active, 0.86f);

    for (i = 0; i < XZ_MOBILE_BUTTON_COUNT; ++i) {
        const int pressed =
            (controls->buttons_down & (1u << (unsigned int)i)) != 0u;
        XzDrawButton(
            controls,
            kButtons[i].x,
            kButtons[i].y,
            kButtons[i].radius,
            kButtons[i].icon,
            pressed,
            0.88f);
    }

    glBindVertexArray((GLuint)old_vao);
    glUseProgram((GLuint)old_program);

    if (!blend_was_enabled)
        glDisable(GL_BLEND);
    if (depth_was_enabled)
        glEnable(GL_DEPTH_TEST);
}
