package com.monopoliorecords.bot;
import android.content.*;import android.os.Build;
public class BootReceiver extends BroadcastReceiver{
 @Override public void onReceive(Context c,Intent i){if(Prefs.getBool(c,"auto_start",false)){Intent s=new Intent(c,BotService.class);if(Build.VERSION.SDK_INT>=26)c.startForegroundService(s);else c.startService(s);}}
}
