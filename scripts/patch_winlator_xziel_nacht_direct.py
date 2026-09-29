#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_winlator_xziel_nacht_direct.py <winlator-app-root>")

root = Path(sys.argv[1]).resolve()
app = root / "app"
java = app / "src/main/java/com/winlator"
assets = app / "src/main/assets"
res = app / "src/main/res"

if not java.is_dir():
    raise SystemExit(f"Winlator Java source not found: {java}")

boot_java = r'''package com.winlator;

import android.content.Intent;
import android.content.res.AssetManager;
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
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.concurrent.Executors;

public class XzielBootActivity extends AppCompatActivity {
    private TextView status;

    private static final String GAME_ASSET = "nacht-onefile.exe";
    private static final String GAME_DIR = "XZIEL";
    private static final String GAME_EXE = "Nacht-Chronicles-XZIEL.exe";
    private static final long GAME_BYTES = 887735046L;
    private static final String GAME_SHA256 =
        "2cc8876fc79d50c3731f8f0681e3bfeb2e2cef084b87bf1b8a87c8c43a430d02";
    private static final String PACKAGE_MARKER = ".xziel-nacht-onefile-v1";

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
        status.setText("XZIEL\nLoading Nacht...");
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
                File marker = new File(gameDir, PACKAGE_MARKER);

                boolean ready =
                    exe.isFile() &&
                    exe.length() == GAME_BYTES &&
                    marker.isFile() &&
                    GAME_SHA256.equals(FileUtils.readString(marker).trim());

                if (!ready) {
                    FileUtils.delete(gameDir);
                    if (!gameDir.mkdirs() && !gameDir.isDirectory()) {
                        throw new RuntimeException("could not create game directory");
                    }

                    installExeTransactional(exe);

                    if (!exe.isFile() || exe.length() != GAME_BYTES) {
                        throw new RuntimeException("installed EXE size mismatch");
                    }
                    FileUtils.writeString(marker, GAME_SHA256 + "\n");
                }

                runOnUiThread(() -> launchGame(container, exe));
            }
            catch (Throwable t) {
                fail("XZIEL game setup failed\n" + t.getMessage());
            }
        });
    }

    private void installExeTransactional(File finalExe) throws Exception {
        File tmp = new File(finalExe.getParentFile(), GAME_EXE + ".partial");
        FileUtils.delete(tmp);

        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long total = 0;

        try (InputStream in = getAssets().open(GAME_ASSET, AssetManager.ACCESS_STREAMING);
             FileOutputStream out = new FileOutputStream(tmp)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = in.read(buffer)) > 0) {
                out.write(buffer, 0, read);
                digest.update(buffer, 0, read);
                total += read;
            }
            out.getFD().sync();
        }

        if (total != GAME_BYTES) {
            FileUtils.delete(tmp);
            throw new RuntimeException("embedded EXE byte count mismatch: " + total);
        }

        String actual = toHex(digest.digest());
        if (!GAME_SHA256.equals(actual)) {
            FileUtils.delete(tmp);
            throw new RuntimeException("embedded EXE SHA-256 mismatch");
        }

        FileUtils.delete(finalExe);
        if (!tmp.renameTo(finalExe)) {
            FileUtils.delete(tmp);
            throw new RuntimeException("atomic EXE install rename failed");
        }
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) sb.append(String.format("%02x", b & 0xff));
        return sb.toString();
    }

    private void launchGame(Container container, File exe) {
        Intent intent = new Intent(this, XServerDisplayActivity.class);
        intent.putExtra("container_id", container.id);
        intent.putExtra("exec_path", exe.getAbsolutePath());
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

xserver = java / "XServerDisplayActivity.java"
text = xserver.read_text(encoding="utf-8")

old_back = '''    @Override
    public void onBackPressed() {
        if (environment != null) {
'''
new_back = '''    @Override
    public void onBackPressed() {
        if (getIntent().getBooleanExtra("xziel_direct_boot", false)) return;
        if (environment != null) {
'''
if old_back not in text:
    raise SystemExit("Could not find XServer onBackPressed anchor")
text = text.replace(old_back, new_back, 1)

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

fg = java / "services/ForegroundService.java"
text = fg.read_text(encoding="utf-8")
text = text.replace('"Winlator:ForegroundService"', '"XZIEL:ForegroundService"')
text = text.replace('"Winlator is running in the background"', '"XZIEL is running in the background"')
text = text.replace('"Winlator"', '"XZIEL"')
fg.write_text(text, encoding="utf-8")

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

drawable = res / "drawable"
drawable.mkdir(parents=True, exist_ok=True)
(drawable / "xziel_icon.xml").write_text(r'''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#080808" android:pathData="M0,0h108v108h-108z"/>
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
text = text.replace('versionName "11.2"', 'versionName "0.1-nacht-hybrid"')

anchor = "    lintOptions {\n"
if anchor in text and "aaptOptions" not in text:
    text = text.replace(
        anchor,
        "    aaptOptions {\n        noCompress 'exe', 'tzst'\n    }\n\n" + anchor,
        1,
    )
gradle.write_text(text, encoding="utf-8")

(root / "gradle.properties").write_text(
    "\n".join([
        "org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8",
        "org.gradle.parallel=false",
        "org.gradle.daemon=false",
        "android.useAndroidX=true",
        "android.enableJetifier=true",
        "android.nonFinalResIds=false",
        "android.nonTransitiveRClass=false",
    ]) + "\n",
    encoding="utf-8",
)

licenses = assets / "licenses"
licenses.mkdir(parents=True, exist_ok=True)
license_src = root / "LICENSE"
if license_src.is_file():
    (licenses / "WINLATOR-LGPL-2.1.txt").write_text(
        license_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

(licenses / "XZIEL-HYBRID-NOTICE.txt").write_text(
    "XZIEL Hybrid prototype uses modified Winlator source as an internal compatibility layer.\n"
    "Upstream: https://github.com/brunodev85/winlator-app\n"
    "Pinned upstream commit: 3981d86efa4f333b2a34a7da8b6521476cd8c8b9\n"
    "Modifications: direct boot, XZIEL branding, transactional Nacht EXE install, hidden container UI.\n",
    encoding="utf-8",
)

print("XZIEL_NACHT_WINLATOR_DIRECT_PATCH_OK")
