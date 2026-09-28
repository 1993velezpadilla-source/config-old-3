#include "xz_zone_db.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int XzZoneDb_Reserve(
    void **storage,
    uint32_t *capacity,
    uint32_t needed,
    uint32_t initial_capacity,
    size_t element_size)
{
    uint32_t new_capacity;
    void *grown;

    if (!storage || !capacity || element_size == 0u)
        return 0;

    if (needed <= *capacity)
        return 1;

    new_capacity =
        *capacity > 0u
            ? *capacity
            : initial_capacity;

    if (new_capacity == 0u)
        new_capacity = 1u;

    while (new_capacity < needed) {
        if (new_capacity > UINT32_MAX / 2u) {
            new_capacity = needed;
            break;
        }
        new_capacity *= 2u;
    }

    if ((size_t)new_capacity > SIZE_MAX / element_size)
        return 0;

    grown =
        realloc(
            *storage,
            (size_t)new_capacity * element_size);

    if (!grown)
        return 0;

    if (new_capacity > *capacity) {
        memset(
            (unsigned char *)grown +
                (size_t)(*capacity) * element_size,
            0,
            (size_t)(new_capacity - *capacity) *
                element_size);
    }

    *storage = grown;
    *capacity = new_capacity;
    return 1;
}

static int XzZoneDb_ReserveZones(
    XzZoneDb *db,
    uint32_t needed)
{
    if (!db || needed > UINT16_MAX)
        return 0;

    return XzZoneDb_Reserve(
        (void **)&db->zones,
        &db->zone_capacity,
        needed,
        XZ_ZONE_DB_INITIAL_ZONES,
        sizeof(*db->zones));
}

static int XzZoneDb_ReserveAssets(
    XzZoneDb *db,
    uint32_t needed)
{
    if (!db)
        return 0;

    return XzZoneDb_Reserve(
        (void **)&db->assets,
        &db->asset_capacity,
        needed,
        XZ_ZONE_DB_INITIAL_ASSETS,
        sizeof(*db->assets));
}

static int XzZoneDb_ReserveDependencies(
    XzZoneDb *db,
    uint32_t needed)
{
    if (!db)
        return 0;

    return XzZoneDb_Reserve(
        (void **)&db->dependencies,
        &db->dependency_capacity,
        needed,
        XZ_ZONE_DB_INITIAL_DEPENDENCIES,
        sizeof(*db->dependencies));
}

static int XzZoneDb_ValidZoneId(
    const XzZoneDb *db,
    uint16_t zone_id)
{
    return db &&
           db->zones &&
           zone_id > 0u &&
           zone_id <= db->zone_count &&
           db->zones[zone_id - 1u].state != XZ_ZONE_EMPTY;
}

static void XzZoneDb_RecomputeReady(XzZoneDb *db)
{
    uint32_t i;
    uint32_t active = 0u;
    uint32_t complete = 0u;
    uint32_t failed = 0u;

    if (!db)
        return;

    for (i = 0u; i < db->zone_count; ++i) {
        const XzZoneRecord *zone = &db->zones[i];

        if (zone->state == XZ_ZONE_EMPTY)
            continue;

        active++;
        if (zone->state == XZ_ZONE_COMPLETE)
            complete++;
        else if (zone->state == XZ_ZONE_FAILED)
            failed++;
    }

    if (failed == 0u && complete == active) {
        for (i = 0u; i < db->dependency_count; ++i) {
            const XzZoneDependency *dep = &db->dependencies[i];
            if (!XzZoneDb_ValidZoneId(db, dep->zone_id) ||
                !XzZoneDb_ValidZoneId(db, dep->depends_on_zone_id) ||
                db->zones[dep->depends_on_zone_id - 1u].state !=
                    XZ_ZONE_COMPLETE) {
                failed++;
                break;
            }
        }
    }

    db->complete_zones = complete;
    db->failed_zones = failed;
    db->database_ready =
        active > 0u &&
        failed == 0u &&
        complete == active;
}

void XzZoneDb_Init(XzZoneDb *db)
{
    if (!db)
        return;

    memset(db, 0, sizeof(*db));
    db->transition_allowed = 1;
}

