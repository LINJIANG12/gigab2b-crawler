import csv
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*65)
print(" 检查导出的 CSV 表格中具体哪些行缺失价格:")
print("="*65)

for fname in ["data/gigab2b_products.csv", "data/gigab2b_skus_all.csv"]:
    total = 0
    empty_price = 0
    sample_empty = []
    try:
        with open(fname, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                p = row.get("price") or row.get("B2B批发价 (Price)") or ""
                p_str = str(p).strip()
                if not p_str or p_str == "0" or p_str == "0.0" or p_str == "None":
                    empty_price += 1
                    if len(sample_empty) < 3:
                        sample_empty.append((row.get("product_id"), row.get("sku"), row.get("title"), p_str))
        print(f"\n文件 [{fname}]:")
        print(f" - 总数据行数:     {total:,} 行")
        print(f" - 缺失价格行数:   {empty_price:,} 行 ({empty_price/total*100:4.1f}%)")
        if sample_empty:
            print(" - 样本:")
            for s in sample_empty:
                print(f"   * PID:{s[0]} | SKU:{s[1]} | 价格:'{s[3]}' | 标题:{s[2][:30]}...")
    except Exception as e:
        print(f"文件 [{fname}] 读取错误: {e}")
