package tv.rufilm.app;

import android.net.Uri;
import android.webkit.CookieManager;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URL;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.net.HttpURLConnection;

/**
 * Loopback-only authenticated HTTP bridge for external video players.
 * It forwards every HLS/DASH child request with the WebView session headers.
 */
public final class LocalStreamProxy {
    private static final String TAG = "RuFilmTV-StreamProxy";
    private static final int MAX_MANIFEST_BYTES = 8 * 1024 * 1024;
    private static volatile ServerSocket server;
    private static volatile Thread acceptThread;
    private static volatile String sessionToken;
    private static volatile int localPort;
    private static volatile Map<String, String> sessionHeaders = new ConcurrentHashMap<>();

    private LocalStreamProxy() {}

    public static synchronized String start(String sourceUrl, Map<String, String> headers) throws IOException {
        if (sourceUrl == null || !(sourceUrl.startsWith("http://") || sourceUrl.startsWith("https://")))
            throw new IOException("Unsupported media URL");
        if (server == null || server.isClosed()) {
            ServerSocket socket = new ServerSocket(0, 24, InetAddress.getByName("127.0.0.1"));
            server = socket;
            localPort = socket.getLocalPort();
            sessionToken = UUID.randomUUID().toString().replace("-", "");
            acceptThread = new Thread(() -> acceptLoop(socket), "RuFilmTV-StreamProxy");
            acceptThread.setDaemon(true);
            acceptThread.start();
        }
        sessionHeaders = new ConcurrentHashMap<>();
        if (headers != null) sessionHeaders.putAll(headers);
        return makeProxyUrl(sourceUrl);
    }

    private static void acceptLoop(ServerSocket socket) {
        while (!socket.isClosed()) {
            try {
                Socket client = socket.accept();
                client.setSoTimeout(30000);
                Thread worker = new Thread(() -> handle(client), "RuFilmTV-ProxyClient");
                worker.setDaemon(true);
                worker.start();
            } catch (IOException e) {
                if (!socket.isClosed()) Log.w(TAG, "Accept failed", e);
            }
        }
    }

