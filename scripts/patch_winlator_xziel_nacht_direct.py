#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("usage: patch_winlator_xziel_nacht_direct.py <winlator-app-root> <exe-bytes> <exe-sha256>")

root = Path(sys.argv[1]).resolve()
game_bytes = int(sys.argv[2])
game_sha256 = sys.argv[3].strip().lower()
if game_bytes < 800_000_000 or len(game_sha256) != 64:
    raise SystemExit("invalid Nacht EXE identity")
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
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.concurrent.Executors;

public class XzielBootActivity extends AppCompatActivity {
    private static final String TAG = "XZIEL-HYBRID";
    private TextView status;

    private static final String GAME_ASSET = "nacht-onefile.exe";
    private static final String GAME_DIR = "XZIEL";
    private static final String GAME_EXE = "Nacht-Chronicles-XZIEL.exe";
    private static final long GAME_BYTES = __XZIEL_GAME_BYTES__L;
    private static final String GAME_SHA256 =
        "__XZIEL_GAME_SHA256__";
    private static final String PACKAGE_MARKER = ".xziel-nacht-onefile-v1";

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
                File marker = new File(gameDir, PACKAGE_MARKER);

                boolean ready =
                    exe.isFile() &&
                    exe.length() == GAME_BYTES &&
                    marker.isFile() &&
                    GAME_SHA256.equals(FileUtils.readString(marker).trim());

