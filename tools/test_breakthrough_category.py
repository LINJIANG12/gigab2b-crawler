import requests
import json
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
cid = 10015 # Beds, Frames & Bases (线上 5000 件)

print("="*65)
print(f" 测试突破分类 [{cid}] 单次 3 页 (90 条) 限制的各种维度组合:")
print("="*65)

# 1. 测试基础单翻页 (前 3 页)
base_pids = set()
for p in range(1, 4):
    r = s.post(url, json={"page": p, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [cid]}).json()
    for item in r.get("data", {}).get("product_list", []):
        base_pids.add(str(item))
print(f"[1] 单纯翻页 (1~3 页): 仅获取到 {len(base_pids)} 个唯一商品")

# 2. 测试组合 6 种排序维度 (Sort Combinations)
sort_pids = set(base_pids)
sort_params = [
    {"sort": "p.price", "order": "ASC"},
    {"sort": "p.price", "order": "DESC"},
    {"sort": "p.date_added", "order": "DESC"},
    {"sort": "p.date_added", "order": "ASC"},
    {"sort": "p.sales", "order": "DESC"},
    {"sort": "p.viewed", "order": "DESC"},
    {"sort": "rating", "order": "DESC"},
]

for sp in sort_params:
    for p in range(1, 4):
        payload = {
            "page": p,
            "limit": 30,
            "search_dimension": 1,
            "scene": 2,
            "product_category_id": [cid],
            "sort": sp["sort"],
            "order": sp["order"]
        }
        try:
            r = s.post(url, json=payload, timeout=6).json()
            for item in r.get("data", {}).get("product_list", []):
                sort_pids.add(str(item))
        except:
            pass
print(f"[2] 引入多排序维度 (6 种排序 × 3 页): 累计获取到 {len(sort_pids)} 个唯一商品 (增长 {len(sort_pids)-len(base_pids)} 个)")

# 3. 测试分类内微细价格切片 ($10 一个切片)
price_slice_pids = set(sort_pids)
price_ranges = [
    (0, 50), (50, 100), (100, 150), (150, 200), (200, 250), (250, 300),
    (300, 350), (350, 400), (400, 450), (450, 500), (500, 600), (600, 700),
    (700, 800), (800, 1000), (1000, 1500), (1500, 3000), (3000, 10000)
]

for p_min, p_max in price_ranges:
    for p in range(1, 4):
        payload = {
            "page": p,
            "limit": 30,
            "search_dimension": 1,
            "scene": 2,
            "product_category_id": [cid],
            "price_min": str(p_min),
            "price_max": str(p_max)
        }
        try:
            r = s.post(url, json=payload, timeout=6).json()
            for item in r.get("data", {}).get("product_list", []):
                price_slice_pids.add(str(item))
        except:
            pass

print(f"[3] 引入分类内价格微切片 (17 个价格段 × 3 页): 累计获取到 {len(price_slice_pids)} 个唯一商品 (增长 {len(price_slice_pids)-len(sort_pids)} 个)")

# 4. 检查这批商品中有多少个此前本地数据库没有
conn_db = set()
try:
    import sqlite3
    c = sqlite3.connect("gigab2b.db").cursor()
    conn_db = set(str(r[0]) for r in c.execute("SELECT product_id FROM products").fetchall())
except:
    pass

new_in_cat = [p for p in price_slice_pids if p not in conn_db]
print(f"\n[+] 仅在分类 [{cid}] 单个分类内，就新挖掘出数据库没有的商品: {len(new_in_cat)} 个！")
