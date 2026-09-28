#ifndef XZ_ZONE_DB_H
#define XZ_ZONE_DB_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_ZONE_DB_MAX_ZONES 64u
#define XZ_ZONE_DB_MAX_ASSETS 8192u
#define XZ_ZONE_DB_MAX_DEPENDENCIES 256u
#define XZ_ZONE_DB_NAME_MAX 96u

typedef enum XzZoneState {
    XZ_ZONE_UNLOADING = -1,
    XZ_ZONE_EMPTY = 0,
    XZ_ZONE_LOADING = 1,
    XZ_ZONE_LOADED = 2,
    XZ_ZONE_COMPLETE = 3,
    XZ_ZONE_FAILED = 4
} XzZoneState;

typedef enum XzZoneMemoryClass {
    XZ_ZONE_MEM_TEMP = 0,
    XZ_ZONE_MEM_RUNTIME_VIRTUAL,
    XZ_ZONE_MEM_RUNTIME_PHYSICAL,
    XZ_ZONE_MEM_DELAY_VIRTUAL,
    XZ_ZONE_MEM_DELAY_PHYSICAL,
    XZ_ZONE_MEM_VIRTUAL,
    XZ_ZONE_MEM_PHYSICAL,
    XZ_ZONE_MEM_STREAMER_RESERVE,
    XZ_ZONE_MEM_STREAMER,
    XZ_ZONE_MEM_MEMMAPPED,
    XZ_ZONE_MEM_COUNT
} XzZoneMemoryClass;

typedef struct XzZoneRecord {
    uint16_t id;
    uint32_t flags;
    int32_t slot;
    XzZoneState state;
    uint8_t stream_preloaded;
    uint64_t bytes[XZ_ZONE_MEM_COUNT];
    char name[XZ_ZONE_DB_NAME_MAX];
} XzZoneRecord;

typedef struct XzAssetRecord {
    uint32_t type;
    uint32_t name_hash;
    uint16_t zone_id;
    uint16_t override_of;
    uint8_t in_use;
    uint8_t resident;
} XzAssetRecord;

typedef struct XzZoneDependency {
    uint16_t zone_id;
    uint16_t depends_on_zone_id;
} XzZoneDependency;

typedef struct XzZoneDb {
    XzZoneRecord zones[XZ_ZONE_DB_MAX_ZONES];
    XzAssetRecord assets[XZ_ZONE_DB_MAX_ASSETS];
    XzZoneDependency dependencies[XZ_ZONE_DB_MAX_DEPENDENCIES];
    uint32_t zone_count;
    uint32_t asset_count;
    uint32_t dependency_count;
    uint32_t complete_zones;
    uint32_t failed_zones;
    int database_ready;
} XzZoneDb;

void XzZoneDb_Init(XzZoneDb *db);

int XzZoneDb_BeginZone(
    XzZoneDb *db,
    const char *name,
    uint32_t flags,
    int32_t slot,
    uint16_t *out_zone_id);

int XzZoneDb_SetZoneState(
    XzZoneDb *db,
    uint16_t zone_id,
    XzZoneState state);

int XzZoneDb_AddDependency(
    XzZoneDb *db,
    uint16_t zone_id,
    uint16_t depends_on_zone_id);

int XzZoneDb_SetZoneMemoryBytes(
    XzZoneDb *db,
    uint16_t zone_id,
    XzZoneMemoryClass memory_class,
    uint64_t bytes);

int XzZoneDb_AddAsset(
    XzZoneDb *db,
    uint16_t zone_id,
    uint32_t type,
    uint32_t name_hash,
    uint16_t override_of,
    uint32_t *out_asset_index);

int XzZoneDb_FindAsset(
    const XzZoneDb *db,
    uint32_t type,
    uint32_t name_hash,
    int include_override,
    uint32_t *out_asset_index);

int XzZoneDb_UnloadZone(
    XzZoneDb *db,
    uint16_t zone_id);

int XzZoneDb_IsReady(
    const XzZoneDb *db);

int XzZoneDb_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
