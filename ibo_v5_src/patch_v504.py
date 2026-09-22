from pathlib import Path

p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

start=s.find('    private View createCastButton(){')
end=s.find('\n    private boolean castMedia(', start)
if start < 0 or end < 0:
    raise SystemExit('createCastButton block not found')

new_method='''    private View createCastButton(){
        try{
            MediaRouteButton b=new MediaRouteButton(this);
            b.setContentDescription(t("Transmitir a Chromecast","Cast to Chromecast"));
            b.setFocusable(true);
            try{
                MediaRouteSelector selector=new MediaRouteSelector.Builder()
                        .addControlCategory(CastMediaControlIntent.categoryForCast(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID))
                        .build();
                b.setRouteSelector(selector);
                CastContext.getSharedInstance(this);
                CastButtonFactory.setUpMediaRouteButton(this,b);
            }catch(Throwable setupError){
                try{
                    MediaRouteSelector selector=new MediaRouteSelector.Builder()
                            .addControlCategory(CastMediaControlIntent.categoryForCast(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID))
                            .build();
                    b.setRouteSelector(selector);
                }catch(Throwable ignored){}
            }
            return b;
        }catch(Throwable constructorError){
            TextView fallback=focusButton("◉",20,()->{
                try{
                    CastContext.getSharedInstance(this);
                    Toast.makeText(this,t("Chromecast se está inicializando. Intenta nuevamente en unos segundos.","Chromecast is initializing. Try again in a few seconds."),Toast.LENGTH_SHORT).show();
                }catch(Throwable ignored){
                    Toast.makeText(this,t("Chromecast no pudo inicializarse en este dispositivo.","Chromecast could not initialize on this device."),Toast.LENGTH_SHORT).show();
                }
            });
            fallback.setContentDescription(t("Chromecast","Chromecast"));
            return fallback;
        }
    }
'''
s=s[:start]+new_method+s[end:]

# Never leave the user stranded on the old generic fallback.
old='''                TextView msg = tv(t("TV DIGITAL está listo. Reinicia la aplicación si el dispositivo acaba de actualizar sus servicios.","TV DIGITAL is ready. Restart the app if the device has just updated its services."),17,TEXT,false);
                msg.setGravity(Gravity.CENTER);
                safe.addView(msg,new LinearLayout.LayoutParams(-1,dp(90)));
                root.addView(safe,new FrameLayout.LayoutParams(-1,-1));'''
new='''                TextView msg = tv(t("TV DIGITAL encontró un problema al cargar la pantalla principal.","TV DIGITAL found a problem loading the home screen."),17,TEXT,false);
                msg.setGravity(Gravity.CENTER);
                safe.addView(msg,new LinearLayout.LayoutParams(-1,dp(70)));
                TextView retry = actionButton(t("REINTENTAR","RETRY"), this::showHome);
                safe.addView(retry,new LinearLayout.LayoutParams(dp(220),dp(52)));
                root.addView(safe,new FrameLayout.LayoutParams(-1,-1));'''
if old in s:
    s=s.replace(old,new,1)

p.write_text(s)

p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text().replace("versionCode 9","versionCode 10").replace("versionName '5.0.3'","versionName '5.0.4'")
p.write_text(s)
