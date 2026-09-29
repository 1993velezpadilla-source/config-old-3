package org.libsdl.app;

import android.content.pm.ActivityInfo;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

/** Native XZIEL Android launcher. */
public final class XzielActivity extends SDLActivity {
    @Override
    public void setOrientationBis(int w, int h, boolean resizable, String hint) {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
    }

    private void applyImmersiveMode() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        applyImmersiveMode();
    }

    @Override
    protected void onResume() {
        super.onResume();
        applyImmersiveMode();
    }

    @Override
    protected String[] getLibraries() {
        return new String[] { "SDL2", "xziel" };
    }

    @Override
    protected String[] getArguments() {
        String mapId = getIntent() != null
            ? getIntent().getStringExtra("xziel_map")
            : null;
        if (mapId == null || mapId.isEmpty()) {
            mapId = "xziel_nuketown_zombies";
        }

        return new String[] {
            "--xziel-root", getFilesDir().getAbsolutePath(),
            "--xziel-map", mapId
        };
    }
}
