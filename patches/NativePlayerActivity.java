package tv.rufilm.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.ActivityInfo;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.Toast;
import android.webkit.CookieManager;

import androidx.media3.common.C;
import androidx.media3.common.Format;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.Player;
import androidx.media3.common.TrackGroup;
import androidx.media3.common.TrackSelectionOverride;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.DefaultRenderersFactory;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector;
import androidx.media3.exoplayer.trackselection.MappingTrackSelector;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.ui.AspectRatioFrameLayout;
import androidx.media3.ui.PlayerView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;

public class NativePlayerActivity extends Activity {
    public static final String EXTRA_URL = "media_url";
    public static final String EXTRA_REFERER = "media_referer";
    public static final String EXTRA_USER_AGENT = "media_user_agent";
    public static final String EXTRA_HEADERS = "media_headers";
    public static final String EXTRA_EPISODE_SELECTORS = "episode_selectors";
    public static final String EXTRA_START_POSITION_MS = "start_position_ms";

    private ExoPlayer player;
    private boolean fallbackToOriginalScheduled;
    private PlayerView playerView;
    private DefaultTrackSelector trackSelector;
    private Button qualityButton;
    private Button volumeButton;
    private android.widget.SeekBar volumeSeekBar;
    private float volumeBeforeMute = 1.0f;
    private android.widget.SeekBar timelineSeek;
    private android.widget.TextView currentTimeText, durationTimeText, playPauseButton;
    private android.widget.TextView displayButton;
    private android.widget.LinearLayout assistantControls, assistantTopBar;
    private boolean controlsVisible = true;
    private boolean zoomMode = false;
    private final android.os.Handler assistantHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable updateTimeline = new Runnable() {
        @Override public void run() {
            if (player != null && timelineSeek != null) {
                long duration = player.getDuration();
                long position = player.getCurrentPosition();
                if (duration > 0 && duration != C.TIME_UNSET) {
                    if (!timelineSeek.isPressed()) timelineSeek.setProgress((int)Math.min(1000L, position * 1000L / duration));
                    durationTimeText.setText(formatTime(duration));
                }
                currentTimeText.setText(formatTime(position));
                playPauseButton.setText(player.isPlaying() ? "Ⅱ" : "▶");
                assistantHandler.postDelayed(this, 500L);
            }
        }
    };

    private String currentMediaUrl;
    private String currentReferer;
    private String currentUserAgent;
    private HashMap<String, String> currentHeaders = new HashMap<>();
    private long captureBaselineForSelection = 0L;
    private long requestedStartPositionMs = 0L;
    private boolean startPositionApplied = false;
    private final android.os.Handler syncHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable syncRunnable = new Runnable() { public void run() { if (player != null && !isFinishing()) { MainActivity.syncOriginalPlayback(player.getCurrentPosition(), true); syncHandler.postDelayed(this, 650L); } } };

    private static class QualityOption {
        final TrackGroup group;
        final int trackIndex;
        final int height;
        QualityOption(TrackGroup group, int trackIndex, int height) {
            this.group = group; this.trackIndex = trackIndex; this.height = height;
        }
        String label() { return height > 0 ? height + "p" : "Неизвестно"; }
    }

    @SuppressWarnings("unchecked")
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(android.graphics.Color.BLACK);
        getWindow().setNavigationBarColor(android.graphics.Color.BLACK);
        if (android.os.Build.VERSION.SDK_INT >= 19) {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);

        String rawUrl = getIntent().getStringExtra(EXTRA_URL);
        currentMediaUrl = rawUrl;
        String referer = getIntent().getStringExtra(EXTRA_REFERER);
        String userAgent = getIntent().getStringExtra(EXTRA_USER_AGENT);
        currentReferer = referer;
        currentUserAgent = userAgent;
        if (rawUrl == null || !(rawUrl.startsWith("http://") || rawUrl.startsWith("https://"))) {
            Toast.makeText(this, "Не удалось получить прямую ссылку на видео", Toast.LENGTH_LONG).show();
            finish(); return;
        }

