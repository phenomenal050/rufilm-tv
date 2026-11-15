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
capture = '''    // Never let the ad filter intercept actual video manifests or media segments.
    private boolean isRuFilmMediaRequest(String url) {
        if (url == null) return false;
        String path = Uri.parse(url).getPath();
        if (path == null) path = url;
        path = path.toLowerCase(Locale.ROOT);
        String[] extensions = {".m3u8", ".mpd", ".ts", ".m4s", ".mp4", ".m4v", ".aac", ".mp3", ".webm", ".key", ".vtt", ".cmfv", ".cmfa"};
        for (String ext : extensions) if (path.endsWith(ext)) return true;
        return false;
    }

    // Capture HLS/DASH manifests and the request headers used by the WebView.
    private void captureMediaRequest(WebResourceRequest request) {
        if (request == null || request.getUrl() == null ||
                !"GET".equalsIgnoreCase(request.getMethod())) return;
        String url = request.getUrl().toString();
        String lower = url.toLowerCase(Locale.ROOT);
        if (!(lower.contains(".m3u8") || lower.contains(".mpd")) || (isAdRequest(url) && !isRuFilmMediaRequest(url))) return;
        saveOriginalPlayerLayout();
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
        try {
            String cookie = android.webkit.CookieManager.getInstance().getCookie(url);
            if (cookie != null && !cookie.isEmpty()) safeHeaders.put("Cookie", cookie);
        } catch (Exception ignored) { }
        if ((userAgent == null || userAgent.isEmpty()) && web != null) {
            try { userAgent = web.getSettings().getUserAgentString(); } catch (Exception ignored) { }
        }
        synchronized (mediaCaptureLock) {
            capturedMediaUrl = url;
            capturedMediaReferer = (referer == null || referer.isEmpty()) ? BASE + "/" : referer;
            capturedMediaUserAgent = userAgent;
            capturedMediaHeaders = safeHeaders;
            capturedMediaAt = System.currentTimeMillis();
        }
        android.util.Log.i("RuFilmTV", "Captured media manifest: " + Uri.parse(url).getHost());
        // Launch only after the site's fullscreen request; keep episode selection available.
    }

    private boolean launchCapturedMedia() {
        final String url, referer, userAgent;
        final HashMap<String, String> headers;
        synchronized (mediaCaptureLock) {
            long now = System.currentTimeMillis();
            if (!"native".equals(playerMode) || nativePlayerLaunching ||
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
                if (web != null) {
                    final Intent launchIntent = intent;
                    String snapshotScript = "(function(){var docs=[document],frameIds=[-1];try{for(var fi=0;fi<window.frames.length;fi++){try{var d=window.frames[fi].document;if(d){docs.push(d);frameIds.push(fi);}}catch(e){}}}catch(e){}" +
                        "var c=[];docs.forEach(function(d,fi){[].slice.call(d.querySelectorAll('select')).forEach(function(x,i){if(!x.options||x.options.length<2)return;" +
                        "var p=x.parentElement;var meta=[x.name,x.id,x.className,x.getAttribute('aria-label'),x.getAttribute('title'),p?p.innerText:''].join(' ').toLowerCase();" +
                        "var opts=[].map.call(x.options,function(o){return {text:(o.textContent||'').trim(),value:o.value,selected:o.selected};});" +
                        "var words=opts.map(function(o){return o.text;}).join(' ').toLowerCase();" +
                        "c.push({frameIndex:frameIds[fi],index:i,meta:meta,words:words,selectedText:opts[x.selectedIndex]?opts[x.selectedIndex].text:'',options:opts});});});" +
                        "function pick(re){for(var i=0;i<c.length;i++)if(re.test(c[i].meta+' '+c[i].words))return c[i];return null;}" +
                        "var season=pick(/season|сезон/),episode=pick(/episode|серия|эпизод/);" +
                        "if((!season||!episode)&&c.length>=2){season=season||c[0];episode=episode||(c[0]===season?c[1]:c[0]);}" +
                        "var sels=[];if(season)sels.push(season);if(episode&&episode!==season)sels.push(episode);" +
                        "var v=document.querySelector('video');if(!v){for(var j=1;j<docs.length&&!v;j++)try{v=docs[j].querySelector('video');}catch(e){}}" +
                        "return JSON.stringify({selectors:sels,time:v&&isFinite(v.currentTime)?v.currentTime:0});})()";
                    web.evaluateJavascript(snapshotScript, value -> {
                        try {
                            Object decoded = new org.json.JSONTokener(value == null ? "{}" : value).nextValue();
                            org.json.JSONObject snapshot = new org.json.JSONObject(String.valueOf(decoded));
                            org.json.JSONArray selectors = snapshot.optJSONArray("selectors");
                            launchIntent.putExtra(NativePlayerActivity.EXTRA_EPISODE_SELECTORS, selectors == null ? "[]" : selectors.toString());
                            launchIntent.putExtra(NativePlayerActivity.EXTRA_START_POSITION_MS, (long)(snapshot.optDouble("time", 0.0) * 1000.0));
                        } catch (Exception ignored) { }
                        web.evaluateJavascript("(function(){window.__rufilmNativeActive=true;var docs=[document];try{for(var i=0;i<window.frames.length;i++)try{docs.push(window.frames[i].document);}catch(e){}}catch(e){}docs.forEach(function(d){var v=d.querySelector('video');if(!v)return;var w=d.defaultView;if(!w.__rufilmSavedPlayerLayout){var nodes=[],n=v;while(n){nodes.push({el:n,style:n.getAttribute('style'),cls:n.getAttribute('class')});n=n.parentElement;}w.__rufilmSavedPlayerLayout={nodes:nodes,muted:v.muted,volume:v.volume,paused:v.paused};}v.muted=true;v.volume=0;v.style.opacity='0';v.style.pointerEvents='none';try{v.pause();}catch(e){}});return true;})()", null);
                        web.postDelayed(() -> {
                            try { startActivity(launchIntent); }
                            catch (Exception e) {
                                nativePlayerLaunching = false;
        syncOriginalPlayback(0L, false);
                                syncOriginalPlayback(0L, false);
                                android.util.Log.e("RuFilmTV", "Cannot launch native player", e);
                                Toast.makeText(MainActivity.this, "Не удалось открыть встроенный плеер", Toast.LENGTH_LONG).show();
                            }
                        }, 250L);
                    });
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

once('''                if (request != null && isAdRequest(request.getUrl().toString()) && !isRuFilmMediaRequest(request.getUrl().toString()))
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
            "var queued=false;window.__rufilmTvDpadObserver=new MutationObserver(function(){if(queued)return;queued=true;setTimeout(function(){queued=false;mark();},350);});" +
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


