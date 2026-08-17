# -*- coding: utf-8 -*-
"""
GigaB2B 免登录价格采集脚本（最大化无登录态可获取的价格信息）

原理（实测结论）：
- 匿名请求会被 safe/captcha 拦截；无 Cookie 带浏览器头会被 302 重定向到登录页；
- 带上任意会话 Cookie（OCSESSID，即使 login_flag=0 未登录）即可访问 JSON API；
- 价格可见性由服务端按卖家设置返回：price_visible=True 的商品在
  product/list/list 批量接口直接返回 price_info{min,max}，在
  product/info/price/list 返回完整 base_price_info（含折扣价）；
- price_visible=False 的商品所有接口 base_price_info 均为空 —— 无服务端旁路，
  只能使用真实登录态（见 cookie_manager / README 的 Edge 提取或剪贴板方式）。

本脚本：
1. 收集商品 ID（全局首页 + 若干末级分类第一页）
2. 用 product/list/list 批量接口（每批 100 个）获取 price_info
3. 对价格可见的商品，按需再拉 product/info/price/list 全字段价格
4. 输出 data/prices_no_login.json 与 data/prices_no_login.csv
"""
import sys
import os
import json
import csv
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from cookie_manager import get_authenticated_session, load_cookies
from parser import ProductParser

BASE_URL = "https://www.gigab2b.com"
SEARCH_URL = f"{BASE_URL}/index.php?route=product/list/search"
LIST_URL = f"{BASE_URL}/index.php?route=product/list/list"
PRICE_URL = f"{BASE_URL}/index.php?route=product/info/price/list"

BATCH_SIZE = 100      # 批量接口每批商品数
SAMPLE_CATS = 12      # 抽样分类数（0 = 只用全局首页）
MAX_IDS = 600         # 本次最多收集多少个商品 ID
FULL_PRICE_LIMIT = 80 # 对价格可见商品拉全量价格的个数上限（0 = 不拉）
WORKERS = 6


def get_session():
    s = get_authenticated_session(load_cookies())
    s.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*"
    })
    return s


def fetch_json(s, url, payload=None, method="GET", timeout=15):
    for attempt in range(3):
        try:
            time.sleep(0.3 + random.uniform(0.05, 0.15))
            if method.upper() == "POST":
                r = s.post(url, json=payload, timeout=timeout)
            else:
                r = s.get(url, params=payload, timeout=timeout)
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    return {}
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {}


def collect_ids(s, max_ids=MAX_IDS, sample_cats=SAMPLE_CATS):
    """全局首页 + 若干分类第一页收集商品 ID"""
    ids = []
    seen = set()

    def add(pid, cat):
        pid = int(pid)
        if pid not in seen:
            seen.add(pid)
            ids.append({"product_id": pid, "category": cat})

    # 全局首页（scene=1）
    res = fetch_json(s, SEARCH_URL, {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1}, "POST")
    data = res.get("data") or {}
    for pid in data.get("product_list") or []:
        add(pid, "Featured")

    parser = ProductParser()
    cats = parser.parse_category_tree(data.get("category") or [])

    # 抽样分类
    random.seed(42)
    sample = cats[:sample_cats]
    for cat in sample:
        if len(ids) >= max_ids:
            break
        res = fetch_json(s, SEARCH_URL, {
            "page": 1, "limit": 30, "search_dimension": 1, "scene": 2,
            "product_category_id": [cat["category_id"]]
        }, "POST")
        for pid in (res.get("data") or {}).get("product_list") or []:
            add(pid, cat["name"])
            if len(ids) >= max_ids:
                break

    return ids


