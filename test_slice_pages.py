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

# 测试在单个切片 [$50.00 ~ $50.49] 内翻 10 页
pids = set()
for page in range(1, 11):
    r = s.post(url, json={"page": page, "limit": 30, "search_dimension": 1, "scene": 1, "price_min": 50.0, "price_max": 50.49}).json()
    d = r.get('data', {})
    pl = d.get('product_list', [])
    for pid in pl:
        pids.add(pid)
    print(f"Page {page:02d} -> Fetched {len(pl)} items | Unique in slice: {len(pids)}")

print(f"\n[+] 单切片 10 页成功获取到 {len(pids)} 个完全不重复的商品！")
