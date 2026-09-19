package com.monopoliorecords.bot;

import android.app.*;import android.os.*;import android.content.*;import android.graphics.Color;import android.view.*;import android.widget.*;

public class MainActivity extends Activity {
    private EditText url,code,phone; private TextView status,pairCode;
    @Override public void onCreate(Bundle b){super.onCreate(b);if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},77);build();}
    private TextView title(String s,int n){TextView t=new TextView(this);t.setText(s);t.setTextSize(n);t.setTextColor(Color.rgb(17,24,39));t.setPadding(0,16,0,8);return t;}
    private EditText input(String hint,String val){EditText e=new EditText(this);e.setHint(hint);e.setText(val);e.setSingleLine(true);return e;}
    private Button button(String s){Button b=new Button(this);b.setText(s);return b;}
    private void build(){ScrollView sv=new ScrollView(this);LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);l.setPadding(34,26,34,50);sv.addView(l);l.addView(title("MONOPOLY RECORDS",26));l.addView(title("Bot de WhatsApp",18));status=title("Estado: listo para configurar",15);l.addView(status);
        l.addView(title("1. Vincular con tu panel web",18));url=input("https://tudominio.com/monopolybot",Prefs.get(this,"panel_url",""));code=input("Código de 6 dígitos","");l.addView(url);l.addView(code);Button claim=button("Vincular panel");l.addView(claim);claim.setOnClickListener(v->bg(()->{try{new PanelClient(this).claim(url.getText().toString().trim(),code.getText().toString().trim());ui("Panel vinculado correctamente");}catch(Exception e){ui("Error panel: "+e.getMessage());}}));
        l.addView(title("2. Vincular WhatsApp",18));phone=input("Número internacional, ej. 573001234567",Prefs.get(this,"wa_phone",""));l.addView(phone);Button pair=button("Generar código WhatsApp");l.addView(pair);pairCode=title("",24);l.addView(pairCode);pair.setOnClickListener(v->{String p=phone.getText().toString().replaceAll("[^0-9]","");Prefs.put(this,"wa_phone",p);startBot();bg(()->{try{Thread.sleep(1800);String x=new WuzApiManager(this).pairPhone(p);runOnUiThread(()->pairCode.setText("Código: "+x+"\nPonlo en WhatsApp > Dispositivos vinculados > Vincular con número."));}catch(Exception e){ui("No se pudo generar código: "+e.getMessage());}});});
        l.addView(title("3. Servicio en segundo plano",18));Button start=button("INICIAR BOT");Button stop=button("DETENER BOT");l.addView(start);l.addView(stop);start.setOnClickListener(v->{Prefs.putBool(this,"auto_start",true);startBot();ui("Bot iniciado. Puede cerrar esta pantalla.");});stop.setOnClickListener(v->{Prefs.putBool(this,"auto_start",false);stopService(new Intent(this,BotService.class));ui("Bot detenido");});
        TextView help=title("El bot trabaja mediante una notificación persistente de Android. No necesita abrir WhatsApp ni mover la pantalla.",14);l.addView(help);setContentView(sv);}
    private void startBot(){Intent i=new Intent(this,BotService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);}
    private void bg(Runnable r){new Thread(r).start();}private void ui(String s){runOnUiThread(()->status.setText("Estado: "+s));}
}