        Map<String, String> headers = new HashMap<>();
        try {
            Object supplied = getIntent().getSerializableExtra(EXTRA_HEADERS);
            if (supplied instanceof Map) headers.putAll((Map<String, String>) supplied);
        } catch (Exception ignored) { }
        if (userAgent != null && !userAgent.trim().isEmpty()) headers.put("User-Agent", userAgent);
        if (referer != null && !referer.trim().isEmpty()) {
            headers.put("Referer", referer);
            if (!headers.containsKey("Origin")) {
                try {
                    Uri page = Uri.parse(referer);
                    if (page.getScheme() != null && page.getHost() != null)
                        headers.put("Origin", page.getScheme() + "://" + page.getHost());
                } catch (Exception ignored) { }
            }
        }
        try {
            String cookie = CookieManager.getInstance().getCookie(rawUrl);
            if ((headers.get("Cookie") == null || headers.get("Cookie").isEmpty()) && cookie != null && !cookie.isEmpty())
                headers.put("Cookie", cookie);
        } catch (Exception ignored) { }

        String effectiveUa = userAgent == null || userAgent.isEmpty()
            ? android.webkit.WebSettings.getDefaultUserAgent(this)
            : userAgent;
        currentUserAgent = effectiveUa;
        currentHeaders.putAll(headers);
        currentHeaders.put("User-Agent", effectiveUa);
        DefaultHttpDataSource.Factory httpFactory = new DefaultHttpDataSource.Factory()
            .setUserAgent(effectiveUa)
            .setAllowCrossProtocolRedirects(true)
            .setConnectTimeoutMs(20000)
            .setReadTimeoutMs(45000)
            .setDefaultRequestProperties(headers);
        DefaultMediaSourceFactory mediaSourceFactory = new DefaultMediaSourceFactory(
            new DefaultDataSource.Factory(this, httpFactory));
        trackSelector = new DefaultTrackSelector(this);
        trackSelector.setParameters(trackSelector.buildUponParameters()
            .setTunnelingEnabled(false)
            .setTrackTypeDisabled(C.TRACK_TYPE_VIDEO, false));
        DefaultRenderersFactory renderersFactory = new DefaultRenderersFactory(this)
            .setEnableDecoderFallback(true);
        player = new ExoPlayer.Builder(this, renderersFactory)
            .setMediaSourceFactory(mediaSourceFactory)
            .setTrackSelector(trackSelector)
            .build();

        FrameLayout root = new FrameLayout(this);
        playerView = new PlayerView(this);
        playerView.setUseController(true);
        playerView.setControllerAutoShow(true);
        playerView.setResizeMode(AspectRatioFrameLayout.RESIZE_MODE_FIT);
        playerView.setKeepScreenOn(true);
        playerView.setBackgroundColor(android.graphics.Color.BLACK);
        playerView.setPlayer(player);
        root.addView(playerView, new FrameLayout.LayoutParams(-1, -1));


        playerView.setUseController(false);
        FrameLayout overlay = new FrameLayout(this);
        overlay.setClickable(false);
        root.addView(overlay, new FrameLayout.LayoutParams(-1, -1));

