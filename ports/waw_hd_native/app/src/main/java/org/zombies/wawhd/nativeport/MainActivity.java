package org.zombies.wawhd.nativeport;

import android.app.Activity;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/**
 * Android lifecycle, touch and EGL surface only. All demo rendering and scene
 * state live in the ARM64 C++ library. No iOS execution or compatibility layer.
 */
public final class MainActivity extends Activity {
    static { System.loadLibrary("waw_hd_port"); }

    private static native void nativeInit();
    private static native void nativeResize(int width, int height);
    private static native void nativeFrame(long uptimeMs);
    private static native void nativeTouch(int action, float x, float y, int width, int height);

    private GLSurfaceView view;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        );
        view = new GLSurfaceView(this);
        view.setEGLContextClientVersion(2);
        view.setRenderer(new GLSurfaceView.Renderer() {
            @Override public void onSurfaceCreated(GL10 unused, EGLConfig config) {
                nativeInit();
            }
            @Override public void onSurfaceChanged(GL10 unused, int w, int h) {
                nativeResize(w, h);
            }
            @Override public void onDrawFrame(GL10 unused) {
                nativeFrame(SystemClock.uptimeMillis());
            }
        });
        view.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);
        view.setOnTouchListener((v, event) -> {
            final int action = event.getActionMasked();
            final int index = event.getActionIndex();
            final float x = event.getX(index);
            final float y = event.getY(index);
            final int width = v.getWidth();
            final int height = v.getHeight();
            view.queueEvent(() -> nativeTouch(action, x, y, width, height));
            return true;
        });
        setContentView(view);
    }

    @Override protected void onPause() {
        super.onPause();
        if (view != null) view.onPause();
    }

    @Override protected void onResume() {
        super.onResume();
        if (view != null) view.onResume();
    }
}
