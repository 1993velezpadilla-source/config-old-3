package org.libsdl.app;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Strict installer for XZIEL .xzp map packages.
 *
 * The package is verified before it is made visible to the XZIEL runtime:
 * - xziel.package.json must be unique and source-inventory strictReady;
 * - map metadata must match the portable descriptor contract;
 * - xziel.runtime.json must promote all 24 universal families to ready;
 * - every runtime artifact must be present in the verified package inventory;
 * - every payload member must match manifest size + SHA-256;
 * - extra, missing, duplicate or unsafe paths are rejected;
 * - extraction occurs into a temporary private directory and is renamed only
 *   after the complete payload verifies.
 */
public final class XzielMapPackageInstaller {
    private XzielMapPackageInstaller() {}

    private static final String RUNTIME_MANIFEST = "xziel.runtime.json";
    private static final String RUNTIME_FORMAT = "xziel_runtime_manifest_v1";
    private static final int REQUIRED_FAMILY_COUNT = 24;

    private static final String[] RUNTIME_FAMILY_ORDER = {
        "world_geometry",
        "collision",
        "navigation_pathing",
        "materials_textures",
        "static_models_props",
        "animated_models_rigs",
        "animations",
        "weapons_equipment",
        "pack_a_punch_variants",
        "audio_sfx",
        "ambient_music_vo",
        "vfx_particles",
        "lighting_postfx",
        "gameplay_scripts",
        "interactables",
        "perks_wunderfizz",
        "powerups",
        "gobblegum",
        "mystery_box",
        "spawns_rounds_ai",
        "hud_ui_prompts",
        "multiplayer_replication",
        "platform_packaging",
        "soak_release_quality"
    };

    private static final Set<String> REQUIRED_RUNTIME_FAMILIES =
        new HashSet<>(Arrays.asList(RUNTIME_FAMILY_ORDER));

    private static final String GENERATED_BOOT_PLAN = ".xziel-boot.plan";
    private static final String GENERATED_PACKAGE_META = ".xziel-package.json";

    private static final String[] REQUIRED_RUNTIME_GLOBALS = {
        "sourceInventoryStrictReady",
        "allRequiredFamiliesReady",
        "entryWorldRuntimeLoadable",
        "noMissingRuntimeArtifacts",
        "noUnsupportedRuntimeFormats",
        "noSilentFallbacks",
        "multiplayerContractReady",
        "platformPackagingReady",
        "soakReleaseQualityReady"
    };

    public static final class InstalledMap {
        public final String mapId;
        public final String entryWorld;
        public final String gameDirectoryName;
        public final File gameDirectory;

        InstalledMap(
                String mapId,
                String entryWorld,
                String gameDirectoryName,
                File gameDirectory) {
            this.mapId = mapId;
            this.entryWorld = entryWorld;
            this.gameDirectoryName = gameDirectoryName;
            this.gameDirectory = gameDirectory;
        }
    }

    private static final class ExpectedFile {
        final String path;
        final long bytes;
        final String sha256;

        ExpectedFile(String path, long bytes, String sha256) {
            this.path = path;
            this.bytes = bytes;
            this.sha256 = sha256;
        }
    }

