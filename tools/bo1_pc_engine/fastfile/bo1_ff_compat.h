#pragma once
// Substitution of Windows HANDLE-based file OPEN/SIZE/CLOSE calls for Android POSIX.
// The original decompiled BO1 DB_FileExists and DB_FileSize function bodies remain unchanged.
// This bridge is for FFD_DEFAULT; FFD_MOD_DIR and USER_MAP are explicitly supported in file-size checks.
#include <cstddef>
#include <cstdint>
#ifndef __cdecl
#define __cdecl
#endif
enum FF_DIR : std::int32_t { FFD_DEFAULT=0, FFD_MOD_DIR=1, FFD_USER_MAP=2 };
void DB_BuildOSPath_FromSource(const char *zoneName, FF_DIR source, unsigned int max_len, char *filename);
void DB_BuildOSPath_ForUsermap(const char *zoneName, unsigned int max_len, char *filename);
void *CreateFileA(const char *name, unsigned int access, unsigned int share,
                  void *security, unsigned int creation, unsigned int flags, void *templ);
unsigned int GetFileSize(void *handle, void *high_size);
int CloseHandle(void *handle);
char __cdecl DB_FileExists(const char *zoneName, FF_DIR source);
int __cdecl DB_FileSize(const char *zoneName, FF_DIR source);
extern "C" __attribute__((visibility("default")))
int bo1_ff_root_configure(const char *game_root, const char *language);
extern "C" __attribute__((visibility("default")))
int bo1_original_zone_exists(const char *name);
extern "C" __attribute__((visibility("default")))
int bo1_original_zone_size(const char *name);
