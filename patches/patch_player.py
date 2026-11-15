#!/usr/bin/env python3
import pathlib, sys
p=pathlib.Path(sys.argv[1])
s=p.read_text(encoding="utf-8")

def once(old, new, label):
    global s
    if new in s: return
    if old not in s:
        print("Skipping unmatched optional patch anchor:", label)
        return
    s=s.replace(old,new,1)

once("import java.util.Locale;", "import java.util.Locale;\nimport java.util.Map;\nimport java.util.HashMap;", "Map imports")
once('    private boolean externalLaunchPending = false;', '''    private boolean externalLaunchPending = false;
    private final Object mediaCaptureLock = new Object();
    private String capturedMediaUrl = null;
    private String capturedMediaReferer = null;
    private String capturedMediaUserAgent = null;
    private Map<String, String> capturedMediaHeaders = new HashMap<>();
    private long capturedMediaAt = 0L;
    private long lastNativePlayerLaunchAt = 0L;
    private boolean nativePlayerLaunching = false;''', "media fields")

anchor = "    // ABP-style network filtering; the cinema origin and ordinary media requests are exempt."
capture = '''    // Capture HLS/DASH manifests and the request headers used by the WebView.
    private void captureMediaRequest(WebResourceRequest request) {
        if (request == null || request.getUrl() == null ||
                !"GET".equalsIgnoreCase(request.getMethod())) return;
        String url = request.getUrl().toString();
        String lower = url.toLowerCase(Locale.ROOT);
        if (!(lower.contains(".m3u8") || lower.contains(".mpd")) || isAdRequest(url)) return;
        Map<String, String> headers = request.getRequestHeaders();
        Map<String, String> safeHeaders = new HashMap<>();
        String referer = null, userAgent = null;
        if (headers != null) {
            for (Map.Entry<String, String> entry : headers.entrySet()) {
                String key = entry.getKey();
                if (key == null) continue;
                String k = key.toLowerCase(Locale.ROOT);
                if (k.equals("user-agent") || k.equals("referer") || k.equals("origin") ||
                    k.equals("cookie") || k.equals("authorization") || k.equals("accept") ||
                    k.equals("accept-language") || k.startsWith("x-")) {
                    safeHeaders.put(key, entry.getValue());
                }
                if ("referer".equals(k)) referer = entry.getValue();
                if ("user-agent".equals(k)) userAgent = entry.getValue();
            }
        }
        synchronized (mediaCaptureLock) {
            capturedMediaUrl = url;
            capturedMediaReferer = (referer == null || referer.isEmpty()) ? BASE + "/" : referer;
            capturedMediaUserAgent = userAgent;
            capturedMediaHeaders = safeHeaders;
            capturedMediaAt = System.currentTimeMillis();
        }
        android.util.Log.i("RuFilmTV", "Captured media manifest: " + Uri.parse(url).getHost());
        launchCapturedMedia();
    }

    private boolean launchCapturedMedia() {
        final String url, referer, userAgent;
        final HashMap<String, String> headers;
        synchronized (mediaCaptureLock) {
            long now = System.currentTimeMillis();
            if (!"native".equals(playerMode) || nativePlayerLaunching ||
                    now - lastNativePlayerLaunchAt < 10000L ||
                    capturedMediaUrl == null || now - capturedMediaAt > 90000L) return false;
            url = capturedMediaUrl;
            referer = capturedMediaReferer;
            userAgent = capturedMediaUserAgent;
            headers = new HashMap<>(capturedMediaHeaders);
            nativePlayerLaunching = true;
            lastNativePlayerLaunchAt = now;
        }
        runOnUiThread(() -> {
            try {
                Intent intent = new Intent(MainActivity.this, NativePlayerActivity.class);
                intent.putExtra(NativePlayerActivity.EXTRA_URL, url);
                intent.putExtra(NativePlayerActivity.EXTRA_REFERER, referer);
                intent.putExtra(NativePlayerActivity.EXTRA_USER_AGENT, userAgent);
                intent.putExtra(NativePlayerActivity.EXTRA_HEADERS, headers);
                // Stop WebView playback before the native surface becomes visible.
                if (web != null) {
                    web.evaluateJavascript("(function(){function stop(d){try{d.querySelectorAll('video,audio').forEach(function(v){try{v.pause();}catch(e){}});d.querySelectorAll('iframe').forEach(function(f){try{if(f.contentDocument)stop(f.contentDocument);}catch(e){}});}catch(e){}}stop(document);return true;})()", null);
                    web.onPause();
                    web.postDelayed(() -> {
                        try { startActivity(intent); }
                        catch (Exception e) {
                            nativePlayerLaunching = false;
                            web.onResume();
                            android.util.Log.e("RuFilmTV", "Cannot launch native player", e);
                            Toast.makeText(MainActivity.this, "Не удалось открыть встроенный плеер", Toast.LENGTH_LONG).show();
                        }
                    }, 350L);
                } else startActivity(intent);
            } catch (Exception e) {
                nativePlayerLaunching = false;
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

once('''          + "if(!/^https?:\\/\\//i.test(u))return false;"''', '''          + "if(!/^https?:\\/\\//i.test(u)){try{if(window.RuFilmPlayer.openCaptured()){v.pause();return true;}}catch(e){}return false;}"''', "blob fallback")
once('''          + "var ok=window.RuFilmPlayer&&window.RuFilmPlayer.openNative(String(u),String(location.href),String(navigator.userAgent));"''', '''          + "var ok=window.RuFilmPlayer&&window.RuFilmPlayer.openNative(String(u),String(location.href),String(navigator.userAgent));"
          + "if(!ok){try{ok=window.RuFilmPlayer&&window.RuFilmPlayer.openCaptured();}catch(e){}}"''', "direct fallback")

once('''        @JavascriptInterface public boolean isNativeEnabled() { return "native".equals(playerMode); }''', '''        @JavascriptInterface public boolean isNativeEnabled() { return "native".equals(playerMode); }
        @JavascriptInterface public boolean openCaptured() { return launchCapturedMedia(); }''', "bridge method")


# Keep the site's season/episode selectors usable. Do not launch on manifest discovery.
import re
capture_start = s.find("private void captureMediaRequest")
capture_end = s.find("private boolean launchCapturedMedia", capture_start)
if capture_start >= 0 and capture_end > capture_start:
    capture_block = s[capture_start:capture_end]
    capture_block = capture_block.replace("        launchCapturedMedia();", "        // Wait for the site's fullscreen request after the user selects an episode.")
    s = s[:capture_start] + capture_block + s[capture_end:]

# Intercept the existing WebChromeClient fullscreen callback. The project already
# defines onShowCustomView, so patch that method instead of adding a duplicate.
show_pos = s.find("onShowCustomView(")
if show_pos < 0:
    raise SystemExit("WebChromeClient fullscreen callback not found.")
if "launchCapturedMedia()" not in s[show_pos:show_pos + 1800]:
    method = re.search(
        r'(public\s+void\s+onShowCustomView\s*\(([^)]*CustomViewCallback\s+(\w+)[^)]*)\)\s*\{)',
        s
    )
    if not method:
        raise SystemExit("Could not safely identify the fullscreen callback parameter.")
    callback_name = method.group(3)
    injected = method.group(1) + """
                if (launchCapturedMedia()) {
                    try { CALLBACK.onCustomViewHidden(); } catch (Exception ignored) {}
                    return;
                }
""".replace("CALLBACK", callback_name)
    s = s[:method.start()] + injected + s[method.end():]


# Make the site's existing season/episode <select> controls reachable by Android TV DPAD.
# Keep the site's own change handlers: choosing an option still triggers the site normally.
episode_support = r'''
    private void installEpisodeSelectorSupport() {
        if (web == null) return;
        final String script = "(function(){try{" +
            "var styleId='rufilm-tv-dpad-select-style';" +
            "if(!document.getElementById(styleId)){var st=document.createElement('style');st.id=styleId;" +
            "st.textContent='select:focus{outline:3px solid #00dce8!important;outline-offset:2px!important;}' +" +
            "select{min-height:40px;}';document.head.appendChild(st);}" +
            "function mark(){var list=document.querySelectorAll('select');" +
            "for(var i=0;i<list.length;i++){var el=list[i];if(!el||!el.options||!el.options.length)continue;" +
            "el.setAttribute('tabindex','0');" +
            "var t='';for(var j=0;j<el.options.length;j++)t+=' '+(el.options[j].textContent||'');" +
            "if(/сезон|season/i.test(t))el.setAttribute('aria-label','Выбор сезона');" +
            "else if(/серия|эпизод|episode/i.test(t))el.setAttribute('aria-label','Выбор серии');" +
            "el.style.minHeight='40px';el.style.fontSize='16px';}}" +
            "mark();if(!window.__rufilmTvDpadObserver&&document.documentElement){" +
            "window.__rufilmTvDpadObserver=new MutationObserver(function(){mark();});" +
            "window.__rufilmTvDpadObserver.observe(document.documentElement,{childList:true,subtree:true});}" +
            "}catch(e){}})();";
        web.evaluateJavascript(script, null);
    }

'''
if "installEpisodeSelectorSupport()" not in s:
    anchor = "    // Capture HLS/DASH manifests and the request headers used by the WebView."
    if anchor not in s:
        raise SystemExit("Could not find insertion point for episode selector support.")
    s = s.replace(anchor, episode_support + anchor, 1)

if "MainActivity.this.installEpisodeSelectorSupport();" not in s:
    page_finished = re.search(
        r'(public\s+void\s+onPageFinished\s*\([^)]*\)\s*\{)',
        s
    )
    if not page_finished:
        raise SystemExit("Could not find WebViewClient.onPageFinished for DPAD selector setup.")
    insert = page_finished.group(1) + "\n                MainActivity.this.installEpisodeSelectorSupport();"
    s = s[:page_finished.start()] + insert + s[page_finished.end():]

p.write_text(s,encoding="utf-8")
print("Patched",p)
