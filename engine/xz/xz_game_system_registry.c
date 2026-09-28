#include "xz_game_system_registry.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static int XzGameSystemRegistry_Reserve(
    void **storage,
    uint32_t *capacity,
    uint32_t needed,
    uint32_t initial_capacity,
    size_t element_size)
{
    uint32_t next;
    void *grown;
    size_t bytes;

    if (!storage || !capacity || element_size == 0u)
        return 0;

    if (needed <= *capacity)
        return 1;

    next = *capacity ? *capacity : initial_capacity;
    if (next == 0u)
        next = 1u;

    while (next < needed) {
        if (next > UINT32_MAX / 2u) {
            next = needed;
            break;
        }
        next *= 2u;
    }

    bytes = (size_t)next * element_size;
    if (next != 0u &&
        bytes / element_size != (size_t)next)
        return 0;

    grown = realloc(*storage, bytes);
    if (!grown)
        return 0;

    memset(
        (unsigned char *)grown +
            (size_t)(*capacity) * element_size,
        0,
        (size_t)(next - *capacity) * element_size);

    *storage = grown;
    *capacity = next;
    return 1;
}

static int XzGameSystemRegistry_ValidIndex(
    const XzGameSystemRegistry *registry,
    uint32_t index)
{
    return registry &&
           registry->systems &&
           index > 0u &&
           index <= registry->system_count;
}

static void XzGameSystemRegistry_Invalidate(
    XzGameSystemRegistry *registry)
{
    if (!registry)
        return;

    registry->finalized = 0;
    registry->ready = 0;
}

void XzGameSystemRegistry_Init(
    XzGameSystemRegistry *registry)
{
    if (!registry)
        return;

    memset(registry, 0, sizeof(*registry));
}

void XzGameSystemRegistry_Destroy(
    XzGameSystemRegistry *registry)
{
    if (!registry)
        return;

    free(registry->systems);
    free(registry->dependencies);
    memset(registry, 0, sizeof(*registry));
}

int XzGameSystemRegistry_Find(
    const XzGameSystemRegistry *registry,
    const char *name,
    uint32_t *out_index)
{
    uint32_t i;

    if (!registry || !name || !name[0])
        return 0;

    for (i = 0u; i < registry->system_count; ++i) {
        if (strcmp(registry->systems[i].name, name) == 0) {
            if (out_index)
                *out_index = i + 1u;
            return 1;
        }
    }

    return 0;
}

int XzGameSystemRegistry_Register(
    XzGameSystemRegistry *registry,
    const char *name,
    uint32_t *out_index)
{
    XzGameSystemRecord *system;
    uint32_t existing = 0u;

    if (!registry ||
        !name ||
        !name[0] ||
        strlen(name) >= XZ_GAME_SYSTEM_NAME_MAX)
        return 0;

    if (XzGameSystemRegistry_Find(
            registry,
            name,
            &existing))
        return 0;

    if (!XzGameSystemRegistry_Reserve(
            (void **)&registry->systems,
            &registry->system_capacity,
            registry->system_count + 1u,
            XZ_GAME_SYSTEM_INITIAL_SYSTEMS,
            sizeof(*registry->systems)))
        return 0;

    system = &registry->systems[registry->system_count];
    memset(system, 0, sizeof(*system));
    memcpy(system->name, name, strlen(name) + 1u);

    registry->system_count++;
    XzGameSystemRegistry_Invalidate(registry);

    if (out_index)
        *out_index = registry->system_count;

    return 1;
}

int XzGameSystemRegistry_AddDependency(
    XzGameSystemRegistry *registry,
    uint32_t system_index,
    uint32_t required_index)
{
    uint32_t i;

    if (!XzGameSystemRegistry_ValidIndex(
            registry,
            system_index) ||
        !XzGameSystemRegistry_ValidIndex(
            registry,
            required_index) ||
        system_index == required_index)
        return 0;

    for (i = 0u;
         i < registry->dependency_count;
         ++i) {
        const XzGameSystemDependency *dep =
            &registry->dependencies[i];

        if (dep->system_index == system_index &&
            dep->required_index == required_index)
            return 0;
    }

    if (!XzGameSystemRegistry_Reserve(
            (void **)&registry->dependencies,
            &registry->dependency_capacity,
            registry->dependency_count + 1u,
            XZ_GAME_SYSTEM_INITIAL_DEPENDENCIES,
            sizeof(*registry->dependencies)))
        return 0;

    registry->dependencies[
        registry->dependency_count].system_index =
            system_index;
    registry->dependencies[
        registry->dependency_count].required_index =
            required_index;

    registry->dependency_count++;
    XzGameSystemRegistry_Invalidate(registry);
    return 1;
}

