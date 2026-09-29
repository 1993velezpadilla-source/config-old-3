#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_winlator_xziel_direct.py <winlator-app-root>")

root = Path(sys.argv[1]).resolve()
app = root / "app"
java = app / "src/main/java/com/winlator"
assets = app / "src/main/assets"
res = app / "src/main/res"

if not java.is_dir():
    raise SystemExit(f"Winlator Java source not found: {java}")

boot_java = r'''package com.winlator;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.winlator.box64.Box64Preset;
import com.winlator.container.AudioDrivers;
import com.winlator.container.Container;
import com.winlator.container.ContainerManager;
import com.winlator.container.DXWrappers;
import com.winlator.container.GraphicsDrivers;
import com.winlator.core.FileUtils;
import com.winlator.core.TarCompressorUtils;
import com.winlator.xenvironment.RootFS;
import com.winlator.xenvironment.RootFSInstaller;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/*
 * XZIEL direct launcher.
 * Uses Winlator's Wine/Box64/X-server stack as an internal compatibility layer.
 * No Winlator container/desktop UI is exposed to the player.
 */
public class XzielBootActivity extends AppCompatActivity {
    private TextView status;
    private static final String GAME_ASSET = "xziel-game.zip";
    private static final String GAME_DIR = "XZIEL";
    private static final String GAME_EXE = "Xziel.exe";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().getDecorView().setSystemUiVisibility(
            android.view.View.SYSTEM_UI_FLAG_FULLSCREEN |
            android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(22f);
        status.setGravity(Gravity.CENTER);
        status.setText("XZIEL\nLoading...");
        root.addView(status, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
        setContentView(root);

        Executors.newSingleThreadExecutor().execute(this::prepareRuntime);
    }

    private void prepareRuntime() {
        try {
            RootFS rootFS = RootFS.find(this);
            if (!rootFS.isValid() || rootFS.getVersion() < RootFSInstaller.LATEST_VERSION) {
                File rootDir = rootFS.getRootDir();
                FileUtils.delete(rootDir);
                rootDir.mkdirs();
                boolean ok = TarCompressorUtils.extract(
                    TarCompressorUtils.Type.ZSTD,
                    this,
                    RootFSInstaller.FILENAME,
                    rootDir
                );
                if (!ok) throw new RuntimeException("runtime extraction failed");
                rootFS.createRFSVersionFile(RootFSInstaller.LATEST_VERSION);
            }

            runOnUiThread(this::ensureContainer);
        }
        catch (Throwable t) {
            fail("XZIEL startup failed\n" + t.getMessage());
        }
    }

    private void ensureContainer() {
        try {
            ContainerManager manager = new ContainerManager(this);
            ArrayList<Container> containers = manager.getContainers();
            if (!containers.isEmpty()) {
                prepareGameAndLaunch(manager, containers.get(0));
                return;
            }

            JSONObject data = new JSONObject();
            data.put("name", "XZIEL");
            data.put("screenSize", "1280x720");
            data.put("envVars", Container.DEFAULT_ENV_VARS);
            // Pixel Fold 1 is Mali-G710: no Turnip dependency. Keep Winlator's
            // generic Vulkan path plus its OpenGL path for this SDL/OpenGL EXE.
            data.put("graphicsDriver", GraphicsDrivers.VORTEK + "," + GraphicsDrivers.GLADIO);
            data.put("dxwrapper", DXWrappers.DXVK);
            data.put("audioDriver", AudioDrivers.ALSA);
            data.put("wincomponents", Container.DEFAULT_WINCOMPONENTS);
            data.put("drives", Container.DEFAULT_DRIVES);
            data.put("hudMode", 0);
            data.put("startupSelection", Container.STARTUP_SELECTION_ESSENTIAL);
            data.put("box64Preset", Box64Preset.DEFAULT);
            data.put("extraData", new JSONObject());

            manager.createContainerAsync(data, (container) -> {
                if (container == null) {
                    fail("XZIEL container setup failed");
                    return;
                }
                prepareGameAndLaunch(manager, container);
            });
        }
        catch (Throwable t) {
            fail("XZIEL setup failed\n" + t.getMessage());
        }
    }

    private void prepareGameAndLaunch(ContainerManager manager, Container container) {
        Executors.newSingleThreadExecutor().execute(() -> {
            try {
                manager.activateContainer(container);
                File gameDir = new File(container.getRootDir(), ".wine/drive_c/" + GAME_DIR);
                File exe = new File(gameDir, GAME_EXE);
                File marker = new File(gameDir, ".xziel-package-ready");

                if (!exe.isFile() || !marker.isFile()) {
                    FileUtils.delete(gameDir);
                    gameDir.mkdirs();
                    extractZipAsset(GAME_ASSET, gameDir);
                    if (!exe.isFile()) throw new RuntimeException("Xziel.exe missing after package extraction");
                    FileUtils.writeString(marker, "XZIEL_DIRECT_PACKAGE_V1\n");
                }

                runOnUiThread(() -> launchGame(container, exe));
            }
            catch (Throwable t) {
                fail("XZIEL game setup failed\n" + t.getMessage());
            }
        });
    }

    private void extractZipAsset(String assetName, File destination) throws Exception {
        String base = destination.getCanonicalPath() + File.separator;
        try (InputStream raw = getAssets().open(assetName);
             ZipInputStream zip = new ZipInputStream(raw)) {
            ZipEntry entry;
            byte[] buffer = new byte[1024 * 128];
            while ((entry = zip.getNextEntry()) != null) {
                File out = new File(destination, entry.getName());
                String canonical = out.getCanonicalPath();
                if (!canonical.startsWith(base)) throw new SecurityException("invalid package entry");

                if (entry.isDirectory()) {
                    out.mkdirs();
                }
                else {
                    File parent = out.getParentFile();
                    if (parent != null) parent.mkdirs();
                    try (FileOutputStream fos = new FileOutputStream(out)) {
                        int read;
                        while ((read = zip.read(buffer)) > 0) fos.write(buffer, 0, read);
                    }
                }
                zip.closeEntry();
            }
        }
    }

    private void launchGame(Container container, File exe) {
        Intent intent = new Intent(this, XServerDisplayActivity.class);
        intent.putExtra("container_id", container.id);
        intent.putExtra("exec_path", exe.getAbsolutePath());
        intent.putExtra("exec_args", "-basedir . +map ndu");
        intent.putExtra("xziel_direct_boot", true);
        startActivity(intent);
        finish();
    }

    private void fail(String message) {
        runOnUiThread(() -> status.setText(message));
    }
}
'''
(java / "XzielBootActivity.java").write_text(boot_java, encoding="utf-8")