    private static void handle(Socket client) {
        HttpURLConnection upstream = null;
        try (Socket socket = client;
             BufferedInputStream input = new BufferedInputStream(socket.getInputStream());
             BufferedOutputStream output = new BufferedOutputStream(socket.getOutputStream())) {
            String requestLine = readLine(input);
            if (requestLine == null) return;
            String[] requestParts = requestLine.split(" ");
            if (requestParts.length < 2) { writeError(output, 400, "Bad Request"); return; }
            String method = requestParts[0].toUpperCase(Locale.ROOT);
            if (!"GET".equals(method) && !"HEAD".equals(method)) {
                writeError(output, 405, "Method Not Allowed"); return;
            }
            Map<String, String> incoming = new HashMap<>();
            String line;
            while ((line = readLine(input)) != null && !line.isEmpty()) {
                int colon = line.indexOf(':');
                if (colon > 0) incoming.put(line.substring(0, colon).trim().toLowerCase(Locale.ROOT),
                        line.substring(colon + 1).trim());
            }

            Uri local = Uri.parse("http://127.0.0.1:" + localPort + requestParts[1]);
            if (!("/" + sessionToken).equals(local.getPath())) {
                writeError(output, 404, "Not Found"); return;
            }
            String target = local.getQueryParameter("u");
            if (target == null || !(target.startsWith("http://") || target.startsWith("https://"))) {
                writeError(output, 400, "Invalid upstream URL"); return;
            }

            upstream = (HttpURLConnection) new URL(target).openConnection();
            upstream.setInstanceFollowRedirects(true);
            upstream.setConnectTimeout(20000);
            upstream.setReadTimeout(45000);
            upstream.setRequestMethod(method);
            for (Map.Entry<String, String> h : sessionHeaders.entrySet()) {
                String key = h.getKey();
                if (key == null || h.getValue() == null) continue;
                String lower = key.toLowerCase(Locale.ROOT);
                if (lower.equals("host") || lower.equals("connection") || lower.equals("content-length") ||
                        lower.equals("accept-encoding") || lower.equals("cookie")) continue;
                upstream.setRequestProperty(key, h.getValue());
            }
            // Cookies are host/path scoped: resolve them separately for each child playlist,
            // segment and encryption-key URL instead of reusing the manifest host's cookie.
            try {
                String cookie = CookieManager.getInstance().getCookie(target);
                if (cookie != null && !cookie.isEmpty()) upstream.setRequestProperty("Cookie", cookie);
                else {
                    for (Map.Entry<String, String> h : sessionHeaders.entrySet())
                        if (h.getKey() != null && "cookie".equalsIgnoreCase(h.getKey()))
                            upstream.setRequestProperty("Cookie", h.getValue());
                }
            } catch (Exception ignored) {
                for (Map.Entry<String, String> h : sessionHeaders.entrySet())
                    if (h.getKey() != null && "cookie".equalsIgnoreCase(h.getKey()))
                        upstream.setRequestProperty("Cookie", h.getValue());
            }
            for (String key : new String[]{"range", "if-range", "accept", "accept-language"}) {
                String value = incoming.get(key);
                if (value != null) upstream.setRequestProperty(key, value);
            }
            upstream.setRequestProperty("Accept-Encoding", "identity");

            int status = upstream.getResponseCode();
            String type = upstream.getContentType();
            String lowerTarget = target.toLowerCase(Locale.ROOT);
            boolean manifest = lowerTarget.contains(".m3u8") || lowerTarget.contains(".mpd") ||
                    (type != null && (type.toLowerCase(Locale.ROOT).contains("mpegurl") ||
                    type.toLowerCase(Locale.ROOT).contains("dash+xml")));

            byte[] manifestBytes = null;
            if ("GET".equals(method) && manifest && status >= 200 && status < 300) {
                try (InputStream body = upstream.getInputStream()) {
                    manifestBytes = readLimited(body, MAX_MANIFEST_BYTES);
                }
                String text = new String(manifestBytes, StandardCharsets.UTF_8);
                String effectiveUrl = upstream.getURL() == null ? target : upstream.getURL().toString();
                String rewritten = lowerTarget.contains(".mpd") || (type != null && type.toLowerCase(Locale.ROOT).contains("dash+xml"))
                        ? rewriteDash(text, effectiveUrl) : rewriteHls(text, effectiveUrl);
                manifestBytes = rewritten.getBytes(StandardCharsets.UTF_8);
            }

            String reason = status == 200 ? "OK" : status == 206 ? "Partial Content" :
                    status == 302 ? "Found" : status == 403 ? "Forbidden" :
                    status == 404 ? "Not Found" : "Upstream";
            writeAscii(output, "HTTP/1.1 " + status + " " + reason + "\r\n");
            if (type != null) writeAscii(output, "Content-Type: " + type + "\r\n");
            copyHeader(upstream, output, "Content-Range");
            copyHeader(upstream, output, "Accept-Ranges");
            copyHeader(upstream, output, "ETag");
            copyHeader(upstream, output, "Last-Modified");
            if (manifestBytes != null) {
                writeAscii(output, "Content-Length: " + manifestBytes.length + "\r\n");
                writeAscii(output, "Cache-Control: no-store\r\n");
                writeAscii(output, "Access-Control-Allow-Origin: *\r\n");
                writeAscii(output, "Connection: close\r\n\r\n");
                output.write(manifestBytes);
            } else {
                int length = upstream.getContentLength();
                if (length >= 0) writeAscii(output, "Content-Length: " + length + "\r\n");
                writeAscii(output, "Access-Control-Allow-Origin: *\r\n");
                writeAscii(output, "Connection: close\r\n\r\n");
                if ("GET".equals(method) && status >= 200 && status < 400) {
                    InputStream body = upstream.getInputStream();
                    byte[] buffer = new byte[64 * 1024];
                    int n;
                    while ((n = body.read(buffer)) != -1) output.write(buffer, 0, n);
                    body.close();
                } else if ("GET".equals(method)) {
                    InputStream body = upstream.getErrorStream();
                    if (body != null) {
                        byte[] buffer = new byte[8192];
                        int n;
                        while ((n = body.read(buffer)) != -1) output.write(buffer, 0, n);
                        body.close();
                    }
                }
            }
            output.flush();
        } catch (Exception e) {
            Log.w(TAG, "Proxy request failed", e);
            try { writeError(client.getOutputStream(), 502, "Bad Gateway"); } catch (Exception ignored) {}
        } finally {
            if (upstream != null) upstream.disconnect();
        }
    }

