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

cid = 10015

tests = [
    {"name": "POST url with query param", "url": f"https://www.gigab2b.com/index.php?route=product/list/search&product_category_id={cid}", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [cid]}},
    {"name": "POST url with category_id query", "url": f"https://www.gigab2b.com/index.php?route=product/list/search&category_id={cid}", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [cid]}},
    {"name": "POST scene 2 only query", "url": f"https://www.gigab2b.com/index.php?route=product/list/search&product_category_id={cid}", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 2}},
    {"name": "POST scene 6 advanced", "url": "https://www.gigab2b.com/index.php?route=product/list/search", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 6, "product_category_id": [cid]}},
    {"name": "GET request", "url": f"https://www.gigab2b.com/index.php?route=product/list/search&product_category_id={cid}&page=1&limit=30&scene=2", "body": None},
]

for t in tests:
    if t["body"] is not None:
        r = s.post(t["url"], json=t["body"]).json()
    else:
        r = s.get(t["url"]).json()
    p_list = r.get('data', {}).get('product_list', [])
    total = r.get('data', {}).get('pagination', {}).get('total', 0)
    print(f"Test [{t['name']}] -> total: {total}, pids: {len(p_list)}")
    if p_list:
        print(f"  Sample PIDs: {p_list[:4]}")
