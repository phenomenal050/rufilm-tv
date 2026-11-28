#!/usr/bin/env python3
from pathlib import Path
import re

root = Path("rufilm-tv-2.9")
candidates = [root / "settings.gradle.kts", root / "settings.gradle"]
settings = next((p for p in candidates if p.exists()), None)
if settings is None:
    raise SystemExit("Could not find app settings.gradle(.kts)")

source = settings.read_text(encoding="utf-8")
repo_url = "https://yuroyami.github.io/maven"
if repo_url not in source:
    match = re.search(r"(dependencyResolutionManagement\s*\{[\s\S]*?repositories\s*\{)", source)
    if not match:
        raise SystemExit("Could not find dependencyResolutionManagement.repositories in settings")
    insertion = match.group(1) + "\n        maven { url = uri(\"" + repo_url + "\") }"
    source = source[:match.start()] + insertion + source[match.end():]
    settings.write_text(source, encoding="utf-8")

print("Configured the MPV artifact repository in dependencyResolutionManagement of", settings)
