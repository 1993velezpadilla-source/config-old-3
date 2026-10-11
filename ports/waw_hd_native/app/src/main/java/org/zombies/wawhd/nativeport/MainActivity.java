package org.zombies.wawhd.nativeport;

import android.app.Activity;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** Thin Android lifecycle / multitouch bridge. All gameplay runs in original ARM64 C++. */
public final class MainActivity extends Activity {
    static { System.loadLibrary("waw_hd_port"); }

    private static native void nativeInit();
    private static native void nativeResize(int width, int height);
    private static native void nativeFrame(long uptimeMs);
    private static native void nativeTouch(
            int action, int pointerId, float x, float y, int width, int height);

    private GLSurfaceView view;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
        view = new GLSurfaceView(this);
        view.setEGLContextClientVersion(2);
        view.setPreserveEGLContextOnPause(true);
        view.setRenderer(new GLSurfaceView.Renderer() {
            @Override public void onSurfaceCreated(GL10 gl, EGLConfig config) {
                nativeInit();
            }
            @Override public void onSurfaceChanged(GL10 gl, int w, int h) {
                nativeResize(w, h);
            }
            @Override public void onDrawFrame(GL10 gl) {
                nativeFrame(SystemClock.uptimeMillis());
            }
        });
        view.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);

        view.setOnTouchListener((v, event) -> {
            final int w = v.getWidth(), h = v.getHeight();
            final int action = event.getActionMasked();
            if (action == MotionEvent.ACTION_MOVE || action == MotionEvent.ACTION_CANCEL) {
                for (int i = 0; i < event.getPointerCount(); ++i) {
                    final int id = event.getPointerId(i);
                    final float x = event.getX(i), y = event.getY(i);
                    final int nativeAction = action;
                    view.queueEvent(() -> nativeTouch(nativeAction, id, x, y, w, h));
                }
            } else {
                final int i = event.getActionIndex();
                final int id = event.getPointerId(i);
                final float x = event.getX(i), y = event.getY(i);
                view.queueEvent(() -> nativeTouch(action, id, x, y, w, h));
            }
            return true;
        });
        setContentView(view);
    }

    @Override protected void onPause() {
        if (view != null) view.onPause();
        super.onPause();
    }

    @Override protected void onResume() {
        super.onResume();
        if (view != null) view.onResume();
    }
}
