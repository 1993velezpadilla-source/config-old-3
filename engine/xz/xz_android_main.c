#include "xz_android_runtime.h"
#include "xz_file_io.h"

#include <SDL.h>
#include <SDL_system.h>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

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

int main(int argc, char **argv)
{
    const char *root =
        XzArgValue(argc, argv, "--xziel-root", ".");
    const char *map_id =
        XzArgValue(
            argc,
            argv,
            "--xziel-map",
            "xziel_nuketown_zombies");
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

    XzAndroidRuntime_Init(256u * 1024u * 1024u);
    XzAndroidRuntime_SetVerifiedMapPackageMode(1);
    XzAndroidRuntime_NotifyWorldTransitionNamed(map_id);

    while (running) {
        SDL_Event event;
        double now;

        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT)
                running = 0;
            if (event.type == SDL_KEYDOWN &&
                event.key.keysym.sym == SDLK_ESCAPE)
                running = 0;
        }

        now = (double)SDL_GetPerformanceCounter() /
            (double)SDL_GetPerformanceFrequency();

        XzAndroidRuntime_BeginFrame(now);
        XzAndroidRuntime_EndFrame(now);
        SDL_GL_SwapWindow(window);
        SDL_Delay(1);
    }

    XzAndroidRuntime_Shutdown();
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
