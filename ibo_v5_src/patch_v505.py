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

# Make lifecycle intent explicit: local player state may pause, but active Cast session is never ended on background/screen lock.
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

# onPause/onStop must not stop or disconnect Cast. Keep only local-state bookkeeping.
old='''    @Override protected void onPause(){saveCurrentResume();super.onPause();}
    @Override protected void onDestroy(){releasePlayer(true);io.shutdownNow();super.onDestroy();}'''
new='''    @Override protected void onPause(){
        saveCurrentResume();
        // Chromecast playback runs on the receiver. Never end the Cast session when the phone is locked/backgrounded.
        super.onPause();
    }
    @Override protected void onStop(){
        // Intentionally keep the Cast session alive. ReconnectionService + saved-session resume handle background/sleep.
        super.onStop();
    }
    @Override protected void onDestroy(){
        // Only release the local ExoPlayer. Do not call endCurrentSession() or stop the receiver.
        releasePlayer(true);
        io.shutdownNow();
        super.onDestroy();
    }'''
if old not in s:
    raise SystemExit('lifecycle block not found')
s=s.replace(old,new,1)
p.write_text(s)