void XzZoneDb_Destroy(XzZoneDb *db)
{
    if (!db)
        return;

    free(db->zones);
    free(db->assets);
    free(db->dependencies);
    memset(db, 0, sizeof(*db));
}

void XzZoneDb_SetDatabaseReady(
    XzZoneDb *db,
    int ready)
{
    if (!db)
        return;

    db->transition_allowed = ready ? 1 : 0;
    XzZoneDb_RecomputeReady(db);
}

int XzZoneDb_BeginZone(
    XzZoneDb *db,
    const char *name,
    uint32_t flags,
    int32_t slot,
    uint16_t *out_zone_id)
{
    XzZoneRecord *zone;
    uint32_t index;
    uint32_t target = UINT32_MAX;

    if (!db || !name || !name[0] ||
        !db->transition_allowed)
        return 0;

    for (index = 0u; index < db->zone_count; ++index) {
        if (db->zones[index].state != XZ_ZONE_EMPTY &&
            strcmp(db->zones[index].name, name) == 0)
            return 0;

        if (target == UINT32_MAX &&
            db->zones[index].state == XZ_ZONE_EMPTY)
            target = index;
    }

    if (target == UINT32_MAX) {
        if (db->zone_count >= UINT16_MAX)
            return 0;

        if (!XzZoneDb_ReserveZones(
                db,
                db->zone_count + 1u))
            return 0;

        target = db->zone_count;
        db->zone_count++;
    }

    zone = &db->zones[target];
    memset(zone, 0, sizeof(*zone));
    zone->id = (uint16_t)(target + 1u);
    zone->flags = flags;
    zone->slot = slot;
    zone->state = XZ_ZONE_LOADING;
    snprintf(zone->name, sizeof(zone->name), "%s", name);

    if (out_zone_id)
        *out_zone_id = zone->id;

    XzZoneDb_RecomputeReady(db);
    return 1;
}

int XzZoneDb_FinishZoneLoad(
    XzZoneDb *db,
    uint16_t zone_id)
{
    if (!XzZoneDb_ValidZoneId(db, zone_id))
        return 0;

    if (db->zones[zone_id - 1u].state != XZ_ZONE_LOADED)
        return 0;

    db->zones[zone_id - 1u].state = XZ_ZONE_COMPLETE;
    XzZoneDb_RecomputeReady(db);
    return 1;
}

int XzZoneDb_SetZoneState(
    XzZoneDb *db,
    uint16_t zone_id,
    XzZoneState state)
{
    XzZoneRecord *zone;

    if (!XzZoneDb_ValidZoneId(db, zone_id))
        return 0;

    zone = &db->zones[zone_id - 1u];

    if (state == XZ_ZONE_LOADING) {
        if (zone->state != XZ_ZONE_EMPTY &&
            zone->state != XZ_ZONE_FAILED)
            return 0;
    } else if (state == XZ_ZONE_LOADED) {
        if (zone->state != XZ_ZONE_LOADING)
            return 0;
    } else if (state == XZ_ZONE_COMPLETE) {
        if (zone->state != XZ_ZONE_LOADED)
            return 0;
    } else if (state == XZ_ZONE_UNLOADING) {
        if (zone->state != XZ_ZONE_LOADING &&
            zone->state != XZ_ZONE_LOADED &&
            zone->state != XZ_ZONE_COMPLETE &&
            zone->state != XZ_ZONE_FAILED)
            return 0;
    } else if (state == XZ_ZONE_FAILED) {
        if (zone->state != XZ_ZONE_LOADING &&
            zone->state != XZ_ZONE_LOADED)
            return 0;
    } else if (state == XZ_ZONE_EMPTY) {
        if (zone->state != XZ_ZONE_UNLOADING)
            return 0;
    } else {
        return 0;
    }

    zone->state = state;
    XzZoneDb_RecomputeReady(db);
    return 1;
}

