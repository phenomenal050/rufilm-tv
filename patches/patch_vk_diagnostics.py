#!/usr/bin/env python3
"""Add privacy-safe VK/WebView diagnostics to the generated MainActivity.java."""
import pathlib
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
        String safe = message.replaceAll("(?i)https?://[^\\\\s\\\\\"']+", "[url]");
        safe = safe.replaceAll("(?i)(cookie|authorization|token|access_token|sig|key)=([^&\\\\s]+)", "$1=[redacted]");
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
                if (request != null && isAdRequest(request.getUrl().toString()))
                    return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, request);
            }'''
new_intercept = '''            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request){
                boolean blocked = request != null && isAdRequest(request.getUrl().toString());
                logVkRequest(request, blocked);
                if (blocked) return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, request);
            }'''
replace_once(old_intercept, new_intercept, "request interception diagnostics")

old_legacy = '''            @SuppressWarnings("deprecation")
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, String url){
                if (isAdRequest(url)) return emptyBlockedResponse();
                return super.shouldInterceptRequest(view, url);
            }'''
new_legacy = '''            @SuppressWarnings("deprecation")
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, String url){
                boolean blocked = isAdRequest(url);
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

path.write_text(source, encoding="utf-8")
print("Added privacy-safe VK diagnostics to", path)
