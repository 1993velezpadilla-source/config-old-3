#include "xz_nacht_mystery_box.h"

#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct TestContext {
    uint32_t rng_values[XZ_NACHT_MYSTERY_BOX_POOL_COUNT];
    size_t rng_index;

    const char *owned[8];
    size_t owned_count;

    const char *limited_id;
    uint32_t limited_count;

    int allow_content;
    int allow_special;
    int native_ready_all;
} TestContext;

static uint32_t RandomSequence(
    void *opaque,
    uint32_t upper_exclusive)
{
    TestContext *context = (TestContext *)opaque;
    uint32_t value;

    assert(context != NULL);
    assert(upper_exclusive == XZ_NACHT_MYSTERY_BOX_POOL_COUNT);
    assert(context->rng_index < XZ_NACHT_MYSTERY_BOX_POOL_COUNT);

    value = context->rng_values[context->rng_index++];
    return value;
}

static int Owns(
    void *opaque,
    const char *weapon_id)
{
    TestContext *context = (TestContext *)opaque;
    size_t i;

    for (i = 0u; i < context->owned_count; ++i) {
        if (strcmp(context->owned[i], weapon_id) == 0)
            return 1;
    }

    return 0;
}

static uint32_t LimitedCount(
    void *opaque,
    const char *weapon_id)
{
    TestContext *context = (TestContext *)opaque;

    if (context->limited_id &&
        strcmp(context->limited_id, weapon_id) == 0)
        return context->limited_count;

    return 0u;
}

static int ContentAllowed(
    void *opaque,
    const char *weapon_id)
{
    TestContext *context = (TestContext *)opaque;
    (void)weapon_id;
    return context->allow_content;
}

static int SpecialAllowed(
    void *opaque,
    const char *weapon_id)
{
    TestContext *context = (TestContext *)opaque;
    (void)weapon_id;
    return context->allow_special;
}

static int NativeReady(
    void *opaque,
    const char *weapon_id)
{
    TestContext *context = (TestContext *)opaque;
    (void)weapon_id;
    return context->native_ready_all;
}

static void InitIdentityRng(TestContext *context)
{
    size_t i;

    memset(context, 0, sizeof(*context));
    for (i = 0u; i < XZ_NACHT_MYSTERY_BOX_POOL_COUNT; ++i)
        context->rng_values[i] = (uint32_t)i;

    context->allow_content = 1;
    context->allow_special = 1;
}

static XzNachtMysteryBoxSelectionContext MakeSelectionContext(
    TestContext *test)
{
    XzNachtMysteryBoxSelectionContext context;

    memset(&context, 0, sizeof(context));
    context.user_context = test;
    context.random_below = RandomSequence;
    context.owns_weapon_or_upgrade = Owns;
    context.limited_occupancy = LimitedCount;
    context.content_allowed = ContentAllowed;
    context.special_allowed = SpecialAllowed;
    context.native_ready = NativeReady;
    return context;
}

static const XzNachtMysteryBoxEntry *FindEntry(
    const char *weapon_id)
{
    size_t i;

    for (i = 0u; i < XzNachtMysteryBox_Count(); ++i) {
        const XzNachtMysteryBoxEntry *entry =
            XzNachtMysteryBox_Get(i);

        if (entry &&
            strcmp(entry->weapon_id, weapon_id) == 0)
            return entry;
    }

    return NULL;
}

