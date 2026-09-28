#define _GNU_SOURCE
#include "ctw_patch.h"
#include "ctw_mod_runtime.h"

#include <assert.h>
#include <dlfcn.h>

__attribute__((visibility("default")))
void Java_com_rockstargames_oswrapper_GameNative_implOnDrawFrame(void) {}

__attribute__((visibility("default")))
void Java_com_rockstargames_oswrapper_GameNative_implOnInitialSetup(void) {}

__attribute__((visibility("default")))
void Java_com_rockstargames_oswrapper_GameNative_implOnGamepadAxesChanged(void) {}

int main(void) {
    void *self = dlopen(NULL, RTLD_NOW);
    assert(self != NULL);

    /*
     * The committed generated profile table is deliberately empty.
     * Runtime init must therefore refuse to patch and return a clean,
     * explicit no-profile status instead of leaving unresolved hooks.
     */
    assert(ctw_mod_init(self) == CTW_PATCH_PROFILE_NOT_FOUND);
    assert(ctw_mod_hooks_active() == 0);
    assert(
        ctw_mod_original_for_hook(CTW_HOOK_CAMERA_UPDATE) == NULL
    );
    assert(ctw_mod_original_for_hook(CTW_HOOK_COUNT) == NULL);
    ctw_mod_shutdown();
    assert(ctw_mod_hooks_active() == 0);

    dlclose(self);
    return 0;
}
