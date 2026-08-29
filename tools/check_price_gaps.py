import sqlite3
import json

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

# 1. 统计价格缺失情况
total = cursor.execute("SELECT count(*) FROM products").fetchone()[0]
no_price_rows = cursor.execute("""
    SELECT count(*) FROM products 
    WHERE price IS NULL OR price = '' OR price = '0' OR price = '0.0' OR price = 'Protected' OR price LIKE '%Protect%'
""").fetchall()

no_price_count = no_price_rows[0][0]

sample_no_price = cursor.execute("""
    SELECT product_id, sku, title, price, discount_price, original_price 
    FROM products 
    WHERE price IS NULL OR price = '' OR price = '0' OR price = '0.0' OR price = 'Protected' OR price LIKE '%Protect%'
    LIMIT 5
""").fetchall()

print("="*65)
print(f" 数据库商品价格完整度普查:")
print(f" - 总商品数:           {total:,} 件")
print(f" - 已有有效价格商品:   {total - no_price_count:,} 件 ({(total - no_price_count)/total*100:4.1f}%)")
print(f" - 待二次探测价格商品: {no_price_count:,} 件 ({no_price_count/total*100:4.1f}%)")
print("="*65)
print("缺失价格样本:")
for s in sample_no_price:
    print(f" - PID: {s[0]} | SKU: {s[1]:<14} | 价格: {s[3]} | 折扣: {s[4]} | MSRP: {s[5]} | 标题: {s[2][:30]}...")

conn.close()
