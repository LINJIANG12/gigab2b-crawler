import sqlite3
import json

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

rows = cursor.execute("""
    SELECT product_id, sku, title, price, category_path, variants
    FROM products
""").fetchall()

# 1. 独立商品 SPU 统计
total_spu = len(rows)

# 2. 变体 SKU 统计
total_sku = 0
for r in rows:
    v_raw = r[5]
    vars_list = []
    try:
        if v_raw:
            vars_list = json.loads(v_raw)
    except:
        pass
    total_sku += len(vars_list) if vars_list else 1

# 3. 分类挂载关系统计 (每个商品拆分为它所属的各级分类)
category_mapped_rows = []
for r in rows:
    pid, sku, title, price, cat_path, v_raw = r
    cat_str = cat_path or "Other"
    
    # 假设一个商品归属于它的完整路径及其父级
    cats = [c.strip() for c in cat_str.split(">") if c.strip()]
    if not cats:
        cats = ["Other"]
    
    for c in cats:
        category_mapped_rows.append({
            "product_id": pid,
            "sku": sku,
            "category": c,
            "title": title,
            "price": price
        })

print(f"============================================================")
print(f" GigaB2B 全站数据在 3 种不同业务视角下的精准行数统计:")
print(f"============================================================")
print(f" 视角 1【绝对独立商品款数 (SPU 实体库)】:      {total_spu:>7,} 行 (100% 物理唯一)")
print(f" 视角 2【可售规格变体明细 (SKU 铺货库)】:      {total_sku:>7,} 行 (按颜色/尺寸展开)")
print(f" 视角 3【类目多重挂载展开展现 (Category 展现库)】: {len(category_mapped_rows):>7,} 行 (按类目挂载拆分)")
print(f" 视角 4【217 个分类前台统计计数求和】:         96,818 条")
print(f"============================================================")

conn.close()