# Direct EXE arguments + clean app exit instead of returning to Winlator UI.
xserver = java / "XServerDisplayActivity.java"
text = xserver.read_text(encoding="utf-8")

anchor = '        preferences = PreferenceManager.getDefaultSharedPreferences(this);\n'
insert = '''        preferences = PreferenceManager.getDefaultSharedPreferences(this);
        String xzielExecArgs = getIntent().getStringExtra("exec_args");
        if (xzielExecArgs != null && !xzielExecArgs.isEmpty()) {
            getOverrideEnvVars().put("EXTRA_EXEC_ARGS", xzielExecArgs);
        }
'''
if anchor not in text:
    raise SystemExit("Could not find XServer preferences anchor")
text = text.replace(anchor, insert, 1)

old_exit = '''        Intent intent = getIntent();
        if (intent.hasExtra("exec_path")) {
'''
new_exit = '''        Intent intent = getIntent();
        if (intent.getBooleanExtra("xziel_direct_boot", false)) {
            ForegroundService.stopSession(this);
            finishAndRemoveTask();
            return;
        }
        if (intent.hasExtra("exec_path")) {
'''
if old_exit not in text:
    raise SystemExit("Could not find XServer exit anchor")
text = text.replace(old_exit, new_exit, 1)
xserver.write_text(text, encoding="utf-8")

# Rebrand any visible foreground-service strings.
fg = java / "services/ForegroundService.java"
text = fg.read_text(encoding="utf-8")
text = text.replace('"Winlator:ForegroundService"', '"XZIEL:ForegroundService"')
text = text.replace('"Winlator"', '"XZIEL"')
text = text.replace('"Winlator is running in the background"', '"XZIEL is running in the background"')
fg.write_text(text, encoding="utf-8")

