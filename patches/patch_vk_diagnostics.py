#!/usr/bin/env python3
"""Add privacy-safe VK/WebView diagnostics to the generated MainActivity.java."""
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global source
    if new in source:
        return
    if old not in source:
        raise SystemExit("Required diagnostic patch anchor not found: " + label)
    source = source.replace(old, new, 1)

helpers = r'''
    // VK WebView diagnostics. Never log query strings, cookies, auth headers or request values.
    private boolean isVkDiagnosticUrl(String rawUrl) {
        if (rawUrl == null) return false;
        try {
            String host = Uri.parse(rawUrl).getHost();
            if (host == null) return false;
            host = host.toLowerCase(Locale.ROOT);
            return host.contains("vk") || host.equals("userapi.com") ||
                host.endsWith(".userapi.com");
        } catch (Exception ignored) { return false; }
    }

    private String safeVkTarget(String rawUrl) {
        if (rawUrl == null) return "(no-url)";
        try {
            Uri uri = Uri.parse(rawUrl);
            String host = uri.getHost();
            String path = uri.getPath();
            if (host == null) return "(invalid-url)";
            if (path == null) path = "/";
            if (path.length() > 140) path = path.substring(0, 140);
            return host + path; // Deliberately omit query and fragment.
        } catch (Exception ignored) { return "(invalid-url)"; }
    }

    private void logVkRequest(WebResourceRequest request, boolean blocked) {
        if (request == null || request.getUrl() == null) return;
        String url = request.getUrl().toString();
        if (!isVkDiagnosticUrl(url)) return;
        android.util.Log.i("RuFilmVK", (blocked ? "BLOCK " : "REQ ") +
            request.getMethod() + " " + safeVkTarget(url) +
            " mainFrame=" + request.isForMainFrame());
    }

    private void logVkUrl(String url, String method, boolean blocked, String detail) {
        if (!isVkDiagnosticUrl(url)) return;
        android.util.Log.i("RuFilmVK", (blocked ? "BLOCK " : "REQ ") +
            method + " " + safeVkTarget(url) +
            (detail == null || detail.isEmpty() ? "" : " " + detail));
    }

    private String safeVkMessage(String message) {
        if (message == null) return "";
        String safe = message.replaceAll("(?i)https?://[^\\s\"']+", "[url]");
        safe = safe.replaceAll("(?i)(cookie|authorization|token|access_token|sig|key)=([^&\\s]+)", "$1=[redacted]");
        return safe.length() > 280 ? safe.substring(0, 280) : safe;
    }

    private void logVkConsole(android.webkit.ConsoleMessage message) {
        if (message == null) return;
        String text = message.message();
        String sourceId = message.sourceId();
        String lower = text == null ? "" : text.toLowerCase(Locale.ROOT);
        boolean relevant = isVkDiagnosticUrl(sourceId) ||
            lower.contains("vk") || lower.contains("video") ||
            lower.contains("playback") || lower.contains("iframe");
        if (!relevant) return;
        android.util.Log.w("RuFilmVK", "JS " + message.messageLevel() +
            " " + safeVkMessage(text) + " source=" + safeVkTarget(sourceId) +
            " line=" + message.lineNumber());
    }

'''
anchor = "    // ABP-style network filtering; the cinema origin and ordinary media requests are exempt."
replace_once(anchor, helpers + anchor, "diagnostic helper insertion")

old_console = '''            @Override public boolean onConsoleMessage(android.webkit.ConsoleMessage message) {
                android.util.Log.d("RuFilmTV", "JS " + message.message() + " @" + message.lineNumber());
                return true;
            }'''
new_console = '''            @Override public boolean onConsoleMessage(android.webkit.ConsoleMessage message) {
                logVkConsole(message);
                android.util.Log.d("RuFilmTV", "JS " + safeVkMessage(message.message()) + " @" + message.lineNumber());
                return true;
            }'''
replace_once(old_console, new_console, "console diagnostics")

old_intercept = '''            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request){
                captureMediaRequest(request);
                if (isAdFilteringEnabled() && request != null &&
                        isAdRequest(request.getUrl().toString()) &&
                        !isRuFilmMediaRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, request);
            }'''
