#include "com_files.h"

// Shared engine file-system state. These were zero-initialized globals in the
// original com_files.cpp; keeping one definition lets the authentic engine and
// the Android-extracted original functions operate on the same search path and
// IWD bookkeeping rather than parallel diagnostic copies.
int fs_iwdFileCount = 0;
int fs_checksumFeed = 0;
int bLanguagesListed = 0;
int com_fileAccessed = 0;
int fs_loadStack = 0;
char fs_gamedir[256] = {};
searchpath_s *fs_searchpaths = nullptr;


// Additional zero-initialized state moved from the original com_files.cpp so
// the full engine and Android source slices share one canonical owner.
const dvar_t *fs_remotePCDirectory = nullptr;
const dvar_t *fs_remotePCName = nullptr;
const dvar_t *fs_homepath = nullptr;
const dvar_s *fs_debug = nullptr;
const dvar_s *fs_restrict = nullptr;
const dvar_s *fs_ignoreLocalized = nullptr;
const dvar_s *fs_basepath = nullptr;
const dvar_s *fs_copyfiles = nullptr;
const dvar_s *fs_cdpath = nullptr;
const dvar_s *fs_gameDirVar = nullptr;
const dvar_s *fs_basegame = nullptr;
int fs_fakeChkSum = 0;
int fs_numServerIwds = 0;
int fs_serverIwds[1024] = {};
void *g_writeLogEvent = nullptr;
int marker_com_files = 0;
void *g_writeLogCompleteEvent = nullptr;
const char *fs_serverIwdNames[1024] = {};
char lastValidBase[256] = {};
char lastValidGame[256] = {};
