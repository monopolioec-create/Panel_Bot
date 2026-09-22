from pathlib import Path

p=Path("ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java")
s=p.read_text()

for line in [
    "import androidx.mediarouter.app.MediaRouteButton;\n",
    "import com.google.android.gms.cast.MediaInfo;\n",
    "import com.google.android.gms.cast.MediaMetadata;\n",
    "import com.google.android.gms.cast.framework.CastButtonFactory;\n",
    "import com.google.android.gms.cast.framework.CastContext;\n",
    "import com.google.android.gms.cast.framework.CastSession;\n",
    "import com.google.android.gms.cast.framework.media.RemoteMediaClient;\n",
    "import com.google.android.gms.cast.MediaLoadRequestData;\n",
]:
    s=s.replace(line,"")

s=s.replace(
'''        MediaRouteButton castButton = createCastButton();
        top.addView(castButton, new LinearLayout.LayoutParams(dp(58), dp(54)));
''',
'''        TextView castButton = focusButton("◫", 21, this::openCastSettings);
        castButton.setContentDescription(t("Transmitir pantalla", "Cast screen"));
        top.addView(castButton, new LinearLayout.LayoutParams(dp(58), dp(54)));
''')

s=s.replace(
'''        MediaRouteButton castButton = createCastButton();
        bar.addView(castButton, new LinearLayout.LayoutParams(dp(48), dp(42)));
''',
'''        TextView castButton = focusButton("◫", 18, this::openCastSettings);
        castButton.setContentDescription(t("Transmitir pantalla", "Cast screen"));
        bar.addView(castButton, new LinearLayout.LayoutParams(dp(48), dp(42)));
''')

start=s.find("    private MediaRouteButton createCastButton(){")
end=s.find("    private void scheduleLiveHealthCheck", start)
if start < 0 or end < 0:
    raise SystemExit("cast method block not found")
replacement='''    private void openCastSettings(){
        try{
            Intent i=new Intent("android.settings.CAST_SETTINGS");
            startActivity(i);
        }catch(Exception first){
            try{
                Intent i=new Intent("android.settings.WIFI_DISPLAY_SETTINGS");
                startActivity(i);
            }catch(Exception second){
                Toast.makeText(this,t("La función de transmisión no está disponible en este dispositivo","Casting is not available on this device"),Toast.LENGTH_LONG).show();
            }
        }
    }

    private boolean castMedia(String url,XtreamApi.Item item,boolean live){
        // Android system screen-casting mirrors the local player automatically.
        return false;
    }

'''
s=s[:start]+replacement+s[end:]
p.write_text(s)

manifest=Path("ibo_independent/android/app/src/main/AndroidManifest.xml")
m=manifest.read_text()
m=m.replace('        <meta-data android:name="com.google.android.gms.cast.framework.OPTIONS_PROVIDER_CLASS_NAME" android:value="com.monopolio.mediaplayeribo.CastOptionsProvider" />\n','')
manifest.write_text(m)

gradle=Path("ibo_independent/android/app/build.gradle")
g=gradle.read_text()
g=g.replace("    implementation 'com.google.android.gms:play-services-cast-framework:22.3.1'\n","")
g=g.replace("versionCode 7","versionCode 8").replace("versionName '5.1.0'","versionName '5.1.1'")
gradle.write_text(g)
