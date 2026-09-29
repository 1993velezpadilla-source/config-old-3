#include "xz_gles3_probe.h"

#include <EGL/egl.h>
#include <GLES3/gl3.h>

#include <SDL_loadso.h>
#include <stdio.h>
#include <string.h>

#if defined(_WIN32)
#define XZ_GLES_LIBRARY_NAME "libGLESv2.dll"
#else
#define XZ_GLES_LIBRARY_NAME "libGLESv2.so"
#endif

#ifndef EGL_OPENGL_ES3_BIT_KHR
#define EGL_OPENGL_ES3_BIT_KHR 0x00000040
#endif

typedef const GLubyte *(*XzGlGetStringFn)(GLenum);
typedef GLuint (*XzGlCreateShaderFn)(GLenum);
typedef void (*XzGlShaderSourceFn)(
    GLuint, GLsizei, const GLchar *const *, const GLint *);
typedef void (*XzGlCompileShaderFn)(GLuint);
typedef void (*XzGlGetShaderivFn)(GLuint, GLenum, GLint *);
typedef void (*XzGlDeleteShaderFn)(GLuint);
typedef GLuint (*XzGlCreateProgramFn)(void);
typedef void (*XzGlAttachShaderFn)(GLuint, GLuint);
typedef void (*XzGlLinkProgramFn)(GLuint);
typedef void (*XzGlGetProgramivFn)(GLuint, GLenum, GLint *);
typedef void (*XzGlDeleteProgramFn)(GLuint);
typedef void (*XzGlClearColorFn)(GLfloat, GLfloat, GLfloat, GLfloat);
typedef void (*XzGlClearFn)(GLbitfield);
typedef void (*XzGlFinishFn)(void);
typedef GLenum (*XzGlGetErrorFn)(void);

typedef struct {
    void *library;
    XzGlGetStringFn GetString;
    XzGlCreateShaderFn CreateShader;
    XzGlShaderSourceFn ShaderSource;
    XzGlCompileShaderFn CompileShader;
    XzGlGetShaderivFn GetShaderiv;
    XzGlDeleteShaderFn DeleteShader;
    XzGlCreateProgramFn CreateProgram;
    XzGlAttachShaderFn AttachShader;
    XzGlLinkProgramFn LinkProgram;
    XzGlGetProgramivFn GetProgramiv;
    XzGlDeleteProgramFn DeleteProgram;
    XzGlClearColorFn ClearColor;
    XzGlClearFn Clear;
    XzGlFinishFn Finish;
    XzGlGetErrorFn GetError;
} XzNativeGles3;

static void XzCopyString(
    char *dst,
    size_t dst_size,
    const GLubyte *src)
{
    if (!dst || dst_size == 0u)
        return;

    if (!src) {
        dst[0] = '\0';
        return;
    }

    snprintf(dst, dst_size, "%s", (const char *)src);
}

static int XzLoadNativeGles3(XzNativeGles3 *api)
{
#define XZ_LOAD_GL(field, symbol)                                      \
    do {                                                               \
        *(void **)(&api->field) = SDL_LoadFunction(api->library, symbol);         \
        if (!api->field)                                               \
            return 0;                                                  \
    } while (0)

    memset(api, 0, sizeof(*api));
    api->library = SDL_LoadObject(XZ_GLES_LIBRARY_NAME);
    if (!api->library)
        return 0;

    XZ_LOAD_GL(GetString, "glGetString");
    XZ_LOAD_GL(CreateShader, "glCreateShader");
    XZ_LOAD_GL(ShaderSource, "glShaderSource");
    XZ_LOAD_GL(CompileShader, "glCompileShader");
    XZ_LOAD_GL(GetShaderiv, "glGetShaderiv");
    XZ_LOAD_GL(DeleteShader, "glDeleteShader");
    XZ_LOAD_GL(CreateProgram, "glCreateProgram");
    XZ_LOAD_GL(AttachShader, "glAttachShader");
    XZ_LOAD_GL(LinkProgram, "glLinkProgram");
    XZ_LOAD_GL(GetProgramiv, "glGetProgramiv");
    XZ_LOAD_GL(DeleteProgram, "glDeleteProgram");
    XZ_LOAD_GL(ClearColor, "glClearColor");
    XZ_LOAD_GL(Clear, "glClear");
    XZ_LOAD_GL(Finish, "glFinish");
    XZ_LOAD_GL(GetError, "glGetError");

#undef XZ_LOAD_GL
    return 1;
}

