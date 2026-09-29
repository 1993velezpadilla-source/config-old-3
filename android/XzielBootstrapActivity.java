package org.libsdl.app;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.graphics.Color;
import android.os.Bundle;
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

        if (new File(getFilesDir(), NACHT_SCENE).isFile()) {
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
        File root = getFilesDir();
        String canonicalRoot =
            root.getCanonicalPath() + File.separator;

        byte[] buffer = new byte[1024 * 1024];
        try (ZipInputStream zip =
                 new ZipInputStream(
                     new BufferedInputStream(
                         getAssets().open(NACHT_ASSET),
                         1024 * 1024))) {
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

                File output = new File(root, name);
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
                             1024 * 1024)) {
                    int count;
                    while ((count = zip.read(buffer)) != -1)
                        out.write(buffer, 0, count);
                }
                zip.closeEntry();
            }
        }

        File scene = new File(root, NACHT_SCENE);
        if (!scene.isFile() || scene.length() <= 0L) {
            throw new IOException(
                "Bundled Nacht scene missing after extraction");
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
