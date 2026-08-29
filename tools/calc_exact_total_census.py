import sqlite3
import json
import requests
import sys
from collections import defaultdict
from cookie_manager import load_cookies

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*75)
print("       GigaB2B 全站真实数据量与全维度普查测算 (Final Census)")
print("="*75)

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

# -------------------------------------------------------------
# 1. 物理数据库去重普查 (Database Census)
# -------------------------------------------------------------
total_unique_spu = cursor.execute("SELECT count(DISTINCT product_id) FROM products").fetchone()[0]
total_tasks_found = cursor.execute("SELECT count(*) FROM crawl_tasks").fetchone()[0]

rows = cursor.execute("""
    SELECT product_id, sku, title, price, discount_price, total_stock, 
           category_path, variants, product_status, status_reason
    FROM products
""").fetchall()

# 2. 统计变体 SKU 详细分布
total_skus = 0
single_variant_spus = 0
multi_variant_spus = 0
variant_counts_dist = defaultdict(int)

for r in rows:
    pid, sku, title, price, disc_price, stock, cat, vars_json, p_status, s_reason = r
    vars_list = []
    try:
        if vars_json:
            vars_list = json.loads(vars_json)
    except:
        pass
    
    cnt = len(vars_list) if vars_list else 1
    if cnt > 1:
        multi_variant_spus += 1
    else:
        single_variant_spus += 1
    total_skus += cnt
    variant_counts_dist[cnt] += 1

# 3. 统计在售与保护状态
protected_count = 0
in_stock_count = 0
out_of_stock_count = 0

for r in rows:
    pid, sku, title, price, disc_price, stock, cat, vars_json, p_status, s_reason = r
    # 判断是否为保护商品
    if price == "Protected" or price == "Channel Protected" or "protect" in str(price).lower() or "protect" in str(s_reason).lower():
        protected_count += 1
    
    try:
        st = int(stock)
        if st > 0:
            in_stock_count += 1
        else:
            out_of_stock_count += 1
    except:
        out_of_stock_count += 1

# 4. 统计全站一级与二级分类覆盖情况
primary_cats = defaultdict(int)
for r in rows:
    cat = r[6] or "Other"
    p_cat = cat.split(" > ")[0].strip() if " > " in cat else cat.strip()
    primary_cats[p_cat] += 1

# 5. 校验 1600000 ~ 1650000 区间是否有未收录商品
session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest"
})

def probe_quick(pid):
    try:
        url = f"https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id={pid}"
        res = session.get(url, timeout=3)
        if res.status_code == 200:
            j = res.json()
            if j.get("code") == 200 and j.get("data") and j.get("data").get("product_info"):
                return True
    except:
        pass
    return False

boundary_pids = [1600000, 1610000, 1620000, 1625000, 1630000, 1640000, 1650000]
boundary_results = {}
for bp in boundary_pids:
    hits = sum(1 for p in range(bp, bp + 20) if probe_quick(p))
    boundary_results[bp] = hits

print(f"\n[维度 1] 平台真实商品总量测算结果 (SPU vs SKU):")
print(f" ---------------------------------------------------------")
print(f" • 全站独立商品款数 (SPU 唯一 Product ID):  {total_unique_spu:>7,} 款 (100% 绝对去重)")
print(f" • 全站可销售规格总数 (SKU 变体展开明细):  {total_skus:>7,} 条 (含各颜色/尺寸独立行)")
print(f" • 单规格商品款数:                         {single_variant_spus:>7,} 款 ({single_variant_spus/total_unique_spu*100:4.1f}%)")
print(f" • 多规格变体商品款数:                     {multi_variant_spus:>7,} 款 ({multi_variant_spus/total_unique_spu*100:4.1f}%)")
print(f" • 平均每款商品拥有的变体数量:             {total_skus/total_unique_spu:>7.2f} 个变体/SPU")

print(f"\n[维度 2] 商品在售与库存状态分布:")
print(f" ---------------------------------------------------------")
print(f" • 海外仓有现货商品:                       {in_stock_count:>7,} 款 ({in_stock_count/total_unique_spu*100:4.1f}%)")
print(f" • 暂无库存/预定/下架归档商品:             {out_of_stock_count:>7,} 款 ({out_of_stock_count/total_unique_spu*100:4.1f}%)")
print(f" • 供应商渠道保护商品:                     {protected_count:>7,} 款 ({protected_count/total_unique_spu*100:4.1f}%)")

print(f"\n[维度 3] 全站大类分布明细 (覆盖 100% 真实商品):")
print(f" ---------------------------------------------------------")
for cat_name, count in sorted(primary_cats.items(), key=lambda x: x[1], reverse=True):
    print(f" • {cat_name:<35}: {count:>6,} 款 ({count/total_unique_spu*100:4.1f}%)")

print(f"\n[维度 4] 最新号段边界实测探针 (160万~165万):")
print(f" ---------------------------------------------------------")
for bp, hits in boundary_results.items():
    print(f" • ID [{bp:>7,} ~ {bp+20:>7,}] 采样命中: {hits:>2}/20 件")

conn.close()
