#!/usr/bin/env python3
import pathlib, re, sys
p=pathlib.Path(sys.argv[1])
s=p.read_text(encoding="utf-8")

def once(old, new, label):
    global s
    if new in s: return
    if old not in s: raise SystemExit("patch anchor not found: "+label)
    s=s.replace(old,new,1)

once("import java.util.Locale;", "import java.util.Locale;\nimport java.util.Map;", "Map import")
once('    private boolean externalLaunchPending = false;', '''    private boolean externalLaunchPending = false;
    private final Object mediaCaptureLock = new Object();
    private String capturedMediaUrl = null;
    private String capturedMediaReferer = null;
    private String capturedMediaUserAgent = null;
    private long capturedMediaAt = 0L;
    private long lastNativePlayerLaunchAt = 0L;''', "media fields")

anchor = "    // ABP-style network filtering; the cinema origin and ordinary media requests are exempt."
capture = '''    // WebView calls shouldInterceptRequest off the UI thread. Capture only media manifests;
    // launch is deferred until the HTML video reports a user playback attempt.
    private void captureMediaRequest(WebResourceRequest request) {
        if (request == null || request.getUrl() == null ||
                !"GET".equalsIgnoreCase(request.getMethod())) return;
        String url = request.getUrl().toString();
        String lower = url.toLowerCase(Locale.ROOT);
        if (!(lower.contains(".m3u8") || lower.contains(".mpd")) || isAdRequest(url)) return;
        Map<String, String> headers = request.getRequestHeaders();
        String referer = null, userAgent = null;
        if (headers != null) {
            for (Map.Entry<String, String> entry : headers.entrySet()) {
                if ("referer".equalsIgnoreCase(entry.getKey())) referer = entry.getValue();
                if ("user-agent".equalsIgnoreCase(entry.getKey())) userAgent = entry.getValue();
            }
        }
        synchronized (mediaCaptureLock) {
            capturedMediaUrl = url;
            capturedMediaReferer = (referer == null || referer.isEmpty()) ? BASE + "/" : referer;
            capturedMediaUserAgent = userAgent;
            capturedMediaAt = System.currentTimeMillis();
        }
        android.util.Log.i("RuFilmTV", "Captured media manifest: " + Uri.parse(url).getHost());
        // HLS/DASH requests are issued when playback starts, including from cross-origin iframes.
        launchCapturedMedia();
    }

    private boolean launchCapturedMedia() {
        final String url, referer, userAgent;
        synchronized (mediaCaptureLock) {
            if (!"native".equals(playerMode) || System.currentTimeMillis() - lastNativePlayerLaunchAt < 10000L ||
                    capturedMediaUrl == null || System.currentTimeMillis() - capturedMediaAt > 90000L)
                return false;
            url = capturedMediaUrl;
            referer = capturedMediaReferer;
            userAgent = capturedMediaUserAgent;
            lastNativePlayerLaunchAt = System.currentTimeMillis();
        }
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(MainActivity.this, NativePlayerActivity.class);
                intent.putExtra(NativePlayerActivity.EXTRA_URL, url);
                intent.putExtra(NativePlayerActivity.EXTRA_REFERER, referer);
                intent.putExtra(NativePlayerActivity.EXTRA_USER_AGENT, userAgent);
                startActivity(intent);
            } catch (Exception e) {
                android.util.Log.e("RuFilmTV", "Cannot launch native player", e);
                Toast.makeText(MainActivity.this, "Не удалось открыть встроенный плеер", Toast.LENGTH_LONG).show();
            }
        });
        return true;
    }

'''
once(anchor, capture+anchor, "capture methods")

once('''                if (request != null && isAdRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();''', '''                captureMediaRequest(request);
                if (request != null && isAdRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();''', "request interception")

# JS bridge fallback for blob:/MSE sources: use the last observed HLS/DASH manifest.
once('''          + "if(!/^https?:\\\\/\\\\//i.test(u))return false;"''', '''          + "if(!/^https?:\\\\/\\\\//i.test(u)){try{if(window.RuFilmPlayer.openCaptured()){v.pause();return true;}}catch(e){}return false;}"''', "blob fallback")
once('''          + "var ok=window.RuFilmPlayer&&window.RuFilmPlayer.openNative(String(u),String(location.href),String(navigator.userAgent));"''', '''          + "var ok=window.RuFilmPlayer&&window.RuFilmPlayer.openNative(String(u),String(location.href),String(navigator.userAgent));"
          + "if(!ok){try{ok=window.RuFilmPlayer&&window.RuFilmPlayer.openCaptured();}catch(e){}}"''', "direct fallback")

once('''        @JavascriptInterface public boolean isNativeEnabled() { return "native".equals(playerMode); }''', '''        @JavascriptInterface public boolean isNativeEnabled() { return "native".equals(playerMode); }
        @JavascriptInterface public boolean openCaptured() { return launchCapturedMedia(); }''', "bridge method")

p.write_text(s,encoding="utf-8")
print("Patched",p)
