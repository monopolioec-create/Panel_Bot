from pathlib import Path
import re

root=Path("ibo_independent/android")
main=root/"app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java"
s=main.read_text()

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
    "private EditText searchBox;\n    private int heroGeneration = 0;",
    "private EditText searchBox;\n    private ProgressBar startupProgress;\n    private TextView startupProgressText;\n    private int heroGeneration = 0;"
)
s=s.replace("MediaRouteButton castButton = createCastButton();","View castButton = createCastButton();")

old="""            ProgressBar p = new ProgressBar(this);
            box.addView(p, new LinearLayout.LayoutParams(dp(42), dp(42)));
            root.addView(box, new FrameLayout.LayoutParams(-1, -1));"""
new="""            startupProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            startupProgress.setMax(100);
            startupProgress.setProgress(8);
            startupProgress.setIndeterminate(false);
            LinearLayout.LayoutParams barLp = new LinearLayout.LayoutParams(dp(430), dp(12));
            barLp.topMargin = dp(8);
            box.addView(startupProgress, barLp);
            startupProgressText = tv(t("Preparando TV DIGITAL…", "Preparing TV DIGITAL…") + "  8%", 14, MUTED, false);
            startupProgressText.setGravity(Gravity.CENTER);
            box.addView(startupProgressText, new LinearLayout.LayoutParams(-1, dp(42)));
            root.addView(box, new FrameLayout.LayoutParams(-1, -1));"""
if old not in s:
    raise SystemExit("activation progress block not found")
s=s.replace(old,new)

m=re.search(r"    private void preloadCatalogAndShowHome\(\) \{.*?\n    \}\n\n    private List<XtreamApi.Category> cachedCategories",s,re.S)
if not m:
    raise SystemExit("preload method not found")
replacement="""    private void preloadCatalogAndShowHome() {
        updateStartupProgress(12, t("Preparando contenido…", "Preparing content…"));
        final java.util.concurrent.atomic.AtomicInteger done = new java.util.concurrent.atomic.AtomicInteger(0);
        CountDownLatch latch = new CountDownLatch(3);
        for (String kind : new String[]{"live","movie","series"}) {
            new Thread(() -> {
                try {
                    catalogCategories.put(kind, XtreamApi.categories(config, kind));
                    catalogItems.put(kind, XtreamApi.items(config, kind));
                } catch (Exception ignored) {
                } finally {
                    int n=done.incrementAndGet();
                    int pct=12 + n*29;
                    String label = n==1 ? t("TV en vivo preparada", "Live TV ready") : n==2 ? t("Películas preparadas", "Movies ready") : t("Series preparadas", "Series ready");
                    updateStartupProgress(Math.min(99,pct), label);
                    latch.countDown();
                }
            }, "preload-" + kind).start();
        }
        try { latch.await(); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
        catalogPreloaded = !catalogItems.isEmpty();
        updateStartupProgress(100, t("Contenido listo", "Content ready"));
        ui.postDelayed(this::showHome, 220);
    }

    private void updateStartupProgress(int percent,String label){
        ui.post(() -> {
            if(startupProgress!=null){startupProgress.setIndeterminate(false);startupProgress.setProgress(Math.max(0,Math.min(100,percent)));}
            if(startupProgressText!=null)startupProgressText.setText(label+"  "+percent+"%");
        });
    }

    private List<XtreamApi.Category> cachedCategories"""
s=s[:m.start()]+replacement+s[m.end():]

m=re.search(r"    private MediaRouteButton createCastButton\(\)\{.*?\n    private void scheduleLiveHealthCheck",s,re.S)
if not m:
    raise SystemExit("cast block not found")
cast="""    private View createCastButton(){
        TextView b=focusButton("◉",21,this::openSystemCast);
        b.setContentDescription(t("Transmitir pantalla", "Cast screen"));
        return b;
    }

    private void openSystemCast(){
        try{
            startActivity(new Intent("android.settings.CAST_SETTINGS"));
        }catch(Throwable first){
            try{
                startActivity(new Intent("android.settings.WIFI_DISPLAY_SETTINGS"));
            }catch(Throwable second){
                Toast.makeText(this,t("La transmisión inalámbrica no está disponible en este dispositivo.","Wireless casting is not available on this device."),Toast.LENGTH_LONG).show();
            }
        }
    }

    private boolean castMedia(String url,XtreamApi.Item item,boolean live){ return false; }

    private void scheduleLiveHealthCheck"""
s=s[:m.start()]+cast+s[m.end():]
main.write_text(s)

(root/"app/build.gradle").write_text("""plugins { id 'com.android.application' }
def panelApiUrl = providers.gradleProperty('PANEL_API_URL').getOrElse('https://ap24.top/ibo/index.php')
android {
    namespace 'com.monopolio.mediaplayeribo'
    compileSdk 35
    defaultConfig {
        applicationId 'com.monopolio.mediaplayeribo'
        minSdk 23
        targetSdk 35
        versionCode 7
        versionName '5.1.0'
        buildConfigField 'String', 'PANEL_API_URL', '"' + panelApiUrl + '"'
        buildConfigField 'String', 'PANEL_APP_KEY', '"GELQV-YktQ03TB6_VsSWOyFDfJBJuTT65M25YUG8O58"'
    }
    buildFeatures { buildConfig true }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}
dependencies {
    implementation 'androidx.media3:media3-exoplayer:1.5.1'
    implementation 'androidx.media3:media3-exoplayer-hls:1.5.1'
    implementation 'androidx.media3:media3-ui:1.5.1'
    implementation 'androidx.mediarouter:mediarouter:1.8.1'
}
""")

manifest=root/"app/src/main/AndroidManifest.xml"
manifest.write_text("""<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <queries><intent><action android:name="android.intent.action.VIEW" /><data android:mimeType="video/*" /></intent></queries>
    <application
        android:allowBackup="false"
        android:usesCleartextTraffic="true"
        android:label="TV DIGITAL"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:banner="@drawable/tv_digital_banner"
        android:theme="@style/AppTheme"
        android:networkSecurityConfig="@xml/network_security_config">
        <activity android:name=".MainActivity" android:screenOrientation="landscape" android:configChanges="keyboard|keyboardHidden|orientation|screenSize" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
                <category android:name="android.intent.category.LEANBACK_LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""")

(root/"app/src/main/res/mipmap-anydpi-v26").mkdir(parents=True,exist_ok=True)
(root/"app/src/main/res/mipmap").mkdir(parents=True,exist_ok=True)
(root/"app/src/main/res/values").mkdir(parents=True,exist_ok=True)
(root/"app/src/main/res/values/launcher_colors.xml").write_text('<resources><color name="launcher_bg">#000000</color></resources>')
adaptive='''<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/launcher_bg"/><foreground android:drawable="@drawable/tv_digital_icon"/></adaptive-icon>'''
(root/"app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml").write_text(adaptive)
(root/"app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml").write_text(adaptive)
legacy='''<layer-list xmlns:android="http://schemas.android.com/apk/res/android"><item android:drawable="@color/launcher_bg"/><item><bitmap android:src="@drawable/tv_digital_icon" android:gravity="center"/></item></layer-list>'''
(root/"app/src/main/res/mipmap/ic_launcher.xml").write_text(legacy)
(root/"app/src/main/res/mipmap/ic_launcher_round.xml").write_text(legacy)
(root/"app/src/main/res/drawable/tv_digital_banner.xml").write_text(legacy)
