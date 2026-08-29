import requests
import json
from cookie_manager import load_cookies

s = requests.Session()
s.cookies.update(load_cookies())
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"
cid = 10015

print("="*65)
print(" 探索各种参数组合在分类 10015 下返回的商品列表数量:")
print("="*65)

test_configs = [
    ("Default (scene: 2, dim: 1)", {"page": 1, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [cid]}),
    ("No Scene", {"page": 1, "limit": 30, "search_dimension": 1, "product_category_id": [cid]}),
    ("Scene: 0", {"page": 1, "limit": 30, "search_dimension": 1, "scene": 0, "product_category_id": [cid]}),
    ("Scene: 1", {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "product_category_id": [cid]}),
    ("Scene: 6", {"page": 1, "limit": 30, "search_dimension": 1, "scene": 6, "product_category_id": [cid]}),
    ("Search Dim: 0", {"page": 1, "limit": 30, "search_dimension": 0, "product_category_id": [cid]}),
    ("Category as int", {"page": 1, "limit": 30, "search_dimension": 1, "product_category_id": cid}),
    ("Limit: 100", {"page": 1, "limit": 100, "search_dimension": 1, "product_category_id": [cid]}),
]

for desc, payload in test_configs:
    try:
        r = s.post(url, json=payload, timeout=6).json()
        d = r.get("data", {})
        pl = d.get("product_list", [])
        tot = d.get("pagination", {}).get("total")
        print(f" - {desc:<30} -> Total: {tot:>5} | Returned PIDs: {len(pl):>2}")
        if pl:
            print(f"    Sample PIDs: {pl[:3]}")
    except Exception as e:
        print(f" - {desc:<30} -> Error: {e}")