# Expose the current activity for the native player's episode and clock callbacks.
bridge_fields = '''
    private static MainActivity rufilmActiveInstance;
    public static void applyEpisodeSelection(int frameIndex, int index, String value) {
        MainActivity a = rufilmActiveInstance;
        if (a == null || a.web == null) return;
        final String quoted = org.json.JSONObject.quote(value == null ? "" : value);
        a.runOnUiThread(() -> a.web.evaluateJavascript("(function(){var d=document;try{if(" + frameIndex + ">=0)d=window.frames[" + frameIndex + "].document;}catch(e){}var s=d.querySelectorAll('select')[" + index + "];if(!s)return false;s.value=" + quoted + ";s.dispatchEvent(new Event('input',{bubbles:true}));s.dispatchEvent(new Event('change',{bubbles:true}));return true;})()", null));
    }
    public static void refreshEpisodeSelectors(android.webkit.ValueCallback<String> callback) {
        MainActivity a = rufilmActiveInstance;
        if (a == null || a.web == null) { if (callback != null) callback.onReceiveValue("[]"); return; }
        final String js = "(function(){var ds=[document],ids=[-1];try{for(var i=0;i<window.frames.length;i++)try{var d=window.frames[i].document;if(d){ds.push(d);ids.push(i);}}catch(e){}}catch(e){}var all=[];ds.forEach(function(d,k){[].slice.call(d.querySelectorAll('select')).forEach(function(x,i){if(!x.options||x.options.length<2)return;var p=x.parentElement;var m=[x.name,x.id,x.className,x.getAttribute('aria-label'),x.getAttribute('title'),p?p.innerText:''].join(' ').toLowerCase();var o=[].map.call(x.options,function(v){return {text:(v.textContent||'').trim(),value:v.value,selected:v.selected};});all.push({frameIndex:ids[k],index:i,meta:m,selectedText:o[x.selectedIndex]?o[x.selectedIndex].text:'',options:o,words:o.map(function(v){return v.text;}).join(' ').toLowerCase()});});});function pick(r){for(var j=0;j<all.length;j++)if(r.test(all[j].meta+' '+all[j].words))return all[j];return null;}var a=pick(/season|сезон/),b=pick(/episode|серия|эпизод/);if(!a&&all.length)a=all[0];if(!b&&all.length>1)b=(a===all[0]?all[1]:all[0]);var z=[];if(a)z.push(a);if(b&&b!==a)z.push(b);return JSON.stringify(z);})()";
        a.runOnUiThread(() -> { if (a.web != null) a.web.evaluateJavascript(js, callback); else if (callback != null) callback.onReceiveValue("[]"); });
    }
    private void saveOriginalPlayerLayout() {
        if (web == null) return;
        final String js = "(function(){var ds=[document];try{for(var i=0;i<window.frames.length;i++)try{ds.push(window.frames[i].document);}catch(e){}}catch(e){}ds.forEach(function(d){try{var v=d.querySelector('video');if(!v)return;var w=d.defaultView;if(w.__rufilmSavedPlayerLayout)return;var nodes=[],x=v;while(x){nodes.push({el:x,style:x.getAttribute('style'),cls:x.getAttribute('class')});if(x===d.documentElement)break;x=x.parentElement;}w.__rufilmSavedPlayerLayout={nodes:nodes,muted:v.muted,volume:v.volume,paused:v.paused,time:v.currentTime};}catch(e){}});return true;})()";
        runOnUiThread(() -> { if (web != null) web.evaluateJavascript(js, null); });
    }
    public static String getCapturedMediaUrl() {
        MainActivity a = rufilmActiveInstance;
        if (a == null) return null;
        synchronized (a.mediaCaptureLock) { return a.capturedMediaUrl; }
    }
    public static void syncOriginalPlayback(long positionMs, boolean nativeActive) {
        MainActivity a = rufilmActiveInstance;
        if (a == null || a.web == null) return;
        a.runOnUiThread(() -> {
            String js = "(function(){var docs=[document];try{for(var i=0;i<window.frames.length;i++)try{docs.push(window.frames[i].document);}catch(e){}}catch(e){}var t=" + (Math.max(0L,positionMs)/1000.0) + ";docs.forEach(function(d){var v=d.querySelector('video');if(!v)return;var w=d.defaultView;if(isFinite(t)&&Math.abs(v.currentTime-t)>1.5){try{v.currentTime=t;}catch(e){}}if(" + nativeActive + "){v.muted=true;v.volume=0;v.style.opacity='0';v.style.pointerEvents='none';}else if(w.__rufilmSavedPlayerLayout){var z=w.__rufilmSavedPlayerLayout;z.nodes.forEach(function(x){if(x.style===null)x.el.removeAttribute('style');else x.el.setAttribute('style',x.style);if(x.cls===null)x.el.removeAttribute('class');else x.el.setAttribute('class',x.cls);});v.muted=z.muted;v.volume=z.volume;w.__rufilmSavedPlayerLayout=null;if(!z.paused){try{var playPromise=v.play();if(playPromise&&playPromise.catch)playPromise.catch(function(){});}catch(e){}}}});return true;})()";
            a.web.evaluateJavascript(js, null);
        });
    }
'''
once('    private final Object mediaCaptureLock = new Object();', bridge_fields + '    private final Object mediaCaptureLock = new Object();', 'native callbacks')
if 'rufilmActiveInstance = this;' not in s:
    on_create = re.search(r'((?:public|protected|private)\s+void\s+onCreate\s*\([^)]*\)\s*\{)', s)
    if not on_create:
        raise SystemExit('Could not find onCreate for activity reference')
    s = s[:on_create.end()] + '\n        rufilmActiveInstance = this;' + s[on_create.end():]

# Release the launch guard when returning from NativePlayerActivity.
# MainActivity receives onResume after the native player is closed.
resume = re.search(r'((?:public|protected)\s+void\s+onResume\s*\(\s*\)\s*\{)', s)
if resume:
    body_end = resume.end()
    if 'nativePlayerLaunching = false;' not in s[body_end:body_end + 220]:
        s = s[:body_end] + '\n        nativePlayerLaunching = false;' + s[body_end:]
else:
    class_end = s.rfind('}')
    if class_end < 0:
        raise SystemExit('Could not find MainActivity class end for onResume')
    s = s[:class_end] + '''
    @Override protected void onResume() {
        super.onResume();
        nativePlayerLaunching = false;
    }

''' + s[class_end:]

# Persist all edits, including the native-player bridge appended above.
p.write_text(s, encoding="utf-8")
print("Patched", p)
