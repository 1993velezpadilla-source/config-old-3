#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: patch_winlator_xziel_nacht_direct.py "
        "<winlator-app-root> <vfs-bytes> <vfs-sha256> <runtime-exe-sha256>"
    )

root = Path(sys.argv[1]).resolve()
vfs_bytes = int(sys.argv[2])
vfs_sha256 = sys.argv[3].strip().lower()
runtime_exe_sha256 = sys.argv[4].strip().lower()
if vfs_bytes < 800_000_000 or len(vfs_sha256) != 64 or len(runtime_exe_sha256) != 64:
    raise SystemExit("invalid Nacht direct payload identity")
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

import java.io.File;
import java.io.BufferedInputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.ArrayList;
import java.util.concurrent.Executors;

public class XzielBootActivity extends AppCompatActivity {
    private static final String TAG = "XZIEL-HYBRID";
    private TextView status;

    private static final String VFS_ASSET = "nacht-vfs.zip";
    private static final String RUNTIME_ASSET_DIR = "nacht-runtime";
    private static final String GAME_DIR = "XZIEL";
    private static final String GAME_EXE = "Xziel-Nacht.exe";
    private static final String SCENE_RELATIVE =
        "xziel/maps/xziel_nacht_bo3/scene.xzsc";
    private static final long VFS_BYTES = __XZIEL_VFS_BYTES__L;
    private static final String VFS_SHA256 =
        "__XZIEL_VFS_SHA256__";
    private static final String RUNTIME_EXE_SHA256 =
        "__XZIEL_RUNTIME_EXE_SHA256__";
    private static final String PACKAGE_MARKER = ".xziel-nacht-direct-vfs-v1";

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
            fail("XZIEL setup failed\n" + t.getMessage());
        }
    }

    private void prepareGameAndLaunch(ContainerManager manager, Container container) {
        Executors.newSingleThreadExecutor().execute(() -> {
            try {
                manager.activateContainer(container);

                File gameDir = new File(container.getRootDir(), ".wine/drive_c/" + GAME_DIR);
                File exe = new File(gameDir, GAME_EXE);
                File scene = new File(gameDir, SCENE_RELATIVE);
                File marker = new File(gameDir, PACKAGE_MARKER);

                boolean ready =
                    exe.isFile() &&
                    scene.isFile() &&
                    marker.isFile() &&
                    VFS_SHA256.equals(FileUtils.readString(marker).trim()) &&
                    RUNTIME_EXE_SHA256.equals(sha256File(exe));

                if (!ready) {
                    Log.i(TAG, "DIRECT_PAYLOAD_INSTALL_BEGIN vfs_bytes=" + VFS_BYTES);
                    runOnUiThread(() -> status.setText("XZIEL\nPreparing Nacht data..."));
                    FileUtils.delete(gameDir);
                    if (!gameDir.mkdirs() && !gameDir.isDirectory()) {
                        throw new RuntimeException("could not create game directory");
                    }

                    copyRuntimeAssets(gameDir);
                    int extracted = unzipVfsAsset(gameDir);

                    if (!exe.isFile()) {
                        throw new RuntimeException("direct runtime EXE missing after install");
                    }
                    if (!RUNTIME_EXE_SHA256.equals(sha256File(exe))) {
                        throw new RuntimeException("direct runtime EXE SHA-256 mismatch");
                    }
                    if (!scene.isFile()) {
                        throw new RuntimeException("Nacht scene missing after VFS extraction");
                    }

                    FileUtils.writeString(marker, VFS_SHA256 + "\n");
                    Log.i(TAG, "DIRECT_PAYLOAD_INSTALL_GREEN files=" + extracted +
                            " exe_bytes=" + exe.length() +
                            " scene_bytes=" + scene.length());
                }
                else {
                    Log.i(TAG, "DIRECT_PAYLOAD_ALREADY_READY exe_bytes=" + exe.length());
                }

                runOnUiThread(() -> launchGame(container, exe));
            }
            catch (Throwable t) {
                Log.e(TAG, "DIRECT_PAYLOAD_INSTALL_FAILED", t);
                fail("XZIEL game setup failed\n" + t.getMessage());
            }
        });
    }

    private void copyRuntimeAssets(File gameDir) throws Exception {
        String[] names = getAssets().list(RUNTIME_ASSET_DIR);
        if (names == null || names.length == 0) {
            throw new RuntimeException("embedded Win64 runtime assets missing");
        }

        int copied = 0;
        for (String name : names) {
            File out = new File(gameDir, name);
            try (InputStream in = getAssets().open(
                        RUNTIME_ASSET_DIR + "/" + name,
                        AssetManager.ACCESS_STREAMING);
                 FileOutputStream stream = new FileOutputStream(out)) {
                byte[] buffer = new byte[1024 * 1024];
                int read;
                while ((read = in.read(buffer)) > 0) {
                    stream.write(buffer, 0, read);
                }
                stream.getFD().sync();
            }
            copied++;
        }
        Log.i(TAG, "DIRECT_RUNTIME_ASSETS_COPIED count=" + copied);
    }

    private int unzipVfsAsset(File gameDir) throws Exception {
        String rootPath = gameDir.getCanonicalPath() + File.separator;
        int files = 0;

        try (InputStream raw = getAssets().open(VFS_ASSET, AssetManager.ACCESS_STREAMING);
             BufferedInputStream buffered = new BufferedInputStream(raw, 1024 * 1024);
             ZipInputStream zip = new ZipInputStream(buffered)) {
            byte[] buffer = new byte[1024 * 1024];
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                File out = new File(gameDir, entry.getName());
                String outPath = out.getCanonicalPath();
                if (!outPath.startsWith(rootPath)) {
                    throw new RuntimeException("unsafe VFS entry: " + entry.getName());
                }

                if (entry.isDirectory()) {
                    if (!out.mkdirs() && !out.isDirectory()) {
                        throw new RuntimeException("could not create VFS directory: " + entry.getName());
                    }
                }
                else {
                    File parent = out.getParentFile();
                    if (parent != null && !parent.mkdirs() && !parent.isDirectory()) {
                        throw new RuntimeException("could not create VFS parent: " + entry.getName());
                    }
                    try (FileOutputStream stream = new FileOutputStream(out)) {
                        int read;
                        while ((read = zip.read(buffer)) > 0) {
                            stream.write(buffer, 0, read);
                        }
                    }
                    files++;
                    if ((files % 500) == 0) {
                        Log.i(TAG, "DIRECT_VFS_EXTRACT_PROGRESS files=" + files);
                    }
                }
                zip.closeEntry();
            }
        }

        if (files == 0) {
            throw new RuntimeException("embedded VFS extracted zero files");
        }
        Log.i(TAG, "DIRECT_VFS_EXTRACT_GREEN files=" + files);
        return files;
    }

    private static String sha256File(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(file)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = in.read(buffer)) > 0) {
                digest.update(buffer, 0, read);
            }
        }
        return toHex(digest.digest());
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) sb.append(String.format("%02x", b & 0xff));
        return sb.toString();
    }

    private void launchGame(Container container, File exe) {
        Log.i(TAG, "LAUNCH_XSERVER exe=" + exe.getName() + " bytes=" + exe.length());
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
boot_java = (
    boot_java
    .replace("__XZIEL_VFS_BYTES__", str(vfs_bytes))
    .replace("__XZIEL_VFS_SHA256__", vfs_sha256)
    .replace("__XZIEL_RUNTIME_EXE_SHA256__", runtime_exe_sha256)
)
(java / "XzielBootActivity.java").write_text(boot_java, encoding="utf-8")

overlay_java = r'''package com.winlator;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.util.SparseArray;
import android.util.SparseIntArray;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;

import com.winlator.xserver.Pointer;
import com.winlator.xserver.XKeycode;
import com.winlator.xserver.XServer;

import java.io.InputStream;

/*
 * XZIEL Zombies Mobile HUD V1.
 *
 * The 12 user-approved skin images are real APK assets loaded from
 * assets/xziel_hud/*.webp.  The artwork is never redrawn procedurally.
 * Idle alpha is intentionally mobile-safe (~82%); pressed buttons become
 * slightly stronger so touch feedback remains obvious.
 */
public final class XzielMobileOverlay extends View implements SensorEventListener {
    private static final int ROLE_NONE = 0;
    private static final int ROLE_JOYSTICK = 1;
    private static final int ROLE_LOOK = 2;
    private static final int ROLE_FIRE = 3;
    private static final int ROLE_ADS = 4;
    private static final int ROLE_ADSFIRE = 5;
    private static final int ROLE_RELOAD = 6;
    private static final int ROLE_INTERACT = 7;
    private static final int ROLE_CROUCH = 8;
    private static final int ROLE_SPRINT = 9;
    private static final int ROLE_GRENADE = 10;
    private static final int ROLE_SWAP = 11;
    private static final int ROLE_PAUSE = 12;
    private static final int ROLE_JUMP = 13;
    private static final int ROLE_KNIFE = 14;
    private static final int ROLE_PRONE = 15;
    private static final int ROLE_SLIDE = 16;

    private static final float JOY_X = 0.155f;
    private static final float JOY_Y = 0.785f;
    private static final float JOY_R = 0.118f;

    private static final float TOUCH_LOOK_NORMAL = 1.18f;
    private static final float TOUCH_LOOK_ADS = 0.72f;
    private static final float GYRO_NORMAL_PX_PER_RAD = 920.0f;
    private static final float GYRO_ADS_PX_PER_RAD = 520.0f;

    private static final int HUD_IDLE_ALPHA = 210;
    private static final int HUD_PRESSED_ALPHA = 246;

    private final XServer xServer;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint bitmapPaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final SparseIntArray pointerRoles = new SparseIntArray();
    private final SparseIntArray pointerButtonIndex = new SparseIntArray();
    private final SparseArray<Bitmap> roleBitmaps = new SparseArray<>();
    private final float[] lastX = new float[32];
    private final float[] lastY = new float[32];

    private final SensorManager sensorManager;
    private final Sensor gyroscope;
    private long lastGyroTimestamp = 0L;

    private int joystickPointer = -1;
    private float joyKnobX = JOY_X;
    private float joyKnobY = JOY_Y;

    private boolean keyW, keyA, keyS, keyD;
    private int fireRefs = 0;
    private int adsRefs = 0;

    private static final class ButtonDef {
        final int role;
        final float x, y, r;
        ButtonDef(int role, float x, float y, float r) {
            this.role = role;
            this.x = x;
            this.y = y;
            this.r = r;
        }
    }

    /*
     * Pixel Fold front-display landscape layout.
     * Right side is the combat cluster; left remains movement/joystick.
     */
    private static final ButtonDef[] BUTTONS = new ButtonDef[] {
        new ButtonDef(ROLE_FIRE,     0.915f, 0.690f, 0.080f),
        new ButtonDef(ROLE_ADSFIRE,  0.815f, 0.575f, 0.066f),
        new ButtonDef(ROLE_ADS,      0.915f, 0.475f, 0.060f),
        new ButtonDef(ROLE_RELOAD,   0.705f, 0.505f, 0.054f),
        new ButtonDef(ROLE_INTERACT, 0.610f, 0.640f, 0.052f),
        new ButtonDef(ROLE_KNIFE,    0.710f, 0.690f, 0.050f),
        new ButtonDef(ROLE_CROUCH,   0.825f, 0.835f, 0.052f),
        new ButtonDef(ROLE_PRONE,    0.760f, 0.835f, 0.050f),
        new ButtonDef(ROLE_SLIDE,    0.695f, 0.835f, 0.050f),
        new ButtonDef(ROLE_GRENADE,  0.615f, 0.835f, 0.050f),
        new ButtonDef(ROLE_SWAP,     0.915f, 0.845f, 0.050f),
        new ButtonDef(ROLE_SPRINT,   0.150f, 0.585f, 0.055f),

        /* Utility buttons that do not have user-supplied V1 art yet. */
        new ButtonDef(ROLE_JUMP,     0.815f, 0.710f, 0.042f),
        new ButtonDef(ROLE_PAUSE,    0.955f, 0.090f, 0.038f)
    };

    public XzielMobileOverlay(Context context, XServer xServer) {
        super(context);
        this.xServer = xServer;

        setClickable(true);
        setFocusable(true);
        setFocusableInTouchMode(true);
        setBackgroundColor(Color.TRANSPARENT);
        setLayoutParams(new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeCap(Paint.Cap.ROUND);
        stroke.setStrokeJoin(Paint.Join.ROUND);

        loadOfficialHudSkins();

        sensorManager = (SensorManager)context.getSystemService(Context.SENSOR_SERVICE);
        gyroscope = sensorManager != null
            ? sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
            : null;

        xServer.setRelativeMouseMovement(true);
    }

    private void loadOfficialHudSkins() {
        loadHudBitmap(ROLE_ADS,      "hud_ads.webp");
        loadHudBitmap(ROLE_ADSFIRE,  "hud_ads_fire.webp");
        loadHudBitmap(ROLE_INTERACT, "hud_claw.webp");
        loadHudBitmap(ROLE_CROUCH,   "hud_crouch.webp");
        loadHudBitmap(ROLE_FIRE,     "hud_fire.webp");
        loadHudBitmap(ROLE_GRENADE,  "hud_grenade.webp");
        loadHudBitmap(ROLE_KNIFE,    "hud_knife.webp");
        loadHudBitmap(ROLE_PRONE,    "hud_prone.webp");
        loadHudBitmap(ROLE_RELOAD,   "hud_reload.webp");
        loadHudBitmap(ROLE_SLIDE,    "hud_slide.webp");
        loadHudBitmap(ROLE_SPRINT,   "hud_sprint.webp");
        loadHudBitmap(ROLE_SWAP,     "hud_swap.webp");

        if (roleBitmaps.size() != 12) {
            throw new IllegalStateException(
                "XZIEL HUD asset gate failed: expected 12, loaded " +
                roleBitmaps.size()
            );
        }
    }

    private void loadHudBitmap(int role, String name) {
        try (InputStream in = getContext().getAssets().open("xziel_hud/" + name)) {
            Bitmap bitmap = BitmapFactory.decodeStream(in);
            if (bitmap == null) {
                throw new IllegalStateException("decode returned null: " + name);
            }
            roleBitmaps.put(role, bitmap);
        }
        catch (Exception e) {
            throw new IllegalStateException("missing XZIEL HUD asset: " + name, e);
        }
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (sensorManager != null && gyroscope != null) {
            sensorManager.registerListener(
                this,
                gyroscope,
                SensorManager.SENSOR_DELAY_GAME
            );
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        releaseAll();
        if (sensorManager != null) sensorManager.unregisterListener(this);
        for (int i = 0; i < roleBitmaps.size(); i++) {
            Bitmap b = roleBitmaps.valueAt(i);
            if (b != null && !b.isRecycled()) b.recycle();
        }
        roleBitmaps.clear();
        super.onDetachedFromWindow();
    }

    private float px(float nx) { return nx * getWidth(); }
    private float py(float ny) { return ny * getHeight(); }

    private boolean hit(float x, float y, ButtonDef b) {
        float dx = (x / Math.max(1f, getWidth())) - b.x;
        float dy = (y / Math.max(1f, getHeight())) - b.y;
        float aspect = getWidth() / Math.max(1f, (float)getHeight());
        dx *= aspect;
        return dx * dx + dy * dy <= b.r * b.r * 1.22f;
    }

    private int buttonAt(float x, float y) {
        for (int i = 0; i < BUTTONS.length; i++) {
            if (hit(x, y, BUTTONS[i])) return i;
        }
        return -1;
    }

    private boolean roleHeld(int role) {
        for (int i = 0; i < pointerRoles.size(); i++) {
            if (pointerRoles.valueAt(i) == role) return true;
        }
        return false;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        drawJoystick(canvas);
        for (ButtonDef b : BUTTONS) {
            drawButton(canvas, b, roleHeld(b.role));
        }
    }

    private void drawJoystick(Canvas canvas) {
        float cx = px(JOY_X);
        float cy = py(JOY_Y);
        float r = JOY_R * getHeight();

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(42, 2, 2, 2));
        canvas.drawCircle(cx, cy, r, paint);

        stroke.setStrokeWidth(Math.max(2f, r * 0.055f));
        stroke.setColor(Color.argb(72, 240, 240, 240));
        canvas.drawCircle(cx, cy, r * 0.92f, stroke);

        float kx = px(joyKnobX);
        float ky = py(joyKnobY);
        paint.setColor(Color.argb(96, 8, 8, 8));
        canvas.drawCircle(kx, ky, r * 0.36f, paint);
        stroke.setStrokeWidth(Math.max(2f, r * 0.045f));
        stroke.setColor(Color.argb(125, 245, 245, 245));
        canvas.drawCircle(kx, ky, r * 0.36f, stroke);
    }

    private void drawButton(Canvas canvas, ButtonDef b, boolean pressed) {
        float cx = px(b.x);
        float cy = py(b.y);
        float r = b.r * getHeight();
        Bitmap bitmap = roleBitmaps.get(b.role);

        if (bitmap != null) {
            float scale = pressed ? 1.05f : 1.0f;
            float rr = r * scale;
            RectF dst = new RectF(cx - rr, cy - rr, cx + rr, cy + rr);
            bitmapPaint.setAlpha(pressed ? HUD_PRESSED_ALPHA : HUD_IDLE_ALPHA);
            canvas.drawBitmap(bitmap, null, dst, bitmapPaint);
            return;
        }

        drawUtilityFallback(canvas, b.role, cx, cy, r, pressed);
    }

    private void drawUtilityFallback(
            Canvas canvas,
            int role,
            float cx,
            float cy,
            float r,
            boolean pressed) {
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(pressed ? 150 : 82, 8, 8, 8));
        canvas.drawCircle(cx, cy, r, paint);

        stroke.setStrokeWidth(Math.max(2f, r * .10f));
        stroke.setColor(Color.argb(pressed ? 245 : 185, 245, 245, 245));

        if (role == ROLE_PAUSE) {
            canvas.drawLine(cx-r*.22f, cy-r*.45f, cx-r*.22f, cy+r*.45f, stroke);
            canvas.drawLine(cx+r*.22f, cy-r*.45f, cx+r*.22f, cy+r*.45f, stroke);
        }
        else if (role == ROLE_JUMP) {
            canvas.drawLine(cx, cy-r*.48f, cx, cy+r*.38f, stroke);
            canvas.drawLine(cx, cy-r*.48f, cx-r*.28f, cy-r*.18f, stroke);
            canvas.drawLine(cx, cy-r*.48f, cx+r*.28f, cy-r*.18f, stroke);
        }
    }

    private void setKey(XKeycode key, boolean down) {
        if (down) xServer.injectKeyPress(key);
        else xServer.injectKeyRelease(key);
    }

    private void setMovementKeys(boolean w, boolean a, boolean s, boolean d) {
        if (w != keyW) { setKey(XKeycode.KEY_W, w); keyW = w; }
        if (a != keyA) { setKey(XKeycode.KEY_A, a); keyA = a; }
        if (s != keyS) { setKey(XKeycode.KEY_S, s); keyS = s; }
        if (d != keyD) { setKey(XKeycode.KEY_D, d); keyD = d; }
    }

    private void addFireRef() {
        if (fireRefs++ == 0) {
            xServer.injectPointerButtonPress(Pointer.Button.BUTTON_LEFT);
        }
    }

    private void removeFireRef() {
        if (fireRefs > 0 && --fireRefs == 0) {
            xServer.injectPointerButtonRelease(Pointer.Button.BUTTON_LEFT);
        }
    }

    private void addAdsRef() {
        if (adsRefs++ == 0) {
            xServer.injectPointerButtonPress(Pointer.Button.BUTTON_RIGHT);
        }
    }

    private void removeAdsRef() {
        if (adsRefs > 0 && --adsRefs == 0) {
            xServer.injectPointerButtonRelease(Pointer.Button.BUTTON_RIGHT);
        }
    }

    private void roleDown(int role) {
        switch (role) {
            case ROLE_FIRE: addFireRef(); break;
            case ROLE_ADS: addAdsRef(); break;
            case ROLE_ADSFIRE: addAdsRef(); addFireRef(); break;
            case ROLE_RELOAD: setKey(XKeycode.KEY_R, true); break;
            case ROLE_INTERACT: setKey(XKeycode.KEY_E, true); break;
            case ROLE_CROUCH: setKey(XKeycode.KEY_CTRL_L, true); break;
            case ROLE_SPRINT: setKey(XKeycode.KEY_SHIFT_L, true); break;
            case ROLE_GRENADE: setKey(XKeycode.KEY_G, true); break;
            case ROLE_SWAP: setKey(XKeycode.KEY_Q, true); break;
            case ROLE_PAUSE: setKey(XKeycode.KEY_ESC, true); break;
            case ROLE_JUMP: setKey(XKeycode.KEY_SPACE, true); break;
            case ROLE_KNIFE: setKey(XKeycode.KEY_F, true); break;
            case ROLE_PRONE: setKey(XKeycode.KEY_C, true); break;
            case ROLE_SLIDE: setKey(XKeycode.KEY_CTRL_L, true); break;
        }
    }

    private void roleUp(int role) {
        switch (role) {
            case ROLE_FIRE: removeFireRef(); break;
            case ROLE_ADS: removeAdsRef(); break;
            case ROLE_ADSFIRE: removeFireRef(); removeAdsRef(); break;
            case ROLE_RELOAD: setKey(XKeycode.KEY_R, false); break;
            case ROLE_INTERACT: setKey(XKeycode.KEY_E, false); break;
            case ROLE_CROUCH: setKey(XKeycode.KEY_CTRL_L, false); break;
            case ROLE_SPRINT: setKey(XKeycode.KEY_SHIFT_L, false); break;
            case ROLE_GRENADE: setKey(XKeycode.KEY_G, false); break;
            case ROLE_SWAP: setKey(XKeycode.KEY_Q, false); break;
            case ROLE_PAUSE: setKey(XKeycode.KEY_ESC, false); break;
            case ROLE_JUMP: setKey(XKeycode.KEY_SPACE, false); break;
            case ROLE_KNIFE: setKey(XKeycode.KEY_F, false); break;
            case ROLE_PRONE: setKey(XKeycode.KEY_C, false); break;
            case ROLE_SLIDE: setKey(XKeycode.KEY_CTRL_L, false); break;
        }
    }

    private void updateJoystick(float x, float y) {
        float nx = x / Math.max(1f, getWidth());
        float ny = y / Math.max(1f, getHeight());
        float aspect = getWidth() / Math.max(1f, (float)getHeight());
        float dx = (nx - JOY_X) * aspect;
        float dy = ny - JOY_Y;
        float len = (float)Math.sqrt(dx*dx + dy*dy);

        if (len > JOY_R && len > 0.0001f) {
            dx *= JOY_R / len;
            dy *= JOY_R / len;
        }

        float mx = dx / JOY_R;
        float my = dy / JOY_R;
        joyKnobX = JOY_X + (dx / aspect);
        joyKnobY = JOY_Y + dy;

        final float dead = 0.18f;
        setMovementKeys(
            my < -dead,
            mx < -dead,
            my > dead,
            mx > dead
        );
    }

    private void releaseJoystick() {
        joystickPointer = -1;
        joyKnobX = JOY_X;
        joyKnobY = JOY_Y;
        setMovementKeys(false, false, false, false);
    }

    private void releaseAll() {
        setMovementKeys(false, false, false, false);
        while (fireRefs > 0) removeFireRef();
        while (adsRefs > 0) removeAdsRef();

        for (int i = 0; i < pointerRoles.size(); i++) {
            int role = pointerRoles.valueAt(i);
            if (role != ROLE_FIRE && role != ROLE_ADS && role != ROLE_ADSFIRE &&
                role != ROLE_JOYSTICK && role != ROLE_LOOK) {
                roleUp(role);
            }
        }

        pointerRoles.clear();
        pointerButtonIndex.clear();
        releaseJoystick();
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        int action = event.getActionMasked();
        int ai = event.getActionIndex();
        int id = event.getPointerId(ai);
        int slot = id & 31;

        if (action == MotionEvent.ACTION_DOWN ||
            action == MotionEvent.ACTION_POINTER_DOWN) {
            float x = event.getX(ai);
            float y = event.getY(ai);
            int bi = buttonAt(x, y);
            int role;

            if (bi >= 0) {
                role = BUTTONS[bi].role;
                pointerButtonIndex.put(id, bi);
                roleDown(role);
            }
            else if (joystickPointer < 0 &&
                     x < getWidth() * 0.42f &&
                     y > getHeight() * 0.38f) {
                role = ROLE_JOYSTICK;
                joystickPointer = id;
                updateJoystick(x, y);
            }
            else {
                role = ROLE_LOOK;
            }

            pointerRoles.put(id, role);
            lastX[slot] = x;
            lastY[slot] = y;
            invalidate();
            return true;
        }

        if (action == MotionEvent.ACTION_MOVE) {
            for (int i = 0; i < event.getPointerCount(); i++) {
                int pid = event.getPointerId(i);
                int pslot = pid & 31;
                int role = pointerRoles.get(pid, ROLE_NONE);
                float x = event.getX(i);
                float y = event.getY(i);

                if (role == ROLE_JOYSTICK && pid == joystickPointer) {
                    updateJoystick(x, y);
                }
                else if (role == ROLE_LOOK) {
                    float sens = adsRefs > 0
                        ? TOUCH_LOOK_ADS
                        : TOUCH_LOOK_NORMAL;
                    int dx = Math.round((x - lastX[pslot]) * sens);
                    int dy = Math.round((y - lastY[pslot]) * sens);
                    if (dx != 0 || dy != 0) {
                        xServer.injectPointerMoveDelta(dx, dy);
                    }
                }

                lastX[pslot] = x;
                lastY[pslot] = y;
            }
            invalidate();
            return true;
        }

        if (action == MotionEvent.ACTION_UP ||
            action == MotionEvent.ACTION_POINTER_UP ||
            action == MotionEvent.ACTION_CANCEL) {
            if (action == MotionEvent.ACTION_CANCEL) {
                releaseAll();
                invalidate();
                return true;
            }

            int role = pointerRoles.get(id, ROLE_NONE);
            if (role == ROLE_JOYSTICK && id == joystickPointer) {
                releaseJoystick();
            }
            else if (role != ROLE_LOOK && role != ROLE_NONE) {
                roleUp(role);
            }

            pointerRoles.delete(id);
            pointerButtonIndex.delete(id);
            invalidate();
            return true;
        }

        return true;
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() != Sensor.TYPE_GYROSCOPE ||
            getWindowToken() == null) {
            return;
        }

        if (lastGyroTimestamp == 0L) {
            lastGyroTimestamp = event.timestamp;
            return;
        }

        float dt = (event.timestamp - lastGyroTimestamp) * 1.0e-9f;
        lastGyroTimestamp = event.timestamp;
        if (dt <= 0f || dt > 0.05f) return;

        float gx = event.values[0];
        float gy = event.values[1];
        float yawRate;
        float pitchRate;

        WindowManager wm =
            (WindowManager)getContext().getSystemService(Context.WINDOW_SERVICE);
        int rotation = wm != null && wm.getDefaultDisplay() != null
            ? wm.getDefaultDisplay().getRotation()
            : Surface.ROTATION_0;

        switch (rotation) {
            case Surface.ROTATION_90:
                yawRate = gx;
                pitchRate = -gy;
                break;
            case Surface.ROTATION_270:
                yawRate = -gx;
                pitchRate = gy;
                break;
            case Surface.ROTATION_180:
                yawRate = gy;
                pitchRate = gx;
                break;
            case Surface.ROTATION_0:
            default:
                yawRate = -gy;
                pitchRate = -gx;
                break;
        }

        float sensitivity = adsRefs > 0
            ? GYRO_ADS_PX_PER_RAD
            : GYRO_NORMAL_PX_PER_RAD;

        int dx = Math.round(yawRate * dt * sensitivity);
        int dy = Math.round(pitchRate * dt * sensitivity);
        if (dx != 0 || dy != 0) {
            xServer.injectPointerMoveDelta(dx, dy);
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {}
}
'''
(java / "XzielMobileOverlay.java").write_text(overlay_java, encoding="utf-8")


xserver = java / "XServerDisplayActivity.java"
text = xserver.read_text(encoding="utf-8")

# XZIEL direct boot must not go through explorer -> winhandler. The Android
# x86 bridge has proven the direct Win64 runtime can stay alive under Wine.
# Bypass both explorer/winhandler and the NSIS one-file wrapper. Override our private
# direct-boot path; normal Winlator launches keep the upstream start command.
guest_anchor = '            String guestExecutable = "wine explorer /desktop="+desktopName+","+xServer.screenInfo+" "+getWineStartCommand();'
if guest_anchor not in text:
    raise SystemExit("Could not find XServer guestExecutable wine/explorer anchor")
direct_override = (
    guest_anchor + "\n" +
    '            if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {\n' +
    r'                guestExecutable = "wine C:\\XZIEL\\Xziel-Nacht.exe --xziel-root C:\\XZIEL --xziel-map xziel_nacht_bo3";' + "\n" +
    '                Log.i("XZIEL-HYBRID", "DIRECT_NACHT_WINE_LAUNCH command=" + guestExecutable);\n' +
    '            }'
)
text = text.replace(guest_anchor, direct_override, 1)
overlay_anchor = "        setupUI();\n"
overlay_insert = '''        setupUI();
        if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {
            inputControlsView.setVisibility(android.view.View.GONE);
            touchpadView.setVisibility(android.view.View.GONE);
            android.widget.FrameLayout gameRoot = findViewById(R.id.FLXServerDisplay);
            XzielMobileOverlay xzielOverlay = new XzielMobileOverlay(this, xServer);
            gameRoot.addView(xzielOverlay);
        }
'''
if overlay_anchor not in text:
    raise SystemExit("Could not find XServer setupUI anchor")
text = text.replace(overlay_anchor, overlay_insert, 1)

if "import android.util.Log;" not in text:
    text = text.replace("import android.os.Bundle;\n", "import android.os.Bundle;\nimport android.util.Log;\n", 1)
if "import android.os.Build;" not in text:
    text = text.replace("import android.os.Bundle;\n", "import android.os.Bundle;\nimport android.os.Build;\n", 1)

activity_anchor = '''        ForegroundService.startSession(this);
'''
activity_insert = '''        ForegroundService.startSession(this);
        if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {
            Log.i("XZIEL-HYBRID", "XSERVER_ACTIVITY_START");
        }
'''
if activity_anchor not in text:
    raise SystemExit("Could not find XServer activity boot anchor")
text = text.replace(activity_anchor, activity_insert, 1)

env_anchor = '''            setupXEnvironment();
        });
'''
env_insert = '''            if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {
                Log.i("XZIEL-HYBRID", "XSERVER_ENV_SETUP_BEGIN");
            }
            setupXEnvironment();
            if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {
                Log.i("XZIEL-HYBRID", "XSERVER_ENVIRONMENT_STARTED");
            }
        });
'''
if env_anchor not in text:
    raise SystemExit("Could not find XServer environment anchor")
text = text.replace(env_anchor, env_insert, 1)

stage_anchor = '''                setupWineSystemFiles();
                extractGraphicsDriverFiles();
                changeWineAudioDriver();
'''
stage_insert = '''                boolean xzielDirectBootStages = getIntent().getBooleanExtra("xziel_direct_boot", false);
                if (xzielDirectBootStages) Log.i("XZIEL-HYBRID", "WINE_SYSTEM_FILES_BEGIN");
                setupWineSystemFiles();
                if (xzielDirectBootStages) Log.i("XZIEL-HYBRID", "WINE_SYSTEM_FILES_GREEN");

                if (xzielDirectBootStages) Log.i("XZIEL-HYBRID", "GRAPHICS_EXTRACT_BEGIN driver=" + graphicsDriver[0] + "," + graphicsDriver[1] + " dx=" + dxwrapper);
                extractGraphicsDriverFiles();
                if (xzielDirectBootStages) Log.i("XZIEL-HYBRID", "GRAPHICS_EXTRACT_GREEN");

                if (xzielDirectBootStages) Log.i("XZIEL-HYBRID", "AUDIO_DRIVER_BEGIN driver=" + audioDriver);
                changeWineAudioDriver();
                if (xzielDirectBootStages) Log.i("XZIEL-HYBRID", "AUDIO_DRIVER_GREEN");
'''
if stage_anchor not in text:
    raise SystemExit("Could not find XServer staged boot anchor")
text = text.replace(stage_anchor, stage_insert, 1)

window_anchor = '''                if (!flags[0] && window.isRenderable() && !window.getClassName().isEmpty()) {
                    xServerView.getRenderer().setCursorVisible(true);
'''
window_insert = '''                if (!flags[0] && window.isRenderable() && !window.getClassName().isEmpty()) {
                    if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {
                        Log.i("XZIEL-HYBRID", "FIRST_RENDERABLE_WINDOW class=" + window.getClassName());
                    }
                    xServerView.getRenderer().setCursorVisible(true);
'''
if window_anchor not in text:
    raise SystemExit("Could not find XServer first-window anchor")
text = text.replace(window_anchor, window_insert, 1)

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

# Direct-boot guest process diagnostics v2: keep stdout/stderr visible in logcat.
debug_anchor = '''        ProcessHelper.removeAllDebugCallbacks();
        boolean enableLogs = preferences.getBoolean("enable_wine_debug", false) || preferences.getInt("box64_logs", 0) >= 1;
'''
debug_insert = '''        ProcessHelper.removeAllDebugCallbacks();
        if (getIntent().getBooleanExtra("xziel_direct_boot", false)) {
            ProcessHelper.addDebugCallback((line) -> Log.i("XZIEL-GUEST", line));
            Log.i("XZIEL-HYBRID", "GUEST_DEBUG_CAPTURE_ENABLED");
        }
        boolean enableLogs = preferences.getBoolean("enable_wine_debug", false) || preferences.getInt("box64_logs", 0) >= 1;
'''
if debug_anchor not in text:
    raise SystemExit("Could not find ProcessHelper debug anchor")
text = text.replace(debug_anchor, debug_insert, 1)

termination_anchor = '''        guestProgramLauncherComponent.setTerminationCallback((status) -> exit());
'''
termination_insert = '''        guestProgramLauncherComponent.setTerminationCallback((status) -> {
            boolean xzielX86KeepAlive =
                    getIntent().getBooleanExtra("xziel_direct_boot", false) &&
                    Build.SUPPORTED_ABIS != null &&
                    Build.SUPPORTED_ABIS.length > 0 &&
                    Build.SUPPORTED_ABIS[0].startsWith("x86");
            if (xzielX86KeepAlive) {
                Log.i("XZIEL-HYBRID", "X86_GUEST_EXIT_KEEPALIVE status=" + status);
            }
            else {
                exit();
            }
        });
'''
if termination_anchor not in text:
    raise SystemExit("Could not find XServer guest termination callback")
text = text.replace(termination_anchor, termination_insert, 1)

xserver.write_text(text, encoding="utf-8")

# Instrument the guest launcher with command, PID and exit status.
guest_launcher = java / "xenvironment/components/GuestProgramLauncherComponent.java"
gtext = guest_launcher.read_text(encoding="utf-8")
if "import android.util.Log;" not in gtext:
    gtext = gtext.replace("import android.os.Process;\n", "import android.os.Process;\nimport android.util.Log;\n", 1)
if "import android.os.Build;" not in gtext:
    gtext = gtext.replace("import android.os.Process;\n", "import android.os.Process;\nimport android.os.Build;\n", 1)
if "import java.util.concurrent.CountDownLatch;" not in gtext:
    gtext = gtext.replace(
        "import android.util.Log;\n",
        "import android.util.Log;\nimport java.util.concurrent.CountDownLatch;\nimport java.util.concurrent.TimeUnit;\n",
        1,
    )

# Keep a dedicated foreground wineserver alive for XZIEL x86-bridge launches.
# XServer initialization recreates rootfs/tmp; starting the server here ensures
# its socket is created only after that reset, immediately before Wine/Nacht.
class_field_anchor = '''    private static int pid = -1;
'''
class_field_insert = '''    private static int pid = -1;
    private static int xzielWineserverPid = -1;
'''
if class_field_anchor not in gtext:
    raise SystemExit("Could not find GuestProgramLauncher pid field anchor")
gtext = gtext.replace(class_field_anchor, class_field_insert, 1)

stop_method_anchor = '''            if (pid != -1) {
                Process.killProcess(pid);
                pid = -1;
            }
'''
stop_method_insert = '''            if (pid != -1) {
                Process.killProcess(pid);
                pid = -1;
            }
            if (xzielWineserverPid != -1) {
                Process.killProcess(xzielWineserverPid);
                xzielWineserverPid = -1;
                Log.i("XZIEL-HYBRID", "RUNTIME_WINESERVER_STOPPED");
            }
'''
if stop_method_anchor not in gtext:
    raise SystemExit("Could not find GuestProgramLauncher stop anchor")
gtext = gtext.replace(stop_method_anchor, stop_method_insert, 1)

ld_anchor = '''        envVars.put("LD_LIBRARY_PATH", rootFS.getLibDir().getPath());
        envVars.put("BOX64_LD_LIBRARY_PATH", rootDir+"/lib/x86_64-linux-gnu");
'''
ld_insert = '''        boolean xzielX86Bridge =
                Build.SUPPORTED_ABIS != null &&
                Build.SUPPORTED_ABIS.length > 0 &&
                Build.SUPPORTED_ABIS[0].startsWith("x86");
        if (xzielX86Bridge) {
            envVars.put("LD_LIBRARY_PATH", "");
            Log.i("XZIEL-HYBRID", "X86_BRIDGE_LD_LIBRARY_PATH_SANITIZED");
        }
        else {
            envVars.put("LD_LIBRARY_PATH", rootFS.getLibDir().getPath());
        }
        envVars.put("BOX64_LD_LIBRARY_PATH", rootDir+"/lib/x86_64-linux-gnu");
'''
if ld_anchor not in gtext:
    raise SystemExit("Could not find GuestProgramLauncher LD_LIBRARY_PATH anchor")
gtext = gtext.replace(ld_anchor, ld_insert, 1)

post_env_anchor = '''        if (this.envVars != null) envVars.putAll(this.envVars);

        File shmDir = new File(rootDir, "/tmp/shm");
'''
post_env_insert = '''        if (this.envVars != null) envVars.putAll(this.envVars);

        if (xzielX86Bridge) {
            envVars.remove("LD_LIBRARY_PATH");
            envVars.put("XZIEL_GUEST_CAPTURE_PATH", rootDir+"/tmp/xziel-guest-output.log");
            envVars.put("BOX64_DYNAREC", "0");
            envVars.put("BOX64_NOBANNER", "1");
            envVars.put("BOX64_LOG", "0");
            envVars.put("BOX64_DLSYM_ERROR", "0");
            envVars.put("BOX64_SHOWSEGV", "1");
            envVars.put("WINEDEBUG", "-all");
            envVars.put("WINEESYNC", "0");
            envVars.put("WINEFSYNC", "0");
            Log.i("XZIEL-HYBRID", "X86_BRIDGE_HOST_LD_LIBRARY_PATH_REMOVED_FINAL");
            Log.i("XZIEL-HYBRID", "X86_BRIDGE_RUNTIME_PROFILE dynarec=0 box64=0 esync=0 fsync=0 freetype=native-bionic wine=quiet");
            Log.i("XZIEL-HYBRID", "GUEST_FILE_CAPTURE path=" + rootDir + "/tmp/xziel-guest-output.log");
            Log.i("XZIEL-HYBRID", "GUEST_ENV prefix=" + envVars.get("WINEPREFIX") +
                    " path=" + envVars.get("PATH") +
                    " box64ld=" + envVars.get("BOX64_LD_LIBRARY_PATH"));
        }

        File shmDir = new File(rootDir, "/tmp/shm");
'''
if post_env_anchor not in gtext:
    raise SystemExit("Could not find GuestProgramLauncher post-env anchor")
gtext = gtext.replace(post_env_anchor, post_env_insert, 1)

guest_exec_anchor = '''        String command = rootDir+"/usr/local/bin/box64 "+guestExecutable;

        return ProcessHelper.exec(command, envVars, rootDir, (status) -> {
            synchronized (lock) {
                pid = -1;
            }
            if (terminationCallback != null) terminationCallback.call(status);
        });
'''
guest_exec_insert = '''        boolean xzielDirectNacht =
                xzielX86Bridge &&
                guestExecutable != null &&
                guestExecutable.contains("Xziel-Nacht.exe");
        if (xzielDirectNacht) {
            // Android now installs the validated VFS natively and launches the
            // small Win64 runtime directly. Keep the actual game launch quiet;
            // CI retains external process/socket probes.
            envVars.put("BOX64_LOG", "0");
            envVars.put("BOX64_NOBANNER", "1");
            envVars.remove("BOX64_DLSYM_ERROR");
            envVars.remove("BOX64_SHOWSEGV");
            envVars.remove("BOX64_DYNAREC_MISSING");
            envVars.remove("BOX64_TRACE_FILE");
            envVars.put("WINEDEBUG", "-all");
            Log.i("XZIEL-HYBRID", "DIRECT_NACHT_QUIET_BOOT box64_log=0 wine_debug=off");

            String guestCapturePath = envVars.get("XZIEL_GUEST_CAPTURE_PATH");
            if (guestCapturePath != null && !guestCapturePath.isEmpty()) {
                envVars.put("XZIEL_GUEST_CAPTURE_PATH", rootDir+"/tmp/xziel-wineserver-runtime.log");
            }

            String wineserverCommand =
                    rootDir+"/usr/local/bin/box64 " +
                    rootDir+rootFS.getWinePath()+"/bin/wineserver -f -p";
            xzielWineserverPid = ProcessHelper.exec(wineserverCommand, envVars, rootDir, (status) -> {
                Log.i("XZIEL-HYBRID", "RUNTIME_WINESERVER_EXIT status=" + status);
                xzielWineserverPid = -1;
            });
            Log.i("XZIEL-HYBRID", "RUNTIME_WINESERVER_STARTED pid=" + xzielWineserverPid +
                    " command=" + wineserverCommand);

            // Gate clients on the actual Wine socket, not an arbitrary delay.
            // Starting cmd.exe before server-*/socket exists races the Bionic
            // Box64 wineserver and reproduces the status=1 failure seen in
            // smoke #105.
            boolean xzielWineserverSocketReady = false;
            File xzielTmpDir = new File(rootDir, "tmp");
            for (int readyAttempt = 0; readyAttempt < 100 && !xzielWineserverSocketReady; readyAttempt++) {
                File[] wineRoots = xzielTmpDir.listFiles();
                if (wineRoots != null) {
                    for (File wineRoot : wineRoots) {
                        if (!wineRoot.isDirectory() || !wineRoot.getName().startsWith(".wine-")) continue;
                        File[] serverDirs = wineRoot.listFiles();
                        if (serverDirs == null) continue;
                        for (File serverDir : serverDirs) {
                            if (!serverDir.isDirectory() || !serverDir.getName().startsWith("server-")) continue;
                            File socket = new File(serverDir, "socket");
                            if (socket.exists()) {
                                xzielWineserverSocketReady = true;
                                Log.i("XZIEL-HYBRID", "RUNTIME_WINESERVER_SOCKET path=" + socket.getAbsolutePath());
                                break;
                            }
                        }
                        if (xzielWineserverSocketReady) break;
                    }
                }
                if (!xzielWineserverSocketReady) {
                    if (xzielWineserverPid <= 0) break;
                    try {
                        Thread.sleep(100);
                    }
                    catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
            Log.i("XZIEL-HYBRID", "RUNTIME_WINESERVER_SOCKET_GATE ready=" +
                    xzielWineserverSocketReady + " pid=" + xzielWineserverPid);

            // Do not gate Nacht on an arbitrary sleep. The x86->ARM bridge
            // only became reliable after a real Windows client completed
            // against the post-XServer foreground wineserver. Reproduce that
            // proven sequence in the launcher itself: server -> cmd.exe /c ver
            // -> Nacht.
            if (guestCapturePath != null && !guestCapturePath.isEmpty()) {
                envVars.put("XZIEL_GUEST_CAPTURE_PATH", rootDir+"/tmp/xziel-warmup-runtime.log");
            }

            String warmupCommand =
                    rootDir+"/usr/local/bin/box64 " +
                    rootDir+rootFS.getWinePath()+"/bin/wine " +
                    "C:\\\\windows\\\\system32\\\\cmd.exe /c ver";
            CountDownLatch warmupDone = new CountDownLatch(1);
            int[] warmupStatus = new int[] {Integer.MIN_VALUE};
            int warmupPid = ProcessHelper.exec(warmupCommand, envVars, rootDir, (status) -> {
                warmupStatus[0] = status;
                Log.i("XZIEL-HYBRID", "RUNTIME_WARMUP_EXIT status=" + status);
                warmupDone.countDown();
            });
            Log.i("XZIEL-HYBRID", "RUNTIME_WARMUP_STARTED pid=" + warmupPid +
                    " command=" + warmupCommand);

            boolean warmupFinished = false;
            try {
                warmupFinished = warmupDone.await(180, TimeUnit.SECONDS);
            }
            catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                Log.i("XZIEL-HYBRID", "RUNTIME_WARMUP_INTERRUPTED");
            }

            if (!warmupFinished && warmupPid > 0) {
                Process.killProcess(warmupPid);
                Log.i("XZIEL-HYBRID", "RUNTIME_WARMUP_TIMEOUT pid=" + warmupPid);
            }
            Log.i("XZIEL-HYBRID", "RUNTIME_WARMUP_GATE finished=" + warmupFinished +
                    " status=" + warmupStatus[0] +
                    " wineserverPid=" + xzielWineserverPid);

            if (guestCapturePath != null && !guestCapturePath.isEmpty()) {
                envVars.put("XZIEL_GUEST_CAPTURE_PATH", guestCapturePath);
            }

            // Keep the warmup diagnostic, then launch the direct Win64 runtime
            // on the quiet fast path.
            envVars.put("BOX64_LOG", "0");
            envVars.put("BOX64_NOBANNER", "1");
            envVars.remove("BOX64_DLSYM_ERROR");
            envVars.remove("BOX64_SHOWSEGV");
            envVars.put("WINEDEBUG", "-all");
            Log.i("XZIEL-HYBRID", "NACHT_FASTPATH_TRACE_OFF box64=0 wine=-all");
        }

        String command = rootDir+"/usr/local/bin/box64 "+guestExecutable;
        Log.i("XZIEL-HYBRID", "GUEST_EXEC command=" + command);

        int launchedPid = ProcessHelper.exec(command, envVars, rootDir, (status) -> {
            Log.i("XZIEL-HYBRID", "GUEST_EXIT status=" + status);
            synchronized (lock) {
                pid = -1;
            }
            if (terminationCallback != null) terminationCallback.call(status);
        });
        Log.i("XZIEL-HYBRID", "GUEST_PID pid=" + launchedPid);
        return launchedPid;
'''
if guest_exec_anchor not in gtext:
    raise SystemExit("Could not find GuestProgramLauncher exec anchor")
gtext = gtext.replace(guest_exec_anchor, guest_exec_insert, 1)
guest_launcher.write_text(gtext, encoding="utf-8")

# Stop silently swallowing ProcessBuilder launch exceptions.
process_helper = java / "core/ProcessHelper.java"
ptext = process_helper.read_text(encoding="utf-8")
if "import android.util.Log;" not in ptext:
    ptext = ptext.replace("import android.system.OsConstants;\n", "import android.system.OsConstants;\nimport android.util.Log;\n", 1)

process_redirect_anchor = '''            ProcessBuilder processBuilder = (new ProcessBuilder(splitCommand(command))).directory(workingDir);
            if (debugCallbacks.isEmpty()) processBuilder.redirectOutput(new File("/dev/null")).redirectErrorStream(true);

            Map<String, String> environment = processBuilder.environment();
'''
process_redirect_insert = '''            ProcessBuilder processBuilder = (new ProcessBuilder(splitCommand(command))).directory(workingDir);
            String xzielCapturePath = envVars != null ? envVars.get("XZIEL_GUEST_CAPTURE_PATH") : null;
            if (xzielCapturePath != null && !xzielCapturePath.isEmpty()) {
                File captureFile = new File(xzielCapturePath);
                File captureParent = captureFile.getParentFile();
                if (captureParent != null && !captureParent.isDirectory()) captureParent.mkdirs();
                processBuilder.redirectOutput(captureFile).redirectErrorStream(true);
                Log.i("XZIEL-PROCESS", "guest output redirected=" + captureFile.getPath());
            }
            else if (debugCallbacks.isEmpty()) {
                processBuilder.redirectOutput(new File("/dev/null")).redirectErrorStream(true);
            }

            Map<String, String> environment = processBuilder.environment();
'''
if process_redirect_anchor not in ptext:
    raise SystemExit("Could not find ProcessHelper redirect anchor")
ptext = ptext.replace(process_redirect_anchor, process_redirect_insert, 1)

process_reader_anchor = '''            if (!debugCallbacks.isEmpty()) {
                createDebugThread(process.getInputStream());
                createDebugThread(process.getErrorStream());
            }
'''
process_reader_insert = '''            if (!debugCallbacks.isEmpty() && (xzielCapturePath == null || xzielCapturePath.isEmpty())) {
                createDebugThread(process.getInputStream());
                createDebugThread(process.getErrorStream());
            }
'''
if process_reader_anchor not in ptext:
    raise SystemExit("Could not find ProcessHelper reader anchor")
ptext = ptext.replace(process_reader_anchor, process_reader_insert, 1)

process_catch_anchor = '''        catch (Exception e) {}
        return pid;
'''
process_catch_insert = '''        catch (Exception e) {
            Log.e("XZIEL-PROCESS", "exec failed command=" + command, e);
        }
        return pid;
'''
if process_catch_anchor not in ptext:
    raise SystemExit("Could not find ProcessHelper silent catch anchor")
ptext = ptext.replace(process_catch_anchor, process_catch_insert, 1)
process_helper.write_text(ptext, encoding="utf-8")

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
if '<uses-feature android:name="android.hardware.sensor.gyroscope"' not in text:
    text = text.replace(
        '<uses-permission android:name="android.permission.INTERNET"/>',
        '<uses-feature android:name="android.hardware.sensor.gyroscope" android:required="false"/>\n    <uses-permission android:name="android.permission.INTERNET"/>',
        1,
    )
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

# Preserve Winlator's internal Java package names, but move runtime sandbox paths
# to an equal-length XZIEL applicationId so ELF/RPATH strings can be rewritten
# without shifting binary offsets.
runtime_old_pkg = "com.winlator"
runtime_new_pkg = "com.xzielapp"
if len(runtime_old_pkg.encode("ascii")) != len(runtime_new_pkg.encode("ascii")):
    raise SystemExit("XZIEL runtime package ids must have equal byte length")

runtime_old_path = "/data/data/" + runtime_old_pkg
runtime_new_path = "/data/data/" + runtime_new_pkg
runtime_old_provider = runtime_old_pkg + ".FileProvider"
runtime_new_provider = runtime_new_pkg + ".FileProvider"

runtime_source_files = [
    java / "core/AppUtils.java",
    java / "core/FileUtils.java",
    app / "src/main/cpp/winlator/include/winlator.h",
    app / "src/main/cpp/vortekrenderer/include/vortek.h",
    app / "src/main/cpp/gladiorenderer/include/gladio.h",
]
runtime_source_replacements = 0
for runtime_file in runtime_source_files:
    if not runtime_file.is_file():
        raise SystemExit(f"Missing runtime package source file: {runtime_file}")
    runtime_text = runtime_file.read_text(encoding="utf-8")
    runtime_before = runtime_text
    runtime_text = runtime_text.replace(runtime_old_path, runtime_new_path)
    runtime_text = runtime_text.replace(runtime_old_provider, runtime_new_provider)
    if runtime_text != runtime_before:
        runtime_source_replacements += (
            runtime_before.count(runtime_old_path)
            + runtime_before.count(runtime_old_provider)
        )
        runtime_file.write_text(runtime_text, encoding="utf-8")

if runtime_source_replacements < 5:
    raise SystemExit(
        f"Expected runtime package hardcodes were not all rewritten: {runtime_source_replacements}"
    )
print(
    "XZIEL_RUNTIME_PACKAGE_SOURCE_GREEN "
    f"old={runtime_old_pkg} new={runtime_new_pkg} replacements={runtime_source_replacements}"
)

gradle = app / "build.gradle"
text = gradle.read_text(encoding="utf-8")
text = text.replace("applicationId 'com.winlator'", "applicationId 'com.xzielapp'")
text = text.replace('versionCode 33', 'versionCode 1')
text = text.replace('versionName "11.2"', 'versionName "0.1-nacht-hybrid"')

anchor = "    lintOptions {\n"
if anchor in text and "aaptOptions" not in text:
    text = text.replace(
        anchor,
        "    aaptOptions {\n        noCompress 'exe', 'dll', 'zip', 'tzst'\n    }\n\n" + anchor,
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
    "Modifications: direct boot, XZIEL branding, native VFS install, direct Win64 runtime launch, hidden container UI.\n",
    encoding="utf-8",
)

print("XZIEL_NACHT_WINLATOR_DIRECT_PATCH_OK")
