import requests
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from cookie_manager import get_authenticated_session
from parser import ProductParser

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

session = get_authenticated_session()
session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 1. 获取全部分类树
r = session.post(url, json={"page": 1, "limit": 1, "search_dimension": 1, "scene": 1}).json()
cat_tree = r.get('data', {}).get('category', [])

parser = ProductParser()
leaf_cats = parser.parse_category_tree(cat_tree)
print(f"[*] 全站共解析出末级分类: {len(leaf_cats)} 个")

category_counts = {}

def get_cat_total(cat):
    c_id = cat['category_id']
    c_name = cat['name']
    try:
        res = session.post(url, json={
            "page": 1,
            "limit": 1,
            "search_dimension": 1,
            "scene": 2,
            "product_category_id": [c_id]
        }, timeout=15).json()
        total = res.get('data', {}).get('pagination', {}).get('total', 0)
        return c_name, c_id, total
    except Exception as e:
        return c_name, c_id, 0

print("[*] 正在多线程并发测算全站 217 个分类的商品总数...")

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(get_cat_total, cat) for cat in leaf_cats]
    for f in as_completed(futures):
        c_name, c_id, total = f.result()
        category_counts[c_name] = total

# 统计分析
total_sum = sum(category_counts.values())
sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

print("\n" + "="*60)
print(f"              GigaB2B 全站商品体量精确测算报告")
print("="*60)
print(f" - 全站末级分类总数: {len(leaf_cats)} 个")
print(f" - 全部分类商品累加总数: {total_sum:,} 件")
print("\n[+] Top 20 大分类商品数量分布：")
for idx, (name, cnt) in enumerate(sorted_cats[:20], 1):
    print(f"  {idx:02d}. {name:<45} : {cnt:>5} 件")

print("\n[+] 商品数量较少/小众分类示例：")
for idx, (name, cnt) in enumerate([c for c in sorted_cats if c[1] > 0][-5:], 1):
    print(f"  - {name:<45} : {cnt:>5} 件")

# 输出统计文件
with open('data_volume_report.json', 'w', encoding='utf-8') as f:
    json.dump({
        "total_categories": len(leaf_cats),
        "total_products_estimate": total_sum,
        "category_distribution": sorted_cats
    }, f, ensure_ascii=False, indent=2)

print("\n[+] 完整测算明细已保存至 data_volume_report.json")
