package com.monopoliorecords.bot;

import android.util.Base64;
import java.io.*;
import java.net.*;

public final class MediaUtil {
    private MediaUtil(){}
    public static String asDataUri(String url) throws Exception {
        URLConnection c=new URL(url).openConnection(); c.setConnectTimeout(10000); c.setReadTimeout(30000);
        String type=c.getContentType(); if(type==null) type="application/octet-stream";
        ByteArrayOutputStream o=new ByteArrayOutputStream();
        try(InputStream in=c.getInputStream()){ byte[] b=new byte[65536]; int n,total=0; while((n=in.read(b))>0){ total+=n; if(total>40*1024*1024) throw new IOException("Archivo superior a 40 MB"); o.write(b,0,n); } }
        return "data:"+type+";base64,"+Base64.encodeToString(o.toByteArray(),Base64.NO_WRAP);
    }
}
