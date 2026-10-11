package com.bubblegum.bo1native;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.content.Intent;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.TextView;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int SELECT_FF = 1851;
    private static final int MAX_FILE_BYTES = 1_750_000_000;
    private static final String NATIVE_LIBRARY = "bo1_real_original_core_arm64";

    private TextView status;
    private Button fileButton;
    private final ExecutorService ioWorker = Executors.newSingleThreadExecutor();
    private boolean nativeLoaded = false;
    private String nativeError = "";

    private static native String nativeSelfTest();
    private static native String nativeProbeFile(String root, String name);

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            System.loadLibrary(NATIVE_LIBRARY);
            nativeLoaded = true;
        } catch (Throwable e) {
            nativeError = e.getClass().getSimpleName() + ": " + e.getMessage();
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 36, 28, 18);
        root.setBackgroundColor(Color.rgb(17, 19, 24));

        TextView title = text("BLACK OPS 1\nORIGINAL ENGINE • ARM64", 24, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView warning = text(
            "NATIVE PORT — ENGINE TEST ONLY\n\n" +
            "Este APK NO es Call of Duty jugable: no contiene mapas, " +
            "zombis, renderer ni archivos del juego. " +
            "Ejecuta componentes C++ auténticos recuperados del motor de BO1.",
            16, Color.rgb(255, 190, 88));
        warning.setPadding(0, 20, 0, 25);
        root.addView(warning);

        Button selfTest = button("1 · PROBAR CÓDIGO ORIGINAL ARM64");
        root.addView(selfTest);
        selfTest.setOnClickListener(v -> runNativeCheck());

        fileButton = button("2 · ABRIR ARCHIVO .FF PROPIO");
        root.addView(fileButton);
        fileButton.setOnClickListener(v -> selectFile());

        TextView info = text(
            "Para probar Kino der Toten, selecciona un archivo " +
            "zombie_theater.ff de tu propia instalación legítima de Black Ops 1 PC. " +
            "No subas el archivo a GitHub; se procesa únicamente en tu teléfono.\n\n" +
            "Puede reconocer el encabezado, tamaño y un prefijo del archivo. " +
            "No puede renderizar o jugar el mapa.",
            14, Color.rgb(185, 192, 206));
        info.setPadding(0, 12, 0, 25);
        root.addView(info);

        status = text("", 15, Color.rgb(145, 232, 180));
        status.setTextIsSelectable(true);
        root.addView(status);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(root);
        setContentView(scroll);

        status.setText("CPU: " + Build.SUPPORTED_ABIS[0] + "\n" +
          "Biblioteca nativa: " + (nativeLoaded ? "CARGADA" : "ERROR\n" + nativeError) +
          "\n\nLa app no afirma que el juego completo funcione.");
        if (nativeLoaded) runNativeCheck();
        else {selfTest.setEnabled(false);fileButton.setEnabled(false);}
    }

    private TextView text(String value, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setGravity(Gravity.START);
        t.setLineSpacing(3, 1.0f);
        return t;
    }

    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setPadding(10, 8, 10, 8);
        return b;
    }

    private void runNativeCheck() {
        if (!nativeLoaded) return;
        try { status.setText(nativeSelfTest()); }
        catch (Throwable e) { status.setText("NATIVE ERROR: " + e.toString()); }
    }

    private void selectFile() {
        if (!nativeLoaded) return;
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        try { startActivityForResult(i, SELECT_FF); }
        catch (Exception e) { status.setText("Android file picker error: " + e); }
    }

    @Override
    protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if (code != SELECT_FF || result != RESULT_OK || data == null) return;
        final Uri uri = data.getData();
        if (uri == null) return;
        String chosen = null;
        try (Cursor c = getContentResolver().query(uri,
            new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) chosen = c.getString(0);
        } catch (Exception e) {
            status.setText("Could not inspect selected file: " + e.getMessage());
            return;
        }
        if (chosen == null || !chosen.matches("[A-Za-z0-9_-]{1,63}\\.ff")) {
            status.setText("Choose a .ff file (for Kino: zombie_theater.ff).");
            return;
        }
        final String zone = chosen.substring(0, chosen.length()-3);
        fileButton.setEnabled(false);
        status.setText("Abriendo " + chosen + "…\nCopiando de forma local; no se sube.");
        ioWorker.execute(() -> {
            File temp = null;
            try {
                File folder = new File(getFilesDir(), "zone/english");
                if (!folder.exists() && !folder.mkdirs()) throw new Exception("Cannot create local zone folder");
                File dest = new File(folder, zone + ".ff");
                temp = new File(folder, zone + ".ff.tmp");
                if (temp.exists() && !temp.delete()) throw new Exception("Stale temporary file");
                long copied = 0L;
                try (InputStream in = getContentResolver().openInputStream(uri);
                     FileOutputStream out = new FileOutputStream(temp)) {
                    if (in == null) throw new Exception("No access to selected file");
                    byte[] buf = new byte[65536];
                    int n;
                    while ((n=in.read(buf))>=0) {
                        if (n==0) continue;
                        copied += n;
                        if (copied > MAX_FILE_BYTES) throw new Exception("File exceeds 1.75 GB safety bound");
                        if (copied > folder.getUsableSpace() + temp.length())
                            throw new Exception("Insufficient local storage");
                        out.write(buf,0,n);
                    }
                    out.getFD().sync();
                }
                if (!temp.renameTo(dest)) throw new Exception("Could not commit local asset file");
                String nativeResult = nativeProbeFile(getFilesDir().getAbsolutePath(),zone);
                final long bytes=copied;
                runOnUiThread(() -> status.setText(
                    "Archivo local: " + zone + ".ff\n" +
                    "Bytes copiados: " + bytes + "\n" +
                    nativeResult +
                    "\n\nEsto es un test de lectura, NO ejecución de Kino."));
            } catch (Throwable e) {
                if (temp!=null) temp.delete();
                String report=e.toString();
                runOnUiThread(() -> status.setText("No se pudo procesar .ff:\n" + report));
            } finally {
                runOnUiThread(() -> fileButton.setEnabled(true));
            }
        });
    }

    @Override
    protected void onDestroy() {
        ioWorker.shutdown();
        super.onDestroy();
    }
}
