#!/usr/bin/env python3
from pathlib import Path

root = Path("rufilm-tv-2.9")
candidates = [root / "settings.gradle.kts", root / "settings.gradle"]
settings = next((p for p in candidates if p.exists()), None)
if settings is None:
    raise SystemExit("Could not find app settings.gradle(.kts)")

text = settings.read_text(encoding="utf-8")
repo_url = "https://yuroyami.github.io/maven"
if repo_url not in text:
    if "mavenCentral()" in text:
        text = text.replace(
            "mavenCentral()",
            'mavenCentral()\n            maven("https://yuroyami.github.io/maven") { content { includeModule("io.github.yuroyami", "libmpv-kmp-view") } }',
            1,
        )
    elif "repositories {" in text:
        text = text.replace(
            "repositories {",
            'repositories {\n            maven { url = uri("https://yuroyami.github.io/maven") }',
            1,
        )
    else:
        raise SystemExit("Could not safely add the MPV Maven repository to settings")
    settings.write_text(text, encoding="utf-8")

print("Configured the pinned MPV artifact repository in", settings)
