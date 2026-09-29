package org.libsdl.app;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.graphics.Color;
import android.os.Bundle;
import android.os.StatFs;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Minimal XZIEL bootstrap.
 *
 * A self-contained playtest APK may carry assets/xziel-nacht-vfs.zip.
 * The archive is extracted exactly once into the app-private XZIEL VFS,
 * then the native SDL runtime is launched. Engine-only CI APKs simply
 * fall through when the bundled archive is absent.
 */
public final class XzielBootstrapActivity extends Activity {
    private static final String NACHT_ASSET = "xziel-nacht-vfs.zip";
    private static final String NACHT_SCENE =
        "xziel/maps/xziel_nacht_bo3/scene.xzsc";
    private static final String NACHT_MAP_ROOT =
        "xziel/maps/xziel_nacht_bo3";
    private static final String COMPLETE_MARKER =
        ".xziel-nacht-vfs-complete-v1";
    private static final String STAGING_DIR =
        ".xziel-nacht-staging";
    private static final long MIN_FREE_BYTES =
        2_700_000_000L;
    private static final String TAG = "XZIEL-BOOT";

    private final ExecutorService executor =
        Executors.newSingleThreadExecutor();
    private TextView statusView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setRequestedOrientation(
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
        applyImmersiveMode();
        buildSplash();

        if (isContentReady()) {
            Log.i(TAG, "XZIEL_BOOT_CONTENT_READY");
            launchXziel();
            return;
        }

        executor.execute(() -> {
            boolean bundled = false;
            try {
                try (InputStream ignored =
                         getAssets().open(NACHT_ASSET)) {
                    bundled = true;
                } catch (IOException missing) {
                    bundled = false;
                }

                if (bundled) {
                    setStatus("XZIEL\nPreparing Nacht...");
                    extractBundledVfs();
                }

                runOnUiThread(this::launchXziel);
            } catch (Exception error) {
                Log.e(TAG, "XZIEL_BOOT_CONTENT_SETUP_FAILED", error);
                runOnUiThread(() -> {
                    if (statusView != null) {
                        statusView.setText(
                            "XZIEL\nContent setup failed");
                    }
                });
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        applyImmersiveMode();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void buildSplash() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        statusView = new TextView(this);
        statusView.setText("XZIEL");
        statusView.setTextColor(Color.WHITE);
        statusView.setTextSize(26.0f);
        statusView.setGravity(Gravity.CENTER);

        FrameLayout.LayoutParams params =
            new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT);
        root.addView(statusView, params);
        setContentView(root);
    }

    private void setStatus(String value) {
        runOnUiThread(() -> {
            if (statusView != null)
                statusView.setText(value);
        });
    }

    private void extractBundledVfs() throws IOException {
        File filesRoot = getFilesDir();
        StatFs stat = new StatFs(filesRoot.getAbsolutePath());
        long available = stat.getAvailableBytes();
        Log.i(
            TAG,
            "XZIEL_BOOT_STORAGE available=" + available
                + " required=" + MIN_FREE_BYTES);
        if (available < MIN_FREE_BYTES) {
            throw new IOException(
                "Not enough free storage for Nacht content: "
                    + available + " bytes available");
        }

        File stagingRoot = new File(filesRoot, STAGING_DIR);
        deleteRecursively(stagingRoot);
        if (!stagingRoot.mkdirs() && !stagingRoot.isDirectory()) {
            throw new IOException(
                "Could not create staging directory");
        }

        String canonicalRoot =
            stagingRoot.getCanonicalPath() + File.separator;
        byte[] buffer = new byte[256 * 1024];
        long extractedBytes = 0L;
        long nextProgress = 128L * 1024L * 1024L;

        Log.i(TAG, "XZIEL_BOOT_EXTRACT_BEGIN");

        try (ZipInputStream zip =
                 new ZipInputStream(
                     new BufferedInputStream(
                         getAssets().open(NACHT_ASSET),
                         256 * 1024))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                String name =
                    entry.getName().replace('\\', '/');
                if (name.startsWith("/") ||
                    name.contains("../") ||
                    name.indexOf('\0') >= 0) {
                    throw new IOException(
                        "Unsafe bundled XZIEL path");
                }

                File output = new File(stagingRoot, name);
                String canonicalOutput =
                    output.getCanonicalPath();
                if (!canonicalOutput.startsWith(canonicalRoot)) {
                    throw new IOException(
                        "Bundled XZIEL path escaped sandbox");
                }

                if (entry.isDirectory()) {
                    if (!output.mkdirs() &&
                        !output.isDirectory()) {
                        throw new IOException(
                            "Could not create " + output);
                    }
                    zip.closeEntry();
                    continue;
                }

                File parent = output.getParentFile();
                if (parent != null &&
                    !parent.mkdirs() &&
                    !parent.isDirectory()) {
                    throw new IOException(
                        "Could not create " + parent);
                }

                try (BufferedOutputStream out =
                         new BufferedOutputStream(
                             new FileOutputStream(output),
                             256 * 1024)) {
                    int count;
                    while ((count = zip.read(buffer)) != -1) {
                        out.write(buffer, 0, count);
                        extractedBytes += count;
                        if (extractedBytes >= nextProgress) {
                            Log.i(
                                TAG,
                                "XZIEL_BOOT_EXTRACT_PROGRESS bytes="
                                    + extractedBytes);
                            nextProgress +=
                                128L * 1024L * 1024L;
                        }
                    }
                }
                zip.closeEntry();
            }
        } catch (IOException error) {
            deleteRecursively(stagingRoot);
            throw error;
        }

        File stagedMap = new File(stagingRoot, NACHT_MAP_ROOT);
        validateExtractedContent(stagedMap);

        File stagedXziel = new File(stagingRoot, "xziel");
        File liveXziel = new File(filesRoot, "xziel");
        deleteRecursively(liveXziel);
        if (!stagedXziel.renameTo(liveXziel)) {
            deleteRecursively(stagingRoot);
            throw new IOException(
                "Could not activate extracted XZIEL VFS");
        }
        deleteRecursively(stagingRoot);

        File marker = new File(filesRoot, COMPLETE_MARKER);
        try (FileOutputStream out =
                 new FileOutputStream(marker, false)) {
            out.write(
                ("ready\nbytes=" + extractedBytes + "\n")
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8));
            out.getFD().sync();
        }

        Log.i(
            TAG,
            "XZIEL_BOOT_EXTRACT_COMPLETE bytes="
                + extractedBytes);
    }

