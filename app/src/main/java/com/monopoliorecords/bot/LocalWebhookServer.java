package com.monopoliorecords.bot;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

public class LocalWebhookServer {
    private final RuleEngine engine; private ServerSocket socket; private volatile boolean run;
    public LocalWebhookServer(RuleEngine e){engine=e;}
    public void start()throws Exception{if(run)return;socket=new ServerSocket();socket.bind(new InetSocketAddress("127.0.0.1",1821));run=true;new Thread(this::loop,"mr-webhook").start();}
    public void stop(){run=false;try{if(socket!=null)socket.close();}catch(Exception ignored){}}
    private void loop(){while(run){try{Socket s=socket.accept();new Thread(()->handle(s)).start();}catch(Exception e){if(run)android.util.Log.e("Webhook","accept",e);}}}
    private void handle(Socket s){try(BufferedReader r=new BufferedReader(new InputStreamReader(s.getInputStream(),StandardCharsets.UTF_8));OutputStream o=s.getOutputStream()){
        int len=0;String line;while((line=r.readLine())!=null&&!line.isEmpty()){String l=line.toLowerCase();if(l.startsWith("content-length:"))len=Integer.parseInt(line.substring(15).trim());}
        char[] b=new char[len];int n=0,x;while(n<len&&(x=r.read(b,n,len-n))>0)n+=x;String body=new String(b,0,n);o.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}".getBytes(StandardCharsets.UTF_8));o.flush();new Thread(()->engine.onWebhook(body)).start();
    }catch(Exception e){android.util.Log.e("Webhook","handle",e);}finally{try{s.close();}catch(Exception ignored){}}}
}
