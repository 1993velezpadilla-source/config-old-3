#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_mod_override.py <cod-boz-port-root>")

root = Path(sys.argv[1]).resolve()
path = root / "src" / "s3e_file.c"
text = path.read_text(encoding="utf-8")

helper_anchor = "static int resolve_read_path(const char *name, char *out, size_t out_size) {\n"
helper = r'''static int resolve_xziel_mod_path(const char *name, char *out, size_t out_size) {
    const char *safe_name = name ? name : "";
    if (!safe_name[0] || safe_name[0] == '/') {
        return 0;
    }

    if (try_asset_path(out, out_size, "assets/xziel_mod", safe_name)) {
        return 1;
    }

    char flat_name[512];
    if (flat_group_name(safe_name, flat_name, sizeof(flat_name)) &&
        try_asset_path(out, out_size, "assets/xziel_mod", flat_name)) {
        return 1;
    }

    const char *leaf = base_name(safe_name);
    if (leaf != safe_name &&
        try_asset_path(out, out_size, "assets/xziel_mod", leaf)) {
        return 1;
    }

    return 0;
}

static int xziel_asset_trace_enabled(void) {
    const char *value = getenv("XZIEL_ASSET_TRACE");
    return value && value[0] && strcmp(value, "0") != 0;
}

static void xziel_trace_asset_request(const char *requested, const char *resolved, int hit) {
    if (!xziel_asset_trace_enabled()) {
        return;
    }

    char trace_path[1200];
    snprintf(trace_path, sizeof(trace_path), "%s/xziel_asset_trace.log", g_root);
    FILE *trace = fopen(trace_path, "a");
    if (!trace) {
        return;
    }

    fprintf(trace, "%s\t%s\t%s\n",
            hit ? "HIT" : "MISS",
            requested ? requested : "",
            resolved ? resolved : "");
    fclose(trace);
}

'''

if "resolve_xziel_mod_path" not in text:
    if helper_anchor not in text:
        raise SystemExit("PATCH_FAILED: resolve_read_path anchor not found")
    text = text.replace(helper_anchor, helper + helper_anchor, 1)
elif "xziel_trace_asset_request" not in text:
    if helper_anchor not in text:
        raise SystemExit("PATCH_FAILED: trace helper anchor not found")
    text = text.replace(helper_anchor, helper.split("static int resolve_xziel_mod_path", 1)[0] + helper_anchor, 1)

resolve_anchor = '''    const char *safe_name = name ? name : "";
    if (dtrz_archive_redirect_path(safe_name, out, out_size)) {
'''
resolve_replacement = '''    const char *safe_name = name ? name : "";
    if (resolve_xziel_mod_path(safe_name, out, out_size)) {
        return 1;
    }
    if (dtrz_archive_redirect_path(safe_name, out, out_size)) {
'''
if resolve_replacement not in text:
    if resolve_anchor not in text:
        raise SystemExit("PATCH_FAILED: resolve_read_path body anchor not found")
    text = text.replace(resolve_anchor, resolve_replacement, 1)

open_anchor = '''    } else if (is_archive_read_mode(safe_mode) && dtrz_prefer_entry(safe_name) &&
               (file = open_dtrz_entry(safe_name, opened_path, sizeof(opened_path))) != NULL) {
'''
open_replacement = '''    } else if (is_read_mode(safe_mode) &&
               resolve_xziel_mod_path(safe_name, path, sizeof(path))) {
        file = fopen(path, fopen_mode);
    } else if (is_archive_read_mode(safe_mode) && dtrz_prefer_entry(safe_name) &&
               (file = open_dtrz_entry(safe_name, opened_path, sizeof(opened_path))) != NULL) {
'''
if open_replacement not in text:
    if open_anchor not in text:
        raise SystemExit("PATCH_FAILED: s3eFileOpen priority anchor not found")
    text = text.replace(open_anchor, open_replacement, 1)

return_anchor = '''    if (!file && is_read_mode(safe_mode) && strcmp(base_name(safe_name), "console.bin") == 0) {
        file = fopen("/dev/null", "rb");
    }
    return file;
}
'''
return_replacement = '''    if (!file && is_read_mode(safe_mode) && strcmp(base_name(safe_name), "console.bin") == 0) {
        file = fopen("/dev/null", "rb");
    }

    if (is_read_mode(safe_mode)) {
        const char *resolved = opened_path[0] ? opened_path : (file ? safe_name : "");
        xziel_trace_asset_request(safe_name, resolved, file != NULL);
    }
    return file;
}
'''
if return_replacement not in text:
    if return_anchor not in text:
        raise SystemExit("PATCH_FAILED: s3eFileOpen return anchor not found")
    text = text.replace(return_anchor, return_replacement, 1)

exists_anchor = '''    if (dtrz_prefer_entry(safe_name) && dtrz_entry_exists(safe_name)) {
        return 1;
    }
'''
exists_replacement = '''    if (resolve_xziel_mod_path(safe_name, path, sizeof(path))) {
        return 1;
    }
    if (dtrz_prefer_entry(safe_name) && dtrz_entry_exists(safe_name)) {
        return 1;
    }
'''
if exists_replacement not in text:
    if exists_anchor not in text:
        raise SystemExit("PATCH_FAILED: s3eFileCheckExists anchor not found")
    text = text.replace(exists_anchor, exists_replacement, 1)

path.write_text(text, encoding="utf-8")
print("XZIEL_BOZ_MOD_OVERRIDE_PATCH_OK")
print("XZIEL_BOZ_ASSET_TRACE_PATCH_OK")
