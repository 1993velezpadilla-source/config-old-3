package org.touchhle.android;

import android.content.Context;
import android.util.Log;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/** Internal personal QA bootstrap: copy the owner's supplied iPad IPA into touchHLE's
 *  own app directory once, before SDL/touchHLE initialization begins.
 *  This is NOT a decompilation of the game and it is NOT a game engine port.
 */
public final class AndroidIpaBootstrap {
    private static final String TAG = "WAW_HD_BOOT";
    private static final String ASSET = "waw_ipad_hd_original.ipa";
    private static final String FILENAME = "WAW_Zombies_HD_iPad_v1.5.0.ipa";
    private static final long EXPECTED_BYTES = 34131256L;

    private AndroidIpaBootstrap() { }

    public static void install(Context context) {
        try {
            final File root = context.getExternalFilesDir(null);
            if (root == null) {
                Log.e(TAG, "WAW_HD_EMBEDDED_IPA_PATH_MISSING");
                return;
            }
            final File dir = new File(root, "touchHLE_apps");
            if (!dir.exists() && !dir.mkdirs()) {
                Log.e(TAG, "WAW_HD_EMBEDDED_IPA_DIR_CREATE_FAILED");
                return;
            }
            final File destination = new File(dir, FILENAME);
            if (destination.length() == EXPECTED_BYTES) {
                Log.i(TAG, "WAW_HD_EMBEDDED_IPA_ALREADY_READY=" + destination.getAbsolutePath());
                return;
            }

            // Atomic copy. Never let the app picker see a partial ZIP/IPA.
            final File temporary = new File(dir, FILENAME + ".pending");
            final byte[] buffer = new byte[32768];
            long total = 0;
            try (InputStream input = context.getAssets().open(ASSET);
                 OutputStream output = new FileOutputStream(temporary)) {
                int got;
                while ((got = input.read(buffer)) != -1) {
                    output.write(buffer, 0, got);
                    total += got;
                }
                output.flush();
            }
            if (total != EXPECTED_BYTES || temporary.length() != EXPECTED_BYTES) {
                Log.e(TAG, "WAW_HD_EMBEDDED_IPA_INCOMPLETE bytes=" + total);
                temporary.delete();
                return;
            }
            if (destination.exists() && !destination.delete()) {
                Log.e(TAG, "WAW_HD_EMBEDDED_IPA_CANNOT_REPLACE");
                temporary.delete();
                return;
            }
            if (!temporary.renameTo(destination)) {
                Log.e(TAG, "WAW_HD_EMBEDDED_IPA_ATOMIC_RENAME_FAILED");
                temporary.delete();
                return;
            }
            Log.i(TAG, "WAW_HD_EMBEDDED_IPA_READY=" + destination.getAbsolutePath()
                    + " bytes=" + total);
        } catch (Throwable t) {
            Log.e(TAG, "WAW_HD_EMBEDDED_IPA_BOOTSTRAP_ERROR", t);
        }
    }
}
