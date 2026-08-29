import sqlite3
import json
import requests
from cookie_manager import load_cookies

print("="*70)
print("             GigaB2B 全站数据量与漏采根因全面诊断")
print("="*70)

# 1. 检查数据库中当前 SPU 与变体 SKU 的展开总数
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

# 2. 检查分类重叠与 96,818 总量
print(f"\n[2] 检查 217 个分类商品体量测算数据:")
try:
    with open("data_volume_report.json", "r", encoding="utf-8") as f:
        rep = json.load(f)
    print(f" - 分类总数: {len(rep)} 个")
    total_cat_sum = sum(item.get("total", 0) for item in rep)
    print(f" - 217 分类商品数累加和: {total_cat_sum:,} 件")
    sorted_rep = sorted(rep, key=lambda x: x.get("total", 0), reverse=True)
    print(f" - 数量最多的前 8 个分类:")
    for c in sorted_rep[:8]:
        print(f"    * [{c.get('category_id'):>6}] {c.get('name'):<40}: {c.get('total'):>5,} 件")
except Exception as e:
    print(f" - 无法读取 data_volume_report.json: {e}")

# 3. 检查数据库中已抓取商品的 ID 分布范围 (MIN ID, MAX ID)
min_id, max_id = cursor.execute("SELECT min(cast(product_id as integer)), max(cast(product_id as integer)) FROM products WHERE product_id GLOB '[0-9]*'").fetchone()
print(f"\n[3] 数据库已采集商品的 ID 实际分布区间:")
print(f" - 最小 Product ID: {min_id:,}")
print(f" - 最大 Product ID: {max_id:,}")

# 4. 统计数据库中已抓取商品覆盖了多少个分类
cats_in_db = cursor.execute("SELECT category_path, count(*) FROM products GROUP BY category_path ORDER BY count(*) DESC LIMIT 10").fetchall()
print(f"\n[4] 数据库中已覆盖的核心品类分布 (Top 10):")
for cp, cnt in cats_in_db:
    print(f" - {cp[:50]:<50}: {cnt:>5,} 件")

conn.close()
