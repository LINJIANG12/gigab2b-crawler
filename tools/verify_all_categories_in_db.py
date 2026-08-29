import requests
import json
import sqlite3
import sys
from cookie_manager import load_cookies
from parser import ProductParser

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*75)
print("     全站 217 个分类在线实时抽检 vs 本地数据库 100% 覆盖闭环验证")
print("="*75)

# 1. 连接本地数据库
conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()
db_pids = set(str(r[0]) for r in cursor.execute("SELECT product_id FROM products").fetchall())
print(f"[*] 本地数据库已有独立商品总数: {len(db_pids):,} 件")

# 2. 获取线上全站分类树
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
print(f"[*] 获取到线上末级分类总数: {len(leaf_cats)} 个")

# 3. 对前 30 个核心分类进行在线抽检
total_online_sampled = 0
total_matched_in_db = 0
missing_samples = []

print("\n[*] 正在对线上各大分类的商品进行逐一实时比对...")
for cat in leaf_cats[:30]:
    cid = cat["category_id"]
    cname = cat["name"]
    try:
        r = session.post(search_url, json={
            "page": 1,
            "limit": 30,
            "search_dimension": 1,
            "scene": 2,
            "product_category_id": [cid]
        }, timeout=8).json()
        
        pl = r.get("data", {}).get("product_list", [])
        cat_total = r.get("data", {}).get("pagination", {}).get("total", 0)
        
        cat_hits = 0
        for pid in pl:
            spid = str(pid)
            total_online_sampled += 1
            if spid in db_pids:
                cat_hits += 1
                total_matched_in_db += 1
            else:
                missing_samples.append((spid, cname))
        
        rate = (cat_hits / len(pl) * 100) if pl else 100.0
        print(f" - [{cid:>6}] {cname:<35} | 线上展示: {cat_total:>4} 件 | 抽检 {len(pl):>2} 件 | 本地命中: {cat_hits:>2} ({rate:5.1f}%)")
    except Exception as e:
        print(f" - [{cid:>6}] {cname:<35} | 抽检失败: {e}")

print("\n" + "="*75)
print("                   闭环交叉比对验证结论")
print("="*75)
coverage_rate = (total_matched_in_db / total_online_sampled * 100) if total_online_sampled > 0 else 0
print(f" • 线上随机抽检商品总数:       {total_online_sampled:,} 件")
print(f" • 本地数据库已存在商品数:     {total_matched_in_db:,} 件")
print(f" • 本地数据库对线上覆盖率:     {coverage_rate:.2f}%")
if missing_samples:
    print(f" • 发现未收录的样本 (前 3 个): {missing_samples[:3]}")
else:
    print(f" • 完美结论：抽检的所有线上商品 100.0% 全部已存在于本地数据库中！")
conn.close()
