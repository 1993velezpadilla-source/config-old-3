package dev.ctw.capture;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.net.Uri;
import android.os.Bundle;
import android.text.method.ScrollingMovementMethod;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.documentfile.provider.DocumentFile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class MainActivity extends Activity {
    private static final int REQUEST_EXPORT_TREE = 1001;

    private static final String TARGET_PACKAGE = "com.rockstargames.gtactw";
    private static final String TARGET_VERSION_NAME = "4.4.243";
    private static final long TARGET_VERSION_CODE = 4277603L;
    private static final String TARGET_CERT_SHA256 =
            "e8c76284d4d652f1881525853ce0aa9fe82b89e276f6204f1a7a53aef67fce19";

    private TextView statusView;
    private Button exportButton;
    private Button shareLibGameButton;
    private CaptureInfo captureInfo;
    private Uri lastLibGameUri;

    private static final class CaptureInfo {
        boolean installed;
        boolean versionMatch;
        boolean versionCodeMatch;
        boolean certificateMatch;
        String versionName = "";
        long versionCode;
        final List<String> signerSha256 = new ArrayList<>();
        final List<String> apkPaths = new ArrayList<>();

        boolean exactTarget() {
            return installed && versionMatch && versionCodeMatch && certificateMatch;
        }
    }

    private static final class CopyResult {
        final long bytes;
        final String sha256;

        CopyResult(long bytes, String sha256) {
            this.bytes = bytes;
            this.sha256 = sha256;
        }
    }

    private static final class ArtifactResult {
        final String logicalName;
        final String sourceApk;
        final String zipEntry;
        final long bytes;
        final String sha256;
        final Uri documentUri;

        ArtifactResult(
                String logicalName,
                String sourceApk,
                String zipEntry,
                long bytes,
                String sha256,
                Uri documentUri
        ) {
            this.logicalName = logicalName;
            this.sourceApk = sourceApk;
            this.zipEntry = zipEntry;
            this.bytes = bytes;
            this.sha256 = sha256;
            this.documentUri = documentUri;
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        root.setPadding(pad, pad, pad, pad);
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        TextView title = new TextView(this);
        title.setText("CTW Capture");
        title.setTextSize(26f);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText(
                "Exports your installed GTA Chinatown Wars APK set and the " +
                "ARM64 analysis payload without root or ADB."
        );
        subtitle.setTextSize(15f);
        subtitle.setPadding(0, dp(8), 0, dp(18));
        root.addView(subtitle);

        statusView = new TextView(this);
        statusView.setTextSize(14f);
        statusView.setTextIsSelectable(true);
        statusView.setMovementMethod(new ScrollingMovementMethod());
        root.addView(statusView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        exportButton = new Button(this);
        exportButton.setText("EXPORT INSTALLATION FOR ANALYSIS");
        exportButton.setOnClickListener(v -> chooseExportFolder());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        buttonParams.topMargin = dp(18);
        root.addView(exportButton, buttonParams);

        shareLibGameButton = new Button(this);
        shareLibGameButton.setText("SHARE libGame.so");
        shareLibGameButton.setEnabled(false);
        shareLibGameButton.setOnClickListener(v -> shareLastLibGame());
        LinearLayout.LayoutParams shareParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        shareParams.topMargin = dp(8);
        root.addView(shareLibGameButton, shareParams);

        TextView note = new TextView(this);
        note.setText(
                "\nThis app only reads com.rockstargames.gtactw. It does not " +
                "request broad app visibility and does not modify the installed game."
        );
        note.setTextSize(12f);
        root.addView(note);

        setContentView(scroll);
        refreshTargetInfo();
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }

    private void refreshTargetInfo() {
        captureInfo = inspectTarget();
        exportButton.setEnabled(captureInfo.installed);

        if (!captureInfo.installed) {
            statusView.setText(
                    "GTA Chinatown Wars is not visible as an installed package.\n\n" +
                    "Target package: " + TARGET_PACKAGE
            );
            return;
        }

        StringBuilder sb = new StringBuilder();
        sb.append("Package: ").append(TARGET_PACKAGE).append('\n');
        sb.append("Version: ").append(captureInfo.versionName)
                .append("  (target ").append(TARGET_VERSION_NAME).append(")\n");
        sb.append("Version code: ").append(captureInfo.versionCode)
                .append("  (target ").append(TARGET_VERSION_CODE).append(")\n");
        sb.append("APK parts found: ").append(captureInfo.apkPaths.size()).append('\n');
        sb.append("Certificate SHA-256 match: ")
                .append(captureInfo.certificateMatch ? "YES" : "NO")
                .append('\n');
        sb.append("Exact 4.4.243 target: ")
                .append(captureInfo.exactTarget() ? "YES" : "NO")
                .append("\n\n");

        if (captureInfo.exactTarget()) {
            sb.append("Ready. Choose a folder and CTW Capture will export the APK set, ")
                    .append("libGame.so, game.pak, dxt.bin, and a SHA-256 manifest.");
        } else {
            sb.append("The installation can still be exported for analysis, but the ")
                    .append("mod pipeline must remain fail-closed until the identity ")
                    .append("matches the verified 4.4.243 profile.");
        }

        statusView.setText(sb.toString());
    }

    private CaptureInfo inspectTarget() {
        CaptureInfo out = new CaptureInfo();
        PackageManager pm = getPackageManager();

        try {
            PackageInfo info = pm.getPackageInfo(
                    TARGET_PACKAGE,
                    PackageManager.GET_SIGNING_CERTIFICATES
            );
            out.installed = true;
            out.versionName = info.versionName == null ? "" : info.versionName;
            out.versionCode = info.getLongVersionCode();
            out.versionMatch = TARGET_VERSION_NAME.equals(out.versionName);
            out.versionCodeMatch = TARGET_VERSION_CODE == out.versionCode;

            SigningInfo signingInfo = info.signingInfo;
            if (signingInfo != null) {
                Signature[] signatures = signingInfo.hasMultipleSigners()
                        ? signingInfo.getApkContentsSigners()
                        : signingInfo.getSigningCertificateHistory();
                if (signatures != null) {
                    for (Signature signature : signatures) {
                        String digest = sha256Bytes(signature.toByteArray());
                        out.signerSha256.add(digest);
                        if (TARGET_CERT_SHA256.equals(digest)) {
                            out.certificateMatch = true;
                        }
                    }
                }
            }

            ApplicationInfo app = info.applicationInfo;
            Set<String> unique = new HashSet<>();
            if (app != null && app.sourceDir != null && unique.add(app.sourceDir)) {
                out.apkPaths.add(app.sourceDir);
            }
            if (app != null && app.splitSourceDirs != null) {
                for (String path : app.splitSourceDirs) {
                    if (path != null && unique.add(path)) {
                        out.apkPaths.add(path);
                    }
                }
            }
        } catch (PackageManager.NameNotFoundException ignored) {
            out.installed = false;
        }

        return out;
    }

    private void chooseExportFolder() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION |
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
                Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION |
                Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
        );
        startActivityForResult(intent, REQUEST_EXPORT_TREE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_EXPORT_TREE || resultCode != RESULT_OK || data == null) {
            return;
        }

        Uri treeUri = data.getData();
        if (treeUri == null) {
            statusView.setText("Export cancelled: Android returned no destination folder.");
            return;
        }

        int flags = data.getFlags() & (
                Intent.FLAG_GRANT_READ_URI_PERMISSION |
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        );
        try {
            getContentResolver().takePersistableUriPermission(treeUri, flags);
        } catch (SecurityException ignored) {
            // The active grant is still enough for this export session.
        }

        exportButton.setEnabled(false);
        shareLibGameButton.setEnabled(false);
        lastLibGameUri = null;
        statusView.setText("Exporting CTW installation…");
        new Thread(() -> exportCapture(treeUri), "ctw-capture-export").start();
    }

    private void exportCapture(Uri treeUri) {
        try {
            CaptureInfo info = inspectTarget();
            if (!info.installed) {
                throw new IllegalStateException("GTA Chinatown Wars is no longer installed.");
            }

            DocumentFile tree = DocumentFile.fromTreeUri(this, treeUri);
            if (tree == null || !tree.canWrite()) {
                throw new IllegalStateException("Selected folder is not writable.");
            }

            String folderName = "CTW_" + sanitize(info.versionName) + "_capture_" +
                    System.currentTimeMillis();
            DocumentFile captureDir = tree.createDirectory(folderName);
            if (captureDir == null) {
                throw new IllegalStateException("Could not create capture folder.");
            }

            JSONArray apkManifest = new JSONArray();
            List<ArtifactResult> artifacts = new ArrayList<>();
            Set<String> extracted = new HashSet<>();

            int index = 0;
            for (String sourcePath : info.apkPaths) {
                File source = new File(sourcePath);
                String baseName = source.getName();
                if (baseName == null || baseName.isEmpty()) {
                    baseName = index == 0 ? "base.apk" : "split_" + index + ".apk";
                }

                DocumentFile dst = captureDir.createFile(
                        "application/vnd.android.package-archive",
                        baseName
                );
                if (dst == null) {
                    throw new IllegalStateException("Could not create " + baseName);
                }

                CopyResult copied;
                try (InputStream in = new BufferedInputStream(new FileInputStream(source))) {
                    copied = copyToDocument(in, dst);
                }

                JSONObject apk = new JSONObject();
                apk.put("name", baseName);
                apk.put("source_path", sourcePath);
                apk.put("size_bytes", copied.bytes);
                apk.put("sha256", copied.sha256);
                apkManifest.put(apk);

                scanArtifacts(source, captureDir, artifacts, extracted);
                index++;
            }

            JSONObject manifest = new JSONObject();
            manifest.put("schema", 1);
            manifest.put("package", TARGET_PACKAGE);
            manifest.put("version_name", info.versionName);
            manifest.put("version_code", info.versionCode);
            manifest.put("target_version_name", TARGET_VERSION_NAME);
            manifest.put("target_version_code", TARGET_VERSION_CODE);
            manifest.put("version_match", info.versionMatch);
            manifest.put("version_code_match", info.versionCodeMatch);
            manifest.put("certificate_match", info.certificateMatch);
            manifest.put("exact_target_match", info.exactTarget());

            JSONArray certs = new JSONArray();
            for (String cert : info.signerSha256) {
                certs.put(cert);
            }
            manifest.put("signer_sha256", certs);
            manifest.put("expected_signer_sha256", TARGET_CERT_SHA256);
            manifest.put("apks", apkManifest);

            JSONArray artifactManifest = new JSONArray();
            for (ArtifactResult artifact : artifacts) {
                JSONObject item = new JSONObject();
                item.put("name", artifact.logicalName);
                item.put("source_apk", artifact.sourceApk);
                item.put("zip_entry", artifact.zipEntry);
                item.put("size_bytes", artifact.bytes);
                item.put("sha256", artifact.sha256);
                artifactManifest.put(item);
            }
            manifest.put("artifacts", artifactManifest);

            DocumentFile manifestFile = captureDir.createFile(
                    "application/json",
                    "capture_manifest.json"
            );
            if (manifestFile == null) {
                throw new IllegalStateException("Could not create capture_manifest.json");
            }
            byte[] manifestBytes = (manifest.toString(2) + "\n").getBytes(StandardCharsets.UTF_8);
            try (InputStream in = new java.io.ByteArrayInputStream(manifestBytes)) {
                copyToDocument(in, manifestFile);
            }

            Uri libGameUri = null;
            for (ArtifactResult artifact : artifacts) {
                if ("libGame.so".equals(artifact.logicalName)) {
                    libGameUri = artifact.documentUri;
                    break;
                }
            }
            final Uri shareUri = libGameUri;

            String result =
                    "CTW capture complete.\n\n" +
                    "Exact target match: " + (info.exactTarget() ? "YES" : "NO") + "\n" +
                    "APK parts exported: " + info.apkPaths.size() + "\n" +
                    "Artifacts extracted: " + artifacts.size() + "\n" +
                    "Folder: " + folderName + "\n\n" +
                    artifactSummary(artifacts);

            runOnUiThread(() -> {
                lastLibGameUri = shareUri;
                statusView.setText(result);
                exportButton.setEnabled(true);
                shareLibGameButton.setEnabled(shareUri != null);
            });
        } catch (Throwable error) {
            runOnUiThread(() -> {
                statusView.setText(
                        "Capture failed.\n\n" +
                        error.getClass().getSimpleName() + ": " +
                        (error.getMessage() == null ? "(no message)" : error.getMessage())
                );
                exportButton.setEnabled(true);
                shareLibGameButton.setEnabled(false);
            });
        }
    }

    private void shareLastLibGame() {
        if (lastLibGameUri == null) {
            return;
        }

        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("application/octet-stream");
        send.putExtra(Intent.EXTRA_STREAM, lastLibGameUri);
        send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(Intent.createChooser(send, "Share CTW libGame.so"));
    }

    private void scanArtifacts(
            File apk,
            DocumentFile captureDir,
            List<ArtifactResult> out,
            Set<String> extracted
    ) throws Exception {
        try (ZipFile zip = new ZipFile(apk)) {
            java.util.Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (entry.isDirectory()) {
                    continue;
                }

                String logical = classifyArtifact(entry.getName());
                if (logical == null || extracted.contains(logical)) {
                    continue;
                }

                String mime = "application/octet-stream";
                DocumentFile dst = captureDir.createFile(mime, logical);
                if (dst == null) {
                    throw new IllegalStateException("Could not create extracted " + logical);
                }

                CopyResult copied;
                try (InputStream in = new BufferedInputStream(zip.getInputStream(entry))) {
                    copied = copyToDocument(in, dst);
                }

                out.add(new ArtifactResult(
                        logical,
                        apk.getName(),
                        entry.getName(),
                        copied.bytes,
                        copied.sha256,
                        dst.getUri()
                ));
                extracted.add(logical);
            }
        }
    }

    private static String classifyArtifact(String entryName) {
        String lower = entryName.toLowerCase(Locale.US);
        if (lower.endsWith("/lib/arm64-v8a/libgame.so") ||
                lower.equals("lib/arm64-v8a/libgame.so")) {
            return "libGame.so";
        }
        if (lower.endsWith("/game.pak") || lower.equals("game.pak")) {
            return "game.pak";
        }
        if (lower.endsWith("/dxt.bin") || lower.equals("dxt.bin")) {
            return "dxt.bin";
        }
        return null;
    }

    private CopyResult copyToDocument(InputStream in, DocumentFile dst) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long total = 0;

        try (OutputStream raw = getContentResolver().openOutputStream(dst.getUri(), "w")) {
            if (raw == null) {
                throw new IllegalStateException("Could not open output " + dst.getName());
            }
            try (BufferedOutputStream out = new BufferedOutputStream(raw)) {
                byte[] buffer = new byte[1024 * 1024];
                int count;
                while ((count = in.read(buffer)) >= 0) {
                    if (count == 0) {
                        continue;
                    }
                    out.write(buffer, 0, count);
                    digest.update(buffer, 0, count);
                    total += count;
                }
                out.flush();
            }
        }

        return new CopyResult(total, hex(digest.digest()));
    }

    private static String sha256Bytes(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return hex(digest.digest(data));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            out.append(String.format(Locale.US, "%02x", value & 0xff));
        }
        return out.toString();
    }

    private static String sanitize(String value) {
        if (value == null || value.isEmpty()) {
            return "unknown";
        }
        return value.replaceAll("[^A-Za-z0-9._-]", "_");
    }

    private static String artifactSummary(List<ArtifactResult> artifacts) {
        if (artifacts.isEmpty()) {
            return "No libGame.so/game.pak/dxt.bin entries were found inside the visible APK parts.";
        }

        StringBuilder sb = new StringBuilder("Extracted:\n");
        for (ArtifactResult artifact : artifacts) {
            sb.append("• ").append(artifact.logicalName)
                    .append("  ").append(artifact.bytes).append(" bytes\n");
        }
        return sb.toString();
    }
}
