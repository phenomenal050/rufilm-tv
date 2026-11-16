#!/usr/bin/env python3
from pathlib import Path
import cairosvg
from PIL import Image, ImageDraw

root = Path("rufilm-tv-2.9/app/src/main")
res = root / "res"
source = Path("patches/rufilm_brand.svg").read_text(encoding="utf-8")

def render_square(svg_text, name):
    src=Path("/tmp")/(name+".svg"); out=Path("/tmp")/(name+".png")
    src.write_text(svg_text,encoding="utf-8")
    cairosvg.svg2png(url=str(src),write_to=str(out),output_width=512,output_height=512)
    return Image.open(out).convert("RGBA")

dark_icon=render_square(source,"rufilm_dark")
light=source.replace('stop-color="#29292c"','stop-color="#fff0d9"').replace('stop-color="#101012"','stop-color="#e8cfad"').replace('fill="#f5f2ed"','fill="#171719"').replace('fill="#eee9e0"','fill="#27221c"')
light_icon=render_square(light,"rufilm_light")

for density,size in [("mdpi",48),("hdpi",72),("xhdpi",96),("xxhdpi",144),("xxxhdpi",192)]:
    for suffix,art in [("",light_icon),("-night",dark_icon)]:
        folder=res/(f"mipmap-night-{density}" if suffix else f"mipmap-{density}")
        folder.mkdir(parents=True,exist_ok=True)
        art.resize((size,size),Image.Resampling.LANCZOS).save(folder/"ic_launcher.png")

for suffix,art,bg,fgname in [
    ("",light_icon,"#f5e3c9","ic_launcher_foreground"),
    ("-night",dark_icon,"#171719","ic_launcher_foreground_dark")]:
    folder=res/("mipmap-night-anydpi-v26" if suffix else "mipmap-anydpi-v26")
    folder.mkdir(parents=True,exist_ok=True)
    fg=res/"mipmap-xxxhdpi";fg.mkdir(parents=True,exist_ok=True)
    art.resize((192,192),Image.Resampling.LANCZOS).save(fg/(fgname+".png"))
    (folder/"ic_launcher.xml").write_text(
      f'<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/rufilm_icon_background{ "_night" if suffix else "" }"/><foreground android:drawable="@mipmap/{fgname}"/></adaptive-icon>',encoding="utf-8")

colors=res/"values/colors.xml";colors.parent.mkdir(parents=True,exist_ok=True)
old=colors.read_text(encoding="utf-8") if colors.exists() else "<resources></resources>"
import re
old=re.sub(r'<color name="rufilm_icon_background">.*?</color>','',old)
old=old.replace("</resources>",'<color name="rufilm_icon_background">#f5e3c9</color></resources>')
colors.write_text(old,encoding="utf-8")
night=res/"values-night/colors.xml";night.parent.mkdir(parents=True,exist_ok=True)
night.write_text('<resources><color name="rufilm_icon_background_night">#171719</color></resources>',encoding="utf-8")

# Install the exact selected Android TV banners; do not redraw or alter the play logo.
import shutil
for suffix, filename in [("", "rufilm_tv_banner_light.webp"),
                          ("-night", "rufilm_tv_banner_dark.webp")]:
    folder = res / ("drawable-night-nodpi" if suffix else "drawable-nodpi")
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path("patches") / filename, folder / "rufilm_tv_banner.webp")

# Manifest launcher metadata
import xml.etree.ElementTree as ET
manifests=list(root.rglob("AndroidManifest.xml"))
if not manifests: raise SystemExit("AndroidManifest.xml not found")
manifest=manifests[0]
ET.register_namespace("android","http://schemas.android.com/apk/res/android")
ET.register_namespace("tools","http://schemas.android.com/tools")
tree=ET.parse(manifest);mx=tree.getroot();a="{http://schemas.android.com/apk/res/android}"
app=mx.find("application")
if app is None: raise SystemExit("application element not found")
app.set(a+"icon","@mipmap/ic_launcher");app.set(a+"roundIcon","@mipmap/ic_launcher");app.set(a+"banner","@drawable/rufilm_tv_banner");app.set(a+"label","RUFILM TV")
for comp in list(app):
    if comp.tag not in ("activity","activity-alias"): continue
    for intent in comp.findall("intent-filter"):
        acts=[x.get(a+"name") for x in intent.findall("action")]
        cats=[x.get(a+"name") for x in intent.findall("category")]
        if "android.intent.action.MAIN" in acts and "android.intent.category.LEANBACK_LAUNCHER" not in cats:
            ET.SubElement(intent,"category",{a+"name":"android.intent.category.LEANBACK_LAUNCHER"})
features={x.get(a+"name") for x in mx.findall("uses-feature")}
for feature in ("android.software.leanback","android.hardware.touchscreen"):
    if feature not in features: ET.SubElement(mx,"uses-feature",{a+"name":feature,a+"required":"false"})
tree.write(manifest,encoding="utf-8",xml_declaration=True)
print("Square launcher icons retained; full-bleed horizontal ATV banners installed.")
