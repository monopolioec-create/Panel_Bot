from pathlib import Path

p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

# Use FragmentActivity: AndroidX MediaRouteButton is designed to show its dialog from a FragmentActivity.
if 'import androidx.fragment.app.FragmentActivity;' not in s:
    s=s.replace('import androidx.mediarouter.app.MediaRouteButton;', 'import androidx.fragment.app.FragmentActivity;\nimport androidx.mediarouter.app.MediaRouteButton;')
s=s.replace('import androidx.mediarouter.media.MediaRouteSelector;\n','')
if 'import android.provider.Settings;' not in s:
    s=s.replace('import android.os.Looper;', 'import android.os.Looper;\nimport android.provider.Settings;')
if 'import com.google.android.gms.cast.framework.SessionManagerListener;' not in s:
    s=s.replace('import com.google.android.gms.cast.framework.CastSession;', 'import com.google.android.gms.cast.framework.CastSession;\nimport com.google.android.gms.cast.framework.SessionManagerListener;')

s=s.replace('public class MainActivity extends Activity {','public class MainActivity extends FragmentActivity {')

# Add listener field.
needle='''    private volatile boolean catalogPreloaded = false;
    private int liveHealthGeneration = 0;'''
replacement='''    private volatile boolean catalogPreloaded = false;
    private int liveHealthGeneration = 0;
    private SessionManagerListener<CastSession> castSessionListener;'''
if needle not in s:
    raise SystemExit('field insertion point missing')
s=s.replace(needle,replacement,1)

# Replace raw Cast init in onCreate with proper CAF init + session listener.
old='''        setContentView(root);
        try { CastContext.getSharedInstance(this); } catch (Throwable ignored) {}
        identity = DeviceIdentity.read(this);'''
new='''        setContentView(root);
        initCastFramework();
        identity = DeviceIdentity.read(this);'''
if old not in s:
    raise SystemExit('onCreate cast init point missing')
s=s.replace(old,new,1)

# Replace createCastButton with CAF-only setup. No manual MediaRouteSelector.
start=s.find('    private View createCastButton(){')
end=s.find('\n    private boolean castMedia(', start)
if start < 0 or end < 0:
    raise SystemExit('createCastButton missing')
new_method='''    private View createCastButton(){
        try{
            MediaRouteButton b=new MediaRouteButton(this);
            b.setContentDescription(t("Transmitir a Chromecast","Cast to Chromecast"));
            b.setFocusable(true);
            CastContext.getSharedInstance(this);
            CastButtonFactory.setUpMediaRouteButton(getApplicationContext(),b);
            b.setOnLongClickListener(v->{openSystemCastSettings();return true;});
            return b;
        }catch(Throwable error){
            TextView fallback=focusButton("◉",20,this::openSystemCastSettings);
            fallback.setContentDescription(t("Compartir pantalla","Share screen"));
            return fallback;
        }
    }

    private void initCastFramework(){
        try{
            CastContext context=CastContext.getSharedInstance(this);
            castSessionListener=new SessionManagerListener<CastSession>(){
                @Override public void onSessionStarted(CastSession session,String sessionId){castCurrentMediaIfPossible();}
                @Override public void onSessionResumed(CastSession session,boolean wasSuspended){castCurrentMediaIfPossible();}
                @Override public void onSessionStarting(CastSession session){}
                @Override public void onSessionStartFailed(CastSession session,int error){}
                @Override public void onSessionEnding(CastSession session){}
                @Override public void onSessionEnded(CastSession session,int error){}
                @Override public void onSessionResuming(CastSession session,String sessionId){}
                @Override public void onSessionResumeFailed(CastSession session,int error){}
                @Override public void onSessionSuspended(CastSession session,int reason){}
            };
            context.getSessionManager().addSessionManagerListener(castSessionListener,CastSession.class);
        }catch(Throwable ignored){}
    }

    private void castCurrentMediaIfPossible(){
        ui.postDelayed(()->{
            try{
                if(currentPlaying==null||config==null)return;
                String url=XtreamApi.playback(config,currentPlaying,prefs.liveFormat());
                castMedia(url,currentPlaying,"live".equals(currentPlaying.kind));
                if(liveMeta!=null)liveMeta.setText(t("Reproduciendo en Chromecast","Casting to Chromecast"));
            }catch(Throwable ignored){}
        },350);
    }

    private void openSystemCastSettings(){
        try{
            Intent i=new Intent(Settings.ACTION_CAST_SETTINGS);
            startActivity(i);
            return;
        }catch(Throwable ignored){}
        try{
            Intent i=new Intent("android.settings.WIFI_DISPLAY_SETTINGS");
            startActivity(i);
            return;
        }catch(Throwable ignored){}
        try{
            startActivity(new Intent(Settings.ACTION_WIRELESS_SETTINGS));
        }catch(Throwable ignored){
            Toast.makeText(this,t("No se pudo abrir la configuración de transmisión del sistema.","Could not open system cast settings."),Toast.LENGTH_SHORT).show();
        }
    }
'''
s=s[:start]+new_method+s[end:]

# Add a visible system screen sharing tile in Settings as a fallback.
needle='''        x.add(new SettingItem("↻",t("Actualice ahora","Update now"),this::refreshNow));
        return x;'''
replacement='''        x.add(new SettingItem("◉",t("Compartir pantalla","Share screen"),this::openSystemCastSettings));
        x.add(new SettingItem("↻",t("Actualice ahora","Update now"),this::refreshNow));
        return x;'''
if needle not in s:
    raise SystemExit('settings insertion point missing')
s=s.replace(needle,replacement,1)

# Remove listener on destroy.
old='''    @Override protected void onDestroy(){releasePlayer(true);io.shutdownNow();super.onDestroy();}'''
new='''    @Override protected void onDestroy(){
        try{
            if(castSessionListener!=null)CastContext.getSharedInstance(this).getSessionManager().removeSessionManagerListener(castSessionListener,CastSession.class);
        }catch(Throwable ignored){}
        releasePlayer(true);io.shutdownNow();super.onDestroy();
    }'''
if old not in s:
    raise SystemExit('onDestroy point missing')
s=s.replace(old,new,1)

p.write_text(s)

# Manifest: multicast state helps discovery on some Wi-Fi stacks.
p=Path('ibo_independent/android/app/src/main/AndroidManifest.xml')
s=p.read_text()
if 'android.permission.CHANGE_WIFI_MULTICAST_STATE' not in s:
    s=s.replace('<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />',
                '<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />\n    <uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />')
p.write_text(s)

# Explicit Fragment dependency and version bump.
p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text()
if "androidx.fragment:fragment:" not in s:
    s=s.replace("dependencies {", "dependencies {\n    implementation 'androidx.fragment:fragment:1.8.5'")
s=s.replace("versionCode 10","versionCode 11").replace("versionName '5.0.4'","versionName '5.1.0'")
p.write_text(s)
