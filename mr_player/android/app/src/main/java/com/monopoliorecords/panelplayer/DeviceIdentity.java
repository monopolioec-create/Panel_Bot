package com.monopoliorecords.panelplayer;

import android.content.Context;
import android.os.Build;
import android.provider.Settings;

import java.net.NetworkInterface;
import java.security.MessageDigest;
import java.util.Collections;

public final class DeviceIdentity {
    public final String mac;
    public final String androidId;
    public final String deviceKey;
    public final String name;
    public final String model;

    private DeviceIdentity(String mac, String androidId, String deviceKey, String name, String model) {
        this.mac = mac;
        this.androidId = androidId;
        this.deviceKey = deviceKey;
        this.name = name;
        this.model = model;
    }

    public static DeviceIdentity read(Context context) {
        String mac = readMac();
        String androidId = Settings.Secure.getString(context.getContentResolver(), Settings.Secure.ANDROID_ID);
        if (androidId == null) androidId = "";
        String material = !mac.isEmpty() ? "mac:" + mac : "android:" + androidId;
        return new DeviceIdentity(mac, androidId, sha256(material), Build.MANUFACTURER, Build.MODEL);
    }

    private static String readMac() {
        try {
            for (NetworkInterface nif : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                String n = nif.getName() == null ? "" : nif.getName().toLowerCase();
                if (!(n.contains("wlan") || n.contains("wifi") || n.contains("eth"))) continue;
                byte[] hw = nif.getHardwareAddress();
                if (hw == null || hw.length == 0) continue;
                StringBuilder sb = new StringBuilder();
                for (byte b : hw) {
                    if (sb.length() > 0) sb.append(':');
                    sb.append(String.format("%02X", b));
                }
                String m = sb.toString();
                if (!m.equals("02:00:00:00:00:00") && !m.equals("00:00:00:00:00:00")) return m;
            }
        } catch (Exception ignored) { }
        return "";
    }

    private static String sha256(String input) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(input.getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
