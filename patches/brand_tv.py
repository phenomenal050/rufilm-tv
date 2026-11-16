#!/usr/bin/env python3
from pathlib import Path
import re
import cairosvg
from PIL import Image, ImageDraw, ImageFont

root = Path("rufilm-tv-2.9/app/src/main")
res = root / "res"
svg = Path("patches/rufilm_brand.svg")
# Render paired launcher artwork: dark mode keeps the current charcoal design;
# light mode uses the same play mark and typography on a warm beige tile.
def render_icon(svg_text, filename):
    source = Path("/tmp") / filename
    output = Path("/tmp") / filename.replace(".svg", ".png")
    source.write_text(svg_text, encoding="utf-8")
    cairosvg.svg2png(url=str(source), write_to=str(output), output_width=512, output_height=512)
    return Image.open(output).convert("RGBA")

dark_icon = render_icon(svg.read_text(encoding="utf-8"), "rufilm_dark.svg")
light_svg = svg.read_text(encoding="utf-8")
light_svg = light_svg.replace('<stop stop-color="#29292c"/>', '<stop stop-color="#fff0d9"/>')
light_svg = light_svg.replace('<stop offset="1" stop-color="#101012"/>', '<stop offset="1" stop-color="#e8cfad"/>')
light_svg = light_svg.replace('fill="#f5f2ed"', 'fill="#171719"')
light_svg = light_svg.replace('fill="#eee9e0"', 'fill="#27221c"')
light_icon = render_icon(light_svg, "rufilm_light.svg")

for density, size in [("mdpi",48),("hdpi",72),("xhdpi",96),("xxhdpi",144),("xxxhdpi",192)]:
    for theme, artwork in [("", dark_icon), ("-night", light_icon)]:
        target = res / f"mipmap-{density}{theme}" / "ic_launcher.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        artwork.resize((size,size), Image.Resampling.LANCZOS).save(target)

# Android 8+ adaptive launcher resources; -night selects the beige artwork
# whenever Android reports that the device is in light appearance.
for theme, artwork, foreground_name, background in [
    ("", dark_icon, "ic_launcher_foreground", "#171719"),
    ("-night", light_icon, "ic_launcher_foreground_light", "#f5e3c9"),
]:
    adaptive_dir = res / f"mipmap-anydpi-v26{theme}"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    fg_dir = res / "mipmap-xxxhdpi"
    fg_dir.mkdir(parents=True, exist_ok=True)
    artwork.resize((192,192), Image.Resampling.LANCZOS).save(fg_dir / f"{foreground_name}.png")
    (adaptive_dir / "ic_launcher.xml").write_text(f'''<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/rufilm_icon_background{theme.replace("-night", "_night")}" />
    <foreground android:drawable="@mipmap/{foreground_name}" />
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

night_colors = res / "values-night" / "colors.xml"
night_colors.parent.mkdir(parents=True, exist_ok=True)
night_colors.write_text('<resources><color name="rufilm_icon_background_night">#f5e3c9</color></resources>', encoding="utf-8")
# Android TV / Google TV banner: the exact same launcher icon, centered, without extra lettering.
banner = Image.new("RGB",(320,180),(17,17,19))
logo_size = 176
logo = icon.resize((logo_size,logo_size),Image.Resampling.LANCZOS)
banner.paste(logo,((320-logo_size)//2,(180-logo_size)//2),logo)
banner_dir = res / "drawable-nodpi"
banner_dir.mkdir(parents=True,exist_ok=True)
banner.save(banner_dir / "rufilm_tv_banner.png")

# Update manifest using XML so the launcher metadata is reliable on Android TV and Google TV.
import xml.etree.ElementTree as ET
manifests = list(root.rglob("AndroidManifest.xml"))
if not manifests:
    raise SystemExit("AndroidManifest.xml not found")
manifest = manifests[0]
ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
ET.register_namespace("tools", "http://schemas.android.com/tools")
tree = ET.parse(manifest)
root_xml = tree.getroot()
android = "{http://schemas.android.com/apk/res/android}"
app = root_xml.find("application")
if app is None:
    raise SystemExit("application element not found")
app.set(android + "icon", "@mipmap/ic_launcher")
app.set(android + "roundIcon", "@mipmap/ic_launcher")
app.set(android + "banner", "@drawable/rufilm_tv_banner")
app.set(android + "label", "RUFILM TV")
leanback = False
main_activity = None
for component in list(app):
    if component.tag not in ("activity", "activity-alias"):
        continue
    for intent in component.findall("intent-filter"):
        actions = [x.get(android + "name") for x in intent.findall("action")]
        categories = [x.get(android + "name") for x in intent.findall("category")]
        if "android.intent.action.MAIN" in actions:
            main_activity = component
            if "android.intent.category.LEANBACK_LAUNCHER" not in categories:
                ET.SubElement(intent, "category", {android + "name": "android.intent.category.LEANBACK_LAUNCHER"})
            leanback = True
if not leanback and main_activity is not None:
    intent = ET.SubElement(main_activity, "intent-filter")
    ET.SubElement(intent, "action", {android + "name": "android.intent.action.MAIN"})
    ET.SubElement(intent, "category", {android + "name": "android.intent.category.LEANBACK_LAUNCHER"})
features = {x.get(android + "name") for x in root_xml.findall("uses-feature")}
if "android.software.leanback" not in features:
    ET.SubElement(root_xml, "uses-feature", {android + "name": "android.software.leanback", android + "required": "false"})
if "android.hardware.touchscreen" not in features:
    ET.SubElement(root_xml, "uses-feature", {android + "name": "android.hardware.touchscreen", android + "required": "false"})
tree.write(manifest, encoding="utf-8", xml_declaration=True)
print("Branding and Android TV launcher assets installed.")
