#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 4:
    raise SystemExit("usage: patch_winlator_xziel_nacht_direct_payload.py <winlator-root> <runtime-zip-sha256> <vfs-sha256>")

root = Path(sys.argv[1]).resolve()
runtime_sha = sys.argv[2].strip().lower()
vfs_sha = sys.argv[3].strip().lower()
if len(runtime_sha) != 64 or len(vfs_sha) != 64:
    raise SystemExit("invalid direct payload identity")

java = root / "app/src/main/java/com/winlator"
boot = java / "XzielBootActivity.java"
xserver = java / "XServerDisplayActivity.java"
guest = java / "xenvironment/components/GuestProgramLauncherComponent.java"
gradle = root / "app/build.gradle"

text = boot.read_text(encoding="utf-8")
text = text.replace("import java.io.InputStream;\n", "import java.io.InputStream;\nimport java.io.BufferedInputStream;\nimport java.util.zip.ZipEntry;\nimport java.util.zip.ZipInputStream;\n", 1)

const_pat = re.compile(
    r'    private static final String GAME_ASSET = "nacht-onefile\.exe";\n'
    r'    private static final String GAME_DIR = "XZIEL";\n'
    r'    private static final String GAME_EXE = "Nacht-Chronicles-XZIEL\.exe";\n'
    r'    private static final long GAME_BYTES = .*?;\n'
    r'    private static final String GAME_SHA256 =\n'
    r'        ".*?";\n'
    r'    private static final String PACKAGE_MARKER = "\.xziel-nacht-onefile-v1";'
)
const_repl = '''    private static final String RUNTIME_ASSET = "xziel-runtime.zip";
    private static final String VFS_ASSET = "xziel-nacht-vfs.zip";
    private static final String GAME_DIR = "XZIEL";
    private static final String GAME_EXE = "Xziel-Nacht.exe";
    private static final String DIRECT_PAYLOAD_ID =
        "__RUNTIME_SHA__:__VFS_SHA__";
    private static final String PACKAGE_MARKER = ".xziel-nacht-direct-payload-v1";'''.replace("__RUNTIME_SHA__", runtime_sha).replace("__VFS_SHA__", vfs_sha)
text, n = const_pat.subn(const_repl, text, count=1)
if n != 1:
    raise SystemExit("direct payload constant anchor missing")

