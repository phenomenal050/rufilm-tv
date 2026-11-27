# RuFilmTV

Modern online cinema for Android, Android TV and Google TV.

## Current build

- App ID: `tv.rufilm.app`
- Version: `3.0.2` (`versionCode 18`)
- Android TV banner: modern cream light theme and charcoal/red dark theme
- Original site HTML5 player remains the playback surface; fullscreen system mouse-arrow support is retained
- In-app updater: **Ещё → Проверить обновления**. It verifies the GitHub Release APK SHA-256, package ID, version and signing certificate before opening Android's standard installer

## Build and release

GitHub Actions builds a debug APK artifact on pushes to `main`. To publish an update that can be installed over the existing app, configure the persistent signing-key secrets described in [RELEASE_SETUP.md](RELEASE_SETUP.md), then push a version tag such as `v3.0.2`. The release workflow publishes the signed APK and checksum as a GitHub Release.

The updater does not perform silent installation. The Android package installer always asks the user to confirm.
