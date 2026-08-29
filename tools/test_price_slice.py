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

# 测试按价格区间分页检索
payload = {
    "page": 1,
    "limit": 30,
    "search_dimension": 1,
    "scene": 1,
    "price_min": 50.0,
    "price_max": 60.0
}
r = s.post(url, json=payload).json()
d = r.get('data', {})
p_list = d.get('product_list', [])
total = d.get('pagination', {}).get('total', 0)
print(f"Price $50~$60 -> Total: {total}, Page 1 PIDs count: {len(p_list)}")
if p_list:
    print(f"Sample PIDs: {p_list[:5]}")
