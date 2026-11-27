#!/usr/bin/env python3
"""Enable cleartext only for the loopback media proxy; keep remote HTTP blocked."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

root = Path("rufilm-tv-2.9/app/src/main")
manifest = root / "AndroidManifest.xml"
resource = root / "res/xml/rufilm_network_security_config.xml"
text = manifest.read_text(encoding="utf-8")
match = re.search(r"<application\\b[^>]*>", text, re.DOTALL)
if not match:
    raise SystemExit("AndroidManifest.xml has no application element")
tag = match.group(0)

def set_attr(tag, name, value):
    pattern = rf'\\b{re.escape(name)}\\s*=\\s*("[^"]*"|\\'[^\\']*\\')'
    if re.search(pattern, tag):
        return re.sub(pattern, f'{name}="{value}"', tag, count=1)
    return tag[:-1] + f' {name}="{value}">'

tag = set_attr(tag, "android:networkSecurityConfig", "@xml/rufilm_network_security_config")
tag = set_attr(tag, "android:usesCleartextTraffic", "false")
text = text[:match.start()] + tag + text[match.end():]
manifest.write_text(text, encoding="utf-8")

resource.parent.mkdir(parents=True, exist_ok=True)
resource.write_text("""<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
    </domain-config>
</network-security-config>
""", encoding="utf-8")

ET.parse(manifest)
ET.parse(resource)
assert 'android:networkSecurityConfig="@xml/rufilm_network_security_config"' in manifest.read_text(encoding="utf-8")
print("Network security configured: cleartext permitted only for 127.0.0.1.")
