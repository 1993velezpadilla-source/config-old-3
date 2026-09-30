#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 6:
    raise SystemExit(
        "usage: patch_winlator_xziel_nacht_direct_runtime.py "
        "<winlator-app-root> <runtime-exe-bytes> <runtime-exe-sha256> <vfs-bytes> <vfs-sha256>"
    )

root = Path(sys.argv[1]).resolve()
runtime_exe_bytes = int(sys.argv[2])
runtime_exe_sha256 = sys.argv[3].strip().lower()
vfs_bytes = int(sys.argv[4])
vfs_sha256 = sys.argv[5].strip().lower()

if runtime_exe_bytes < 100_000 or len(runtime_exe_sha256) != 64:
    raise SystemExit("invalid XZIEL runtime EXE identity")
if vfs_bytes < 800_000_000 or len(vfs_sha256) != 64:
    raise SystemExit("invalid Nacht VFS identity")

# First reuse the existing, validated touch/gyro/direct-boot patch so this path
# keeps the exact same HUD, gyro, branding, hidden Winlator UI and diagnostics.
base_patch = Path(__file__).with_name("patch_winlator_xziel_nacht_direct.py")
subprocess.check_call([
    sys.executable,
    str(base_patch),
    str(root),
    "800000001",
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
])

app = root / "app"
java = app / "src/main/java/com/winlator"

