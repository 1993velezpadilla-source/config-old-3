package org.libsdl.app;

import android.content.Context;
import android.os.Build;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Experimental XZWin host for XZIEL.
 *
 * This deliberately keeps the Windows compatibility path separate from the
 * native XZIEL renderer/gameplay path. The ARM64 host executable (Box64) is
 * expected in the APK native-library directory so Android API 29+ does not
 * need to exec a file from the app's writable home directory.
 *
 * Wine and its x86_64 userspace live under files/xzwin/rootfs and are opened
 * by Box64 as guest code.
 */
public final class XzWinRuntime {
    private static final String USER = "xuser";
    private static final String BOX64_HOST_NAME = "libxzbox64.so";

    private XzWinRuntime() {}

    public enum ProbeState {
        READY,
        UNSUPPORTED_ABI,
        MISSING_BOX64_HOST,
        MISSING_ROOTFS,
        MISSING_WINE_GUEST
    }

    public static final class Layout {
        public final File runtimeRoot;
        public final File rootfs;
        public final File prefix;
        public final File imports;
        public final File logs;
        public final File box64Host;
        public final File wineGuest;

        Layout(Context context) {
            runtimeRoot = new File(context.getFilesDir(), "xzwin");
            rootfs = new File(runtimeRoot, "rootfs");
            prefix = new File(runtimeRoot, "prefix/default");
            imports = new File(runtimeRoot, "imports");
            logs = new File(runtimeRoot, "logs");

            String nativeDir = context.getApplicationInfo().nativeLibraryDir;
            box64Host = new File(nativeDir, BOX64_HOST_NAME);
            wineGuest = new File(rootfs, "opt/wine/bin/wine");
        }

        public void ensureWritableDirs() throws IOException {
            mkdir(runtimeRoot);
            mkdir(prefix);
            mkdir(imports);
            mkdir(logs);
            mkdir(new File(rootfs, "tmp"));
            mkdir(new File(rootfs, "home/" + USER));
        }

        private static void mkdir(File dir) throws IOException {
            if (!dir.mkdirs() && !dir.isDirectory()) {
                throw new IOException("Could not create " + dir);
            }
        }
    }

    public static final class Probe {
        public final ProbeState state;
        public final String detail;
        public final Layout layout;

        Probe(ProbeState state, String detail, Layout layout) {
            this.state = state;
            this.detail = detail;
            this.layout = layout;
        }

        public boolean ready() {
            return state == ProbeState.READY;
        }

        @Override
        public String toString() {
            return state + ": " + detail;
        }
    }

    public static final class LaunchSpec {
        public final List<String> argv;
        public final Map<String, String> environment;
        public final File workingDirectory;

        LaunchSpec(
                List<String> argv,
                Map<String, String> environment,
                File workingDirectory) {
            this.argv = Collections.unmodifiableList(new ArrayList<>(argv));
            this.environment =
                Collections.unmodifiableMap(new LinkedHashMap<>(environment));
            this.workingDirectory = workingDirectory;
        }
    }

    public static final class RunResult {
        public final int exitCode;
        public final File logFile;

        RunResult(int exitCode, File logFile) {
            this.exitCode = exitCode;
            this.logFile = logFile;
        }
    }

    public static Probe probe(Context context) {
        Layout layout = new Layout(context);

        boolean arm64 = false;
        for (String abi : Build.SUPPORTED_ABIS) {
            if ("arm64-v8a".equals(abi)) {
                arm64 = true;
                break;
            }
        }
        if (!arm64) {
            return new Probe(
                ProbeState.UNSUPPORTED_ABI,
                "XZWin phase-1 requires arm64-v8a",
                layout);
        }
        if (!layout.box64Host.isFile()) {
            return new Probe(
                ProbeState.MISSING_BOX64_HOST,
                "Expected APK-native Box64 host at " + layout.box64Host,
                layout);
        }
        if (!layout.rootfs.isDirectory()) {
            return new Probe(
                ProbeState.MISSING_ROOTFS,
                "Expected XZWin rootfs at " + layout.rootfs,
                layout);
        }
        if (!layout.wineGuest.isFile()) {
            return new Probe(
                ProbeState.MISSING_WINE_GUEST,
                "Expected Wine guest at " + layout.wineGuest,
                layout);
        }
        return new Probe(ProbeState.READY, "Box64 + Wine launch path ready", layout);
    }

    public static LaunchSpec buildWineLaunch(
            Context context,
            File windowsExe,
            List<String> args) throws IOException {
        Probe probe = probe(context);
        if (!probe.ready()) {
            throw new IOException("XZWin probe failed: " + probe);
        }
        if (windowsExe == null || !windowsExe.isFile()) {
            throw new IOException("Windows executable not found: " + windowsExe);
        }

        Layout layout = probe.layout;
        layout.ensureWritableDirs();

        List<String> argv = new ArrayList<>();
        argv.add(layout.box64Host.getAbsolutePath());
        argv.add(layout.wineGuest.getAbsolutePath());
        argv.add(windowsExe.getAbsolutePath());
        if (args != null) argv.addAll(args);

        String root = layout.rootfs.getAbsolutePath();
        Map<String, String> env = new LinkedHashMap<>();
        env.put("HOME", root + "/home/" + USER);
        env.put("USER", USER);
        env.put("TMPDIR", root + "/tmp");
        env.put("WINEPREFIX", layout.prefix.getAbsolutePath());
        env.put(
            "PATH",
            root + "/opt/wine/bin:"
                + root + "/usr/local/bin:"
                + root + "/usr/bin");
        env.put(
            "LD_LIBRARY_PATH",
            root + "/usr/lib:"
                + root + "/lib:"
                + root + "/lib/aarch64-linux-gnu:"
                + root + "/usr/lib/aarch64-linux-gnu");
        env.put(
            "BOX64_LD_LIBRARY_PATH",
            root + "/lib/x86_64-linux-gnu:"
                + root + "/usr/lib/x86_64-linux-gnu:"
                + root + "/opt/wine/lib/wine/x86_64-unix");
        env.put("BOX64_NOBANNER", "1");
        env.put("BOX64_DYNAREC", "1");
        env.put("WINEDEBUG", "-all");

        File working = windowsExe.getParentFile();
        if (working == null) working = layout.imports;
        return new LaunchSpec(argv, env, working);
    }

    public static RunResult launchAndWait(
            Context context,
            File windowsExe,
            List<String> args,
            String logName) throws IOException, InterruptedException {
        LaunchSpec spec = buildWineLaunch(context, windowsExe, args);
        Layout layout = new Layout(context);
        layout.ensureWritableDirs();

        String safeName =
            (logName == null || logName.isEmpty())
                ? "xzwin-run.log"
                : logName.replaceAll("[^A-Za-z0-9._-]", "_");
        File log = new File(layout.logs, safeName);

        ProcessBuilder builder = new ProcessBuilder(spec.argv);
        builder.directory(spec.workingDirectory);
        builder.redirectErrorStream(true);
        builder.environment().putAll(spec.environment);

        Process process = builder.start();
        try (BufferedReader reader =
                 new BufferedReader(
                     new InputStreamReader(
                         process.getInputStream(),
                         StandardCharsets.UTF_8));
             FileOutputStream out = new FileOutputStream(log, false)) {
            String line;
            while ((line = reader.readLine()) != null) {
                out.write(line.getBytes(StandardCharsets.UTF_8));
                out.write('\n');
            }
        }

        int code = process.waitFor();
        return new RunResult(code, log);
    }
}
