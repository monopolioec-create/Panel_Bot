package com.monopoliorecords.bot;

import android.content.Context;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.InetAddress;
import java.util.*;

public class WuzApiManager {
    private final Context c; private Process process; private File work;
    public WuzApiManager(Context c){ this.c=c.getApplicationContext(); }

    public synchronized void start() throws Exception {
        if(process!=null && process.isAlive()) return;
        work=StorageBootstrap.prepare(c);
        String bin=c.getApplicationInfo().nativeLibraryDir+"/libwuzapi.so";
        ProcessBuilder pb=new ProcessBuilder(bin,"-skipmedia","-logtype","json","-address","127.0.0.1","-port","8080","-osname","Monopoly Records","-datadir",work.getAbsolutePath());
        pb.directory(work); pb.redirectErrorStream(true);
        Map<String,String> e=pb.environment();
        String admin=Prefs.get(c,"wuz_admin",""); if(admin.isEmpty()){admin=Prefs.randomHex(16);Prefs.put(c,"wuz_admin",admin);}
        e.put("WUZAPI_ADMIN_TOKEN",admin);
        e.put("WUZAPI_GLOBAL_WEBHOOK","http://127.0.0.1:1821");
        e.put("WEBHOOK_FORMAT","json"); e.put("WUZAPI_PORT","8080"); e.put("TZ","America/Bogota");
        process=pb.start();
        new Thread(() -> {
            try(BufferedReader r=new BufferedReader(new InputStreamReader(process.getInputStream()))){
                String l; while((l=r.readLine())!=null){
                    Log.i("WuzAPI",l);
                    String low=l.toLowerCase(Locale.ROOT);
                    if(low.contains("\"level\":\"error\"") || low.contains(" failed ") || low.contains("\"error\"")){
                        String clip=l.length()>500?l.substring(l.length()-500):l;
                        Prefs.put(c,"wuz_last_error",clip);
                    }
                }
            }catch(Exception ignored){}
        },"wuz-log").start();
        waitReady(25000); ensureUser();
    }

    public synchronized void restart() throws Exception {
        stop();
        Thread.sleep(1200);
        start();
    }

    public void waitReady(long timeoutMs) throws Exception {
        long until=System.currentTimeMillis()+timeoutMs; Exception last=null;
        while(System.currentTimeMillis()<until){
            try{ HttpJson.Result r=HttpJson.call("GET","http://127.0.0.1:8080/health",null,null); if(r.ok()) return; }
            catch(Exception ex){ last=ex; }
            Thread.sleep(500);
        }
        throw new IOException("El motor interno no respondió"+(last!=null?": "+last.getMessage():""));
    }

    private Map<String,String> adminAuth(){ Map<String,String> h=new HashMap<>(); h.put("Authorization",Prefs.get(c,"wuz_admin","")); return h; }
    private Map<String,String> auth(){ Map<String,String> h=new HashMap<>(); String t=Prefs.get(c,"wuz_token",""); h.put("Token",t); h.put("Authorization",t); return h; }

    private void ensureUser() throws Exception {
        String token=Prefs.get(c,"wuz_token",""); if(token.isEmpty()){token=Prefs.randomHex(24);Prefs.put(c,"wuz_token",token);}
        JSONObject b=new JSONObject().put("name","monopolyrecords").put("token",token).put("webhook","http://127.0.0.1:1821").put("events","Message");
        HttpJson.Result r=HttpJson.call("POST","http://127.0.0.1:8080/admin/users",b,adminAuth());
        if(!r.ok()){
            HttpJson.Result s=HttpJson.call("GET","http://127.0.0.1:8080/session/status",null,auth());
            if(!(s.ok() || s.code==409 || s.code==500)) throw new IOException("No se pudo preparar sesión: "+r.body);
        }
    }

    public synchronized void stop(){ if(process!=null){ process.destroy(); try{process.waitFor();}catch(Exception ignored){} process=null; } }
    public HttpJson.Result get(String path)throws Exception{return HttpJson.call("GET","http://127.0.0.1:8080"+path,null,auth());}
    public HttpJson.Result post(String path,JSONObject b)throws Exception{return HttpJson.call("POST","http://127.0.0.1:8080"+path,b,auth());}
    public JSONObject status(){ try{return get("/session/status").json();}catch(Exception e){return new JSONObject();} }

    private boolean isConnected(JSONObject j){
        JSONObject d=j.optJSONObject("data"); if(d==null)d=j;
        return d.optBoolean("Connected",false) || d.optBoolean("connected",false) || d.optBoolean("IsConnected",false);
    }
    private boolean isLoggedIn(JSONObject j){
        JSONObject d=j.optJSONObject("data"); if(d==null)d=j;
        return d.optBoolean("LoggedIn",false) || d.optBoolean("loggedIn",false) || d.optBoolean("IsLoggedIn",false);
    }

