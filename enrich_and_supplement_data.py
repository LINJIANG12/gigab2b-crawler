import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from cookie_manager import load_cookies
from parser import ProductParser
from database import Database

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')

session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest"
})

db = Database.get_instance()
parser = ProductParser()

print("="*70)
print(" 阶段一：补充扫描 [1,600,000 ~ 1,630,000] 最新商品号段")
print("="*70)

# 加载已有商品 ID
existing_pids = set(r[0] for r in db._get_conn().execute("SELECT product_id FROM products").fetchall())
print(f"[*] 数据库已有商品: {len(existing_pids):,} 件")

pids_to_scan = [p for p in range(1600001, 1630001) if str(p) not in existing_pids]
print(f"[*] 待补充扫描号段数: {len(pids_to_scan):,} 个 ID")

new_saved = 0
scanned = 0
total_scan = len(pids_to_scan)

def fetch_single_new(pid):
    spid = str(pid)
    base_url = f"https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id={spid}"
    price_url = f"https://www.gigab2b.com/index.php?route=product/info/price/list&product_id={spid}"
    try:
        r1 = session.get(base_url, timeout=6)
        if r1.status_code == 200:
            j1 = r1.json()
            if j1.get("code") == 200 and j1.get("data") and j1.get("data").get("product_info"):
                try:
                    r2 = session.get(price_url, timeout=6)
                    j2 = r2.json() if r2.status_code == 200 else {}
                except:
                    j2 = {}
                data = parser.parse_api_data(j1, j2, product_url=f"https://www.gigab2b.com/index.php?route=product/product&product_id={spid}")
                data["product_id"] = spid
                return True, data
    except:
        pass
    return False, None

if pids_to_scan:
    with ThreadPoolExecutor(max_workers=35) as ex:
        chunk_size = 500
        for i in range(0, total_scan, chunk_size):
            chunk = pids_to_scan[i:i+chunk_size]
            futures = [ex.submit(fetch_single_new, p) for p in chunk]
            for f in as_completed(futures):
                valid, data = f.result()
                scanned += 1
                if valid and data:
                    db.save_product_buffered(data)
                    new_saved += 1
            db.flush()
            print(f"[*] 补充扫描进度: {scanned:,}/{total_scan:,} ({(scanned/total_scan)*100:4.1f}%) | 新增入库: {new_saved:,} 件", flush=True)

print(f"\n[+] 补充号段扫描完成！本次新增入库: {new_saved:,} 件")

# 阶段二：对价格/费用为 0 或缺失的商品进行定向二次探查
print("\n" + "="*70)
print(" 阶段二：对运费/折扣价/MSRP 缺失商品进行二次全量深度探查与补齐")
print("="*70)

incomplete_rows = db._get_conn().execute("""
    SELECT product_id, sku FROM products 
    WHERE drop_ship_fee IS NULL OR drop_ship_fee = '' OR drop_ship_fee = '0' OR original_price IS NULL OR original_price = ''
""").fetchall()

print(f"[*] 待补全深层费用与 MSRP 的商品数: {len(incomplete_rows):,} 件")

def recheck_pricing(item):
    pid, sku = item
    price_url = f"https://www.gigab2b.com/index.php?route=product/info/price/list&product_id={pid}"
    try:
        r = session.get(price_url, timeout=5)
        if r.status_code == 200:
            j = r.json()
            if j.get("code") == 200 and j.get("data"):
                d = j["data"]
                # 提取运费和零售价
                msrp = d.get("msrp") or d.get("retail_price") or d.get("market_price") or ""
                fee = d.get("shipping_fee") or d.get("drop_shipping_fee") or d.get("freight") or ""
                return pid, msrp, fee
    except:
        pass
    return pid, None, None

fixed_cnt = 0
with ThreadPoolExecutor(max_workers=30) as ex:
    futures = [ex.submit(recheck_pricing, item) for item in incomplete_rows]
    for f in as_completed(futures):
        pid, msrp, fee = f.result()
        if msrp or fee:
            updates = []
            params = []
            if msrp:
                updates.append("original_price = ?")
                params.append(str(msrp))
            if fee:
                updates.append("drop_ship_fee = ?")
                params.append(str(fee))
            if updates:
                params.append(pid)
                db._get_conn().execute(f"UPDATE products SET {', '.join(updates)} WHERE product_id = ?", params)
                fixed_cnt += 1
                if fixed_cnt % 500 == 0:
                    db._get_conn().commit()
                    print(f"[*] 已优化补齐 {fixed_cnt:,} 件商品深层价格/运费数据...", flush=True)

db._get_conn().commit()
print(f"[+] 二次探查优化完成！累计补齐优化 {fixed_cnt:,} 件商品")

# 导出最新全量 SKU 与 SPU 报表
print("\n[*] 正在重新生成并导出全量 9 万+ SKU 明细与 SPU 报表...")
from exporter import DataExporter
exporter = DataExporter()
efs, cf = exporter.export_all()
sk_efs, sk_cf = exporter.export_expanded_skus()

print("\n" + "="*70)
print("               全部数据二次探查与导出圆满完成！")
print("="*70)
print("1. 全量独立 SPU 报表:")
for f in efs: print(f" - Excel: {f}")
print(f" - CSV:   {cf}")
print("\n2. 全量 9 万+ SKU 变体明细报表:")
for f in sk_efs: print(f" - Excel (分卷): {f}")
print(f" - CSV (全量):   {sk_cf}")
