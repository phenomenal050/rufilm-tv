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
import java.util.Collections;
import java.util.Set;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.net.HttpURLConnection;

/**
 * Beta.18: resilient HLS/DASH bridge for external players, including range-aware segment forwarding.
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
    private static final Set<Socket> activeClients = Collections.newSetFromMap(new ConcurrentHashMap<Socket, Boolean>());

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

    /**
     * Ends the current Media3 proxy session. Closing active loopback clients
     * prevents a previous signed audio/video request from leaking into the
     * next playback session.
     */
    public static synchronized void stop() {
        ServerSocket oldServer = server;
        server = null;
        Thread oldAcceptThread = acceptThread;
        acceptThread = null;
        sessionToken = null;
        localPort = 0;
        sessionHeaders.clear();
        for (Socket client : activeClients.toArray(new Socket[0])) {
            try { client.close(); } catch (IOException ignored) { }
        }
        activeClients.clear();
        if (oldServer != null) {
            try { oldServer.close(); } catch (IOException ignored) { }
        }
        if (oldAcceptThread != null) oldAcceptThread.interrupt();
        Log.i(TAG, "Media proxy session stopped; server, headers and active clients cleared");
    }

    private static void acceptLoop(ServerSocket socket) {
        while (!socket.isClosed()) {
            try {
                Socket client = socket.accept();
                activeClients.add(client);
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
            if ("OPTIONS".equals(method)) {
                writeAscii(output, "HTTP/1.1 204 No Content\r\n");
                writeAscii(output, "Access-Control-Allow-Origin: *\r\n");
                writeAscii(output, "Access-Control-Allow-Methods: GET, HEAD, OPTIONS\r\n");
                writeAscii(output, "Access-Control-Allow-Headers: Range, If-Range, Accept, Origin, Referer\r\n");
                writeAscii(output, "Access-Control-Max-Age: 86400\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
                output.flush();
                return;
            }
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
            // OK/VK CDN delivers signed MP4 tracks as byte windows encoded in
            // the URL query. Present those windows as one continuous file to Media3.
            if ("GET".equals(method) && isOkChunkUrl(target) &&
                    handleOkChunkedMedia(target, incoming, output)) return;

            upstream = (HttpURLConnection) new URL(target).openConnection();
            upstream.setInstanceFollowRedirects(true);
            upstream.setConnectTimeout(20000);
            upstream.setReadTimeout(90000);
            upstream.setUseCaches(false);
            upstream.setRequestMethod(method);
            upstream.setRequestProperty("Connection", "close");
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
            // Do not apply byte ranges to rewritten manifests: their byte offsets and
            // lengths change when child URLs are routed through this bridge.
            boolean targetLooksLikeManifest = target.toLowerCase(Locale.ROOT).contains(".m3u8") ||
                    target.toLowerCase(Locale.ROOT).contains(".mpd");
            for (String key : new String[]{"range", "if-range", "accept", "accept-language"}) {
                String value = incoming.get(key);
                if (value != null && !(targetLooksLikeManifest &&
                        ("range".equals(key) || "if-range".equals(key))))
                    upstream.setRequestProperty(key, value);
            }
            upstream.setRequestProperty("Accept-Encoding", "identity");

            int status = upstream.getResponseCode();
            String type = upstream.getContentType();
            try {
                URL effective = upstream.getURL();
                String host = effective == null ? "upstream" : effective.getHost();
                Log.i(TAG, method + " " + host + " -> HTTP " + status +
                        (type == null ? "" : " (" + type + ")"));
                if (status >= 400) {
                    String refererHost = "none";
                    String originHost = "none";
                    try {
                        String referer = upstream.getRequestProperty("Referer");
                        if (referer != null) refererHost = new URL(referer).getHost();
                    } catch (Exception ignored) { }
                    try {
                        String origin = upstream.getRequestProperty("Origin");
                        if (origin != null) originHost = new URL(origin).getHost();
                    } catch (Exception ignored) { }
                    Log.e(TAG, "Upstream rejected request: HTTP " + status +
                            " host=" + host + " refererHost=" + refererHost +
                            " originHost=" + originHost + " method=" + method);
                }
            } catch (Exception ignored) { }
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
            if (manifestBytes == null) {
                copyHeader(upstream, output, "Content-Range");
                copyHeader(upstream, output, "Accept-Ranges");
            }
            copyHeader(upstream, output, "ETag");
            copyHeader(upstream, output, "Last-Modified");
            copyHeader(upstream, output, "Cache-Control");
            copyHeader(upstream, output, "Expires");
            copyHeader(upstream, output, "Content-Disposition");
            if (manifestBytes != null) {
                writeAscii(output, "Content-Length: " + manifestBytes.length + "\r\n");
                writeAscii(output, "Cache-Control: no-store\r\n");
                writeAscii(output, "Access-Control-Allow-Origin: *\r\n");
                writeAscii(output, "Connection: close\r\n\r\n");
                output.write(manifestBytes);
            } else {
                String lengthHeader = upstream.getHeaderField("Content-Length");
                if (lengthHeader != null && !lengthHeader.isEmpty())
                    writeAscii(output, "Content-Length: " + lengthHeader + "\r\n");
                else {
                    int length = upstream.getContentLength();
                    if (length >= 0) writeAscii(output, "Content-Length: " + length + "\r\n");
                }
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
            activeClients.remove(client);
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


    private static final long OK_CHUNK_SIZE = 1024L * 1024L;
    private static boolean isOkChunkUrl(String target) {
        try {
            Uri u = Uri.parse(target); String host = u.getHost();
            return host != null && host.toLowerCase(Locale.ROOT).endsWith(".vkuser.net") &&
                u.getQueryParameter("bytes") != null && u.getQueryParameter("sig") != null &&
                u.getQueryParameter("id") != null &&
                ("2".equals(u.getQueryParameter("type")) || "3".equals(u.getQueryParameter("type")) || "4".equals(u.getQueryParameter("type")));
        } catch (Exception ignored) { return false; }
    }
    private static String withOkBytes(String target, long start, long end) throws IOException {
        Matcher m = Pattern.compile("([?&]bytes=)[^&]*").matcher(target);
        if (!m.find()) throw new IOException("OK CDN URL has no bytes parameter");
        return m.replaceFirst(Matcher.quoteReplacement(m.group(1) + start + "-" + end));
    }
    private static HttpURLConnection openOkChunk(String target, long start, long end) throws IOException {
        String chunkUrl = withOkBytes(target, start, end);
        HttpURLConnection c = (HttpURLConnection)new URL(chunkUrl).openConnection();
        c.setInstanceFollowRedirects(true); c.setConnectTimeout(20000); c.setReadTimeout(90000);
        c.setUseCaches(false); c.setRequestMethod("GET");
        c.setRequestProperty("Connection", "close"); c.setRequestProperty("Accept-Encoding", "identity");
        for (Map.Entry<String,String> h : sessionHeaders.entrySet()) {
            String k=h.getKey(); if(k==null||h.getValue()==null)continue;
            String l=k.toLowerCase(Locale.ROOT);
            if(l.equals("host")||l.equals("connection")||l.equals("content-length")||
               l.equals("accept-encoding")||l.equals("cookie")||l.equals("range"))continue;
            c.setRequestProperty(k,h.getValue());
        }
        try {
            String cookie=CookieManager.getInstance().getCookie(chunkUrl);
            if(cookie!=null&&!cookie.isEmpty())c.setRequestProperty("Cookie",cookie);
            else for(Map.Entry<String,String> h:sessionHeaders.entrySet())
                if(h.getKey()!=null&&"cookie".equalsIgnoreCase(h.getKey()))c.setRequestProperty("Cookie",h.getValue());
        } catch(Exception ignored) {}
        return c;
    }
    private static long[] parseOkContentRange(String value) {
        if(value==null)return null;
        Matcher m=Pattern.compile("(?i)bytes\\s+(\\d+)-(\\d+)/(\\d+)").matcher(value.trim());
        if(!m.matches())return null;
        try{return new long[]{Long.parseLong(m.group(1)),Long.parseLong(m.group(2)),Long.parseLong(m.group(3))};}
        catch(Exception ignored){return null;}
    }
    private static void copyOkBytes(InputStream in,OutputStream out,long count)throws IOException {
        byte[] buffer=new byte[64*1024]; long left=count;
        while(left>0){int n=in.read(buffer,0,(int)Math.min(buffer.length,left));
            if(n<0)throw new IOException("OK CDN ended a byte window early");out.write(buffer,0,n);left-=n;}
    }
    private static boolean handleOkChunkedMedia(String target,Map<String,String> incoming,OutputStream output)throws IOException {
        long start=0L,end=-1L; String range=incoming.get("range");
        if(range!=null){Matcher rm=Pattern.compile("(?i)bytes=(\\d+)-(\\d*)").matcher(range.trim());
            if(!rm.matches())return false;
            try{start=Long.parseLong(rm.group(1));if(!rm.group(2).isEmpty())end=Long.parseLong(rm.group(2));}
            catch(Exception ignored){return false;}}
        HttpURLConnection current=null; boolean sent=false;
        try{
            long askEnd=end>=0?end:start+OK_CHUNK_SIZE-1L;
            current=openOkChunk(target,start,askEnd); int code=current.getResponseCode();
            long[] win=parseOkContentRange(current.getHeaderField("Content-Range"));
            if(code<200||code>=300||win==null||win[0]!=start){current.disconnect();return false;}
            long total=win[2]; if(start>=total){current.disconnect();writeError(output,416,"Range Not Satisfiable");return true;}
            long finalEnd=end>=0?Math.min(end,total-1L):total-1L;
            String type=current.getContentType(); int localStatus=range==null?200:206;
            writeAscii(output,"HTTP/1.1 "+localStatus+(localStatus==206?" Partial Content":" OK")+"\r\n");
            if(type!=null)writeAscii(output,"Content-Type: "+type+"\r\n");
            writeAscii(output,"Accept-Ranges: bytes\r\nContent-Length: "+(finalEnd-start+1L)+"\r\n");
            if(localStatus==206)writeAscii(output,"Content-Range: bytes "+start+"-"+finalEnd+"/"+total+"\r\n");
            writeAscii(output,"Cache-Control: no-store\r\nConnection: close\r\n\r\n"); output.flush(); sent=true;
            long cursor=start;
            while(cursor<=finalEnd){
                long chunkEnd=Math.min(win[1],finalEnd); InputStream body=current.getInputStream();
                try{copyOkBytes(body,output,chunkEnd-cursor+1L);}
                finally{try{body.close();}catch(Exception ignored){}current.disconnect();}
                cursor=chunkEnd+1L;if(cursor>finalEnd)break;
                long nextEnd=Math.min(cursor+OK_CHUNK_SIZE-1L,finalEnd);
                current=openOkChunk(target,cursor,nextEnd);int nextCode=current.getResponseCode();
                win=parseOkContentRange(current.getHeaderField("Content-Range"));
                if(nextCode<200||nextCode>=300||win==null||win[0]!=cursor)
                    throw new IOException("OK CDN rejected continuation at byte "+cursor+" HTTP "+nextCode);
            }
            output.flush();Log.i(TAG,"OK CDN virtual stream complete bytes="+(finalEnd-start+1L));
            return true;
        }catch(Exception e){
            if(sent){Log.w(TAG,"OK CDN range continuation failed",e);try{output.flush();}catch(Exception ignored){}return true;}
            if(current!=null)current.disconnect();
            if(e instanceof IOException)throw(IOException)e;throw new IOException("OK CDN bridge failed",e);
        }finally{if(current!=null)current.disconnect();}
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
