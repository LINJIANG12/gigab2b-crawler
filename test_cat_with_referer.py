import requests
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

# 测试分类 10015 的 page 1 和 page 2
for p in [1, 2]:
    payload = {
        "page": p,
        "limit": 30,
        "search_dimension": 1,
        "scene": 2,
        "product_category_id": [10015]
    }
    r = s.post(url, json=payload).json()
    d = r.get('data', {})
    p_list = d.get('product_list', [])
    total = d.get('pagination', {}).get('total', 0)
    print(f"Page {p} -> Found {len(p_list)} products. Total in category: {total}")
    if p_list:
        print(f"  First 3 PIDs: {p_list[:3]}")
