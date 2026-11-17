# RuFilmTV releases and signing

The Android application uses `applicationId = tv.rufilm.app`. Version 3.0.2 is built with `versionCode = 18`.

## GitHub updater

The in-app item **Ещё → Проверить обновления** reads the latest public GitHub Release from this repository. It looks for an APK asset and its GitHub `sha256:` digest, downloads the APK only after the user confirms, verifies the checksum, checks the APK package ID and version, and compares the installed and downloaded signing certificates. A certificate or package mismatch stops the process. The app then opens Android's standard package installer; the user must confirm installation.

The updater intentionally fails closed if the Release has no APK or no SHA-256 digest. The repository currently needs its first published Release before the in-app checker can offer an update.

## One-time signing setup

**Do not publish update APKs using the default GitHub Actions debug key.** GitHub-hosted runners create a different debug key on fresh runners, so those APKs are not guaranteed to update one another.

Create one private release keystore and keep a secure backup. Never commit it to this public repository:

```bash
keytool -genkeypair -v \
  -keystore rufilm-tv-release.jks \
  -alias rufilm-tv \
  -keyalg RSA -keysize 4096 \
  -validity 10000
base64 -w0 rufilm-tv-release.jks
```

Add these repository Actions secrets:

- `ANDROID_SIGNING_KEYSTORE_BASE64` — the one-line Base64 output
- `ANDROID_KEYSTORE_PASSWORD` — keystore password
- `ANDROID_KEY_ALIAS` — `rufilm-tv` (or the alias you chose)
- `ANDROID_KEY_PASSWORD` — key password

Both the debug build and the release workflow use this same keystore when all four secrets are present. The tag workflow builds a signed Release APK, verifies its package/version/signature, creates a SHA-256 sidecar, and publishes both files as a GitHub Release.

After the signing secrets are configured, push a version tag such as `v3.0.2` to publish a Release. Keep using the same keystore for every later version; losing it means Android will reject in-place updates.

## First-install migration warning

The earlier CI APK was signed with an ephemeral Android debug certificate. Its private key is not stored in this repository. A first APK signed with a newly created persistent keystore therefore cannot update that old installation in place. For the one-time migration, uninstall the old RuFilmTV build, install the first APK signed with the persistent keystore, and then use the in-app updater for subsequent releases. Back up any app data you need before uninstalling.

The app never attempts a silent install. Android's package installer and the user remain in control.