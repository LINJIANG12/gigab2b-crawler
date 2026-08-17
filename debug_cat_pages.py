import requests
import json
from cookie_manager import get_authenticated_session

session = get_authenticated_session()
session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 测试分类 ID 10015 (Beds, Frames & Bases)
# 尝试 page 1, 2, 3, 4
for p in [1, 2, 3]:
    payload = {
        "page": p,
        "limit": 30,
        "search_dimension": 1,
        "scene": 2,
        "product_category_id": [10015]
    }
    r = session.post(url, json=payload).json()
    d = r.get('data', {})
    p_list = d.get('product_list', [])
    pagination = d.get('pagination', {})
    print(f"Page {p} -> Found {len(p_list)} products. Pagination: {pagination}")
    if p_list:
        print(f"  First 3 PIDs: {p_list[:3]}")