int XzGameSystemRegistry_SetIgnored(
    XzGameSystemRegistry *registry,
    uint32_t system_index,
    int ignored)
{
    if (!XzGameSystemRegistry_ValidIndex(
            registry,
            system_index))
        return 0;

    registry->systems[system_index - 1u].ignored =
        ignored ? 1u : 0u;
    XzGameSystemRegistry_Invalidate(registry);
    return 1;
}

int XzGameSystemRegistry_MarkPreDone(
    XzGameSystemRegistry *registry,
    uint32_t system_index)
{
    XzGameSystemRecord *system;

    if (!XzGameSystemRegistry_ValidIndex(
            registry,
            system_index))
        return 0;

    system = &registry->systems[system_index - 1u];

    if (system->failed)
        return 0;

    system->pre_done = 1u;
    XzGameSystemRegistry_Invalidate(registry);
    return 1;
}

int XzGameSystemRegistry_MarkPostDone(
    XzGameSystemRegistry *registry,
    uint32_t system_index)
{
    XzGameSystemRecord *system;
    uint32_t i;

    if (!XzGameSystemRegistry_ValidIndex(
            registry,
            system_index))
        return 0;

    system = &registry->systems[system_index - 1u];

    if (system->failed || !system->pre_done)
        return 0;

    for (i = 0u;
         i < registry->dependency_count;
         ++i) {
        const XzGameSystemDependency *dep =
            &registry->dependencies[i];
        const XzGameSystemRecord *required;

        if (dep->system_index != system_index)
            continue;

        if (!XzGameSystemRegistry_ValidIndex(
                registry,
                dep->required_index))
            return 0;

        required =
            &registry->systems[dep->required_index - 1u];

        if (!required->ignored &&
            (!required->post_done || required->failed))
            return 0;
    }

    system->post_done = 1u;
    XzGameSystemRegistry_Invalidate(registry);
    return 1;
}

int XzGameSystemRegistry_MarkFailed(
    XzGameSystemRegistry *registry,
    uint32_t system_index)
{
    if (!XzGameSystemRegistry_ValidIndex(
            registry,
            system_index))
        return 0;

    registry->systems[system_index - 1u].failed = 1u;
    registry->systems[system_index - 1u].post_done = 0u;
    XzGameSystemRegistry_Invalidate(registry);
    return 1;
}

static int XzGameSystemRegistry_Acyclic(
    const XzGameSystemRegistry *registry,
    uint32_t *out_unresolved)
{
    uint32_t *indegree = NULL;
    uint32_t *queue = NULL;
    uint32_t active = 0u;
    uint32_t visited = 0u;
    uint32_t head = 0u;
    uint32_t tail = 0u;
    uint32_t i;
    int ok = 0;

    if (out_unresolved)
        *out_unresolved = 0u;

    if (!registry)
        return 0;

    if (registry->system_count == 0u)
        return 1;

    indegree =
        (uint32_t *)calloc(
            registry->system_count,
            sizeof(*indegree));
    queue =
        (uint32_t *)calloc(
            registry->system_count,
            sizeof(*queue));

    if (!indegree || !queue)
        goto cleanup;

    for (i = 0u; i < registry->system_count; ++i) {
        if (!registry->systems[i].ignored)
            active++;
    }

    for (i = 0u;
         i < registry->dependency_count;
         ++i) {
        const XzGameSystemDependency *dep =
            &registry->dependencies[i];

        if (!XzGameSystemRegistry_ValidIndex(
                registry,
                dep->system_index) ||
            !XzGameSystemRegistry_ValidIndex(
                registry,
                dep->required_index))
            goto cleanup;

        if (registry->systems[
                dep->system_index - 1u].ignored ||
            registry->systems[
                dep->required_index - 1u].ignored)
            continue;

        indegree[dep->system_index - 1u]++;
    }

    for (i = 0u; i < registry->system_count; ++i) {
        if (!registry->systems[i].ignored &&
            indegree[i] == 0u) {
            queue[tail++] = i + 1u;
        }
    }

    while (head < tail) {
        uint32_t current = queue[head++];

        visited++;

        for (i = 0u;
             i < registry->dependency_count;
             ++i) {
            const XzGameSystemDependency *dep =
                &registry->dependencies[i];
            uint32_t child;

            if (dep->required_index != current)
                continue;

            child = dep->system_index;

            if (registry->systems[child - 1u].ignored)
                continue;

            if (indegree[child - 1u] == 0u)
                goto cleanup;

            indegree[child - 1u]--;

            if (indegree[child - 1u] == 0u)
                queue[tail++] = child;
        }
    }

    if (out_unresolved)
        *out_unresolved =
            active >= visited
                ? active - visited
                : 0u;

    ok = visited == active;

cleanup:
    free(indegree);
    free(queue);
    return ok;
}

