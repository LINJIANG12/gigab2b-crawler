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

# 测试大分类 10015 (Beds, Frames & Bases, 共有 5,000 件商品)
cid = 10015

pids_found = set()

# 策略 1: 不同的排序方式
sort_strategies = [
    {"sort": "", "order": ""},
    {"sort": "p.price", "order": "asc"},
    {"sort": "p.price", "order": "desc"},
    {"sort": "p.date_added", "order": "desc"},
    {"sort": "p.date_added", "order": "asc"},
    {"sort": "rating", "order": "desc"},
    {"sort": "sales", "order": "desc"},
    {"sort": "p.sort_order", "order": "asc"},
]

print(f"[*] 针对大分类 10015 (Beds, Frames & Bases) 测试多维正交挖掘...")

for idx, st in enumerate(sort_strategies, 1):
    for page in [1, 2, 3]:
        payload = {
            "page": page,
            "limit": 30,
            "search_dimension": 1,
            "scene": 2,
            "product_category_id": [cid],
            "sort": st["sort"],
            "order": st["order"]
        }
        r = s.post(url, json=payload).json()
        pl = r.get('data', {}).get('product_list', [])
        for p in pl:
            pids_found.add(p)
    print(f"  策略 {idx} (sort={st['sort']}, order={st['order']}) -> 累计独立 PIDs: {len(pids_found)}")

# 策略 2: 在该分类下，按价格粗切片 ($0~50, $50~100, $100~150, $150~200, $200~300, $300~500, $500~1000, $1000~3000)
price_brackets = [
    (0.01, 50), (50.01, 100), (100.01, 150), (150.01, 200),
    (200.01, 250), (250.01, 300), (300.01, 400), (400.01, 500),
    (500.01, 700), (700.01, 1000), (1000.01, 2000), (2000.01, 5000)
]

for p1, p2 in price_brackets:
    for page in [1, 2, 3]:
        payload = {
            "page": page,
            "limit": 30,
            "search_dimension": 1,
            "scene": 2,
            "product_category_id": [cid],
            "price_min": p1,
            "price_max": p2
        }
        r = s.post(url, json=payload).json()
        pl = r.get('data', {}).get('product_list', [])
        for p in pl:
            pids_found.add(p)
    print(f"  分类内价格区间 [${p1} ~ ${p2}] -> 累计独立 PIDs: {len(pids_found)}")

print(f"\n[+] 单个分类 10015 经过交叉正交挖掘，成功获取到 {len(pids_found)} 个独立商品！")
