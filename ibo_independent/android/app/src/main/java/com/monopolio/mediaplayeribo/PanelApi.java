package com.monopolio.mediaplayeribo;

import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class PanelApi {
    public static final class Config {
        public String status = "pending";
        public String playlistName = "TV DIGITAL";
        public String server = "";
        public String username = "";
        public String password = "";
    }

    private static String apiUrl(String action) {
        return BuildConfig.PANEL_API_URL + "?client=1&action=" + action;
    }

    public static String register(DeviceIdentity d) throws Exception {
        JSONObject j = new JSONObject();
        j.put("device_key", d.deviceKey);
        j.put("mac", d.mac);
        j.put("android_id", d.androidId);
        j.put("manufacturer", d.manufacturer);
        j.put("model", d.model);
        j.put("app_version", BuildConfig.VERSION_NAME);

        JSONObject r = request("POST", apiUrl("register"), j, null);
        if (!r.optBoolean("ok")) throw new Exception(r.optString("error", "register_failed"));
        return r.getString("device_token");
    }

    public static Config config(DeviceIdentity d, String token) throws Exception {
        String u = apiUrl("config") + "&device_key=" + java.net.URLEncoder.encode(d.deviceKey, "UTF-8");
        JSONObject r = request("GET", u, null, token);
        if (!r.optBoolean("ok")) throw new Exception(r.optString("error", "config_failed"));
        Config c = new Config();
        c.status = r.optString("status", "pending");
        JSONObject x = r.optJSONObject("config");
        if (x != null) {
            c.playlistName = x.optString("playlist_name", "TV DIGITAL");
            c.server = x.optString("server", "");
            c.username = x.optString("username", "");
            c.password = x.optString("password", "");
        }
        return c;
    }

    private static JSONObject request(String method, String urlString, JSONObject body, String token) throws Exception {
        URL url = new URL(urlString);
        if (!"https".equalsIgnoreCase(url.getProtocol())) throw new Exception("El panel requiere HTTPS");

        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(12000);
        c.setReadTimeout(15000);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("X-App-Key", BuildConfig.PANEL_APP_KEY);
        if (token != null && !token.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + token);

        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] data = body.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream os = c.getOutputStream()) { os.write(data); }
        }

        int code = c.getResponseCode();
        InputStream in = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        StringBuilder sb = new StringBuilder();
        if (in != null) {
            try (BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
            }
        }
        c.disconnect();

        String raw = sb.toString().trim();
        if (!raw.startsWith("{")) throw new Exception("El panel no devolvió JSON (HTTP " + code + ")");
        return new JSONObject(raw);
    }
}
