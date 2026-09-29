package org.libsdl.app;

import android.content.Context;
import android.system.Os;

import com.github.luben.zstd.ZstdInputStream;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * First-run installer for the experimental XZWin userspace.
 *
 * The compressed Linux/Wine userspace is data. The ARM64 Box64 host itself is
 * intentionally not extracted here; it is packaged as an APK native library
 * and executed from ApplicationInfo.nativeLibraryDir by XzWinRuntime.
 */
public final class XzWinRuntimeInstaller {
    private static final String ROOTFS_ASSET = "xzwin/rootfs.tzst";
    private static final String BOX64_RC_ASSET = "xzwin/default.box64rc";
    private static final String MARKER = ".xzwin-runtime-v1";

    private XzWinRuntimeInstaller() {}

    private static final class PendingHardLink {
        final File output;
        final String target;

        PendingHardLink(File output, String target) {
            this.output = output;
            this.target = target;
        }
    }

    public static boolean isInstalled(Context context) {
        XzWinRuntime.Layout layout = new XzWinRuntime.Layout(context);
        return new File(layout.runtimeRoot, MARKER).isFile()
            && layout.rootfs.isDirectory()
            && layout.wine64.isFile();
    }

    public static synchronized void installIfNeeded(Context context)
            throws IOException {
        if (isInstalled(context)) return;

        XzWinRuntime.Layout layout = new XzWinRuntime.Layout(context);
        if (!layout.runtimeRoot.mkdirs() && !layout.runtimeRoot.isDirectory()) {
            throw new IOException("Could not create XZWin runtime root");
        }

        File temp = new File(layout.runtimeRoot, "rootfs.installing");
        deleteTree(temp);
        if (!temp.mkdirs()) {
            throw new IOException("Could not create temporary XZWin rootfs");
        }

        try {
            extractRootfs(context, temp);
            installBox64Config(context, temp);

            File wine64 = new File(temp, "opt/wine/bin/wine64");
            if (!wine64.isFile()) {
                throw new IOException(
                    "XZWin rootfs is missing opt/wine/bin/wine64");
            }

            deleteTree(layout.rootfs);
            if (!temp.renameTo(layout.rootfs)) {
                throw new IOException("Could not atomically install XZWin rootfs");
            }

            layout.ensureWritableDirs();
            File marker = new File(layout.runtimeRoot, MARKER);
            try (FileOutputStream out = new FileOutputStream(marker, false)) {
                out.write(
                    ("XZWIN_RUNTIME_V1\n"
                        + "rootfs=" + ROOTFS_ASSET + "\n"
                        + "box64Host=" + layout.box64Host.getName() + "\n")
                        .getBytes(StandardCharsets.UTF_8));
            }
        } catch (IOException error) {
            deleteTree(temp);
            throw error;
        }
    }

    private static void extractRootfs(Context context, File root)
            throws IOException {
        List<PendingHardLink> hardLinks = new ArrayList<>();

        try (InputStream raw =
                 new BufferedInputStream(
                     context.getAssets().open(ROOTFS_ASSET), 128 * 1024);
             ZstdInputStream zstd = new ZstdInputStream(raw);
             TarArchiveInputStream tar = new TarArchiveInputStream(zstd)) {

            TarArchiveEntry entry;
            byte[] buffer = new byte[128 * 1024];
            while ((entry = tar.getNextTarEntry()) != null) {
                String name = normalizeTarPath(entry.getName());
                if (name.isEmpty()) continue;

                File output = safeOutput(root, name);
                if (entry.isDirectory()) {
                    mkdir(output);
                    chmodBestEffort(output, entry.getMode());
                    continue;
                }

                File parent = output.getParentFile();
                if (parent != null) mkdir(parent);

                if (entry.isSymbolicLink()) {
                    if (output.exists() && !output.delete()) {
                        throw new IOException("Could not replace " + output);
                    }
                    try {
                        Os.symlink(entry.getLinkName(), output.getAbsolutePath());
                    } catch (Exception e) {
                        throw new IOException(
                            "Could not create symlink " + name, e);
                    }
                    continue;
                }

                if (entry.isLink()) {
                    hardLinks.add(
                        new PendingHardLink(output, entry.getLinkName()));
                    continue;
                }

                if (!entry.isFile()) continue;

                try (BufferedOutputStream out =
                         new BufferedOutputStream(
                             new FileOutputStream(output), 128 * 1024)) {
                    int count;
                    while ((count = tar.read(buffer)) != -1) {
                        out.write(buffer, 0, count);
                    }
                }
                chmodBestEffort(output, entry.getMode());
            }
        }

        for (PendingHardLink link : hardLinks) {
            File target =
                safeOutput(root, normalizeTarPath(link.target));
            if (!target.exists()) {
                throw new IOException(
                    "Missing XZWin hard-link target " + link.target);
            }
            try {
                if (link.output.exists() && !link.output.delete()) {
                    throw new IOException(
                        "Could not replace " + link.output);
                }
                Os.link(
                    target.getAbsolutePath(),
                    link.output.getAbsolutePath());
            } catch (Exception e) {
                throw new IOException(
                    "Could not create hard link " + link.output, e);
            }
        }
    }

    private static void installBox64Config(Context context, File root)
            throws IOException {
        File out = safeOutput(root, "etc/config.box64rc");
        File parent = out.getParentFile();
        if (parent != null) mkdir(parent);

        try (InputStream input =
                 context.getAssets().open(BOX64_RC_ASSET);
             BufferedOutputStream output =
                 new BufferedOutputStream(new FileOutputStream(out))) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
        }
    }

    private static String normalizeTarPath(String value)
            throws IOException {
        String path = value == null ? "" : value.replace('\\', '/');
        while (path.startsWith("./")) path = path.substring(2);
        while (path.endsWith("/") && !path.isEmpty()) {
            path = path.substring(0, path.length() - 1);
        }
        if (path.startsWith("/")
                || path.equals("..")
                || path.startsWith("../")
                || path.contains("/../")
                || path.indexOf('\0') >= 0) {
            throw new IOException("Unsafe XZWin archive path: " + value);
        }
        return path;
    }

    private static File safeOutput(File root, String relative)
            throws IOException {
        File output = new File(root, relative);
        String rootPath = root.getCanonicalPath() + File.separator;
        String outputPath = output.getCanonicalPath();
        if (!outputPath.startsWith(rootPath)) {
            throw new IOException("XZWin archive escaped root: " + relative);
        }
        return output;
    }

    private static void mkdir(File dir) throws IOException {
        if (!dir.mkdirs() && !dir.isDirectory()) {
            throw new IOException("Could not create " + dir);
        }
    }

    private static void chmodBestEffort(File file, int mode) {
        try {
            Os.chmod(file.getAbsolutePath(), mode & 0777);
        } catch (Exception ignored) {
            // Some archive metadata is advisory on Android app-private storage.
        }
    }

    private static void deleteTree(File file) throws IOException {
        if (file == null || !file.exists()) return;
        if (file.isDirectory() && !java.nio.file.Files.isSymbolicLink(file.toPath())) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteTree(child);
            }
        }
        if (!file.delete()) {
            throw new IOException("Could not delete " + file);
        }
    }
}
