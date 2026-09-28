#pragma once

#include "ctw_hooks.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Runtime adapter-facing API.
 * Returns NULL unless the six-hook session is fully active.
 */
void *ctw_mod_original_for_hook(size_t hook_index);
int ctw_mod_hooks_active(void);

#ifdef __cplusplus
}
#endif
