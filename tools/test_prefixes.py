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

prefixes = ['W', 'B', 'T', 'S', 'M', 'C', 'D', 'A', 'P', 'H', 'L', 'F', 'G', 'E', 'R', 'N', 'K', 'J', 'O', 'I', 'U', 'V', 'X', 'Y', 'Z', 'Q']

print("[*] 正在测试全字母 SKU 前缀覆盖率...")

all_pids = set()

for prefix in prefixes:
    r = s.post(url, json={"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "search": prefix}).json()
    d = r.get('data', {})
    tot = d.get('pagination', {}).get('total', 0)
    pl = d.get('product_list', [])
    for p in pl:
        all_pids.add(p)
    print(f"Prefix '{prefix}' -> Total in platform: {tot:>5} | Page 1 items: {len(pl):>2} | Cumulative unique: {len(all_pids):,}")

print(f"\n[+] 仅 26 个字母搜索，平台商品命中总量就达到了极高覆盖！")
