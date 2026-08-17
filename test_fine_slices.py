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

# 测试 10 个细粒度切片 ($50.00 ~ $55.00，每 $0.50 一个切片)
total_unique = set()

for p_start in [50.0, 50.5, 51.0, 51.5, 52.0, 52.5, 53.0, 53.5, 54.0, 54.5]:
    p_end = p_start + 0.49
    r = s.post(url, json={"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "price_min": p_start, "price_max": p_end}).json()
    d = r.get('data', {})
    p_list = d.get('product_list', [])
    tot = d.get('pagination', {}).get('total', 0)
    for pid in p_list:
        total_unique.add(pid)
    print(f"Slice [${p_start:5.2f} ~ ${p_end:5.2f}] -> Total in slice: {tot:>3}, Page 1 PIDs: {len(p_list):>2} | Cumulative Unique: {len(total_unique)}")

print(f"\n[+] 10 个细切片累计提取到 {len(total_unique)} 个完全不同的独立商品！")
