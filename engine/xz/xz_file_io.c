#include "xz_file_io.h"

#include <limits.h>
#include <stdio.h>
#include <string.h>

#define XZ_FILE_IO_MAX_HANDLES 64
#define XZ_FILE_IO_MAX_PATH 2048

static FILE *xz_file_handles[XZ_FILE_IO_MAX_HANDLES];
static char xz_file_root[XZ_FILE_IO_MAX_PATH] = ".";

static int XzFile_SafeRelativePath(const char *path)
{
    if (!path || !path[0])
        return 0;
    if (path[0] == '/' || path[0] == '\\')
        return 0;
    if (strstr(path, "../") || strstr(path, "..\\"))
        return 0;
    return 1;
}

static int XzFile_BuildPath(
    const char *path,
    char output[XZ_FILE_IO_MAX_PATH])
{
    int written;

    if (!output || !XzFile_SafeRelativePath(path))
        return 0;

    if (strcmp(xz_file_root, ".") == 0)
        written = snprintf(output, XZ_FILE_IO_MAX_PATH, "%s", path);
    else
        written = snprintf(
            output,
            XZ_FILE_IO_MAX_PATH,
            "%s/%s",
            xz_file_root,
            path);

    return written > 0 && written < XZ_FILE_IO_MAX_PATH;
}

int XzFile_SetRoot(const char *root_path)
{
    size_t length;

    if (!root_path || !root_path[0])
        return 0;

    length = strlen(root_path);
    while (length > 1u &&
           (root_path[length - 1u] == '/' ||
            root_path[length - 1u] == '\\'))
        length--;

    if (length == 0u || length >= sizeof(xz_file_root))
        return 0;

    memcpy(xz_file_root, root_path, length);
    xz_file_root[length] = '\0';
    return 1;
}

const char *XzFile_Root(void)
{
    return xz_file_root;
}

int XzFile_Open(const char *path, int *handle)
{
    char resolved[XZ_FILE_IO_MAX_PATH];
    FILE *file;
    long bytes;
    int slot;

    if (handle)
        *handle = -1;

    if (!handle || !XzFile_BuildPath(path, resolved))
        return -1;

    file = fopen(resolved, "rb");
    if (!file)
        return -1;

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return -1;
    }

    bytes = ftell(file);
    if (bytes < 0 || bytes > INT_MAX ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return -1;
    }

    for (slot = 0; slot < XZ_FILE_IO_MAX_HANDLES; ++slot) {
        if (!xz_file_handles[slot]) {
            xz_file_handles[slot] = file;
            *handle = slot + 1;
            return (int)bytes;
        }
    }

    fclose(file);
    return -1;
}

void XzFile_Close(int handle)
{
    int slot = handle - 1;

    if (slot < 0 || slot >= XZ_FILE_IO_MAX_HANDLES)
        return;

    if (xz_file_handles[slot]) {
        fclose(xz_file_handles[slot]);
        xz_file_handles[slot] = NULL;
    }
}

int XzFile_Read(int handle, void *destination, int count)
{
    int slot = handle - 1;
    size_t got;

    if (slot < 0 || slot >= XZ_FILE_IO_MAX_HANDLES ||
        !xz_file_handles[slot] ||
        !destination ||
        count <= 0)
        return 0;

    got = fread(destination, 1u, (size_t)count, xz_file_handles[slot]);
    if (got > (size_t)INT_MAX)
        return 0;

    return (int)got;
}

void XzFile_Seek(int handle, int position)
{
    int slot = handle - 1;

    if (slot < 0 || slot >= XZ_FILE_IO_MAX_HANDLES ||
        !xz_file_handles[slot] ||
        position < 0)
        return;

    (void)fseek(xz_file_handles[slot], (long)position, SEEK_SET);
}
