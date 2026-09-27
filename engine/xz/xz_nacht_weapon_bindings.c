#include "xz_nacht_weapon_bindings.h"

#include <string.h>

XzNachtWeaponBindingResult XzNachtWeaponBinding_Resolve(
    size_t purchase_index,
    const XzNachtPurchase **purchase_out,
    const XzBo3WeaponSpec **spec_out)
{
    const XzNachtPurchase *purchase;
    const XzBo3WeaponSpec *spec;

    if (purchase_out)
        *purchase_out = NULL;
    if (spec_out)
        *spec_out = NULL;

    if (purchase_index >= XZ_NACHT_PURCHASE_COUNT)
        return XZ_NACHT_WEAPON_BINDING_INVALID_INDEX;

    purchase = XzNacht_GetPurchase(purchase_index);
    if (!purchase)
        return XZ_NACHT_WEAPON_BINDING_INVALID_INDEX;

    if (purchase->kind == XZ_NACHT_PURCHASE_EQUIPMENT)
        return XZ_NACHT_WEAPON_BINDING_NON_FIREARM;

    spec = XzBo3WeaponSpec_FindByLogicalItemId(
        purchase->logical_item_id);
    if (!spec)
        return XZ_NACHT_WEAPON_BINDING_MISSING_SPEC;

    if (!spec->logical_item_id ||
        !spec->display_name ||
        strcmp(
            spec->logical_item_id,
            purchase->logical_item_id) != 0 ||
        strcmp(
            spec->display_name,
            purchase->display_name) != 0)
        return XZ_NACHT_WEAPON_BINDING_IDENTITY_MISMATCH;

    if (spec->wall_cost != purchase->price)
        return XZ_NACHT_WEAPON_BINDING_COST_MISMATCH;

    if (purchase_out)
        *purchase_out = purchase;
    if (spec_out)
        *spec_out = spec;

    return XZ_NACHT_WEAPON_BINDING_OK;
}

XzNachtWeaponBindingResult XzNachtWeaponBinding_InitBehaviorRuntime(
    size_t purchase_index,
    XzBo3WeaponRuntimeState *runtime_out)
{
    const XzBo3WeaponSpec *spec = NULL;
    XzNachtWeaponBindingResult result;

    if (!runtime_out)
        return XZ_NACHT_WEAPON_BINDING_RUNTIME_INIT_FAILED;

    result = XzNachtWeaponBinding_Resolve(
        purchase_index,
        NULL,
        &spec);
    if (result != XZ_NACHT_WEAPON_BINDING_OK)
        return result;

    if (XzBo3WeaponRuntime_Init(
            runtime_out,
            spec) != XZ_BO3_WEAPON_RUNTIME_OK)
        return XZ_NACHT_WEAPON_BINDING_RUNTIME_INIT_FAILED;

    return XZ_NACHT_WEAPON_BINDING_OK;
}

int XzNachtWeaponBinding_CanExposePlayable(
    size_t purchase_index)
{
    const XzBo3WeaponSpec *spec = NULL;

    if (XzNachtWeaponBinding_Resolve(
            purchase_index,
            NULL,
            &spec) != XZ_NACHT_WEAPON_BINDING_OK)
        return 0;

    return XzBo3WeaponSpec_IsNativeReady(spec);
}

int XzNachtWeaponBinding_SelfTest(void)
{
    size_t index;
    size_t firearm_count = 0u;
    size_t equipment_count = 0u;

    for (index = 0u;
         index < XZ_NACHT_PURCHASE_COUNT;
         ++index) {
        const XzNachtPurchase *purchase = NULL;
        const XzBo3WeaponSpec *spec = NULL;
        XzBo3WeaponRuntimeState runtime;
        XzNachtWeaponBindingResult result;

        result = XzNachtWeaponBinding_Resolve(
            index,
            &purchase,
            &spec);

        if (result == XZ_NACHT_WEAPON_BINDING_NON_FIREARM) {
            equipment_count++;
            if (purchase || spec)
                return 0;
            continue;
        }

        if (result != XZ_NACHT_WEAPON_BINDING_OK ||
            !purchase ||
            !spec)
            return 0;

        firearm_count++;

        if (XzNachtWeaponBinding_InitBehaviorRuntime(
                index,
                &runtime) != XZ_NACHT_WEAPON_BINDING_OK)
            return 0;

        if (runtime.spec != spec ||
            runtime.magazine_ammo != spec->magazine ||
            runtime.reserve_ammo != spec->reserve)
            return 0;

        /*
         * Behavior bindings may be exercised in tests before art/audio/native
         * implementation is complete, but must never leak through as playable.
         */
        if (XzNachtWeaponBinding_CanExposePlayable(index))
            return 0;
    }

    return firearm_count == XZ_NACHT_FIREARM_BINDING_COUNT &&
        equipment_count == 1u;
}

const char *XzNachtWeaponBinding_ResultName(
    XzNachtWeaponBindingResult result)
{
    switch (result) {
    case XZ_NACHT_WEAPON_BINDING_OK:
        return "OK";
    case XZ_NACHT_WEAPON_BINDING_INVALID_INDEX:
        return "INVALID_INDEX";
    case XZ_NACHT_WEAPON_BINDING_NON_FIREARM:
        return "NON_FIREARM";
    case XZ_NACHT_WEAPON_BINDING_MISSING_SPEC:
        return "MISSING_SPEC";
    case XZ_NACHT_WEAPON_BINDING_IDENTITY_MISMATCH:
        return "IDENTITY_MISMATCH";
    case XZ_NACHT_WEAPON_BINDING_COST_MISMATCH:
        return "COST_MISMATCH";
    case XZ_NACHT_WEAPON_BINDING_RUNTIME_INIT_FAILED:
        return "RUNTIME_INIT_FAILED";
    case XZ_NACHT_WEAPON_BINDING_NOT_NATIVE_READY:
        return "NOT_NATIVE_READY";
    default:
        return "UNKNOWN";
    }
}
