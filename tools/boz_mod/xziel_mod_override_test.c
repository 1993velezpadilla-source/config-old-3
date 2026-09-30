#include "s3e_host_internal.h"

#include <assert.h>

char g_root[1024];
struct dtrz_index g_dtrz;
struct memory_file *g_memory_files;

void codboz_hide_virtual_stick_artwork(const char *name, uint8_t *data, size_t size) {
    (void)name;
    (void)data;
    (void)size;
}

static void make_dir(const char *path) {
    int rc = mkdir(path, 0777);
    assert(rc == 0 || errno == EEXIST);
}

static void write_bytes(const char *path, const void *data, size_t size) {
    FILE *f = fopen(path, "wb");
    assert(f);
    assert(fwrite(data, 1, size, f) == size);
    assert(fclose(f) == 0);
}

static void write_le16(FILE *f, uint16_t value) {
    uint8_t b[2] = {(uint8_t)value, (uint8_t)(value >> 8)};
    assert(fwrite(b, 1, sizeof(b), f) == sizeof(b));
}

static void write_le32(FILE *f, uint32_t value) {
    uint8_t b[4] = {
        (uint8_t)value,
        (uint8_t)(value >> 8),
        (uint8_t)(value >> 16),
        (uint8_t)(value >> 24),
    };
    assert(fwrite(b, 1, sizeof(b), f) == sizeof(b));
}

static void create_fake_dtrz(const char *path, const char *entry_name,
                             const char *payload) {
    FILE *f = fopen(path, "wb");
    assert(f);

    const uint16_t file_count = 1;
    const uint16_t group_count = 0;
    const size_t name_len = strlen(entry_name) + 1;
    const uint32_t payload_offset =
        (uint32_t)(9 + name_len + 4 + 6 + 16);

    assert(fwrite("DTRZ", 1, 4, f) == 4);
    write_le16(f, file_count);
    write_le16(f, group_count);
    fputc(0, f);

    assert(fwrite(entry_name, 1, name_len, f) == name_len);
    write_le32(f, 1);

    uint8_t six_zeroes[6] = {0};
    assert(fwrite(six_zeroes, 1, sizeof(six_zeroes), f) == sizeof(six_zeroes));

    write_le32(f, payload_offset);
    write_le32(f, (uint32_t)strlen(payload));
    write_le32(f, 0);
    write_le32(f, 0);

    assert(ftell(f) == (long)payload_offset);
    assert(fwrite(payload, 1, strlen(payload), f) == strlen(payload));
    assert(fclose(f) == 0);
}

static void read_exact_asset(const char *name, char *out, size_t out_size) {
    memset(out, 0, out_size);
    void *file = s3eFileOpen(name, "rb");
    assert(file);
    uint32_t n = s3eFileRead(out, 1, (uint32_t)(out_size - 1), file);
    assert(n > 0);
    assert(s3eFileClose(file) == 0);
}

static void assert_trace_contains(const char *needle) {
    char path[1400];
    snprintf(path, sizeof(path), "%s/xziel_asset_trace.log", g_root);
    FILE *f = fopen(path, "rb");
    assert(f);

    char buffer[8192];
    size_t n = fread(buffer, 1, sizeof(buffer) - 1, f);
    buffer[n] = 0;
    fclose(f);

    if (!strstr(buffer, needle)) {
        fprintf(stderr, "trace missing '%s'\nTRACE:\n%s\n", needle, buffer);
        abort();
    }
}

int main(void) {
    char template[] = "/tmp/xziel-boz-mod.XXXXXX";
    char *root = mkdtemp(template);
    assert(root);
    snprintf(g_root, sizeof(g_root), "%s", root);

    char p[1400];
    snprintf(p, sizeof(p), "%s/assets", g_root);
    make_dir(p);
    snprintf(p, sizeof(p), "%s/assets/xziel_mod", g_root);
    make_dir(p);
    snprintf(p, sizeof(p), "%s/assets/xziel_mod/data-etc", g_root);
    make_dir(p);
    snprintf(p, sizeof(p), "%s/assets/data-gles1", g_root);
    make_dir(p);

    const char *requested = "data-etc/xziel_probe.group.bin";

    snprintf(p, sizeof(p), "%s/assets/xziel_mod/data-etc/xziel_probe.group.bin", g_root);
    write_bytes(p, "XZIEL_OVERRIDE", strlen("XZIEL_OVERRIDE"));

    snprintf(p, sizeof(p), "%s/assets/blackops_gles1.dz", g_root);
    create_fake_dtrz(p, requested, "STOCK_DTRZ");

    memset(&g_dtrz, 0, sizeof(g_dtrz));
    assert(setenv("XZIEL_ASSET_TRACE", "1", 1) == 0);

    assert(s3eFileCheckExists(requested) == 1);

    char contents[64];
    read_exact_asset(requested, contents, sizeof(contents));

    if (strcmp(contents, "XZIEL_OVERRIDE") != 0) {
        fprintf(stderr, "override failed: got '%s'\n", contents);
        return 2;
    }

    assert_trace_contains("HIT\tdata-etc/xziel_probe.group.bin\t");
    assert_trace_contains("assets/xziel_mod/data-etc/xziel_probe.group.bin");

    puts("XZIEL_BOZ_OVERRIDE_PRIORITY_OK");
    puts("XZIEL_BOZ_ASSET_TRACE_OK");
    puts("requested=data-etc/xziel_probe.group.bin");
    puts("winner=assets/xziel_mod/data-etc/xziel_probe.group.bin");
    puts("stock_source=assets/blackops_gles1.dz");
    puts("trace=xziel_asset_trace.log");
    return 0;
}
