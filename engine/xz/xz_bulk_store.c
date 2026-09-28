#include "xz_bulk_store.h"

#include <stdio.h>
#include <string.h>

void XzBulkStore_Init(XzBulkStore *store)
{
    if (!store)
        return;

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
        strlen(path) >= XZ_BULK_STORE_PATH_MAX ||
        store->package_count >= XZ_BULK_STORE_MAX_PACKAGES)
        return 0;

    for (i = 0u; i < store->package_count; ++i) {
        if (strcmp(store->packages[i].path, path) == 0)
            return 0;
    }

    pkg = &store->packages[store->package_count];
    memset(pkg, 0, sizeof(*pkg));
    pkg->id = store->package_count + 1u;
    snprintf(pkg->path, sizeof(pkg->path), "%s", path);

    store->package_count++;
    store->ready = 1;

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
    uint32_t i;

    if (!store ||
        package_id == 0u ||
        package_id > store->package_count ||
        key == 0u ||
        compressed_bytes == 0u ||
        uncompressed_bytes == 0u ||
        store->entry_count >= XZ_BULK_STORE_MAX_ENTRIES)
        return 0;

    if (codec != XZ_BULK_CODEC_RAW &&
        codec != XZ_BULK_CODEC_LZ4)
        return 0;

    for (i = 0u; i < store->entry_count; ++i) {
        if (store->entries[i].key == key)
            return 0;
    }

    entry = &store->entries[store->entry_count];
    memset(entry, 0, sizeof(*entry));
    entry->key = key;
    entry->offset = offset;
    entry->compressed_bytes = compressed_bytes;
    entry->uncompressed_bytes = uncompressed_bytes;
    entry->package_id = package_id;
    entry->codec = (uint8_t)codec;

    store->packages[package_id - 1u].entry_count++;
    store->entry_count++;
    store->indexed_compressed_bytes += compressed_bytes;
    store->indexed_uncompressed_bytes += uncompressed_bytes;
    store->ready = store->package_count > 0u &&
                   store->entry_count > 0u;

    return 1;
}

int XzBulkStore_Find(
    const XzBulkStore *store,
    uint64_t key,
    uint32_t *out_entry_index)
{
    uint32_t i;

    if (!store || key == 0u)
        return 0;

    for (i = 0u; i < store->entry_count; ++i) {
        if (store->entries[i].key == key) {
            if (out_entry_index)
                *out_entry_index = i + 1u;
            return 1;
        }
    }

    return 0;
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

    XzBulkStore_Init(&store);

    if (!XzBulkStore_AddPackage(
            &store,
            "zone/test.xpak",
            &package_id))
        return 0;

    if (!XzBulkStore_AddEntry(
            &store,
            package_id,
            0x1122334455667788ull,
            4096u,
            1024u,
            4096u,
            XZ_BULK_CODEC_LZ4))
        return 0;

    if (!XzBulkStore_Find(
            &store,
            0x1122334455667788ull,
            &entry_index))
        return 0;

    return XzBulkStore_IsReady(&store) &&
           entry_index == 1u &&
           store.indexed_compressed_bytes == 1024u &&
           store.indexed_uncompressed_bytes == 4096u;
}