int XzZoneDb_AddDependency(
    XzZoneDb *db,
    uint16_t zone_id,
    uint16_t depends_on_zone_id)
{
    uint32_t i;

    if (!XzZoneDb_ValidZoneId(db, zone_id) ||
        !XzZoneDb_ValidZoneId(db, depends_on_zone_id) ||
        zone_id == depends_on_zone_id)
        return 0;

    for (i = 0u; i < db->dependency_count; ++i) {
        if (db->dependencies[i].zone_id == zone_id &&
            db->dependencies[i].depends_on_zone_id == depends_on_zone_id)
            return 0;
    }

    if (!XzZoneDb_ReserveDependencies(
            db,
            db->dependency_count + 1u))
        return 0;

    db->dependencies[db->dependency_count].zone_id = zone_id;
    db->dependencies[db->dependency_count].depends_on_zone_id =
        depends_on_zone_id;
    db->dependency_count++;
    XzZoneDb_RecomputeReady(db);
    return 1;
}

int XzZoneDb_SetZoneMemoryBytes(
    XzZoneDb *db,
    uint16_t zone_id,
    XzZoneMemoryClass memory_class,
    uint64_t bytes)
{
    if (!XzZoneDb_ValidZoneId(db, zone_id) ||
        (unsigned int)memory_class >= XZ_ZONE_MEM_COUNT)
        return 0;

    db->zones[zone_id - 1u].bytes[memory_class] = bytes;
    return 1;
}

int XzZoneDb_AddAsset(
    XzZoneDb *db,
    uint16_t zone_id,
    uint32_t type,
    uint32_t name_hash,
    uint32_t override_of,
    uint32_t *out_asset_index)
{
    XzAssetRecord *asset;
    uint32_t i;

    if (!XzZoneDb_ValidZoneId(db, zone_id) ||
        name_hash == 0u)
        return 0;

    if (override_of != 0u &&
        override_of > db->asset_count)
        return 0;

    for (i = 0u; i < db->asset_count; ++i) {
        const XzAssetRecord *existing = &db->assets[i];
        if (existing->in_use &&
            existing->zone_id == zone_id &&
            existing->type == type &&
            existing->name_hash == name_hash)
            return 0;
    }

    if (!XzZoneDb_ReserveAssets(
            db,
            db->asset_count + 1u))
        return 0;

    asset = &db->assets[db->asset_count];
    memset(asset, 0, sizeof(*asset));
    asset->type = type;
    asset->name_hash = name_hash;
    asset->zone_id = zone_id;
    asset->override_of = override_of;
    asset->in_use = 1u;
    asset->resident = 1u;

    if (out_asset_index)
        *out_asset_index = db->asset_count + 1u;

    db->asset_count++;
    return 1;
}

int XzZoneDb_FindAsset(
    const XzZoneDb *db,
    uint32_t type,
    uint32_t name_hash,
    int include_override,
    uint32_t *out_asset_index)
{
    uint32_t i;

    if (!db || name_hash == 0u)
        return 0;

    if (include_override) {
        for (i = db->asset_count; i > 0u; --i) {
            const XzAssetRecord *asset = &db->assets[i - 1u];
            if (!asset->in_use)
                continue;
            if (asset->type == type &&
                asset->name_hash == name_hash) {
                if (out_asset_index)
                    *out_asset_index = i;
                return 1;
            }
        }
    } else {
        for (i = 0u; i < db->asset_count; ++i) {
            const XzAssetRecord *asset = &db->assets[i];
            if (!asset->in_use || asset->override_of != 0u)
                continue;
            if (asset->type == type &&
                asset->name_hash == name_hash) {
                if (out_asset_index)
                    *out_asset_index = i + 1u;
                return 1;
            }
        }
    }

    return 0;
}

