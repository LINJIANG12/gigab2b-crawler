import requests
import json
import sqlite3
import sys
from bs4 import BeautifulSoup
from cookie_manager import load_cookies

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*75)
print("       严肃法医级诊断：找出我们到底漏掉了哪些真实商品，以及为什么漏采！")
print("="*75)

# 1. 连接本地数据库
conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()
db_pids = set(str(r[0]) for r in cursor.execute("SELECT product_id FROM products").fetchall())
db_skus = set(str(r[0]).strip().upper() for r in cursor.execute("SELECT sku FROM products WHERE sku IS NOT NULL").fetchall())
print(f"[*] 本地数据库现有商品: {len(db_pids):,} 件, SKU: {len(db_skus):,} 个")

# 2. 模拟真实用户访问前台热门分类列表
session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

search_url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 测试 5 个不同的大类
test_categories = [
    (10027, "Living Room > Sofas (沙发)"),
    (10015, "Bedroom > Beds (床架)"),
    (10052, "Dining > Sets (餐桌椅)"),
    (10078, "Outdoor > Patio (户外家具)"),
    (10120, "Office > Chairs (办公椅)"),
]

missing_details = []

for cid, cname in test_categories:
    print(f"\n[*] 正在深入前台类目 [{cid}] {cname} 抓取前台在售商品样本...")
    # 用不同的排序拉取
    for sort_val in ["p.date_added", "p.sales", "p.price"]:
        try:
            payload = {
                "page": 1,
                "limit": 30,
                "search_dimension": 1,
                "scene": 2,
                "product_category_id": [cid],
                "sort": sort_val,
                "order": "DESC"
            }
            res = session.post(search_url, json=payload, timeout=8).json()
            p_list = res.get("data", {}).get("product_list", [])
            for pid in p_list:
                spid = str(pid)
                if spid not in db_pids:
                    # 详细探测该 PID 的接口返回值
                    base_url = f"https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id={spid}"
                    r = session.get(base_url, timeout=6).json()
                    code = r.get("code")
                    pinfo = r.get("data", {}).get("product_info") if isinstance(r.get("data"), dict) else None
                    missing_details.append({
                        "pid": spid,
                        "category": cname,
                        "baseInfos_code": code,
                        "has_pinfo": bool(pinfo),
                        "sku": pinfo.get("sku") if pinfo else None,
                        "title": pinfo.get("product_name") if pinfo else None
                    })
                    if len(missing_details) >= 10:
                        break
            if len(missing_details) >= 10:
                break
        except Exception as e:
            print(f"   类目 {cid} 请求异常: {e}")
    if len(missing_details) >= 10:
        break

print("\n" + "="*75)
print(" 诊断结果：抓取到的 10 个本地数据库缺失商品详情与服务端真实响应:")
print("="*75)
for m in missing_details:
    print(f" • PID: {m['pid']:<8} | 类目: {m['category']:<25} | 接口Code: {m['baseInfos_code']} | 包含详情: {m['has_pinfo']} | SKU: {m['sku']} | 标题: {str(m['title'])[:30]}")

conn.close()
