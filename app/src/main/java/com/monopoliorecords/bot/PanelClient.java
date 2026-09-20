package com.monopoliorecords.bot;

import android.content.Context;
import android.content.pm.PackageInfo;
import org.json.JSONObject;
import java.util.*;

public class PanelClient {
    private final Context c; public PanelClient(Context c){this.c=c.getApplicationContext();}
    private String base(){ String b=Prefs.get(c,"panel_url","").trim(); while(b.endsWith("/"))b=b.substring(0,b.length()-1); return b; }
    private Map<String,String> h(){ Map<String,String> h=new HashMap<>(); String t=Prefs.get(c,"device_token",""); if(!t.isEmpty())h.put("Authorization","Bearer "+t); return h; }
    private String version(){
        try { PackageInfo p=c.getPackageManager().getPackageInfo(c.getPackageName(),0); return p.versionName==null?"":p.versionName; }
        catch(Exception e){ return ""; }
    }
    public JSONObject claim(String url,String code)throws Exception{
        while(url.endsWith("/"))url=url.substring(0,url.length()-1); Prefs.put(c,"panel_url",url);
        JSONObject b=new JSONObject().put("code",code).put("device_uuid",Prefs.deviceUuid(c)).put("name","Teléfono Monopolio Records");
        JSONObject j=HttpJson.call("POST",url+"/api/v1/device/claim.php",b,null).json();
        String t=j.optString("device_token",""); if(t.isEmpty())throw new Exception(j.optString("error","No se pudo vincular")); Prefs.put(c,"device_token",t); return j;
    }
    public JSONObject sync()throws Exception{return HttpJson.call("GET",base()+"/api/v1/device/sync.php",null,h()).json();}
    public void heartbeat(JSONObject status)throws Exception{
        JSONObject b=new JSONObject().put("status",status).put("app_version",version());
        HttpJson.call("POST",base()+"/api/v1/device/heartbeat.php",b,h());
    }
    public void jobResult(String id,boolean ok,String msg)throws Exception{ HttpJson.call("POST",base()+"/api/v1/device/job_result.php",new JSONObject().put("id",id).put("ok",ok).put("message",msg),h()); }
    public void log(String level,String message)throws Exception{ HttpJson.call("POST",base()+"/api/v1/device/event.php",new JSONObject().put("level",level).put("message",message),h()); }
    public boolean linked(){return !base().isEmpty()&&!Prefs.get(c,"device_token","").isEmpty();}
}
