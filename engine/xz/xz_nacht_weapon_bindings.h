#ifndef XZ_NACHT_WEAPON_BINDINGS_H
#define XZ_NACHT_WEAPON_BINDINGS_H

#include "xz_bo3_weapon_runtime.h"
#include "xz_nacht_reference.h"

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_NACHT_FIREARM_BINDING_COUNT 8u

typedef enum XzNachtWeaponBindingResult {
    XZ_NACHT_WEAPON_BINDING_OK = 0,
    XZ_NACHT_WEAPON_BINDING_INVALID_INDEX,
    XZ_NACHT_WEAPON_BINDING_NON_FIREARM,
    XZ_NACHT_WEAPON_BINDING_MISSING_SPEC,
    XZ_NACHT_WEAPON_BINDING_IDENTITY_MISMATCH,
    XZ_NACHT_WEAPON_BINDING_COST_MISMATCH,
    XZ_NACHT_WEAPON_BINDING_NOT_NATIVE_READY
} XzNachtWeaponBindingResult;

XzNachtWeaponBindingResult XzNachtWeaponBinding_Resolve(
    size_t purchase_index,
    const XzNachtPurchase **purchase_out,
    const XzBo3WeaponSpec **spec_out);

XzNachtWeaponBindingResult XzNachtWeaponBinding_InitBehaviorRuntime(
    size_t purchase_index,
    XzBo3WeaponRuntimeState *runtime_out);

int XzNachtWeaponBinding_CanExposePlayable(
    size_t purchase_index);

int XzNachtWeaponBinding_SelfTest(void);

const char *XzNachtWeaponBinding_ResultName(
    XzNachtWeaponBindingResult result);

#ifdef __cplusplus
}
#endif

#endif
