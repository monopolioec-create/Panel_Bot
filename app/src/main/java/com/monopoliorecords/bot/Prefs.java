package com.monopoliorecords.bot;

import android.content.Context;
import android.content.SharedPreferences;
import java.security.SecureRandom;

public final class Prefs {
    private static final String NAME = "mrbot";
    private Prefs() {}
    public static SharedPreferences p(Context c) { return c.getSharedPreferences(NAME, Context.MODE_PRIVATE); }
    public static String get(Context c, String k, String d) { return p(c).getString(k, d); }
    public static boolean getBool(Context c, String k, boolean d) { return p(c).getBoolean(k, d); }
    public static void put(Context c, String k, String v) { p(c).edit().putString(k, v).apply(); }
    public static void putBool(Context c, String k, boolean v) { p(c).edit().putBoolean(k, v).apply(); }
    public static String randomHex(int bytes) {
        byte[] b = new byte[bytes]; new SecureRandom().nextBytes(b);
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format("%02x", x & 0xff));
        return s.toString();
    }
    public static String deviceUuid(Context c) {
        String v = get(c, "device_uuid", "");
        if (v.isEmpty()) { v = randomHex(16); put(c, "device_uuid", v); }
        return v;
    }
}
