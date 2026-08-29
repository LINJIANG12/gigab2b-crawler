import sqlite3
import json

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

rows = cursor.execute("""
    SELECT product_id, sku, title, price, total_stock, inventory_warehouses, variants
    FROM products
""").fetchall()

# 1. SPU 计数
total_spus = len(rows)

# 2. SKU 规格展开计数
total_skus = 0
for r in rows:
    v_raw = r[6]
    v_list = []
    try:
        if v_raw:
            v_list = json.loads(v_raw)
    except:
        pass
    total_skus += len(v_list) if v_list else 1

# 3. 分仓展开计数 (每个变体在不同海外仓独立拆行)
total_warehouse_skus = 0
for r in rows:
    wh_raw = r[5]
    v_raw = r[6]
    
    wh_list = []
    try:
        if wh_raw:
            wh_list = json.loads(wh_raw) if wh_raw.startswith("[") or wh_raw.startswith("{") else wh_raw.split(";")
    except:
        pass
    wh_count = max(1, len(wh_list))
    
    v_list = []
    try:
        if v_raw:
            v_list = json.loads(v_raw)
    except:
        pass
    v_count = max(1, len(v_list))
    
    total_warehouse_skus += (v_count * wh_count)

print("="*65)
print(" GigaB2B 全站商品在不同电商分销颗粒度下的精准数据量:")
print("="*65)
print(f" 1. 【SPU 商品主体粒度】:       {total_spus:>7,} 款商品")
print(f" 2. 【SKU 规格变体粒度】:       {total_skus:>7,} 条数据 (按颜色/尺寸展开)")
print(f" 3. 【SKU × 海外分仓分发明细】: {total_warehouse_skus:>7,} 条数据 (按变体+分仓展开)")
print("="*65)

conn.close()
