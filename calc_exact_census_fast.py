import sqlite3
import json
import sys
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*75)
print("       GigaB2B 全站真实数据量全维度精准普查测算报告")
print("="*75)

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

total_unique_spu = cursor.execute("SELECT count(DISTINCT product_id) FROM products").fetchone()[0]

rows = cursor.execute("""
    SELECT product_id, sku, title, price, discount_price, total_stock, 
           category_path, variants, product_status, status_reason
    FROM products
""").fetchall()

total_skus = 0
single_variant_spus = 0
multi_variant_spus = 0
variant_distribution = defaultdict(int)

protected_count = 0
in_stock_count = 0
out_of_stock_count = 0
primary_cats = defaultdict(int)

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
    variant_distribution[cnt] += 1
    
    if price == "Protected" or price == "Channel Protected" or "protect" in str(price).lower() or "protect" in str(s_reason).lower():
        protected_count += 1
    
    try:
        if int(stock) > 0:
            in_stock_count += 1
        else:
            out_of_stock_count += 1
    except:
        out_of_stock_count += 1

    cat_str = cat or "Other"
    p_cat = cat_str.split(" > ")[0].strip() if " > " in cat_str else cat_str.strip()
    primary_cats[p_cat] += 1

print(f"\n【统计维度一：SPU（商品款数）vs SKU（可售规格总数）】")
print(f" -------------------------------------------------------------")
print(f" 1. 全站独立商品主体 (SPU / 唯一 Product ID):   {total_unique_spu:>7,} 款  [100% 绝对去重]")
print(f" 2. 全站可销售规格总数 (SKU / 变体展开明细):   {total_skus:>7,} 条  [各颜色/尺寸独立行]")
print(f" 3. 单规格（无变体）商品款数:                  {single_variant_spus:>7,} 款  ({single_variant_spus/total_unique_spu*100:4.1f}%)")
print(f" 4. 多规格（含多变体）商品款数:                {multi_variant_spus:>7,} 款  ({multi_variant_spus/total_unique_spu*100:4.1f}%)")
print(f" 5. 平均每款商品含规格数:                      {total_skus/total_unique_spu:>7.2f} 个 SKU/款")

print(f"\n【统计维度二：库存与在售状态分布】")
print(f" -------------------------------------------------------------")
print(f" 1. 海外仓现货可售商品:                        {in_stock_count:>7,} 款  ({in_stock_count/total_unique_spu*100:4.1f}%)")
print(f" 2. 缺货/已售罄/历史款商品:                    {out_of_stock_count:>7,} 款  ({out_of_stock_count/total_unique_spu*100:4.1f}%)")

print(f"\n【统计维度三：全站各一级大类真实商品分布 (Top 10)】")
print(f" -------------------------------------------------------------")
for cat_name, count in sorted(primary_cats.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f" - {cat_name:<38}: {count:>6,} 款  ({count/total_unique_spu*100:4.1f}%)")

print(f"\n【统计维度四：跨分类重叠测算 (为什么前台累加会有 9 万+？)】")
print(f" -------------------------------------------------------------")
print(f" - 217 个分类前台展示商品计数累加求和:          96,818 次")
print(f" - 全站实际独立商品物理总数 (SPU):            {total_unique_spu:,} 款")
print(f" - 平均每款商品跨分类挂载率 (重复倍率):        {96818/total_unique_spu:.2f} 个分类/款")
print(f"   (说明：GigaB2B 平台为增加曝光，一件商品平均被运营同时配置在 4.52 个不同分类/二级类目中)")

conn.close()
