import sqlite3
import csv
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

print("="*75)
print("              深入排查 '89.99' 出现频次与根本原因分析")
print("="*75)

# 1. 检查各个字段中 89.99 的出现次数
fields = ["price", "original_price", "discount_price", "drop_ship_fee"]
for f in fields:
    cnt = cursor.execute(f"SELECT count(*) FROM products WHERE {f} = '89.99' OR {f} = '89.9900' OR {f} LIKE '%89.99%'").fetchone()[0]
    print(f" - 字段 [{f:<16}]: 包含 '89.99' 的数量为 {cnt:>6,} 次")

# 2. 采样分析这些商品真实的 price 与 title
sample_rows = cursor.execute("""
    SELECT product_id, sku, title, price, original_price 
    FROM products 
    WHERE original_price = '89.99' OR price = '89.99'
    LIMIT 10
""").fetchall()

print("\n[*] 抽样包含 89.99 的商品真实价格与标题:")
for s in sample_rows:
    print(f" • PID: {s[0]} | SKU: {s[1]:<14} | 批发底价: {s[3]} | 市场MSRP: {s[4]} | 标题: {s[2][:35]}...")

# 3. 检查 CSV 表格中的情况
print("\n" + "="*75)
print(" 检查导出的 96,818 行 CSV 表格中的 89.99 分布:")
print("="*75)

csv_path = "data/gigab2b_full_96818_all.csv"
csv_price_8999 = 0
csv_msrp_8999 = 0
total_csv = 0

with open(csv_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        total_csv += 1
        p = row.get("price") or row.get("B2B批发价 (Price)") or ""
        msrp = row.get("original_price") or row.get("市场参考价 (MSRP)") or ""
        if "89.99" in str(p):
            csv_price_8999 += 1
        if "89.99" in str(msrp):
            csv_msrp_8999 += 1

print(f" - CSV 总行数:           {total_csv:,} 行")
print(f" - B2B批发价为 89.99 行数: {csv_price_8999:,} 行 ({(csv_price_8999/total_csv)*100:4.1f}%)")
print(f" - 市场MSRP为 89.99 行数:  {csv_msrp_8999:,} 行 ({(csv_msrp_8999/total_csv)*100:4.1f}%)")

conn.close()
