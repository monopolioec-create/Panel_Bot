package com.monopoliorecords.panelplayer;

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
        public String status;
        public String server;
        public String username;
        public String password;
    }

    public static String register(DeviceIdentity d, String oldToken) throws Exception {
        JSONObject body = new JSONObject();
        body.put("device_key", d.deviceKey);
        body.put("mac", d.mac);
        body.put("android_id", d.androidId);
        body.put("device_name", d.name);
        body.put("model", d.model);
        body.put("app_version", BuildConfig.VERSION_NAME);
        JSONObject r = request("POST", BuildConfig.PANEL_API_URL + "?action=register", body, null);
        if (!r.optBoolean("ok")) throw new Exception(r.optString("error", "register_failed"));
        return r.getString("device_token");
    }

    public static Config getConfig(DeviceIdentity d, String token) throws Exception {
        String url = BuildConfig.PANEL_API_URL + "?action=config&device_key=" + java.net.URLEncoder.encode(d.deviceKey, "UTF-8");
        JSONObject r = request("GET", url, null, token);
        if (!r.optBoolean("ok")) throw new Exception(r.optString("error", "config_failed"));
        Config c = new Config();
        c.status = r.optString("status", "pending");
        JSONObject x = r.optJSONObject("config");
        if (x != null) {
            c.server = x.optString("server", "");
            c.username = x.optString("username", "");
            c.password = x.optString("password", "");
        }
        return c;
    }

    private static JSONObject request(String method, String urlString, JSONObject body, String token) throws Exception {
        URL url = new URL(urlString);
        if (!"https".equalsIgnoreCase(url.getProtocol())) throw new Exception("El panel debe usar HTTPS");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(12000);
        c.setReadTimeout(12000);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("X-App-Key", BuildConfig.PANEL_APP_KEY);
        if (token != null && !token.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + token);
        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] data = body.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = c.getOutputStream()) { out.write(data); }
        }
        int code = c.getResponseCode();
        InputStream in = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        StringBuilder sb = new StringBuilder();
        if (in != null) try (BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line; while ((line = br.readLine()) != null) sb.append(line);
        }
        c.disconnect();
        if (sb.length() == 0) throw new Exception("Respuesta vacía del panel (HTTP " + code + ")");
        return new JSONObject(sb.toString());
    }
}
