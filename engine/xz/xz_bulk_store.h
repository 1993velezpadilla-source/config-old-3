#ifndef XZ_BULK_STORE_H
#define XZ_BULK_STORE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_BULK_STORE_INITIAL_PACKAGES 8u
#define XZ_BULK_STORE_INITIAL_ENTRIES 4096u
#define XZ_BULK_STORE_INITIAL_BUCKETS 8192u
#define XZ_BULK_STORE_PATH_MAX 192u

typedef enum XzBulkCodec {
    XZ_BULK_CODEC_RAW = 0,
    XZ_BULK_CODEC_LZ4 = 3
} XzBulkCodec;

typedef struct XzBulkPackage {
    uint32_t id;
    uint32_t entry_count;
    char path[XZ_BULK_STORE_PATH_MAX];
} XzBulkPackage;

typedef struct XzBulkEntry {
    uint64_t key;
    uint64_t offset;
    uint64_t compressed_bytes;
    uint64_t uncompressed_bytes;
    uint32_t package_id;
    uint32_t next_hash;
    uint8_t codec;
    uint8_t resident;
} XzBulkEntry;

typedef struct XzBulkStore {
    XzBulkPackage *packages;
    XzBulkEntry *entries;
    uint32_t *buckets;
    uint32_t package_count;
    uint32_t package_capacity;
    uint32_t entry_count;
    uint32_t entry_capacity;
    uint32_t bucket_count;
    uint64_t indexed_compressed_bytes;
    uint64_t indexed_uncompressed_bytes;
    int ready;
} XzBulkStore;

void XzBulkStore_Init(XzBulkStore *store);

void XzBulkStore_Destroy(XzBulkStore *store);

int XzBulkStore_AddPackage(
    XzBulkStore *store,
    const char *path,
    uint32_t *out_package_id);

int XzBulkStore_AddEntry(
    XzBulkStore *store,
    uint32_t package_id,
    uint64_t key,
    uint64_t offset,
    uint64_t compressed_bytes,
    uint64_t uncompressed_bytes,
    XzBulkCodec codec);

int XzBulkStore_Find(
    const XzBulkStore *store,
    uint64_t key,
    uint32_t *out_entry_index);

int XzBulkStore_IsReady(
    const XzBulkStore *store);

int XzBulkStore_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
