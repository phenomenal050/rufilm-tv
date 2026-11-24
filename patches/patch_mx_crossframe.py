#!/usr/bin/env python3
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
s = path.read_text(encoding="utf-8")

def once(old, new, label):
    global s
    if new in s:
        return
    if old not in s:
        raise SystemExit("Missing patch anchor: " + label)
    s = s.replace(old, new, 1)

once(
    "import android.webkit.JavascriptInterface;",
    "import android.webkit.JavascriptInterface;\n"
    "import androidx.webkit.WebViewCompat;\n"
    "import androidx.webkit.WebViewFeature;\n"
    "import java.util.Collections;",
    "AndroidX WebKit imports"
)

once(
    '        web.addJavascriptInterface(new PlayerBridge(), "RuFilmPlayer");',
    '        web.addJavascriptInterface(new PlayerBridge(), "RuFilmPlayer");\n'
    '        installCrossFrameMediaCapture(web);',
    "install all-frame media bridge before first page load"
)

java = r"""
    // Inject into every frame at document start. Alloha/VK may resolve the real
    // media URL inside a cross-origin iframe and deliver it over WebSocket.
    private void installCrossFrameMediaCapture(WebView target) {
        if (target == null) return;
        try {
            if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
                android.util.Log.w("RuFilmMX", "WebMessageListener unsupported");
                return;
            }
            WebViewCompat.addWebMessageListener(target, "RuFilmCapture",
                Collections.singleton("*"),
                (sourceView, message, sourceOrigin, isMainFrame, replyProxy) -> {
                    try {
                        if (sourceOrigin == null ||
                            !"https".equalsIgnoreCase(sourceOrigin.getScheme())) return;
                        String data = message == null ? null : message.getData();
                        if (data == null || data.length() > 1200000) return;
                        org.json.JSONObject payload = new org.json.JSONObject(data);
                        String mediaUrl = payload.optString("url", "");
                        String referer = payload.optString("referer", sourceOrigin.toString());
                        String userAgent = payload.optString("userAgent",
                            target.getSettings().getUserAgentString());
                        if (!(mediaUrl.startsWith("https://") || mediaUrl.startsWith("http://"))) return;
                        android.util.Log.i("RuFilmMX", "Frame candidate origin=" +
                            sourceOrigin.getHost() + " kind=" + payload.optString("kind", "frame"));
                        captureMxMedia(mediaUrl, referer, userAgent);
                    } catch (Exception e) {
                        android.util.Log.w("RuFilmMX", "Rejected frame media message", e);
                    }
                });

            if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                android.util.Log.w("RuFilmMX", "Document-start script unsupported");
                return;
            }

            String js =
                "(function(){try{if(window.__rufilmCrossFrameHook)return;window.__rufilmCrossFrameHook=true;" +
                "function send(u,k){try{if(!u||!(u.indexOf('https://')===0||u.indexOf('http://')===0))return;" +
                "var x=u.toLowerCase(),ok=false;['.m3u8','.mpd','.mp4','.m4v','.webm'].forEach(function(e){" +
                "var p=x.indexOf(e);if(p>=0&&(p+e.length===x.length||['?','&','#'].indexOf(x.charAt(p+e.length))>=0))ok=true;});" +
                "if(!ok)return;var o=window.RuFilmCapture;if(o&&o.postMessage)o.postMessage(JSON.stringify({" +
                "url:u,referer:String(location.href||''),userAgent:String(navigator.userAgent||''),kind:k||'frame'}));" +
                "}catch(e){}}" +
                "function walk(v,d,k){if(d>4||v==null)return;if(typeof v==='string'){extract(v,k,d+1);return;}" +
                "if(Array.isArray(v)){v.slice(0,300).forEach(function(x){walk(x,d+1,k);});return;}" +
                "if(typeof v==='object'){Object.keys(v).slice(0,300).forEach(function(n){walk(v[n],d+1,k);});}}" +
                "function extract(t,k,d){if(d>4||t==null)return;if(typeof t!=='string')t=String(t);if(t.length>1000000)return;" +
                "var s=t.split('\\\\/').join('/').split('\\\\u0026').join('&').split('&amp;').join('&');" +
                "var i=0;while((i=s.indexOf('http',i))>=0){if(s.substr(i,7)!=='http://'&&s.substr(i,8)!=='https://'){i+=4;continue;}" +
                "var j=i;while(j<s.length&&' \\t\\r\\n\\\"\\'<>'.indexOf(s.charAt(j))<0)j++;var u=s.substring(i,j);" +
                "while(u.length&&'),.;]}'.indexOf(u.charAt(u.length-1))>=0)u=u.substring(0,u.length-1);send(u,k);i=Math.max(j,i+4);}" +
                "if(s.charAt(0)==='{'||s.charAt(0)==='['){try{walk(JSON.parse(s),d+1,k);}catch(e){}}" +
                "else if(s.length>48&&s.length<100000){try{extract(atob(s.replace(/-/g,'+').replace(/_/g,'/')),k+'-base64',d+1);}catch(e){}}}" +
                "function inspect(v,k){try{if(typeof Blob!=='undefined'&&v instanceof Blob){v.text().then(function(t){extract(t,k,0);});return;}" +
                "if(v instanceof ArrayBuffer){extract(new TextDecoder().decode(v),k,0);return;}" +
                "if(ArrayBuffer.isView(v)){extract(new TextDecoder().decode(v),k,0);return;}extract(v,k,0);}catch(e){}}" +
                "try{var N=window.WebSocket;if(N)window.WebSocket=new Proxy(N,{construct:function(C,a){var w=Reflect.construct(C,a,C);" +
                "try{w.addEventListener('message',function(e){inspect(e.data,'websocket-in');});var old=w.send;" +
                "w.send=function(v){inspect(v,'websocket-out');return old.apply(this,arguments);};}catch(e){}return w;}});}catch(e){}" +
                "try{var f=window.fetch;if(f)window.fetch=function(){return f.apply(this,arguments).then(function(r){" +
                "try{r.clone().text().then(function(t){extract(t,'fetch-response',0);});}catch(e){}return r;});};}catch(e){}" +
                "try{var o=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(){this.addEventListener('load',function(){" +
                "try{if(typeof this.responseText==='string')extract(this.responseText,'xhr-response',0);}catch(e){} });return o.apply(this,arguments);};}catch(e){}" +
                "try{if(window.PerformanceObserver)new PerformanceObserver(function(l){l.getEntries().forEach(function(e){send(e.name,'resource');});}).observe({type:'resource',buffered:true});}catch(e){}" +
                "try{document.addEventListener('play',function(e){var v=e.target;if(v&&v.tagName==='VIDEO')send(v.currentSrc||v.src,'video-element');},true);}catch(e){}" +
                "var __rfOriginalSuspended=false;function stopOriginal(){__rfOriginalSuspended=true;try{[].slice.call(document.querySelectorAll('video,audio')).forEach(function(v){try{v.pause();v.muted=true;v.volume=0;v.style.opacity='0';v.style.pointerEvents='none';if(!v.__rufilmStopGuard){v.__rufilmStopGuard=true;var stop=function(){try{v.pause();v.muted=true;v.volume=0;v.style.opacity='0';v.style.pointerEvents='none';}catch(x){}};v.addEventListener('play',stop,true);v.addEventListener('playing',stop,true);try{v.play=function(){stop();return Promise.resolve();};}catch(x){}}}catch(x){}});}catch(x){}}" +
                "function watchOriginal(){try{if(document.documentElement&&!window.__rufilmStopObserver){window.__rufilmStopObserver=new MutationObserver(function(){if(__rfOriginalSuspended)stopOriginal();});window.__rufilmStopObserver.observe(document.documentElement,{childList:true,subtree:true});}}catch(x){}}watchOriginal();document.addEventListener('DOMContentLoaded',watchOriginal,{once:true});" +
                "document.addEventListener('play',function(e){if(__rfOriginalSuspended)stopOriginal();},true);document.addEventListener('playing',function(e){if(__rfOriginalSuspended)stopOriginal();},true);" +
                "window.addEventListener('message',function(e){try{if(e.data&&e.data.__rufilmStopOriginal){stopOriginal();setTimeout(stopOriginal,150);setTimeout(stopOriginal,650);setTimeout(stopOriginal,1400);setTimeout(stopOriginal,2500);}}catch(x){}});" +
                "function epText(e){return (e.innerText||e.textContent||'').replace(/\\\\s+/g,' ').trim();}" +
                "function epPath(e){if(!e||!e.parentElement)return '';if(e.id)return '#'+CSS.escape(e.id);var a=[],n=e;while(n&&n.nodeType===1&&n!==n.ownerDocument.documentElement){var t=n.tagName.toLowerCase(),k=1,p=n;while((p=p.previousElementSibling))if(p.tagName===n.tagName)k++;a.unshift(t+':nth-of-type('+k+')');n=n.parentElement;}return 'html>'+a.join('>');}" +
                "function epVisible(e){try{var r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';}catch(x){return false;}}" +
                "async function epScan(frameIndex){var out=[],sels=[].slice.call(document.querySelectorAll('select'));sels.forEach(function(x,i){if(!x.options||x.options.length<2)return;var p=x.parentElement,meta=[x.name,x.id,x.className,x.getAttribute('aria-label'),x.getAttribute('title'),p?epText(p):''].join(' ').toLowerCase(),o=[].map.call(x.options,function(q){return {text:epText(q),value:q.value,selected:q.selected};}),words=o.map(function(q){return q.text;}).join(' ').toLowerCase(),kind=/season|сезон/.test(meta+' '+words)?'season':(/episode|серия|эпизод/.test(meta+' '+words)?'episode':'');if(kind)out.push({frameIndex:frameIndex,index:i,kind:kind,selectedText:o[x.selectedIndex]?o[x.selectedIndex].text:'',options:o});});" +
                "for(var kind of ['season','episode']){if(out.some(function(x){return x.kind===kind;}))continue;var re=kind==='season'?/^сезон\\\\s*[:№]?\\\\s*\\\\d+$/i:/^(серия|эпизод)\\\\s*[:№]?\\\\s*\\\\d+$/i,tr=[].slice.call(document.querySelectorAll('button,[role=combobox],[aria-haspopup],[class*=select],[class*=dropdown]')).filter(function(x){return epVisible(x)&&re.test(epText(x))&&epText(x).length<40;});if(!tr.length)continue;var trigger=tr[0],selected=epText(trigger);try{trigger.click();}catch(x){}await new Promise(function(r){setTimeout(r,160);});" +
                "var optRe=/^(?:(?:серия|эпизод)\\\\s*)?\\\\d+(?:\\\\s*(?:серия|эпизод))?$/i,nodes=[].slice.call(document.querySelectorAll('[role=option],[role=menuitem],li,button,[class*=option],[class*=item],span,div')).filter(function(x){return epVisible(x)&&x.children.length<=1&&epText(x).length<24&&optRe.test(epText(x));}),groups=[];nodes.forEach(function(x){var p=x.parentElement;if(!p)return;var count=nodes.filter(function(y){return y.parentElement===p;}).length;if(count>=2&&!groups.some(function(g){return g.el===p;}))groups.push({el:p,count:count});});groups.sort(function(a,b){return b.count-a.count;});var pool=groups.length?nodes.filter(function(x){return x.parentElement===groups[0].el;}):nodes,options=[];pool.forEach(function(x){var t=epText(x),p=epPath(x),num=(t.match(/\\\\d+/)||[])[0],sel=(selected.match(/\\\\d+/)||[])[0];if(p&&!options.some(function(o){return o.path===p;}))options.push({text:t,value:num||t,path:p,selected:!!num&&num===sel});});if(options.length)out.push({frameIndex:frameIndex,index:-1,kind:kind,custom:true,selectedText:selected,options:options});try{trigger.click();}catch(x){}await new Promise(function(r){setTimeout(r,40);});}return out;}" +
                "window.addEventListener('message',function(e){try{var d=e.data||{};if(d.__rfGetEpisodeSelectors){epScan(d.frameIndex).then(function(a){try{e.source.postMessage({__rfEpisodeSelectors:a},'*');}catch(x){}});}if(d.__rfEpisodeSelect){var q=d.__rfEpisodeSelect;if(q.index>=0){var s=document.querySelectorAll('select')[q.index];if(s){s.value=q.value;s.dispatchEvent(new Event('input',{bubbles:true}));s.dispatchEvent(new Event('change',{bubbles:true}));}}else{var n=document.querySelector(q.value);if(n)n.click();}}}catch(x){}});" +
                "}catch(e){}})();";

            WebViewCompat.addDocumentStartJavaScript(target, js, Collections.singleton("*"));
            android.util.Log.i("RuFilmMX", "Cross-frame WebSocket/media capture installed");
        } catch (Exception e) {
            android.util.Log.e("RuFilmMX", "Cross-frame capture installation failed", e);
        }
    }

"""
if "private void installCrossFrameMediaCapture" not in s:
    marker = "    private class PlayerBridge {"
    if marker not in s:
        raise SystemExit("Missing PlayerBridge insertion anchor")
    s = s.replace(marker, java + marker, 1)

# Add the iframe origin required by some external stream servers.
origin_old = '        if (referer != null && !referer.isEmpty()) headers.put("Referer", referer);'
origin_new = origin_old + """
        try {
            Uri ref = Uri.parse(referer);
            if (ref.getScheme() != null && ref.getAuthority() != null)
                headers.put("Origin", ref.getScheme() + "://" + ref.getAuthority());
        } catch (Exception ignored) { }"""
once(origin_old, origin_new, "Origin header for external player handoff")

path.write_text(s, encoding="utf-8")
print("Patched", path)
