#include "com_files.h"

#include <cstddef>

// The original source has 32-bit layout comments from the Win32 build.
// Assert native layouts explicitly before any source slice is compiled on
// Android ARM64; allocations must use sizeof/alignof, not the old constants.
static_assert(sizeof(fileInIwd_s) == (sizeof(void *) == 8 ? 24u : 12u),
              "Unexpected KisakCOD fileInIwd_s layout");
static_assert(offsetof(fileInIwd_s, name) == (sizeof(void *) == 8 ? 8u : 4u),
              "Unexpected KisakCOD fileInIwd_s::name offset");
static_assert(offsetof(fileInIwd_s, next) == (sizeof(void *) == 8 ? 16u : 8u),
              "Unexpected KisakCOD fileInIwd_s::next offset");

static_assert(sizeof(iwd_t) == (sizeof(void *) == 8 ? 816u : 804u),
              "Unexpected KisakCOD iwd_t layout");
static_assert(offsetof(iwd_t, hashTable) == (sizeof(void *) == 8 ? 800u : 796u),
              "Unexpected KisakCOD iwd_t::hashTable offset");
static_assert(offsetof(iwd_t, buildBuffer) == (sizeof(void *) == 8 ? 808u : 800u),
              "Unexpected KisakCOD iwd_t::buildBuffer offset");

static_assert(sizeof(searchpath_s) == (sizeof(void *) == 8 ? 40u : 28u),
              "Unexpected KisakCOD searchpath_s layout");
static_assert(offsetof(searchpath_s, dir) == (sizeof(void *) == 8 ? 16u : 8u),
              "Unexpected KisakCOD searchpath_s::dir offset");
static_assert(offsetof(searchpath_s, language) == (sizeof(void *) == 8 ? 36u : 24u),
              "Unexpected KisakCOD searchpath_s::language offset");

// Keep the original engine's handle table ABI explicit on both supported
// layouts: Win32 remains 284 bytes; native 64-bit builds use 304 bytes.
static_assert(sizeof(fileHandleData_t) == (sizeof(void *) == 8 ? 304u : 284u),
              "Unexpected KisakCOD fileHandleData_t size");
static_assert(offsetof(fileHandleData_t, zipFile) ==
                  (sizeof(void *) == 8 ? 32u : 20u),
              "Unexpected KisakCOD fileHandleData_t::zipFile offset");
static_assert(offsetof(fileHandleData_t, name) ==
                  (sizeof(void *) == 8 ? 44u : 28u),
              "Unexpected KisakCOD fileHandleData_t::name offset");

// Shared by the authentic com_files.cpp implementation and the Android port's
// exact extracted FS_HandleForFile / open / read / close function bodies.
fileHandleData_t fsh[65] = {};