new_intercept = '''            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request){
                captureMediaRequest(request);
                boolean blocked = isAdFilteringEnabled() && request != null &&
                    isAdRequest(request.getUrl().toString()) && !isRuFilmMediaRequest(request.getUrl().toString());
                logVkRequest(request, blocked);
                if (blocked) return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, request);
            }'''
if old_intercept in source:
    replace_once(old_intercept, new_intercept, "request interception diagnostics")
else:
    toggle_filter = '''                String requestUrl = request == null ? null : request.getUrl().toString();
                if (requestUrl != null && !isRuFilmMediaRequest(requestUrl) &&
                        (isAdFilteringEnabled() && (isKnownAdRequest(requestUrl) || isAdRequest(requestUrl))))
                    return emptyBlockedResponse();'''
    toggle_with_log = '''                String requestUrl = request == null ? null : request.getUrl().toString();
                boolean blocked = requestUrl != null && !isRuFilmMediaRequest(requestUrl) &&
                    (isAdFilteringEnabled() && (isKnownAdRequest(requestUrl) || isAdRequest(requestUrl)));
                logVkRequest(request, blocked);
                if (blocked) return emptyBlockedResponse();'''
    replace_once(toggle_filter, toggle_with_log, "ad-filter toggle request diagnostics")

old_legacy = '''            @SuppressWarnings("deprecation")
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, String url){
                if (!isRuFilmMediaRequest(url) &&
                        (isAdFilteringEnabled() && (isKnownAdRequest(url) || isAdRequest(url))))
                    return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, url);
            }'''
new_legacy = '''            @SuppressWarnings("deprecation")
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, String url){
                boolean blocked = !isRuFilmMediaRequest(url) &&
                    (isAdFilteringEnabled() && (isKnownAdRequest(url) || isAdRequest(url)));
                logVkUrl(url, "GET", blocked, "legacy-api");
                if (blocked) return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, url);
            }'''
replace_once(old_legacy, new_legacy, "legacy request interception diagnostics")

old_error = '''            @Override public void onReceivedError(WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
                if (request != null && request.isForMainFrame()) {'''
new_error = '''            @Override public void onReceivedError(WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
                if (request != null && request.getUrl() != null && isVkDiagnosticUrl(request.getUrl().toString())) {
                    android.util.Log.e("RuFilmVK", "LOAD_ERROR " + safeVkTarget(request.getUrl().toString()) +
                        " code=" + error.getErrorCode() + " description=" + safeVkMessage(String.valueOf(error.getDescription())) +
                        " mainFrame=" + request.isForMainFrame());
                }
                if (request != null && request.isForMainFrame()) {'''
replace_once(old_error, new_error, "resource load error diagnostics")

http_anchor = '''            @Override public void onPageFinished(WebView view,String url){'''
http_methods = '''            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request != null && request.getUrl() != null && isVkDiagnosticUrl(request.getUrl().toString())) {
                    android.util.Log.e("RuFilmVK", "HTTP_ERROR " + safeVkTarget(request.getUrl().toString()) +
                        " status=" + response.getStatusCode() + " reason=" + safeVkMessage(response.getReasonPhrase()) +
                        " mainFrame=" + request.isForMainFrame());
                }
                super.onReceivedHttpError(view, request, response);
            }
            @Override public void onReceivedSslError(WebView view, android.webkit.SslErrorHandler handler, android.net.http.SslError error) {
                if (error != null && error.getUrl() != null && isVkDiagnosticUrl(error.getUrl())) {
                    android.util.Log.e("RuFilmVK", "SSL_ERROR " + safeVkTarget(error.getUrl()) +
                        " primary=" + error.getPrimaryError());
                }
                handler.cancel(); // Never bypass certificate validation.
            }
'''
replace_once(http_anchor, http_methods + http_anchor, "HTTP and SSL diagnostics")


