#!/usr/bin/env python3
from pathlib import Path
import re
import cairosvg
from PIL import Image, ImageDraw, ImageFont

root = Path("rufilm-tv-2.9/app/src/main")
res = root / "res"
svg = Path("patches/rufilm_brand.svg")
png = Path("/tmp/rufilm_icon.png")
cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=512, output_height=512)
icon = Image.open(png).convert("RGBA")
for density, size in [("mdpi",48),("hdpi",72),("xhdpi",96),("xxhdpi",144),("xxxhdpi",192)]:
    target = res / f"mipmap-{density}" / "ic_launcher.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    icon.resize((size,size), Image.Resampling.LANCZOS).save(target)
target = res / "mipmap-anydpi-v26"
target.mkdir(parents=True, exist_ok=True)
fg = res / "mipmap-xxxhdpi" / "ic_launcher_foreground.png"
icon.resize((192,192), Image.Resampling.LANCZOS).save(fg)
(target / "ic_launcher.xml").write_text('''<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/rufilm_icon_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
</adaptive-icon>''', encoding="utf-8")
colors = res / "values" / "colors.xml"
colors.parent.mkdir(parents=True, exist_ok=True)
if colors.exists():
    c = colors.read_text(encoding="utf-8")
    if "rufilm_icon_background" not in c:
        c = c.replace("</resources>", '    <color name="rufilm_icon_background">#171719</color>\n</resources>')
else:
    c = '<resources><color name="rufilm_icon_background">#171719</color></resources>'
colors.write_text(c, encoding="utf-8")
banner = Image.new("RGB",(320,180),(17,17,19))
d = ImageDraw.Draw(banner)
logo = icon.resize((126,126),Image.Resampling.LANCZOS)
banner.paste(logo,(15,27),logo)
bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
d.text((158,55),"RUFILM",font=ImageFont.truetype(bold,25),fill=(247,244,239))
d.text((158,84),"TV",font=ImageFont.truetype(bold,25),fill=(242,43,49))
d.text((158,126),"ТВОЙ ОНЛАЙН",font=ImageFont.truetype(regular,10),fill=(238,234,226))
d.text((158,141),"КИНОТЕАТР",font=ImageFont.truetype(regular,10),fill=(238,234,226))
banner_dir = res / "drawable-nodpi"
banner_dir.mkdir(parents=True,exist_ok=True)
banner.save(banner_dir / "rufilm_tv_banner.png")

manifests = list(root.rglob("AndroidManifest.xml"))
if not manifests:
    raise SystemExit("AndroidManifest.xml not found")
manifest = manifests[0]
xml = manifest.read_text(encoding="utf-8")
app = re.search(r"<application\b[^>]*>", xml, re.S)
if not app:
    raise SystemExit("application tag not found")
tag = app.group(0)
def attr(text, name, value):
    pattern = rf'\s+android:{name}="[^"]*"'
    if re.search(pattern,text):
        return re.sub(pattern, f' android:{name}="{value}"', text, count=1)
    return text[:-1] + f' android:{name}="{value}">'
tag = attr(tag,"icon","@mipmap/ic_launcher")
tag = attr(tag,"banner","@drawable/rufilm_tv_banner")
tag = attr(tag,"label","RUFILM TV")
xml = xml[:app.start()] + tag + xml[app.end():]
if "android.intent.category.LEANBACK_LAUNCHER" not in xml:
    pattern = r'(<intent-filter\b[^>]*>(?:(?!</intent-filter>).)*?<action android:name="android.intent.action.MAIN"\s*/>(?:(?!</intent-filter>).)*?<category android:name="android.intent.category.LAUNCHER"\s*/>(?:(?!</intent-filter>).)*?</intent-filter>)'
    m = re.search(pattern,xml,re.S)
    if m:
        block = m.group(1).replace("</intent-filter>",'    <category android:name="android.intent.category.LEANBACK_LAUNCHER" />\n        </intent-filter>')
        xml = xml[:m.start()] + block + xml[m.end():]
if "android.software.leanback" not in xml:
    xml = xml.replace("<application", '<uses-feature android:name="android.software.leanback" android:required="false" />\n    <uses-feature android:name="android.hardware.touchscreen" android:required="false" />\n    <application', 1)
manifest.write_text(xml,encoding="utf-8")
print("Branding and Android TV launcher assets installed.")