static void XzUnloadNativeGles3(XzNativeGles3 *api)
{
    if (api && api->library)
        SDL_UnloadObject(api->library);
    if (api)
        memset(api, 0, sizeof(*api));
}

static int XzCompileShader(
    const XzNativeGles3 *gl,
    GLenum type,
    const char *source,
    GLuint *shader_out)
{
    GLuint shader;
    GLint ok = 0;

    shader = gl->CreateShader(type);
    if (!shader)
        return 0;

    gl->ShaderSource(shader, 1, &source, NULL);
    gl->CompileShader(shader);
    gl->GetShaderiv(shader, GL_COMPILE_STATUS, &ok);

    if (!ok) {
        gl->DeleteShader(shader);
        return 0;
    }

    *shader_out = shader;
    return 1;
}

void XzGles3Probe_InitResult(XzGles3ProbeResult *result)
{
    if (!result)
        return;

    memset(result, 0, sizeof(*result));
    result->status = XZ_GLES3_PROBE_NOT_RUN;
}

int XzGles3Probe_Run(XzGles3ProbeResult *result)
{
    static const char *vertex_source =
        "#version 300 es\n"
        "layout(location=0) in vec2 aPos;\n"
        "void main(){ gl_Position=vec4(aPos,0.0,1.0); }\n";
    static const char *fragment_source =
        "#version 300 es\n"
        "precision mediump float;\n"
        "out vec4 outColor;\n"
        "void main(){ outColor=vec4(0.2,0.4,0.8,1.0); }\n";

    EGLDisplay display;
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;
    EGLConfig config = NULL;
    EGLint config_count = 0;
    EGLSurface pbuffer = EGL_NO_SURFACE;
    EGLContext context = EGL_NO_CONTEXT;
    EGLint egl_major = 0;
    EGLint egl_minor = 0;
    XzNativeGles3 gl;
    GLuint vs = 0u;
    GLuint fs = 0u;
    GLuint program = 0u;
    GLint linked = 0;
    int ok = 0;
    int made_current = 0;

    const EGLint config_attribs[] = {
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_NONE
    };
    const EGLint pbuffer_attribs[] = {
        EGL_WIDTH, 1,
        EGL_HEIGHT, 1,
        EGL_NONE
    };
    const EGLint context_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_NONE
    };

    if (!result)
        return 0;

    XzGles3Probe_InitResult(result);
    memset(&gl, 0, sizeof(gl));

    previous_display = eglGetCurrentDisplay();
    previous_draw = eglGetCurrentSurface(EGL_DRAW);
    previous_read = eglGetCurrentSurface(EGL_READ);
    previous_context = eglGetCurrentContext();

    display = previous_display;
    if (display == EGL_NO_DISPLAY)
        display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (display == EGL_NO_DISPLAY)
        goto cleanup;

    if (!eglInitialize(display, &egl_major, &egl_minor))
        goto cleanup;

    result->egl_major = egl_major;
    result->egl_minor = egl_minor;

    if (!eglBindAPI(EGL_OPENGL_ES_API))
        goto cleanup;

    if (!eglChooseConfig(
            display,
            config_attribs,
            &config,
            1,
            &config_count) ||
        config_count < 1)
        goto cleanup;

    pbuffer = eglCreatePbufferSurface(
        display,
        config,
        pbuffer_attribs);
    if (pbuffer == EGL_NO_SURFACE)
        goto cleanup;

    context = eglCreateContext(
        display,
        config,
        EGL_NO_CONTEXT,
        context_attribs);
    if (context == EGL_NO_CONTEXT)
        goto cleanup;

    if (!eglMakeCurrent(
            display,
            pbuffer,
            pbuffer,
            context))
        goto cleanup;

    made_current = 1;
    result->status = XZ_GLES3_PROBE_CONTEXT_OK;

    if (!XzLoadNativeGles3(&gl))
        goto cleanup;

    XzCopyString(
        result->vendor,
        sizeof(result->vendor),
        gl.GetString(GL_VENDOR));
    XzCopyString(
        result->renderer,
        sizeof(result->renderer),
        gl.GetString(GL_RENDERER));
    XzCopyString(
        result->version,
        sizeof(result->version),
        gl.GetString(GL_VERSION));

    if (sscanf(result->version, "OpenGL ES %d.%d",
               &result->gl_major,
               &result->gl_minor) != 2) {
        result->gl_major = 0;
        result->gl_minor = 0;
    }

    if (result->gl_major < 3)
        goto cleanup;

    if (!XzCompileShader(
            &gl,
            GL_VERTEX_SHADER,
            vertex_source,
            &vs))
        goto cleanup;

    if (!XzCompileShader(
            &gl,
            GL_FRAGMENT_SHADER,
            fragment_source,
            &fs))
        goto cleanup;

    result->shader_compile_ok = 1;

    program = gl.CreateProgram();
    if (!program)
        goto cleanup;

    gl.AttachShader(program, vs);
    gl.AttachShader(program, fs);
    gl.LinkProgram(program);
    gl.GetProgramiv(program, GL_LINK_STATUS, &linked);
    if (!linked)
        goto cleanup;

    result->shader_link_ok = 1;

    gl.ClearColor(0.02f, 0.03f, 0.04f, 1.0f);
    gl.Clear(GL_COLOR_BUFFER_BIT);
    gl.Finish();

    result->gl_error = (unsigned int)gl.GetError();
    if (result->gl_error != GL_NO_ERROR)
        goto cleanup;

    result->status = XZ_GLES3_PROBE_SHADER_OK;
    ok = 1;

