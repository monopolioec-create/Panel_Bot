from pathlib import Path

# Fix MainActivity Cast button to use CAF exactly as documented.
p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

# Remove manual MediaRouteSelector import if present.
s=s.replace('import androidx.mediarouter.media.MediaRouteSelector;\n','')

start=s.find('    private View createCastButton(){')
end=s.find('\n    private boolean castMedia(', start)
if start < 0 or end < 0:
    raise SystemExit('createCastButton block not found')

new_method='''    private View createCastButton(){
        try{
            MediaRouteButton b=new MediaRouteButton(this);
            b.setContentDescription(t("Transmitir a Chromecast","Cast to Chromecast"));
            b.setFocusable(true);
            CastContext.getSharedInstance(this);
            CastButtonFactory.setUpMediaRouteButton(getApplicationContext(), b);
            return b;
        }catch(Throwable castUiError){
            TextView fallback=focusButton("◉",20,()->{
                try{
                    CastContext.getSharedInstance(this);
                    Toast.makeText(this,t("Chromecast se está inicializando. Intenta nuevamente.","Chromecast is initializing. Try again."),Toast.LENGTH_SHORT).show();
                }catch(Throwable ignored){
                    Toast.makeText(this,t("No fue posible iniciar Chromecast.","Could not initialize Chromecast."),Toast.LENGTH_SHORT).show();
                }
            });
            fallback.setContentDescription(t("Chromecast","Chromecast"));
            return fallback;
        }
    }
'''
s=s[:start]+new_method+s[end:]
p.write_text(s)

# CastOptionsProvider: let CAF own discovery and enable Android 13+ system output switcher.
p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/CastOptionsProvider.java')
s=p.read_text()
old='''        return new CastOptions.Builder()
                .setReceiverApplicationId(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID)
                .build();'''
new='''        return new CastOptions.Builder()
                .setReceiverApplicationId(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID)
                .setShowSystemOutputSwitcherOnCastIconClick(true)
                .build();'''
if old not in s:
    raise SystemExit('CastOptions builder block not found')
s=s.replace(old,new,1)
p.write_text(s)

# Manifest: MediaTransferReceiver supports Android 13+ output switching.
p=Path('ibo_independent/android/app/src/main/AndroidManifest.xml')
s=p.read_text()
receiver='''        <receiver
            android:name="androidx.mediarouter.media.MediaTransferReceiver"
            android:exported="true" />
'''
if 'androidx.mediarouter.media.MediaTransferReceiver' not in s:
    marker='''        <meta-data android:name="com.google.android.gms.cast.framework.OPTIONS_PROVIDER_CLASS_NAME" android:value="com.monopolio.mediaplayeribo.CastOptionsProvider" />
'''
    s=s.replace(marker, marker+receiver)
p.write_text(s)

# Explicit mediarouter dependency + version bump.
p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text()
if "androidx.mediarouter:mediarouter" not in s:
    s=s.replace("implementation 'com.google.android.gms:play-services-cast-framework:22.3.1'",
                "implementation 'com.google.android.gms:play-services-cast-framework:22.3.1'\n    implementation 'androidx.mediarouter:mediarouter:1.8.1'")
s=s.replace("versionCode 10","versionCode 11").replace("versionName '5.0.4'","versionName '5.1.0'")
s=s.replace("versionCode 9","versionCode 11").replace("versionName '5.0.3'","versionName '5.1.0'")
p.write_text(s)