int XzGameSystemRegistry_Finalize(
    XzGameSystemRegistry *registry)
{
    uint32_t i;
    uint32_t unresolved_cycle = 0u;
    int acyclic;

    if (!registry)
        return 0;

    registry->active_count = 0u;
    registry->pre_done_count = 0u;
    registry->post_done_count = 0u;
    registry->ignored_count = 0u;
    registry->failed_count = 0u;
    registry->unresolved_dependency_count = 0u;

    acyclic =
        XzGameSystemRegistry_Acyclic(
            registry,
            &unresolved_cycle);

    registry->unresolved_dependency_count =
        unresolved_cycle;

    for (i = 0u; i < registry->system_count; ++i) {
        const XzGameSystemRecord *system =
            &registry->systems[i];

        if (system->ignored) {
            registry->ignored_count++;
            continue;
        }

        registry->active_count++;

        if (system->pre_done)
            registry->pre_done_count++;

        if (system->post_done)
            registry->post_done_count++;

        if (system->failed)
            registry->failed_count++;
    }

    for (i = 0u;
         i < registry->dependency_count;
         ++i) {
        const XzGameSystemDependency *dep =
            &registry->dependencies[i];
        const XzGameSystemRecord *system;
        const XzGameSystemRecord *required;

        if (!XzGameSystemRegistry_ValidIndex(
                registry,
                dep->system_index) ||
            !XzGameSystemRegistry_ValidIndex(
                registry,
                dep->required_index)) {
            registry->unresolved_dependency_count++;
            continue;
        }

        system =
            &registry->systems[dep->system_index - 1u];
        required =
            &registry->systems[dep->required_index - 1u];

        if (system->ignored || required->ignored)
            continue;

        if (!required->post_done ||
            required->failed) {
            registry->unresolved_dependency_count++;
        }
    }

    registry->finalized = 1;
    registry->ready =
        registry->system_count > 0u &&
        acyclic &&
        registry->failed_count == 0u &&
        registry->unresolved_dependency_count == 0u &&
        registry->pre_done_count ==
            registry->active_count &&
        registry->post_done_count ==
            registry->active_count;

    return registry->ready;
}

int XzGameSystemRegistry_IsReady(
    const XzGameSystemRegistry *registry)
{
    return registry &&
           registry->finalized &&
           registry->ready;
}

int XzGameSystemRegistry_SelfTest(void)
{
    XzGameSystemRegistry registry;
    uint32_t core = 0u;
    uint32_t audio = 0u;
    uint32_t spawner = 0u;
    uint32_t ignored = 0u;
    int ok = 0;

    XzGameSystemRegistry_Init(&registry);

    if (!XzGameSystemRegistry_Register(
            &registry,
            "zm",
            &core) ||
        !XzGameSystemRegistry_Register(
            &registry,
            "audio",
            &audio) ||
        !XzGameSystemRegistry_Register(
            &registry,
            "spawner",
            &spawner) ||
        !XzGameSystemRegistry_Register(
            &registry,
            "unused_mp_gadget",
            &ignored))
        goto cleanup;

    if (!XzGameSystemRegistry_AddDependency(
            &registry,
            audio,
            core) ||
        !XzGameSystemRegistry_AddDependency(
            &registry,
            spawner,
            audio))
        goto cleanup;

    if (!XzGameSystemRegistry_SetIgnored(
            &registry,
            ignored,
            1))
        goto cleanup;

    if (!XzGameSystemRegistry_MarkPreDone(
            &registry,
            core) ||
        !XzGameSystemRegistry_MarkPostDone(
            &registry,
            core))
        goto cleanup;

    if (!XzGameSystemRegistry_MarkPreDone(
            &registry,
            audio) ||
        !XzGameSystemRegistry_MarkPostDone(
            &registry,
            audio))
        goto cleanup;

    if (!XzGameSystemRegistry_MarkPreDone(
            &registry,
            spawner) ||
        !XzGameSystemRegistry_MarkPostDone(
            &registry,
            spawner))
        goto cleanup;

    if (!XzGameSystemRegistry_Finalize(&registry))
        goto cleanup;

    if (!registry.ready ||
        registry.active_count != 3u ||
        registry.ignored_count != 1u)
        goto cleanup;

    /*
     * Dependency cycles must fail closed.
     */
    if (!XzGameSystemRegistry_AddDependency(
            &registry,
            core,
            spawner))
        goto cleanup;

    if (XzGameSystemRegistry_Finalize(&registry))
        goto cleanup;

    if (registry.unresolved_dependency_count == 0u)
        goto cleanup;

    ok = 1;

cleanup:
    XzGameSystemRegistry_Destroy(&registry);
    return ok;
}
