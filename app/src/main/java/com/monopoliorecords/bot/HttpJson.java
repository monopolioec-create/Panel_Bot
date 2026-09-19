package com.monopoliorecords.bot;

import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.Map;

public final class HttpJson {
    public static class Result {
        public final int code; public final String body;
        Result(int c, String b) { code=c; body=b; }
        public JSONObject json() { try { return new JSONObject(body); } catch(Exception e) { return new JSONObject(); } }
        public boolean ok() { return code >= 200 && code < 300; }
    }
    private HttpJson() {}
    public static Result call(String method, String url, JSONObject body, Map<String,String> headers) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();
        c.setRequestMethod(method); c.setConnectTimeout(10000); c.setReadTimeout(30000);
        c.setRequestProperty("Accept","application/json");
        if(headers!=null) for(Map.Entry<String,String> e:headers.entrySet()) c.setRequestProperty(e.getKey(),e.getValue());
        if(body!=null){
            c.setDoOutput(true); c.setRequestProperty("Content-Type","application/json; charset=utf-8");
            try(OutputStream o=c.getOutputStream()){ o.write(body.toString().getBytes(StandardCharsets.UTF_8)); }
        }
        int code=c.getResponseCode(); InputStream in=code>=400?c.getErrorStream():c.getInputStream();
        StringBuilder s=new StringBuilder(); if(in!=null){ try(BufferedReader r=new BufferedReader(new InputStreamReader(in,StandardCharsets.UTF_8))){ String l; while((l=r.readLine())!=null)s.append(l).append('\n'); }}
        c.disconnect(); return new Result(code,s.toString().trim());
    }
}
