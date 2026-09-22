from pathlib import Path

p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

if 'import androidx.mediarouter.media.MediaRouteSelector;' not in s:
    s=s.replace('import androidx.mediarouter.app.MediaRouteButton;', 'import androidx.mediarouter.app.MediaRouteButton;\nimport androidx.mediarouter.media.MediaRouteSelector;')
if 'import com.google.android.gms.cast.CastMediaControlIntent;' not in s:
    s=s.replace('import com.google.android.gms.cast.MediaInfo;', 'import com.google.android.gms.cast.CastMediaControlIntent;\nimport com.google.android.gms.cast.MediaInfo;')

needle='''        root = new FrameLayout(this);
        root.setBackgroundColor(BG);
        setContentView(root);'''
replacement='''        root = new FrameLayout(this);
        root.setBackgroundColor(BG);
        setContentView(root);
        try { CastContext.getSharedInstance(this); } catch (Throwable ignored) {}'''
if needle not in s:
    raise SystemExit('onCreate insertion point not found')
s=s.replace(needle,replacement,1)

start=s.find('    private View createCastButton(){')
end=s.find('\n    private boolean castMedia(', start)
if start < 0 or end < 0:
    raise SystemExit('createCastButton block not found')
new_method='''    private View createCastButton(){
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
        }catch(Throwable first){
            try{
                MediaRouteSelector selector=new MediaRouteSelector.Builder()
                        .addControlCategory(CastMediaControlIntent.categoryForCast(CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID))
                        .build();
                b.setRouteSelector(selector);
            }catch(Throwable ignored){}
        }
        return b;
    }
'''
s=s[:start]+new_method+s[end:]
s=s.replace('GoogleApiAvailability','GoogleApiAvailability_REMOVED')
p.write_text(s)

p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text().replace("versionCode 8","versionCode 9").replace("versionName '5.0.2'","versionName '5.0.3'")
p.write_text(s)
