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
    private PlayerView playerView;
    private DefaultTrackSelector trackSelector;
    private Button qualityButton;
    private Button seasonButton;
    private Button episodeButton;
    private org.json.JSONArray episodeSelectors = new org.json.JSONArray();
    private String currentMediaUrl;
    private final android.os.Handler syncHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable syncRunnable = new Runnable() { public void run() { if (player != null) { MainActivity.syncOriginalPlayback(player.getCurrentPosition(), true); syncHandler.postDelayed(this, 1200L); } } };

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
            try {
                Uri page = Uri.parse(referer);
                if (page.getScheme() != null && page.getHost() != null)
                    headers.put("Origin", page.getScheme() + "://" + page.getHost());
            } catch (Exception ignored) { }
        }
        try {
            String cookie = CookieManager.getInstance().getCookie(rawUrl);
            if ((headers.get("Cookie") == null || headers.get("Cookie").isEmpty()) && cookie != null && !cookie.isEmpty())
                headers.put("Cookie", cookie);
        } catch (Exception ignored) { }

        String effectiveUa = userAgent == null || userAgent.isEmpty()
            ? "Mozilla/5.0 (Linux; Android 10; Android TV) AppleWebKit/537.36 Chrome/83.0.4103.120 Safari/537.36"
            : userAgent;
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

        android.widget.LinearLayout selectorBar = new android.widget.LinearLayout(this);
        selectorBar.setOrientation(android.widget.LinearLayout.HORIZONTAL);
        selectorBar.setGravity(Gravity.END);
        FrameLayout.LayoutParams barParams = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.TOP | Gravity.END);
        int margin = dp(18);
        barParams.setMargins(margin, margin, margin, margin);
        root.addView(selectorBar, barParams);
        seasonButton = new Button(this);
        seasonButton.setText("Сезон ▾");
        seasonButton.setFocusable(true);
        seasonButton.setOnClickListener(v -> showEpisodeSelector(0));
        selectorBar.addView(seasonButton);
        episodeButton = new Button(this);
        episodeButton.setText("Серия ▾");
        episodeButton.setFocusable(true);
        episodeButton.setOnClickListener(v -> showEpisodeSelector(1));
        selectorBar.addView(episodeButton);
        qualityButton = new Button(this);
        qualityButton.setText("Качество ▾");
        qualityButton.setFocusable(true);
        qualityButton.setOnClickListener(v -> showQualityDialog());
        selectorBar.addView(qualityButton);
        try {
            String selectors = getIntent().getStringExtra(EXTRA_EPISODE_SELECTORS);
            if (selectors != null) episodeSelectors = new org.json.JSONArray(selectors);
        } catch (Exception ignored) { }
        updateEpisodeButtonLabels();
        setContentView(root);

        MediaItem.Builder item = new MediaItem.Builder().setUri(Uri.parse(rawUrl));
        String lower = rawUrl.toLowerCase(Locale.ROOT);
        if (lower.contains(".m3u8")) item.setMimeType(MimeTypes.APPLICATION_M3U8);
        else if (lower.contains(".mpd")) item.setMimeType(MimeTypes.APPLICATION_MPD);
        player.setMediaItem(item.build());
        long startPosition = getIntent().getLongExtra(EXTRA_START_POSITION_MS, 0L);
        if (startPosition > 0L) player.seekTo(startPosition);
        player.addListener(new Player.Listener() {
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
            }
            @Override public void onTracksChanged(androidx.media3.common.Tracks tracks) {
                if (qualityButton != null) qualityButton.setEnabled(hasVideoTracks());
            }
        });
        player.prepare();
        player.play();
        syncHandler.postDelayed(syncRunnable, 1200L);
    }

    private void updateEpisodeButtonLabels() {
        try {
            if (episodeSelectors.length() < 2) { seasonButton.setText("Сезон ▾"); episodeButton.setText("Серия ▾"); seasonButton.setEnabled(true); episodeButton.setEnabled(true); return; }
            org.json.JSONObject season = episodeSelectors.getJSONObject(0);
            org.json.JSONObject episode = episodeSelectors.getJSONObject(1);
            seasonButton.setText("Сезон: " + season.optString("selectedText", "—") + " ▾");
            episodeButton.setText("Серия: " + episode.optString("selectedText", "—") + " ▾");
            seasonButton.setEnabled(season.optJSONArray("options") != null && season.optJSONArray("options").length() > 0);
            episodeButton.setEnabled(episode.optJSONArray("options") != null && episode.optJSONArray("options").length() > 0);
        } catch (Exception ignored) { }
    }
    private void showEpisodeSelector(int which) {
        if (episodeSelectors.length() <= which || episodeSelectors.optJSONObject(which) == null ||
                episodeSelectors.optJSONObject(which).optJSONArray("options") == null ||
                episodeSelectors.optJSONObject(which).optJSONArray("options").length() == 0) {
            MainActivity.refreshEpisodeSelectors(raw -> runOnUiThread(() -> {
                try {
                    Object decoded = new org.json.JSONTokener(raw == null ? "\"[]\"" : raw).nextValue();
                    String json = decoded instanceof String ? (String)decoded : String.valueOf(decoded);
                    episodeSelectors = new org.json.JSONArray(json);
                    updateEpisodeButtonLabels();
                    showEpisodeSelectorNow(which);
                } catch (Exception e) {
                    Toast.makeText(this, "Сайт пока не предоставил список сезонов/серий", Toast.LENGTH_SHORT).show();
                }
            }));
            return;
        }
        showEpisodeSelectorNow(which);
    }

    private void showEpisodeSelectorNow(int which) {
        try {
            if (episodeSelectors.length() <= which) {
                Toast.makeText(this, "На этой странице нет списка " + (which == 0 ? "сезонов" : "серий"), Toast.LENGTH_SHORT).show();
                return;
            }
            org.json.JSONObject selector = episodeSelectors.getJSONObject(which);
            org.json.JSONArray options = selector.optJSONArray("options");
            if (options == null || options.length() == 0) return;
            String[] labels = new String[options.length()];
            int selected = 0;
            for (int i = 0; i < options.length(); i++) {
                org.json.JSONObject option = options.getJSONObject(i);
                labels[i] = option.optString("text", option.optString("value", ""));
                if (option.optBoolean("selected", false)) selected = i;
            }
            final int selectIndex = selector.optInt("index", which);
            final int frameIndex = selector.optInt("frameIndex", -1);
            new AlertDialog.Builder(this).setTitle(which == 0 ? "Выбор сезона" : "Выбор серии")
                .setSingleChoiceItems(labels, selected, (dialog, choice) -> {
                    try {
                        String value = options.getJSONObject(choice).optString("value", "");
                        MainActivity.applyEpisodeSelection(frameIndex, selectIndex, value);
                        selector.put("selectedText", labels[choice]);
                        for (int i = 0; i < options.length(); i++) options.getJSONObject(i).put("selected", i == choice);
                        updateEpisodeButtonLabels();
                        syncEpisodeStreamAfterSelection();
                    } catch (Exception ignored) { }
                    dialog.dismiss();
                }).setNegativeButton("Закрыть", null).show();
        } catch (Exception e) { Toast.makeText(this, "Не удалось открыть список", Toast.LENGTH_SHORT).show(); }
    }
    private void syncEpisodeStreamAfterSelection() {
        syncHandler.postDelayed(() -> {
            if (player == null) return;
            String updated = MainActivity.getCapturedMediaUrl();
            if (updated != null && !updated.equals(currentMediaUrl)) {
                currentMediaUrl = updated;
                MediaItem.Builder item = new MediaItem.Builder().setUri(Uri.parse(updated));
                String lower = updated.toLowerCase(Locale.ROOT);
                if (lower.contains(".m3u8")) item.setMimeType(MimeTypes.APPLICATION_M3U8);
                else if (lower.contains(".mpd")) item.setMimeType(MimeTypes.APPLICATION_MPD);
                player.setMediaItem(item.build());
                player.prepare();
                player.play();
            }
        }, 2200L);
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

    private int dp(int value) { return (int)(value * getResources().getDisplayMetrics().density + 0.5f); }

    @Override protected void onStop() { super.onStop(); releasePlayer(); }
    @Override protected void onDestroy() { releasePlayer(); super.onDestroy(); }
    private void releasePlayer() {
        syncHandler.removeCallbacks(syncRunnable);
        if (player != null) {
            MainActivity.syncOriginalPlayback(player.getCurrentPosition(), false);
            if (playerView != null) playerView.setPlayer(null);
            player.release(); player = null;
        }
    }
    @Override public void onBackPressed() { releasePlayer(); super.onBackPressed(); }
}
