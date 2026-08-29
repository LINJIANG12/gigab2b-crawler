import requests
import json
from cookie_manager import get_authenticated_session, load_cookies

cookies = load_cookies()
print("Saved cookies:", list(cookies.keys()))

s = requests.Session()
s.cookies.update(cookies)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.gigab2b.com",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"
res = s.post(url, json={"page": 1, "limit": 10, "search_dimension": 1, "scene": 1}).json()
print("Search code:", res.get('code'))
print("Search msg:", res.get('msg'))
print("Total category:", len(res.get('data', {}).get('category', [])))
print("Product list:", len(res.get('data', {}).get('product_list', [])))