    private static String rewriteHls(String playlist, String baseUrl) throws Exception {
        StringBuilder out = new StringBuilder(playlist.length() + 256);
        String[] lines = playlist.split("\\r?\\n", -1);
        Pattern uriAttribute = Pattern.compile("URI=\"([^\"]+)\"");
        for (String line : lines) {
            String value = line;
            if (line.startsWith("#")) {
                Matcher matcher = uriAttribute.matcher(line);
                StringBuffer replaced = new StringBuffer();
                while (matcher.find()) {
                    String absolute = new URL(new URL(baseUrl), matcher.group(1)).toExternalForm();
                    matcher.appendReplacement(replaced, Matcher.quoteReplacement("URI=\"" + makeProxyUrl(absolute) + "\""));
                }
                matcher.appendTail(replaced);
                value = replaced.toString();
            } else if (!line.trim().isEmpty()) {
                value = makeProxyUrl(new URL(new URL(baseUrl), line.trim()).toExternalForm());
            }
            out.append(value).append('\n');
        }
        return out.toString();
    }

    private static String rewriteDash(String mpd, String baseUrl) throws Exception {
        Pattern base = Pattern.compile("(?is)(<BaseURL[^>]*>)(.*?)(</BaseURL>)");
        Matcher bm = base.matcher(mpd);
        StringBuffer b = new StringBuffer();
        while (bm.find()) {
            String absolute = new URL(new URL(baseUrl), bm.group(2).trim()).toExternalForm();
            bm.appendReplacement(b, Matcher.quoteReplacement(bm.group(1) + makeProxyUrl(absolute) + bm.group(3)));
        }
        bm.appendTail(b);
        String result = b.toString();

        Pattern attrs = Pattern.compile("(?i)(media|initialization|sourceURL)=\"([^\"]+)\"");
        Matcher am = attrs.matcher(result);
        StringBuffer a = new StringBuffer();
        while (am.find()) {
            String ref = am.group(2);
            if (ref.startsWith("http://") || ref.startsWith("https://")) continue;
            String absolute = new URL(new URL(baseUrl), ref).toExternalForm();
            am.appendReplacement(a, Matcher.quoteReplacement(am.group(1) + "=\"" + makeProxyUrl(absolute) + "\""));
        }
        am.appendTail(a);
        return a.toString();
    }

    private static String makeProxyUrl(String target) throws IOException {
        String encoded = URLEncoder.encode(target, "UTF-8")
                .replace("%24Number%24", "$Number$")
                .replace("%24Time%24", "$Time$")
                .replace("%24RepresentationID%24", "$RepresentationID$")
                .replace("%24Bandwidth%24", "$Bandwidth$")
                .replace("%24SubNumber%24", "$SubNumber$");
        return "http://127.0.0.1:" + localPort + "/" + sessionToken + "?u=" + encoded;
    }

    private static byte[] readLimited(InputStream in, int limit) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[16384];
        int total = 0, n;
        while ((n = in.read(buffer)) != -1) {
            total += n;
            if (total > limit) throw new IOException("Manifest too large");
            out.write(buffer, 0, n);
        }
        return out.toByteArray();
    }

    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int c;
        while ((c = in.read()) != -1) {
            if (c == '\n') break;
            if (c != '\r') out.write(c);
            if (out.size() > 16384) throw new IOException("HTTP header too long");
        }
        if (c == -1 && out.size() == 0) return null;
        return out.toString("UTF-8");
    }

    private static void copyHeader(HttpURLConnection source, OutputStream out, String name) throws IOException {
        String value = source.getHeaderField(name);
        if (value != null) writeAscii(out, name + ": " + value + "\r\n");
    }

    private static void writeError(OutputStream out, int code, String reason) throws IOException {
        byte[] body = (reason + "\n").getBytes(StandardCharsets.UTF_8);
        writeAscii(out, "HTTP/1.1 " + code + " " + reason + "\r\nContent-Type: text/plain; charset=utf-8\r\n");
        writeAscii(out, "Content-Length: " + body.length + "\r\nConnection: close\r\n\r\n");
        out.write(body);
        out.flush();
    }

    private static void writeAscii(OutputStream out, String text) throws IOException {
        out.write(text.getBytes(StandardCharsets.ISO_8859_1));
    }
}
