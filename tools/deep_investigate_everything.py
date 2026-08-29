import requests
import json
import re
import sys
from bs4 import BeautifulSoup
from cookie_manager import load_cookies

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})

print("="*75)
print("       GigaB2B 全站数据量与底层架构彻底大排查 (Deep Investigation)")
print("="*75)

# -------------------------------------------------------------
# 1. 探查前台页面渲染的总数 (Total Count on Frontend Pages)
# -------------------------------------------------------------
print("\n[1] 抓取前台商品列表页 HTML 真实渲染的总数与分类结构:")
urls_to_check = [
    ("全部商品页 (All Products)", "https://www.gigab2b.com/index.php?route=product/list/list"),
    ("热销商品专区 (Hot Sales)", "https://www.gigab2b.com/index.php?route=product/list/list&scene=2"),
    ("供应商合作专区 (Channel)", "https://www.gigab2b.com/index.php?route=product/list/list&scene=6"),
    ("分销专区 (Distribution)", "https://www.gigab2b.com/index.php?route=product/list/list&scene=1"),
]

for label, url in urls_to_check:
    try:
        r = session.get(url, timeout=10)
        html = r.text
        # 提取页面中的 total 数量标识
        totals = re.findall(r'(\d[\d,]*)\s*(?:results|items|products|条|个|件)', html, re.I)
        # 提取 window.__INITIAL_STATE__ 或 json 变量
        js_totals = re.findall(r'total["\']?\s*:\s*(\d+)', html)
        print(f" - {label:<25} -> Status: {r.status_code} | 页面匹配数量: {totals[:3]} | JS变量: {js_totals[:3]}")
    except Exception as e:
        print(f" - {label:<25} -> 抓取异常: {e}")

# -------------------------------------------------------------
# 2. 探查搜索接口在无任何筛选条件下的真实全局 total
# -------------------------------------------------------------
print("\n[2] 探测搜索 API 在不同全局场景 (scene) 下返回的全局 total 数值:")
search_url = "https://www.gigab2b.com/index.php?route=product/list/search"
session.headers.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"})

for sc in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
    try:
        payload = {"page": 1, "limit": 1, "search_dimension": 1, "scene": sc}
        res = session.post(search_url, json=payload, timeout=8).json()
        if res.get("code") == 200:
            d = res.get("data", {})
            p_total = d.get("pagination", {}).get("total")
            cats = len(d.get("category", []))
            print(f" - Scene {sc:>2} -> Code: 200 | pagination.total: {p_total:>7,} | 分类树顶层数: {cats}")
        else:
            print(f" - Scene {sc:>2} -> Code: {res.get('code')}, Msg: {res.get('msg')}")
    except Exception as e:
        print(f" - Scene {sc:>2} -> 请求失败: {e}")

# -------------------------------------------------------------
# 3. 探查商品详情的其他子接口 (是否有更多的变体/SKU API?)
# -------------------------------------------------------------
print("\n[3] 探查商品详情体系下的全部子路由 (是否有单独的变体/SKU接口?):")
sample_pid = 1459370
sub_routes = [
    "product/info/info/baseInfos",
    "product/info/price/list",
    "product/info/info/variantList",
    "product/info/info/options",
    "product/info/info/skuList",
    "product/info/info/skus",
    "product/info/info/combination",
    "product/info/info/detail",
    "product/info/info/attributes",
    "product/info/info/specifications",
    "product/info/info/inventory",
]

for rt in sub_routes:
    try:
        u = f"https://www.gigab2b.com/index.php?route={rt}&product_id={sample_pid}"
        r = session.get(u, timeout=5).json()
        code = r.get("code")
        keys = list(r.get("data", {}).keys()) if isinstance(r.get("data"), dict) else type(r.get("data"))
        print(f" - 路由 {rt:<35} -> Code: {code:>3} | Data Keys: {keys}")
    except Exception as e:
        print(f" - 路由 {rt:<35} -> 非JSON或异常")

# -------------------------------------------------------------
# 4. 探查其他可能的列表接口 (如 supplier, goods, catalog)
# -------------------------------------------------------------
print("\n[4] 探测全站其他潜在商品池接口:")
other_apis = [
    "supplier/product/list",
    "supplier/goods/list",
    "product/supplier/list",
    "distribution/product/list",
    "catalog/product/list",
    "product/all/list",
    "open/product/list",
]
for api in other_apis:
    try:
        u = f"https://www.gigab2b.com/index.php?route={api}"
        r = session.post(u, json={"page": 1, "limit": 10}, timeout=5).json()
        print(f" - 接口 {api:<30} -> Code: {r.get('code')} | Keys: {list(r.get('data', {}).keys()) if isinstance(r.get('data'), dict) else ''}")
    except Exception:
        pass