        android.widget.LinearLayout top = new android.widget.LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(22), dp(10), dp(22), dp(10));
        top.setBackgroundColor(0x55000000);
        assistantTopBar = top;
        FrameLayout.LayoutParams topParams = new FrameLayout.LayoutParams(-1, dp(54), Gravity.TOP);
        overlay.addView(top, topParams);
        android.widget.TextView title = new android.widget.TextView(this);
        title.setText("RUFILM TV");
        title.setTextColor(android.graphics.Color.WHITE);
        title.setTextSize(16);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        top.addView(title, new android.widget.LinearLayout.LayoutParams(0, -2, 1f));
        android.widget.TextView exitFullscreen = controlText("Выход", 14);
        exitFullscreen.setContentDescription("Выйти из полноэкранного режима");
        top.addView(exitFullscreen, new android.widget.LinearLayout.LayoutParams(dp(76), dp(46)));
        exitFullscreen.setOnClickListener(v -> { releasePlayer(); finish(); });
        android.widget.TextView menu = controlText("⋮", 30);
        top.addView(menu, new android.widget.LinearLayout.LayoutParams(dp(48), dp(46)));
        menu.setOnClickListener(v -> showAssistantMenu());

        assistantControls = new android.widget.LinearLayout(this);
        assistantControls.setOrientation(android.widget.LinearLayout.VERTICAL);
        assistantControls.setPadding(dp(18), dp(8), dp(18), dp(12));
        assistantControls.setBackgroundColor(0x55000000);
        FrameLayout.LayoutParams bottomParams = new FrameLayout.LayoutParams(-1, dp(124), Gravity.BOTTOM);
        overlay.addView(assistantControls, bottomParams);

        android.widget.LinearLayout timelineRow = new android.widget.LinearLayout(this);
        timelineRow.setGravity(Gravity.CENTER_VERTICAL);
        assistantControls.addView(timelineRow, new android.widget.LinearLayout.LayoutParams(-1, dp(34)));
        currentTimeText = controlText("0:00", 11);
        timelineRow.addView(currentTimeText, new android.widget.LinearLayout.LayoutParams(dp(48), -2));
        timelineSeek = new android.widget.SeekBar(this);
        timelineSeek.setMax(1000);
        timelineSeek.setProgressTintList(android.content.res.ColorStateList.valueOf(0xffa78bfa));
        timelineSeek.setThumbTintList(android.content.res.ColorStateList.valueOf(0xffb49aff));
        timelineSeek.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(0x99ffffff));
        timelineSeek.setPadding(dp(4), 0, dp(4), 0);
        timelineSeek.setFocusable(true);
        timelineRow.addView(timelineSeek, new android.widget.LinearLayout.LayoutParams(0, dp(32), 1f));
        durationTimeText = controlText("0:00", 11);
        durationTimeText.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        timelineRow.addView(durationTimeText, new android.widget.LinearLayout.LayoutParams(dp(48), -2));
        timelineSeek.setOnSeekBarChangeListener(new android.widget.SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(android.widget.SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && player != null) {
                    long duration = player.getDuration();
                    if (duration > 0 && duration != C.TIME_UNSET) currentTimeText.setText(formatTime(duration * progress / 1000L));
                }
            }
            @Override public void onStartTrackingTouch(android.widget.SeekBar seekBar) { showAssistantControls(); }
            @Override public void onStopTrackingTouch(android.widget.SeekBar seekBar) {
                if (player != null) {
                    long duration = player.getDuration();
                    if (duration > 0 && duration != C.TIME_UNSET) player.seekTo(duration * seekBar.getProgress() / 1000L);
                }
                scheduleAssistantHide();
            }
        });

        android.widget.FrameLayout controlRow = new android.widget.FrameLayout(this);
        assistantControls.addView(controlRow, new android.widget.LinearLayout.LayoutParams(-1, dp(62)));
        android.widget.LinearLayout transport = new android.widget.LinearLayout(this);
        transport.setGravity(Gravity.CENTER);
        android.widget.FrameLayout.LayoutParams transportParams = new android.widget.FrameLayout.LayoutParams(-2, -1, Gravity.CENTER);
        controlRow.addView(transport, transportParams);
        android.widget.TextView back = controlText("↶10", 17);
        transport.addView(back, new android.widget.LinearLayout.LayoutParams(dp(58), dp(54)));
        back.setOnClickListener(v -> { if (player != null) player.seekTo(Math.max(0L, player.getCurrentPosition()-10000L)); showAssistantControls(); });
        playPauseButton = controlText("Ⅱ", 29);
        transport.addView(playPauseButton, new android.widget.LinearLayout.LayoutParams(dp(68), dp(54)));
        playPauseButton.setOnClickListener(v -> { if (player != null) { if (player.isPlaying()) player.pause(); else player.play(); } showAssistantControls(); });
        android.widget.TextView forward = controlText("10↷", 17);
        transport.addView(forward, new android.widget.LinearLayout.LayoutParams(dp(58), dp(54)));
        forward.setOnClickListener(v -> { if (player != null) player.seekTo(Math.min(player.getDuration(), player.getCurrentPosition()+10000L)); showAssistantControls(); });

        displayButton = controlText("⛶", 23);
        android.widget.FrameLayout.LayoutParams displayParams = new android.widget.FrameLayout.LayoutParams(dp(54), dp(54), Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        controlRow.addView(displayButton, displayParams);
        displayButton.setOnClickListener(v -> {
            if (playerView != null) {
                zoomMode = !zoomMode;
                playerView.setResizeMode(zoomMode
                    ? AspectRatioFrameLayout.RESIZE_MODE_ZOOM : AspectRatioFrameLayout.RESIZE_MODE_FIT);
            }
            showAssistantControls();
        });

        overlay.setOnClickListener(v -> {
            if (!controlsVisible) showAssistantControls();
            else scheduleAssistantHide();
        });
        root.setOnClickListener(v -> {
            if (!controlsVisible) showAssistantControls();
            else scheduleAssistantHide();
        });

        // Episode selection is intentionally left to the source website.
        qualityButton = new Button(this);
        setContentView(root);
        showAssistantControls();

        MediaItem.Builder item = new MediaItem.Builder().setUri(Uri.parse(rawUrl));
        String lower = rawUrl.toLowerCase(Locale.ROOT);
        if (lower.contains(".m3u8")) item.setMimeType(MimeTypes.APPLICATION_M3U8);
        else if (lower.contains(".mpd")) item.setMimeType(MimeTypes.APPLICATION_MPD);
        player.setMediaItem(item.build());
        requestedStartPositionMs = Math.max(0L, getIntent().getLongExtra(EXTRA_START_POSITION_MS, 0L));
        android.util.Log.i("RuFilmTV", "Native handoff requested start position: " + requestedStartPositionMs + " ms");
        player.addListener(new Player.Listener() {
            @Override public void onPlaybackStateChanged(int playbackState) {
                if (playbackState == Player.STATE_READY && !startPositionApplied) {
                    startPositionApplied = true;
                    long duration = player.getDuration();
                    long target = requestedStartPositionMs;
                    if (target > 0L && (duration == C.TIME_UNSET || duration <= 0L || target < duration)) {
                        player.seekTo(target);
                        android.util.Log.i("RuFilmTV", "Native player seek applied: " + target + " ms");
                    }
                    player.play();
                }
            }
            @Override public void onPlayerError(androidx.media3.common.PlaybackException error) {
                String detail = "Ошибка потока, код: " + error.errorCode;
                Throwable cause = error.getCause();
                while (cause != null) {
                    if (cause instanceof androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException) {
                        androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException http =
                            (androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException) cause;
                        detail += " (HTTP " + http.responseCode + ")";
                        android.util.Log.e("RuFilmTV", "Media HTTP " + http.responseCode +
                            " for " + http.dataSpec.uri, error);
                        break;
                    }
                    cause = cause.getCause();
                }
                android.util.Log.e("RuFilmTV", "Media3 playback failed: " + error.getMessage(), error);
                Toast.makeText(NativePlayerActivity.this, detail, Toast.LENGTH_LONG).show();
                // A failed native handoff must never strand the viewer on a black screen.
                // Return to MainActivity, which restores and resumes the original HTML5 player.
                if (!fallbackToOriginalScheduled) {
                    fallbackToOriginalScheduled = true;
                    new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
                        if (!isFinishing()) {
                            android.util.Log.w("RuFilmTV", "Native playback failed; returning to original WebView player");
                            finish();
                        }
                    }, 2200L);
                }
            }
            @Override public void onTracksChanged(androidx.media3.common.Tracks tracks) {
                if (qualityButton != null) qualityButton.setEnabled(hasVideoTracks());
            }
        });
        player.prepare();
        syncHandler.postDelayed(syncRunnable, 1200L);
        assistantHandler.post(updateTimeline);
        scheduleAssistantHide();
    }

    private void syncEpisodeStreamAfterSelection() {
        syncHandler.postDelayed(() -> trySyncEpisodeStream(0), 700L);
    }

    private void trySyncEpisodeStream(int attempt) {
        if (player == null) return;
        try {
            org.json.JSONObject snapshot = new org.json.JSONObject(MainActivity.getCapturedMediaSnapshot());
            long capturedAt = snapshot.optLong("capturedAt", 0L);
            String updated = snapshot.optString("url", "");
            if (capturedAt <= captureBaselineForSelection || updated.isEmpty()) {
                if (attempt < 14) syncHandler.postDelayed(() -> trySyncEpisodeStream(attempt + 1), 500L);
                return;
            }
            if (updated.equals(currentMediaUrl)) return;
            HashMap<String, String> headers = new HashMap<>();
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
        } catch (Exception e) {
            android.util.Log.w("RuFilmTV", "Could not refresh stream after episode selection", e);
        }
    }

    private void switchCapturedStream(String url, String referer, String userAgent, HashMap<String, String> headers) {
        if (player == null || url == null || url.isEmpty()) return;
        if (referer != null && !referer.isEmpty()) headers.put("Referer", referer);
        if (userAgent != null && !userAgent.isEmpty()) headers.put("User-Agent", userAgent);
        try {
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null && !cookie.isEmpty()) headers.put("Cookie", cookie);
        } catch (Exception ignored) { }
        String ua = (userAgent == null || userAgent.isEmpty())
            ? android.webkit.WebSettings.getDefaultUserAgent(this) : userAgent;
        headers.put("User-Agent", ua);
        DefaultHttpDataSource.Factory httpFactory = new DefaultHttpDataSource.Factory()
            .setUserAgent(ua)
            .setAllowCrossProtocolRedirects(true)
            .setConnectTimeoutMs(20000)
            .setReadTimeoutMs(45000)
            .setDefaultRequestProperties(headers);
        DefaultMediaSourceFactory factory = new DefaultMediaSourceFactory(new DefaultDataSource.Factory(this, httpFactory));
        MediaItem.Builder item = new MediaItem.Builder().setUri(Uri.parse(url));
        String lower = url.toLowerCase(Locale.ROOT);
        if (lower.contains(".m3u8")) item.setMimeType(MimeTypes.APPLICATION_M3U8);
        else if (lower.contains(".mpd")) item.setMimeType(MimeTypes.APPLICATION_MPD);
        player.setMediaSource(factory.createMediaSource(item.build()));
        currentMediaUrl = url;
        currentReferer = referer;
        currentUserAgent = ua;
        currentHeaders = new HashMap<>(headers);
        player.prepare();
        player.play();
    }
    private boolean hasVideoTracks() {
        if (trackSelector == null || trackSelector.getCurrentMappedTrackInfo() == null) return false;
        MappingTrackSelector.MappedTrackInfo info = trackSelector.getCurrentMappedTrackInfo();
        for (int r = 0; r < info.getRendererCount(); r++)
            if (info.getRendererType(r) == C.TRACK_TYPE_VIDEO && info.getTrackGroups(r).length > 0) return true;
        return false;
    }

    private void showQualityDialog() {
        if (trackSelector == null || trackSelector.getCurrentMappedTrackInfo() == null) {
            Toast.makeText(this, "Список качества ещё загружается", Toast.LENGTH_SHORT).show();
            return;
        }
        ArrayList<QualityOption> options = new ArrayList<>();
        HashSet<String> seen = new HashSet<>();
        MappingTrackSelector.MappedTrackInfo info = trackSelector.getCurrentMappedTrackInfo();
        for (int r = 0; r < info.getRendererCount(); r++) {
            if (info.getRendererType(r) != C.TRACK_TYPE_VIDEO) continue;
            androidx.media3.exoplayer.source.TrackGroupArray groups = info.getTrackGroups(r);
            for (int g = 0; g < groups.length; g++) {
                TrackGroup group = groups.get(g);
                for (int i = 0; i < group.length; i++) {
                    Format f = group.getFormat(i);
                    if (f.height <= 0) continue;
                    String key = f.height + "";
                    if (seen.add(key)) options.add(new QualityOption(group, i, f.height));
                }
            }
        }
        Collections.sort(options, (a,b) -> Integer.compare(b.height, a.height));
        ArrayList<String> labels = new ArrayList<>();
        labels.add("Авто");
        for (QualityOption option : options) labels.add(option.label());
        new AlertDialog.Builder(this)
            .setTitle("Качество видео")
            .setSingleChoiceItems(labels.toArray(new String[0]), 0, (dialog, which) -> {
                if (which == 0) {
                    trackSelector.setParameters(trackSelector.buildUponParameters()
                        .clearOverridesOfType(C.TRACK_TYPE_VIDEO)
                        .setTrackTypeDisabled(C.TRACK_TYPE_VIDEO, false).build());
                    qualityButton.setText("Качество: Авто ▾");
                } else {
                    QualityOption option = options.get(which - 1);
                    trackSelector.setParameters(trackSelector.buildUponParameters()
                        .setTrackTypeDisabled(C.TRACK_TYPE_VIDEO, false)
                        .setOverrideForType(new TrackSelectionOverride(option.group,
                            Collections.singletonList(option.trackIndex))).build());
                    qualityButton.setText("Качество: " + option.label() + " ▾");
                }
                dialog.dismiss();
            })
            .setNegativeButton("Закрыть", null)
            .show();
    }


    private android.widget.TextView controlText(String value, int size) {
        android.widget.TextView t = new android.widget.TextView(this);
        t.setText(value);
        t.setTextColor(android.graphics.Color.WHITE);
        t.setTextSize(size);
        t.setGravity(Gravity.CENTER);
        t.setFocusable(true);
        t.setBackgroundColor(0x00000000);
        return t;
    }
    private String formatTime(long ms) {
        long total = Math.max(0L, ms / 1000L);
        long h = total / 3600L, m = (total % 3600L) / 60L, sec = total % 60L;
        return h > 0 ? String.format(Locale.ROOT, "%d:%02d:%02d", h, m, sec)
            : String.format(Locale.ROOT, "%d:%02d", m, sec);
    }
    private void showAssistantMenu() {
        String[] items = {"Качество видео", "Скрыть панель"};
        new AlertDialog.Builder(this).setItems(items, (d, which) -> {
            if (which == 0) showQualityDialog();
            else hideAssistantControls();
        }).show();
        showAssistantControls();
    }
    private void showAssistantControls() {
        if (assistantControls == null) return;
        controlsVisible = true;
        assistantControls.setVisibility(View.VISIBLE);
        if (assistantTopBar != null) assistantTopBar.setVisibility(View.VISIBLE);
        scheduleAssistantHide();
    }
    private void hideAssistantControls() {
        if (assistantControls == null) return;
        controlsVisible = false;
        assistantControls.setVisibility(View.GONE);
        if (assistantTopBar != null) assistantTopBar.setVisibility(View.GONE);
    }
    private void scheduleAssistantHide() {
        assistantHandler.removeCallbacks(hideAssistantRunnable);
        assistantHandler.postDelayed(hideAssistantRunnable, 5000L);
    }
    private final Runnable hideAssistantRunnable = () -> {
        if (player != null) hideAssistantControls();
    };

    @Override public void onUserInteraction() {
        super.onUserInteraction();
        if (assistantControls != null && player != null) showAssistantControls();
    }

    @Override public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if (event != null && (event.getAction() == android.view.MotionEvent.ACTION_HOVER_ENTER ||
                event.getAction() == android.view.MotionEvent.ACTION_HOVER_MOVE ||
                event.getAction() == android.view.MotionEvent.ACTION_SCROLL)) {
            if (assistantControls != null && player != null) showAssistantControls();
        }
        return super.dispatchGenericMotionEvent(event);
    }
    private int dp(int value) { return (int)(value * getResources().getDisplayMetrics().density + 0.5f); }

    @Override protected void onStop() { super.onStop(); releasePlayer(); }
    @Override protected void onDestroy() { releasePlayer(); super.onDestroy(); }
    private void releasePlayer() {
        syncHandler.removeCallbacks(syncRunnable);
        assistantHandler.removeCallbacks(updateTimeline);
        assistantHandler.removeCallbacks(hideAssistantRunnable);
        if (player != null) {
            MainActivity.syncOriginalPlayback(player.getCurrentPosition(), false);
            if (playerView != null) playerView.setPlayer(null);
            player.release(); player = null;
        }
    }
    @Override public void onBackPressed() { releasePlayer(); super.onBackPressed(); }
}
