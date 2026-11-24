#!/usr/bin/env python3
"""Declare external video players for Android 11+ package visibility."""
import pathlib
import re
import sys

manifest = pathlib.Path(sys.argv[1])
source = manifest.read_text(encoding="utf-8")

packages = [
    "com.mxtech.videoplayer.ad",
    "com.mxtech.videoplayer.pro",
    "is.xyz.mpv",
    "org.videolan.vlc",
    "net.gtvbox.videoplayer",
    "net.gtvbox.vimuhd",
    "com.brouken.player",
    "org.xbmc.kodi",
]
missing = [p for p in packages if f'android:name="{p}"' not in source]
if missing:
    query_block = "    <queries>\\n" + "".join(
        f'        <package android:name="{p}" />\\n' for p in missing
    ) + "    </queries>\\n"
    match = re.search(r"<manifest\\b[^>]*>", source)
    if not match:
        raise SystemExit("AndroidManifest.xml has no manifest root element")
    source = source[:match.end()] + "\\n" + query_block + source[match.end():]
    manifest.write_text(source, encoding="utf-8")

for package in packages:
    if f'android:name="{package}"' not in source:
        raise SystemExit(f"Package visibility declaration missing: {package}")
print("Declared Android package visibility for external video players.")
