#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Resolve helper symbols from the exact verified Rockstar libGame_orig.so
 * before any runtime hook is installed.
 */
int ctw_runtime_adapters_bind(void *original_game_handle);
int ctw_runtime_adapters_install_aux(void);
int ctw_runtime_adapters_uninstall_aux(void);

#ifdef __cplusplus
}
#endif
