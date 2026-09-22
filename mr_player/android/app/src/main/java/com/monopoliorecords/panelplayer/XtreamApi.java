package com.monopoliorecords.panelplayer;

import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public final class XtreamApi {
    public static List<Channel> liveChannels(String server, String user, String pass) throws Exception {
        String base = server.endsWith("/") ? server.substring(0, server.length()-1) : server;
        String q = base + "/player_api.php?username=" + Uri.encode(user) + "&password=" + Uri.encode(pass) + "&action=get_live_streams";
        HttpURLConnection c=(HttpURLConnection)new URL(q).openConnection();
        c.setConnectTimeout(12000); c.setReadTimeout(20000); c.setRequestProperty("Accept","application/json");
        int code=c.getResponseCode();
        if(code<200||code>=300) throw new Exception("Servidor IPTV respondió HTTP "+code);
        StringBuilder sb=new StringBuilder();
        try(BufferedReader br=new BufferedReader(new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8))){String line;while((line=br.readLine())!=null)sb.append(line);} finally {c.disconnect();}
        JSONArray a=new JSONArray(sb.toString()); List<Channel> out=new ArrayList<>();
        for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i); if(x==null)continue; String id=String.valueOf(x.opt("stream_id")); String name=x.optString("name","Canal "+id); if(!"null".equals(id)&&!id.isEmpty())out.add(new Channel(name,id));}
        return out;
    }

    public static String liveUrl(String server,String user,String pass,String streamId){
        String base=server.endsWith("/")?server.substring(0,server.length()-1):server;
        return base+"/live/"+Uri.encode(user)+"/"+Uri.encode(pass)+"/"+Uri.encode(streamId)+".m3u8";
    }
}
