#!/usr/bin/env python3
"""Enable temporary Android WebView remote inspection for VK player diagnosis.

This is intended for beta diagnostic builds only. It does not alter page content,
network filtering, player controls, or touch dispatch.
"""
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
marker = "android.webkit.WebView.setWebContentsDebuggingEnabled(true);"
if marker not in source:
    pattern = re.compile(r"(?m)^(\s*)(?:web\s*=\s*new\s+WebView\s*\(this\)\s*;|web\s*=\s*new\s+WebView\(MainActivity\.this\)\s*;)")
    match = pattern.search(source)
    if not match:
        raise SystemExit("Could not locate WebView construction; refusing to enable inspector at an uncertain location.")
    indent = match.group(1)
    source = source[:match.start()] + indent + marker + "\n" + source[match.start():]
    source = source.replace(
        "android.webkit.WebView.setWebContentsDebuggingEnabled(true);\n" + match.group(0),
        "android.webkit.WebView.setWebContentsDebuggingEnabled(true);\n" + match.group(0),
        1
    )
    source = source.replace(
        marker,
        marker + '\n' + indent + 'android.util.Log.i("RuFilmInspect", "Remote WebView inspection enabled for beta diagnostics");',
        1
    )
path.write_text(source, encoding="utf-8")
print("Enabled temporary WebView remote inspection in", path)
