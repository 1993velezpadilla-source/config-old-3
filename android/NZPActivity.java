package org.libsdl.app;

import android.content.pm.ActivityInfo;
import android.view.WindowInsetsController;
import android.view.WindowInsets;
import android.os.Bundle;
import android.os.Build;
import android.view.View;
import android.view.WindowManager;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Android launcher for the native NZ:P/Vril build.
 *
 * The complete official NZ:P data archive is bundled inside the APK by CI.
 * Before SDL_main starts, it is expanded into private app storage and Vril is
 * launched with that folder as -basedir. Nothing is streamed from the web at
 * runtime.
 */
public class NZPActivity extends SDLActivity {
    private static final String DATA_ARCHIVE = "nzp-data.zip";
    private static final String DATA_VERSION = "nzp-data.version";
    private XzielMultiplayer multiplayer;

    /**
     * Keep SDL/Vril locked to sensor-landscape. Without this override SDL2
     * treats the resizable desktop-style window as FULL_USER and Android can
     * rotate/recreate the Surface after the GLES context has been created.
     */
    @Override
    public void setOrientationBis(int w, int h, boolean resizable, String hint) {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
    }

    private void applyImmersiveMode() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);

        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                );
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            );
        }

        WindowManager.LayoutParams attrs = getWindow().getAttributes();
        if (Build.VERSION.SDK_INT >= 28) {
            attrs.layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            getWindow().setAttributes(attrs);
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        multiplayer = new XzielMultiplayer(this, BuildConfig.XZIEL_MULTIPLAYER_URL);
        applyImmersiveMode();

        boolean ciPublicMatch = getIntent() != null
            && getIntent().getBooleanExtra("xziel_ci_public_match", false);
        final String ciMatchQueue = getIntent() != null
            ? getIntent().getStringExtra("xziel_ci_match_queue")
            : null;
        final String ciPlayerId = getIntent() != null
            ? getIntent().getStringExtra("xziel_ci_player_id")
            : null;
        if (ciPlayerId != null && multiplayer != null) {
            multiplayer.setCiPlayerId(ciPlayerId);
        }
        boolean ciEvidenceMode = getIntent() != null
            && getIntent().getBooleanExtra("xziel_ci_evidence_mode", false);
        if (multiplayer != null) {
            multiplayer.setCiEvidenceMode(ciEvidenceMode);
        }
        if (ciPublicMatch) {
            getWindow().getDecorView().postDelayed(new Runnable() {
                @Override
                public void run() {
                    if (multiplayer != null) {
                        multiplayer.findPublicMatch(
                            ciMatchQueue == null ? "public-v1" : ciMatchQueue
                        );
                    }
                }
            }, 5000);
        }
        boolean ciSquadPreview = getIntent() != null
            && getIntent().getBooleanExtra("xziel_ci_squad_preview", false);
        if (ciSquadPreview) {
            getWindow().getDecorView().postDelayed(new Runnable() {
                @Override
                public void run() {
                    if (multiplayer != null) multiplayer.showCiSquadPreview();
                }
            }, 5000);
        }
        boolean ciMultiplayerMenuPreview = getIntent() != null
            && getIntent().getBooleanExtra(
                "xziel_ci_multiplayer_menu_preview", false);
        if (ciMultiplayerMenuPreview) {
            getWindow().getDecorView().postDelayed(new Runnable() {
                @Override
                public void run() {
                    if (multiplayer != null) multiplayer.openMultiplayerMenu();
                }
            }, 5000);
        }
        getWindow().getDecorView().postDelayed(new Runnable() {
            @Override
            public void run() {
                applyImmersiveMode();
            }
        }, 350);
    }

    @Override
    protected void onResume() {
        super.onResume();
        applyImmersiveMode();
    }

    public void requestFullExitFromNative() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (Build.VERSION.SDK_INT >= 21) {
                    finishAndRemoveTask();
                } else {
                    finish();
                }
            }
        });
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            applyImmersiveMode();
        }
    }

    public void xzielOpenMultiplayer() {
        if (multiplayer != null) multiplayer.openMultiplayerMenu();
    }

    public boolean xzielOnlineActive() {
        return multiplayer != null && multiplayer.isOnlineActive();
    }

    public boolean xzielGameSend(byte[] data, int destinationSlot,
                                 int sourcePort, int destinationPort) {
        return multiplayer != null &&
            multiplayer.sendGameDatagram(data, destinationSlot, sourcePort, destinationPort);
    }

    public byte[] xzielGamePoll(int localPort) {
        return multiplayer != null ? multiplayer.pollGameDatagram(localPort) : null;
    }

    public boolean xzielGameHasPacket(int localPort) {
        return multiplayer != null && multiplayer.hasGameDatagram(localPort);
    }

    public String xzielOnlinePollCommand() {
        return multiplayer != null ? multiplayer.pollNativeCommand() : "";
    }

    public void xzielOnlineEngineState(boolean serverActive, boolean clientConnected,
                                       int signon, String map) {
        if (multiplayer != null) {
            multiplayer.onEngineState(serverActive, clientConnected, signon, map);
        }
    }

    public void xzielLeaveMultiplayer() {
        if (multiplayer != null) multiplayer.leaveRoom();
    }

    public void xzielVoiceUpdatePosition(float x, float y, float z) {
        if (multiplayer != null) multiplayer.updateVoicePosition(x, y, z);
    }

    public void xzielCiRemoteEntity(int slot, float x, float y, float z,
                                    int frame, float yaw) {
        if (multiplayer != null) {
            multiplayer.onCiRemoteEntity(slot, x, y, z, frame, yaw);
        }
    }

    public void xzielCiSoundEvent(int entity, int channel, String name,
                                  float x, float y, float z) {
        if (multiplayer != null) {
            multiplayer.onCiSoundEvent(entity, channel, name, x, y, z);
        }
    }

    public void xzielOnlinePauseVoice(boolean visible) {
        if (multiplayer != null) multiplayer.showVoicePausePanel(visible);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == XzielVoiceChat.MIC_PERMISSION_REQUEST &&
            multiplayer != null) {
            boolean granted = grantResults != null && grantResults.length > 0
                && grantResults[0] ==
                    android.content.pm.PackageManager.PERMISSION_GRANTED;
            multiplayer.onMicrophonePermissionResult(granted);
        }
    }

    @Override
    protected void onDestroy() {
        if (multiplayer != null) {
            multiplayer.shutdown();
            multiplayer = null;
        }
        super.onDestroy();
    }

    @Override
    protected String[] getLibraries() {
        return new String[] {
            "SDL2",
            "SDL2_mixer",
            "main"
        };
    }

    @Override
    protected String[] getArguments() {
        File dataRoot = new File(getFilesDir(), "nzp-runtime");

        try {
            ensureBundledGameData(dataRoot);
        } catch (IOException e) {
            throw new RuntimeException("Unable to prepare bundled NZ:P game data", e);
        }

        String ciMap = getIntent() != null
            ? getIntent().getStringExtra("xziel_ci_map")
            : null;
        if (ciMap != null) {
            ciMap = ciMap.trim();
        }
        if (ciMap != null && !ciMap.isEmpty()) {
            // CI/development map validation path. This does not affect normal
            // launches and lets map workflows boot a freshly bundled BSP
            // directly on the Android emulator/device.
            return new String[] {
                "-basedir", dataRoot.getAbsolutePath(),
                "+map", ciMap
            };
        }

        boolean hudPreview = getIntent() != null
            && getIntent().getBooleanExtra("xziel_ci_hud_preview", false);

        if (hudPreview) {
            // CI-only visual validation path. "ndu" is the bundled Nacht der
            // Untoten map; starting it directly lets the workflow capture the
            // actual gameplay HUD rather than only a menu/loading screen.
            return new String[] {
                "-basedir", dataRoot.getAbsolutePath(),
                "+map", "ndu"
            };
        }

        return new String[] {
            "-basedir", dataRoot.getAbsolutePath()
        };
    }

    private void ensureBundledGameData(File dataRoot) throws IOException {
        String expectedVersion = readAssetText(DATA_VERSION).trim();
        File marker = new File(dataRoot, ".xziel-data-version");

        if (marker.isFile() && expectedVersion.equals(readFileText(marker).trim())) {
            return;
        }

        deleteTree(dataRoot);
        if (!dataRoot.mkdirs() && !dataRoot.isDirectory()) {
            throw new IOException("Could not create " + dataRoot);
        }

        String canonicalRoot = dataRoot.getCanonicalPath() + File.separator;

        try (InputStream raw = getAssets().open(DATA_ARCHIVE);
             ZipInputStream zip = new ZipInputStream(new BufferedInputStream(raw))) {

            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];

            while ((entry = zip.getNextEntry()) != null) {
                File out = new File(dataRoot, entry.getName());
                String canonicalOut = out.getCanonicalPath();

                if (!canonicalOut.equals(dataRoot.getCanonicalPath())
                        && !canonicalOut.startsWith(canonicalRoot)) {
                    throw new IOException("Blocked invalid archive path: " + entry.getName());
                }

                if (entry.isDirectory()) {
                    if (!out.mkdirs() && !out.isDirectory()) {
                        throw new IOException("Could not create directory " + out);
                    }
                } else {
                    File parent = out.getParentFile();
                    if (parent != null && !parent.mkdirs() && !parent.isDirectory()) {
                        throw new IOException("Could not create directory " + parent);
                    }

                    try (BufferedOutputStream output =
                                 new BufferedOutputStream(new FileOutputStream(out))) {
                        int count;
                        while ((count = zip.read(buffer)) != -1) {
                            output.write(buffer, 0, count);
                        }
                    }
                }

                zip.closeEntry();
            }
        }

        try (FileOutputStream output = new FileOutputStream(marker)) {
            output.write(expectedVersion.getBytes(StandardCharsets.UTF_8));
        }
    }

    private String readAssetText(String name) throws IOException {
        try (InputStream input = getAssets().open(name);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return output.toString("UTF-8");
        }
    }

    private String readFileText(File file) throws IOException {
        try (FileInputStream input = new FileInputStream(file);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return output.toString("UTF-8");
        }
    }

    private void deleteTree(File file) throws IOException {
        if (!file.exists()) {
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
            throw new IOException("Could not delete old runtime path " + file);
        }
    }
}
