import sqlite3
import csv
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("gigab2b.db")
c = conn.cursor()

tot = c.execute("SELECT count(*) FROM products").fetchone()[0]

# 检查 description_text 里是否有尺寸信息
desc_with_dim = c.execute("SELECT count(*) FROM products WHERE description_text LIKE '%Dimensions%' OR description_text LIKE '%Package Size%' OR description_text LIKE '%Weight%'").fetchone()[0]
print(f"[*] 数据库总商品: {tot:,} 款 | 详情描述中包含尺寸/箱规关键词的商品: {desc_with_dim:,} 款 ({desc_with_dim/tot*100:4.1f}%)")

# 检查 CSV 异常
csv_path = "data/gigab2b_full_96818_all.csv"
msrp_samples = []
fee_samples = []
with open(csv_path, "r", encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    for idx, row in enumerate(r, 1):
        m = row.get("original_price", "")
        fee = row.get("drop_ship_fee", "")
        try:
            float(m)
        except Exception:
            if len(msrp_samples) < 5:
                msrp_samples.append((idx, row.get("product_id"), row.get("sku"), m))
        try:
            float(fee)
        except Exception:
            if len(fee_samples) < 5:
                fee_samples.append((idx, row.get("product_id"), row.get("sku"), fee))

print(f"\n[*] MSRP 异常样本 (前 5 个):")
for s in msrp_samples:
    print(f" - Row {s[0]} | PID {s[1]} | SKU {s[2]} | MSRP: '{s[3]}'")

print(f"\n[*] 运费异常样本 (前 5 个):")
for s in fee_samples:
    print(f" - Row {s[0]} | PID {s[1]} | SKU {s[2]} | Fee: '{s[3]}'")

conn.close()
