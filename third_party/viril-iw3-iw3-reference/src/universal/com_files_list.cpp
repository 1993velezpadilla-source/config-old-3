// Original IW3 file-list ownership contract, shared by every platform.
#include <qcommon/qcommon.h>
#include <universal/com_memory.h>
#include <universal/com_files.h>

void __cdecl FS_FreeFileList(const char **list)
{
    if (list)
        Hunk_UserDestroy((HunkUser *)*(list - 1));
}
