package tv.rufilm.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.ActivityInfo;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import org.videolan.libvlc.LibVLC;
import org.videolan.libvlc.Media;
import org.videolan.libvlc.MediaPlayer;
import org.videolan.libvlc.interfaces.IMedia;
import org.videolan.libvlc.util.VLCVideoLayout;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public class NativePlayerActivity extends Activity {
    public static final String EXTRA_URL = "media_url";
    public static final String EXTRA_AUDIO_URL = "media_audio_url";
    public static final String EXTRA_REFERER = "media_referer";
    public static final String EXTRA_USER_AGENT = "media_user_agent";
    public static final String EXTRA_HEADERS = "media_headers";
    public static final String EXTRA_EPISODE_SELECTORS = "episode_selectors";
    public static final String EXTRA_START_POSITION_MS = "start_position_ms";

    private LibVLC libVLC;
    private MediaPlayer player;
    private VLCVideoLayout videoLayout;
    private TextView currentTimeText, durationTimeText, playPauseButton;
    private TextView volumeButton, zoomButton;
    private SeekBar timelineSeek, volumeSeek;
    private LinearLayout controls, topBar;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean controlsVisible = true;
    private boolean zoomMode = false;
    private boolean startPositionApplied = false;
    private boolean released = false;
    private boolean failureFallbackScheduled = false;
    private float volumeBeforeMute = 100f;
    private long requestedStartPositionMs = 0L;
    private long captureBaselineForSelection = 0L;
    private String currentMediaUrl, currentReferer, currentUserAgent, currentAudioUrl;
    private HashMap<String,String> currentHeaders = new HashMap<>();

    private final Runnable updateTimeline = new Runnable() {
        @Override public void run() {
            if (player == null || released) return;
            long duration = player.getLength();
            long position = player.getTime();
            if (duration > 0) {
                if (timelineSeek != null && !timelineSeek.isPressed())
                    timelineSeek.setProgress((int)Math.min(1000L, Math.max(0L, position) * 1000L / duration));
                durationTimeText.setText(formatTime(duration));
            }
            currentTimeText.setText(formatTime(Math.max(0L, position)));
            MainActivity.syncOriginalPlayback(Math.max(0L, position), true);
            playPauseButton.setText(player.isPlaying() ? "Ⅱ" : "▶");
            handler.postDelayed(this, 500L);
        }
    };

    private final Runnable hideControls = () -> {
        if (player != null && !released) {
            controlsVisible = false;
            controls.setVisibility(View.GONE);
            topBar.setVisibility(View.GONE);
        }
    };

    private final Runnable syncEpisode = new Runnable() {
        @Override public void run() {
            if (player == null || released || isFinishing()) return;
            try {
                org.json.JSONObject snapshot = new org.json.JSONObject(MainActivity.getCapturedMediaSnapshot());
                long capturedAt = snapshot.optLong("capturedAt", 0L);
                String updated = snapshot.optString("url", "");
                if (capturedAt > captureBaselineForSelection && !updated.isEmpty() && !updated.equals(currentMediaUrl)) {
                    HashMap<String,String> headers = new HashMap<>();
                    org.json.JSONObject jsonHeaders = snapshot.optJSONObject("headers");
                    if (jsonHeaders != null) {
                        java.util.Iterator<String> keys = jsonHeaders.keys();
                        while (keys.hasNext()) {
                            String key = keys.next();
                            headers.put(key, jsonHeaders.optString(key, ""));
                        }
                    }
                    String referer = snapshot.optString("referer", currentReferer == null ? "" : currentReferer);
                    String ua = snapshot.optString("userAgent", currentUserAgent == null ? "" : currentUserAgent);
                    switchCapturedStream(updated, referer, ua, headers);
                    captureBaselineForSelection = capturedAt;
                }
            } catch (Exception e) {
                android.util.Log.w("RuFilmTV-VLC", "Episode stream refresh failed", e);
            }
            handler.postDelayed(this, 900L);
        }
    };

    @SuppressWarnings("unchecked")
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(android.graphics.Color.BLACK);
        getWindow().setNavigationBarColor(android.graphics.Color.BLACK);
        if (android.os.Build.VERSION.SDK_INT >= 19) getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);

        currentMediaUrl = getIntent().getStringExtra(EXTRA_URL);
        currentAudioUrl = getIntent().getStringExtra(EXTRA_AUDIO_URL);
        currentReferer = getIntent().getStringExtra(EXTRA_REFERER);
        currentUserAgent = getIntent().getStringExtra(EXTRA_USER_AGENT);
        requestedStartPositionMs = Math.max(0L, getIntent().getLongExtra(EXTRA_START_POSITION_MS, 0L));
        if (!validUrl(currentMediaUrl)) {
            Toast.makeText(this, "Не удалось получить прямую ссылку на видео", Toast.LENGTH_LONG).show();
            finish();
            return;
        }

        try {
            Object supplied = getIntent().getSerializableExtra(EXTRA_HEADERS);
            if (supplied instanceof Map) currentHeaders.putAll((Map<String,String>) supplied);
        } catch (Exception ignored) {}
        addHeaderIfPresent("Referer", currentReferer);
        if (currentUserAgent == null || currentUserAgent.trim().isEmpty())
            currentUserAgent = WebSettings.getDefaultUserAgent(this);
        addHeaderIfPresent("User-Agent", currentUserAgent);
        try {
            String cookie = CookieManager.getInstance().getCookie(currentMediaUrl);
            if (cookie != null && !cookie.isEmpty() && !containsHeader("Cookie")) currentHeaders.put("Cookie", cookie);
        } catch (Exception ignored) {}

        buildInterface();
        ArrayList<String> options = new ArrayList<>();
        options.add("--no-video-title-show");
        options.add("--network-caching=1500");
        options.add("--file-caching=1000");
        options.add("--avcodec-hw=any");
        options.add("--no-sout-keep");
        options.add("--verbose=1");
        try {
            libVLC = new LibVLC(this, options);
            player = new MediaPlayer(libVLC);
            player.attachViews(videoLayout, null, false, false);
            player.setEventListener(event -> {
                if (event.type == MediaPlayer.Event.Playing && !startPositionApplied && requestedStartPositionMs > 0L) {
                    startPositionApplied = true;
                    handler.postDelayed(() -> {
                        if (player != null && !released) player.setTime(requestedStartPositionMs);
                    }, 350L);
                } else if (event.type == MediaPlayer.Event.EncounteredError) {
                    runOnUiThread(() -> {
                        Toast.makeText(this, "VLC не смог открыть видеопоток", Toast.LENGTH_LONG).show();
                        android.util.Log.e("RuFilmTV-VLC", "LibVLC encountered playback error for " + diagnosticUrl(currentMediaUrl));
                        if (!failureFallbackScheduled) {
                            failureFallbackScheduled = true;
                            handler.postDelayed(() -> { if (!isFinishing()) { releasePlayer(); finish(); } }, 2200L);
                        }
                    });
                }
            });
            openStream(currentMediaUrl, currentAudioUrl, currentHeaders, true);
            handler.post(updateTimeline);
            handler.postDelayed(syncEpisode, 1200L);
            showControls();
        } catch (Exception e) {
            android.util.Log.e("RuFilmTV-VLC", "LibVLC initialization failed", e);
            Toast.makeText(this, "Не удалось запустить LibVLC: " + e.getClass().getSimpleName(), Toast.LENGTH_LONG).show();
            finish();
        }
    }

    private void buildInterface() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(android.graphics.Color.BLACK);
        videoLayout = new VLCVideoLayout(this);
        root.addView(videoLayout, new FrameLayout.LayoutParams(-1, -1));

        FrameLayout overlay = new FrameLayout(this);
        overlay.setClickable(false);
        root.addView(overlay, new FrameLayout.LayoutParams(-1, -1));

        topBar = new LinearLayout(this);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setPadding(dp(22), dp(8), dp(22), dp(8));
        topBar.setBackgroundColor(0x55000000);
        FrameLayout.LayoutParams topParams = new FrameLayout.LayoutParams(-1, dp(54), Gravity.TOP);
        overlay.addView(topBar, topParams);
        TextView title = controlText("RUFILM TV · VLC", 16);
        title.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        topBar.addView(title, new LinearLayout.LayoutParams(0, -1, 1f));
        TextView exit = controlText("Выход", 14);
        topBar.addView(exit, new LinearLayout.LayoutParams(dp(76), -1));
        exit.setOnClickListener(v -> { releasePlayer(); finish(); });
        TextView menu = controlText("⋮", 28);
        topBar.addView(menu, new LinearLayout.LayoutParams(dp(48), -1));
        menu.setOnClickListener(v -> showMenu());

        controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.VERTICAL);
        controls.setPadding(dp(18), dp(8), dp(18), dp(10));
        controls.setBackgroundColor(0x55000000);
        FrameLayout.LayoutParams bottom = new FrameLayout.LayoutParams(-1, dp(124), Gravity.BOTTOM);
        overlay.addView(controls, bottom);

        LinearLayout timeline = new LinearLayout(this);
        timeline.setGravity(Gravity.CENTER_VERTICAL);
        controls.addView(timeline, new LinearLayout.LayoutParams(-1, dp(34)));
        currentTimeText = controlText("0:00", 11);
        timeline.addView(currentTimeText, new LinearLayout.LayoutParams(dp(50), -2));
        timelineSeek = new SeekBar(this);
        timelineSeek.setMax(1000);
        timelineSeek.setFocusable(true);
        timeline.addView(timelineSeek, new LinearLayout.LayoutParams(0, dp(32), 1f));
        durationTimeText = controlText("0:00", 11);
        timeline.addView(durationTimeText, new LinearLayout.LayoutParams(dp(50), -2));
        timelineSeek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean fromUser) {
                if (fromUser && player != null) {
                    long length = player.getLength();
                    if (length > 0) currentTimeText.setText(formatTime(length * value / 1000L));
                }
            }
            @Override public void onStartTrackingTouch(SeekBar bar) { showControls(); }
            @Override public void onStopTrackingTouch(SeekBar bar) {
                if (player != null && player.getLength() > 0)
                    player.setTime(player.getLength() * bar.getProgress() / 1000L);
                scheduleHide();
            }
        });

        FrameLayout row = new FrameLayout(this);
        controls.addView(row, new LinearLayout.LayoutParams(-1, dp(62)));
        LinearLayout transport = new LinearLayout(this);
        transport.setGravity(Gravity.CENTER);
        row.addView(transport, new FrameLayout.LayoutParams(-2, -1, Gravity.CENTER));
        TextView back = controlText("↶10", 17);
        transport.addView(back, new LinearLayout.LayoutParams(dp(58), -1));
        back.setOnClickListener(v -> seekBy(-10000L));
        playPauseButton = controlText("▶", 28);
        transport.addView(playPauseButton, new LinearLayout.LayoutParams(dp(68), -1));
        playPauseButton.setOnClickListener(v -> {
            if (player != null) { if (player.isPlaying()) player.pause(); else player.play(); }
            showControls();
        });
        TextView forward = controlText("10↷", 17);
        transport.addView(forward, new LinearLayout.LayoutParams(dp(58), -1));
        forward.setOnClickListener(v -> seekBy(10000L));

        LinearLayout volume = new LinearLayout(this);
        volume.setGravity(Gravity.CENTER_VERTICAL);
        row.addView(volume, new FrameLayout.LayoutParams(-2, -1, Gravity.LEFT | Gravity.CENTER_VERTICAL));
        volumeButton = controlText("🔊", 18);
        volume.addView(volumeButton, new LinearLayout.LayoutParams(dp(46), -1));
        volumeButton.setOnClickListener(v -> {
            if (player == null) return;
            int current = player.getVolume();
            if (current > 0) { volumeBeforeMute = current; player.setVolume(0); }
            else player.setVolume((int)Math.max(1f, volumeBeforeMute));
            updateVolume();
            showControls();
        });
        volumeSeek = new SeekBar(this);
        volumeSeek.setMax(200);
        volumeSeek.setProgress(100);
        volumeSeek.setFocusable(true);
        volume.addView(volumeSeek, new LinearLayout.LayoutParams(dp(130), dp(44)));
        volumeSeek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean fromUser) {
                if (fromUser && player != null) {
                    player.setVolume(value);
                    if (value > 0) volumeBeforeMute = value;
                    updateVolumeButton();
                }
            }
            @Override public void onStartTrackingTouch(SeekBar bar) { showControls(); }
            @Override public void onStopTrackingTouch(SeekBar bar) { scheduleHide(); }
        });

        zoomButton = controlText("⛶", 23);
        row.addView(zoomButton, new FrameLayout.LayoutParams(dp(54), -1, Gravity.RIGHT | Gravity.CENTER_VERTICAL));
        zoomButton.setOnClickListener(v -> {
            zoomMode = !zoomMode;
            if (player != null) player.setScale(zoomMode ? 0f : 0f);
            if (player != null) player.setAspectRatio(zoomMode ? "16:9" : null);
            showControls();
        });

        overlay.setOnClickListener(v -> toggleControls());
        root.setOnClickListener(v -> toggleControls());
        setContentView(root);
    }

    private void openStream(String url, String audioUrl, Map<String,String> headers, boolean initial) {
        if (!validUrl(url) || player == null) return;
        try {
            boolean useProxy = audioUrl != null || isOkOrVk(url);
            String playbackUrl = createPlaybackUrl(url, headers, useProxy);
            Media media = new Media(libVLC, Uri.parse(playbackUrl));
            addMediaOptions(media, headers);
            media.addOption(":network-caching=1500");
            media.addOption(":clock-jitter=0");
            media.addOption(":clock-synchro=0");
            player.stop();
            player.setMedia(media);
            media.release();
            if (audioUrl != null && validUrl(audioUrl)) {
                String audioPlaybackUrl = createPlaybackUrl(audioUrl, headers, true);
                boolean added = player.addSlave(IMedia.Slave.Type.Audio, Uri.parse(audioPlaybackUrl), true);
                android.util.Log.i("RuFilmTV-VLC", "OK.ru external audio slave attached=" + added);
            }
            player.play();
            if (initial) android.util.Log.i("RuFilmTV-VLC", "LibVLC stream opened route=" +
                (useProxy ? "LOCAL_PROXY" : "DIRECT") + " url=" + diagnosticUrl(url));
        } catch (Exception e) {
            android.util.Log.e("RuFilmTV-VLC", "Could not open stream", e);
            Toast.makeText(this, "Ошибка запуска VLC: " + e.getClass().getSimpleName(), Toast.LENGTH_LONG).show();
        }
    }

    private void addMediaOptions(Media media, Map<String,String> headers) {
        String ua = header(headers, "User-Agent");
        String referer = header(headers, "Referer");
        String cookie = header(headers, "Cookie");
        if (ua != null) media.addOption(":http-user-agent=" + safeOption(ua));
        if (referer != null) media.addOption(":http-referrer=" + safeOption(referer));
        if (cookie != null) media.addOption(":http-cookie=" + safeOption(cookie));
        String origin = header(headers, "Origin");
        if (origin != null) media.addOption(":http-origin=" + safeOption(origin));
        media.addOption(":avcodec-hw=any");
    }

    private void switchCapturedStream(String url, String referer, String ua, HashMap<String,String> headers) {
        if (!validUrl(url) || player == null || released) return;
        if (referer != null && !referer.isEmpty()) headers.put("Referer", referer);
        if (ua != null && !ua.isEmpty()) headers.put("User-Agent", ua);
        try {
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null && !cookie.isEmpty()) headers.put("Cookie", cookie);
        } catch (Exception ignored) {}
        if (!headers.containsKey("User-Agent")) headers.put("User-Agent", WebSettings.getDefaultUserAgent(this));
        currentMediaUrl = url;
        currentReferer = referer;
        currentUserAgent = headers.get("User-Agent");
        currentHeaders = new HashMap<>(headers);
        currentAudioUrl = null;
        startPositionApplied = true;
        openStream(url, null, headers, false);
        android.util.Log.i("RuFilmTV-VLC", "Episode stream switched to " + diagnosticUrl(url));
    }

    private String createPlaybackUrl(String sourceUrl, Map<String,String> headers, boolean useProxy) {
        if (!useProxy) return sourceUrl;
        try {
            String proxy = LocalStreamProxy.start(sourceUrl, headers);
            android.util.Log.i("RuFilmTV-VLC", "Authenticated proxy started for " + diagnosticUrl(sourceUrl));
            return proxy;
        } catch (Exception e) {
            android.util.Log.e("RuFilmTV-VLC", "Proxy startup failed; using source URL directly", e);
            return sourceUrl;
        }
    }

    private boolean isOkOrVk(String url) {
        String value = (url == null ? "" : url).toLowerCase(Locale.ROOT);
        String ref = (currentReferer == null ? "" : currentReferer).toLowerCase(Locale.ROOT);
        return value.contains("ok.ru") || value.contains("odnoklassniki") || ref.contains("ok.ru") ||
            value.contains("vk.com") || value.contains("vk.ru") || ref.contains("vk.com");
    }

    private void addHeaderIfPresent(String key, String value) {
        if (value != null && !value.trim().isEmpty() && !containsHeader(key)) currentHeaders.put(key, value);
    }
    private boolean containsHeader(String key) {
        for (String k : currentHeaders.keySet()) if (k != null && k.equalsIgnoreCase(key)) return true;
        return false;
    }
    private String header(Map<String,String> headers, String key) {
        if (headers == null) return null;
        for (Map.Entry<String,String> entry : headers.entrySet())
            if (entry.getKey() != null && key.equalsIgnoreCase(entry.getKey())) return entry.getValue();
        return null;
    }
    private String safeOption(String value) { return value == null ? "" : value.replace("\r","").replace("\n",""); }
    private boolean validUrl(String value) {
        return value != null && (value.startsWith("https://") || value.startsWith("http://"));
    }
    private void seekBy(long delta) {
        if (player != null) {
            long length = player.getLength();
            long current = Math.max(0L, player.getTime());
            player.setTime(Math.max(0L, length > 0 ? Math.min(length, current + delta) : current + delta));
        }
        showControls();
    }
    private void updateVolume() {
        if (player == null) return;
        int value = Math.max(0, player.getVolume());
        if (volumeSeek != null && volumeSeek.getProgress() != value) volumeSeek.setProgress(Math.min(200, value));
        updateVolumeButton();
    }
    private void updateVolumeButton() {
        if (volumeButton != null && player != null)
            volumeButton.setText(player.getVolume() <= 0 ? "🔇" : (player.getVolume() < 70 ? "🔉" : "🔊"));
    }
    private void showMenu() {
        new AlertDialog.Builder(this).setTitle("Плеер VLC")
            .setItems(new String[]{"Качество и дорожки выбираются источником", "Скрыть панель"}, (d, which) -> {
                if (which == 1) hideControls();
            }).show();
        showControls();
    }
    private void showControls() {
        if (controls == null) return;
        controlsVisible = true;
        controls.setVisibility(View.VISIBLE);
        topBar.setVisibility(View.VISIBLE);
        scheduleHide();
    }
    private void hideControls() {
        controlsVisible = false;
        controls.setVisibility(View.GONE);
        topBar.setVisibility(View.GONE);
    }
    private void toggleControls() { if (controlsVisible) hideControls(); else showControls(); }
    private void scheduleHide() {
        handler.removeCallbacks(hideControls);
        handler.postDelayed(hideControls, 5000L);
    }
    private TextView controlText(String value, int size) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextColor(android.graphics.Color.WHITE);
        t.setTextSize(size);
        t.setGravity(Gravity.CENTER);
        t.setFocusable(true);
        return t;
    }
    private String formatTime(long ms) {
        long total = Math.max(0L, ms / 1000L);
        long h = total / 3600L, m = (total % 3600L) / 60L, sec = total % 60L;
        return h > 0 ? String.format(Locale.ROOT, "%d:%02d:%02d", h, m, sec)
            : String.format(Locale.ROOT, "%d:%02d", m, sec);
    }
    private String diagnosticUrl(String value) {
        try { Uri u = Uri.parse(value); return (u.getHost() == null ? "unknown" : u.getHost()) + (u.getPath() == null ? "/" : u.getPath()); }
        catch (Exception ignored) { return "invalid-url"; }
    }
    private int dp(int value) { return (int)(value * getResources().getDisplayMetrics().density + 0.5f); }

    @Override public void onUserInteraction() {
        super.onUserInteraction();
        if (controls != null && player != null) showControls();
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent event) {
        if (event != null && (event.getAction() == MotionEvent.ACTION_HOVER_ENTER ||
            event.getAction() == MotionEvent.ACTION_HOVER_MOVE || event.getAction() == MotionEvent.ACTION_SCROLL))
            showControls();
        return super.dispatchGenericMotionEvent(event);
    }
    @Override protected void onStop() { super.onStop(); releasePlayer(); }
    @Override protected void onDestroy() { releasePlayer(); super.onDestroy(); }
    @Override public void onBackPressed() { releasePlayer(); super.onBackPressed(); }

    private void releasePlayer() {
        if (released) return;
        released = true;
        handler.removeCallbacks(updateTimeline);
        handler.removeCallbacks(syncEpisode);
        handler.removeCallbacks(hideControls);
        if (player != null) {
            try {
                MainActivity.syncOriginalPlayback(Math.max(0L, player.getTime()), false);
                player.setEventListener(null);
                player.stop();
                player.detachViews();
                player.release();
            } catch (Exception e) {
                android.util.Log.w("RuFilmTV-VLC", "Player release warning", e);
            }
            player = null;
        }
        if (libVLC != null) {
            try { libVLC.release(); } catch (Exception ignored) {}
            libVLC = null;
        }
    }
}