def batch_price_info(s, ids):
    """product/list/list 批量接口获取 price_info（min/max）与可见性"""
    result = {}
    for i in range(0, len(ids), BATCH_SIZE):
        chunk = ids[i:i + BATCH_SIZE]
        res = fetch_json(s, LIST_URL, {
            "product_ids": chunk,
            "with_seller": True,
            "with_wishlist": False,
            "type": "list"
        }, "POST", timeout=25)
        for item in res.get("data") or []:
            p = item.get("product") or {}
            pid = p.get("id")
            pi = p.get("price_info")
            result[pid] = {
                "price_visible": pi is not None,
                "price_min": (pi or {}).get("min"),
                "price_max": (pi or {}).get("max"),
                "map": (pi or {}).get("map"),
                "title": p.get("name") or "",
                "sku": p.get("sku") or "",
                "store": ((item.get("seller") or {}).get("store_name")) or "",
                "is_available": p.get("is_available"),
            }
    return result


def full_price(s, pid):
    res = fetch_json(s, PRICE_URL, {"product_id": pid}, "GET")
    d = (res.get("data") or {}) if res.get("code") == 200 else {}
    bp = d.get("base_price_info") or {}
    opts = d.get("option") or []
    return {
        "price": bp.get("price"),
        "discount_price": bp.get("discount_price"),
        "original_price": bp.get("line_through_normal_price"),
        "currency": "$",
        "moq": bp.get("moq"),
        "variant_pids": [o.get("product_id") for o in opts if o.get("product_id")],
        "variant_titles": [o.get("title") for o in opts if o.get("title")],
        "qty_visible": d.get("qty_visible"),
        "is_cooperate": d.get("is_cooperate"),
    }


def main():
    print("=" * 60)
    print(" GigaB2B 免登录价格采集（尽力而为版）")
    print("=" * 60)

    s = get_session()
    ids = collect_ids(s)
    print(f"[+] 收集商品 ID: {len(ids)} 个")

    info = batch_price_info(s, [i["product_id"] for i in ids])
    visible = [pid for pid, v in info.items() if v["price_visible"]]
    hidden = [pid for pid, v in info.items() if not v["price_visible"]]
    print(f"[+] 价格可见: {len(visible)} | 价格隐藏: {len(hidden)}")

    # 对可见商品拉全量价格
    details = {}
    if FULL_PRICE_LIMIT > 0 and visible:
        todo = visible[:FULL_PRICE_LIMIT]
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(full_price, s, pid): pid for pid in todo}
            for f in as_completed(futs):
                pid = futs[f]
                try:
                    details[pid] = f.result()
                except Exception:
                    details[pid] = {}
        print(f"[+] 已拉取 {len(details)} 个商品的全量价格明细")

    # 汇总输出
    rows = []
    for pid in [i["product_id"] for i in ids]:
        v = info.get(pid, {})
        det = details.get(pid, {})
        rows.append({
            "product_id": pid,
            "category": next((i["category"] for i in ids if i["product_id"] == pid), ""),
            "sku": v.get("sku", ""),
            "title": v.get("title", ""),
            "store": v.get("store", ""),
            "price_visible": v.get("price_visible", False),
            "price_min": v.get("price_min"),
            "price_max": v.get("price_max"),
            "map_price": v.get("map"),
            "detail_price": det.get("price"),
            "discount_price": det.get("discount_price"),
            "original_price": det.get("original_price"),
            "moq": det.get("moq"),
            "variant_count": len(det.get("variant_titles", [])),
            "variant_pids": "|".join(map(str, det.get("variant_pids", []))),
            "is_available": v.get("is_available"),
        })

    os.makedirs("data", exist_ok=True)
    with open("data/prices_no_login.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    with open("data/prices_no_login.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["product_id"])
        w.writeheader()
        w.writerows(rows)

    print("\n" + "=" * 60)
    print(f"[+] 完成！共 {len(rows)} 条")
    print(f"    价格可见 {len(visible)} 条（已尽力抓取价格）")
    print(f"    价格隐藏 {len(hidden)} 条（需真实登录态，见 README 的 Cookie 方式）")
    print("    输出: data/prices_no_login.json / data/prices_no_login.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()
