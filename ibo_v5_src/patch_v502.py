from pathlib import Path

p=Path('ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java')
s=p.read_text()

old='''            ImageView logo = brandLogo();
            box.addView(logo, new LinearLayout.LayoutParams(dp(360), dp(210)));'''
new='''            ImageView logo = new ImageView(this);
            logo.setImageResource(com.monopolio.mediaplayeribo.R.drawable.tv_digital_icon);
            logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
            logo.setAdjustViewBounds(true);
            logo.setPadding(dp(8),dp(4),dp(8),dp(4));
            box.addView(logo, new LinearLayout.LayoutParams(dp(420), dp(240)));'''
if old not in s:
    raise SystemExit('startup logo block not found')
s=s.replace(old,new,1)
p.write_text(s)

p=Path('ibo_independent/android/app/build.gradle')
s=p.read_text().replace("versionCode 7","versionCode 8").replace("versionName '5.0.1'","versionName '5.0.2'")
p.write_text(s)
