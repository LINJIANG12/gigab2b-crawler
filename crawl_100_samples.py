import sys
import os
import json
import time

# 强制 UTF-8 标准输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from database import Database
from cookie_manager import get_authenticated_session, check_login_status
from parser import ProductParser
from exporter import DataExporter
from concurrent.futures import ThreadPoolExecutor, as_completed

TARGET_COUNT = 100

session = get_authenticated_session()
session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*"
})

parser = ProductParser()
db = Database.get_instance()
exporter = DataExporter()

print("="*60)
print(f"       GigaB2B - 开始采集 {TARGET_COUNT} 个商品示例全字段数据")
print("="*60)

# 1. 获取全站分类树
search_url = "https://www.gigab2b.com/index.php?route=product/list/search"
r = session.post(search_url, json={"page": 1, "limit": 30, "search_dimension": 1, "scene": 1}, timeout=15)
cat_tree = r.json().get('data', {}).get('category', [])
leaf_cats = parser.parse_category_tree(cat_tree)
print(f"[+] 成功解析全站末级分类数: {len(leaf_cats)} 个")

# 2. 收集 100 个商品 ID
collected_items = []
seen_pids = set()

# 先加第一页
init_pids = r.json().get('data', {}).get('product_list', [])
for pid in init_pids:
    if pid not in seen_pids:
        seen_pids.add(pid)
        collected_items.append({"product_id": pid, "category": "Featured"})

print(f"[*] 初始商品池: {len(collected_items)} 个")

# 遍历各个子分类补充至 100 个
for cat in leaf_cats:
    if len(collected_items) >= TARGET_COUNT:
        break
    c_id = cat["category_id"]
    c_name = cat["name"]
    res = session.post(search_url, json={"page": 1, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [c_id]}, timeout=10)
    p_list = res.json().get('data', {}).get('product_list', [])
    new_in_cat = 0
    for pid in p_list:
        if pid not in seen_pids:
            seen_pids.add(pid)
            collected_items.append({"product_id": pid, "category": c_name})
            new_in_cat += 1
            if len(collected_items) >= TARGET_COUNT:
                break
    if new_in_cat > 0:
        print(f"  - 分类 [{c_name}]: 获取到 {new_in_cat} 个商品 (累计收集: {len(collected_items)}/{TARGET_COUNT})")

print(f"\n[+] 成功收集到 {len(collected_items)} 个待采集商品，开始多线程并发获取所有字段...\n")

# 3. 多线程并发采集详情全字段
scraped_products = []

def crawl_one(item, idx):
    pid = str(item["product_id"])
    cat = item.get("category", "")
    url = f"https://www.gigab2b.com/index.php?route=product/product&product_id={pid}"
    base_info_url = f"https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id={pid}"
    price_list_url = f"https://www.gigab2b.com/index.php?route=product/info/price/list&product_id={pid}"

    try:
        base_res = session.get(base_info_url, timeout=15).json()
        price_res = session.get(price_list_url, timeout=15).json()
        if base_res.get('code') == 200:
            pdata = parser.parse_api_data(base_res, price_res, product_url=url)
            pdata["product_id"] = pid
            if not pdata.get("category_path") and cat:
                pdata["category_path"] = cat
            db.save_product(pdata)
            return pdata
    except Exception as e:
        print(f"[!] 抓取出错 {pid}: {e}")
    return None

start_time = time.time()
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(crawl_one, item, i) for i, item in enumerate(collected_items)]
    for i, future in enumerate(as_completed(futures), 1):
        res = future.result()
        if res:
            scraped_products.append(res)
            price_str = f"{res.get('currency', '$')}{res.get('price', '-')}"
            sku_str = res.get('sku') or '-'
            title_str = (res.get('title') or 'Unknown')[:35]
            img_count = len(res.get('gallery_images', []))
            print(f"[{i:03d}/{len(collected_items)}] ID:{res['product_id']} | SKU:{sku_str:<12} | 价格:{price_str:<8} | 图片:{img_count:2d}张 | {title_str}")

cost = time.time() - start_time
print("\n" + "="*60)
print(f"[+] 采集完毕！成功抓取: {len(scraped_products)} 条，耗时: {cost:.1f} 秒")
print("="*60)

# 4. 导出
excel_file = exporter.export_to_excel_chunked(scraped_products, "gigab2b_sample_100.xlsx")
csv_file = exporter.export_to_csv(scraped_products, "gigab2b_sample_100.csv")

print(f"\n[+] 示例数据报表已成功生成：")
for ef in excel_file:
    print(f"  * Excel 文件: {ef}")
print(f"  * CSV  文件: {csv_file}")
