import requests
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from cookie_manager import load_cookies
from parser import ProductParser

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()
db_pids = set(str(r[0]) for r in cursor.execute("SELECT product_id FROM products").fetchall())
print(f"[*] 数据库当前商品总数: {len(db_pids):,} 件")

session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

search_url = "https://www.gigab2b.com/index.php?route=product/list/search"
res = session.post(search_url, json={"page": 1, "limit": 1, "search_dimension": 1, "scene": 1}).json()
cat_tree = res.get("data", {}).get("category", [])

parser = ProductParser()
leaf_cats = parser.parse_category_tree(cat_tree)

online_all_pids = set()

def fetch_cat_pids(cat):
    cid = cat["category_id"]
    pids = []
    for p in range(1, 4): # 前 3 页
        try:
            r = session.post(search_url, json={
                "page": p,
                "limit": 30,
                "search_dimension": 1,
                "scene": 2,
                "product_category_id": [cid]
            }, timeout=6).json()
            pl = r.get("data", {}).get("product_list", [])
            for item in pl:
                pids.append(str(item))
        except:
            pass
    return pids

with ThreadPoolExecutor(max_workers=20) as ex:
    futures = [ex.submit(fetch_cat_pids, c) for c in leaf_cats]
    for f in as_completed(futures):
        pids = f.result()
        for p in pids:
            online_all_pids.add(p)

print(f"[*] 从 217 个分类前 3 页中成功抓取到独立商品 ID: {len(online_all_pids):,} 个")

missing_pids = [p for p in online_all_pids if p not in db_pids]
print(f"[*] 其中本地数据库尚未收录的商品 ID: {len(missing_pids):,} 个 ({len(missing_pids)/len(online_all_pids)*100:.2f}%)")
if missing_pids:
    print(f"[*] 缺失样本 ID: {missing_pids[:10]}")

conn.close()
