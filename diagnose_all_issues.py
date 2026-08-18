import sqlite3
import json
import requests
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from cookie_manager import load_cookies

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*70)
print("             GigaB2B 全站数据量与漏采根因全面诊断")
print("="*70)

# -------------------------------------------------------------
# 1. 检查数据库中当前 SPU 与变体 SKU 的展开总数
# -------------------------------------------------------------
conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

total_spu = cursor.execute("SELECT count(*) FROM products").fetchone()[0]
rows = cursor.execute("SELECT product_id, sku, variants FROM products").fetchall()

total_sku_count = 0
items_with_variants = 0
for pid, sku, variants_json in rows:
    try:
        vars_list = json.loads(variants_json) if variants_json else []
        if vars_list:
            items_with_variants += 1
            total_sku_count += len(vars_list)
        else:
            total_sku_count += 1
    except:
        total_sku_count += 1

print(f"[1] 数据库现状:")
print(f" - 独立商品 (SPU / Product ID 总数): {total_spu:,} 件")
print(f" - 包含多变体的商品数:              {items_with_variants:,} 件")
print(f" - 展开全部颜色/尺寸后的 SKU 变体总数: {total_sku_count:,} 个")

# -------------------------------------------------------------
# 2. 探测 ID 空间外部边界：1~400,000 和 1,600,000~3,000,000
# -------------------------------------------------------------
session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest"
})

def probe_pid(pid):
    try:
        url = f"https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id={pid}"
        r = session.get(url, timeout=5)
        if r.status_code == 200:
            j = r.json()
            if j.get("code") == 200 and j.get("data") and j.get("data").get("product_info"):
                pinfo = j["data"]["product_info"]
                return pid, True, pinfo.get("sku"), pinfo.get("product_name")
    except:
        pass
    return pid, False, None, None

print(f"\n[2] 探测外部 ID 空间 (0 ~ 40万 以及 160万 ~ 300万):")

test_ranges = [
    (1000, "1千号段 (超早期)"),
    (50000, "5万号段 (超早期)"),
    (100000, "10万号段 (早期)"),
    (200000, "20万号段 (早期)"),
    (300000, "30万号段 (早期)"),
    (350000, "35万号段 (临界点)"),
    (380000, "38万号段 (临界点)"),
    (1600000, "160万号段 (边界)"),
    (1650000, "165万号段 (最新)"),
    (1700000, "170万号段 (最新)"),
    (1800000, "180万号段 (超前)"),
    (2000000, "200万号段 (超前)"),
]

for base_id, label in test_ranges:
    pids = list(range(base_id, base_id + 30))
    hits = 0
    sample_sku = None
    sample_name = None
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(probe_pid, p) for p in pids]
        for f in as_completed(futures):
            p, valid, sku, name = f.result()
            if valid:
                hits += 1
                sample_sku = sku
                sample_name = name
    if hits > 0:
        print(f" - {label:<22} [ID: {base_id}~{base_id+30}] -> 命中率: {hits:>2}/30 (样本: {sample_sku} | {sample_name[:30]}...)")
    else:
        print(f" - {label:<22} [ID: {base_id}~{base_id+30}] -> 命中率:  0/30 (无商品)")

# -------------------------------------------------------------
# 3. 检查 217 个分类的 96,818 是否包含跨分类重复
# -------------------------------------------------------------
print(f"\n[3] 检查 217 个分类商品体量测算数据:")
try:
    with open("data_volume_report.json", "r", encoding="utf-8") as f:
        rep = json.load(f)
    print(f" - 分类总数: {len(rep)} 个")
    total_cat_sum = sum(item.get("total", 0) for item in rep)
    print(f" - 217 分类商品数简单累加和: {total_cat_sum:,} 件")
    
    # 打印前 10 个最大分类
    sorted_rep = sorted(rep, key=lambda x: x.get("total", 0), reverse=True)
    print(f" - 数量最多的前 5 个分类:")
    for c in sorted_rep[:5]:
        print(f"    * [{c.get('category_id')}] {c.get('name')}: {c.get('total'):,} 件")
except Exception as e:
    print(f" - 无法读取 data_volume_report.json: {e}")
