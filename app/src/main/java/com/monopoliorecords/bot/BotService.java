package com.monopoliorecords.bot;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;

public class BotService extends Service {
    public static final String CH="mrbot";
    public static final String ACTION_RESTART_ENGINE="com.monopoliorecords.bot.RESTART_ENGINE";
    private volatile boolean running;
    private WuzApiManager wuz;
    private LocalWebhookServer webhook;
    private PanelClient panel;
    private RuleEngine engine;
    private PowerManager.WakeLock wakeLock;

    @Override public void onCreate(){
        super.onCreate();
        createChannel();
        startForeground(14,notification("Iniciando motor…"));
        acquireWakeLock();
        running=true;
        Prefs.putBool(this,"auto_start",true);
        new Thread(this::main,"mr-main").start();
    }

    private void acquireWakeLock(){
        try{
            PowerManager pm=(PowerManager)getSystemService(POWER_SERVICE);
            wakeLock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"MonopolioRecordsBot:Engine");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire();
        }catch(Exception e){android.util.Log.w("BotService","WakeLock no disponible",e);}
    }

    private void main(){
        try{
            wuz=new WuzApiManager(this);
            engine=new RuleEngine(this,wuz);
            webhook=new LocalWebhookServer(engine);
            webhook.start();
            wuz.start();
            panel=new PanelClient(this);

            new Thread(()->{
                try{wuz.connect();}
                catch(Exception e){android.util.Log.w("BotService","Conexión inicial pendiente: "+e.getMessage());}
            },"wa-connect").start();

            while(running){
                try{
                    wuz.start();
                    if(panel.linked()){
                        JSONObject sync=panel.sync();

                        boolean enabled=sync.optBoolean("bot_enabled",true);
                        Prefs.putBool(this,"bot_enabled",enabled);

                        JSONArray rules=sync.optJSONArray("rules");
                        if(rules!=null)Prefs.put(this,"rules_json",rules.toString());

                        JSONArray jobs=sync.optJSONArray("jobs");
                        if(jobs!=null)for(int i=0;i<jobs.length();i++){
                            JSONObject j=jobs.getJSONObject(i);
                            String id=j.optString("id");
                            try{
                                String m=engine.executeJob(j);
                                panel.jobResult(id,true,m);
                            }catch(Exception e){
                                panel.jobResult(id,false,e.getMessage());
                            }
                        }

                        JSONObject hb=wuz.status();
                        hb.put("bot_service",true);
                        hb.put("bot_enabled",enabled);
                        hb.put("last_message_at",Prefs.get(this,"last_message_at",""));
                        hb.put("last_message_text",Prefs.get(this,"last_message_text",""));
                        hb.put("last_message_from",Prefs.get(this,"last_message_from",""));
                        hb.put("last_reply_at",Prefs.get(this,"last_reply_at",""));
                        hb.put("last_reply_to",Prefs.get(this,"last_reply_to",""));
                        panel.heartbeat(hb);
                    }
                    ensureConnected();
                    updateNotification();
                }catch(Exception e){
                    android.util.Log.e("BotService","sync",e);
                }
                Thread.sleep(2500);
            }
        }catch(Exception e){
            android.util.Log.e("BotService","fatal",e);
            notifyText("Error del motor · se intentará recuperar");
        }
    }

    private void ensureConnected(){
        try{
            JSONObject s=wuz.status();
            JSONObject d=s.optJSONObject("data");
            boolean connected=d!=null&&d.optBoolean("Connected",false);
            boolean logged=d!=null&&d.optBoolean("LoggedIn",false);
            if(logged&&!connected){
                new Thread(()->{try{wuz.connect();}catch(Exception ignored){}},"wa-autoreconnect").start();
            }
        }catch(Exception ignored){}
    }

    private synchronized void restartEngine(){
        new Thread(()->{
            try{
                notifyText("Reiniciando motor de WhatsApp…");
                if(wuz!=null)wuz.restart();
                new Thread(()->{try{wuz.connect();}catch(Exception ignored){}},"wa-reconnect").start();
            }catch(Exception e){
                android.util.Log.e("BotService","restart",e);
            }
        },"mr-restart").start();
    }

    private void updateNotification(){
        JSONObject s=wuz.status();
        JSONObject d=s.optJSONObject("data");
        boolean logged=d!=null&&d.optBoolean("LoggedIn",false);
        boolean enabled=Prefs.getBool(this,"bot_enabled",true);
        if(logged){
            notifyText(enabled?"WhatsApp conectado · BOT ENCENDIDO":"WhatsApp conectado · BOT APAGADO");
        }else{
            notifyText("Servicio activo · WhatsApp pendiente");
        }
    }

    private Notification notification(String text){
        Intent i=new Intent(this,MainActivity.class);
        PendingIntent pi=PendingIntent.getActivity(this,0,i,PendingIntent.FLAG_UPDATE_CURRENT|(Build.VERSION.SDK_INT>=23?PendingIntent.FLAG_IMMUTABLE:0));
        return new Notification.Builder(this,Build.VERSION.SDK_INT>=26?CH:null)
            .setSmallIcon(R.drawable.ic_notify)
            .setContentTitle("Monopolio Records Bot")
            .setContentText(text)
            .setOngoing(true)
            .setContentIntent(pi)
            .build();
    }

    private void notifyText(String t){((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(14,notification(t));}

    private void createChannel(){
        if(Build.VERSION.SDK_INT>=26){
            NotificationChannel c=new NotificationChannel(CH,"Monopolio Records Bot",NotificationManager.IMPORTANCE_LOW);
            c.setDescription("Mantiene el motor de WhatsApp funcionando en segundo plano");
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(c);
        }
    }

    @Override public int onStartCommand(Intent i,int f,int id){
        Prefs.putBool(this,"auto_start",true);
        if(i!=null&&ACTION_RESTART_ENGINE.equals(i.getAction()))restartEngine();
        return START_STICKY;
    }

    @Override public void onTaskRemoved(Intent rootIntent){
        Prefs.putBool(this,"auto_start",true);
        super.onTaskRemoved(rootIntent);
    }

    @Override public void onDestroy(){
        running=false;
        if(webhook!=null)webhook.stop();
        if(wuz!=null)wuz.stop();
        try{if(wakeLock!=null&&wakeLock.isHeld())wakeLock.release();}catch(Exception ignored){}
        super.onDestroy();
    }

    @Override public android.os.IBinder onBind(Intent i){return null;}
}
