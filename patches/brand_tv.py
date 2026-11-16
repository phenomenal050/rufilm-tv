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

# Full-bleed 16:9 Android TV banner: same play mark and wordmark, composed horizontally.
def banner_svg(dark_mode):
    bg1,bg2,main,sub=("#29292c","#101012","#f5f2ed","#eee9e0") if dark_mode else ("#fff0d9","#e8cfad","#171719","#27221c")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
    <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient>
    <linearGradient id="red" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ff795c"/><stop offset=".42" stop-color="#ff302d"/><stop offset="1" stop-color="#d90017"/></linearGradient>
    <linearGradient id="cream" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff1dc"/><stop offset="1" stop-color="#d9b98e"/></linearGradient></defs>
    <rect width="960" height="540" rx="76" fill="url(#bg)"/>
    <path d="M155 92 C137 78 112 94 112 122 L112 416 C112 451 141 469 171 449 L350 325 L350 213 Z" fill="url(#cream)"/>
    <path d="M158 78 C181 64 207 73 235 91 L485 235 C531 262 531 310 485 337 L235 481 C201 501 166 481 166 444 L166 382 L335 286 L179 197 C145 178 135 101 158 78 Z" fill="url(#red)"/>
    <path d="M166 382 L335 286 L166 190 Z" fill="{bg2}"/>
    <path d="M158 78 C181 64 207 73 235 91 L260 105 C217 83 181 95 181 133 L181 430 C181 454 174 470 158 475 C140 466 126 451 126 418 L126 128 C126 105 139 88 158 78 Z" fill="url(#cream)" opacity=".62"/>
    <text x="570" y="257" text-anchor="middle" font-family="DejaVu Sans,Arial,sans-serif" font-size="100" font-weight="700" letter-spacing="-5" fill="{main}">RUFILM <tspan fill="#f22b31">TV</tspan></text>
    <text x="575" y="340" text-anchor="middle" font-family="DejaVu Sans,Arial,sans-serif" font-size="39" font-weight="500" letter-spacing="5" fill="{sub}">ТВОЙ ОНЛАЙН</text>
    <text x="575" y="395" text-anchor="middle" font-family="DejaVu Sans,Arial,sans-serif" font-size="39" font-weight="500" letter-spacing="5" fill="{sub}">КИНОТЕАТР</text></svg>'''

for suffix,is_dark in [("",False),("-night",True)]:
    tmp=Path("/tmp")/("rufilm_banner_dark.svg" if is_dark else "rufilm_banner_light.svg")
    png=Path("/tmp")/("rufilm_banner_dark.png" if is_dark else "rufilm_banner_light.png")
    tmp.write_text(banner_svg(is_dark),encoding="utf-8")
    cairosvg.svg2png(url=str(tmp),write_to=str(png),output_width=960,output_height=540)
    art=Image.open(png).convert("RGBA").resize((960,540),Image.Resampling.LANCZOS)
    mask=Image.new("L",(960,540),0);ImageDraw.Draw(mask).rounded_rectangle((0,0,959,539),radius=76,fill=255)
    art.putalpha(mask)
    folder=res/("drawable-night-nodpi" if is_dark else "drawable-nodpi")
    folder.mkdir(parents=True,exist_ok=True)
    art.resize((320,180),Image.Resampling.LANCZOS).save(folder/"rufilm_tv_banner.png")

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
