package com.monopoliorecords.bot;

import android.content.Context;
import org.json.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.regex.Pattern;

public class RuleEngine {
    private final Context c; private final WuzApiManager wuz; private final PanelClient panel;
    public RuleEngine(Context c,WuzApiManager w){this.c=c.getApplicationContext();this.wuz=w;this.panel=new PanelClient(this.c);}

    public void onWebhook(String raw){
        try{
            JSONObject root=new JSONObject(raw);

            // Compatibilidad con WEBHOOK_FORMAT=form o wrappers antiguos.
            String wrapped=root.optString("jsonData","");
            if(!wrapped.isEmpty() && wrapped.trim().startsWith("{")){
                try{ root=new JSONObject(wrapped); }catch(Exception ignored){}
            }

            String eventString = root.opt("event") instanceof String ? root.optString("event","") : "";
            String type=first(root.optString("type",""),root.optString("eventType",""),eventString);
            if(!type.isEmpty() && !"Message".equalsIgnoreCase(type)) return;

            JSONObject d=null;
            Object ev=root.opt("event");
            if(ev instanceof JSONObject) d=(JSONObject)ev;
            if(d==null)d=root.optJSONObject("data");
            if(d==null)d=root;

            JSONObject info=d.optJSONObject("Info"); if(info==null)info=d.optJSONObject("info");

            boolean fromMe=false;
            if(info!=null) fromMe=info.optBoolean("IsFromMe",info.optBoolean("isFromMe",false));
            fromMe=fromMe || d.optBoolean("fromMe",false) || d.optBoolean("IsFromMe",false);
            if(fromMe) return;

            String chat="",sender="",senderAlt="",name="";
            if(info!=null){
                chat=jidValue(info.opt("Chat"));
                sender=jidValue(info.opt("Sender"));
                senderAlt=jidValue(info.opt("SenderAlt"));
                name=first(info.optString("PushName",""),info.optString("pushName",""));
            }
            chat=first(chat,jidValue(d.opt("chat")),jidValue(root.opt("chat")));
            sender=first(sender,jidValue(d.opt("sender")),jidValue(root.opt("sender")));
            senderAlt=first(senderAlt,jidValue(d.opt("senderAlt")),jidValue(d.opt("senderPN")));
            name=first(name,d.optString("pushName",""),root.optString("pushName",""));

            // Para responder usamos el JID completo del chat. Esto funciona tanto
            // con PN (@s.whatsapp.net), LID (@lid) como con grupos (@g.us).
            String route=first(chat,sender,senderAlt);
            if(route.isEmpty()){
                safeLog("error","Webhook recibido pero sin destinatario de respuesta.");
                return;
            }

            // Para variables y panel, preferimos el número telefónico real si
            // WhatsApp lo entrega como alternativa al LID.
            String phone=preferredPhone(senderAlt,sender,chat);

            JSONObject m=d.optJSONObject("Message"); if(m==null)m=d.optJSONObject("message");
            String msg="";
            if(m!=null){
                msg=first(
                    m.optString("conversation",""),
                    nested(m,"extendedTextMessage","text"),
                    nested(m,"ExtendedTextMessage","Text"),
                    nested(m,"imageMessage","caption"),
                    nested(m,"ImageMessage","Caption"),
                    nested(m,"videoMessage","caption"),
                    nested(m,"VideoMessage","Caption")
                );
            }
            msg=first(msg,d.optString("text",""),root.optString("message",""));
            msg=msg==null?"":msg.trim();

            Prefs.put(c,"last_message_at",String.valueOf(System.currentTimeMillis()));
            Prefs.put(c,"last_message_text",msg);
            Prefs.put(c,"last_message_from",phone);
            safeLog("info","Mensaje recibido: ""+shortText(msg,100)+"" · de "+(phone.isEmpty()?route:phone));

            boolean matched=executeRules(route,phone,name,msg);
            if(!matched) safeLog("info","Mensaje recibido sin regla coincidente: ""+shortText(msg,100)+""");
        }catch(Exception e){
            safeLog("error","Error procesando webhook: "+e.getMessage());
            android.util.Log.e("RuleEngine","webhook",e);
        }
    }

    private String shortText(String s,int max){ if(s==null)return""; return s.length()<=max?s:s.substring(0,max)+"…"; }

    private String jidValue(Object v){
        if(v==null || v==JSONObject.NULL)return "";
        if(v instanceof String)return ((String)v).trim();
        if(v instanceof JSONObject){
            JSONObject j=(JSONObject)v;
            String user=first(j.optString("User",""),j.optString("user",""));
            String server=first(j.optString("Server",""),j.optString("server",""));
            if(!user.isEmpty()&&!server.isEmpty())return user+"@"+server;
        }
        return String.valueOf(v);
    }

    private String preferredPhone(String...jids){
        for(String j:jids){
            if(j==null||j.isEmpty())continue;
            String low=j.toLowerCase(Locale.ROOT);
            if(low.contains("@s.whatsapp.net")){
                return j.substring(0,j.indexOf('@')).replaceAll("[^0-9]","");
            }
        }
        for(String j:jids){
            if(j==null||j.isEmpty())continue;
            String x=j;
            int at=x.indexOf('@'); if(at>=0)x=x.substring(0,at);
            int colon=x.indexOf(':'); if(colon>=0)x=x.substring(0,colon);
            String digits=x.replaceAll("[^0-9]","");
            if(digits.length()>=8)return digits;
        }
        return "";
    }

