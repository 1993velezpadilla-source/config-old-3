#ifndef XZ_GAME_SYSTEM_REGISTRY_H
#define XZ_GAME_SYSTEM_REGISTRY_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_GAME_SYSTEM_NAME_MAX 64u
#define XZ_GAME_SYSTEM_INITIAL_SYSTEMS 32u
#define XZ_GAME_SYSTEM_INITIAL_DEPENDENCIES 64u

typedef struct XzGameSystemRecord {
    char name[XZ_GAME_SYSTEM_NAME_MAX];
    uint8_t pre_done;
    uint8_t post_done;
    uint8_t ignored;
    uint8_t failed;
} XzGameSystemRecord;

typedef struct XzGameSystemDependency {
    uint32_t system_index;
    uint32_t required_index;
} XzGameSystemDependency;

typedef struct XzGameSystemRegistry {
    XzGameSystemRecord *systems;
    XzGameSystemDependency *dependencies;
    uint32_t system_count;
    uint32_t system_capacity;
    uint32_t dependency_count;
    uint32_t dependency_capacity;
    uint32_t active_count;
    uint32_t pre_done_count;
    uint32_t post_done_count;
    uint32_t ignored_count;
    uint32_t failed_count;
    uint32_t unresolved_dependency_count;
    int finalized;
    int ready;
} XzGameSystemRegistry;

void XzGameSystemRegistry_Init(
    XzGameSystemRegistry *registry);

void XzGameSystemRegistry_Destroy(
    XzGameSystemRegistry *registry);

int XzGameSystemRegistry_Register(
    XzGameSystemRegistry *registry,
    const char *name,
    uint32_t *out_index);

int XzGameSystemRegistry_Find(
    const XzGameSystemRegistry *registry,
    const char *name,
    uint32_t *out_index);

int XzGameSystemRegistry_AddDependency(
    XzGameSystemRegistry *registry,
    uint32_t system_index,
    uint32_t required_index);

int XzGameSystemRegistry_SetIgnored(
    XzGameSystemRegistry *registry,
    uint32_t system_index,
    int ignored);

int XzGameSystemRegistry_MarkPreDone(
    XzGameSystemRegistry *registry,
    uint32_t system_index);

int XzGameSystemRegistry_MarkPostDone(
    XzGameSystemRegistry *registry,
    uint32_t system_index);

int XzGameSystemRegistry_MarkFailed(
    XzGameSystemRegistry *registry,
    uint32_t system_index);

int XzGameSystemRegistry_Finalize(
    XzGameSystemRegistry *registry);

int XzGameSystemRegistry_IsReady(
    const XzGameSystemRegistry *registry);

int XzGameSystemRegistry_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
