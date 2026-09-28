#include "xz_bulk_store.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t XzBulkStore_Hash(uint64_t key)
{
    uint64_t x = key;

    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdull;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ull;
    x ^= x >> 33;

    return (uint32_t)(x ^ (x >> 32));
}

static int XzBulkStore_ReservePackages(
    XzBulkStore *store,
    uint32_t needed)
{
    uint32_t capacity;
    XzBulkPackage *grown;

    if (!store)
        return 0;

    if (needed <= store->package_capacity)
        return 1;

    capacity =
        store->package_capacity > 0u
            ? store->package_capacity
            : XZ_BULK_STORE_INITIAL_PACKAGES;

    while (capacity < needed) {
        if (capacity > UINT32_MAX / 2u) {
            capacity = needed;
            break;
        }
        capacity *= 2u;
    }

    {
        size_t bytes =
            (size_t)capacity *
            sizeof(*store->packages);

        if (capacity != 0u &&
            bytes / sizeof(*store->packages) !=
                (size_t)capacity)
            return 0;

        grown =
            (XzBulkPackage *)realloc(
                store->packages,
                bytes);
    }

    if (!grown)
        return 0;

    memset(
        grown + store->package_capacity,
        0,
        (size_t)(capacity -
                 store->package_capacity) *
            sizeof(*store->packages));

    store->packages = grown;
    store->package_capacity = capacity;
    return 1;
}

static int XzBulkStore_ReserveEntries(
    XzBulkStore *store,
    uint32_t needed)
{
    uint32_t capacity;
    XzBulkEntry *grown;

    if (!store)
        return 0;

    if (needed <= store->entry_capacity)
        return 1;

    capacity =
        store->entry_capacity > 0u
            ? store->entry_capacity
            : XZ_BULK_STORE_INITIAL_ENTRIES;

    while (capacity < needed) {
        if (capacity > UINT32_MAX / 2u) {
            capacity = needed;
            break;
        }
        capacity *= 2u;
    }

    {
        size_t bytes =
            (size_t)capacity *
            sizeof(*store->entries);

        if (capacity != 0u &&
            bytes / sizeof(*store->entries) !=
                (size_t)capacity)
            return 0;

        grown =
            (XzBulkEntry *)realloc(
                store->entries,
                bytes);
    }

    if (!grown)
        return 0;

    memset(
        grown + store->entry_capacity,
        0,
        (size_t)(capacity -
                 store->entry_capacity) *
            sizeof(*store->entries));

    store->entries = grown;
    store->entry_capacity = capacity;
    return 1;
}

static int XzBulkStore_Rehash(
    XzBulkStore *store,
    uint32_t requested_bucket_count)
{
    uint32_t bucket_count =
        XZ_BULK_STORE_INITIAL_BUCKETS;
    uint32_t *buckets;
    uint32_t i;

    if (!store)
        return 0;

    while (bucket_count < requested_bucket_count) {
        if (bucket_count > UINT32_MAX / 2u) {
            bucket_count = requested_bucket_count;
            break;
        }
        bucket_count *= 2u;
    }

    if (bucket_count == 0u)
        return 0;

    buckets =
        (uint32_t *)calloc(
            bucket_count,
            sizeof(*buckets));

    if (!buckets)
        return 0;

    for (i = 0u; i < store->entry_count; ++i) {
        uint32_t bucket =
            XzBulkStore_Hash(
                store->entries[i].key) %
            bucket_count;

        store->entries[i].next_hash =
            buckets[bucket];
        buckets[bucket] = i + 1u;
    }

    free(store->buckets);
    store->buckets = buckets;
    store->bucket_count = bucket_count;
    return 1;
}

static int XzBulkStore_EnsureHashCapacity(
    XzBulkStore *store,
    uint32_t entry_count)
{
    uint64_t requested;

    if (!store)
        return 0;

    requested = (uint64_t)entry_count * 2ull;
    if (requested <
        XZ_BULK_STORE_INITIAL_BUCKETS) {
        requested =
            XZ_BULK_STORE_INITIAL_BUCKETS;
    }

    if (requested > UINT32_MAX)
        return 0;

    if (store->bucket_count >=
        (uint32_t)requested)
        return 1;

    return XzBulkStore_Rehash(
        store,
        (uint32_t)requested);
}

static int XzBulkStore_FindIndex(
    const XzBulkStore *store,
    uint64_t key,
    uint32_t *out_entry_index)
{
    uint32_t bucket;
    uint32_t link;

    if (!store ||
        !store->buckets ||
        store->bucket_count == 0u ||
        key == 0u)
        return 0;

    bucket =
        XzBulkStore_Hash(key) %
        store->bucket_count;

    link = store->buckets[bucket];
    while (link != 0u) {
        uint32_t index = link - 1u;
        const XzBulkEntry *entry;

        if (index >= store->entry_count)
            return 0;

        entry = &store->entries[index];
        if (entry->key == key) {
            if (out_entry_index)
                *out_entry_index = index + 1u;
            return 1;
        }

        link = entry->next_hash;
    }

    return 0;
}

void XzBulkStore_Init(XzBulkStore *store)
{
    if (!store)
        return;

    memset(store, 0, sizeof(*store));
}

