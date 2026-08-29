import sqlite3

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

total = cursor.execute("SELECT count(*) FROM products").fetchone()[0]

fields = ["price", "discount_price", "original_price", "drop_ship_fee", "cloud_freight_range", "moq"]
print("="*60)
print(f" 全站 {total:,} 条商品各价格/费用字段填充统计:")
print("="*60)

for f in fields:
    has_val = cursor.execute(f"""
        SELECT count(*) FROM products 
        WHERE {f} IS NOT NULL AND {f} != '' AND {f} != '0' AND {f} != '0.0' AND {f} != 'None'
    """).fetchone()[0]
    print(f" - 字段 [{f:<20}]: 填充率 {has_val:>6,} / {total:,} ({has_val/total*100:5.1f}%) | 缺失 {total - has_val:,} 条")

conn.close()