int main(void)
{
    TestContext test;
    XzNachtMysteryBoxSelectionContext context;
    XzNachtMysteryBoxSelection selection;
    XzNachtMysteryBoxState state;
    const XzNachtMysteryBoxEntry *ray;
    const XzNachtMysteryBoxEntry *mk2;
    const XzNachtMysteryBoxEntry *annihilator;
    uint32_t points;
    size_t i;

    assert(XZ_NACHT_MYSTERY_BOX_COST == 950u);
    assert(XZ_NACHT_MYSTERY_BOX_MOVABLE == 0);
    assert(XzNachtMysteryBox_Count() == 34u);
    assert(XzNachtMysteryBox_SelfTest());

    annihilator = FindEntry("hero_annihilator");
    ray = FindEntry("ray_gun");
    mk2 = FindEntry("raygun_mark2");

    assert(annihilator && ray && mk2);
    assert(annihilator->source_is_limited == 1u);
    assert(annihilator->quota_defined == 0u);
    assert(mk2->source_is_limited == 1u);
    assert(mk2->quota_defined == 1u);
    assert(mk2->quota == 1u);

    /*
     * Identity random sequence means BO3's swap-every-index shuffle leaves
     * the validated pool order unchanged.
     */
    InitIdentityRng(&test);
    context = MakeSelectionContext(&test);

    assert(
        XzNachtMysteryBox_Select(
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_OK);
    assert(selection.entry != NULL);
    assert(strcmp(selection.entry->weapon_id, "ar_accurate") == 0);
    assert(selection.used_unfiltered_fallback == 0u);

    /*
     * randomint(count)==0 for every swap yields
     * [33,0,1,2,...,32], so Thundergun is examined first.
     */
    InitIdentityRng(&test);
    for (i = 0u; i < XZ_NACHT_MYSTERY_BOX_POOL_COUNT; ++i)
        test.rng_values[i] = 0u;
    test.limited_id = "thundergun";
    test.limited_count = 1u;
    context = MakeSelectionContext(&test);

    assert(
        XzNachtMysteryBox_Select(
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_OK);
    assert(strcmp(selection.entry->weapon_id, "ar_accurate") == 0);

    test.rng_index = 0u;
    test.owned[0] = "ar_accurate";
    test.owned_count = 1u;
    assert(
        XzNachtMysteryBox_Select(
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_OK);
    assert(strcmp(selection.entry->weapon_id, "ar_cqb") == 0);

    /*
     * BO3's Ray Gun / Mark II mutual-exclusion rule is independent of
     * limited quotas.
     */
    InitIdentityRng(&test);
    context = MakeSelectionContext(&test);
    test.owned[0] = "raygun_mark2_upgraded";
    test.owned_count = 1u;
    assert(!XzNachtMysteryBox_IsEligible(ray, &context));

    test.owned[0] = "ray_gun";
    assert(!XzNachtMysteryBox_IsEligible(mk2, &context));

    /*
     * If every stock receiveability check fails, BO3 returns shuffled keys[0].
     * Reference mode preserves that fallback and marks it explicitly.
     */
    InitIdentityRng(&test);
    test.allow_content = 0;
    context = MakeSelectionContext(&test);
    assert(
        XzNachtMysteryBox_Select(
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_OK);
    assert(strcmp(selection.entry->weapon_id, "ar_accurate") == 0);
    assert(selection.used_unfiltered_fallback == 1u);

    /*
     * Native-safe mode never uses the stock unfiltered fallback. Until every
     * selected weapon has a native gameplay binding, the roll is rejected.
     */
    InitIdentityRng(&test);
    context = MakeSelectionContext(&test);
    context.require_native_ready = 1;
    test.native_ready_all = 0;
    assert(
        XzNachtMysteryBox_Select(
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_NO_ELIGIBLE_NATIVE_WEAPON);

    points = 2000u;
    XzNachtMysteryBox_Reset(&state);
    test.rng_index = 0u;
    assert(
        XzNachtMysteryBox_TryRoll(
            &state,
            &points,
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_NO_ELIGIBLE_NATIVE_WEAPON);
    assert(points == 2000u);
    assert(!state.busy);

    /*
     * Once the supplied native readiness probe says all candidates are ready,
     * a normal 950-point roll is accepted and remains busy until completion.
     */
    test.native_ready_all = 1;
    test.rng_index = 0u;
    assert(
        XzNachtMysteryBox_TryRoll(
            &state,
            &points,
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_OK);
    assert(points == 1050u);
    assert(state.busy);

    assert(
        XzNachtMysteryBox_TryRoll(
            &state,
            &points,
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_BUSY);
    assert(points == 1050u);

    XzNachtMysteryBox_CompleteRoll(&state);
    assert(!state.busy);
    assert(state.completed_uses == 1u);

    points = 949u;
    test.rng_index = 0u;
    assert(
        XzNachtMysteryBox_TryRoll(
            &state,
            &points,
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_INSUFFICIENT_POINTS);
    assert(points == 949u);

    InitIdentityRng(&test);
    test.rng_values[7] = XZ_NACHT_MYSTERY_BOX_POOL_COUNT;
    context = MakeSelectionContext(&test);
    assert(
        XzNachtMysteryBox_Select(
            &context,
            &selection) ==
        XZ_NACHT_MYSTERY_BOX_RNG_OUT_OF_RANGE);

    assert(strcmp(
        XzNachtMysteryBox_ResultName(
            XZ_NACHT_MYSTERY_BOX_BUSY),
        "BUSY") == 0);

    return 0;
}
