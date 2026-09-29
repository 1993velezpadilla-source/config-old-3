#include "xz_source_adapter_registry.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int FindKind(
    const char *name,
    XzSourceAssetKind *out_kind)
{
    unsigned int i;

    if (!name || !out_kind)
        return 0;

    for (i = 0u; i < XZ_SOURCE_KIND_COUNT; ++i) {
        XzSourceAssetKind kind = (XzSourceAssetKind)i;
        if (strcmp(
                name,
                XzSourceAdapterRegistry_KindName(kind)) == 0) {
            *out_kind = kind;
            return 1;
        }
    }

    return 0;
}

int main(void)
{
    XzSourceAdapterRegistry registry;
    char line[256];
    uint32_t seen_mask = 0u;
    unsigned int rows = 0u;
    unsigned int i;

    XzSourceAdapterRegistry_Init(&registry);

    while (fgets(line, sizeof(line), stdin)) {
        char *sep;
        char *end = NULL;
        unsigned long long parsed;
        XzSourceAssetKind kind;
        uint32_t bit;
        size_t len = strlen(line);

        while (len > 0u &&
               (line[len - 1u] == '\n' ||
                line[len - 1u] == '\r'))
            line[--len] = '\0';

        if (!line[0])
            continue;

        sep = strchr(line, '|');
        if (!sep || sep == line || !sep[1]) {
            fprintf(stderr,
                "XZIEL_SOURCE_ADAPTER_REQUIREMENT_INVALID %s\n",
                line);
            return 2;
        }

        *sep = '\0';

        if (!FindKind(line, &kind)) {
            fprintf(stderr,
                "XZIEL_SOURCE_ADAPTER_KIND_UNKNOWN %s\n",
                line);
            return 3;
        }

        bit = 1u << (unsigned int)kind;
        if ((seen_mask & bit) != 0u) {
            fprintf(stderr,
                "XZIEL_SOURCE_ADAPTER_KIND_DUPLICATE %s\n",
                line);
            return 4;
        }

        parsed = strtoull(sep + 1, &end, 10);
        if (!end || *end != '\0' || parsed == 0ull) {
            fprintf(stderr,
                "XZIEL_SOURCE_ADAPTER_COUNT_INVALID %s|%s\n",
                line,
                sep + 1);
            return 5;
        }

        if (!XzSourceAdapterRegistry_Require(
                &registry,
                kind,
                (uint64_t)parsed)) {
            fprintf(stderr,
                "XZIEL_SOURCE_ADAPTER_REQUIRE_FAILED %s\n",
                line);
            return 6;
        }

        /*
         * Parsing has been proven exhaustively by the UE property sweep.
         * Native conversion and validation are deliberately NOT claimed.
         */
        if (!XzSourceAdapterRegistry_RegisterSupport(
                &registry,
                kind,
                1,
                0,
                0)) {
            fprintf(stderr,
                "XZIEL_SOURCE_ADAPTER_REGISTER_FAILED %s\n",
                line);
            return 7;
        }

        seen_mask |= bit;
        rows++;
    }

    if (rows == 0u || registry.required_exports == 0u) {
        fprintf(stderr,
            "XZIEL_SOURCE_ADAPTER_REQUIREMENTS_EMPTY\n");
        return 8;
    }

    if (XzSourceAdapterRegistry_Finalize(&registry)) {
        fprintf(stderr,
            "XZIEL_SOURCE_CONVERSION_FALSE_READY\n");
        return 9;
    }

    if (registry.ready ||
        registry.converted_exports != 0u ||
        registry.verified_exports != 0u ||
        registry.failed_kind_mask !=
            registry.required_kind_mask) {
        fprintf(stderr,
            "XZIEL_SOURCE_CONVERSION_FAIL_CLOSED_BROKEN\n");
        return 10;
    }

    for (i = 0u; i < XZ_SOURCE_KIND_COUNT; ++i) {
        const XzSourceAdapterSpec *spec = &registry.kinds[i];
        if (spec->required_exports == 0u)
            continue;

        printf(
            "XZIEL_SOURCE_CONVERSION_BLOCKER %s required=%" PRIu64
            " parsed=1 converter=0 validator=0\n",
            XzSourceAdapterRegistry_KindName(
                (XzSourceAssetKind)i),
            spec->required_exports);
    }

    printf(
        "XZIEL_SOURCE_CONVERSION_FAIL_CLOSED_GREEN "
        "requiredExports=%" PRIu64
        " requiredKindMask=0x%08x failedKindMask=0x%08x\n",
        registry.required_exports,
        registry.required_kind_mask,
        registry.failed_kind_mask);

    return 0;
}