                if (!ready) {
                    Log.i(TAG, "EXE_INSTALL_BEGIN");
                    FileUtils.delete(gameDir);
                    if (!gameDir.mkdirs() && !gameDir.isDirectory()) {
                        throw new RuntimeException("could not create game directory");
                    }

                    installExeTransactional(exe);

                    if (!exe.isFile() || exe.length() != GAME_BYTES) {
                        throw new RuntimeException("installed EXE size mismatch");
                    }
                    FileUtils.writeString(marker, GAME_SHA256 + "\n");
                    Log.i(TAG, "EXE_INSTALL_GREEN bytes=" + exe.length());
                }
                else {
                    Log.i(TAG, "EXE_ALREADY_READY bytes=" + exe.length());
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
boot_java = boot_java.replace("__XZIEL_GAME_BYTES__", str(game_bytes)).replace("__XZIEL_GAME_SHA256__", game_sha256)
(java / "XzielBootActivity.java").write_text(boot_java, encoding="utf-8")

overlay_java = r'''package com.winlator;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.util.SparseIntArray;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;

import com.winlator.xserver.Pointer;
import com.winlator.xserver.XKeycode;
import com.winlator.xserver.XServer;

/*
 * XZIEL mobile overlay for the EXE-in-APK path.
 * Deliberately bypasses Winlator's profile/editor UI: the player sees only
 * the game plus XZIEL's own touch skin.
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

    private static final float JOY_X = 0.155f;
    private static final float JOY_Y = 0.785f;
    private static final float JOY_R = 0.118f;

    private static final float TOUCH_LOOK_NORMAL = 1.18f;
    private static final float TOUCH_LOOK_ADS = 0.72f;

    // Separate walking/hip and ADS/scope gyro sensitivities.
    private static final float GYRO_NORMAL_PX_PER_RAD = 920.0f;
    private static final float GYRO_ADS_PX_PER_RAD = 520.0f;

    private final XServer xServer;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final SparseIntArray pointerRoles = new SparseIntArray();
    private final SparseIntArray pointerButtonIndex = new SparseIntArray();
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
            this.role = role; this.x = x; this.y = y; this.r = r;
        }
    }

    private static final ButtonDef[] BUTTONS = new ButtonDef[] {
        new ButtonDef(ROLE_FIRE,     0.905f, 0.690f, 0.078f),
        new ButtonDef(ROLE_ADSFIRE,  0.805f, 0.575f, 0.064f),
        new ButtonDef(ROLE_ADS,      0.910f, 0.485f, 0.058f),
        new ButtonDef(ROLE_RELOAD,   0.705f, 0.505f, 0.052f),
        new ButtonDef(ROLE_INTERACT, 0.690f, 0.690f, 0.054f),
        new ButtonDef(ROLE_CROUCH,   0.820f, 0.835f, 0.052f),
        new ButtonDef(ROLE_SPRINT,   0.150f, 0.585f, 0.052f),
        new ButtonDef(ROLE_GRENADE,  0.705f, 0.835f, 0.050f),
        new ButtonDef(ROLE_SWAP,     0.910f, 0.845f, 0.050f),
        new ButtonDef(ROLE_JUMP,     0.795f, 0.710f, 0.050f),
        new ButtonDef(ROLE_KNIFE,    0.610f, 0.735f, 0.048f),
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

        sensorManager = (SensorManager)context.getSystemService(Context.SENSOR_SERVICE);
        gyroscope = sensorManager != null
            ? sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
            : null;

        xServer.setRelativeMouseMovement(true);
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
        paint.setColor(Color.argb(48, 2, 2, 2));
        canvas.drawCircle(cx, cy, r, paint);

        stroke.setStrokeWidth(Math.max(2f, r * 0.055f));
        stroke.setColor(Color.argb(75, 240, 240, 240));
        canvas.drawCircle(cx, cy, r * 0.92f, stroke);

        drawSmear(canvas, cx, cy, r, joystickPointer >= 0);

        float kx = px(joyKnobX);
        float ky = py(joyKnobY);
        paint.setColor(Color.argb(105, 8, 8, 8));
        canvas.drawCircle(kx, ky, r * 0.36f, paint);
        stroke.setStrokeWidth(Math.max(2f, r * 0.045f));
        stroke.setColor(Color.argb(130, 245, 245, 245));
        canvas.drawCircle(kx, ky, r * 0.36f, stroke);
    }

    private void drawSmear(Canvas canvas, float cx, float cy, float r, boolean pressed) {
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(pressed
            ? Color.argb(118, 14, 12, 5)
            : Color.argb(72, 3, 3, 3));

        path.reset();
        for (int i = 0; i < 18; i++) {
            double a = (Math.PI * 2.0 * i) / 18.0;
            float wobble = 0.83f + ((i * 37) % 9) * 0.018f;
            float x = cx + (float)Math.cos(a) * r * wobble;
            float y = cy + (float)Math.sin(a) * r * wobble;
            if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
        }
        path.close();
        canvas.drawPath(path, paint);

        // Faint black handprint/zombie-hand texture, not a solid card.
        paint.setColor(Color.argb(pressed ? 90 : 58, 0, 0, 0));
        canvas.save();
        canvas.rotate(-18f, cx, cy);
        canvas.drawOval(new RectF(cx-r*.23f, cy-r*.12f, cx+r*.22f, cy+r*.36f), paint);
        float fy = cy-r*.40f;
        for (int i = 0; i < 5; i++) {
            float fx = cx + (i-2) * r*.105f;
            float fr = r * (i == 2 ? .095f : .078f);
            canvas.drawCircle(fx, fy - Math.abs(i-2)*r*.035f, fr, paint);
        }
        canvas.restore();
    }

    private void drawButton(Canvas canvas, ButtonDef b, boolean pressed) {
        float cx = px(b.x);
        float cy = py(b.y);
        float r = b.r * getHeight();

        drawSmear(canvas, cx, cy, r, pressed);

        stroke.setStrokeWidth(Math.max(2f, r * (pressed ? .085f : .055f)));
        stroke.setColor(pressed
            ? Color.argb(235, 244, 200, 61)
            : Color.argb(118, 242, 246, 248));
        canvas.drawCircle(cx, cy, r * .88f, stroke);

        drawIcon(canvas, b.role, cx, cy, r * .58f, pressed);
    }

    private void drawIcon(Canvas canvas, int role, float cx, float cy, float s, boolean pressed) {
        stroke.setStrokeWidth(Math.max(3f, s * .11f));
        stroke.setColor(pressed
            ? Color.rgb(255, 244, 194)
            : Color.rgb(245, 247, 248));
        paint.setColor(stroke.getColor());
        paint.setStyle(Paint.Style.FILL);

        switch (role) {
            case ROLE_FIRE:
                canvas.save();
                canvas.rotate(-38f, cx, cy);
                canvas.drawRoundRect(new RectF(cx-s*.15f, cy-s*.58f, cx+s*.15f, cy+s*.54f), s*.10f, s*.10f, paint);
                canvas.drawRect(cx-s*.22f, cy-s*.60f, cx+s*.22f, cy-s*.44f, paint);
                canvas.restore();
                break;

            case ROLE_ADS:
                canvas.drawCircle(cx, cy, s*.42f, stroke);
                canvas.drawLine(cx-s*.72f, cy, cx-s*.34f, cy, stroke);
                canvas.drawLine(cx+s*.34f, cy, cx+s*.72f, cy, stroke);
                canvas.drawLine(cx, cy-s*.72f, cx, cy-s*.34f, stroke);
                canvas.drawLine(cx, cy+s*.34f, cx, cy+s*.72f, stroke);
                canvas.drawCircle(cx, cy, s*.06f, paint);
                break;

            case ROLE_ADSFIRE:
                canvas.drawCircle(cx-s*.08f, cy-s*.05f, s*.38f, stroke);
                canvas.drawLine(cx-s*.72f, cy-s*.05f, cx-s*.40f, cy-s*.05f, stroke);
                canvas.drawLine(cx+s*.24f, cy-s*.05f, cx+s*.56f, cy-s*.05f, stroke);
                canvas.save();
                canvas.rotate(-35f, cx+s*.44f, cy+s*.42f);
                canvas.drawRoundRect(new RectF(cx+s*.34f, cy+s*.10f, cx+s*.54f, cy+s*.63f), s*.07f, s*.07f, paint);
                canvas.restore();
                break;

            case ROLE_RELOAD:
                path.reset();
                path.addArc(new RectF(cx-s*.48f, cy-s*.48f, cx+s*.48f, cy+s*.48f), -55f, 275f);
                canvas.drawPath(path, stroke);
                path.reset();
                path.moveTo(cx+s*.48f, cy-s*.18f);
                path.lineTo(cx+s*.72f, cy-s*.32f);
                path.lineTo(cx+s*.62f, cy-s*.02f);
                path.close();
                canvas.drawPath(path, paint);
                break;

            case ROLE_INTERACT:
                // Open-hand glyph.
                canvas.drawOval(new RectF(cx-s*.25f, cy-s*.05f, cx+s*.28f, cy+s*.45f), paint);
                for (int i=0;i<4;i++) {
                    float fx = cx + (i-1.5f)*s*.14f;
                    canvas.drawRoundRect(new RectF(fx-s*.05f, cy-s*.50f, fx+s*.05f, cy+s*.05f), s*.05f, s*.05f, paint);
                }
                break;

            case ROLE_CROUCH:
                canvas.drawLine(cx-s*.48f, cy-s*.18f, cx, cy+s*.30f, stroke);
                canvas.drawLine(cx, cy+s*.30f, cx+s*.48f, cy-s*.18f, stroke);
                canvas.drawLine(cx-s*.36f, cy+s*.48f, cx+s*.36f, cy+s*.48f, stroke);
                break;

            case ROLE_SPRINT:
                canvas.drawLine(cx-s*.55f, cy+s*.26f, cx+s*.12f, cy-s*.34f, stroke);
                canvas.drawLine(cx+s*.08f, cy-s*.34f, cx+s*.52f, cy-s*.10f, stroke);
                canvas.drawLine(cx-s*.22f, cy+s*.48f, cx+s*.44f, cy+s*.48f, stroke);
                break;

            case ROLE_GRENADE:
                canvas.drawCircle(cx, cy+s*.10f, s*.36f, stroke);
                canvas.drawLine(cx+s*.12f, cy-s*.28f, cx+s*.30f, cy-s*.54f, stroke);
                canvas.drawLine(cx+s*.30f, cy-s*.54f, cx+s*.54f, cy-s*.42f, stroke);
                break;

            case ROLE_SWAP:
                canvas.drawLine(cx-s*.55f, cy-s*.20f, cx+s*.42f, cy-s*.20f, stroke);
                canvas.drawLine(cx+s*.42f, cy-s*.20f, cx+s*.20f, cy-s*.42f, stroke);
                canvas.drawLine(cx+s*.55f, cy+s*.20f, cx-s*.42f, cy+s*.20f, stroke);
                canvas.drawLine(cx-s*.42f, cy+s*.20f, cx-s*.20f, cy+s*.42f, stroke);
                break;

            case ROLE_JUMP:
                canvas.drawLine(cx, cy-s*.55f, cx, cy+s*.38f, stroke);
                canvas.drawLine(cx, cy-s*.55f, cx-s*.28f, cy-s*.20f, stroke);
                canvas.drawLine(cx, cy-s*.55f, cx+s*.28f, cy-s*.20f, stroke);
                break;

            case ROLE_KNIFE:
                path.reset();
                path.moveTo(cx-s*.48f, cy+s*.35f);
                path.lineTo(cx+s*.46f, cy-s*.42f);
                path.lineTo(cx+s*.22f, cy+s*.25f);
                path.close();
                canvas.drawPath(path, paint);
                canvas.drawLine(cx-s*.42f, cy+s*.44f, cx-s*.12f, cy+s*.10f, stroke);
                break;

            case ROLE_PAUSE:
                paint.setColor(stroke.getColor());
                canvas.drawRoundRect(new RectF(cx-s*.34f, cy-s*.52f, cx-s*.10f, cy+s*.52f), s*.05f, s*.05f, paint);
                canvas.drawRoundRect(new RectF(cx+s*.10f, cy-s*.52f, cx+s*.34f, cy+s*.52f), s*.05f, s*.05f, paint);
                break;
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
        if (fireRefs++ == 0) xServer.injectPointerButtonPress(Pointer.Button.BUTTON_LEFT);
    }

    private void removeFireRef() {
        if (fireRefs > 0 && --fireRefs == 0) xServer.injectPointerButtonRelease(Pointer.Button.BUTTON_LEFT);
    }

    private void addAdsRef() {
        if (adsRefs++ == 0) xServer.injectPointerButtonPress(Pointer.Button.BUTTON_RIGHT);
    }

    private void removeAdsRef() {
        if (adsRefs > 0 && --adsRefs == 0) xServer.injectPointerButtonRelease(Pointer.Button.BUTTON_RIGHT);
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

        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
            float x = event.getX(ai);
            float y = event.getY(ai);
            int bi = buttonAt(x, y);
            int role;

            if (bi >= 0) {
                role = BUTTONS[bi].role;
                pointerButtonIndex.put(id, bi);
                roleDown(role);
            } else if (joystickPointer < 0 &&
                       x < getWidth() * 0.42f &&
                       y > getHeight() * 0.38f) {
                role = ROLE_JOYSTICK;
                joystickPointer = id;
                updateJoystick(x, y);
            } else {
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
                } else if (role == ROLE_LOOK) {
                    float sens = adsRefs > 0 ? TOUCH_LOOK_ADS : TOUCH_LOOK_NORMAL;
                    int dx = Math.round((x - lastX[pslot]) * sens);
                    int dy = Math.round((y - lastY[pslot]) * sens);
                    if (dx != 0 || dy != 0) xServer.injectPointerMoveDelta(dx, dy);
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
            } else if (role != ROLE_LOOK && role != ROLE_NONE) {
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
        if (event.sensor.getType() != Sensor.TYPE_GYROSCOPE || getWindowToken() == null) return;

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

        WindowManager wm = (WindowManager)getContext().getSystemService(Context.WINDOW_SERVICE);
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
        if (dx != 0 || dy != 0) xServer.injectPointerMoveDelta(dx, dy);
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {}
}
'''
(java / "XzielMobileOverlay.java").write_text(overlay_java, encoding="utf-8")


xserver = java / "XServerDisplayActivity.java"
text = xserver.read_text(encoding="utf-8")

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
