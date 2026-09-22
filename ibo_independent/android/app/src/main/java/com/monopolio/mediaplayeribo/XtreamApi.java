package com.monopolio.mediaplayeribo;

import android.net.Uri;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public final class XtreamApi {
    public static final class Item {
        public final String name, id, ext, kind;
        public Item(String name, String id, String ext, String kind) { this.name=name; this.id=id; this.ext=ext; this.kind=kind; }
        @Override public String toString() { return name; }
    }

    private static String base(String server) {
        String s = server == null ? "" : server.trim();
        while (s.endsWith("/")) s = s.substring(0, s.length()-1);
        return s;
    }

    private static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(url).openConnection();
        c.setConnectTimeout(12000); c.setReadTimeout(25000);
        c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("User-Agent", "MediaPlayerIbo/1.0");
        int code = c.getResponseCode();
        InputStream input = code>=200 && code<300 ? c.getInputStream() : c.getErrorStream();
        StringBuilder sb = new StringBuilder();
        if (input != null) try (BufferedReader br = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line; while ((line=br.readLine())!=null) sb.append(line);
        }
        c.disconnect();
        if (code < 200 || code >= 300) throw new Exception("Servidor IPTV HTTP " + code);
        return sb.toString();
    }

    private static String api(PanelApi.Config c, String action) {
        return base(c.server) + "/player_api.php?username=" + Uri.encode(c.username) + "&password=" + Uri.encode(c.password) + "&action=" + action;
    }

    public static List<Item> live(PanelApi.Config c) throws Exception {
        JSONArray a = new JSONArray(get(api(c, "get_live_streams"))); List<Item> out = new ArrayList<>();
        for (int i=0;i<a.length();i++) { JSONObject x=a.optJSONObject(i); if(x==null)continue; String id=String.valueOf(x.opt("stream_id")); if("null".equals(id)||id.isEmpty())continue; out.add(new Item(x.optString("name","Canal "+id),id,"ts","live")); }
        return out;
    }

    public static List<Item> movies(PanelApi.Config c) throws Exception {
        JSONArray a = new JSONArray(get(api(c, "get_vod_streams"))); List<Item> out = new ArrayList<>();
        for (int i=0;i<a.length();i++) { JSONObject x=a.optJSONObject(i); if(x==null)continue; String id=String.valueOf(x.opt("stream_id")); if("null".equals(id)||id.isEmpty())continue; out.add(new Item(x.optString("name","Película "+id),id,x.optString("container_extension","mp4"),"movie")); }
        return out;
    }

    public static List<Item> series(PanelApi.Config c) throws Exception {
        JSONArray a = new JSONArray(get(api(c, "get_series"))); List<Item> out = new ArrayList<>();
        for (int i=0;i<a.length();i++) { JSONObject x=a.optJSONObject(i); if(x==null)continue; String id=String.valueOf(x.opt("series_id")); if("null".equals(id)||id.isEmpty())continue; out.add(new Item(x.optString("name","Serie "+id),id,"","series")); }
        return out;
    }

    public static List<Item> episodes(PanelApi.Config c, String seriesId) throws Exception {
        JSONObject root = new JSONObject(get(api(c, "get_series_info") + "&series_id=" + Uri.encode(seriesId)));
        JSONObject eps = root.optJSONObject("episodes"); List<Item> out = new ArrayList<>(); if (eps == null) return out;
        Iterator<String> keys = eps.keys();
        while(keys.hasNext()) { String season=keys.next(); JSONArray arr=eps.optJSONArray(season); if(arr==null)continue; for(int i=0;i<arr.length();i++){JSONObject x=arr.optJSONObject(i);if(x==null)continue;String id=String.valueOf(x.opt("id"));if("null".equals(id)||id.isEmpty())continue;out.add(new Item("T"+season+" · "+x.optString("title","Episodio "+(i+1)),id,x.optString("container_extension","mp4"),"series_episode"));}}
        return out;
    }

    public static String playback(PanelApi.Config c, Item item) {
        String b=base(c.server),u=Uri.encode(c.username),p=Uri.encode(c.password),id=Uri.encode(item.id);
        if("movie".equals(item.kind)) return b+"/movie/"+u+"/"+p+"/"+id+"."+(item.ext.isEmpty()?"mp4":item.ext);
        if("series_episode".equals(item.kind)) return b+"/series/"+u+"/"+p+"/"+id+"."+(item.ext.isEmpty()?"mp4":item.ext);
        return b+"/live/"+u+"/"+p+"/"+id+".ts";
    }
}
