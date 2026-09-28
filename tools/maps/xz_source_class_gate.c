#include "xz_source_class_registry.h"

#include <stdio.h>
#include <string.h>

int main(void)
{
    XzSourceClassCoverage coverage;
    char line[512];

    XzSourceClassCoverage_Init(&coverage);

    while (fgets(line, sizeof(line), stdin)) {
        size_t n = strlen(line);

        while (n > 0u &&
               (line[n - 1u] == '\n' ||
                line[n - 1u] == '\r'))
            line[--n] = '\0';

        if (!line[0])
            continue;

        if (!XzSourceClassCoverage_Record(
                &coverage,
                line))
            fprintf(
                stderr,
                "XZIEL_SOURCE_CLASS_UNSUPPORTED %s\n",
                line);
    }

    if (!XzSourceClassCoverage_Finalize(&coverage)) {
        fprintf(
            stderr,
            "XZIEL_SOURCE_CLASS_GATE_FAILURE total=%u classified=%u unsupported=%u first=%s\n",
            coverage.source_class_count,
            coverage.classified_class_count,
            coverage.unclassified_class_count,
            coverage.first_unclassified);
        return 5;
    }

    printf(
        "XZIEL_SOURCE_CLASS_GATE_GREEN total=%u classified=%u unsupported=0 familyMask=0x%08x\n",
        coverage.source_class_count,
        coverage.classified_class_count,
        coverage.family_mask);

    return 0;
}