    public static InstalledMap install(File packageFile, File dataRoot)
            throws IOException {
        if (packageFile == null || !packageFile.isFile()) {
            throw new IOException("XZIEL map package does not exist");
        }
        if (dataRoot == null || !dataRoot.isDirectory()) {
            throw new IOException("XZIEL runtime data root is unavailable");
        }

        try (ZipFile zip = new ZipFile(packageFile)) {
            ZipEntry manifestEntry = null;
            int manifestCount = 0;
            Set<String> zipNames = new HashSet<>();

            Enumeration<? extends ZipEntry> enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                ZipEntry entry = enumeration.nextElement();
                String name = normalize(entry.getName());
                if (!zipNames.add(name)) {
                    throw new IOException("Duplicate ZIP member: " + name);
                }
                validateSafeRelativePath(name);
                if ("xziel.package.json".equals(name)) {
                    manifestEntry = entry;
                    manifestCount++;
                }
            }

            if (manifestCount != 1 || manifestEntry == null) {
                throw new IOException(
                    "XZIEL package must contain exactly one xziel.package.json");
            }

            JSONObject manifest = parseJson(readAll(zip.getInputStream(manifestEntry)));
            JSONObject summary = object(manifest, "summary");
            if (!summary.optBoolean("strictReady", false)) {
                throw new IOException("XZIEL package inventory is not strictReady");
            }

            JSONObject packageMeta = object(manifest, "package");
            requireString(packageMeta, "format", "xziel_xzp_v1");
            requireString(packageMeta, "payloadRoot", "payload/");
            if (!packageMeta.optBoolean("sourceBytesPreserved", false)) {
                throw new IOException("XZIEL package sourceBytesPreserved is false");
            }
            if (!packageMeta.optBoolean("runtimePromotionRequired", false)) {
                throw new IOException(
                    "XZIEL package does not require runtime promotion");
            }

            JSONObject mapMeta = object(manifest, "map");
            String mapId = mapMeta.optString("mapId", "");
            if (!mapId.matches("^[a-z0-9][a-z0-9_]{0,62}$")) {
                throw new IOException("Invalid XZIEL mapId");
            }
            String entryWorld = normalize(mapMeta.optString("entryWorld", ""));
            if (!entryWorld.equals("maps/" + mapId + ".bsp")) {
                throw new IOException(
                    "entryWorld must equal maps/<mapId>.bsp");
            }
            requireString(mapMeta, "gameMode", "round_based_zombies");
            requireString(
                mapMeta,
                "contentContract",
                "xziel_map_content_contract_v1");
            if (!mapMeta.optBoolean("serverAuthoritative", false)) {
                throw new IOException("Map must be server authoritative");
            }
            int maxPlayers = mapMeta.optInt("maxPlayers", 0);
            if (maxPlayers < 1 || maxPlayers > 4) {
                throw new IOException("Map maxPlayers must be 1..4");
            }

            JSONObject runtimeSummary = object(manifest, "runtime");
            requireString(runtimeSummary, "format", RUNTIME_FORMAT);
            requireString(runtimeSummary, "manifestPath", RUNTIME_MANIFEST);
            if (!runtimeSummary.optBoolean("runtimeReady", false)) {
                throw new IOException("XZIEL runtime promotion is not ready");
            }
            if (!runtimeSummary.optBoolean("sourceInventoryStrictReady", false)) {
                throw new IOException(
                    "XZIEL runtime promotion did not attest strict inventory");
            }
            if (runtimeSummary.optInt("requiredFamilyCount", -1)
                    != REQUIRED_FAMILY_COUNT
                    || runtimeSummary.optInt("readyFamilyCount", -1)
                    != REQUIRED_FAMILY_COUNT) {
                throw new IOException("XZIEL runtime family count mismatch");
            }
            validateRuntimeGlobals(
                object(runtimeSummary, "globalRequirements"),
                "runtime summary");

            String runtimeManifestSha = runtimeSummary
                .optString("manifestSha256", "")
                .toLowerCase(Locale.US);
            if (!runtimeManifestSha.matches("^[0-9a-f]{64}$")) {
                throw new IOException("Invalid runtime manifest SHA-256");
            }

            JSONArray files = manifest.optJSONArray("files");
            if (files == null || files.length() == 0) {
                throw new IOException("XZIEL package file inventory is empty");
            }

            Map<String, ExpectedFile> expected = new HashMap<>();
            long totalExpectedBytes = 0L;
            for (int i = 0; i < files.length(); ++i) {
                JSONObject row = files.optJSONObject(i);
                if (row == null) {
                    throw new IOException("Invalid XZIEL file inventory row");
                }
                String rel = normalize(row.optString("path", ""));
                validateSafeRelativePath(rel);
                if (rel.startsWith("payload/")) {
                    throw new IOException("Inventory paths must be payload-relative");
                }

                long bytes = row.optLong("bytes", -1L);
                String digest = row.optString("sha256", "")
                    .toLowerCase(Locale.US);
                if (bytes < 0L || !digest.matches("^[0-9a-f]{64}$")) {
                    throw new IOException("Invalid file metadata for " + rel);
                }

                String archiveName = "payload/" + rel;
                if (GENERATED_BOOT_PLAN.equals(rel)
                        || GENERATED_PACKAGE_META.equals(rel)) {
                    throw new IOException(
                        "Payload uses reserved generated runtime path: " + rel);
                }
                if (expected.put(
                        archiveName,
                        new ExpectedFile(rel, bytes, digest)) != null) {
                    throw new IOException("Duplicate inventory path: " + rel);
                }
                totalExpectedBytes += bytes;
            }

            if (!expected.containsKey("payload/" + entryWorld)) {
                throw new IOException("entryWorld is missing from payload inventory");
            }

            ExpectedFile runtimeExpected =
                expected.get("payload/" + RUNTIME_MANIFEST);
            if (runtimeExpected == null) {
                throw new IOException(
                    "runtime manifest is missing from payload inventory");
            }
            if (!runtimeManifestSha.equals(runtimeExpected.sha256)) {
                throw new IOException(
                    "runtime manifest SHA does not match payload inventory");
            }

            long declaredTotal = summary.optLong("totalBytes", -1L);
            if (declaredTotal != totalExpectedBytes) {
                throw new IOException("XZIEL totalBytes mismatch");
            }

            Set<String> actualPayload = new HashSet<>();
            for (String name : zipNames) {
                if (!name.startsWith("payload/") || name.endsWith("/")) {
                    continue;
                }
                actualPayload.add(name);
            }
            if (!actualPayload.equals(expected.keySet())) {
                Set<String> missing = new HashSet<>(expected.keySet());
                missing.removeAll(actualPayload);
                Set<String> extra = new HashSet<>(actualPayload);
                extra.removeAll(expected.keySet());
                throw new IOException(
                    "XZIEL payload membership mismatch missing="
                    + missing + " extra=" + extra);
            }

            ZipEntry runtimeEntry =
                zip.getEntry("payload/" + RUNTIME_MANIFEST);
            if (runtimeEntry == null || runtimeEntry.isDirectory()) {
                throw new IOException("Missing runtime manifest payload member");
            }
            JSONObject runtimeManifest = parseJson(
                readAll(zip.getInputStream(runtimeEntry)));
            validateRuntimeManifest(
                runtimeManifest,
                mapId,
                entryWorld,
                expected);

            File importRoot = new File(dataRoot, "xziel-import");
            if (!importRoot.mkdirs() && !importRoot.isDirectory()) {
                throw new IOException("Could not create " + importRoot);
            }

            File target = new File(importRoot, mapId);
            File temp = new File(importRoot, "." + mapId + ".installing");
            deleteTree(temp);
            if (!temp.mkdirs() && !temp.isDirectory()) {
                throw new IOException("Could not create " + temp);
            }

            String canonicalTempRoot = temp.getCanonicalPath() + File.separator;
            try {
                for (Map.Entry<String, ExpectedFile> item : expected.entrySet()) {
                    String archiveName = item.getKey();
                    ExpectedFile meta = item.getValue();
                    ZipEntry payloadEntry = zip.getEntry(archiveName);
                    if (payloadEntry == null || payloadEntry.isDirectory()) {
                        throw new IOException("Missing payload member " + archiveName);
                    }

                    File out = new File(temp, meta.path);
                    String canonicalOut = out.getCanonicalPath();
                    if (!canonicalOut.startsWith(canonicalTempRoot)) {
                        throw new IOException(
                            "Blocked invalid extraction path " + meta.path);
                    }

                    File parent = out.getParentFile();
                    if (parent != null
                            && !parent.mkdirs()
                            && !parent.isDirectory()) {
                        throw new IOException("Could not create " + parent);
                    }

                    MessageDigest digest = sha256Digest();
                    long written = 0L;
                    try (InputStream input =
                             new BufferedInputStream(zip.getInputStream(payloadEntry));
                         BufferedOutputStream output =
                             new BufferedOutputStream(new FileOutputStream(out))) {
                        byte[] buffer = new byte[64 * 1024];
                        int count;
                        while ((count = input.read(buffer)) != -1) {
                            digest.update(buffer, 0, count);
                            output.write(buffer, 0, count);
                            written += count;
                        }
                    }

                    if (written != meta.bytes) {
                        throw new IOException("Size mismatch for " + meta.path);
                    }
                    String actualSha = hex(digest.digest());
                    if (!actualSha.equals(meta.sha256)) {
                        throw new IOException("SHA-256 mismatch for " + meta.path);
                    }
                }

                writeBootPlan(temp, runtimeManifest);

                File installedManifest = new File(temp, GENERATED_PACKAGE_META);
                try (BufferedOutputStream output =
                         new BufferedOutputStream(
                             new FileOutputStream(installedManifest))) {
                    output.write(
                        manifest.toString().getBytes(StandardCharsets.UTF_8));
                    output.write('\n');
                }

                deleteTree(target);
                if (!temp.renameTo(target)) {
                    throw new IOException(
                        "Could not atomically install XZIEL map " + mapId);
                }
            } catch (IOException error) {
                deleteTree(temp);
                throw error;
            }

            return new InstalledMap(
                mapId,
                entryWorld,
                "xziel-import/" + mapId,
                target);
        }
    }

    private static int bootPhase(String familyId) throws IOException {
        switch (familyId) {
        case "world_geometry":
        case "collision":
        case "navigation_pathing":
            return 1;

        case "materials_textures":
        case "static_models_props":
        case "lighting_postfx":
        case "vfx_particles":
            return 2;

        case "animated_models_rigs":
        case "animations":
            return 3;

        case "weapons_equipment":
        case "pack_a_punch_variants":
        case "gameplay_scripts":
        case "interactables":
        case "perks_wunderfizz":
        case "powerups":
        case "gobblegum":
        case "mystery_box":
        case "spawns_rounds_ai":
            return 4;

        case "audio_sfx":
        case "ambient_music_vo":
            return 5;

        case "hud_ui_prompts":
        case "multiplayer_replication":
            return 6;

        case "platform_packaging":
        case "soak_release_quality":
            return 7;

        default:
            throw new IOException("Unknown boot family " + familyId);
        }
    }

    private static void writeBootPlan(
            File root,
            JSONObject runtime) throws IOException {
        JSONArray families = runtime.optJSONArray("families");
        if (families == null
                || families.length() != REQUIRED_FAMILY_COUNT) {
            throw new IOException("Cannot generate package boot plan");
        }

        Map<String, JSONObject> byId = new HashMap<>();
        int artifactTotal = 0;
        for (int i = 0; i < families.length(); ++i) {
            JSONObject family = families.optJSONObject(i);
            if (family == null) {
                throw new IOException("Invalid runtime family during boot-plan build");
            }
            String familyId = family.optString("id", "");
            if (!REQUIRED_RUNTIME_FAMILIES.contains(familyId)
                    || byId.put(familyId, family) != null) {
                throw new IOException(
                    "Invalid/duplicate boot family " + familyId);
            }
            JSONArray artifacts = family.optJSONArray("runtimeArtifacts");
            if (artifacts == null || artifacts.length() == 0) {
                throw new IOException(
                    "No runtime artifacts for boot family " + familyId);
            }
            artifactTotal += artifacts.length();
        }

        StringBuilder plan = new StringBuilder();
        plan.append("XZBP1|")
            .append(REQUIRED_FAMILY_COUNT)
            .append('|')
            .append(artifactTotal)
            .append('\n');

        for (String familyId : RUNTIME_FAMILY_ORDER) {
            JSONObject family = byId.get(familyId);
            if (family == null) {
                throw new IOException(
                    "Missing boot family " + familyId);
            }
            JSONArray artifacts = family.optJSONArray("runtimeArtifacts");
            if (artifacts == null || artifacts.length() == 0) {
                throw new IOException(
                    "No runtime artifacts for boot family " + familyId);
            }
            plan.append("F|")
                .append(bootPhase(familyId))
                .append('|')
                .append(familyId)
                .append('|')
                .append(artifacts.length())
                .append('\n');

            for (int j = 0; j < artifacts.length(); ++j) {
                String artifact = normalize(artifacts.optString(j, ""));
                validateSafeRelativePath(artifact);
                if (artifact.indexOf('|') >= 0
                        || artifact.indexOf('\n') >= 0
                        || artifact.indexOf('\r') >= 0) {
                    throw new IOException(
                        "Boot artifact contains reserved delimiter: " + artifact);
                }
                plan.append("A|")
                    .append(familyId)
                    .append('|')
                    .append(artifact)
                    .append('\n');
            }
        }

        File bootPlan = new File(root, GENERATED_BOOT_PLAN);
        try (BufferedOutputStream output =
                 new BufferedOutputStream(new FileOutputStream(bootPlan))) {
            output.write(plan.toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private static void validateRuntimeManifest(
            JSONObject runtime,
            String mapId,
            String entryWorld,
            Map<String, ExpectedFile> expected) throws IOException {
        if (runtime.optInt("schemaVersion", -1) != 1) {
            throw new IOException("runtime schemaVersion must be 1");
        }
        requireString(runtime, "format", RUNTIME_FORMAT);
        requireString(runtime, "mapId", mapId);
        requireString(
            runtime,
            "contentContract",
            "xziel_map_content_contract_v1");
        if (!runtime.optBoolean("sourceInventoryStrictReady", false)) {
            throw new IOException(
                "runtime manifest sourceInventoryStrictReady is false");
        }

        validateRuntimeGlobals(
            object(runtime, "globalRequirements"),
            "runtime manifest");

        JSONArray families = runtime.optJSONArray("families");
        if (families == null
                || families.length() != REQUIRED_FAMILY_COUNT) {
            throw new IOException(
                "runtime manifest must contain exactly "
                + REQUIRED_FAMILY_COUNT + " families");
        }

        Set<String> seenFamilies = new HashSet<>();
        boolean worldBindsEntryWorld = false;

        for (int i = 0; i < families.length(); ++i) {
            JSONObject family = families.optJSONObject(i);
            if (family == null) {
                throw new IOException("Invalid runtime family row");
            }

            String familyId = family.optString("id", "");
            if (!REQUIRED_RUNTIME_FAMILIES.contains(familyId)) {
                throw new IOException(
                    "Unknown runtime family: " + familyId);
            }
            if (!seenFamilies.add(familyId)) {
                throw new IOException(
                    "Duplicate runtime family: " + familyId);
            }
            requireString(family, "state", "ready");

            JSONArray artifacts = family.optJSONArray("runtimeArtifacts");
            if (artifacts == null || artifacts.length() == 0) {
                throw new IOException(
                    "runtimeArtifacts missing for " + familyId);
            }
            for (int j = 0; j < artifacts.length(); ++j) {
                String artifact = normalize(artifacts.optString(j, ""));
                validateSafeRelativePath(artifact);
                if (RUNTIME_MANIFEST.equals(artifact)) {
                    throw new IOException(
                        familyId + " cannot self-reference "
                        + RUNTIME_MANIFEST);
                }
                if (!expected.containsKey("payload/" + artifact)) {
                    throw new IOException(
                        "Missing runtime artifact for "
                        + familyId + ": " + artifact);
                }
                if ("world_geometry".equals(familyId)
                        && entryWorld.equals(artifact)) {
                    worldBindsEntryWorld = true;
                }
            }

            JSONArray evidence = family.optJSONArray("validationEvidence");
            if (evidence == null || evidence.length() == 0) {
                throw new IOException(
                    "validationEvidence missing for " + familyId);
            }
            for (int j = 0; j < evidence.length(); ++j) {
                String value = evidence.optString(j, "");
                if (value.trim().isEmpty()) {
                    throw new IOException(
                        "Invalid validationEvidence for " + familyId);
                }
            }
        }

        if (!seenFamilies.equals(REQUIRED_RUNTIME_FAMILIES)) {
            Set<String> missing =
                new HashSet<>(REQUIRED_RUNTIME_FAMILIES);
            missing.removeAll(seenFamilies);
            throw new IOException(
                "runtime family coverage mismatch missing=" + missing);
        }
        if (!worldBindsEntryWorld) {
            throw new IOException(
                "world_geometry must bind descriptor entryWorld");
        }
    }

    private static void validateRuntimeGlobals(
            JSONObject globals,
            String label) throws IOException {
        for (String key : REQUIRED_RUNTIME_GLOBALS) {
            if (!globals.optBoolean(key, false)) {
                throw new IOException(
                    label + " global requirement not ready: " + key);
            }
        }
    }

    private static JSONObject parseJson(byte[] bytes) throws IOException {
        try {
            return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
        } catch (JSONException error) {
            throw new IOException("Invalid XZIEL JSON", error);
        }
    }

    private static JSONObject object(JSONObject parent, String name)
            throws IOException {
        JSONObject value = parent.optJSONObject(name);
        if (value == null) {
            throw new IOException("Missing JSON object: " + name);
        }
        return value;
    }

    private static void requireString(
            JSONObject object,
            String key,
            String expected) throws IOException {
        if (!expected.equals(object.optString(key, ""))) {
            throw new IOException("XZIEL manifest " + key + " mismatch");
        }
    }

    private static byte[] readAll(InputStream input) throws IOException {
        try (InputStream in = new BufferedInputStream(input);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = in.read(buffer)) != -1) {
                out.write(buffer, 0, count);
            }
            return out.toByteArray();
        }
    }

    private static String normalize(String path) {
        String result = path == null ? "" : path.replace('\\', '/');
        while (result.startsWith("./")) {
            result = result.substring(2);
        }
        while (result.contains("//")) {
            result = result.replace("//", "/");
        }
        return result;
    }

    private static void validateSafeRelativePath(String path)
            throws IOException {
        if (path == null
                || path.isEmpty()
                || path.startsWith("/")
                || path.contains("/../")
                || path.startsWith("../")
                || path.endsWith("/..")
                || path.indexOf('\0') >= 0) {
            throw new IOException("Unsafe XZIEL package path: " + path);
        }
    }

    private static MessageDigest sha256Digest() throws IOException {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException error) {
            throw new IOException("SHA-256 unavailable", error);
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            out.append(String.format(Locale.US, "%02x", value & 0xff));
        }
        return out.toString();
    }

    private static void deleteTree(File file) throws IOException {
        if (file == null || !file.exists()) {
            return;
        }
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteTree(child);
                }
            }
        }
        if (!file.delete()) {
            throw new IOException("Could not delete " + file);
        }
    }
}
