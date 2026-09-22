from pathlib import Path

p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

old='''            ProgressBar p = new ProgressBar(this);
            box.addView(p, new LinearLayout.LayoutParams(dp(42), dp(42)));'''
new='''            ProgressBar p = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            p.setIndeterminate(true);
            LinearLayout.LayoutParams progressLp = new LinearLayout.LayoutParams(dp(440), dp(10));
            progressLp.topMargin = dp(10);
            box.addView(p, progressLp);'''
if old not in s:
    raise SystemExit('startup ProgressBar block not found')
s=s.replace(old,new,1)

s=s.replace('MediaRouteButton castButton = createCastButton();','View castButton = createCastButton();')

old_method='''    private MediaRouteButton createCastButton(){
        MediaRouteButton b=new MediaRouteButton(this);
        b.setContentDescription(t("Transmitir a Chromecast","Cast to Chromecast"));
        try{CastButtonFactory.setUpMediaRouteButton(getApplicationContext(),b);}catch(Throwable ignored){}
        b.setFocusable(true);
        return b;
    }'''
new_method='''    private View createCastButton(){
        try{
            int status=com.google.android.gms.common.GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(this);
            if(status!=com.google.android.gms.common.ConnectionResult.SUCCESS){
                TextView fallback=focusButton("◉",20,()->Toast.makeText(this,t("Chromecast no está disponible en este dispositivo","Chromecast is not available on this device"),Toast.LENGTH_SHORT).show());
                fallback.setContentDescription(t("Chromecast no disponible","Chromecast unavailable"));
                return fallback;
            }
            MediaRouteButton b=new MediaRouteButton(this);
            b.setContentDescription(t("Transmitir a Chromecast","Cast to Chromecast"));
            CastButtonFactory.setUpMediaRouteButton(getApplicationContext(),b);
            b.setFocusable(true);
            return b;
        }catch(Throwable error){
            TextView fallback=focusButton("◉",20,()->Toast.makeText(this,t("Chromecast no está disponible en este dispositivo","Chromecast is not available on this device"),Toast.LENGTH_SHORT).show());
            fallback.setContentDescription(t("Chromecast no disponible","Chromecast unavailable"));
            return fallback;
        }
    }'''
if old_method not in s:
    raise SystemExit('createCastButton method not found')
s=s.replace(old_method,new_method,1)

old='''        catalogPreloaded = !catalogItems.isEmpty();
        ui.post(this::showHome);'''
new='''        catalogPreloaded = !catalogItems.isEmpty();
        ui.post(() -> {
            try { showHome(); }
            catch (Throwable fatalUi) {
                root.removeAllViews();
                LinearLayout safe = new LinearLayout(this);
                safe.setOrientation(LinearLayout.VERTICAL);
                safe.setGravity(Gravity.CENTER);
                safe.setPadding(dp(40),dp(30),dp(40),dp(30));
                ImageView logo = brandLogo();
                safe.addView(logo,new LinearLayout.LayoutParams(dp(320),dp(190)));
                TextView msg = tv(t("TV DIGITAL está listo. Reinicia la aplicación si el dispositivo acaba de actualizar sus servicios.","TV DIGITAL is ready. Restart the app if the device has just updated its services."),17,TEXT,false);
                msg.setGravity(Gravity.CENTER);
                safe.addView(msg,new LinearLayout.LayoutParams(-1,dp(90)));
                root.addView(safe,new FrameLayout.LayoutParams(-1,-1));
            }
        });'''
if old not in s:
    raise SystemExit('preload showHome block not found')
s=s.replace(old,new,1)
p.write_text(s)

p=Path('ibo_independent/android/app/src/main/AndroidManifest.xml')
s=p.read_text()
s=s.replace('android:icon="@drawable/tv_digital_icon"','android:icon="@mipmap/ic_launcher"')
s=s.replace('android:roundIcon="@drawable/tv_digital_icon"','android:roundIcon="@mipmap/ic_launcher"')
if 'android:banner=' not in s:
    s=s.replace('android:roundIcon="@mipmap/ic_launcher"', 'android:roundIcon="@mipmap/ic_launcher"\n        android:banner="@drawable/tv_digital_banner"')
p.write_text(s)

p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text().replace("versionCode 6","versionCode 7").replace("versionName '5.0.0'","versionName '5.0.1'")
p.write_text(s)
