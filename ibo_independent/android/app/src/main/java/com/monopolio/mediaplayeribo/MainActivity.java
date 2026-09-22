package com.monopolio.mediaplayeribo;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.ArrayAdapter;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.ui.PlayerView;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private DeviceIdentity identity;
    private String token="";
    private PanelApi.Config config;
    private FrameLayout root;
    private TextView footer;
    private ExoPlayer player;
    private String screen="activation";

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        root=new FrameLayout(this); root.setBackgroundColor(Color.rgb(5,7,10)); setContentView(root);
        identity=DeviceIdentity.read(this);
        token=getPreferences(MODE_PRIVATE).getString("device_token","");
        showActivation("Conectando con el panel…"); bootstrap();
    }

    private void bootstrap(){
        io.execute(()->{try{if(token.isEmpty()){token=PanelApi.register(identity);getPreferences(MODE_PRIVATE).edit().putString("device_token",token).apply();}checkPanel();}catch(Exception e){showActivation("Sin conexión al panel. Reintentando…\n"+msg(e));ui.postDelayed(this::bootstrap,7000);}});
    }

    private void checkPanel(){
        try{
            config=PanelApi.config(identity,token);
            if("active".equals(config.status)&&!config.server.isEmpty()&&!config.username.isEmpty()&&!config.password.isEmpty())ui.post(this::showHome);
            else if("blocked".equals(config.status)){showActivation("DISPOSITIVO BLOQUEADO\nContacta al administrador.");ui.postDelayed(()->io.execute(this::checkPanel),8000);}
            else{showActivation("Esperando activación en el panel…");ui.postDelayed(()->io.execute(this::checkPanel),5000);}
        }catch(Exception e){
            if(String.valueOf(e.getMessage()).contains("unauthorized_device")){token="";getPreferences(MODE_PRIVATE).edit().remove("device_token").apply();ui.postDelayed(this::bootstrap,1000);}
            else{showActivation("Panel temporalmente sin respuesta.\n"+msg(e));ui.postDelayed(()->io.execute(this::checkPanel),7000);}
        }
    }

    private void showActivation(String message){
        ui.post(()->{
            screen="activation";releasePlayer();root.removeAllViews();
            LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);box.setGravity(Gravity.CENTER);box.setPadding(dp(40),dp(25),dp(40),dp(25));
            TextView logo=text("ibo  TV",52,Color.WHITE);logo.setTypeface(Typeface.DEFAULT_BOLD);logo.setGravity(Gravity.CENTER);logo.setBackground(round(Color.rgb(185,25,43),Color.rgb(50,50,50),1));box.addView(logo,new LinearLayout.LayoutParams(dp(330),dp(125)));
            TextView title=text("MediaPlayerIbo",28,Color.WHITE);title.setGravity(Gravity.CENTER);box.addView(title,new LinearLayout.LayoutParams(-1,dp(58)));
            TextView info=text(message,18,Color.LTGRAY);info.setGravity(Gravity.CENTER);box.addView(info,new LinearLayout.LayoutParams(-1,dp(78)));
            TextView id=text("MAC: "+(identity.mac.isEmpty()?"NO DISPONIBLE":identity.mac)+"    ID: "+identity.deviceKey.substring(0,16).toUpperCase(),15,Color.rgb(170,180,190));id.setGravity(Gravity.CENTER);box.addView(id,new LinearLayout.LayoutParams(-1,dp(48)));
            ProgressBar p=new ProgressBar(this);box.addView(p,new LinearLayout.LayoutParams(dp(42),dp(42)));root.addView(box,new FrameLayout.LayoutParams(-1,-1));
        });
    }

    private void showHome(){
        screen="home";releasePlayer();root.removeAllViews();
        LinearLayout all=new LinearLayout(this);all.setOrientation(LinearLayout.VERTICAL);all.setPadding(dp(28),dp(18),dp(28),dp(18));
        LinearLayout head=new LinearLayout(this);head.setGravity(Gravity.CENTER_VERTICAL);
        TextView logo=text("ibo  TV",30,Color.WHITE);logo.setTypeface(Typeface.DEFAULT_BOLD);logo.setGravity(Gravity.CENTER);logo.setBackground(round(Color.rgb(185,25,43),Color.rgb(55,55,55),1));head.addView(logo,new LinearLayout.LayoutParams(dp(210),dp(82)));
        TextView name=text(config.playlistName,22,Color.WHITE);name.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);head.addView(name,new LinearLayout.LayoutParams(0,dp(82),1));all.addView(head,new LinearLayout.LayoutParams(-1,dp(92)));
        LinearLayout cards=new LinearLayout(this);cards.setGravity(Gravity.CENTER);
        cards.addView(card("TV","LIVE TV",Color.rgb(26,115,180),()->load("live")),new LinearLayout.LayoutParams(0,-1,1));
        cards.addView(card("▶","MOVIES",Color.rgb(167,24,49),()->load("movies")),new LinearLayout.LayoutParams(0,-1,1));
        cards.addView(card("S","SERIES",Color.rgb(33,119,168),()->load("series")),new LinearLayout.LayoutParams(0,-1,1));
        cards.addView(card("⚙","SETTINGS",Color.rgb(155,24,43),this::settings),new LinearLayout.LayoutParams(0,-1,1));
        all.addView(cards,new LinearLayout.LayoutParams(-1,0,1));
        footer=text("MAC: "+(identity.mac.isEmpty()?"ID "+identity.deviceKey.substring(0,12).toUpperCase():identity.mac)+"    •    PANEL CONECTADO",14,Color.rgb(170,180,190));all.addView(footer,new LinearLayout.LayoutParams(-1,dp(42)));
        root.addView(all,new FrameLayout.LayoutParams(-1,-1));cards.getChildAt(0).requestFocus();
    }

    private View card(String icon,String label,int color,Runnable action){
        LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);c.setGravity(Gravity.CENTER);c.setPadding(dp(12),dp(14),dp(12),dp(14));c.setFocusable(true);c.setClickable(true);
        GradientDrawable g=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{color,Color.rgb(12,19,27)});g.setCornerRadius(dp(16));g.setStroke(dp(1),Color.rgb(70,80,90));c.setBackground(g);
        TextView i=text(icon,48,Color.WHITE);i.setGravity(Gravity.CENTER);i.setTypeface(Typeface.DEFAULT_BOLD);c.addView(i,new LinearLayout.LayoutParams(-1,0,1));
        TextView t=text(label,20,Color.WHITE);t.setGravity(Gravity.CENTER);t.setTypeface(Typeface.DEFAULT_BOLD);c.addView(t,new LinearLayout.LayoutParams(-1,dp(56)));
        c.setOnClickListener(v->action.run());c.setOnKeyListener((v,k,e)->{if(e.getAction()==KeyEvent.ACTION_UP&&(k==KeyEvent.KEYCODE_DPAD_CENTER||k==KeyEvent.KEYCODE_ENTER)){action.run();return true;}return false;});
        c.setOnFocusChangeListener((v,h)->{v.animate().scaleX(h?1.06f:1f).scaleY(h?1.06f:1f).setDuration(120).start();GradientDrawable x=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{color,Color.rgb(12,19,27)});x.setCornerRadius(dp(16));x.setStroke(dp(h?3:1),h?Color.WHITE:Color.rgb(70,80,90));v.setBackground(x);});
        return c;
    }

    private void load(String type){
        screen=type;loading(type.equals("live")?"Cargando TV…":type.equals("movies")?"Cargando películas…":"Cargando series…");
        io.execute(()->{try{List<XtreamApi.Item> items="live".equals(type)?XtreamApi.live(config):"movies".equals(type)?XtreamApi.movies(config):XtreamApi.series(config);ui.post(()->browser(type,items));}catch(Exception e){ui.post(()->error("No se pudo cargar el contenido",e));}});
    }

    private void loading(String s){root.removeAllViews();LinearLayout b=new LinearLayout(this);b.setOrientation(LinearLayout.VERTICAL);b.setGravity(Gravity.CENTER);b.addView(new ProgressBar(this),new LinearLayout.LayoutParams(dp(55),dp(55)));TextView t=text(s,20,Color.WHITE);t.setGravity(Gravity.CENTER);b.addView(t,new LinearLayout.LayoutParams(-1,dp(70)));root.addView(b,new FrameLayout.LayoutParams(-1,-1));}

    private void browser(String type,List<XtreamApi.Item> items){
        root.removeAllViews();
        LinearLayout all=new LinearLayout(this);all.setOrientation(LinearLayout.VERTICAL);all.setPadding(dp(18),dp(12),dp(18),dp(12));
        LinearLayout h=new LinearLayout(this);h.setGravity(Gravity.CENTER_VERTICAL);TextView back=text("‹ HOME",18,Color.WHITE);back.setGravity(Gravity.CENTER);back.setFocusable(true);back.setClickable(true);back.setOnClickListener(v->showHome());h.addView(back,new LinearLayout.LayoutParams(dp(150),dp(56)));
        String title="live".equals(type)?"LIVE TV":"movies".equals(type)?"MOVIES":"SERIES";h.addView(text(title+"   •   "+items.size(),22,Color.WHITE),new LinearLayout.LayoutParams(0,dp(56),1));all.addView(h,new LinearLayout.LayoutParams(-1,dp(58)));
        LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.HORIZONTAL);
        ListView list=new ListView(this);list.setBackgroundColor(Color.rgb(14,18,23));list.setDividerHeight(1);
        ArrayAdapter<XtreamApi.Item> ad=new ArrayAdapter<XtreamApi.Item>(this,android.R.layout.simple_list_item_1,items){@Override public View getView(int p,View v,ViewGroup parent){TextView x=(TextView)super.getView(p,v,parent);x.setTextColor(Color.WHITE);x.setTextSize(17);x.setPadding(dp(16),dp(11),dp(10),dp(11));return x;}};
        list.setAdapter(ad);body.addView(list,new LinearLayout.LayoutParams(0,-1,.40f));
        FrameLayout box=new FrameLayout(this);box.setBackgroundColor(Color.BLACK);TextView hint=text("Selecciona un elemento para reproducir",18,Color.GRAY);hint.setGravity(Gravity.CENTER);box.addView(hint,new FrameLayout.LayoutParams(-1,-1));body.addView(box,new LinearLayout.LayoutParams(0,-1,.60f));
        all.addView(body,new LinearLayout.LayoutParams(-1,0,1));footer=text("OK: reproducir    •    BACK: inicio",14,Color.rgb(170,180,190));all.addView(footer,new LinearLayout.LayoutParams(-1,dp(38)));root.addView(all,new FrameLayout.LayoutParams(-1,-1));
        list.setOnItemClickListener((p,v,pos,id)->{XtreamApi.Item item=items.get(pos);if("series".equals(item.kind)){loading("Cargando episodios…");io.execute(()->{try{List<XtreamApi.Item> eps=XtreamApi.episodes(config,item.id);ui.post(()->browser("episodes",eps));}catch(Exception e){ui.post(()->error("No se pudieron cargar episodios",e));}});}else play(item,box);});list.requestFocus();
    }

    private void play(XtreamApi.Item item,FrameLayout box){
        releasePlayer();box.removeAllViews();PlayerView pv=new PlayerView(this);pv.setUseController(true);box.addView(pv,new FrameLayout.LayoutParams(-1,-1));player=new ExoPlayer.Builder(this).build();pv.setPlayer(player);player.setMediaItem(MediaItem.fromUri(XtreamApi.playback(config,item)));player.prepare();player.play();footer.setText("Reproduciendo: "+item.name);player.addListener(new Player.Listener(){@Override public void onPlayerError(androidx.media3.common.PlaybackException e){footer.setText("Error: "+e.getErrorCodeName());}});
    }

    private void settings(){
        screen="settings";releasePlayer();root.removeAllViews();LinearLayout a=new LinearLayout(this);a.setOrientation(LinearLayout.VERTICAL);a.setPadding(dp(42),dp(30),dp(42),dp(30));a.addView(text("SETTINGS",28,Color.WHITE),new LinearLayout.LayoutParams(-1,dp(65)));a.addView(text("MAC: "+(identity.mac.isEmpty()?"No disponible":identity.mac),18,Color.WHITE));a.addView(text("DEVICE ID: "+identity.deviceKey.substring(0,20).toUpperCase(),18,Color.WHITE));a.addView(text("SERVER: "+config.server,18,Color.LTGRAY));a.addView(text("USER: "+mask(config.username),18,Color.LTGRAY));a.addView(text("STATUS: ACTIVE",18,Color.rgb(80,220,145)));
        TextView r=text("REFRESH PANEL",19,Color.WHITE);r.setGravity(Gravity.CENTER);r.setFocusable(true);r.setClickable(true);r.setBackground(round(Color.rgb(30,40,48),Color.rgb(0,199,217),2));r.setOnClickListener(v->{showActivation("Actualizando desde el panel…");io.execute(this::checkPanel);});LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(dp(280),dp(62));lp.topMargin=dp(30);a.addView(r,lp);root.addView(a,new FrameLayout.LayoutParams(-1,-1));r.requestFocus();
    }

    private void error(String title,Exception e){root.removeAllViews();LinearLayout b=new LinearLayout(this);b.setOrientation(LinearLayout.VERTICAL);b.setGravity(Gravity.CENTER);TextView t=text(title,26,Color.WHITE);t.setGravity(Gravity.CENTER);b.addView(t,new LinearLayout.LayoutParams(-1,dp(70)));TextView m=text(msg(e),17,Color.LTGRAY);m.setGravity(Gravity.CENTER);b.addView(m,new LinearLayout.LayoutParams(-1,dp(100)));TextView v=text("VOLVER",18,Color.WHITE);v.setGravity(Gravity.CENTER);v.setFocusable(true);v.setClickable(true);v.setBackground(round(Color.rgb(30,40,48),Color.rgb(0,199,217),2));v.setOnClickListener(x->showHome());b.addView(v,new LinearLayout.LayoutParams(dp(220),dp(60)));root.addView(b,new FrameLayout.LayoutParams(-1,-1));v.requestFocus();}

    private TextView text(String s,int sp,int c){TextView v=new TextView(this);v.setText(s);v.setTextSize(sp);v.setTextColor(c);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private GradientDrawable round(int fill,int stroke,int width){GradientDrawable g=new GradientDrawable();g.setColor(fill);g.setCornerRadius(dp(10));if(width>0)g.setStroke(dp(width),stroke);return g;}
    private int dp(int v){return (int)(v*getResources().getDisplayMetrics().density+.5f);}
    private String msg(Exception e){return e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();}
    private String mask(String s){if(s==null||s.length()<3)return "***";return s.substring(0,2)+"***"+s.substring(s.length()-1);}
    private void releasePlayer(){if(player!=null){player.release();player=null;}}
    @Override public void onBackPressed(){if("home".equals(screen)||"activation".equals(screen))super.onBackPressed();else showHome();}
    @Override protected void onDestroy(){releasePlayer();io.shutdownNow();super.onDestroy();}
}