void XzBulkStore_Destroy(XzBulkStore *store)
{
    if (!store)
        return;

    free(store->packages);
    free(store->entries);
    free(store->buckets);
    memset(store, 0, sizeof(*store));
}

int XzBulkStore_AddPackage(
    XzBulkStore *store,
    const char *path,
    uint32_t *out_package_id)
{
    XzBulkPackage *pkg;
    uint32_t i;

    if (!store || !path || !path[0] ||
        strlen(path) >= XZ_BULK_STORE_PATH_MAX)
        return 0;

    for (i = 0u; i < store->package_count; ++i) {
        if (strcmp(store->packages[i].path, path) == 0)
            return 0;
    }

    if (!XzBulkStore_ReservePackages(
            store,
            store->package_count + 1u))
        return 0;

    pkg = &store->packages[store->package_count];
    memset(pkg, 0, sizeof(*pkg));
    pkg->id = store->package_count + 1u;
    snprintf(pkg->path, sizeof(pkg->path), "%s", path);

    store->package_count++;
    store->ready =
        store->package_count > 0u &&
        store->entry_count > 0u;

    if (out_package_id)
        *out_package_id = pkg->id;

    return 1;
}

int XzBulkStore_AddEntry(
    XzBulkStore *store,
    uint32_t package_id,
    uint64_t key,
    uint64_t offset,
    uint64_t compressed_bytes,
    uint64_t uncompressed_bytes,
    XzBulkCodec codec)
{
    XzBulkEntry *entry;
    uint32_t bucket;

    if (!store ||
        package_id == 0u ||
        package_id > store->package_count ||
        key == 0u ||
        compressed_bytes == 0u ||
        uncompressed_bytes == 0u)
        return 0;

    if (codec != XZ_BULK_CODEC_RAW &&
        codec != XZ_BULK_CODEC_LZ4)
        return 0;

    if (XzBulkStore_FindIndex(
            store,
            key,
            NULL))
        return 0;

    if (UINT64_MAX -
            store->indexed_compressed_bytes <
        compressed_bytes)
        return 0;

    if (UINT64_MAX -
            store->indexed_uncompressed_bytes <
        uncompressed_bytes)
        return 0;

    if (!XzBulkStore_ReserveEntries(
            store,
            store->entry_count + 1u))
        return 0;

    if (!XzBulkStore_EnsureHashCapacity(
            store,
            store->entry_count + 1u))
        return 0;

    entry = &store->entries[store->entry_count];
    memset(entry, 0, sizeof(*entry));
    entry->key = key;
    entry->offset = offset;
    entry->compressed_bytes = compressed_bytes;
    entry->uncompressed_bytes = uncompressed_bytes;
    entry->package_id = package_id;
    entry->codec = (uint8_t)codec;

    bucket =
        XzBulkStore_Hash(key) %
        store->bucket_count;

    entry->next_hash = store->buckets[bucket];
    store->buckets[bucket] =
        store->entry_count + 1u;

    store->packages[package_id - 1u].entry_count++;
    store->entry_count++;
    store->indexed_compressed_bytes +=
        compressed_bytes;
    store->indexed_uncompressed_bytes +=
        uncompressed_bytes;
    store->ready =
        store->package_count > 0u &&
        store->entry_count > 0u;

    return 1;
}

int XzBulkStore_Find(
    const XzBulkStore *store,
    uint64_t key,
    uint32_t *out_entry_index)
{
    return XzBulkStore_FindIndex(
        store,
        key,
        out_entry_index);
}

int XzBulkStore_IsReady(
    const XzBulkStore *store)
{
    return store ? store->ready : 0;
}

int XzBulkStore_SelfTest(void)
{
    XzBulkStore store;
    uint32_t package_id = 0u;
    uint32_t entry_index = 0u;
    uint32_t i;
    char path[64];
    int ok = 0;

    XzBulkStore_Init(&store);

    for (i = 0u; i < 100u; ++i) {
        snprintf(
            path,
            sizeof(path),
            "zone/test-%u.xpak",
            i);

        if (!XzBulkStore_AddPackage(
                &store,
                path,
                &package_id))
            goto cleanup;
    }

    if (store.package_count != 100u ||
        store.package_capacity <
            store.package_count)
        goto cleanup;

    package_id = 1u;

    for (i = 0u; i < 40000u; ++i) {
        if (!XzBulkStore_AddEntry(
                &store,
                package_id,
                0x100000000ull +
                    (uint64_t)i + 1ull,
                (uint64_t)i * 4096ull,
                1024u,
                4096u,
                XZ_BULK_CODEC_LZ4))
            goto cleanup;
    }

    if (store.entry_count != 40000u ||
        store.entry_capacity <
            store.entry_count ||
        store.bucket_count <
            XZ_BULK_STORE_INITIAL_BUCKETS)
        goto cleanup;

    if (!XzBulkStore_Find(
            &store,
            0x100000000ull + 39999ull + 1ull,
            &entry_index))
        goto cleanup;

    if (!XzBulkStore_IsReady(&store) ||
        entry_index != 40000u ||
        store.indexed_compressed_bytes !=
            40000ull * 1024ull ||
        store.indexed_uncompressed_bytes !=
            40000ull * 4096ull)
        goto cleanup;

    ok = 1;

cleanup:
    XzBulkStore_Destroy(&store);
    return ok;
}
