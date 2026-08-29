import requests
from cookie_manager import get_authenticated_session

session = get_authenticated_session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 测试大分类 Beds, Frames & Bases (ID: 10015)
# 遍历前 10 页
cid = 10015
all_pids = []

for page in range(1, 11):
    payload = {
        "page": page,
        "limit": 30,
        "search_dimension": 1,
        "scene": 2,
        "product_category_id": [cid]
    }
    res = session.post(url, json=payload, timeout=15).json()
    d = res.get('data', {})
    p_list = d.get('product_list', [])
    pagination = d.get('pagination', {})
    total = pagination.get('total', 0)
    
    print(f"Page {page:02d} -> Got {len(p_list)} products. Category total: {total}")
    for pid in p_list:
        if pid not in all_pids:
            all_pids.append(pid)
    if not p_list:
        print("  Break on empty product_list")
        break

print(f"\n[+] Total unique PIDs collected from first 10 pages: {len(all_pids)}")