boot_java = r'''package com.winlator;

import android.content.Intent;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
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

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class XzielBootActivity extends AppCompatActivity {
    private static final String TAG = "XZIEL-HYBRID";
    private TextView status;

    private static final String VFS_ASSET = "xziel-nacht-vfs.zip";
    private static final String RUNTIME_ASSET_DIR = "xziel_runtime";
    private static final String GAME_DIR = "XZIEL";
    private static final String GAME_EXE = "Xziel-Nacht.exe";
    private static final long GAME_EXE_BYTES = __XZIEL_RUNTIME_EXE_BYTES__L;
    private static final String GAME_EXE_SHA256 = "__XZIEL_RUNTIME_EXE_SHA256__";
    private static final long VFS_BYTES = __XZIEL_VFS_BYTES__L;
    private static final String VFS_SHA256 = "__XZIEL_VFS_SHA256__";
    private static final String PACKAGE_MARKER = ".xziel-nacht-direct-runtime-v1";

    private static final String[] RUNTIME_FILES = new String[] {
        "Xziel-Nacht.exe",
        "SDL2.dll",
        "libEGL.dll",
        "libGLESv2.dll",
        "libgcc_s_seh-1.dll",
        "libstdc++-6.dll",
        "libwinpthread-1.dll",
        "zlib1.dll"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "BOOT_ACTIVITY_START");
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
            Log.i(TAG, "ROOTFS_READY version=" + rootFS.getVersion());
            runOnUiThread(this::ensureContainer);
        }
        catch (Throwable t) {
            Log.e(TAG, "BOOT_FAIL", t);
            fail("XZIEL startup failed\n" + t.getMessage());
        }
    }

    private void ensureContainer() {
        try {
            ContainerManager manager = new ContainerManager(this);
            ArrayList<Container> containers = manager.getContainers();
            if (!containers.isEmpty()) {
                Log.i(TAG, "CONTAINER_READY id=" + containers.get(0).id + " reused=1");
                prepareGameAndLaunch(manager, containers.get(0));
                return;
            }

            JSONObject data = new JSONObject();
            data.put("name", "XZIEL");
            data.put("screenSize", "1280x720");
            data.put("envVars", Container.DEFAULT_ENV_VARS);

            boolean xzielX86Bridge =
                    Build.SUPPORTED_ABIS != null &&
                    Build.SUPPORTED_ABIS.length > 0 &&
                    Build.SUPPORTED_ABIS[0].startsWith("x86");

            if (xzielX86Bridge) {
                data.put("graphicsDriver", GraphicsDrivers.VIRGL + "," + GraphicsDrivers.VIRGL);
                data.put("dxwrapper", DXWrappers.WINED3D);
                Log.i(TAG, "GRAPHICS_PROFILE x86_bridge=1 vulkan=off opengl=virgl dx=wined3d");
            }
            else {
                data.put("graphicsDriver", GraphicsDrivers.VORTEK + "," + GraphicsDrivers.GLADIO);
                data.put("dxwrapper", DXWrappers.DXVK);
                Log.i(TAG, "GRAPHICS_PROFILE x86_bridge=0 vulkan=vortek opengl=gladio dx=dxvk");
            }

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
                Log.i(TAG, "CONTAINER_READY id=" + container.id + " reused=0");
                prepareGameAndLaunch(manager, container);
            });
        }
        catch (Throwable t) {
            Log.e(TAG, "CONTAINER_FAIL", t);
            fail("XZIEL setup failed\n" + t.getMessage());
        }
    }

    private void prepareGameAndLaunch(ContainerManager manager, Container container) {
        Executors.newSingleThreadExecutor().execute(() -> {
            try {
                manager.activateContainer(container);

                File driveC = new File(container.getRootDir(), ".wine/drive_c");
                File gameDir = new File(driveC, GAME_DIR);
                File exe = new File(gameDir, GAME_EXE);
                File scene = new File(gameDir, "xziel/maps/xziel_nacht_bo3/scene.xzsc");
                File meshes = new File(gameDir, "xziel/maps/xziel_nacht_bo3/meshes");
                File marker = new File(gameDir, PACKAGE_MARKER);
                String markerValue = GAME_EXE_SHA256 + ":" + VFS_SHA256;

                boolean ready =
                    exe.isFile() &&
                    exe.length() == GAME_EXE_BYTES &&
                    scene.isFile() &&
                    countMeshes(meshes) == 492 &&
                    marker.isFile() &&
                    markerValue.equals(FileUtils.readString(marker).trim());

                if (!ready) {
                    Log.i(TAG, "DIRECT_INSTALL_BEGIN");
                    runOnUiThread(() -> status.setText("XZIEL\nInstalling Nacht..."));

                    File staging = new File(driveC, GAME_DIR + ".partial");
                    FileUtils.delete(staging);
                    if (!staging.mkdirs() && !staging.isDirectory()) {
                        throw new RuntimeException("could not create staging directory");
                    }

                    installRuntimeAssets(staging);

                    File stagedExe = new File(staging, GAME_EXE);
                    if (!stagedExe.isFile() || stagedExe.length() != GAME_EXE_BYTES) {
                        throw new RuntimeException("runtime EXE size mismatch");
                    }
                    if (!GAME_EXE_SHA256.equals(sha256File(stagedExe))) {
                        throw new RuntimeException("runtime EXE SHA-256 mismatch");
                    }
                    Log.i(TAG, "DIRECT_RUNTIME_GREEN bytes=" + stagedExe.length());

                    File stagedZip = new File(staging, VFS_ASSET);
                    copyAssetVerified(VFS_ASSET, stagedZip, VFS_BYTES, VFS_SHA256);
                    Log.i(TAG, "VFS_COPY_GREEN bytes=" + stagedZip.length());

                    extractVfs(stagedZip, staging);
                    FileUtils.delete(stagedZip);

                    File stagedScene = new File(staging, "xziel/maps/xziel_nacht_bo3/scene.xzsc");
                    File stagedMeshes = new File(staging, "xziel/maps/xziel_nacht_bo3/meshes");
                    int meshCount = countMeshes(stagedMeshes);
                    if (!stagedScene.isFile()) {
                        throw new RuntimeException("scene.xzsc missing after VFS extraction");
                    }
                    if (meshCount != 492) {
                        throw new RuntimeException("mesh count mismatch after VFS extraction: " + meshCount);
                    }
                    Log.i(TAG, "VFS_EXTRACT_GREEN meshes=" + meshCount);

                    FileUtils.writeString(new File(staging, PACKAGE_MARKER), markerValue + "\n");
                    FileUtils.delete(gameDir);
                    if (!staging.renameTo(gameDir)) {
                        throw new RuntimeException("atomic game directory install rename failed");
                    }

                    exe = new File(gameDir, GAME_EXE);
                    Log.i(TAG, "DIRECT_INSTALL_GREEN");
                }
                else {
                    Log.i(TAG, "DIRECT_ALREADY_READY meshes=492");
                }

                File finalExe = exe;
                runOnUiThread(() -> launchGame(container, finalExe));
            }
            catch (Throwable t) {
                Log.e(TAG, "DIRECT_INSTALL_FAIL", t);
                fail("XZIEL game setup failed\n" + t.getMessage());
            }
        });
    }

    private void installRuntimeAssets(File gameDir) throws Exception {
        for (String name : RUNTIME_FILES) {
            File dst = new File(gameDir, name);
            try (InputStream in = getAssets().open(RUNTIME_ASSET_DIR + "/" + name, AssetManager.ACCESS_STREAMING);
                 BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(dst), 1024 * 1024)) {
                byte[] buffer = new byte[1024 * 1024];
                int read;
                while ((read = in.read(buffer)) > 0) out.write(buffer, 0, read);
            }
            if (!dst.isFile() || dst.length() == 0) {
                throw new RuntimeException("runtime asset copy failed: " + name);
            }
        }
    }

    private void copyAssetVerified(String assetName, File dst, long expectedBytes, String expectedSha) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long total = 0;
        try (InputStream in = new BufferedInputStream(getAssets().open(assetName, AssetManager.ACCESS_STREAMING), 1024 * 1024);
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(dst), 1024 * 1024)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = in.read(buffer)) > 0) {
                out.write(buffer, 0, read);
                digest.update(buffer, 0, read);
                total += read;
            }
        }
        if (total != expectedBytes) {
            FileUtils.delete(dst);
            throw new RuntimeException("VFS byte count mismatch: " + total);
        }
        String actual = toHex(digest.digest());
        if (!expectedSha.equals(actual)) {
            FileUtils.delete(dst);
            throw new RuntimeException("VFS SHA-256 mismatch");
        }
    }

    private void extractVfs(File zipFile, File destination) throws Exception {
        String destCanonical = destination.getCanonicalPath() + File.separator;
        int files = 0;

        try (ZipInputStream zin = new ZipInputStream(
                new BufferedInputStream(new FileInputStream(zipFile), 1024 * 1024))) {
            ZipEntry entry;
            byte[] buffer = new byte[1024 * 1024];

            while ((entry = zin.getNextEntry()) != null) {
                File outFile = new File(destination, entry.getName());
                String canonical = outFile.getCanonicalPath();
                if (!canonical.startsWith(destCanonical)) {
                    throw new RuntimeException("unsafe ZIP entry: " + entry.getName());
                }

                if (entry.isDirectory()) {
                    if (!outFile.mkdirs() && !outFile.isDirectory()) {
                        throw new RuntimeException("could not create directory: " + entry.getName());
                    }
                }
                else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
                        throw new RuntimeException("could not create parent: " + entry.getName());
                    }
                    try (BufferedOutputStream out = new BufferedOutputStream(
                            new FileOutputStream(outFile), 1024 * 1024)) {
                        int read;
                        while ((read = zin.read(buffer)) > 0) out.write(buffer, 0, read);
                    }
                    files++;
                    if ((files % 50) == 0) {
                        Log.i(TAG, "VFS_EXTRACT_PROGRESS files=" + files);
                    }
                }
                zin.closeEntry();
            }
        }
        Log.i(TAG, "VFS_EXTRACT_FILES files=" + files);
    }

    private int countMeshes(File dir) {
        File[] items = dir.listFiles((d, name) -> name.endsWith(".xzm"));
        return items == null ? 0 : items.length;
    }

    private String sha256File(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new BufferedInputStream(new FileInputStream(file), 1024 * 1024)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = in.read(buffer)) > 0) digest.update(buffer, 0, read);
        }
        return toHex(digest.digest());
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) sb.append(String.format("%02x", b & 0xff));
        return sb.toString();
    }

    private void launchGame(Container container, File exe) {
        Log.i(TAG, "LAUNCH_XSERVER_DIRECT exe=" + exe.getName() + " bytes=" + exe.length());
        Intent intent = new Intent(this, XServerDisplayActivity.class);
        intent.putExtra("container_id", container.id);
        intent.putExtra("exec_path", exe.getAbsolutePath());
        intent.putExtra("xziel_exec_args", "--xziel-root C:\\XZIEL --xziel-map xziel_nacht_bo3");
        intent.putExtra("xziel_direct_boot", true);
        startActivity(intent);
        finish();
    }

    private void fail(String message) {
        runOnUiThread(() -> status.setText(message));
    }
}
'''