int XzZoneDb_UnloadZone(
    XzZoneDb *db,
    uint16_t zone_id)
{
    uint32_t i;
    uint32_t write_index = 0u;

    if (!XzZoneDb_ValidZoneId(db, zone_id))
        return 0;

    if (!XzZoneDb_SetZoneState(
            db,
            zone_id,
            XZ_ZONE_UNLOADING))
        return 0;

    for (i = 0u; i < db->asset_count; ++i) {
        if (db->assets[i].zone_id == zone_id) {
            db->assets[i].in_use = 0u;
            db->assets[i].resident = 0u;
        }
    }

    for (i = 0u; i < db->dependency_count; ++i) {
        const XzZoneDependency dep = db->dependencies[i];

        if (dep.depends_on_zone_id == zone_id &&
            XzZoneDb_ValidZoneId(db, dep.zone_id)) {
            db->zones[dep.zone_id - 1u].state =
                XZ_ZONE_FAILED;
        }

        if (dep.zone_id == zone_id ||
            dep.depends_on_zone_id == zone_id) {
            continue;
        }

        if (write_index != i)
            db->dependencies[write_index] = dep;
        write_index++;
    }

    db->dependency_count = write_index;

    memset(
        db->zones[zone_id - 1u].bytes,
        0,
        sizeof(db->zones[zone_id - 1u].bytes));

    db->zones[zone_id - 1u].stream_preloaded = 0u;
    db->zones[zone_id - 1u].state = XZ_ZONE_EMPTY;
    db->zones[zone_id - 1u].name[0] = '\0';

    XzZoneDb_RecomputeReady(db);
    return 1;
}

int XzZoneDb_IsReady(
    const XzZoneDb *db)
{
    return db ? db->database_ready : 0;
}

int XzZoneDb_SelfTest(void)
{
    XzZoneDb db;
    uint16_t zone_a = 0u;
    uint16_t zone_b = 0u;
    uint16_t zone_reused = 0u;
    uint32_t base_asset = 0u;
    uint32_t override_asset = 0u;
    uint32_t found = 0u;
    uint32_t i;
    int ok = 0;

    XzZoneDb_Init(&db);
    XzZoneDb_SetDatabaseReady(&db, 1);

    if (!XzZoneDb_BeginZone(
            &db, "zm_common", XZ_ZONE_FLAG_DYNAMIC_CUSTOM, 0, &zone_a))
        goto cleanup;

    if (!XzZoneDb_BeginZone(
            &db, "zm_test", 2u, 1, &zone_b))
        goto cleanup;

    if (!XzZoneDb_AddDependency(&db, zone_b, zone_a))
        goto cleanup;

    if (!XzZoneDb_AddAsset(
            &db, zone_a, 9u, 0x11111111u, 0u, &base_asset))
        goto cleanup;

    if (!XzZoneDb_AddAsset(
            &db,
            zone_b,
            9u,
            0x11111111u,
            base_asset,
            &override_asset))
        goto cleanup;

    if (!XzZoneDb_FindAsset(
            &db, 9u, 0x11111111u, 1, &found) ||
        found != override_asset)
        goto cleanup;

    /*
     * Exercise growth past the old 8192-asset ceiling. This is the important
     * regression for large virgin maps such as Kino.
     */
    for (i = 0u; i < 9000u; ++i) {
        if (!XzZoneDb_AddAsset(
                &db,
                zone_a,
                9u,
                0x20000000u + i,
                0u,
                NULL))
            goto cleanup;
    }

    if (db.asset_count < 9002u ||
        db.asset_capacity < db.asset_count)
        goto cleanup;

    if (!XzZoneDb_SetZoneState(
            &db, zone_a, XZ_ZONE_LOADED) ||
        !XzZoneDb_SetZoneState(
            &db, zone_b, XZ_ZONE_LOADED))
        goto cleanup;

    if (XzZoneDb_IsReady(&db))
        goto cleanup;

    if (!XzZoneDb_FinishZoneLoad(&db, zone_a) ||
        !XzZoneDb_FinishZoneLoad(&db, zone_b))
        goto cleanup;

    if (!XzZoneDb_IsReady(&db))
        goto cleanup;

    if (!XzZoneDb_UnloadZone(&db, zone_b))
        goto cleanup;

    if (!XzZoneDb_FindAsset(
            &db, 9u, 0x11111111u, 1, &found) ||
        found != base_asset)
        goto cleanup;

    if (!XzZoneDb_BeginZone(
            &db, "zm_reused", 4u, 2, &zone_reused))
        goto cleanup;

    if (zone_reused != zone_b)
        goto cleanup;

    ok = 1;

cleanup:
    XzZoneDb_Destroy(&db);
    return ok;
}
