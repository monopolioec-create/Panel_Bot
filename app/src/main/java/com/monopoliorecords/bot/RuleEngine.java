package com.monopoliorecords.bot;

import android.content.Context;
import org.json.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.regex.Pattern;

public class RuleEngine {
    private final Context c; private final WuzApiManager wuz;
    public RuleEngine(Context c,WuzApiManager w){this.c=c.getApplicationContext();this.wuz=w;}
    public void onWebhook(String raw){
        try{
            JSONObject root=new JSONObject(raw);
            String type=first(root.optString("type",""),root.optString("eventType",""));
            if(!type.isEmpty() && !"Message".equalsIgnoreCase(type)) return;
            JSONObject d=root.optJSONObject("event"); if(d==null)d=root.optJSONObject("data"); if(d==null)d=root;
            JSONObject info=d.optJSONObject("Info"); if(info==null)info=d.optJSONObject("info");
            if((info!=null && info.optBoolean("IsFromMe",false)) || d.optBoolean("fromMe",false)) return;
            String phone=""; String name="";
            if(info!=null){ phone=first(info.optString("Sender",""),info.optString("Chat",""),info.optString("sender","")); name=first(info.optString("PushName",""),info.optString("pushName","")); }
            phone=first(phone,d.optString("sender",""),d.optString("chat",""),root.optString("sender",""));
            phone=phone.replaceAll("@.*$","").replaceAll("[^0-9]","");
            name=first(name,d.optString("pushName",""),root.optString("pushName",""));
            JSONObject m=d.optJSONObject("Message"); if(m==null)m=d.optJSONObject("message"); String msg="";
            if(m!=null){ msg=first(m.optString("conversation",""), nested(m,"extendedTextMessage","text"), nested(m,"imageMessage","caption"), nested(m,"videoMessage","caption")); }
            msg=first(msg,d.optString("text",""),root.optString("message",""));
            if(phone.isEmpty())return; executeRules(phone,name,msg);
        }catch(Exception e){ android.util.Log.e("RuleEngine","webhook",e); }
    }
    private String nested(JSONObject o,String a,String b){JSONObject x=o.optJSONObject(a);return x==null?"":x.optString(b,"");}
    private String first(String...s){for(String x:s)if(x!=null&&!x.isEmpty())return x;return "";}
    private void executeRules(String phone,String name,String msg)throws Exception{
        String raw=Prefs.get(c,"rules_json","[]"); JSONArray rs=new JSONArray(raw);
        for(int i=0;i<rs.length();i++){JSONObject r=rs.getJSONObject(i);if(!r.optBoolean("enabled",true)||!matches(r,msg))continue; JSONArray a=r.optJSONArray("actions");if(a!=null)for(int k=0;k<a.length();k++)executeAction(phone,name,msg,a.getJSONObject(k)); if(r.optBoolean("stop_after",true))break;}
    }
    private boolean matches(JSONObject r,String msg){String type=r.optString("match_type","contains"),p=r.optString("pattern","");String a=msg==null?"":msg,b=p==null?"":p;boolean cs=r.optBoolean("case_sensitive",false);if(!cs){a=a.toLowerCase();b=b.toLowerCase();}
        try{switch(type){case"any":return true;case"exact":return a.equals(b);case"starts":return a.startsWith(b);case"regex":return Pattern.compile(p,cs?0:Pattern.CASE_INSENSITIVE).matcher(msg).find();default:return a.contains(b);}}catch(Exception e){return false;}}
    private String vars(String s,String phone,String name,String msg){ if(s==null)return"";Date now=new Date();Locale es=new Locale("es","CO");return s.replace("@mensaje",msg==null?"":msg).replace("@telefono",phone).replace("@nombre",name==null?"":name).replace("@hora",new SimpleDateFormat("HH:mm",es).format(now)).replace("@dia",new SimpleDateFormat("EEEE",es).format(now)).replace("@fecha_completa",new SimpleDateFormat("dd/MM/yyyy HH:mm",es).format(now)); }
    private void executeAction(String phone,String name,String msg,JSONObject a)throws Exception{
        long delay=a.optLong("delay_ms",0);if(delay>0)Thread.sleep(Math.min(delay,3600000));String type=a.optString("type","");String text=vars(a.optString("text",a.optString("caption","")),phone,name,msg);String url=a.optString("url","");
        switch(type){case"text":wuz.sendText(phone,text);break;case"image":wuz.sendImage(phone,MediaUtil.asDataUri(url),text);break;case"video":wuz.sendVideo(phone,MediaUtil.asDataUri(url),text);break;case"audio":wuz.sendAudio(phone,MediaUtil.asDataUri(url));break;case"document":wuz.sendDocument(phone,MediaUtil.asDataUri(url),a.optString("file_name","archivo"),text);break;case"sticker":wuz.sendSticker(phone,MediaUtil.asDataUri(url));break;case"location":wuz.sendLocation(phone,a.optDouble("lat"),a.optDouble("lng"),a.optString("name","Ubicación"));break;case"contact":wuz.sendContact(phone,a.optString("name","Contacto"),a.optString("number",""));break;}
    }
    public String executeJob(JSONObject job)throws Exception{
        String type=job.optString("type","");JSONObject p=job.optJSONObject("payload");if(p==null)p=new JSONObject();
        if("status_text".equals(type)){wuz.setTextStatus(p.optString("text",""));return"Estado de texto publicado";}
        if("status_image".equals(type)||"status_video".equals(type)) throw new UnsupportedOperationException("Publicación multimedia de estados pendiente de adaptador compatible.");
        throw new IllegalArgumentException("Trabajo no soportado: "+type);
    }
}
