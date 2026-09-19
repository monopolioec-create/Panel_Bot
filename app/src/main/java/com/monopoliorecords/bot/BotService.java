package com.monopoliorecords.bot;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;

public class BotService extends Service {
    public static final String CH="mrbot"; private volatile boolean running; private WuzApiManager wuz; private LocalWebhookServer webhook; private PanelClient panel; private RuleEngine engine;
    @Override public void onCreate(){super.onCreate();createChannel();startForeground(14,notification("Bot iniciando…"));running=true;new Thread(this::main,"mr-main").start();}
    private void main(){
        try{wuz=new WuzApiManager(this);engine=new RuleEngine(this,wuz);webhook=new LocalWebhookServer(engine);webhook.start();wuz.start();panel=new PanelClient(this);Thread.sleep(1600);try{wuz.connect();}catch(Exception ignored){};
            while(running){try{wuz.start();if(panel.linked()){JSONObject sync=panel.sync();JSONArray rules=sync.optJSONArray("rules");if(rules!=null)Prefs.put(this,"rules_json",rules.toString());JSONArray jobs=sync.optJSONArray("jobs");if(jobs!=null)for(int i=0;i<jobs.length();i++){JSONObject j=jobs.getJSONObject(i);String id=j.optString("id");try{String m=engine.executeJob(j);panel.jobResult(id,true,m);}catch(Exception e){panel.jobResult(id,false,e.getMessage());}}panel.heartbeat(wuz.status());}updateNotification();}catch(Exception e){android.util.Log.e("BotService","sync",e);}Thread.sleep(20000);}
        }catch(Exception e){android.util.Log.e("BotService","fatal",e);notifyText("Error: "+e.getMessage());}
    }
    private void updateNotification(){JSONObject s=wuz.status();JSONObject d=s.optJSONObject("data");boolean on=d!=null&&d.optBoolean("LoggedIn",false);notifyText(on?"WhatsApp conectado · bot activo":"Bot activo · WhatsApp pendiente");}
    private Notification notification(String text){Intent i=new Intent(this,MainActivity.class);PendingIntent pi=PendingIntent.getActivity(this,0,i,PendingIntent.FLAG_UPDATE_CURRENT|(Build.VERSION.SDK_INT>=23?PendingIntent.FLAG_IMMUTABLE:0));return new Notification.Builder(this,Build.VERSION.SDK_INT>=26?CH:null).setSmallIcon(android.R.drawable.stat_notify_chat).setContentTitle("Monopoly Records Bot").setContentText(text).setOngoing(true).setContentIntent(pi).build();}
    private void notifyText(String t){((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(14,notification(t));}
    private void createChannel(){if(Build.VERSION.SDK_INT>=26){NotificationChannel c=new NotificationChannel(CH,"Monopoly Records Bot",NotificationManager.IMPORTANCE_LOW);((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(c);}}
    @Override public int onStartCommand(Intent i,int f,int id){return START_STICKY;}
    @Override public void onDestroy(){running=false;if(webhook!=null)webhook.stop();if(wuz!=null)wuz.stop();super.onDestroy();}
    @Override public android.os.IBinder onBind(Intent i){return null;}
}