cleanup:
    if (gl.DeleteProgram && program)
        gl.DeleteProgram(program);
    if (gl.DeleteShader && vs)
        gl.DeleteShader(vs);
    if (gl.DeleteShader && fs)
        gl.DeleteShader(fs);

    XzUnloadNativeGles3(&gl);

    if (made_current) {
        if (previous_display != EGL_NO_DISPLAY &&
            previous_context != EGL_NO_CONTEXT) {
            result->restore_ok = eglMakeCurrent(
                previous_display,
                previous_draw,
                previous_read,
                previous_context) ? 1 : 0;
        } else {
            result->restore_ok = eglMakeCurrent(
                display,
                EGL_NO_SURFACE,
                EGL_NO_SURFACE,
                EGL_NO_CONTEXT) ? 1 : 0;
        }
    } else {
        result->restore_ok = 1;
    }

    if (context != EGL_NO_CONTEXT)
        eglDestroyContext(display, context);
    if (pbuffer != EGL_NO_SURFACE)
        eglDestroySurface(display, pbuffer);

    if (!result->restore_ok)
        return 0;

    if (!ok && result->status == XZ_GLES3_PROBE_NOT_RUN)
        result->status = XZ_GLES3_PROBE_UNAVAILABLE;

    return ok;
}

const char *XzGles3ProbeStatus_Name(XzGles3ProbeStatus status)
{
    switch (status) {
    case XZ_GLES3_PROBE_NOT_RUN: return "NOT_RUN";
    case XZ_GLES3_PROBE_UNAVAILABLE: return "UNAVAILABLE";
    case XZ_GLES3_PROBE_CONTEXT_OK: return "CONTEXT_OK";
    case XZ_GLES3_PROBE_SHADER_OK: return "SHADER_OK";
    default: return "UNKNOWN";
    }
}
