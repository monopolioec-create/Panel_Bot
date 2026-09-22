from pathlib import Path

p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text().replace("versionCode 10","versionCode 11").replace("versionName '5.0.4'","versionName '5.0.5'")
p.write_text(s)

p=Path('ibo_independent/android/app/src/main/AndroidManifest.xml')
s=p.read_text()
perm='<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
if perm not in s:
    s=s.replace('<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />',
                '<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />\n    '+perm)
p.write_text(s)

p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

if 'import androidx.mediarouter.media.MediaRouter;' not in s:
    s=s.replace('import androidx.mediarouter.media.MediaRouteSelector;', 'import androidx.mediarouter.media.MediaRouteSelector;\nimport androidx.mediarouter.media.MediaRouter;')

# Stable TV DIGITAL Chromecast button + direct route discovery.
start=s.find('    private View createCastButton(){')
end=s.find('\n    private boolean castMedia(', start)
if start < 0 or end < 0:
    raise SystemExit('createCastButton block not found')

new_block='''    private View createCastButton(){
        ImageView b=new ImageView(this);
        b.setImageResource(com.monopolio.mediaplayeribo.R.drawable.ic_cast_tv);
        b.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        b.setPadding(dp(12),dp(10),dp(12),dp(10));
        b.setBackground(round(Color.argb(185,7,31,35),ACCENT,1,10));
        b.setContentDescription(t("Chromecast","Chromecast"));
        wireAction(b,this::showCastChooser);
        b.setOnFocusChangeListener((v,h)->{
            v.setBackground(round(h?Color.rgb(17,69,75):Color.argb(185,7,31,35),h?SELECTED:ACCENT,h?2:1,10));
            v.animate().scaleX(h?1.06f:1f).scaleY(h?1.06f:1f).setDuration(90).start();
        });
        return b;
    }

    private void showCastChooser(){
        try{
            CastContext castContext=CastContext.getSharedInstance(this);
            CastSession current=castContext.getSessionManager().getCurrentCastSession();
            if(current!=null && current.isConnected()){
                String device=t("dispositivo conectado","connected device");
                try{if(current.getCastDevice()!=null && current.getCastDevice().getFriendlyName()!=null)device=current.getCastDevice().getFriendlyName();}catch(Throwable ignored){}
                final String deviceName=device;
                new AlertDialog.Builder(this)
                        .setTitle(t("Chromecast conectado","Chromecast connected"))
                        .setMessage(deviceName)
                        .setPositiveButton(t("Desconectar","Disconnect"),(d,w)->castContext.getSessionManager().endCurrentSession(true))
                        .setNegativeButton(t("Cerrar","Close"),null)
                        .show();
                return;
            }

            MediaRouter router=MediaRouter.getInstance(this);
            MediaRouteSelector selector=new MediaRouteSelector.Builder()
                    .addControlCategory(CastMediaControlIntent.categoryForCast(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID))
                    .build();

            Toast.makeText(this,t("Buscando dispositivos Chromecast…","Searching for Chromecast devices…"),Toast.LENGTH_SHORT).show();

            MediaRouter.Callback callback=new MediaRouter.Callback(){};
            router.addCallback(selector,callback,MediaRouter.CALLBACK_FLAG_REQUEST_DISCOVERY);

            ui.postDelayed(()->{
                try{
                    List<MediaRouter.RouteInfo> routes=new ArrayList<>();
                    for(MediaRouter.RouteInfo route:router.getRoutes()){
                        if(route!=null && route.isEnabled() && !route.isDefault() && route.matchesSelector(selector))routes.add(route);
                    }
                    router.removeCallback(callback);

                    if(routes.isEmpty()){
                        new AlertDialog.Builder(this)
                                .setTitle(t("Chromecast","Chromecast"))
                                .setMessage(t("No se encontraron dispositivos Chromecast disponibles. Verifica que el teléfono y el televisor estén conectados a la misma red Wi‑Fi y vuelve a intentarlo.","No Chromecast devices were found. Make sure the phone and TV are connected to the same Wi‑Fi network and try again."))
                                .setPositiveButton(t("REINTENTAR","RETRY"),(d,w)->showCastChooser())
                                .setNegativeButton(t("CERRAR","CLOSE"),null)
                                .show();
                        return;
                    }

                    String[] names=new String[routes.size()];
                    for(int i=0;i<routes.size();i++)names[i]=String.valueOf(routes.get(i).getName());

                    new AlertDialog.Builder(this)
                            .setTitle(t("Transmitir a","Cast to"))
                            .setItems(names,(d,which)->{
                                MediaRouter.RouteInfo route=routes.get(which);
                                router.selectRoute(route);
                                Toast.makeText(this,t("Conectando con ","Connecting to ")+route.getName()+"…",Toast.LENGTH_SHORT).show();
                            })
                            .setNegativeButton(t("CANCELAR","CANCEL"),null)
                            .show();
                }catch(Throwable error){
                    try{router.removeCallback(callback);}catch(Throwable ignored){}
                    Toast.makeText(this,t("No se pudo abrir el selector de Chromecast.","Could not open the Chromecast selector."),Toast.LENGTH_SHORT).show();
                }
            },1400);
        }catch(Throwable error){
            Toast.makeText(this,t("Chromecast no pudo inicializarse. Intenta nuevamente.","Chromecast could not initialize. Try again."),Toast.LENGTH_SHORT).show();
        }
    }
'''
s=s[:start]+new_block+s[end:]

# Show the real build version in the UI, never a hardcoded old version.
s=s.replace('TextView ver = tv("v2.0", 14, MUTED, false);','TextView ver = tv("v"+BuildConfig.VERSION_NAME, 14, MUTED, false);')
old_footer='footer = tv(t("OK: abrir    •    Mantén OK: favorito    •    BACK: casa", "OK: open    •    Hold OK: favorite    •    BACK: home"), 13, MUTED, false);'
if old_footer in s:
    s=s.replace(old_footer,'footer = tv(t("OK: abrir    •    Mantén OK: favorito    •    BACK: casa", "OK: open    •    Hold OK: favorite    •    BACK: home")+"    •    v"+BuildConfig.VERSION_NAME, 13, MUTED, false);',1)

# Keep Cast receiver session alive when phone goes to background / screen locks.
if 'private boolean hasActiveCastSession()' not in s:
    anchor='''    private void saveCurrentResume(){if(player!=null&&currentPlaying!=null&&!"live".equals(currentPlayingKind)){try{prefs.saveResume(currentPlayingKind,currentPlaying.id,player.getCurrentPosition());}catch(Throwable ignored){}}}'''
    addition='''    private boolean hasActiveCastSession(){
        try{
            CastSession session=CastContext.getSharedInstance(this).getSessionManager().getCurrentCastSession();
            return session!=null && session.isConnected();
        }catch(Throwable ignored){return false;}
    }
'''
    if anchor not in s:
        raise SystemExit('saveCurrentResume anchor not found')
    s=s.replace(anchor, addition+anchor,1)

old='''    @Override protected void onPause(){saveCurrentResume();super.onPause();}
    @Override protected void onDestroy(){releasePlayer(true);io.shutdownNow();super.onDestroy();}'''
new='''    @Override protected void onPause(){
        saveCurrentResume();
        super.onPause();
    }
    @Override protected void onStop(){
        super.onStop();
    }
    @Override protected void onDestroy(){
        releasePlayer(true);
        io.shutdownNow();
        super.onDestroy();
    }'''
if old in s:
    s=s.replace(old,new,1)

p.write_text(s)