prepare_pat = re.compile(
    r'    private void prepareGameAndLaunch\(ContainerManager manager, Container container\) \{.*?\n'
    r'    \}\n\n'
    r'    private void installExeTransactional\(File finalExe\) throws Exception \{.*?\n'
    r'    \}\n\n'
    r'    private static String toHex\(byte\[\] bytes\) \{.*?\n'
    r'    \}\n',
    re.S,
)
prepare_repl = r'''    private void prepareGameAndLaunch(ContainerManager manager, Container container) {
        Executors.newSingleThreadExecutor().execute(() -> {
            try {
                manager.activateContainer(container);

                File gameDir = new File(container.getRootDir(), ".wine/drive_c/" + GAME_DIR);
                File exe = new File(gameDir, GAME_EXE);
                File scene = new File(gameDir, "xziel/maps/xziel_nacht_bo3/scene.xzsc");
                File marker = new File(gameDir, PACKAGE_MARKER);

                boolean ready =
                    exe.isFile() &&
                    scene.isFile() &&
                    marker.isFile() &&
                    DIRECT_PAYLOAD_ID.equals(FileUtils.readString(marker).trim());

                if (!ready) {
                    Log.i(TAG, "DIRECT_PAYLOAD_INSTALL_BEGIN");
                    runOnUiThread(() -> status.setText("XZIEL\nInstalling Nacht payload..."));
                    FileUtils.delete(gameDir);
                    if (!gameDir.mkdirs() && !gameDir.isDirectory()) {
                        throw new RuntimeException("could not create game directory");
                    }

                    Log.i(TAG, "DIRECT_RUNTIME_EXTRACT_BEGIN");
                    extractZipAsset(RUNTIME_ASSET, gameDir);
                    Log.i(TAG, "DIRECT_RUNTIME_EXTRACT_GREEN");

                    Log.i(TAG, "DIRECT_VFS_EXTRACT_BEGIN");
                    extractZipAsset(VFS_ASSET, gameDir);
                    Log.i(TAG, "DIRECT_VFS_EXTRACT_GREEN");

                    if (!exe.isFile()) throw new RuntimeException("Xziel-Nacht.exe missing after extraction");
                    if (!scene.isFile()) throw new RuntimeException("Nacht scene missing after extraction");
                    FileUtils.writeString(marker, DIRECT_PAYLOAD_ID + "\n");
                    Log.i(TAG, "DIRECT_PAYLOAD_INSTALL_GREEN exe_bytes=" + exe.length());
                }
                else {
                    Log.i(TAG, "DIRECT_PAYLOAD_ALREADY_READY exe_bytes=" + exe.length());
                }

                runOnUiThread(() -> launchGame(container, exe));
            }
            catch (Throwable t) {
                fail("XZIEL game setup failed\n" + t.getMessage());
            }
        });
    }

    private void extractZipAsset(String assetName, File destination) throws Exception {
        String canonicalRoot = destination.getCanonicalPath() + File.separator;
        byte[] buffer = new byte[1024 * 1024];
        int files = 0;

        try (InputStream raw = getAssets().open(assetName, AssetManager.ACCESS_STREAMING);
             BufferedInputStream buffered = new BufferedInputStream(raw, 1024 * 1024);
             ZipInputStream zin = new ZipInputStream(buffered)) {
            ZipEntry entry;
            while ((entry = zin.getNextEntry()) != null) {
                File out = new File(destination, entry.getName());
                String canonicalOut = out.getCanonicalPath();
                if (!canonicalOut.equals(destination.getCanonicalPath()) &&
                    !canonicalOut.startsWith(canonicalRoot)) {
                    throw new RuntimeException("unsafe zip entry: " + entry.getName());
                }

                if (entry.isDirectory()) {
                    if (!out.mkdirs() && !out.isDirectory()) {
                        throw new RuntimeException("could not create " + out);
                    }
                }
                else {
                    File parent = out.getParentFile();
                    if (parent != null && !parent.mkdirs() && !parent.isDirectory()) {
                        throw new RuntimeException("could not create " + parent);
                    }
                    try (FileOutputStream fout = new FileOutputStream(out)) {
                        int read;
                        while ((read = zin.read(buffer)) > 0) fout.write(buffer, 0, read);
                        fout.getFD().sync();
                    }
                    files++;
                    if ((files & 127) == 0) {
                        Log.i(TAG, "DIRECT_PAYLOAD_EXTRACT_PROGRESS asset=" + assetName + " files=" + files);
                    }
                }
                zin.closeEntry();
            }
        }
        Log.i(TAG, "DIRECT_PAYLOAD_EXTRACT_DONE asset=" + assetName + " files=" + files);
    }
'''
text, n = prepare_pat.subn(prepare_repl, text, count=1)
if n != 1:
    raise SystemExit("direct payload install-method anchor missing")
boot.write_text(text, encoding="utf-8")

text = xserver.read_text(encoding="utf-8")
old = r'                guestExecutable = "wine C:\\XZIEL\\Nacht-Chronicles-XZIEL.exe";'
new = r'                guestExecutable = "wine C:\\XZIEL\\Xziel-Nacht.exe --xziel-root C:\\XZIEL --xziel-map xziel_nacht_bo3";'
if old not in text:
    raise SystemExit("direct payload XServer command anchor missing")
text = text.replace(old, new, 1)
text = text.replace(
    'Log.i("XZIEL-HYBRID", "DIRECT_NACHT_WINE_LAUNCH command=" + guestExecutable);',
    'Log.i("XZIEL-HYBRID", "DIRECT_PAYLOAD_WINE_LAUNCH command=" + guestExecutable);',
    1,
)
xserver.write_text(text, encoding="utf-8")

text = guest.read_text(encoding="utf-8")
if 'guestExecutable.contains("Nacht-Chronicles-XZIEL.exe")' not in text:
    raise SystemExit("direct payload guest detection anchor missing")
text = text.replace(
    'guestExecutable.contains("Nacht-Chronicles-XZIEL.exe")',
    'guestExecutable.contains("Xziel-Nacht.exe")',
    1,
)
guest.write_text(text, encoding="utf-8")

text = gradle.read_text(encoding="utf-8")
text = text.replace("noCompress 'exe', 'tzst'", "noCompress 'exe', 'tzst', 'zip'")
gradle.write_text(text, encoding="utf-8")

print("XZIEL_DIRECT_PAYLOAD_PATCH_GREEN")
