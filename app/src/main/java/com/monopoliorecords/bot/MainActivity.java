package com.monopoliorecords.bot;

import android.app.*;import android.os.*;import android.content.*;import android.graphics.Color;import android.view.*;import android.widget.*;

public class MainActivity extends Activity {
    private EditText url,code,phone; private TextView status,pairCode; private Button pairButton;
    @Override public void onCreate(Bundle b){super.onCreate(b);if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},77);build();}
    private int dp(int v){return (int)(v*getResources().getDisplayMetrics().density+0.5f);}
    private TextView title(String s,int n){TextView t=new TextView(this);t.setText(s);t.setTextSize(n);t.setTextColor(Color.rgb(17,24,39));t.setPadding(0,14,0,7);return t;}
    private EditText input(String hint,String val){EditText e=new EditText(this);e.setHint(hint);e.setText(val);e.setSingleLine(true);return e;}
    private Button button(String s){Button b=new Button(this);b.setText(s);return b;}

    private void build(){
        ScrollView sv=new ScrollView(this);LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);l.setPadding(dp(20),dp(14),dp(20),dp(40));sv.addView(l);

        ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.ic_mr_logo);logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(112));lp.setMargins(0,0,0,dp(4));l.addView(logo,lp);

        TextView brand=title("MONOPOLY RECORDS BOT",26);brand.setGravity(Gravity.CENTER_HORIZONTAL);l.addView(brand);
        TextView sub=title("Automatización de WhatsApp",17);sub.setGravity(Gravity.CENTER_HORIZONTAL);l.addView(sub);
        status=title("Estado: listo para configurar",15);l.addView(status);

        l.addView(title("1. Vincular con tu panel web",18));
        url=input("https://tudominio.com/monopolybot",Prefs.get(this,"panel_url",""));
        code=input("Código de 6 dígitos","");
        l.addView(url);l.addView(code);
        Button claim=button("Vincular panel");l.addView(claim);
        claim.setOnClickListener(v->bg(()->{try{new PanelClient(this).claim(url.getText().toString().trim(),code.getText().toString().trim());ui("Panel vinculado correctamente");}catch(Exception e){ui("Error panel: "+e.getMessage());}}));

        l.addView(title("2. Vincular WhatsApp",18));
        phone=input("Número internacional, ej. 573001234567",Prefs.get(this,"wa_phone",""));
        l.addView(phone);
        pairButton=button("Generar código WhatsApp");l.addView(pairButton);
        pairCode=title("",24);pairCode.setGravity(Gravity.CENTER_HORIZONTAL);l.addView(pairCode);

        pairButton.setOnClickListener(v->{
            String p=phone.getText().toString().replaceAll("[^0-9]","");
            Prefs.put(this,"wa_phone",p); pairButton.setEnabled(false); pairCode.setText("");
            startBot(); ui("Iniciando motor interno…");
            bg(()->{
                WuzApiManager api=new WuzApiManager(this);
                try{
                    api.waitReady(25000);
                    ui("Conectando con los servidores de WhatsApp…");
                    String x;
                    try{
                        x=api.pairPhone(p);
                    }catch(Exception first){
                        ui("La primera conexión falló. Reiniciando motor y reintentando…");
                        restartBotEngine();
                        Thread.sleep(3500);
                        api.waitReady(30000);
                        x=api.pairPhone(p);
                    }
                    final String codeValue=x;
                    runOnUiThread(()->{
                        pairCode.setText("CÓDIGO: "+codeValue+"\n\nWhatsApp > Dispositivos vinculados > Vincular con número.");
                        status.setText("Estado: Código generado correctamente");
                    });
                }catch(Exception e){
                    ui("No se pudo generar código: "+e.getMessage());
                }finally{
                    runOnUiThread(()->pairButton.setEnabled(true));
                }
            });
        });

        l.addView(title("3. Servicio en segundo plano",18));
        Button start=button("INICIAR BOT");Button stop=button("DETENER BOT");l.addView(start);l.addView(stop);
        start.setOnClickListener(v->{Prefs.putBool(this,"auto_start",true);startBot();ui("Bot iniciado. Puede cerrar esta pantalla.");});
        stop.setOnClickListener(v->{Prefs.putBool(this,"auto_start",false);stopService(new Intent(this,BotService.class));ui("Bot detenido");});

        TextView help=title("El bot trabaja mediante una notificación persistente de Android. No necesita abrir WhatsApp ni mover la pantalla.",14);l.addView(help);
        TextView version=title("Versión 0.3.0",12);version.setGravity(Gravity.CENTER_HORIZONTAL);version.setTextColor(Color.GRAY);l.addView(version);
        setContentView(sv);
    }
    private void startBot(){Intent i=new Intent(this,BotService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);}
    private void restartBotEngine(){Intent i=new Intent(this,BotService.class);i.setAction(BotService.ACTION_RESTART_ENGINE);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);}
    private void bg(Runnable r){new Thread(r).start();}
    private void ui(String s){runOnUiThread(()->status.setText("Estado: "+s));}
}
