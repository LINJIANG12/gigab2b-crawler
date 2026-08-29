import requests
import re

html = requests.get('https://www.gigab2b.com/').text
js_files = re.findall(r'src="([^"]+\.js)"', html)
print("Found JS files:", len(js_files))

for js in js_files:
    if not js.startswith('http'):
        js = 'https://www.gigab2b.com' + js
    try:
        content = requests.get(js).text
        if 'changeSort' in content or 'product/list/search' in content:
            print(f"\n[+] Found in {js}:")
            for m in re.finditer(r'sort:\s*["\']([^"\']+)["\']', content):
                print("  sort:", m.group(1))
    except Exception:
        pass