    private boolean isContentReady() {
        File marker =
            new File(getFilesDir(), COMPLETE_MARKER);
        if (!marker.isFile())
            return false;

        try {
            validateExtractedContent(
                new File(getFilesDir(), NACHT_MAP_ROOT));
            return true;
        } catch (IOException invalid) {
            Log.w(
                TAG,
                "XZIEL_BOOT_MARKER_INVALID",
                invalid);
            if (!marker.delete()) {
                Log.w(
                    TAG,
                    "Could not delete invalid marker");
            }
            return false;
        }
    }

    private void validateExtractedContent(File mapRoot)
        throws IOException {
        String[] required = {
            "scene.xzsc",
            "materials.xzmt",
            "materials.xzpb",
            "materials.xzmn",
            "environment.xzen",
            "fog.xzfg",
            "reflection.xzrc",
            "lightmaps.xzlt",
            "lightmap-bindings.xzlb"
        };
        for (String name : required) {
            File file = new File(mapRoot, name);
            if (!file.isFile() || file.length() <= 0L) {
                throw new IOException(
                    "Bundled Nacht file missing: " + name);
            }
        }

        File meshDir = new File(mapRoot, "meshes");
        File[] meshes = meshDir.listFiles(
            (dir, name) -> name.endsWith(".xzm"));
        if (meshes == null || meshes.length != 492) {
            throw new IOException(
                "Bundled Nacht mesh count mismatch: "
                    + (meshes == null ? 0 : meshes.length));
        }
    }

    private static void deleteRecursively(File file)
        throws IOException {
        if (file == null || !file.exists())
            return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children)
                    deleteRecursively(child);
            }
        }
        if (!file.delete() && file.exists()) {
            throw new IOException(
                "Could not delete " + file);
        }
    }

    private void launchXziel() {
        Intent intent =
            new Intent(this, XzielActivity.class);
        intent.putExtra("xziel_map", "xziel_nacht_bo3");
        startActivity(intent);
        finish();
    }

    private void applyImmersiveMode() {
        getWindow().addFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController controller =
                getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(
                    WindowInsets.Type.statusBars() |
                    WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                    WindowInsetsController.
                        BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
                View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }
}
