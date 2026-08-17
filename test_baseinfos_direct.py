import requests
import json
from cookie_manager import load_cookies

s = requests.Session()
s.cookies.update(load_cookies())
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/product&product_id=1459370"
})

url = "https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id=1459370"
r = s.get(url, timeout=10)
print("Status Code:", r.status_code)
print("Response text:", r.text[:300])