# Make XZIEL the only launcher entry point. Keep Winlator's activities internal.
manifest = app / "src/main/AndroidManifest.xml"
text = manifest.read_text(encoding="utf-8")
old_main = '''        <activity android:name="com.winlator.MainActivity"
            android:theme="@style/AppThemeDark"
            android:exported="true"
            android:screenOrientation="sensor"
            android:configChanges="keyboard|keyboardHidden|orientation|screenSize|screenLayout|smallestScreenSize|density|navigation">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
'''
new_main = '''        <activity android:name="com.winlator.XzielBootActivity"
            android:theme="@style/AppThemeFullscreenDark"
            android:exported="true"
            android:screenOrientation="sensorLandscape"
            android:configChanges="keyboard|keyboardHidden|orientation|screenSize|screenLayout|smallestScreenSize|density|navigation">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>

        <activity android:name="com.winlator.MainActivity"
            android:theme="@style/AppThemeDark"
            android:exported="false"
            android:screenOrientation="sensor"
            android:configChanges="keyboard|keyboardHidden|orientation|screenSize|screenLayout|smallestScreenSize|density|navigation"/>
'''
if old_main not in text:
    raise SystemExit("Could not find MainActivity manifest block")
text = text.replace(old_main, new_main, 1)
text = text.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@drawable/xziel_icon"')
text = text.replace('android:authorities="com.winlator.FileProvider"', 'android:authorities="${applicationId}.FileProvider"')
manifest.write_text(text, encoding="utf-8")

# Minimal XZIEL icon; avoids exposing Winlator branding.
drawable = res / "drawable"
drawable.mkdir(parents=True, exist_ok=True)
(drawable / "xziel_icon.xml").write_text(r'''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#090909" android:pathData="M0,0h108v108h-108z"/>
    <path android:fillColor="#FFFFFF" android:pathData="M22,24h64v10h-64zM22,74h64v10h-64z"/>
    <path android:fillColor="#FFFFFF" android:pathData="M28,34h15l37,40h-15zM80,34h-15l-37,40h15z"/>
</vector>
''', encoding="utf-8")

strings = res / "values/strings.xml"
text = strings.read_text(encoding="utf-8")
text = text.replace('<string name="app_name">Winlator</string>', '<string name="app_name">XZIEL</string>')
strings.write_text(text, encoding="utf-8")

gradle = app / "build.gradle"
text = gradle.read_text(encoding="utf-8")
text = text.replace("applicationId 'com.winlator'", "applicationId 'com.xziel.hybrid'")
text = text.replace('versionCode 33', 'versionCode 1')
text = text.replace('versionName "11.2"', 'versionName "0.1-hybrid"')
# Guest ZIP and compatibility-layer TZST payloads are already compressed.
# Keep AAPT from recompressing them (saves heap and first-build time).
android_anchor = "    lintOptions {\n"
if android_anchor in text and "aaptOptions" not in text:
    text = text.replace(
        android_anchor,
        "    aaptOptions {\n        noCompress 'zip', 'tzst'\n    }\n\n" + android_anchor,
        1,
    )
gradle.write_text(text, encoding="utf-8")

(root / "gradle.properties").write_text(
    "org.gradle.jvmargs=-Xmx5g -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8\\n"
    "org.gradle.parallel=false\\n"
    "android.useAndroidX=true\\n",
    encoding="utf-8",
)

licenses = assets / "licenses"
licenses.mkdir(parents=True, exist_ok=True)
license_src = root / "LICENSE"
if license_src.is_file():
    (licenses / "WINLATOR-LGPL-2.1.txt").write_text(license_src.read_text(encoding="utf-8"), encoding="utf-8")
(licenses / "XZIEL-HYBRID-NOTICE.txt").write_text(
    "XZIEL Hybrid prototype uses modified Winlator source as an internal compatibility layer.\n"
    "Winlator source: https://github.com/brunodev85/winlator-app\n"
    "Modifications: direct boot, XZIEL branding, bundled Xziel.exe package, no container UI.\n",
    encoding="utf-8"
)

print("XZIEL_WINLATOR_DIRECT_PATCH_OK")
