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

# 测试带上 search_property_key 的分类 10015
payload = {
    "page": 1,
    "limit": 30,
    "search_dimension": 1,
    "scene": 1,
    "product_category_id": [10015],
    "search_property_key": "product_category_id"
}
r = s.post(url, json=payload).json()
d = r.get('data', {})
p_list = d.get('product_list', [])
total = d.get('pagination', {}).get('total', 0)
print(f"Category 10015 -> total: {total}, pids count: {len(p_list)}")
if p_list:
    print(f"First 5 PIDs in category 10015: {p_list[:5]}")