    private String nested(JSONObject o,String a,String b){JSONObject x=o.optJSONObject(a);return x==null?"":x.optString(b,"");}
    private String first(String...s){for(String x:s)if(x!=null&&!x.isEmpty())return x;return "";}

    private boolean executeRules(String route,String phone,String name,String msg)throws Exception{
        String raw=Prefs.get(c,"rules_json","[]"); JSONArray rs=new JSONArray(raw);
        if(rs.length()==0){
            safeLog("warn","No hay reglas sincronizadas todavía en la APK.");
            return false;
        }
        for(int i=0;i<rs.length();i++){
            JSONObject r=rs.getJSONObject(i);
            if(!r.optBoolean("enabled",true)||!matches(r,msg))continue;
            String ruleName=r.optString("name","Regla");
            safeLog("info","Regla coincidente: "+ruleName+" · mensaje ""+shortText(msg,80)+""");
            JSONArray a=r.optJSONArray("actions");
            if(a!=null)for(int k=0;k<a.length();k++)executeAction(route,phone,name,msg,a.getJSONObject(k),ruleName);
            if(r.optBoolean("stop_after",true))return true;
        }
        return false;
    }

    private boolean matches(JSONObject r,String msg){
        String type=r.optString("match_type","contains"),p=r.optString("pattern","");
        String a=msg==null?"":msg,b=p==null?"":p;
        boolean cs=r.optBoolean("case_sensitive",false);
        if(!cs){a=a.toLowerCase(Locale.ROOT);b=b.toLowerCase(Locale.ROOT);}
        try{
            switch(type){
                case"any":return true;
                case"exact":return a.trim().equals(b.trim());
                case"starts":return a.trim().startsWith(b.trim());
                case"regex":return Pattern.compile(p,cs?0:Pattern.CASE_INSENSITIVE).matcher(msg).find();
                default:return a.contains(b);
            }
        }catch(Exception e){return false;}
    }

    private String vars(String s,String phone,String name,String msg){
        if(s==null)return"";Date now=new Date();Locale es=new Locale("es","CO");
        return s.replace("@mensaje",msg==null?"":msg).replace("@telefono",phone).replace("@nombre",name==null?"":name).replace("@hora",new SimpleDateFormat("HH:mm",es).format(now)).replace("@dia",new SimpleDateFormat("EEEE",es).format(now)).replace("@fecha_completa",new SimpleDateFormat("dd/MM/yyyy HH:mm",es).format(now));
    }

    private void checked(String label,HttpJson.Result r)throws Exception{
        JSONObject j=r.json();
        boolean apiSuccess=!j.has("success") || j.optBoolean("success",true);
        if(!r.ok() || !apiSuccess){
            String err=j.optString("error",r.body);
            throw new Exception(label+": "+(err==null||err.isEmpty()?"HTTP "+r.code:err));
        }
    }

    private void executeAction(String route,String phone,String name,String msg,JSONObject a,String ruleName)throws Exception{
        long delay=a.optLong("delay_ms",0);if(delay>0)Thread.sleep(Math.min(delay,3600000));
        String type=a.optString("type","");
        String text=vars(a.optString("text",a.optString("caption","")),phone,name,msg);
        String url=a.optString("url","");
        try{
            switch(type){
                case"text":checked("texto",wuz.sendText(route,text));break;
                case"image":checked("imagen",wuz.sendImage(route,MediaUtil.asDataUri(url),text));break;
                case"video":checked("video",wuz.sendVideo(route,MediaUtil.asDataUri(url),text));break;
                case"audio":checked("audio",wuz.sendAudio(route,MediaUtil.asDataUri(url)));break;
                case"document":checked("documento",wuz.sendDocument(route,MediaUtil.asDataUri(url),a.optString("file_name","archivo"),text));break;
                case"sticker":checked("sticker",wuz.sendSticker(route,MediaUtil.asDataUri(url)));break;
                case"location":checked("ubicación",wuz.sendLocation(route,a.optDouble("lat"),a.optDouble("lng"),a.optString("name","Ubicación")));break;
                case"contact":checked("contacto",wuz.sendContact(route,a.optString("name","Contacto"),a.optString("number","")));break;
                default:throw new Exception("Tipo de acción no soportado: "+type);
            }
            Prefs.put(c,"last_reply_at",String.valueOf(System.currentTimeMillis()));
            Prefs.put(c,"last_reply_to",phone);
            safeLog("info","Respuesta enviada · regla "+ruleName+" · tipo "+type+" · a "+(phone.isEmpty()?route:phone));
        }catch(Exception e){
            safeLog("error","Error enviando respuesta · regla "+ruleName+" · "+e.getMessage());
            throw e;
        }
    }

    private void safeLog(String level,String message){
        android.util.Log.i("RuleEngine",level+": "+message);
        if(panel.linked()){
            try{panel.log(level,message);}catch(Exception ignored){}
        }
    }

    public String executeJob(JSONObject job)throws Exception{
        String type=job.optString("type","");JSONObject p=job.optJSONObject("payload");if(p==null)p=new JSONObject();
        if("status_text".equals(type)){wuz.setTextStatus(p.optString("text",""));return"Estado de texto publicado";}
        if("status_image".equals(type)||"status_video".equals(type)) throw new UnsupportedOperationException("Publicación multimedia de estados pendiente de adaptador compatible.");
        throw new IllegalArgumentException("Trabajo no soportado: "+type);
    }
}