boot_java = (
    boot_java
    .replace("__XZIEL_RUNTIME_EXE_BYTES__", str(runtime_exe_bytes))
    .replace("__XZIEL_RUNTIME_EXE_SHA256__", runtime_exe_sha256)
    .replace("__XZIEL_VFS_BYTES__", str(vfs_bytes))
    .replace("__XZIEL_VFS_SHA256__", vfs_sha256)
)
(java / "XzielBootActivity.java").write_text(boot_java, encoding="utf-8")

# Let direct-runtime boot pass the native runtime arguments through winhandler.
xserver = java / "XServerDisplayActivity.java"
text = xserver.read_text(encoding="utf-8")
args_anchor = '''            if (intent.hasExtra("exec_path")) {
                execPath = WineUtils.unixToDOSPath(intent.getStringExtra("exec_path"), container);
'''
args_insert = '''            if (intent.hasExtra("exec_path")) {
                execPath = WineUtils.unixToDOSPath(intent.getStringExtra("exec_path"), container);
                String xzielExecArgs = intent.getStringExtra("xziel_exec_args");
                if (xzielExecArgs != null && !xzielExecArgs.isEmpty()) {
                    execArgs = " " + xzielExecArgs;
                    Log.i("XZIEL-HYBRID", "DIRECT_EXEC_ARGS " + xzielExecArgs);
                }
'''
if args_anchor not in text:
    raise SystemExit("Could not find direct-runtime exec args anchor")
text = text.replace(args_anchor, args_insert, 1)
xserver.write_text(text, encoding="utf-8")

# Store the huge VFS ZIP without re-compressing it inside the APK.
gradle = app / "build.gradle"
text = gradle.read_text(encoding="utf-8")
text = text.replace(
    "noCompress 'exe', 'tzst'",
    "noCompress 'exe', 'tzst', 'zip', 'dll'",
)
gradle.write_text(text, encoding="utf-8")

print("XZIEL_NACHT_DIRECT_RUNTIME_PATCH_OK")
