#!/usr/bin/env python3
"""Add a native app-level button that expands the embedded video frame."""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def once(old, new, label):
    global s
    if new in s:
        return
    if old not in s:
        raise SystemExit(f"Required fullscreen-button anchor missing: {label}")
    s = s.replace(old, new, 1)

once(
    "    private Button cleanButton, filterButton, playerButton, moreButton, refreshButton;",
    "    private Button cleanButton, filterButton, playerButton, moreButton, refreshButton;\n"
    "    private View appHeader, appTitleBar;\n"
    "    private Button videoFullscreenButton, exitVideoFullscreenButton;\n"
    "    private FrameLayout videoFullscreenOverlay;\n"
    "    private int savedVideoFullscreenUi = 0;\n"
    "    private boolean videoFullscreenMode = false;",
    "fullscreen state fields")

once(
    '        Button search=button("⌕",true);search.setTextSize(20);search.setOnClickListener(v->searchDialog());',
    '        videoFullscreenButton=button("⛶",true);videoFullscreenButton.setTextSize(20);\n'
    '        videoFullscreenButton.setContentDescription("Открыть видео на весь экран");\n'
    '        videoFullscreenButton.setOnClickListener(v->enterVideoFullscreenMode());\n'
    '        LinearLayout.LayoutParams vfp=new LinearLayout.LayoutParams(dp(48),dp(42));vfp.leftMargin=dp(6);header.addView(videoFullscreenButton,vfp);\n'
    '        Button search=button("⌕",true);search.setTextSize(20);search.setOnClickListener(v->searchDialog());',
    "fullscreen header button")
once("        root.addView(header);", "        appHeader=header;\n        root.addView(header);", "save header")
once("        root.addView(bar);", "        appTitleBar=bar;\n        root.addView(bar);", "save title bar")

methods = r'''    // App-level fullscreen fallback: expands the embedded VK/OK iframe itself,
    // without relying on the broken native controls inside the cross-origin player.
    private void enterVideoFullscreenMode() {
        if (web == null || videoFullscreenMode || customView != null) return;
        videoFullscreenMode = true;
        if (appHeader != null) appHeader.setVisibility(View.GONE);
        if (appTitleBar != null) appTitleBar.setVisibility(View.GONE);
        if (bottomNav != null) bottomNav.setVisibility(View.GONE);
        savedVideoFullscreenUi = getWindow().getDecorView().getSystemUiVisibility();
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        FrameLayout decor = (FrameLayout)getWindow().getDecorView();
        videoFullscreenOverlay = new FrameLayout(this);
        videoFullscreenOverlay.setClipChildren(false);
        videoFullscreenOverlay.setClipToPadding(false);
        exitVideoFullscreenButton = button("Выйти", false);
        exitVideoFullscreenButton.setContentDescription("Выйти из полноэкранного режима видео");
        exitVideoFullscreenButton.setOnClickListener(v -> exitVideoFullscreenMode());
        FrameLayout.LayoutParams exitParams = new FrameLayout.LayoutParams(dp(104), dp(52), Gravity.TOP | Gravity.END);
        exitParams.setMargins(0, dp(18), dp(18), 0);
        videoFullscreenOverlay.addView(exitVideoFullscreenButton, exitParams);
        decor.addView(videoFullscreenOverlay, new FrameLayout.LayoutParams(-1, -1));

        web.postDelayed(() -> {
            if (!videoFullscreenMode || web == null) return;
            String js = "(function(){try{" +
                "var old=document.getElementById('rufilm-app-video-fullscreen-style');if(old)old.remove();" +
                "var nodes=[].slice.call(document.querySelectorAll('iframe,video')).filter(function(e){var r=e.getBoundingClientRect();" +
                "if(r.width<120||r.height<70)return false;if(e.tagName==='VIDEO')return true;" +
                "var u=(e.src||e.getAttribute('src')||'')+' '+(e.title||'');return /vk|ok\\.ru|video|player|embed/i.test(u);});" +
                "nodes.sort(function(a,b){var x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return y.width*y.height-x.width*x.height;});" +
                "var target=nodes[0];if(!target)return false;target.setAttribute('data-rufilm-app-video-fullscreen','1');" +
                "target.scrollIntoView({block:'center',inline:'center'});" +
                "var st=document.createElement('style');st.id='rufilm-app-video-fullscreen-style';" +
                "st.textContent='html,body{background:#000!important;overflow:hidden!important}iframe[data-rufilm-app-video-fullscreen=\\\"1\\\"],video[data-rufilm-app-video-fullscreen=\\\"1\\\"]{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;max-width:none!important;max-height:none!important;min-width:100vw!important;min-height:100vh!important;margin:0!important;border:0!important;z-index:2147483647!important;object-fit:contain!important}';" +
                "(document.head||document.documentElement).appendChild(st);return true;" +
                "}catch(e){return false;}})()";
            web.evaluateJavascript(js, null);
            web.requestFocus();
        }, 120L);
    }

    private void exitVideoFullscreenMode() {
        if (!videoFullscreenMode) return;
        videoFullscreenMode = false;
        if (web != null) web.evaluateJavascript("(function(){var s=document.getElementById('rufilm-app-video-fullscreen-style');if(s)s.remove();document.querySelectorAll('[data-rufilm-app-video-fullscreen]').forEach(function(e){e.removeAttribute('data-rufilm-app-video-fullscreen');});document.documentElement.style.removeProperty('overflow');document.body.style.removeProperty('overflow');})()", null);
        if (videoFullscreenOverlay != null) {
            ViewGroup parent = (ViewGroup)videoFullscreenOverlay.getParent();
            if (parent != null) parent.removeView(videoFullscreenOverlay);
        }
        videoFullscreenOverlay = null;
        exitVideoFullscreenButton = null;
        if (appHeader != null) appHeader.setVisibility(View.VISIBLE);
        if (appTitleBar != null) appTitleBar.setVisibility(View.VISIBLE);
        if (bottomNav != null) bottomNav.setVisibility(View.VISIBLE);
        getWindow().getDecorView().setSystemUiVisibility(savedVideoFullscreenUi);
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (web != null) web.requestFocus();
    }

'''
once("    private int getAudioSyncOffsetMs() {", methods + "    private int getAudioSyncOffsetMs() {", "fullscreen methods")
once(
    "    @Override public void onBackPressed(){if(customView!=null){hideCustomView();return;}if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}",
    "    @Override public void onBackPressed(){if(videoFullscreenMode){exitVideoFullscreenMode();return;}if(customView!=null){hideCustomView();return;}if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}",
    "back exits app fullscreen")
p.write_text(s, encoding="utf-8")
print("Applied app-level video fullscreen button to", p)
