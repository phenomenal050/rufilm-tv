package tv.rufilm.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class AppUpdateManager {
    private static final String STABLE_RELEASE_API =
        "https://api.github.com/repos/phenomenal050/rufilm-tv/releases/latest";
    private static final String TEST_RELEASES_API =
        "https://api.github.com/repos/phenomenal050/rufilm-tv/releases?per_page=20";
    private static final String USER_AGENT = "RuFilmTV-Android-Updater";
    private static final int REQUEST_UNKNOWN_SOURCES = 7421;
    private static final int REQUEST_INSTALL = 7422;
    private static final long MAX_APK_BYTES = 250L * 1024L * 1024L;
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();
    private static File pendingInstallFile;

    private AppUpdateManager() { }

    private static final class NoReleaseException extends Exception { }
    private static final class NoUpdateException extends Exception {
        NoUpdateException(String message) { super(message); }
    }
    private static final class SignatureMismatchException extends Exception {
        SignatureMismatchException() {
            super("Сертификат подписи APK не совпадает с установленным приложением. Установка остановлена, чтобы не повредить текущую установку.");
        }
    }
    private static final class AssetInfo {
        String name;
        String url;
        String digest;
        long size;
    }
    private static final class ReleaseInfo {
        String name;
        String tag;
        String body;
        AssetInfo apk;
        boolean prerelease;
    }

    public static void check(Activity activity) {
        if (!isAlive(activity)) return;
        new AlertDialog.Builder(activity)
            .setTitle("Канал обновлений")
            .setMessage("Выберите, какие обновления проверить. Тестовые сборки предназначены для желающих помочь с проверкой новых функций и могут содержать диагностические изменения.")
            .setSingleChoiceItems(new String[]{"Стабильные обновления", "Тестовые сборки"}, 0, (dialog, which) -> {
                dialog.dismiss();
                checkChannel(activity, which == 1);
            })
            .setNegativeButton("Отмена", null)
            .show();
    }

    private static void checkChannel(Activity activity, boolean testChannel) {
        if (!isAlive(activity)) return;
        ProgressDialog progress = new ProgressDialog(activity);
        progress.setTitle("RuFilmTV");
        progress.setMessage(testChannel ? "Проверяем тестовые сборки…" : "Проверяем стабильные обновления…");
        progress.setIndeterminate(true);
        progress.setCancelable(false);
        progress.show();

        EXECUTOR.execute(() -> {
            try {
                ReleaseInfo release = fetchLatestRelease(testChannel);
                PackageInfo installed = getInstalledPackage(activity);
                activity.runOnUiThread(() -> {
                    if (!isAlive(activity)) return;
                    progress.dismiss();
                    showReleaseDialog(activity, release, installed);
                });
            } catch (NoReleaseException e) {
                activity.runOnUiThread(() -> {
                    if (!isAlive(activity)) return;
                    progress.dismiss();
                    String message = testChannel
                        ? "В тестовом канале пока нет опубликованных сборок. Когда появится новая тестовая версия, она будет доступна здесь."
                        : "В публичном репозитории пока нет опубликованных стабильных GitHub Releases.";
                    new AlertDialog.Builder(activity)
                        .setTitle("Обновлений пока нет")
                        .setMessage(message)
                        .setPositiveButton("Понятно", null)
                        .show();
                });
            } catch (Exception e) {
                activity.runOnUiThread(() -> {
                    if (!isAlive(activity)) return;
                    progress.dismiss();
                    showError(activity, "Не удалось проверить обновления", readableError(e));
                });
            }
        });
    }

    private static ReleaseInfo fetchLatestRelease(boolean testChannel) throws Exception {
        String endpoint = testChannel ? TEST_RELEASES_API : STABLE_RELEASE_API;
        HttpURLConnection connection = openConnection(endpoint);
        try {
            int status = connection.getResponseCode();
            if (status == 404) throw new NoReleaseException();
            if (status != 200) throw new java.io.IOException("GitHub API вернул HTTP " + status);
            String response = readText(connection.getInputStream(), 2 * 1024 * 1024);
            JSONObject json;
            if (testChannel) {
                JSONArray releases = new JSONArray(response);
                json = null;
                for (int i = 0; i < releases.length(); i++) {
                    JSONObject candidate = releases.optJSONObject(i);
                    if (candidate != null && candidate.optBoolean("prerelease", false) &&
                        !candidate.optBoolean("draft", false)) {
                        json = candidate;
                        break;
                    }
                }
                if (json == null) throw new NoReleaseException();
            } else {
                json = new JSONObject(response);
            }

            ReleaseInfo release = new ReleaseInfo();
            release.name = json.optString("name", "");
            release.tag = json.optString("tag_name", "");
            release.body = json.optString("body", "").trim();
            release.prerelease = json.optBoolean("prerelease", false);
            JSONArray assets = json.optJSONArray("assets");
            if (assets == null) throw new java.io.IOException("В Release нет списка файлов.");
            for (int i = 0; i < assets.length(); i++) {
                JSONObject item = assets.optJSONObject(i);
                if (item == null) continue;
                String name = item.optString("name", "");
                if (!name.toLowerCase(Locale.ROOT).endsWith(".apk")) continue;
                AssetInfo asset = new AssetInfo();
                asset.name = name;
                asset.url = item.optString("browser_download_url", "");
                asset.digest = item.optString("digest", "").trim();
                asset.size = item.optLong("size", 0L);
                release.apk = asset;
                break;
            }
            if (release.apk == null) throw new java.io.IOException("В выбранном Release не найден APK-файл.");
            if (release.apk.url.isEmpty() || !isGithubDownloadUrl(release.apk.url))
                throw new java.io.IOException("Ссылка на APK не прошла проверку домена GitHub.");
            if (release.apk.size <= 0L || release.apk.size > MAX_APK_BYTES)
                throw new java.io.IOException("Размер APK отсутствует или превышает допустимые 250 МБ.");
            if (release.apk.digest.startsWith("sha256:"))
                release.apk.digest = release.apk.digest.substring("sha256:".length());
            if (!release.apk.digest.matches("(?i)[0-9a-f]{64}"))
                throw new java.io.IOException("GitHub не предоставил корректный SHA-256 для APK. Добавьте APK как asset Release с SHA-256 digest.");
            return release;
        } finally {
            connection.disconnect();
        }
    }

    private static boolean isGithubDownloadUrl(String value) {
        try {
            URL url = new URL(value);
            return "https".equalsIgnoreCase(url.getProtocol()) &&
                "github.com".equalsIgnoreCase(url.getHost());
        } catch (Exception e) {
            return false;
        }
    }

    private static HttpURLConnection openConnection(String address) throws Exception {
        URL url = new URL(address);
        if (!"https".equalsIgnoreCase(url.getProtocol()))
            throw new java.io.IOException("Разрешены только HTTPS-соединения.");
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(30000);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("User-Agent", USER_AGENT);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        return connection;
    }

    private static String readText(InputStream input, int limit) throws Exception {
        StringBuilder result = new StringBuilder();
        try (InputStream in = input;
             BufferedReader reader = new BufferedReader(new InputStreamReader(in, "UTF-8"))) {
            char[] buffer = new char[4096];
            int total = 0;
            int count;
            while ((count = reader.read(buffer)) != -1) {
                total += count;
                if (total > limit) throw new java.io.IOException("Ответ GitHub слишком большой.");
                result.append(buffer, 0, count);
            }
        }
        return result.toString();
    }

    private static void showReleaseDialog(Activity activity, ReleaseInfo release, PackageInfo installed) {
        String currentName = installed.versionName == null ? "—" : installed.versionName;
        String releaseTitle = !release.name.isEmpty() ? release.name : release.tag;
        String notes = release.body.isEmpty() ? "Разработчик не добавил описание изменений." : release.body;
        String message = "Установлено: " + currentName + " (versionCode " + versionCode(installed) + ")\n" +
            "Последний релиз: " + release.tag + "\n" +
            "APK: " + release.apk.name + "\n\n" +
            notes + "\n\n" +
            "После загрузки приложение проверит applicationId, versionCode/versionName, SHA-256 и сертификат подписи. Затем откроется штатный установщик Android с подтверждением.";
        String dialogTitle = release.prerelease ? "Тестовая сборка: " + releaseTitle : releaseTitle;
        new AlertDialog.Builder(activity)
            .setTitle(dialogTitle.isEmpty() ? "Доступен GitHub Release" : dialogTitle)
            .setMessage(message)
            .setPositiveButton("Скачать и установить", (dialog, which) ->
                downloadVerifyAndInstall(activity, release))
            .setNegativeButton("Позже", null)
            .show();
    }

    private static void downloadVerifyAndInstall(Activity activity, ReleaseInfo release) {
        if (!isAlive(activity)) return;
        ProgressDialog progress = new ProgressDialog(activity);
        progress.setTitle("RuFilmTV");
        progress.setMessage("Скачиваем APK…");
        progress.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        progress.setIndeterminate(false);
        progress.setMax(100);
        progress.setProgress(0);
        progress.setCancelable(false);
        progress.show();

        EXECUTOR.execute(() -> {
            File apk = null;
            try {
                File folder = new File(activity.getCacheDir(), "updates");
                if (!folder.exists() && !folder.mkdirs())
                    throw new java.io.IOException("Не удалось создать каталог для обновления.");
                apk = new File(folder, "rufilm-update.apk");
                downloadAsset(release.apk, apk, progress, activity);
                String actualDigest = sha256(apk);
                if (!actualDigest.equalsIgnoreCase(release.apk.digest))
                    throw new java.io.IOException("SHA-256 не совпал. APK удалён, установка запрещена.");

                PackageInfo candidate = getArchivePackage(activity, apk);
                if (candidate == null) throw new java.io.IOException("Android не распознал скачанный APK.");
                if (!activity.getPackageName().equals(candidate.packageName))
                    throw new java.io.IOException("applicationId APK не совпадает с установленным приложением.");
                PackageInfo installed = getInstalledPackage(activity);
                long candidateCode = versionCode(candidate);
                long installedCode = versionCode(installed);
                if (candidateCode <= installedCode) {
                    String candidateName = candidate.versionName == null ? "—" : candidate.versionName;
                    throw new NoUpdateException("Установлена версия " + installed.versionName +
                        " (code " + installedCode + "). В Release находится " + candidateName +
                        " (code " + candidateCode + "); более новой версии нет.");
                }
                if (!sameSigningCertificates(installed, candidate))
                    throw new SignatureMismatchException();

                File verifiedApk = apk;
                String installedName = installed.versionName == null ? "—" : installed.versionName;
                String candidateName = candidate.versionName == null ? "—" : candidate.versionName;
                activity.runOnUiThread(() -> {
                    if (!isAlive(activity)) return;
                    progress.dismiss();
                    showVerifiedUpdateDialog(activity, verifiedApk,
                        installedName, installedCode, candidateName, candidateCode);
                });
            } catch (Exception e) {
                if (apk != null && apk.exists()) apk.delete();
                activity.runOnUiThread(() -> {
                    if (!isAlive(activity)) return;
                    progress.dismiss();
                    showError(activity, e instanceof NoUpdateException ? "Обновлений нет" : "Обновление не установлено", readableError(e));
                });
            }
        });
    }

    private static void downloadAsset(AssetInfo asset, File destination,
                                      ProgressDialog progress, Activity activity) throws Exception {
        HttpURLConnection connection = openConnection(asset.url);
        try {
            connection.setRequestProperty("Accept", "application/octet-stream");
            int status = connection.getResponseCode();
            if (status != 200) throw new java.io.IOException("Не удалось скачать APK: HTTP " + status);
            long expected = connection.getContentLength();
            if (expected > MAX_APK_BYTES) throw new java.io.IOException("APK превышает допустимый размер.");
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = connection.getInputStream();
                 FileOutputStream output = new FileOutputStream(destination)) {
                byte[] buffer = new byte[32768];
                long total = 0L;
                int count;
                while ((count = input.read(buffer)) != -1) {
                    total += count;
                    if (total > MAX_APK_BYTES) throw new java.io.IOException("Загрузка превысила 250 МБ.");
                    output.write(buffer, 0, count);
                    digest.update(buffer, 0, count);
                    if (expected > 0L) {
                        int value = (int)Math.min(100L, total * 100L / expected);
                        activity.runOnUiThread(() -> {
                            if (isAlive(activity)) progress.setProgress(value);
                        });
                    }
                }
                output.flush();
            }
            String actual = toHex(digest.digest());
            if (!actual.equalsIgnoreCase(asset.digest))
                throw new java.io.IOException("SHA-256 не совпал. Загрузка будет удалена.");
        } finally {
            connection.disconnect();
        }
    }

    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new java.io.FileInputStream(file)) {
            byte[] buffer = new byte[32768];
            int count;
            while ((count = input.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        return toHex(digest.digest());
    }

    private static String toHex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return result.toString();
    }

    private static PackageInfo getInstalledPackage(Activity activity) throws Exception {
        return activity.getPackageManager().getPackageInfo(activity.getPackageName(), packageInfoFlags());
    }

    private static PackageInfo getArchivePackage(Activity activity, File apk) {
        return activity.getPackageManager().getPackageArchiveInfo(apk.getAbsolutePath(), packageInfoFlags());
    }

    private static int packageInfoFlags() {
        return Build.VERSION.SDK_INT >= 28
            ? PackageManager.GET_SIGNING_CERTIFICATES
            : PackageManager.GET_SIGNATURES;
    }

    private static long versionCode(PackageInfo info) {
        return Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
    }

    private static Set<String> signingFingerprints(PackageInfo info) throws Exception {
        Signature[] signatures = null;
        if (Build.VERSION.SDK_INT >= 28 && info.signingInfo != null)
            signatures = info.signingInfo.getApkContentsSigners();
        if (signatures == null || signatures.length == 0)
            signatures = info.signatures;
        if (signatures == null || signatures.length == 0)
            throw new java.io.IOException("Не удалось прочитать сертификат подписи APK.");
        Set<String> result = new HashSet<>();
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (Signature signature : signatures) {
            digest.reset();
            result.add(toHex(digest.digest(signature.toByteArray())));
        }
        return result;
    }

    private static boolean sameSigningCertificates(PackageInfo installed, PackageInfo candidate) throws Exception {
        return signingFingerprints(installed).equals(signingFingerprints(candidate));
    }

    private static void showVerifiedUpdateDialog(Activity activity, File apk,
                                                  String installedName, long installedCode,
                                                  String candidateName, long candidateCode) {
        String comparison = installedName.equals(candidateName)
            ? "versionName не изменился, но versionCode увеличился."
            : "versionName изменился.";
        String message = "Текущая версия: " + installedName + " (versionCode " + installedCode + ")\n" +
            "Новая версия: " + candidateName + " (versionCode " + candidateCode + ")\n\n" +
            "SHA-256 APK проверен. applicationId и сертификат подписи совпадают. " + comparison + "\n\n" +
            "Далее откроется штатный установщик Android, который отдельно запросит подтверждение.";
        new AlertDialog.Builder(activity)
            .setTitle("Обновление проверено")
            .setMessage(message)
            .setPositiveButton("Открыть установщик", (dialog, which) -> {
                pendingInstallFile = apk;
                requestInstallPermissionOrLaunch(activity);
            })
            .setNegativeButton("Отмена", (dialog, which) -> apk.delete())
            .show();
    }

    private static void requestInstallPermissionOrLaunch(Activity activity) {
        if (pendingInstallFile == null || !pendingInstallFile.isFile()) {
            showError(activity, "Обновление", "Проверенный APK не найден в кэше.");
            return;
        }
        if (Build.VERSION.SDK_INT >= 26 && !activity.getPackageManager().canRequestPackageInstalls()) {
            try {
                Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + activity.getPackageName()));
                activity.startActivityForResult(settings, REQUEST_UNKNOWN_SOURCES);
            } catch (Exception e) {
                showError(activity, "Разрешение на установку", "Откройте системные настройки и разрешите этому приложению установку неизвестных приложений.");
            }
            return;
        }
        launchPackageInstaller(activity);
    }

    private static void launchPackageInstaller(Activity activity) {
        try {
            Uri uri = FileProvider.getUriForFile(activity,
                activity.getPackageName() + ".fileprovider", pendingInstallFile);
            Intent install = new Intent(Intent.ACTION_INSTALL_PACKAGE);
            install.setDataAndType(uri, "application/vnd.android.package-archive");
            install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            install.putExtra(Intent.EXTRA_RETURN_RESULT, true);
            activity.startActivityForResult(install, REQUEST_INSTALL);
        } catch (Exception e) {
            showError(activity, "Не удалось открыть установщик", readableError(e));
        }
    }

    public static void onActivityResult(Activity activity, int requestCode, int resultCode) {
        if (requestCode == REQUEST_UNKNOWN_SOURCES) {
            if (Build.VERSION.SDK_INT < 26 || activity.getPackageManager().canRequestPackageInstalls())
                launchPackageInstaller(activity);
            else
                Toast.makeText(activity, "Разрешение на установку не предоставлено.", Toast.LENGTH_LONG).show();
        } else if (requestCode == REQUEST_INSTALL) {
            if (resultCode == Activity.RESULT_OK) {
                Toast.makeText(activity, "Установщик Android завершил обновление.", Toast.LENGTH_LONG).show();
                if (pendingInstallFile != null) pendingInstallFile.delete();
                pendingInstallFile = null;
            } else {
                Toast.makeText(activity, "Установка отменена или не завершена.", Toast.LENGTH_LONG).show();
            }
        }
    }

    private static void showError(Activity activity, String title, String message) {
        new AlertDialog.Builder(activity)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("Закрыть", null)
            .show();
    }

    private static String readableError(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
            ? error.getClass().getSimpleName()
            : message;
    }

    private static boolean isAlive(Activity activity) {
        return activity != null && !activity.isFinishing() &&
            (Build.VERSION.SDK_INT < 17 || !activity.isDestroyed());
    }
}
