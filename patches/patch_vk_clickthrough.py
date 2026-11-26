#!/usr/bin/env python3
"""Keep the RuFilmTV fullscreen exit control out of VK's video hit-test area."""
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

pattern = re.compile(
    r"    private void addFullscreenControls\(\) \{.*?\n    \}\n",
    re.S,
)
match = pattern.search(source)
if not match:
    raise SystemExit("Required addFullscreenControls() method was not found")

old = match.group(0)
if "new FrameLayout.LayoutParams(dp(104), dp(58), Gravity.TOP | Gravity.END)" in old:
    print("VK fullscreen click-through fix already applied")
    raise SystemExit(0)

replacement = r'''    private void addFullscreenControls() {
        if (fullscreenContainer == null || fullscreenControls != null) return;
        fullscreenControls = new FrameLayout(this);
        fullscreenControls.setFocusable(false);
        fullscreenControls.setClickable(false);
        fullscreenControls.setLongClickable(false);

        // IMPORTANT: this overlay is deliberately only as large as the exit button.
        // A full-screen transparent ViewGroup can steal pointer hit-testing from
        // controls rendered inside VK's cross-origin iframe on Android WebView.
        FrameLayout.LayoutParams overlayParams =
            new FrameLayout.LayoutParams(dp(104), dp(58), Gravity.TOP | Gravity.END);
        overlayParams.setMargins(0, dp(16), dp(18), 0);
        fullscreenContainer.addView(fullscreenControls, overlayParams);

        Button exit = button("Выйти", false);
        exit.setContentDescription("Выйти из полноэкранного режима");
        exit.setOnClickListener(v -> hideCustomView());
        fullscreenControls.addView(exit, new FrameLayout.LayoutParams(-1, -1));

        installFullscreenCursor(fullscreenControls);
        showFullscreenUi();
    }
'''
source = source[:match.start()] + replacement + source[match.end():]
path.write_text(source, encoding="utf-8")
print("Applied VK fullscreen hit-test isolation to", path)
