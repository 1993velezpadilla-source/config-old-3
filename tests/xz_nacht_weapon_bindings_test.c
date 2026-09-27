#include "xz_nacht_weapon_bindings.h"

#include <assert.h>
#include <string.h>

int main(void)
{
    const XzNachtPurchase *purchase = NULL;
    const XzBo3WeaponSpec *spec = NULL;
    XzBo3WeaponRuntimeState runtime;
    size_t index;
    size_t resolved = 0u;

    assert(XzNachtWeaponBinding_SelfTest());

    assert(
        XzNachtWeaponBinding_Resolve(
            0u,
            &purchase,
            &spec) ==
        XZ_NACHT_WEAPON_BINDING_OK);
    assert(purchase && spec);
    assert(strcmp(purchase->display_name, "KN-44") == 0);
    assert(strcmp(spec->logical_item_id, "ar_standard") == 0);
    assert(purchase->price == 1400u);
    assert(spec->wall_cost == 1400u);

    purchase = NULL;
    spec = NULL;
    assert(
        XzNachtWeaponBinding_Resolve(
            2u,
            &purchase,
            &spec) ==
        XZ_NACHT_WEAPON_BINDING_NON_FIREARM);
    assert(purchase == NULL);
    assert(spec == NULL);

    assert(
        XzNachtWeaponBinding_Resolve(
            5u,
            &purchase,
            &spec) ==
        XZ_NACHT_WEAPON_BINDING_OK);
    assert(purchase && spec);
    assert(strcmp(purchase->display_name, "Locus") == 0);
    assert(spec->wall_cost == 5000u);
    assert(spec->wall_refill_cost == 2500u);

    for (index = 0u;
         index < XZ_NACHT_PURCHASE_COUNT;
         ++index) {
        XzNachtWeaponBindingResult result =
            XzNachtWeaponBinding_Resolve(
                index,
                NULL,
                NULL);

        if (index == 2u) {
            assert(
                result ==
                XZ_NACHT_WEAPON_BINDING_NON_FIREARM);
            continue;
        }

        assert(result == XZ_NACHT_WEAPON_BINDING_OK);
        assert(!XzNachtWeaponBinding_CanExposePlayable(index));
        resolved++;
    }

    assert(resolved == XZ_NACHT_FIREARM_BINDING_COUNT);

    assert(
        XzNachtWeaponBinding_InitBehaviorRuntime(
            8u,
            &runtime) ==
        XZ_NACHT_WEAPON_BINDING_OK);
    assert(runtime.spec != NULL);
    assert(strcmp(runtime.spec->display_name, "RK5") == 0);
    assert(runtime.magazine_ammo == 15u);
    assert(runtime.reserve_ammo == 120u);
    assert(!XzBo3WeaponRuntime_IsPlayable(&runtime));

    assert(
        XzNachtWeaponBinding_InitBehaviorRuntime(
            2u,
            &runtime) ==
        XZ_NACHT_WEAPON_BINDING_NON_FIREARM);

    assert(
        XzNachtWeaponBinding_Resolve(
            XZ_NACHT_PURCHASE_COUNT,
            NULL,
            NULL) ==
        XZ_NACHT_WEAPON_BINDING_INVALID_INDEX);

    assert(
        XzNachtWeaponBinding_InitBehaviorRuntime(
            0u,
            NULL) ==
        XZ_NACHT_WEAPON_BINDING_RUNTIME_INIT_FAILED);

    assert(strcmp(
        XzNachtWeaponBinding_ResultName(
            XZ_NACHT_WEAPON_BINDING_COST_MISMATCH),
        "COST_MISMATCH") == 0);

    return 0;
}
