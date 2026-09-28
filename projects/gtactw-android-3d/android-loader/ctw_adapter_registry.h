#pragma once

#include "ctw_hooks.h"
#include "ctw_profile.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *name;
    void *replacement;
} CtwAdapterBinding;

/*
 * Returns 0 when all six profile adapter names resolve to compiled native
 * functions, 1 when one or more verified adapter functions are not compiled,
 * and a negative value for invalid input.
 */
int ctw_adapter_registry_resolve_from(
    const CtwBuildProfile *profile,
    CtwHookReplacements *out,
    const CtwAdapterBinding *bindings,
    size_t binding_count
);

int ctw_adapter_registry_resolve(
    const CtwBuildProfile *profile,
    CtwHookReplacements *out
);

#ifdef __cplusplus
}
#endif
