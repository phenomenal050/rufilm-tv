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
    start = source.find("dependencyResolutionManagement")
    if start < 0:
        raise SystemExit("Could not find dependencyResolutionManagement in settings")
    match = re.search(r"repositories\s*\{[^}]*\}", source[start:], re.DOTALL)
    if not match:
        raise SystemExit("Could not find dependencyResolutionManagement.repositories block")
    block = """repositories {
        google()
        mavenCentral()
        maven { url = uri("https://yuroyami.github.io/maven") }
    }"""
    absolute_start = start + match.start()
    absolute_end = start + match.end()
    source = source[:absolute_start] + block + source[absolute_end:]
    settings.write_text(source, encoding="utf-8")

print("Configured MPV Maven repository in dependencyResolutionManagement of", settings)
