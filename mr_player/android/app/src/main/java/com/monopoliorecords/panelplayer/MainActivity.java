package com.monopoliorecords.panelplayer;

import android.app.Activity;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.VideoView;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private DeviceIdentity identity;
    private String token="";
    private PanelApi.Config activeConfig;
    private TextView status, ids;
    private ProgressBar progress;
    private ListView list;
    private VideoView video;
    private boolean destroyed=false;

    @Override public void onCreate(Bundle b){super.onCreate(b); buildUi(); identity=DeviceIdentity.read(this); showIds(); token=getPreferences(MODE_PRIVATE).getString("device_token",""); bootstrap();}

    private void buildUi(){
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(24,18,24,18); root.setBackgroundColor(Color.rgb(12,13,16));
        TextView title=t("MR Panel Player",26,Color.WHITE); root.addView(title);
        ids=t("",14,Color.LTGRAY); root.addView(ids);
        status=t("Iniciando…",16,Color.WHITE); status.setPadding(0,10,0,10); root.addView(status);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal); progress.setIndeterminate(true); root.addView(progress,new LinearLayout.LayoutParams(-1,8));
        LinearLayout body=new LinearLayout(this); body.setOrientation(LinearLayout.HORIZONTAL); body.setPadding(0,12,0,0);
        list=new ListView(this); list.setBackgroundColor(Color.rgb(23,25,31)); list.setDividerHeight(1);
        video=new VideoView(this); video.setBackgroundColor(Color.BLACK); video.setVisibility(View.GONE);
        body.addView(list,new LinearLayout.LayoutParams(0,-1,0.42f)); body.addView(video,new LinearLayout.LayoutParams(0,-1,0.58f));
        root.addView(body,new LinearLayout.LayoutParams(-1,0,1)); setContentView(root);
    }
    private TextView t(String s,int sp,int c){TextView v=new TextView(this);v.setText(s);v.setTextSize(sp);v.setTextColor(c);v.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);return v;}
    private void showIds(){ids.setText("MAC: "+(identity.mac.isEmpty()?"no disponible por Android":identity.mac)+"   •   ID: "+identity.deviceKey.substring(0,16).toUpperCase());}

    private void bootstrap(){
        status.setText(token.isEmpty()?"Registrando dispositivo…":"Consultando panel…"); progress.setVisibility(View.VISIBLE);
        io.execute(()->{try{if(token.isEmpty()){token=PanelApi.register(identity,""); getPreferences(MODE_PRIVATE).edit().putString("device_token",token).apply();} pollConfig();}catch(Exception e){fail("No se pudo conectar al panel: "+e.getMessage()); scheduleRetry(8000);}});
    }

    private void pollConfig(){
        if(destroyed)return;
        try{
            PanelApi.Config c=PanelApi.getConfig(identity,token);
            if("active".equals(c.status)&&c.server!=null&&!c.server.isEmpty()&&c.username!=null&&!c.username.isEmpty()){
                boolean changed=activeConfig==null||!safe(activeConfig.server).equals(safe(c.server))||!safe(activeConfig.username).equals(safe(c.username))||!safe(activeConfig.password).equals(safe(c.password));
                activeConfig=c; ok("Equipo activo. Credenciales recibidas desde tu panel."); if(changed) loadChannels(c);
            } else if("blocked".equals(c.status)) { activeConfig=null; ui.post(()->{status.setText("Este equipo está bloqueado desde el panel.");progress.setVisibility(View.GONE);list.setAdapter(null);video.stopPlayback();video.setVisibility(View.GONE);}); }
            else { activeConfig=null; ui.post(()->{status.setText("Esperando activación en el panel…");progress.setVisibility(View.VISIBLE);list.setAdapter(null);}); }
        }catch(Exception e){
            String m=e.getMessage()==null?"":e.getMessage();
            if(m.contains("unauthorized_device")){
                token=""; getPreferences(MODE_PRIVATE).edit().remove("device_token").apply();
                ui.postDelayed(this::bootstrap,1500); return;
            }
            fail("Panel sin respuesta: "+m);
        }
        scheduleRetry(10000);
    }

    private void loadChannels(PanelApi.Config c){
        ui.post(()->{status.setText("Cargando canales…"); progress.setVisibility(View.VISIBLE);});
        io.execute(()->{try{List<Channel> ch=XtreamApi.liveChannels(c.server,c.username,c.password); ui.post(()->{progress.setVisibility(View.GONE);status.setText("Activo • "+ch.size()+" canales");ArrayAdapter<Channel>a=new ArrayAdapter<>(this,android.R.layout.simple_list_item_1,ch);list.setAdapter(a);list.setOnItemClickListener((p,v,pos,id)->play(ch.get(pos)));});}catch(Exception e){fail("Credenciales recibidas, pero el servidor IPTV respondió con error: "+e.getMessage());}});
    }
    private void play(Channel ch){if(activeConfig==null)return;String u=XtreamApi.liveUrl(activeConfig.server,activeConfig.username,activeConfig.password,ch.streamId);video.setVisibility(View.VISIBLE);video.setVideoURI(Uri.parse(u));video.setOnPreparedListener(mp->{mp.setScreenOnWhilePlaying(true);mp.start();status.setText("Reproduciendo: "+ch.name);});video.setOnErrorListener((mp,what,extra)->{status.setText("No se pudo reproducir este stream.");return true;});video.requestFocus();}
    private void scheduleRetry(long ms){ui.postDelayed(()->io.execute(this::pollConfig),ms);}
    private void ok(String s){ui.post(()->{status.setText(s);progress.setVisibility(View.GONE);});}
    private void fail(String s){ui.post(()->{status.setText(s);progress.setVisibility(View.GONE);});}
    private static String safe(String s){return s==null?"":s;}
    @Override protected void onDestroy(){destroyed=true;io.shutdownNow();video.stopPlayback();super.onDestroy();}
}