# Mouse/pointer diagnostics for the inline WebView player (including Tanix W2).
mouse_helpers = r'''
    private long lastVkPointerMoveLogAt = 0L;

    private void logVkPointerEvent(String source, android.view.MotionEvent event, android.view.View target) {
        if (event == null) return;
        int action = event.getActionMasked();
        int tool = event.getPointerCount() > 0 ? event.getToolType(0) : -1;
        boolean mouse = tool == android.view.MotionEvent.TOOL_TYPE_MOUSE ||
            tool == android.view.MotionEvent.TOOL_TYPE_STYLUS ||
            (event.getSource() & android.view.InputDevice.SOURCE_MOUSE) == android.view.InputDevice.SOURCE_MOUSE;
        boolean pointerAction = action == android.view.MotionEvent.ACTION_HOVER_ENTER ||
            action == android.view.MotionEvent.ACTION_HOVER_MOVE ||
            action == android.view.MotionEvent.ACTION_HOVER_EXIT ||
            action == android.view.MotionEvent.ACTION_BUTTON_PRESS ||
            action == android.view.MotionEvent.ACTION_BUTTON_RELEASE ||
            action == android.view.MotionEvent.ACTION_SCROLL;
        if (!mouse && !pointerAction) return;
        long now = android.os.SystemClock.uptimeMillis();
        if (action == android.view.MotionEvent.ACTION_HOVER_MOVE && now - lastVkPointerMoveLogAt < 250L) return;
        if (action == android.view.MotionEvent.ACTION_HOVER_MOVE) lastVkPointerMoveLogAt = now;
        float x = event.getX(), y = event.getY();
        float rawX = event.getRawX(), rawY = event.getRawY();
        int width = target == null ? -1 : target.getWidth();
        int height = target == null ? -1 : target.getHeight();
        android.util.Log.i("RuFilmMouse", source + " action=" + action +
            " tool=" + tool + " source=0x" + Integer.toHexString(event.getSource()) +
            " buttons=0x" + Integer.toHexString(event.getButtonState()) +
            " xy=" + Math.round(x) + "," + Math.round(y) +
            " raw=" + Math.round(rawX) + "," + Math.round(rawY) +
            " view=" + width + "x" + height +
            " device=" + event.getDeviceId());
    }
'''
anchor = '    // VK WebView diagnostics. Never log query strings, cookies, auth headers or request values.'
if 'private void logVkPointerEvent(' not in source:
    replace_once(anchor, mouse_helpers + '\n' + anchor, 'mouse diagnostic helper')

# Attach the WebView listener immediately after WebView creation/configuration.
# Older project snapshots do not install a touch listener at all, so do not
# require a pre-existing listener anchor.
if 'logVkPointerEvent("WEBVIEW_TOUCH"' not in source:
    web_anchor = '        android.webkit.CookieManager.getInstance().setAcceptCookie(true);'
    web_listener = '''        web.setOnTouchListener((v, event) -> {
            logVkPointerEvent("WEBVIEW_TOUCH", event, v);
            if (event.getAction() == MotionEvent.ACTION_DOWN) {
                v.requestFocus();
                v.requestFocusFromTouch();
            }
            return false;
        });
'''
    replace_once(web_anchor, web_listener + web_anchor, "WebView initialization for mouse diagnostics")

def add_dispatch_log(method_name, log_line):
    global source
    if log_line in source:
        return
    pattern = re.compile(r'(    @Override\s+public boolean\s+' + method_name + r'\s*\([^)]*\)\s*\{)')
    match = pattern.search(source)
    if match:
        source = source[:match.end()] + '\n        ' + log_line + source[match.end():]
        return
    # Older base projects have no dispatch override; add one before onBackPressed.
    anchor = '    @Override public void onBackPressed()'
    if anchor not in source:
        raise SystemExit("Required Activity insertion point not found for " + method_name)
    if method_name == "dispatchTouchEvent":
        body = '''    @Override public boolean dispatchTouchEvent(android.view.MotionEvent event) {
        logVkPointerEvent("ACTIVITY_TOUCH", event, web);
        return super.dispatchTouchEvent(event);
    }

'''
    else:
        body = '''    @Override public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        logVkPointerEvent("ACTIVITY_GENERIC", event, web);
        return super.dispatchGenericMotionEvent(event);
    }

'''
    source = source.replace(anchor, body + anchor, 1)

add_dispatch_log("dispatchTouchEvent", 'logVkPointerEvent("ACTIVITY_TOUCH", event, web);')
add_dispatch_log("dispatchGenericMotionEvent", 'logVkPointerEvent("ACTIVITY_GENERIC", event, web);')

path.write_text(source, encoding="utf-8")
print("Added privacy-safe VK diagnostics to", path)
