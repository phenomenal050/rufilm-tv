#!/usr/bin/env python3
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path("rufilm-tv-2.9/app/src/main")
manifest = root / "AndroidManifest.xml"
if not manifest.exists():
    raise SystemExit("AndroidManifest.xml not found")

ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
tree = ET.parse(manifest)
mx = tree.getroot()
a = "{http://schemas.android.com/apk/res/android}"

permissions = {node.get(a + "name") for node in mx.findall("uses-permission")}
if "android.permission.REQUEST_INSTALL_PACKAGES" not in permissions:
    node = ET.Element("uses-permission", {a + "name": "android.permission.REQUEST_INSTALL_PACKAGES"})
    app = mx.find("application")
    if app is not None:
        mx.insert(list(mx).index(app), node)
    else:
        mx.append(node)

app = mx.find("application")
if app is None:
    raise SystemExit("application element not found")

provider_name = "androidx.core.content.FileProvider"
provider = next((x for x in app.findall("provider") if x.get(a + "name") == provider_name), None)
if provider is None:
    provider = ET.SubElement(app, "provider", {
        a + "name": provider_name,
        a + "authorities": "$" + "{applicationId}.fileprovider",
        a + "exported": "false",
        a + "grantUriPermissions": "true",
    })
meta = next((x for x in provider.findall("meta-data")
             if x.get(a + "name") == "android.support.FILE_PROVIDER_PATHS"), None)
if meta is None:
    ET.SubElement(provider, "meta-data", {
        a + "name": "android.support.FILE_PROVIDER_PATHS",
        a + "resource": "@xml/rufilm_file_paths",
    })

xml_dir = root / "res" / "xml"
xml_dir.mkdir(parents=True, exist_ok=True)
(xml_dir / "rufilm_file_paths.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<paths xmlns:android="http://schemas.android.com/apk/res/android">\n'
    '    <cache-path name="updates" path="updates/" />\n'
    '</paths>\n',
    encoding="utf-8",
)

tree.write(manifest, encoding="utf-8", xml_declaration=True)
print("Update installer permission and FileProvider paths installed.")
