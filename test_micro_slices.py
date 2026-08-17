import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# 测试 30 个 $0.10 细切片
slices = []
for i in range(200, 230):
    p1 = i / 10.0
    p2 = round(p1 + 0.09, 2)
    slices.append((p1, p2))

def scan_slice(p1, p2):
    pids = []
    for page in [1, 2]:
        r = s.post(url, json={"page": page, "limit": 30, "search_dimension": 1, "scene": 1, "price_min": p1, "price_max": p2}, timeout=15).json()
        pl = r.get('data', {}).get('product_list', [])
        pids.extend(pl)
        if len(pl) < 12:
            break
    return p1, p2, pids

print(f"[*] 正在并发测试 30 个 $0.10 超细切片 ($20.00 ~ $23.00)...")
unique_pids = set()

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(scan_slice, s[0], s[1]) for s in slices]
    for f in as_completed(futures):
        p1, p2, pids = f.result()
        for p in pids:
            unique_pids.add(p)
        print(f"Slice [${p1:5.2f} ~ ${p2:5.2f}] -> Found {len(pids):>2} items (Unique total: {len(unique_pids)})")

print(f"\n[+] 仅 $20~$23 这 $3 的价格区间内，就成功挖掘出了 {len(unique_pids)} 个独立商品！")
