from pathlib import Path

main = Path("ibo_independent/android/app/src/main/java/com/monopolio/mediaplayeribo/MainActivity.java")
s = main.read_text()

s = s.replace(
"import java.util.concurrent.ConcurrentHashMap;\n",
"import java.util.concurrent.ConcurrentHashMap;\nimport java.util.concurrent.atomic.AtomicInteger;\n"
)

s = s.replace(
"    private volatile boolean catalogPreloaded = false;\n    private int liveHealthGeneration = 0;\n",
"    private volatile boolean catalogPreloaded = false;\n    private int liveHealthGeneration = 0;\n    private ProgressBar startupProgress;\n    private TextView startupProgressText;\n"
)

old = '''            ProgressBar p = new ProgressBar(this);
            box.addView(p, new LinearLayout.LayoutParams(dp(42), dp(42)));
            root.addView(box, new FrameLayout.LayoutParams(-1, -1));
'''
new = '''            ProgressBar p = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            p.setIndeterminate(true);
            p.setMax(100);
            LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(dp(430), dp(12));
            pp.topMargin = dp(10);
            box.addView(p, pp);
            root.addView(box, new FrameLayout.LayoutParams(-1, -1));
'''
if old not in s:
    raise SystemExit("activation progress pattern not found")
s = s.replace(old,new)

old = '''    private void preloadCatalogAndShowHome() {
        CountDownLatch latch = new CountDownLatch(3);
        for (String kind : new String[]{"live","movie","series"}) {
            new Thread(() -> {
                try {
                    catalogCategories.put(kind, XtreamApi.categories(config, kind));
                    catalogItems.put(kind, XtreamApi.items(config, kind));
                } catch (Exception ignored) {
                } finally { latch.countDown(); }
            }, "preload-" + kind).start();
        }
        try { latch.await(); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
        catalogPreloaded = !catalogItems.isEmpty();
        ui.post(this::showHome);
    }
'''
new = '''    private void preloadCatalogAndShowHome() {
        ui.post(this::showCatalogPreload);
        CountDownLatch latch = new CountDownLatch(3);
        AtomicInteger done = new AtomicInteger(0);
        for (String kind : new String[]{"live","movie","series"}) {
            new Thread(() -> {
                try {
                    catalogCategories.put(kind, XtreamApi.categories(config, kind));
                    catalogItems.put(kind, XtreamApi.items(config, kind));
                } catch (Exception ignored) {
                } finally {
                    int finished = done.incrementAndGet();
                    int pct = finished >= 3 ? 100 : finished * 33;
                    String label = finished == 1 ? t("TV en vivo lista", "Live TV ready")
                            : finished == 2 ? t("Películas listas", "Movies ready")
                            : t("Series listas", "Series ready");
                    ui.post(() -> updateStartupProgress(pct, label));
                    latch.countDown();
                }
            }, "preload-" + kind).start();
        }
        try { latch.await(); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
        catalogPreloaded = !catalogItems.isEmpty();
        ui.post(() -> {
            updateStartupProgress(100, t("Contenido preparado", "Content ready"));
            ui.postDelayed(this::showHome, 220);
        });
    }

    private void showCatalogPreload() {
        screen = "loading";
        releasePlayer(false);
        root.removeAllViews();
        root.setBackgroundColor(BG);

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(dp(42), dp(26), dp(42), dp(26));

        ImageView logo = new ImageView(this);
        logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        logo.setImageResource(com.monopolio.mediaplayeribo.R.drawable.tv_digital_icon);
        box.addView(logo, new LinearLayout.LayoutParams(dp(330), dp(230)));

        TextView title = tv(t("Preparando TV DIGITAL", "Preparing TV DIGITAL"), 22, TEXT, true);
        title.setGravity(Gravity.CENTER);
        box.addView(title, new LinearLayout.LayoutParams(-1, dp(52)));

        startupProgressText = tv(t("Cargando TV en vivo, películas y series…", "Loading Live TV, movies and series…"), 16, MUTED, false);
        startupProgressText.setGravity(Gravity.CENTER);
        box.addView(startupProgressText, new LinearLayout.LayoutParams(-1, dp(48)));

        startupProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        startupProgress.setIndeterminate(false);
        startupProgress.setMax(100);
        startupProgress.setProgress(5);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(460), dp(14));
        lp.topMargin = dp(8);
        box.addView(startupProgress, lp);

        root.addView(box, new FrameLayout.LayoutParams(-1, -1));
    }

    private void updateStartupProgress(int progress, String text) {
        if (startupProgress != null) startupProgress.setProgress(Math.max(0, Math.min(100, progress)));
        if (startupProgressText != null) startupProgressText.setText(text + "   " + Math.max(0, Math.min(100, progress)) + "%");
    }
'''
if old not in s:
    raise SystemExit("preload method pattern not found")
s = s.replace(old,new)

# Make brand fallback use the bundled validated logo.
s = s.replace(
'if(remote!=null&&!remote.isEmpty())ImageLoader.load(v,remote,Color.TRANSPARENT);else v.setImageResource(com.monopolio.mediaplayeribo.R.drawable.tv_digital_icon);',
'if(remote!=null&&!remote.isEmpty())ImageLoader.load(v,remote,Color.TRANSPARENT);else v.setImageResource(com.monopolio.mediaplayeribo.R.drawable.tv_digital_icon);'
)

main.write_text(s)

manifest = Path("ibo_independent/android/app/src/main/AndroidManifest.xml")
m = manifest.read_text()
if 'android:banner="@drawable/tv_digital_banner"' not in m:
    m = m.replace('android:roundIcon="@drawable/tv_digital_icon"', 'android:roundIcon="@drawable/tv_digital_icon"\n        android:banner="@drawable/tv_digital_banner"\n        android:logo="@drawable/tv_digital_icon"')
manifest.write_text(m)

gradle = Path("ibo_independent/android/app/build.gradle")
g = gradle.read_text().replace("versionCode 6","versionCode 7").replace("versionName '5.0.0'","versionName '5.1.0'")
gradle.write_text(g)
