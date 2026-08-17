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

# 1. 抓取第 1 页并获取 request_id
r1 = s.post(url, json={"page": 1, "limit": 30, "search_dimension": 1, "scene": 1}).json()
d1 = r1.get('data', {})
req_id = d1.get('search_info', {}).get('request_id', '')
total = d1.get('pagination', {}).get('total', 0)
pids1 = d1.get('product_list', [])

print(f"Page 01 -> RequestID: {req_id} | Total: {total} | PIDs: {len(pids1)}")

all_pids = list(pids1)

# 2. 连续翻 10 页
for page in range(2, 11):
    payload = {
        "page": page,
        "limit": 30,
        "search_dimension": 1,
        "scene": 1,
        "search_request_id": req_id
    }
    r = s.post(url, json=payload).json()
    d = r.get('data', {})
    pl = d.get('product_list', [])
    new_in_page = [p for p in pl if p not in all_pids]
    all_pids.extend(new_in_page)
    print(f"Page {page:02d} -> Fetched {len(pl)} | New unique: {len(new_in_page)} | Cumulative unique: {len(all_pids)}")

print(f"\n[+] 带上 search_request_id 后，10 页成功获取了 {len(all_pids)} 个连续递增的商品！")
