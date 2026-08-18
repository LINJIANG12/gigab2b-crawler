import sqlite3
import json

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

total = cursor.execute("SELECT count(*) FROM products").fetchone()[0]

print("="*75)
print(f"       GigaB2B 本地数据库 {total:,} 条商品全字段质量与空值率深度体检")
print("="*75)

# 获取所有列名
cursor.execute("PRAGMA table_info(products)")
columns = [col[1] for col in cursor.fetchall() if col[1] not in ["created_at", "updated_at", "id"]]

field_stats = []

for col in columns:
    # 统计有效填充数量
    filled = cursor.execute(f"""
        SELECT count(*) FROM products 
        WHERE {col} IS NOT NULL 
          AND {col} != '' 
          AND {col} != '0' 
          AND {col} != '0.0' 
          AND {col} != 'None' 
          AND {col} != '[]' 
          AND {col} != '{{}}'
    """).fetchone()[0]
    
    empty_cnt = total - filled
    fill_rate = (filled / total * 100) if total > 0 else 0
    field_stats.append((col, filled, empty_cnt, fill_rate))

# 按填充率从低到高排序输出
field_stats.sort(key=lambda x: x[3])

print(f"{'字段名称 (Column Name)':<28} | {'有效填充数':>10} | {'缺失空值数':>10} | {'填充率':>8}")
print("-" * 75)
for col, filled, empty_cnt, fill_rate in field_stats:
    flag = " ⚠️ 缺失较多" if fill_rate < 50 else (" ⚡ 部分缺失" if fill_rate < 90 else " ✅ 完整")
    print(f"{col:<28} | {filled:>10,} | {empty_cnt:>10,} | {fill_rate:>7.1f}%{flag}")

print("="*75)

# 变体展开统计
rows = cursor.execute("SELECT variants FROM products").fetchall()
total_skus = 0
multi_var_pids = 0
for r in rows:
    v_raw = r[0]
    v_list = []
    try:
        if v_raw:
            v_list = json.loads(v_raw)
    except:
        pass
    if v_list and len(v_list) > 1:
        multi_var_pids += 1
        total_skus += len(v_list)
    else:
        total_skus += 1

print(f"变体结构统计:")
print(f" - 单品商品:   {total - multi_var_pids:,} 款 ({(total - multi_var_pids)/total*100:4.1f}%)")
print(f" - 多变体商品: {multi_var_pids:,} 款 ({multi_var_pids/total*100:4.1f}%)")
print(f" - SKU 展开总数: {total_skus:,} 条")
print("="*75)

conn.close()
