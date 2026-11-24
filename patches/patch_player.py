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
    private volatile long mxPlayIntentUntil = 0L;
    private volatile boolean mxOfferTriggered = false;
    private final Object mediaCaptureLock = new Object();
    private String capturedMediaUrl = null;
    private String capturedMediaReferer = null;
    private String capturedMediaUserAgent = null;
    private Map<String, String> capturedMediaHeaders = new HashMap<>();
    private long capturedMediaAt = 0L;
    private int capturedMediaPriority = 0; // HLS/DASH manifests outrank individual MP4 fragments.
    private long lastNativePlayerLaunchAt = 0L;
    private boolean nativePlayerLaunching = false;''', "media fields")

anchor = "    // ABP-style network filtering; the cinema origin and ordinary media requests are exempt."
capture = '''    // Never let the ad filter intercept actual video manifests or media segments.
    private boolean isRuFilmMediaRequest(String url) {
        if (url == null) return false;
        Uri parsed = Uri.parse(url);
        String path = parsed.getPath();
        if (path == null) path = url;
        path = path.toLowerCase(Locale.ROOT);
        String host = parsed.getHost();
        if (host == null) return false;
        String h = host.toLowerCase(Locale.ROOT);
        // VK/OK player bootstrap, API and media must never be mistaken for ad requests.
        boolean vkHost = h.equals("vk.com") || h.endsWith(".vk.com") ||
            h.equals("vk.ru") || h.endsWith(".vk.ru") ||
            h.equals("vkvideo.ru") || h.endsWith(".vkvideo.ru") ||
            h.equals("ok.ru") || h.endsWith(".ok.ru") ||
            h.equals("cdn-vk.ru") || h.endsWith(".cdn-vk.ru") ||
            h.equals("userapi.com") || h.endsWith(".userapi.com") ||
            h.equals("mycdn.me") || h.endsWith(".mycdn.me") ||
            h.equals("vkuser.net") || h.endsWith(".vkuser.net") ||
            h.equals("vk-cdn.net") || h.endsWith(".vk-cdn.net") ||
            h.equals("vkuseraudio.net") || h.endsWith(".vkuseraudio.net");
        if (vkHost) return true; // Preserve all first-party player bootstrap/API assets on VK/OK hosts.
        if (h.equals("st.okcdn.ru") || h.endsWith(".st.okcdn.ru") ||
                h.endsWith(".vkuser.net") || h.endsWith(".okcdn.ru") ||
                h.endsWith(".vk-cdn.net") || h.endsWith(".vkuseraudio.net")) return true;
        if (h.equals("st.okcdn.ru") || h.endsWith(".st.okcdn.ru") || h.endsWith(".vkuser.net") || h.endsWith(".okcdn.ru")) {
            String[] mediaExtensions = {".m3u8", ".mpd", ".ts", ".m4s", ".mp4", ".m4v", ".aac", ".mp3", ".webm", ".key", ".vtt", ".cmfv", ".cmfa"};
            for (String ext : mediaExtensions) if (path.endsWith(ext)) return true;
        }
        String[] extensions = {".m3u8", ".mpd", ".ts", ".m4s", ".mp4", ".m4v", ".aac", ".mp3", ".webm", ".key", ".vtt", ".cmfv", ".cmfa"};
        for (String ext : extensions) if (path.endsWith(ext)) return true;
        return false;
    }

    private boolean isKnownAdRequest(String url) {
        if (url == null || isRuFilmMediaRequest(url)) return false;
        Uri u = Uri.parse(url);
        String h = u.getHost();
        if (h == null) return false;
        h = h.toLowerCase(Locale.ROOT);
        String path = u.getPath() == null ? "" : u.getPath().toLowerCase(Locale.ROOT);
        return h.equals("digitalcaramel.com") || h.endsWith(".digitalcaramel.com") ||
            h.equals("vak345.com") || h.endsWith(".vak345.com") ||
            h.equals("qepolax.com") || h.endsWith(".qepolax.com") ||
            (h.equals("yandex.ru") && path.equals("/ads/system/context.js"));
    }

    // Recover a user's first Play tap if VK attaches the stream asynchronously.
    private void installVkFirstTapSupport() {
        if (web == null) return;
        final String script = "(function(){try{var docs=[document];try{for(var i=0;i<window.frames.length;i++)try{docs.push(window.frames[i].document);}catch(e){}}catch(e){}" +
            "function bind(d){if(!d||d.__rufilmFirstTapInstalled)return;d.__rufilmFirstTapInstalled=true;" +
            "function arm(v){if(!v||v.__rufilmFirstTapBound)return;v.__rufilmFirstTapBound=true;" +
            "function start(){if(!v.__rufilmPlayIntentUntil||Date.now()>v.__rufilmPlayIntentUntil||!v.paused||v.readyState<2||!v.currentSrc)return;try{var p=v.play();if(p&&p.catch)p.catch(function(){});}catch(e){}}" +
            "['loadeddata','canplay','canplaythrough','loadedmetadata'].forEach(function(n){v.addEventListener(n,start);});" +
            "d.addEventListener('click',function(e){var t=e.target,hit=t===v||v.contains(t);if(!hit){var el=t&&t.closest?t.closest('button,[role=button],[class*=play],[aria-label*=play i],[title*=play i]'):null;" +
            "if(el){var root=v;for(var k=0;k<7&&root;k++,root=root.parentElement){if(root.contains(el)){hit=true;break;}}}}" +
            "if(!hit)return;v.__rufilmPlayIntentUntil=Date.now()+8000;[80,300,700,1300,2200].forEach(function(ms){setTimeout(start,ms);});},true);}" +
            "function scan(){[].slice.call(d.querySelectorAll('video')).forEach(arm);}" +
            "scan();if(d.documentElement&&!d.__rufilmFirstTapObserver){var ob=new MutationObserver(scan);ob.observe(d.documentElement,{childList:true,subtree:true});d.__rufilmFirstTapObserver=ob;}}" +
            "docs.forEach(bind);return true;}catch(e){return false;}})();";
        web.evaluateJavascript(script, null);
    }

    private void installAdCosmeticFilters() {
        if (web == null) return;
        final String js = "(function(){try{var id='rufilm-ad-cosmetic-style';var css=" +
            "'html.rf-adfilter-enabled .adsbygoogle,html.rf-adfilter-enabled [id^=div-gpt-ad],html.rf-adfilter-enabled iframe[src*=kaspi],html.rf-adfilter-enabled iframe[src*=digitalcaramel],html.rf-adfilter-enabled iframe[src*=yandex],html.rf-adfilter-enabled iframe[src*=vak345],html.rf-adfilter-enabled iframe[src*=qepolax],html.rf-adfilter-enabled iframe[src*=doubleclick],html.rf-adfilter-enabled iframe[src*=adservice],html.rf-adfilter-enabled iframe[src*=adnxs],html.rf-adfilter-enabled iframe[src*=googlesyndication],html.rf-adfilter-enabled a[href*=kaspi],html.rf-adfilter-enabled img[src*=kaspi],html.rf-adfilter-enabled [data-href*=kaspi]{display:none!important;visibility:hidden!important;pointer-events:none!important;width:0!important;height:0!important;min-width:0!important;min-height:0!important;max-width:0!important;max-height:0!important}'" +
            ";var st=document.getElementById(id);if(!st){st=document.createElement('style');st.id=id;(document.head||document.documentElement).appendChild(st);}st.textContent=css;" +
            "function playerNode(e){if(!e)return false;try{if(e.matches&&e.matches('video,iframe[src*=vk],iframe[src*=\\\"ok.ru\\\"]'))return true;return !!e.querySelector('video,iframe[src*=vk],iframe[src*=\\\"ok.ru\\\"]');}catch(x){return false;}}" +
            "function restore(){document.querySelectorAll('[data-rufilm-ad-hidden=\\\"1\\\"]').forEach(function(e){var d=e.getAttribute('data-rufilm-old-display')||'',dp=e.getAttribute('data-rufilm-old-display-priority')||'',p=e.getAttribute('data-rufilm-old-pointer')||'',pp=e.getAttribute('data-rufilm-old-pointer-priority')||'';if(d)e.style.setProperty('display',d,dp);else e.style.removeProperty('display');if(p)e.style.setProperty('pointer-events',p,pp);else e.style.removeProperty('pointer-events');['data-rufilm-ad-hidden','data-rufilm-old-display','data-rufilm-old-display-priority','data-rufilm-old-pointer','data-rufilm-old-pointer-priority'].forEach(function(a){e.removeAttribute(a);});});}" +
            "function hideOne(e){if(playerNode(e))return;if(!e.hasAttribute('data-rufilm-ad-hidden')){e.setAttribute('data-rufilm-ad-hidden','1');e.setAttribute('data-rufilm-old-display',e.style.getPropertyValue('display'));e.setAttribute('data-rufilm-old-display-priority',e.style.getPropertyPriority('display'));e.setAttribute('data-rufilm-old-pointer',e.style.getPropertyValue('pointer-events'));e.setAttribute('data-rufilm-old-pointer-priority',e.style.getPropertyPriority('pointer-events'));}e.style.setProperty('display','none','important');e.style.setProperty('pointer-events','none','important');}" +
            "function hide(){if(!document.documentElement.classList.contains('rf-adfilter-enabled')){restore();return;}var q='[class*=advert],[id*=advert],[class*=ad-container],[id*=ad-container],[class*=ad-slot],[id*=ad-slot],[class*=banner-ad],[id*=banner-ad],[class*=sponsor],[id*=sponsor],[class*=sidebar-ad],[id*=sidebar-ad],.left-ad,.ad-left,.sticky-ad,.ads,.ad,.ad-box,.ad-wrapper,.adblock,[id^=ad_],[class^=ad_],iframe[src*=kaspi],iframe[src*=digitalcaramel],iframe[src*=yandex],iframe[src*=vak345],iframe[src*=qepolax],iframe[src*=doubleclick],iframe[src*=adservice],iframe[src*=adnxs],iframe[src*=googlesyndication],a[href*=kaspi],img[src*=kaspi],[data-href*=kaspi]';" +
            "document.querySelectorAll(q).forEach(function(e){if(playerNode(e))return;var n=((e.id||'')+' '+(typeof e.className==='string'?e.className:'')).toLowerCase();if(!/(^|[-_\\\\s])(ad|ads|advert|banner|sponsor)([-_\\\\s]|$)/.test(n)&&!/(advert|ad-container|ad-slot|banner-ad|sponsor)/.test(n))return;hideOne(e);});" +
            "document.querySelectorAll('iframe[src*=kaspi],a[href*=kaspi],img[src*=kaspi],[data-href*=kaspi]').forEach(function(e){var p=e;for(var k=0;k<5&&p&&p!==document.body&&p!==document.documentElement;k++,p=p.parentElement){if(playerNode(p))break;var r=p.getBoundingClientRect(),st=getComputedStyle(p);if((st.position==='fixed'||st.position==='absolute')&&r.width>100&&r.height>50){hideOne(p);break;}}});}" +
            "hide();if(!window.__rufilmAdCosmeticObserver){var t=0;window.__rufilmAdCosmeticObserver=new MutationObserver(function(){if(t)return;t=1;setTimeout(function(){t=0;hide();},250);});window.__rufilmAdCosmeticObserver.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});}" +
            "}catch(e){}})();";
        web.evaluateJavascript(js, null);
    }

    private void installVkFrameSupport() {
        if (web == null) return;
        final String js = "(function(){try{" +
            "function collect(w,a,depth){if(depth>5)return;try{a.push(w.document);for(var i=0;i<w.frames.length;i++)try{collect(w.frames[i],a,depth+1);}catch(e){}}catch(e){}}" +
            "function scan(){var ds=[];collect(window,ds,0);ds.forEach(function(d){try{var w=d.defaultView||window;if(!d.__rufilmFrameClickHook){d.__rufilmFrameClickHook=true;" +
            "d.addEventListener('click',function(e){var t=e.target;if(t&&t.tagName==='IFRAME'&&/vk|ok\\\\.ru/i.test(t.src||'')){window.__rufilmVkIntentUntil=Date.now()+10000;}},true);}" +
            "[].slice.call(d.querySelectorAll('video')).forEach(function(v){if(v.__rufilmFramePlayHook)return;v.__rufilmFramePlayHook=true;" +
            "function start(){var until=Math.max(w.__rufilmVkIntentUntil||0,window.__rufilmVkIntentUntil||0);if(Date.now()>until||!v.paused||v.readyState<2||!v.currentSrc)return;try{var p=v.play();if(p&&p.catch)p.catch(function(){});}catch(e){}}" +
            "['loadeddata','canplay','canplaythrough','loadedmetadata'].forEach(function(n){v.addEventListener(n,start);});" +
            "d.addEventListener('click',function(e){var t=e.target;if(t===v||(t&&v.contains(t))){w.__rufilmVkIntentUntil=Date.now()+10000;[100,350,800,1500].forEach(function(ms){setTimeout(start,ms);});}},true);" +
            "});if(!d.__rufilmFrameObserver&&d.documentElement){d.__rufilmFrameObserver=new MutationObserver(function(){scan();});d.__rufilmFrameObserver.observe(d.documentElement,{childList:true,subtree:true});}" +
            "}catch(e){}});}" +
            "window.addEventListener('message',function(e){try{if(!/vk|ok\\\\.ru/i.test(e.origin||''))return;var x=e.data;if(typeof x==='string'){try{x=JSON.parse(x);}catch(z){return;}}" +
            "var found=null;function walk(o,k){if(!o||typeof o!=='object'||k>5)return;Object.keys(o).forEach(function(n){var v=o[n];if(/^(currentTime|current_time|time|position)$/i.test(n)&&typeof v==='number'&&isFinite(v)&&v>0&&v<86400)found=v;else if(v&&typeof v==='object')walk(v,k+1);});}walk(x,0);if(found!==null)window.__rufilmVkTime=found;}catch(z){}},true);" +
            "scan();if(!window.__rufilmFrameRootObserver&&document.documentElement){window.__rufilmFrameRootObserver=new MutationObserver(scan);window.__rufilmFrameRootObserver.observe(document.documentElement,{childList:true,subtree:true});}return true;}catch(e){return false;}})();";
        web.evaluateJavascript(js, null);
    }

    // Capture HLS/DASH manifests and the request headers used by the WebView.
    private void captureMediaRequest(WebResourceRequest request) {
        if (request == null || request.getUrl() == null ||
                !"GET".equalsIgnoreCase(request.getMethod())) return;
        String url = request.getUrl().toString();
        String lower = url.toLowerCase(Locale.ROOT);
        boolean playlist = lower.contains(".m3u8") || lower.contains(".mpd");
        boolean directVideo = lower.contains(".mp4") || lower.contains(".m4v") || lower.contains(".webm");
        if (!(playlist || directVideo) || (isAdRequest(url) && !isRuFilmMediaRequest(url))) return;
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
        int priority = playlist ? 3 : 1;
        synchronized (mediaCaptureLock) {
            long now = System.currentTimeMillis();
            if (capturedMediaUrl == null || now - capturedMediaAt > 15000L || priority >= capturedMediaPriority) {
                capturedMediaUrl = url;
                capturedMediaReferer = (referer == null || referer.isEmpty()) ? BASE + "/" : referer;
                capturedMediaUserAgent = userAgent;
                capturedMediaHeaders = safeHeaders;
                capturedMediaAt = now;
                capturedMediaPriority = priority;
                android.util.Log.i("RuFilmTV", "Captured MX candidate priority=" + priority +
                    " type=" + (playlist ? "playlist" : "file") + " host=" + Uri.parse(url).getHost());
            } else {
                android.util.Log.i("RuFilmTV", "Ignored lower-priority media fragment host=" + Uri.parse(url).getHost());
            }
        }
        maybeOfferMxPlayer(0L);
        // Launch only after the site's fullscreen request; keep episode selection available.
    }

    private boolean isMxPackageInstalled(String packageName) {
        try { getPackageManager().getPackageInfo(packageName, 0); return true; }
        catch (Exception ignored) { return false; }
    }

    // Arm a short capture window after a deliberate Play/fullscreen gesture.
    private void armMxPlayIntent() {
        mxPlayIntentUntil = System.currentTimeMillis() + 15000L;
        mxOfferTriggered = false;
        maybeOfferMxPlayer(0L);
    }

    private void maybeOfferMxPlayer(long positionMs) {
        if (System.currentTimeMillis() > mxPlayIntentUntil || mxOfferTriggered) return;
        synchronized (mediaCaptureLock) {
            if (capturedMediaUrl == null || System.currentTimeMillis() - capturedMediaAt > 90000L) return;
        }
        mxOfferTriggered = true;
        offerMxPlayer(positionMs);
    }

    private void captureMxMedia(String rawUrl, String referer, String userAgent) {
        if (rawUrl == null || !(rawUrl.startsWith("https://") || rawUrl.startsWith("http://"))) return;
        String lower = rawUrl.toLowerCase(Locale.ROOT);
        if (!(lower.contains(".m3u8") || lower.contains(".mpd") || lower.contains(".mp4") ||
                lower.contains(".m4v") || lower.contains(".webm"))) return;
        if (isAdRequest(rawUrl) && !isRuFilmMediaRequest(rawUrl)) return;
        // JS/WebSocket discovery is useful for finding a URL, but the actual
        // WebView request is authoritative for authentication headers. Never let
        // a later JS candidate erase Origin/Authorization/Cookie captured from
        // shouldInterceptRequest for the same media URL.
        HashMap<String, String> headers = new HashMap<>();
        if (referer != null && !referer.isEmpty()) headers.put("Referer", referer);
        try {
            Uri ref = Uri.parse(referer);
            if (ref.getScheme() != null && ref.getAuthority() != null)
                headers.put("Origin", ref.getScheme() + "://" + ref.getAuthority());
        } catch (Exception ignored) { }
        if (userAgent != null && !userAgent.isEmpty()) headers.put("User-Agent", userAgent);
        try {
            String cookie = android.webkit.CookieManager.getInstance().getCookie(rawUrl);
            if (cookie != null && !cookie.isEmpty()) headers.put("Cookie", cookie);
        } catch (Exception ignored) { }
        int priority = (lower.contains(".m3u8") || lower.contains(".mpd")) ? 3 : 1;
        synchronized (mediaCaptureLock) {
            long now = System.currentTimeMillis();
            boolean sameUrl = rawUrl.equals(capturedMediaUrl);
            boolean stale = capturedMediaUrl == null || now - capturedMediaAt > 15000L;
            if (sameUrl) {
                // Keep all real request headers already collected; fill only gaps.
                for (Map.Entry<String, String> entry : headers.entrySet()) {
                    boolean exists = false;
                    for (String key : capturedMediaHeaders.keySet()) {
                        if (key.equalsIgnoreCase(entry.getKey())) { exists = true; break; }
                    }
                    if (!exists) capturedMediaHeaders.put(entry.getKey(), entry.getValue());
                }
                if ((capturedMediaReferer == null || capturedMediaReferer.isEmpty()) &&
                        referer != null) capturedMediaReferer = referer;
                if ((capturedMediaUserAgent == null || capturedMediaUserAgent.isEmpty()) &&
                        userAgent != null) capturedMediaUserAgent = userAgent;
                capturedMediaAt = now;
            } else if (stale || priority > capturedMediaPriority) {
                capturedMediaUrl = rawUrl;
                capturedMediaReferer = referer == null || referer.isEmpty() ? BASE + "/" : referer;
                capturedMediaUserAgent = userAgent;
                capturedMediaHeaders = headers;
                capturedMediaAt = now;
                capturedMediaPriority = priority;
            } else {
                android.util.Log.i("RuFilmTV", "Ignored secondary JS media candidate host=" +
                    Uri.parse(rawUrl).getHost() + " priority=" + priority);
            }
        }
        maybeOfferMxPlayer(0L);
    }

    // Media3 is the only playback engine. Handoff automatically on HTML5 fullscreen.
    private void offerMxPlayer(long positionMs) {
        runOnUiThread(() -> {
            if (nativePlayerLaunching) return;
            playerMode = "native";
            boolean launched = launchCapturedMedia();
            playerMode = "original";
            if (!launched) {
                nativePlayerLaunching = false;
                Toast.makeText(this, "Не удалось перехватить видео для Media3. Оригинальный плеер оставлен на паузе.", Toast.LENGTH_LONG).show();
            }
        });
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
                        "var best=null,bestScore=-1;docs.forEach(function(d,di){try{[].slice.call(d.querySelectorAll('video')).forEach(function(v){var r=v.getBoundingClientRect(),cs=d.defaultView.getComputedStyle(v);var visible=r.width>120&&r.height>70&&r.bottom>0&&r.right>0&&cs.display!=='none'&&cs.visibility!=='hidden';var score=(v.paused?0:100)+(v.readyState>=2?30:0)+(v.videoWidth>0?20:0)+(v.currentTime>0?15:0)+(visible?20:0);if(score>bestScore){bestScore=score;best={video:v,frame:frameIds[di],score:score};}});}catch(e){}});" +
                        "docs.forEach(function(d){var x=d.defaultView||window;x.__rufilmActiveVideo=null;x.__rufilmSavedPlayerLayout=null;});var v=best&&best.video;if(v){var w=v.ownerDocument.defaultView;w.__rufilmActiveVideo=v;var nodes=[],n=v;while(n){nodes.push({el:n,style:n.getAttribute('style'),cls:n.getAttribute('class')});if(n===v.ownerDocument.documentElement)break;n=n.parentElement;}w.__rufilmSavedPlayerLayout={video:v,nodes:nodes,muted:v.muted,volume:v.volume,paused:v.paused,time:v.currentTime};}var tm=v&&isFinite(v.currentTime)?v.currentTime:0;if(tm<0.5&&window.__rufilmVkTime)tm=window.__rufilmVkTime;" +
                        "return JSON.stringify({selectors:sels,time:tm,frameIndex:best?best.frame:-1,score:bestScore,playing:!!(v&&!v.paused)});})()";
                    web.evaluateJavascript(snapshotScript, value -> {
                        try {
                            Object decoded = new org.json.JSONTokener(value == null ? "{}" : value).nextValue();
                            org.json.JSONObject snapshot = new org.json.JSONObject(String.valueOf(decoded));
                            org.json.JSONArray selectors = snapshot.optJSONArray("selectors");
                            long startMs = (long)(snapshot.optDouble("time", 0.0) * 1000.0);
                            launchIntent.putExtra(NativePlayerActivity.EXTRA_EPISODE_SELECTORS, selectors == null ? "[]" : selectors.toString());
                            launchIntent.putExtra(NativePlayerActivity.EXTRA_START_POSITION_MS, startMs);
                            android.util.Log.i("RuFilmTV", "VK fullscreen handoff snapshot: positionMs=" + startMs +
                                " frame=" + snapshot.optInt("frameIndex", -1) +
                                " playing=" + snapshot.optBoolean("playing", false) +
                                " score=" + snapshot.optInt("score", -1));
                        } catch (Exception ignored) { }
                        web.evaluateJavascript("(function(){window.__rufilmNativeActive=true;var docs=[document];try{for(var i=0;i<window.frames.length;i++)try{docs.push(window.frames[i].document);}catch(e){}}catch(e){}docs.forEach(function(d){var w=d.defaultView||window;var v=w.__rufilmActiveVideo;if(!v)return;if(!w.__rufilmSavedPlayerLayout){var nodes=[],n=v;while(n){nodes.push({el:n,style:n.getAttribute('style'),cls:n.getAttribute('class')});if(n===d.documentElement)break;n=n.parentElement;}w.__rufilmSavedPlayerLayout={video:v,nodes:nodes,muted:v.muted,volume:v.volume,paused:v.paused,time:v.currentTime};}v.muted=true;v.volume=0;v.style.opacity='0';v.style.pointerEvents='none';try{v.pause();}catch(e){}});return true;})()", null);
                        web.postDelayed(() -> {
                            try { startActivity(launchIntent); }
                            catch (Exception e) {
                                nativePlayerLaunching = false;
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

once('''                captureMediaRequest(request);
                if (isAdFilteringEnabled() && request != null &&
                        isAdRequest(request.getUrl().toString()) &&
                        !isRuFilmMediaRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();''', '''                captureMediaRequest(request);
                if (request != null && isAdRequest(request.getUrl().toString()) && !isRuFilmMediaRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();''', "request interception")

once('''          + "if(!/^https?:\\/\\//i.test(u))return false;"''', '''          + "if(!/^https?:\\/\\//i.test(u)){try{if(window.RuFilmPlayer.openCaptured()){v.pause();return true;}}catch(e){}return false;}"''', "blob fallback")
once('''          + "var ok=window.RuFilmPlayer&&window.RuFilmPlayer.openNative(String(u),String(location.href),String(navigator.userAgent));"''', '''          + "var ok=window.RuFilmPlayer&&window.RuFilmPlayer.openNative(String(u),String(location.href),String(navigator.userAgent));"
          + "if(!ok){try{ok=window.RuFilmPlayer&&window.RuFilmPlayer.openCaptured();}catch(e){}}"''', "direct fallback")

once('''        @JavascriptInterface public boolean isNativeEnabled() { return "native".equals(playerMode); }''', '''        @JavascriptInterface public boolean isNativeEnabled() { return "native".equals(playerMode); }
        @JavascriptInterface public boolean openCaptured() { return launchCapturedMedia(); }
        @JavascriptInterface public void offerMxPlayer(long positionMs) { MainActivity.this.offerMxPlayer(positionMs); }
        @JavascriptInterface public void armMxPlayIntent() { MainActivity.this.armMxPlayIntent(); }
        @JavascriptInterface public void captureMxMedia(String url, String referer, String userAgent) {
            MainActivity.this.captureMxMedia(url, referer, userAgent);
        }''', "bridge method")


# Keep the site's season/episode selectors usable. Do not launch on manifest discovery.
import re
capture_start = s.find("private void captureMediaRequest")
capture_end = s.find("private boolean launchCapturedMedia", capture_start)
if capture_start >= 0 and capture_end > capture_start:
    capture_block = s[capture_start:capture_end]
    capture_block = capture_block.replace("        launchCapturedMedia();", "        // Wait for the site's fullscreen request after the user selects an episode.")
    s = s[:capture_start] + capture_block + s[capture_end:]

# WebChromeClient keeps the original HTML5 video alive in its fullscreen custom view.

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
            "function installMxOffer(){var docs=[];try{document.addEventListener('click',function(e){var f=e.target&&e.target.closest?e.target.closest('iframe'):null;if(f&&/vk|alloha|stravers/i.test(f.src||'')){try{var z=window.RuFilmPlayer;if(z&&z.armMxPlayIntent)z.armMxPlayIntent();}catch(q){}}},true);}catch(q){}function collect(w,depth){if(depth>5)return;try{var d=w.document;if(d&&docs.indexOf(d)<0)docs.push(d);for(var i=0;i<w.frames.length;i++)try{collect(w.frames[i],depth+1);}catch(e){}}catch(e){}}" +
            "function bindDoc(d){try{var w=d.defaultView||window;[].slice.call(d.querySelectorAll('video')).forEach(function(v){if(v.__rufilmMxOfferHook)return;v.__rufilmMxOfferHook=true;v.__rufilmMxOfferShown=false;" +
            "v.addEventListener('play',function(){if(v.__rufilmMxOfferShown)return;v.__rufilmMxOfferShown=true;try{var b=w.RuFilmPlayer||window.RuFilmPlayer;if(b){if(b.armMxPlayIntent)b.armMxPlayIntent();if(b.captureMxMedia)b.captureMxMedia(String(v.currentSrc||v.src||''),String(w.location.href||location.href),String(w.navigator.userAgent||navigator.userAgent));}}catch(e){}},true);" +
            "v.addEventListener('emptied',function(){v.__rufilmMxOfferShown=false;});});if(!d.__rufilmMxOfferObserver&&d.documentElement){d.__rufilmMxOfferObserver=new MutationObserver(function(){bindDoc(d);});d.__rufilmMxOfferObserver.observe(d.documentElement,{childList:true,subtree:true});}}catch(e){}}" +
            "collect(window,0);docs.forEach(bindDoc);}" +
            "function installFullscreenButton(){var vids=[].slice.call(document.querySelectorAll('video'));vids.forEach(function(v){if(v.__rufilmFsButton)return;" +
            "var b=document.createElement('button');b.type='button';b.setAttribute('aria-label','Во весь экран');b.title='Во весь экран';" +
            "b.innerHTML='<svg viewBox=\"0 0 24 24\" width=\"25\" height=\"25\" fill=\"none\" stroke=\"white\" stroke-width=\"2.1\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M8 3H3v5M3 3l7 7M16 3h5v5m0-5-7 7M8 21H3v-5m0 5 7-7m6 7h5v-5m0 5-7-7\"/></svg>';" +
            "b.style.cssText='position:fixed;z-index:2147483647;width:52px;height:52px;border:1px solid rgba(255,255,255,.72);border-radius:50%;background:rgba(105,91,226,.97);box-shadow:0 4px 16px rgba(0,0,0,.42);display:flex;align-items:center;justify-content:center;padding:0;cursor:pointer;opacity:.98;-webkit-tap-highlight-color:transparent;';" +
            "b.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();try{if(v.requestFullscreen)v.requestFullscreen();else if(v.webkitEnterFullscreen)v.webkitEnterFullscreen();}catch(x){}},true);" +
            "document.body.appendChild(b);v.__rufilmFsButton=b;function place(){try{var r=v.getBoundingClientRect(),w=document.documentElement.clientWidth,h=document.documentElement.clientHeight;" +
            "var visible=!v.paused&&r.width>120&&r.height>70&&r.bottom>0&&r.top<h&&r.right>0&&r.left<w&&getComputedStyle(v).visibility!=='hidden'&&getComputedStyle(v).display!=='none';" +
            "b.style.display=visible?'flex':'none';if(visible){var x=Math.max(8,Math.min(w-60,r.left+(r.width-52)/2));var y=r.bottom+9;if(y+52>h)y=Math.max(8,r.bottom-60);b.style.left=x+'px';b.style.top=y+'px';}}catch(x){b.style.display='none';}}" +
            "['loadedmetadata','play','pause','timeupdate','durationchange','emptied'].forEach(function(e){v.addEventListener(e,place);});" +
            "window.addEventListener('resize',place);window.addEventListener('scroll',place,true);place();v.__rufilmFsPlace=place;});}" +
            "installMxOffer();installFullscreenButton();mark();if(!window.__rufilmTvDpadObserver&&document.documentElement){" +
            "var queued=false;window.__rufilmTvDpadObserver=new MutationObserver(function(){if(queued)return;queued=true;setTimeout(function(){queued=false;installMxOffer();installFullscreenButton();mark();},350);});" +
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

if "MainActivity.this.installEpisodeSelectorSupport();\n                MainActivity.this.installPremiumTopNavigation();" not in s:
    page_finished = re.search(
        r'(public\s+void\s+onPageFinished\s*\([^)]*\)\s*\{)',
        s
    )
    if not page_finished:
        raise SystemExit("Could not find WebViewClient.onPageFinished for DPAD selector setup.")
    insert = page_finished.group(1) + "\n                MainActivity.this.installEpisodeSelectorSupport();\n                MainActivity.this.installVkFirstTapSupport();\n                MainActivity.this.installVkFrameSupport();\n                MainActivity.this.installAdCosmeticFilters();\n                MainActivity.this.applyCleanMode();"
    s = s[:page_finished.start()] + insert + s[page_finished.end():]


# Wire the filter toggle into the existing visible filter button and every ad-filter path.
s = s.replace('''            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request){
                if (request != null && isAdRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, request);
            }''', '''            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request){
                captureMediaRequest(request);
                if (isAdFilteringEnabled() && request != null &&
                        isAdRequest(request.getUrl().toString()) &&
                        !isRuFilmMediaRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, request);
            }''', 1)
s = s.replace('''            @SuppressWarnings("deprecation")
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, String url){
                if (isAdRequest(url)) return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, url);
            }''', '''            @SuppressWarnings("deprecation")
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, String url){
                if (isAdFilteringEnabled() && isAdRequest(url) && !isRuFilmMediaRequest(url))
                    return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, url);
            }''', 1)
s = s.replace('filterButton.setOnClickListener(v->updateFilterLists());',
              'filterButton.setOnClickListener(v->showAdFilterDialog());', 1)
s = s.replace('String[] items = {"Чистый", "Цвет", "Фильтры", "Видеоплеер",', 'String[] items = {"Чистый", "Цвет", "Фильтры рекламы",', 1)
s = s.replace('''    private void applyCleanMode(){
        if(web!=null) web.evaluateJavascript("document.documentElement.classList.toggle('rf-clean',"+cleanMode+");",null);
    }''', '''    private void applyCleanMode(){
        if(web!=null) web.evaluateJavascript("(function(){document.documentElement.classList.toggle('rf-clean',"+cleanMode+");document.documentElement.classList.toggle('rf-no-adfilter',"+(!isAdFilteringEnabled())+");})();",null);
    }''', 1)
s = s.replace('html.rf-clean', 'html.rf-clean:not(.rf-no-adfilter)')

p.write_text(s,encoding="utf-8")
print("Patched",p)



# Apply a restrained premium skin to the site's REAL category navigation.
# Existing anchors, hrefs, forms and event handlers are never replaced or intercepted.
premium_nav = r'''
    private void installPremiumTopNavigation() {
        if (web == null) return;
        final String js = "(function(){try{" +
            "var wanted=['/films','/serials','/cartoon','/tv-show','/trailers'];" +
            "function apply(){var links=[].slice.call(document.querySelectorAll('a[href]')).filter(function(a){try{var u=new URL(a.href,location.href);return u.origin===location.origin&&wanted.indexOf(u.pathname.replace(/\\\\/$/,''))>=0;}catch(e){return false;}});" +
            "if(links.length<4)return;var candidates=links.map(function(a){return a.closest('nav,header,.menu,.navigation,.nav,ul');}).filter(Boolean);var root=null;" +
            "for(var i=0;i<candidates.length;i++){if(links.every(function(a){return candidates[i].contains(a);})){root=candidates[i];break;}}" +
            "if(!root)return;root.classList.add('rufilm-premium-topnav');var list=root.tagName==='UL'?root:root.querySelector('ul');if(list)list.classList.add('rufilm-premium-topnav-list');" +
            "links.forEach(function(a){a.classList.add('rufilm-premium-topnav-link');var li=a.closest('li');if(li)li.classList.add('rufilm-premium-topnav-item');});" +
            "var current=location.pathname.replace(/\\\\/$/,'');links.forEach(function(a){try{var u=new URL(a.href,location.href);if(u.pathname.replace(/\\\\/$/,'')===current)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}catch(e){}});}" +
            "var id='rufilm-premium-topnav-style';if(!document.getElementById(id)){var st=document.createElement('style');st.id=id;st.textContent='.rufilm-premium-topnav{position:sticky!important;top:0!important;z-index:10000!important;background:rgba(17,19,22,.97)!important;border-bottom:1px solid rgba(255,255,255,.09)!important;padding:7px 14px!important}.rufilm-premium-topnav-list{display:flex!important;align-items:center!important;gap:8px!important;flex-wrap:nowrap!important;overflow-x:auto!important;white-space:nowrap!important;scrollbar-width:none!important;margin:0!important;padding:0!important}.rufilm-premium-topnav-list::-webkit-scrollbar{display:none!important}.rufilm-premium-topnav-item{list-style:none!important;flex:0 0 auto!important;margin:0!important;padding:0!important}.rufilm-premium-topnav-link{display:inline-flex!important;align-items:center!important;min-height:38px!important;padding:0 13px!important;border-radius:9px!important;color:#dedee2!important;text-decoration:none!important;font-size:14px!important;font-weight:600!important;outline-offset:3px!important}.rufilm-premium-topnav-link:hover,.rufilm-premium-topnav-link:focus,.rufilm-premium-topnav-link[aria-current=page]{background:#d73445!important;color:#fff!important}.rufilm-premium-topnav-link:focus{outline:2px solid #fff!important}';(document.head||document.documentElement).appendChild(st);}" +
            "apply();if(!window.__rufilmPremiumNavObserver&&document.documentElement){var queued=false;window.__rufilmPremiumNavObserver=new MutationObserver(function(){if(queued)return;queued=true;setTimeout(function(){queued=false;apply();},200);});window.__rufilmPremiumNavObserver.observe(document.documentElement,{childList:true,subtree:true});}" +
            "}catch(e){}})();";
        web.evaluateJavascript(js, null);
    }

'''


# Expose the current activity for the native player's episode and clock callbacks.
bridge_fields = '''
    private static MainActivity rufilmActiveInstance;
    public static void applyEpisodeSelection(int frameIndex, int index, String value) {
        MainActivity a = rufilmActiveInstance;
        if (a == null || a.web == null) return;
        final String quoted = org.json.JSONObject.quote(value == null ? "" : value);
        a.runOnUiThread(() -> a.web.evaluateJavascript("(function(){if(" + frameIndex + ">=0){try{window.frames[" + frameIndex + "].postMessage({__rfEpisodeSelect:{index:" + index + ",value:" + quoted + "}},'*');return true;}catch(e){return false;}}var d=document;var s=d.querySelectorAll('select')[" + index + "];if(s){s.value=" + quoted + ";var w=d.defaultView||window;s.dispatchEvent(new w.Event('input',{bubbles:true}));s.dispatchEvent(new w.Event('change',{bubbles:true}));return true;}try{var e=d.querySelector(" + quoted + ");if(e){e.click();return true;}}catch(x){}return false;})()", null));
    }
    public static void refreshEpisodeSelectors(android.webkit.ValueCallback<String> callback) {
        MainActivity a = rufilmActiveInstance;
        if (a == null || a.web == null) { if (callback != null) callback.onReceiveValue("[]"); return; }
        final String js = "(async function(){try{" +
            "var ds=[document],ids=[-1];window.__rfEpisodeFrameResults=[];if(!window.__rfEpisodeListener){window.__rfEpisodeListener=true;window.addEventListener('message',function(e){try{if(e.data&&e.data.__rfEpisodeSelectors)window.__rfEpisodeFrameResults=window.__rfEpisodeFrameResults.concat(e.data.__rfEpisodeSelectors);}catch(x){}});}for(var fi=0;fi<window.frames.length;fi++){try{window.frames[fi].postMessage({__rfGetEpisodeSelectors:true,frameIndex:fi},'*');}catch(x){}}" +
            "function path(e){if(!e||!e.parentElement)return '';if(e.id)return '#'+CSS.escape(e.id);var a=[],n=e;while(n&&n.nodeType===1&&n!==n.ownerDocument.documentElement){var t=n.tagName.toLowerCase(),k=1,p=n;while((p=p.previousElementSibling))if(p.tagName===n.tagName)k++;a.unshift(t+':nth-of-type('+k+')');n=n.parentElement;}return 'html>'+a.join('>');}" +
            "function vis(e){if(!e)return false;var r=e.getBoundingClientRect(),s=(e.ownerDocument.defaultView||window).getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';}" +
            "function txt(e){return (e.innerText||e.textContent||'').replace(/\\\\s+/g,' ').trim();}function wait(ms){return new Promise(function(r){setTimeout(r,ms);});}await wait(900);" +
            "var out=(window.__rfEpisodeFrameResults||[]).slice();for(var di=0;di<ds.length;di++){var d=ds[di],id=ids[di],sels=[].slice.call(d.querySelectorAll('select'));" +
            "sels.forEach(function(x,i){if(!x.options||x.options.length<2)return;var p=x.parentElement,meta=[x.name,x.id,x.className,x.getAttribute('aria-label'),x.getAttribute('title'),p?txt(p):''].join(' ').toLowerCase();var o=[].map.call(x.options,function(q){return {text:txt(q),value:q.value,selected:q.selected};});var words=o.map(function(q){return q.text;}).join(' ').toLowerCase();var kind=/season|сезон/.test(meta+' '+words)?'season':(/episode|серия|эпизод/.test(meta+' '+words)?'episode':'');if(kind)out.push({frameIndex:id,index:i,kind:kind,selectedText:o[x.selectedIndex]?o[x.selectedIndex].text:'',options:o});});" +
            "for(var kind of ['season','episode']){if(out.some(function(x){return x.frameIndex===id&&x.kind===kind;}))continue;var re=kind==='season'?/^сезон\\\\s*[:№]?\\\\s*\\\\d+$/i:/^(серия|эпизод)\\\\s*[:№]?\\\\s*\\\\d+$/i;" +
            "var triggers=[].slice.call(d.querySelectorAll('button,[role=combobox],[aria-haspopup],[class*=select],[class*=dropdown]')).filter(function(e){return vis(e)&&re.test(txt(e))&&txt(e).length<40;});if(!triggers.length)continue;triggers.sort(function(a,b){return (a.tagName==='BUTTON'?-1:0)-(b.tagName==='BUTTON'?-1:0);});var trigger=triggers[0],selectedText=txt(trigger),triggerPath=path(trigger);try{trigger.click();}catch(e){}await wait(140);" +
            "var optionRe=/^(?:(?:серия|эпизод)\\\\s*)?\\\\d+(?:\\\\s*(?:серия|эпизод))?$/i;var candidates=[].slice.call(d.querySelectorAll('[role=option],[role=menuitem],li,button,[class*=option],[class*=item],span,div')).filter(function(e){if(!vis(e)||e.children.length>1)return false;var t=txt(e);return t.length<24&&optionRe.test(t);});" +
            "var parents=[];candidates.forEach(function(e){var p=e.parentElement;if(!p)return;var count=candidates.filter(function(x){return x.parentElement===p;}).length;if(count>=2&&!parents.some(function(x){return x.el===p;}))parents.push({el:p,count:count});});parents.sort(function(a,b){return b.count-a.count;});" +
            "var pool=parents.length?candidates.filter(function(e){return e.parentElement===parents[0].el;}):candidates;var opts=[];pool.forEach(function(e){var t=txt(e),p=path(e);if(!p||opts.some(function(o){return o.path===p;}))return;var num=(t.match(/\\\\d+/)||[])[0],sel=(selectedText.match(/\\\\d+/)||[])[0];opts.push({text:t,value:num||t,path:p,selected:!!num&&num===sel});});" +
            "if(opts.length){out.push({frameIndex:id,index:-1,kind:kind,custom:true,selectedText:selectedText,options:opts});}try{trigger.click();}catch(e){}await wait(40);" +
            "}}var result=[];['season','episode'].forEach(function(k){var a=out.filter(function(x){return x.kind===k;});if(a.length)result.push(a[0]);});return JSON.stringify(result);" +
            "}catch(e){return '[]';}})()";
        a.runOnUiThread(() -> { if (a.web != null) a.web.evaluateJavascript(js, callback); else if (callback != null) callback.onReceiveValue("[]"); });
    }
    private void saveOriginalPlayerLayout() {
        if (web == null) return;
        final String js = "(function(){var ds=[document];try{for(var i=0;i<window.frames.length;i++)try{ds.push(window.frames[i].document);}catch(e){}}catch(e){}ds.forEach(function(d){try{var v=d.querySelector('video');if(!v)return;var w=d.defaultView;if(w.__rufilmSavedPlayerLayout)return;var nodes=[],x=v;while(x){nodes.push({el:x,style:x.getAttribute('style'),cls:x.getAttribute('class')});if(x===d.documentElement)break;x=x.parentElement;}w.__rufilmSavedPlayerLayout={video:v,nodes:nodes,muted:v.muted,volume:v.volume,paused:v.paused,time:v.currentTime};}catch(e){}});return true;})()";
        runOnUiThread(() -> { if (web != null) web.evaluateJavascript(js, null); });
    }
    public static String getCapturedMediaUrl() {
        MainActivity a = rufilmActiveInstance;
        if (a == null) return null;
        synchronized (a.mediaCaptureLock) { return a.capturedMediaUrl; }
    }
    public static long getCapturedMediaAt() {
        MainActivity a = rufilmActiveInstance;
        if (a == null) return 0L;
        synchronized (a.mediaCaptureLock) { return a.capturedMediaAt; }
    }
    public static String getCapturedMediaSnapshot() {
        MainActivity a = rufilmActiveInstance;
        if (a == null) return "{}";
        synchronized (a.mediaCaptureLock) {
            try {
                org.json.JSONObject result = new org.json.JSONObject();
                result.put("url", a.capturedMediaUrl);
                result.put("referer", a.capturedMediaReferer);
                result.put("userAgent", a.capturedMediaUserAgent);
                result.put("headers", new org.json.JSONObject(a.capturedMediaHeaders));
                result.put("capturedAt", a.capturedMediaAt);
                return result.toString();
            } catch (Exception e) { return "{}"; }
        }
    }
    public static void syncOriginalPlayback(long positionMs, boolean nativeActive) {
        MainActivity a = rufilmActiveInstance;
        if (a == null || a.web == null) return;
        final long syncPositionMs = positionMs;
        a.runOnUiThread(() -> {
            String js = "(function(){function collect(w,a,n){if(n>5)return;try{a.push(w.document);for(var i=0;i<w.frames.length;i++)try{collect(w.frames[i],a,n+1);}catch(e){}}catch(e){}}var docs=[];collect(window,docs,0);(function send(w,n){if(n>6)return;try{w.postMessage({__rufilmStopOriginal:true},\\\"*\\\");for(var i=0;i<w.frames.length;i++)send(w.frames[i],n+1);}catch(e){}})(window,0);window.__rufilmOriginalSuspended=true;function notifyFrames(){try{var fs=document.querySelectorAll('iframe,frame');for(var i=0;i<fs.length;i++){var f=fs[i];if(!f.__rufilmStopBound){f.__rufilmStopBound=true;f.addEventListener('load',function(){try{this.contentWindow.postMessage({__rufilmStopOriginal:true},'*');}catch(e){}});}try{f.contentWindow.postMessage({__rufilmStopOriginal:true},'*');}catch(e){}}}catch(e){}}notifyFrames();if(!window.__rufilmFrameObserver&&document.documentElement){window.__rufilmFrameObserver=new MutationObserver(notifyFrames);window.__rufilmFrameObserver.observe(document.documentElement,{childList:true,subtree:true});}var t=" + (syncPositionMs > 0L ? syncPositionMs/1000.0 : -1.0) + ";docs.forEach(function(d){try{var w=d.defaultView||window,z=w.__rufilmSavedPlayerLayout,v=(z&&z.video)||w.__rufilmActiveVideo;if(!v)return;if(" + nativeActive + "){w.__rufilmNativeActive=true;if(t>=0&&isFinite(t)&&Math.abs(v.currentTime-t)>2){try{v.currentTime=t;}catch(e){}}v.muted=true;v.volume=0;v.style.opacity='0';v.style.pointerEvents='none';try{v.pause();}catch(e){}return;}w.__rufilmNativeActive=false;var done=false;function keepOriginalStopped(){try{v.pause();v.muted=true;v.volume=0;v.style.opacity='0';v.style.visibility='hidden';v.style.pointerEvents='none';v.style.display='none';}catch(e){}}if(!v.__rufilmStopGuard){v.__rufilmStopGuard=true;v.addEventListener('play',function(){keepOriginalStopped();},true);v.addEventListener('playing',function(){keepOriginalStopped();},true);try{var originalPlay=v.play.bind(v);v.play=function(){keepOriginalStopped();return Promise.reject(new DOMException('Original player is suspended','AbortError'));};}catch(e){}}function finishSeek(){if(done)return;done=true;if(t>=0&&isFinite(t)&&Math.abs(v.currentTime-t)>1.25){try{v.currentTime=t;}catch(e){}}keepOriginalStopped();[150,350,700,1100,1800,3000].forEach(function(ms){setTimeout(keepOriginalStopped,ms);});}function seek(){if(t>=0&&isFinite(t)&&Math.abs(v.currentTime-t)>1.25){try{v.addEventListener('seeked',finishSeek,{once:true});v.currentTime=t;}catch(e){}}setTimeout(finishSeek,500);}if(v.readyState>=1)seek();else{v.addEventListener('loadedmetadata',seek,{once:true});setTimeout(seek,900);}}catch(e){}});return true;})()";
            android.util.Log.i("RuFilmTV", "Restore original VK playback at " + syncPositionMs + " ms; nativeActive=" + nativeActive);
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

# Apply the user's persisted A/V offset through the Android TV audio HAL.
# This is a vendor-specific request; the in-app calibration menu lets the user test support.
if "applyAudioSyncOffset(getAudioSyncOffsetMs())" not in s:
    s = s.replace('        rufilmActiveInstance = this;\n', '''        rufilmActiveInstance = this;
        applyAudioSyncOffset(getAudioSyncOffsetMs());
''', 1)

# Make WebView requests look like the installed Chrome engine and allow player iframe cookies.
web_ctor = re.search(r'(\bweb\s*=\s*new\s+WebView\s*\([^;]*\);)', s)
if web_ctor and 'setAcceptThirdPartyCookies(web, true)' not in s:
    setup = '''
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);
        web.setOnTouchListener((v, event) -> {
            if (event.getAction() == MotionEvent.ACTION_DOWN) {
                v.requestFocus();
                v.requestFocusFromTouch();
            }
            return false;
        });
        android.webkit.CookieManager.getInstance().setAcceptCookie(true);
        if (android.os.Build.VERSION.SDK_INT >= 21)
            android.webkit.CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);
        try {
            String ua = web.getSettings().getUserAgentString();
            if (ua != null) web.getSettings().setUserAgentString(ua.replace("; wv", "").replace("Version/4.0 ", ""));
        } catch (Exception ignored) { }
'''
    s = s[:web_ctor.end()] + setup + s[web_ctor.end():]

# Release the launch guard when returning from NativePlayerActivity.
# MainActivity receives onResume after the native player is closed.
resume = re.search(r'((?:public|protected)\s+void\s+onResume\s*\(\s*\)\s*\{)', s)
if resume:
    body_end = resume.end()
    if 'nativePlayerLaunching = false;' not in s[body_end:body_end + 220]:
        s = s[:body_end] + '\n        boolean returningFromNativePlayer = nativePlayerLaunching;\n        if (web != null) web.onResume();\n        if (returningFromNativePlayer && customView != null) hideCustomView();\n        nativePlayerLaunching = false;\n        syncOriginalPlayback(0L, false);\n        applyAudioSyncOffset(getAudioSyncOffsetMs());\n        if (returningFromNativePlayer && web != null) {\n            web.postDelayed(() -> syncOriginalPlayback(0L, false), 350L);\n            web.postDelayed(() -> syncOriginalPlayback(0L, false), 1100L);\n        }' + s[body_end:]
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


# The vendor HAL request may affect the device audio path, so clear it when app loses foreground.
pause = re.search(r'((?:public|protected)\s+void\s+onPause\s*\(\s*\)\s*\{)', s)
if pause:
    body_end = pause.end()
    if 'applyAudioSyncOffset(0);' not in s[body_end:body_end + 300]:
        s = s[:body_end] + '\n        applyAudioSyncOffset(0);' + s[body_end:]
    if 'if (nativePlayerLaunching && web != null) web.onPause();' not in s[body_end:body_end + 500]:
        s = s[:body_end] + '\n        if (nativePlayerLaunching && web != null) web.onPause();' + s[body_end:]
else:
    class_end = s.rfind('}')
    if class_end < 0:
        raise SystemExit('Could not find MainActivity class end for onPause')
    s = s[:class_end] + '''
    @Override protected void onPause() {
        applyAudioSyncOffset(0);
        if (nativePlayerLaunching && web != null) web.onPause();
        super.onPause();
    }

''' + s[class_end:]

# Use the same HTML5 element for fullscreen; never auto-launch a second ExoPlayer.
hook_start = s.find("    private void injectExternalPlayerHook(WebView view) {")
hook_end = s.find("    private class PlayerBridge", hook_start)
if hook_start < 0 or hook_end < 0:
    raise SystemExit("Could not locate external-player hook")
s = s[:hook_start] + "    private void injectExternalPlayerHook(WebView view) { installEpisodeSelectorSupport(); }\n\n" + s[hook_end:]

fullscreen_fields = r"""
    // The fullscreen root keeps Android's normal mouse arrow visible over the HTML5 surface.
    private final class CursorVisibleFrame extends FrameLayout {
        CursorVisibleFrame(Context context) {
            super(context);
            if (Build.VERSION.SDK_INT >= 24)
                setPointerIcon(PointerIcon.getSystemIcon(MainActivity.this, PointerIcon.TYPE_ARROW));
        }
        @Override public PointerIcon onResolvePointerIcon(MotionEvent event, int pointerIndex) {
            if (Build.VERSION.SDK_INT >= 24)
                return PointerIcon.getSystemIcon(MainActivity.this, PointerIcon.TYPE_ARROW);
            return null;
        }
    }
    private FrameLayout fullscreenControls;
    private Button fullscreenSeasonButton, fullscreenEpisodeButton, fullscreenMuteButton;
    private android.widget.SeekBar fullscreenVolumeSeek;
    private org.json.JSONObject fullscreenSeasonData, fullscreenEpisodeData;
    private final android.os.Handler fullscreenUiHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    // Never request TYPE_NULL: Android TV mouse pointers must remain visible over HTML5 video.
    private final Runnable hideSystemCursor = () -> { };
    private void setSystemCursorVisible(boolean visible) {
        if (Build.VERSION.SDK_INT < 24 || customView == null) return;
        PointerIcon arrow = PointerIcon.getSystemIcon(this, PointerIcon.TYPE_ARROW);
        getWindow().getDecorView().setPointerIcon(arrow);
        if (fullscreenContainer != null) fullscreenContainer.setPointerIcon(arrow);
        if (customView != null) customView.setPointerIcon(arrow);
        if (web != null) web.setPointerIcon(arrow);
    }
    private void revealSystemCursor() {
        if (Build.VERSION.SDK_INT < 24 || customView == null) return;
        fullscreenUiHandler.removeCallbacks(hideSystemCursor);
        setSystemCursorVisible(true);
    }
    private void installFullscreenCursor(View target) {
        if (target == null || Build.VERSION.SDK_INT < 24) return;
        final PointerIcon arrow = PointerIcon.getSystemIcon(this, PointerIcon.TYPE_ARROW);
        target.setPointerIcon(arrow);
        target.setOnHoverListener((v, event) -> {
            int action = event.getAction();
            if (action == MotionEvent.ACTION_HOVER_ENTER ||
                    action == MotionEvent.ACTION_HOVER_MOVE ||
                    action == MotionEvent.ACTION_SCROLL) {
                v.setPointerIcon(arrow);
                revealSystemCursor();
                showFullscreenUi();
            }
            return false;
        });
        if (target instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) target;
            for (int i = 0; i < group.getChildCount(); i++) {
                installFullscreenCursor(group.getChildAt(i));
            }
        }
    }
    private final Runnable hideFullscreenUi = () -> {
        if (fullscreenControls != null) fullscreenControls.animate().alpha(0f).setDuration(220L).withEndAction(() -> {
            if (fullscreenControls != null && fullscreenControls.getAlpha() < 0.1f) fullscreenControls.setVisibility(View.GONE);
        }).start();
    };
    private int lastNonZeroMusicVolume = 5;
"""
if "private FrameLayout fullscreenControls;" not in s:
    anchor = "    private final Object mediaCaptureLock = new Object();"
    if anchor not in s: raise SystemExit("fullscreen fields anchor missing")
    s = s.replace(anchor, fullscreen_fields + "\n" + anchor, 1)

fullscreen_methods = r"""
    private void showFullscreenUi() {
        if (fullscreenControls == null) return;
        fullscreenControls.setVisibility(View.VISIBLE);
        fullscreenControls.animate().alpha(1f).setDuration(140L).start();
        fullscreenUiHandler.removeCallbacks(hideFullscreenUi);
        fullscreenUiHandler.postDelayed(hideFullscreenUi, 5000L);
    }

    private void addFullscreenControls() {
        if (fullscreenContainer == null || fullscreenControls != null) return;
        fullscreenControls = new FrameLayout(this);
        fullscreenControls.setFocusable(false);
        if (Build.VERSION.SDK_INT >= 24) {
            fullscreenControls.setPointerIcon(PointerIcon.getSystemIcon(this, PointerIcon.TYPE_ARROW));
            fullscreenControls.setOnHoverListener((v, event) -> {
                int action = event.getAction();
                if (action == MotionEvent.ACTION_HOVER_ENTER || action == MotionEvent.ACTION_HOVER_MOVE) {
                    v.setPointerIcon(PointerIcon.getSystemIcon(MainActivity.this, PointerIcon.TYPE_ARROW));
                    showFullscreenUi();
                }
                return false;
            });
        }
        // Let the original HTML5 video receive the click; use it only to reveal controls.
        fullscreenControls.setOnTouchListener((v, event) -> {
            if (event.getAction() == MotionEvent.ACTION_DOWN) showFullscreenUi();
            return false;
        });
        fullscreenContainer.addView(fullscreenControls, new FrameLayout.LayoutParams(-1, -1));

        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(12), dp(6), dp(12), dp(6));
        bar.setBackground(shape(0xdd111316, 12));
        FrameLayout.LayoutParams barParams = new FrameLayout.LayoutParams(-1, dp(62), Gravity.TOP);
        barParams.setMargins(dp(18), dp(16), dp(18), 0);
        fullscreenControls.addView(bar, barParams);

        Button exit = button("Назад", false);
        exit.setOnClickListener(v -> hideCustomView());
        bar.addView(exit, new LinearLayout.LayoutParams(dp(82), dp(46)));

        TextView brand = text("RU FILM TV", 15, Color.WHITE, true);
        LinearLayout.LayoutParams brandParams = new LinearLayout.LayoutParams(0, dp(46), 1f);
        brandParams.leftMargin = dp(12);
        bar.addView(brand, brandParams);

        fullscreenSeasonButton = button("Сезон ▾", false);
        fullscreenSeasonButton.setTextSize(11);
        fullscreenSeasonButton.setOnClickListener(v -> { showFullscreenUi(); showFullscreenSelector(true); });
        bar.addView(fullscreenSeasonButton, new LinearLayout.LayoutParams(dp(126), dp(46)));

        fullscreenEpisodeButton = button("Серия ▾", true);
        fullscreenEpisodeButton.setTextSize(11);
        LinearLayout.LayoutParams epParams = new LinearLayout.LayoutParams(dp(126), dp(46));
        epParams.leftMargin = dp(8);
        bar.addView(fullscreenEpisodeButton, epParams);
        fullscreenEpisodeButton.setOnClickListener(v -> { showFullscreenUi(); showFullscreenSelector(false); });

        LinearLayout volumeBar = new LinearLayout(this);
        volumeBar.setGravity(Gravity.CENTER_VERTICAL);
        volumeBar.setPadding(dp(12), dp(4), dp(12), dp(4));
        volumeBar.setBackground(shape(0xdd111316, 12));
        FrameLayout.LayoutParams volumeParams = new FrameLayout.LayoutParams(dp(300), dp(58), Gravity.BOTTOM | Gravity.START);
        volumeParams.setMargins(dp(18), 0, 0, dp(18));
        fullscreenControls.addView(volumeBar, volumeParams);

        fullscreenMuteButton = button("Звук", false);
        fullscreenMuteButton.setTextSize(10);
        fullscreenMuteButton.setOnClickListener(v -> {
            android.media.AudioManager am = (android.media.AudioManager)getSystemService(AUDIO_SERVICE);
            if (am == null) return;
            int current = am.getStreamVolume(android.media.AudioManager.STREAM_MUSIC);
            if (current > 0) {
                lastNonZeroMusicVolume = current;
                am.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, 0, 0);
            } else {
                int max = am.getStreamMaxVolume(android.media.AudioManager.STREAM_MUSIC);
                am.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, Math.max(1, Math.min(max, lastNonZeroMusicVolume)), 0);
            }
            updateFullscreenVolumeUi();
            showFullscreenUi();
        });
        volumeBar.addView(fullscreenMuteButton, new LinearLayout.LayoutParams(dp(74), dp(46)));

        fullscreenVolumeSeek = new android.widget.SeekBar(this);
        android.media.AudioManager am = (android.media.AudioManager)getSystemService(AUDIO_SERVICE);
        int max = am == null ? 15 : Math.max(1, am.getStreamMaxVolume(android.media.AudioManager.STREAM_MUSIC));
        int current = am == null ? max : am.getStreamVolume(android.media.AudioManager.STREAM_MUSIC);
        fullscreenVolumeSeek.setMax(max);
        fullscreenVolumeSeek.setProgress(current);
        fullscreenVolumeSeek.setFocusable(true);
        fullscreenVolumeSeek.setContentDescription("Громкость");
        fullscreenVolumeSeek.setOnSeekBarChangeListener(new android.widget.SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(android.widget.SeekBar seekBar, int progress, boolean fromUser) {
                if (!fromUser) return;
                android.media.AudioManager audio = (android.media.AudioManager)getSystemService(AUDIO_SERVICE);
                if (audio != null) audio.setStreamVolume(android.media.AudioManager.STREAM_MUSIC, progress, 0);
                if (progress > 0) lastNonZeroMusicVolume = progress;
                updateFullscreenVolumeUi();
                showFullscreenUi();
            }
            @Override public void onStartTrackingTouch(android.widget.SeekBar seekBar) { showFullscreenUi(); }
            @Override public void onStopTrackingTouch(android.widget.SeekBar seekBar) { showFullscreenUi(); }
        });
        LinearLayout.LayoutParams seekParams = new LinearLayout.LayoutParams(0, dp(44), 1f);
        seekParams.leftMargin = dp(8);
        volumeBar.addView(fullscreenVolumeSeek, seekParams);

        refreshFullscreenSelectors();
        updateFullscreenVolumeUi();
        showFullscreenUi();
    }

    private void updateFullscreenVolumeUi() {
        android.media.AudioManager am = (android.media.AudioManager)getSystemService(AUDIO_SERVICE);
        if (am == null || fullscreenVolumeSeek == null) return;
        int max = Math.max(1, am.getStreamMaxVolume(android.media.AudioManager.STREAM_MUSIC));
        int current = am.getStreamVolume(android.media.AudioManager.STREAM_MUSIC);
        fullscreenVolumeSeek.setMax(max);
        if (!fullscreenVolumeSeek.isPressed()) fullscreenVolumeSeek.setProgress(current);
        if (fullscreenMuteButton != null) fullscreenMuteButton.setText(current == 0 ? "Без звука" : "Звук");
    }

    private void refreshFullscreenSelectors() {
        if (web == null) return;
        final String js = "(function(){var ds=[document],ids=[-1];try{for(var i=0;i<window.frames.length;i++)try{var d=window.frames[i].document;if(d){ds.push(d);ids.push(i);}}catch(e){}}catch(e){}" +
            "var all=[];ds.forEach(function(d,k){[].slice.call(d.querySelectorAll('select')).forEach(function(x,i){if(!x.options||x.options.length<2)return;" +
            "var n=x,near='';for(var z=0;z<4&&n;z++,n=n.parentElement)if(n.innerText)near+=' '+n.innerText;" +
            "var meta=[x.name,x.id,x.className,x.getAttribute('aria-label'),x.getAttribute('title'),near].join(' ').toLowerCase();" +
            "var opts=[].map.call(x.options,function(o){return {text:(o.textContent||'').trim(),value:o.value};});var words=opts.map(function(o){return o.text;}).join(' ').toLowerCase();" +
            "var season=/season|сезон/.test(meta+' '+words),episode=/episode|серия|эпизод/.test(meta+' '+words);" +
            "all.push({frameIndex:ids[k],index:i,kind:season?'season':(episode?'episode':'other'),meta:meta,words:words,selectedText:opts[x.selectedIndex]?opts[x.selectedIndex].text:'',options:opts,score:(season||episode?100:0)+(/player|video|serial|series|плеер|сериал/.test(meta)?30:0)});});});" +
            "var ss=all.filter(function(x){return x.kind==='season'}).sort(function(a,b){return b.score-a.score;});var ee=all.filter(function(x){return x.kind==='episode'}).sort(function(a,b){return b.score-a.score;});" +
            "if(!ss.length||!ee.length){var rest=all.filter(function(x){return x!== (ss.length?ss[0]:null) && !/quality|качество|разрешение|озвучка|субтитр|не требуется/.test((x.meta||'')+' '+(x.words||''));}).sort(function(a,b){return b.score-a.score;});" +
            "if(!ss.length&&rest.length)ss=[rest.shift()];if(!ee.length&&rest.length)ee=[rest.shift()];}" +
            "return JSON.stringify({season:ss.length?ss[0]:null,episode:ee.length?ee[0]:null});})()";
        web.evaluateJavascript(js, value -> {
            try {
                Object decoded = new org.json.JSONTokener(value == null ? "{}" : value).nextValue();
                org.json.JSONObject data = new org.json.JSONObject(String.valueOf(decoded));
                fullscreenSeasonData = data.optJSONObject("season");
                fullscreenEpisodeData = data.optJSONObject("episode");
                if (fullscreenSeasonButton != null) fullscreenSeasonButton.setText(fullscreenSeasonData == null ? "Сезон —" : "Сезон: " + fullscreenSeasonData.optString("selectedText", "Выбрать") + " ▾");
                if (fullscreenEpisodeButton != null) fullscreenEpisodeButton.setText(fullscreenEpisodeData == null ? "Серия —" : "Серия: " + fullscreenEpisodeData.optString("selectedText", "Выбрать") + " ▾");
            } catch (Exception ignored) { }
        });
    }

    private void showFullscreenSelector(boolean season) {
        org.json.JSONObject data = season ? fullscreenSeasonData : fullscreenEpisodeData;
        if (data == null) {
            refreshFullscreenSelectors();
            Toast.makeText(this, "Список серий не найден на странице плеера.", Toast.LENGTH_LONG).show();
            return;
        }
        org.json.JSONArray options = data.optJSONArray("options");
        if (options == null || options.length() == 0) return;
        String[] labels = new String[options.length()];
        for (int i = 0; i < options.length(); i++) {
            org.json.JSONObject item = options.optJSONObject(i);
            labels[i] = item == null ? "" : item.optString("text", "");
        }
        new AlertDialog.Builder(this).setTitle(season ? "Выбор сезона" : "Выбор серии")
            .setItems(labels, (dialog, which) -> {
                org.json.JSONObject item = options.optJSONObject(which);
                if (item == null) return;
                int frame = data.optInt("frameIndex", -1);
                int index = data.optInt("index", -1);
                String selected = org.json.JSONObject.quote(item.optString("value", ""));
                String script = "(function(){var d=document;try{if(" + frame + ">=0)d=window.frames[" + frame + "].document;}catch(e){return false;}" +
                    "var s=d.querySelectorAll('select')[" + index + "];if(!s)return false;s.value=" + selected + ";" +
                    "var w=d.defaultView||window;s.dispatchEvent(new w.Event('input',{bubbles:true}));s.dispatchEvent(new w.Event('change',{bubbles:true}));return true;})()";
                web.evaluateJavascript(script, null);
                fullscreenUiHandler.postDelayed(this::refreshFullscreenSelectors, 900L);
                showFullscreenUi();
            }).setNegativeButton("Отмена", null).show();
    }

    @Override public boolean dispatchTouchEvent(MotionEvent event) {
        if (customView != null && event != null && event.getAction() == MotionEvent.ACTION_DOWN)
            showFullscreenUi();
        return super.dispatchTouchEvent(event);
    }

    @Override public boolean dispatchGenericMotionEvent(MotionEvent event) {
        boolean handled = super.dispatchGenericMotionEvent(event);
        if (customView != null && event != null) {
            int action = event.getAction();
            if (action == MotionEvent.ACTION_HOVER_ENTER ||
                    action == MotionEvent.ACTION_HOVER_MOVE ||
                    action == MotionEvent.ACTION_SCROLL) {
                revealSystemCursor();
                setSystemCursorVisible(true);
                showFullscreenUi();
            }
        }
        return handled;
    }
"""
if "private void addFullscreenControls()" not in s:
    anchor = "    private void hideCustomView(){"
    if anchor not in s:
        raise SystemExit("fullscreen methods anchor missing")
    s = s.replace(anchor, fullscreen_methods + "\n" + anchor, 1)

# Force the original WebChromeClient fullscreen container and its video surface to use a visible arrow.
s = s.replace(
    "fullscreenContainer=new FrameLayout(MainActivity.this);",
    "fullscreenContainer=new CursorVisibleFrame(MainActivity.this);",
    1
)
view_anchor = "fullscreenContainer.addView(view,new FrameLayout.LayoutParams(-1,-1));"
if view_anchor in s and "installFullscreenCursor(view);" not in s:
    nl = chr(10)
    cursor_code = (view_anchor + nl
                   + "                installFullscreenCursor(view);" + nl
                   + "                installFullscreenCursor(fullscreenContainer);" + nl
                   + "                setSystemCursorVisible(true);" + nl
                   + "                addFullscreenControls();")
    s = s.replace(view_anchor, cursor_code, 1)

hide_anchor = "if(customView==null)return;";
if "fullscreenUiHandler.removeCallbacks(hideSystemCursor);" not in s:
    s = s.replace(hide_anchor, hide_anchor + "\n        fullscreenUiHandler.removeCallbacks(hideSystemCursor);", 1)
if hide_anchor in s and "fullscreenUiHandler.removeCallbacks(hideFullscreenUi);" not in s:
    s = s.replace(hide_anchor, hide_anchor + "\n        fullscreenUiHandler.removeCallbacks(hideFullscreenUi);fullscreenControls=null;", 1)

key_anchor = "    @Override public boolean dispatchKeyEvent(KeyEvent event) {"
key_inject = "if(customView!=null && event.getAction()==KeyEvent.ACTION_DOWN) showFullscreenUi();"
if key_anchor in s and key_inject not in s:
    s = s.replace(key_anchor, key_anchor + "\n        " + key_inject, 1)


s = s.replace('private final int bg = Color.rgb(17,19,22), panel = Color.rgb(33,36,40),\n        accent = Color.rgb(215,52,69), muted = Color.rgb(173,176,183);',
'''private final int bg = Color.rgb(17,19,22), panel = Color.rgb(33,36,40),
        muted = Color.rgb(173,176,183);
    private int accent = Color.rgb(215,52,69);
    private Button themeButton;
    private int selectedTheme = 0;
    private final String[] themeNames = {"Красный","Фиолетовый","Синий","Голубой","Бирюзовый","Зелёный","Лайм","Оранжевый","Розовый","Золотой"};
    private final int[] themeColors = {0xffd73445,0xff9b6bdb,0xff3978e8,0xff20a6d8,0xff16a6a0,0xff35a866,0xff91b832,0xffe88732,0xffdc669e,0xffc49a42};''')
s = s.replace('text("RU FILM",23,Color.WHITE,true)', 'text("RUFILM TV",23,Color.WHITE,true)')
s = s.replace('text("TV  •  YOUR CINEMA",9,0xffff7b86,true)', 'text("ТВОЙ ОНЛАЙН КИНОТЕАТР",9,0xffff7b86,true)')
s = s.replace('playerMode = "original"; // Native Media3 handoff intentionally disabled; keep the site original player.',
'''playerMode = "original"; // Keep the website's original player; Media3 handoff is disabled.
        selectedTheme = Math.max(0, Math.min(9, prefs.getInt("theme_index", 0)));
        accent = themeColors[selectedTheme];''')
s = s.replace('''        playerButton=button("Плеер",false);playerButton.setTextSize(9);''', '''        themeButton=button("Цвет",false);themeButton.setTextSize(9);
        themeButton.setOnClickListener(v->showThemeDialog());
        LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(dp(54),dp(42));tp.leftMargin=dp(5);header.addView(themeButton,tp);
        playerButton=button("Плеер",false);playerButton.setTextSize(9);''')
s = s.replace('root.addView(nav);setContentView(root);updateTabs();',
              'root.addView(nav);setContentView(root);updateTabs();applyTheme(false);')
s = s.replace('''                    injectExternalPlayerHook(view);
                    applyCleanMode();''', '''                    injectExternalPlayerHook(view);
                    applyTheme(true);
                    applyCleanMode();''')
methods = r"""
    private void showThemeDialog() {
        new AlertDialog.Builder(this).setTitle("Цвет оформления")
            .setSingleChoiceItems(themeNames, selectedTheme, (dialog, which) -> {
                selectedTheme = which; accent = themeColors[which];
                prefs.edit().putInt("theme_index", which).apply();
                applyTheme(true); dialog.dismiss();
            }).setNegativeButton("Закрыть", null).show();
    }
    private void applyTheme(boolean updateWeb) {
        if (rootLayout != null) rootLayout.setBackgroundColor(bg);
        // Keep the original backup UI; move only native app controls into the More dialog.
        if (cleanButton != null) cleanButton.setVisibility(View.GONE);
        if (themeButton != null) themeButton.setVisibility(View.GONE);
        if (filterButton != null) filterButton.setVisibility(View.GONE);
        if (playerButton != null) playerButton.setVisibility(View.GONE);
        if (cleanButton != null) cleanButton.setBackground(shape(cleanMode ? accent : panel, 13));
        if (filterButton != null) filterButton.setBackground(shape(panel, 13));
        if (playerButton != null) playerButton.setBackground(shape(panel, 13));
        if (themeButton != null) themeButton.setBackground(shape(accent, 13));
        if (web != null && updateWeb) {
            String a = String.format(Locale.US, "#%06X", (0xFFFFFF & accent));
            String js = "(function(){var id='rufilm-theme-colors',accent='" + a + "';" +
                "function install(d){try{if(!d||!d.documentElement)return;var st=d.getElementById(id);if(!st){st=d.createElement('style');st.id=id;(d.head||d.documentElement).appendChild(st);}" +
                "var css=':root{--rf-accent:'+accent+'!important;--rf-red:'+accent+'!important;--primary:'+accent+'!important;--accent:'+accent+'!important;color-scheme:dark;}'" +
                "+'a,a:visited,.link,.pagination a,.pages a,.navigation a,.pagi a,.description a,.entry-content a{color:'+accent+'!important;}'" +
                "+'a:focus,button:focus,input:focus,select:focus,textarea:focus,[tabindex]:focus{outline:3px solid '+accent+'!important;outline-offset:2px!important;}'" +
                "+'button,input[type=submit],input[type=button],.active,.current,.pagination .active,.pages .active,.selected,.is-active,[aria-current=true]{background:'+accent+'!important;border-color:'+accent+'!important;color:#fff!important;}'" +
                "+'input[type=checkbox],input[type=radio],progress{accent-color:'+accent+'!important;}'" +
                "+'::selection{background:'+accent+'!important;color:#fff!important;}'" +
                "+'article,.shortstory,.short-story,.movie-item,.film-item,.serial-item,.item,.post,.news-item,.story,.content-item,.movie,.film,.serial,.card{border-color:'+accent+'66!important;}'" +
                "+'.progress,.progress-bar,.video-js .vjs-play-progress,.plyr__progress__played{background-color:'+accent+'!important;}';st.textContent=css;" +
                "}catch(e){}}" +
                "install(document);function scan(){var fs=document.querySelectorAll('iframe');for(var i=0;i<fs.length;i++){try{install(fs[i].contentDocument);}catch(e){}if(!fs[i].__rufilmThemeBound){fs[i].__rufilmThemeBound=true;fs[i].addEventListener('load',function(){try{install(this.contentDocument);}catch(e){}});}}}" +
                "scan();if(!window.__rufilmThemeObserver){window.__rufilmThemeObserver=new MutationObserver(scan);window.__rufilmThemeObserver.observe(document.documentElement,{childList:true,subtree:true});}})();";
            web.evaluateJavascript(js, null);
        }
        updateTabs();
    }
"""
if "private void showThemeDialog()" not in s:
    s = s.replace("    private void updateFilterLists(){", methods + "\n    private void updateFilterLists(){")

# User-controlled master switch for network ad filtering. Enabled by default.
if "private boolean isAdFilteringEnabled()" not in s:
    ad_filter_controls = r"""
    private boolean isAdFilteringEnabled() {
        return prefs == null || prefs.getBoolean("ad_filters_enabled", true);
    }

    private void showAdFilterDialog() {
        boolean enabled = isAdFilteringEnabled();
        String[] choices = {"Включить блокировку рекламы", "Отключить фильтры рекламы"};
        new AlertDialog.Builder(this)
            .setTitle("Фильтры рекламы")
            .setItems(choices, (dialog, which) -> {
                boolean turnOn = which == 0;
                if (prefs != null) prefs.edit().putBoolean("ad_filters_enabled", turnOn).apply();
                applyCleanMode();
                Toast.makeText(this, turnOn ? "Блокировка рекламы включена" : "Фильтры рекламы отключены", Toast.LENGTH_LONG).show();
            })
            .setNegativeButton("Закрыть", null)
            .show();
    }
"""
    anchor = "    private void updateFilterLists(){"
    if anchor not in s: raise SystemExit("Ad-filter dialog insertion anchor missing")
    s = s.replace(anchor, ad_filter_controls + "\n" + anchor, 1)

s=s.replace('''                if (Build.VERSION.SDK_INT >= 24) {
                    view.setOnHoverListener((v, event) -> {''', '''                if (Build.VERSION.SDK_INT >= 24) {
                    view.setPointerIcon(PointerIcon.getSystemIcon(MainActivity.this, PointerIcon.TYPE_ARROW));
                    view.setOnHoverListener((v, event) -> {''', 1)
s=s.replace('''                fullscreenContainer.setBackgroundColor(Color.BLACK);
                fullscreenContainer.addView(view,new FrameLayout.LayoutParams(-1,-1));''', '''                fullscreenContainer.setBackgroundColor(Color.BLACK);
                if (Build.VERSION.SDK_INT >= 24) {
                    fullscreenContainer.setPointerIcon(PointerIcon.getSystemIcon(MainActivity.this, PointerIcon.TYPE_ARROW));
                    fullscreenContainer.setOnHoverListener((v, event) -> {
                        if (event.getAction() == MotionEvent.ACTION_HOVER_ENTER || event.getAction() == MotionEvent.ACTION_HOVER_MOVE)
                            v.setPointerIcon(PointerIcon.getSystemIcon(MainActivity.this, PointerIcon.TYPE_ARROW));
                        return false;
                    });
                }
                fullscreenContainer.addView(view,new FrameLayout.LayoutParams(-1,-1));''')

# Keep the original HTML5/VK player in its own fullscreen surface.
# Never hide the site's player or switch to Media3 on the Play/fullscreen gesture.
fullscreen_anchor = """            @Override public void onShowCustomView(View view, CustomViewCallback callback){
                if(customView!=null){callback.onCustomViewHidden();return;}"""
fullscreen_handoff = """            @Override public void onShowCustomView(View view, CustomViewCallback callback){
                if(customView!=null){callback.onCustomViewHidden();return;}
                // Original-player-only mode: never intercept VK/HTML5 fullscreen for Media3.
                MainActivity.this.armMxPlayIntent();"""
if fullscreen_handoff not in s:
    if fullscreen_anchor not in s:
        raise SystemExit("Could not find original WebChromeClient fullscreen anchor")
    s = s.replace(fullscreen_anchor, fullscreen_handoff, 1)

# Keep the Android mouse cursor available while the WebView custom view is fullscreen.
s=s.replace('decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);',
              'decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);')

# Persist all edits, including the native-player bridge appended above.
# Requested cleanup: preserve the current player, remove redundant season/episode and volume overlay.
s = s.replace('fullscreenContainer.addView(view,new FrameLayout.LayoutParams(-1,-1));\n                addFullscreenControls();', 'fullscreenContainer.addView(view,new FrameLayout.LayoutParams(-1,-1));\n                addFullscreenControls();')
# Hide bottom navigation only on film/series detail pages that actually contain a player.
s = s.replace('private View rootLayout, customView;', 'private View rootLayout, customView, bottomNav;')
s = s.replace('root.addView(nav);setContentView(root);updateTabs();', 'bottomNav=nav;root.addView(nav);setContentView(root);updateTabs();')
s = s.replace('pageTitle.setText(titleFor(url));\n                view.evaluateJavascript(skin, ignored -> {', 'pageTitle.setText(titleFor(url));\n                updateBottomNavForPage(url);\n                new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> updateBottomNavForPage(url), 1000L);\n                view.evaluateJavascript(skin, ignored -> {')
s = s.replace('pageTitle.setText(titleFor(url));\n                firstPageReady = true;', 'pageTitle.setText(titleFor(url));\n                if (bottomNav != null) bottomNav.setVisibility(View.VISIBLE);\n                firstPageReady = true;')
if 'private void updateBottomNavForPage(String url)' not in s:
    nav_method = '''\n    private void updateBottomNavForPage(String url) {\n        if (bottomNav == null || web == null) return;\n        boolean detail = url != null && url.matches("(?i).*://[^/]+/(films?|serials?)/[^/?#]+.*");\n        if (!detail) { bottomNav.setVisibility(View.VISIBLE); return; }\n        web.evaluateJavascript("(function(){return !!document.querySelector('video, .player iframe, .video iframe, iframe[src*=player], iframe[src*=video], iframe[src*=embed]');})()", value -> {\n            if (bottomNav != null) bottomNav.setVisibility("true".equals(value) ? View.GONE : View.VISIBLE);\n        });\n    }\n'''
    anchor = '    private String titleFor(String url){'
    if anchor not in s: raise SystemExit('titleFor anchor missing')
    s = s.replace(anchor, nav_method + anchor, 1)
if 'web.setOverScrollMode(View.OVER_SCROLL_NEVER);' not in s:
    s = s.replace('web.setLayerType(View.LAYER_TYPE_HARDWARE, null);', 'web.setLayerType(View.LAYER_TYPE_HARDWARE, null);\n        web.setOverScrollMode(View.OVER_SCROLL_NEVER);')
if 'web.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_DEFAULT);' not in s:
    s = s.replace('web.getSettings().setDomStorageEnabled(true);', 'web.getSettings().setDomStorageEnabled(true);\n        web.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_DEFAULT);\n        web.getSettings().setSupportZoom(false);\n        web.getSettings().setJavaScriptCanOpenWindowsAutomatically(false);')

# Final UI pass: keep the compact fullscreen bar, but remove season/episode and volume widgets.
import re as _rufilm_re
_start = s.find("    private void addFullscreenControls() {")
_end = s.find("    private void refreshFullscreenSelectors()", _start)
if _start >= 0 and _end > _start:
    _minimal_controls = r"""    private void addFullscreenControls() {
        if (fullscreenContainer == null || fullscreenControls != null) return;
        fullscreenControls = new FrameLayout(this);
        fullscreenControls.setFocusable(false);
        fullscreenControls.setClickable(false);
        fullscreenContainer.addView(fullscreenControls, new FrameLayout.LayoutParams(-1, -1));
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(12), dp(6), dp(12), dp(6));
        bar.setBackground(shape(0xdd111316, 12));
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(-2, dp(58), Gravity.TOP | Gravity.END);
        params.setMargins(0, dp(16), dp(18), 0);
        fullscreenControls.addView(bar, params);
        Button exit = button("Выйти", false);
        exit.setContentDescription("Выйти из полноэкранного режима");
        exit.setOnClickListener(v -> hideCustomView());
        bar.addView(exit, new LinearLayout.LayoutParams(dp(92), dp(44)));
        installFullscreenCursor(fullscreenControls);
        showFullscreenUi();
    }

"""
    s = s[:_start] + _minimal_controls + s[_end:]
# Hide the bottom tabs on any non-home page where the actual video player/embed is present.
_nav = _rufilm_re.search(r"    private void updateBottomNavForPage\(String url\) \{.*?\n    \}", s, _rufilm_re.S)
if _nav:
    _nav_method = r"""    private void updateBottomNavForPage(String url) {
        if (bottomNav == null || web == null) return;
        boolean home = url == null || "/".equals(Uri.parse(url).getPath()) || Uri.parse(url).getPath().isEmpty();
        if (home) { bottomNav.setVisibility(View.VISIBLE); return; }
        web.evaluateJavascript("(function(){return !!document.querySelector('video, .jwplayer, .video-js, iframe[src*=player], iframe[src*=video], iframe[src*=embed], [class*=player], [id*=player]');})()", value -> {
            if (bottomNav != null) bottomNav.setVisibility("true".equals(value) ? View.GONE : View.VISIBLE);
        });
    }"""
    s = s[:_nav.start()] + _nav_method + s[_nav.end():]


# Reliable bottom navigation visibility: detect real player DOM on every completed page,
# not only hard-coded /films/ and /serials/ URL patterns.
import re as _nav_re
_nav_method = r"""    private int videoNavCheckGeneration = 0;
    private final android.os.Handler videoNavHandler = new android.os.Handler(android.os.Looper.getMainLooper());

    private void updateBottomNavForPage(String url) {
        if (bottomNav == null || web == null) return;
        int generation = ++videoNavCheckGeneration;
        String path = "";
        try { path = url == null ? "" : Uri.parse(url).getPath(); } catch (Exception ignored) {}
        if (path.isEmpty() || "/".equals(path)) {
            bottomNav.setVisibility(View.VISIBLE);
            return;
        }
        checkVideoPageForNavigation(generation, 0);
    }

    private void checkVideoPageForNavigation(int generation, int attempt) {
        if (generation != videoNavCheckGeneration || bottomNav == null || web == null) return;
        String js = "(function(){try{" +
            "var selectors='video,audio,iframe,object,embed,[class*=player i],[id*=player i],[class*=video i],[id*=video i],[data-player]';" +
            "var nodes=document.querySelectorAll(selectors);" +
            "for(var i=0;i<nodes.length;i++){var e=nodes[i],r=e.getBoundingClientRect(),st=getComputedStyle(e);" +
            "if(r.width>100&&r.height>60&&st.display!=='none'&&st.visibility!=='hidden')return true;}" +
            "return false;}catch(e){return false;}})()";
        web.evaluateJavascript(js, value -> {
            if (generation != videoNavCheckGeneration || bottomNav == null) return;
            if ("true".equals(value)) {
                bottomNav.setVisibility(View.GONE);
            } else if (attempt < 24) {
                videoNavHandler.postDelayed(() -> checkVideoPageForNavigation(generation, attempt + 1), 300L);
            } else {
                bottomNav.setVisibility(View.VISIBLE);
            }
        });
    }
"""
_nav_pattern = _nav_re.compile(r"    private void updateBottomNavForPage\(String url\) \{.*?\n    \}", _nav_re.S)
if _nav_pattern.search(s):
    s = _nav_pattern.sub(lambda m: _nav_method.rstrip(), s, count=1)
else:
    anchor = '    private String titleFor(String url){'
    if anchor not in s: raise SystemExit("titleFor insertion anchor missing")
    s = s.replace(anchor, _nav_method + "\n" + anchor, 1)

# Run the detector after actual page load completes; this also catches delayed iframe players.
if "MainActivity.this.updateBottomNavForPage(view.getUrl());" not in s:
    s = s.replace(
        "MainActivity.this.installEpisodeSelectorSupport();",
        "MainActivity.this.installEpisodeSelectorSupport();\n                MainActivity.this.updateBottomNavForPage(view.getUrl());",
        1
    )
# Remove the redundant fixed 1-second duplicate check that added needless UI work.
s = s.replace(
    "updateBottomNavForPage(url);\n                new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> updateBottomNavForPage(url), 1000L);",
    "updateBottomNavForPage(url);"
)
# Ensure WebView uses the normal HTTP cache and hardware rendering without forced reloads.
s = s.replace("web.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_DEFAULT);",
              "web.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_DEFAULT);")


# Add a compact app menu with the GitHub Release updater.
once("private Button cleanButton, filterButton, playerButton;",
     "private Button cleanButton, filterButton, playerButton, moreButton, refreshButton;",
     "app menu button field")
once('        Button search=button("⌕",true);',
     '        moreButton=button("Ещё",false); moreButton.setTextSize(10);\n        moreButton.setOnClickListener(v->showAppMenu());\n        LinearLayout.LayoutParams mp=new LinearLayout.LayoutParams(dp(58),dp(42));mp.leftMargin=dp(5);header.addView(moreButton,mp);\n        refreshButton=button("↻",false); refreshButton.setTextSize(21);\n        refreshButton.setContentDescription("Обновить страницу");\n        refreshButton.setOnClickListener(v->{ if(web!=null){ web.reload(); web.requestFocus(); } });\n        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(dp(42),dp(42));rp.leftMargin=dp(5);header.addView(refreshButton,rp);\n        Button search=button("⌕",true);',
     "app menu and refresh button")
once("    private void showPlayerDialog() {",
     '''    private int getAudioSyncOffsetMs() {
        return getSharedPreferences("rufilm_audio_sync", MODE_PRIVATE).getInt("offset_ms", -275);
    }

    private void applyAudioSyncOffset(int offsetMs) {
        try {
            android.media.AudioManager audio = (android.media.AudioManager)getSystemService(AUDIO_SERVICE);
            if (audio == null) {
                android.util.Log.w("RuFilmTV", "A/V sync offset not applied: AudioManager unavailable");
                return;
            }
            audio.setParameters("audio_delay=" + offsetMs);
            android.util.Log.i("RuFilmTV", "A/V sync HAL request: audio_delay=" + offsetMs
                    + " ms; device=" + android.os.Build.MANUFACTURER + "/" + android.os.Build.MODEL);
        } catch (Exception e) {
            android.util.Log.w("RuFilmTV", "A/V sync HAL request failed for " + offsetMs + " ms", e);
        }
    }

    private void showAudioSyncDialog() {
        java.util.ArrayList<Integer> values = new java.util.ArrayList<>();
        values.add(0);
        for (int value = -50; value >= -700; value -= 50) values.add(value);
        for (int value = 10; value <= 100; value += 10) values.add(value);
        for (int value = 150; value <= 700; value += 50) values.add(value);
        final int[] offsets = new int[values.size()];
        String[] labels = new String[values.size()];
        int selected = 0;
        int current = getAudioSyncOffsetMs();
        for (int i = 0; i < values.size(); i++) {
            int value = values.get(i);
            offsets[i] = value;
            labels[i] = value == 0 ? "0 мс — без коррекции" :
                (value < 0 ? "−" + (-value) + " мс" : "+" + value + " мс");
            if (value == current) selected = i;
        }
        new AlertDialog.Builder(this).setTitle("Синхронизация звука")
            .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                int value = offsets[which];
                getSharedPreferences("rufilm_audio_sync", MODE_PRIVATE).edit()
                    .putInt("offset_ms", value).apply();
                applyAudioSyncOffset(value);
                String message = value == 0 ? "Коррекция отключена" :
                    (value < 0 ? "Запрошено опережение звука на " + (-value) + " мс" :
                        "Запрошена задержка звука на " + value + " мс");
                Toast.makeText(this, message, Toast.LENGTH_LONG).show();
                dialog.dismiss();
            }).setNegativeButton("Закрыть", null).show();
    }

    private void showAppMenu() {
        String[] items = {"Чистый", "Цвет", "Фильтры",
                "Синхронизация звука", "Проверить обновления", "Обновить списки рекламы"};
        new AlertDialog.Builder(this).setTitle("Ещё").setItems(items, (dialog, which) -> {
            if (which == 0) { if (cleanButton != null) cleanButton.performClick(); }
            else if (which == 1) { if (themeButton != null) themeButton.performClick(); }
            else if (which == 2) showAdFilterDialog();
            else if (which == 3) showAudioSyncDialog();
            else if (which == 4) AppUpdateManager.check(MainActivity.this);
            else if (which == 5) updateFilterLists();
        }).show();
    }

    private void showPlayerDialog() {''',
     "GitHub updater menu and audio sync calibration")
s = s.replace("showPlayerDialog(); return true;", "showAppMenu(); return true;")
once("    @Override protected void onSaveInstanceState(Bundle out){",
     '''    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        AppUpdateManager.onActivityResult(this, requestCode, resultCode);
    }

    @Override protected void onSaveInstanceState(Bundle out){''',
     "updater installer result callback")


if "private void installPremiumTopNavigation()" not in s:
    nav_anchor = "    // Capture HLS/DASH manifests and the request headers used by the WebView."
    if nav_anchor not in s:
        raise SystemExit("Java method insertion anchor missing")
    s = s.replace(nav_anchor, premium_nav + nav_anchor, 1)

if "MainActivity.this.installPremiumTopNavigation();" not in s:
    page_finished = re.search(
        r'(public\s+void\s+onPageFinished\s*\([^)]*\)\s*\{)',
        s
    )
    if not page_finished:
        raise SystemExit("onPageFinished anchor missing")
    insert = page_finished.group(1) + "\n                MainActivity.this.installPremiumTopNavigation();"
    s = s[:page_finished.start()] + insert + s[page_finished.end():]


# FINAL GUARDED AD-FILTER AND MEDIA-CAPTURE WIRING
# Apply after every other transformation so later insertions cannot undo these guards.
import re as _final_re
_apply = '''    private void applyCleanMode(){
        if(web!=null) web.evaluateJavascript("(function(){var d=document.documentElement;if(!d)return;d.classList.toggle('rf-clean',"+cleanMode+");d.classList.toggle('rf-no-adfilter',"+(!isAdFilteringEnabled())+");d.classList.toggle('rf-adfilter-enabled',"+isAdFilteringEnabled()+");})();",null);
        if(cleanButton!=null){
            cleanButton.setText(cleanMode?"Чистый ✓":"Чистый");
            cleanButton.setBackground(shape(cleanMode?0xffb9273d:panel,13));
        }
    }'''
s, _n = _final_re.subn(r'    private void applyCleanMode\(\)\s*\{.*?\n    \}', _apply, s, count=1, flags=_final_re.S)
if _n != 1:
    raise SystemExit("Could not enforce ad-filter CSS toggle in applyCleanMode")
_modern = r'''(@Override public WebResourceResponse shouldInterceptRequest\(WebView view, WebResourceRequest request\)\s*\{).*?(return super\.shouldInterceptRequest\(view, request\);\s*\})'''
_modern_body = r'''\1
                captureMediaRequest(request);
                String requestUrl = request == null ? null : request.getUrl().toString();
                if (requestUrl != null && !isRuFilmMediaRequest(requestUrl) &&
                        (isAdFilteringEnabled() && (isKnownAdRequest(requestUrl) || isAdRequest(requestUrl))))
                    return emptyBlockedResponse();
                \2'''
s, _n = _final_re.subn(_modern, _modern_body, s, count=1, flags=_final_re.S)
if _n != 1:
    raise SystemExit("Could not enforce modern WebView interception and manifest capture")
_legacy = r'''(@SuppressWarnings\("deprecation"\)\s*@Override public WebResourceResponse shouldInterceptRequest\(WebView view, String url\)\s*\{).*?(return super\.shouldInterceptRequest\(view, url\);\s*\})'''
_legacy_body = r'''\1
                if (!isRuFilmMediaRequest(url) &&
                        (isAdFilteringEnabled() && (isKnownAdRequest(url) || isAdRequest(url))))
                    return emptyBlockedResponse();
                \2'''
s, _n = _final_re.subn(_legacy, _legacy_body, s, count=1, flags=_final_re.S)
if _n != 1:
    raise SystemExit("Could not enforce legacy WebView interception guard")

# VK returns its playable stream asynchronously from this player API after the user presses Play.
# Do not make WebView reject that delayed play() call as an autoplay gesture violation.
if "setMediaPlaybackRequiresUserGesture(true)" in s:
    s = s.replace("setMediaPlaybackRequiresUserGesture(true)", "setMediaPlaybackRequiresUserGesture(false)", 1)
elif "setMediaPlaybackRequiresUserGesture(false)" not in s:
    raise SystemExit("Could not locate WebView media gesture setting")

# Copy the loopback proxy helper next to MainActivity so Android compiles it in-package.
proxy_source = pathlib.Path(__file__).with_name("LocalStreamProxy.java")
if not proxy_source.exists():
    raise SystemExit("LocalStreamProxy.java is missing from patches/")
(p.parent / "LocalStreamProxy.java").write_text(proxy_source.read_text(encoding="utf-8"), encoding="utf-8")

p.write_text(s, encoding="utf-8")
print("Patched", p)
# Rebuild trigger after native assistant controls fix.

# Trigger rebuild after Java line-break correction.
