#!/usr/bin/env python3
"""Patch a pinned Winlator source tree into the Xziel IW4 probe APK.

The upstream source remains LGPL-2.1. This patch only adds an Xziel launcher
activity and changes the application ID/label so the probe can coexist with a
normal Winlator install. No MW2 files are embedded or copied.
"""

from __future__ import annotations

import argparse
from pathlib import Path


UPSTREAM_COMMIT = "90390783d955c75ca8ca153353cf3c5b9ca6d6a1"
APPLICATION_ID = "com.xziel.iw4probe"
SHORTCUT_NAME = "XZIEL_IW4"


ACTIVITY_SOURCE = r'''package com.winlator;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.winlator.container.ContainerManager;
import com.winlator.container.Shortcut;

import java.util.ArrayList;

/**
 * Xziel one-tap entrypoint for the IW4 Android compatibility experiment.
 *
 * It deliberately never searches for, downloads, or bundles MW2. The owned
 * Windows install is configured inside the compatibility container. Once a
 * Winlator shortcut named XZIEL_IW4 exists, this launcher jumps straight into
 * the same internal XServerDisplayActivity path used by Winlator itself.
 */
public final class IW4ProbeActivity extends AppCompatActivity {
    public static final String TARGET_SHORTCUT = "XZIEL_IW4";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Shortcut target = findTargetShortcut();
        if (target != null) {
            Intent intent = new Intent(this, XServerDisplayActivity.class);
            intent.putExtra("container_id", target.container.id);
            intent.putExtra("shortcut_path", target.file.getPath());
            startActivity(intent);
            finish();
            return;
        }

        Toast.makeText(
            this,
            "IW4 probe setup: create a Winlator shortcut named XZIEL_IW4, then reopen this app.",
            Toast.LENGTH_LONG
        ).show();

        Intent setup = new Intent(this, MainActivity.class);
        startActivity(setup);
        finish();
    }

    private Shortcut findTargetShortcut() {
        ContainerManager manager = new ContainerManager(this);
        ArrayList<Shortcut> shortcuts = manager.loadShortcuts(null);
        for (Shortcut shortcut : shortcuts) {
            if (shortcut.file.isDirectory()) continue;
            if (TARGET_SHORTCUT.equalsIgnoreCase(shortcut.name)) return shortcut;
        }
        return null;
    }
}
'''


PROBE_ACTIVITY_MANIFEST = r'''
        <activity android:name="com.winlator.IW4ProbeActivity"
            android:exported="true"
            android:theme="@style/AppThemeDark"
            android:screenOrientation="sensorLandscape"
            android:configChanges="keyboard|keyboardHidden|orientation|screenSize|screenLayout|smallestScreenSize|density|navigation">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def patch_tree(root: Path) -> None:
    gradle = root / "app" / "build.gradle"
    manifest = root / "app" / "src" / "main" / "AndroidManifest.xml"
    java_dir = root / "app" / "src" / "main" / "java" / "com" / "winlator"
    license_file = root / "LICENSE"

    for required in (gradle, manifest, license_file, java_dir):
        if not required.exists():
            raise FileNotFoundError(f"missing upstream Winlator path: {required}")

    if "GNU LESSER GENERAL PUBLIC LICENSE" not in license_file.read_text(
        encoding="utf-8", errors="replace"
    ):
        raise RuntimeError("unexpected upstream license; refusing to patch")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(
        gradle_text,
        "applicationId 'com.winlator'",
        f"applicationId '{APPLICATION_ID}'",
        "applicationId",
    )
    gradle_text = replace_once(
        gradle_text,
        'versionName "11.2"',
        'versionName "11.2-xziel-iw4-probe"',
        "versionName",
    )
    gradle.write_text(gradle_text, encoding="utf-8")

    manifest_text = manifest.read_text(encoding="utf-8")

    launcher_filter = '''            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
'''
    manifest_text = replace_once(
        manifest_text,
        launcher_filter,
        "",
        "upstream launcher filter",
    )

    manifest_text = replace_once(
        manifest_text,
        'android:label="@string/app_name"',
        'android:label="Xziel IW4 Probe"',
        "application label",
    )

    manifest_text = replace_once(
        manifest_text,
        'android:authorities="com.winlator.FileProvider"',
        'android:authorities="${applicationId}.FileProvider"',
        "FileProvider authority",
    )

    marker = '        <activity android:name="com.winlator.XServerDisplayActivity"'
    if marker not in manifest_text:
        raise RuntimeError("XServerDisplayActivity manifest marker missing")
    manifest_text = manifest_text.replace(
        marker,
        PROBE_ACTIVITY_MANIFEST + "\n" + marker,
        1,
    )
    manifest.write_text(manifest_text, encoding="utf-8")

    (java_dir / "IW4ProbeActivity.java").write_text(
        ACTIVITY_SOURCE,
        encoding="utf-8",
    )

    notice = root / "XZIEL_IW4_PROBE_NOTICE.txt"
    notice.write_text(
        "Xziel IW4 Probe\n"
        "Upstream: https://github.com/brunodev85/winlator-app\n"
        f"Pinned commit: {UPSTREAM_COMMIT}\n"
        "Upstream license: LGPL-2.1 (see LICENSE)\n"
        "This probe contains no Call of Duty: Modern Warfare 2 game files.\n"
        f"Expected shortcut name: {SHORTCUT_NAME}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    patch_tree(args.source.resolve())
    print(
        f"Patched Winlator {UPSTREAM_COMMIT} -> {APPLICATION_ID}; "
        f"launcher shortcut={SHORTCUT_NAME}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
