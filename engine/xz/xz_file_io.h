#ifndef XZ_FILE_IO_H
#define XZ_FILE_IO_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int XzFile_SetRoot(const char *root_path);
const char *XzFile_Root(void);

int XzFile_Open(const char *path, int *handle);
void XzFile_Close(int handle);
int XzFile_Read(int handle, void *destination, int count);
void XzFile_Seek(int handle, int position);

#ifdef __cplusplus
}
#endif

#endif