    private boolean waitConnected(long timeoutMs) throws Exception {
        long until=System.currentTimeMillis()+timeoutMs;
        while(System.currentTimeMillis()<until){
            JSONObject s=status();
            if(isConnected(s)) return true;
            Thread.sleep(750);
        }
        return false;
    }

    private void checkInternet() throws Exception {
        try{
            InetAddress[] a=InetAddress.getAllByName("web.whatsapp.com");
            if(a==null || a.length==0) throw new IOException("DNS sin respuesta");
        }catch(Exception e){
            throw new IOException("El teléfono no puede resolver los servidores de WhatsApp. Revisa Internet/DNS/VPN.");
        }
    }

    public JSONObject connect() throws Exception {
        waitReady(15000);
        if(isConnected(status())) return status();
        checkInternet();

        JSONObject b=new JSONObject();
        b.put("Subscribe",new JSONArray().put("Message"));
        // Immediate=true evita el límite interno de 10 s de WuzAPI.
        // La app hace su propia espera hasta que Connected=true.
        b.put("Immediate",true);
        HttpJson.Result r=post("/session/connect",b);

        // Incluso si WuzAPI devuelve un error transitorio, el goroutine de conexión
        // puede seguir trabajando; por eso esperamos el estado real.
        if(waitConnected(75000)) return status();

        String detail=Prefs.get(c,"wuz_last_error","");
        String base=(r.body==null?"":r.body);
        throw new IOException("No fue posible abrir la conexión con WhatsApp en 75 s"
            +(detail.isEmpty()?(base.isEmpty()?"":" · "+base):" · Detalle: "+detail));
    }

    public String pairPhone(String phone)throws Exception{
        String clean=phone==null?"":phone.replaceAll("[^0-9]","");
        if(clean.length()<8) throw new IOException("Número de WhatsApp inválido");

        waitReady(20000);
        if(!isConnected(status())) connect();

        Exception last=null;
        for(int attempt=1; attempt<=3; attempt++){
            try{
                if(!isConnected(status())){
                    connect();
                }
                JSONObject b=new JSONObject().put("Phone",clean);
                HttpJson.Result res=post("/session/pairphone",b);
                JSONObject j=res.json();
                JSONObject data=j.optJSONObject("data");
                String code=data!=null?data.optString("LinkingCode",""):j.optString("LinkingCode","");
                if(code.isEmpty()) code=j.optString("linkingCode","");
                if(!code.isEmpty()) return code;

                String err=j.optString("error",res.body==null?"":res.body);
                last=new IOException(err.isEmpty()?"No se recibió código":err);
                Thread.sleep(1500L*attempt);
            }catch(Exception e){
                last=e;
                Thread.sleep(1500L*attempt);
            }
        }
        throw new IOException(last!=null?last.getMessage():"No fue posible generar el código de WhatsApp");
    }

    public boolean loggedIn(){ return isLoggedIn(status()); }

    public HttpJson.Result sendText(String phone,String text)throws Exception{return post("/chat/send/text",new JSONObject().put("Phone",phone).put("Body",text));}
    public HttpJson.Result sendImage(String phone,String data,String caption)throws Exception{return post("/chat/send/image",new JSONObject().put("Phone",phone).put("Image",data).put("Caption",caption));}
    public HttpJson.Result sendVideo(String phone,String data,String caption)throws Exception{return post("/chat/send/video",new JSONObject().put("Phone",phone).put("Video",data).put("Caption",caption));}
    public HttpJson.Result sendAudio(String phone,String data)throws Exception{return post("/chat/send/audio",new JSONObject().put("Phone",phone).put("Audio",data));}
    public HttpJson.Result sendDocument(String phone,String data,String name,String caption)throws Exception{return post("/chat/send/document",new JSONObject().put("Phone",phone).put("Document",data).put("FileName",name).put("Caption",caption));}
    public HttpJson.Result sendSticker(String phone,String data)throws Exception{return post("/chat/send/sticker",new JSONObject().put("Phone",phone).put("Sticker",data));}
    public HttpJson.Result sendLocation(String phone,double lat,double lng,String name)throws Exception{return post("/chat/send/location",new JSONObject().put("Phone",phone).put("Latitude",lat).put("Longitude",lng).put("Name",name));}
    public HttpJson.Result sendContact(String phone,String name,String number)throws Exception{return post("/chat/send/contact",new JSONObject().put("Phone",phone).put("Name",name).put("Vcard","BEGIN:VCARD\\nVERSION:3.0\\nFN:"+name+"\\nTEL;TYPE=CELL:"+number+"\\nEND:VCARD"));}
    public HttpJson.Result setTextStatus(String text)throws Exception{return post("/status/set/text",new JSONObject().put("Text",text));}
}
