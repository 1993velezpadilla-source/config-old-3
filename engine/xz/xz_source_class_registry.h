#ifndef XZ_SOURCE_CLASS_REGISTRY_H
#define XZ_SOURCE_CLASS_REGISTRY_H

#include "xz_package_boot.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_SOURCE_CLASS_NAME_MAX 128u

typedef struct XzSourceClassCoverage {
    uint32_t source_class_count;
    uint32_t classified_class_count;
    uint32_t ignored_class_count;
    uint32_t unclassified_class_count;
    uint32_t family_class_count[XZ_PACKAGE_BOOT_FAMILY_COUNT];
    uint32_t family_mask;
    int ready;
    char first_unclassified[XZ_SOURCE_CLASS_NAME_MAX];
} XzSourceClassCoverage;

int XzSourceClass_Classify(
    const char *class_name,
    XzPackageBootFamily *out_family);

void XzSourceClassCoverage_Init(
    XzSourceClassCoverage *coverage);

int XzSourceClassCoverage_Record(
    XzSourceClassCoverage *coverage,
    const char *class_name);

int XzSourceClassCoverage_Finalize(
    XzSourceClassCoverage *coverage);

int XzSourceClassRegistry_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif
