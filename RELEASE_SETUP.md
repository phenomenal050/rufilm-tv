# RuFilmTV releases and signing

The Android application uses `applicationId = tv.rufilm.app`. Version 3.0.2 is built with `versionCode = 18`.

## In-app GitHub updater

The in-app item **Ещё → Проверить обновления** reads the latest public GitHub Release from this repository. It looks for an APK asset and its GitHub SHA-256 digest, downloads the APK only after the user confirms, verifies the checksum, checks the APK package ID and version, and compares the installed and downloaded signing certificates. A certificate or package mismatch stops the process. The app then opens Android's standard package installer; the user must confirm installation.

The updater intentionally fails closed if the Release has no APK or no SHA-256 digest. Keep publishing APKs as GitHub Release assets. The first published release establishes the update channel; later releases must have a higher `versionCode` and use the same signing key.

## Publishing the first release

1. Open **Actions → Publish RuFilmTV GitHub Release**.
2. Choose **Run workflow** on the `main` branch.
3. Keep the default tag `v3.0.2` and run it.
4. Wait for the job to finish successfully. It creates the GitHub Release and attaches the signed APK plus a SHA-256 checksum file.

The manual workflow validates that the tag version matches `versionName` in `patches/app-build.gradle.kts`, validates the persistent signing key, builds a release APK, verifies its package/version/signature, and publishes the APK. The same workflow also runs automatically when a `v*` tag is pushed.

The currently installed 3.0.2 app will see the initial 3.0.2 release as the same version, not as an update. This first release only initializes the channel. For every future update, increase both `versionCode` and `versionName` in `patches/app-build.gradle.kts`, then run the workflow with the matching tag (for example, `v3.0.3`). Do not reuse a published tag.

## Signing key

**Do not publish update APKs using a different signing key or the default GitHub Actions debug key.** Every update must use the same persistent keystore already configured in GitHub Actions secrets.

Required repository Actions secrets:

- `ANDROID_SIGNING_KEYSTORE_BASE64` — the one-line Base64 keystore
- `ANDROID_KEYSTORE_PASSWORD` — keystore password
- `ANDROID_KEY_ALIAS` — key alias
- `ANDROID_KEY_PASSWORD` — key password

Never commit the keystore or its passwords to this public repository. Keep a secure backup. Losing the key means Android will reject in-place updates.

## Installation behavior

The app verifies SHA-256, application ID, version code and signing certificate before offering the APK to Android. It never attempts a silent install. Android's package installer and the user remain in control. The one-time permission to install unknown apps may be requested in Android settings.
