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

# 测试不同的分页参数名
candidates = [
    {"page": 2, "limit": 12, "search_dimension": 1, "scene": 1},
    {"page": 2, "limit": 30, "search_dimension": 1, "scene": 1, "search_request_id": ""},
    {"page": 2, "limit": 30, "search_dimension": 1, "scene": 1, "page_no": 2},
    {"page": 2, "limit": 30, "search_dimension": 1, "scene": 1, "offset": 12},
    {"page": 2, "limit": 30, "search_dimension": 1, "scene": 1, "start": 12},
    {"page": 2, "limit": 30, "search_dimension": 1, "scene": 1, "p": 2},
]

# 对照组：第 1 页的 PIDs
r1 = s.post(url, json={"page": 1, "limit": 12, "search_dimension": 1, "scene": 1}).json()
pids1 = r1.get('data', {}).get('product_list', [])
print("Page 1 PIDs:", pids1[:5])

for idx, body in enumerate(candidates, 1):
    r = s.post(url, json=body).json()
    pids = r.get('data', {}).get('product_list', [])
    overlap = set(pids).intersection(set(pids1))
    print(f"Candidate {idx} ({list(body.keys())}) -> PIDs: {pids[:5]} (Overlap with page 1: {len(overlap)}/{len(pids)})")
