# -*- coding: utf-8 -*-
"""
GigaB2B 渠道保护商品价格探测脚本（搜索筛选二分法）

原理（已实测验证）：
- product/list/search 接口的 price_min / price_max 价格筛选对渠道保护商品同样生效
- 用 search=<SKU> 精确锁定商品，配合价格区间二分：
  价格在区间内 -> 商品出现在结果中；否则不出现
- 校准验证：已知价格 74.38 的商品收敛到 74.37~74.38（分精度）

用法：
  py -3.14 crawl_protected_prices.py            # 探测数据库中全部保护商品
  py -3.14 crawl_protected_prices.py --limit 12 # 只探测前 N 个
  py -3.14 crawl_protected_prices.py --dry-run  # 只预览名单不请求

说明：
- 只读查询，不修改平台任何数据
- 每个商品约 18~20 次请求(共约 8 秒)，请勿并发、勿高频，避免触发 WAF 风控
- 结果写入数据库 price 字段（status_reason 记录探测来源），并输出
  data/protected_prices.json 备查
- 注意：此方法绕过平台的"联系卖家/申请合作"机制获取价格，可能违反平台条款，
  请自行评估使用范围，建议仅用于低频、自用场景。
"""
import sys
import os
import json
import time
import random
import sqlite3
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from cookie_manager import get_authenticated_session, load_cookies
from database import Database

BASE = 'https://www.gigab2b.com'
SEARCH_URL = f'{BASE}/index.php?route=product/list/search'
BISECT_STEPS = 18
HI_BOUND = 3000.0  # 假设商品价不超过 $3000（超出会命中不了，自动跳过）
REQUEST_GAP = 0.3  # 每次查询间隔秒数（不含随机抖动）


def build_session():
    s = get_authenticated_session(load_cookies())
    s.headers.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"})
    return s


def in_price_range(s, sku, lo, hi):
    """商品价格是否落在 [lo, hi]（价格筛选预言机）"""
    payload = {'page': 1, 'limit': 30, 'search_dimension': 1, 'scene': 1,
               'search': sku, 'price_min': round(lo, 2), 'price_max': round(hi, 2)}
    time.sleep(REQUEST_GAP + random.uniform(0, 0.1))
    try:
        j = s.post(SEARCH_URL, json=payload, timeout=15).json()
    except Exception:
        return None  # 请求失败（风控/网络），返回 None 表示未知
    d = j.get('data') or {}
    if j.get('code') != 200:
        return None
    return (d.get('pagination') or {}).get('total', 0) > 0


def bisect_price(s, sku):
    """二分探测价格；返回 ((low, high), status)"""
    # 先确认 SKU 可被搜索到
    total_hit = in_price_range(s, sku, 0.01, HI_BOUND)
    if total_hit is None:
        return None, 'request_failed'
    if not total_hit:
        return None, 'not_found_or_above_bound'
    lo, hi = 0.01, HI_BOUND
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2
        hit = in_price_range(s, sku, lo, mid)
        if hit is None:
            return None, 'request_failed'
        if hit:
            hi = mid
        else:
            lo = mid
    return (lo, hi), 'ok'


def load_protected_products(limit=None, dry_run=False):
    """数据库中需补价的保护商品（price 含"申请"标记）"""
    conn = sqlite3.connect(Database.get_instance().db_path)
    conn.row_factory = sqlite3.Row
    sql = ("SELECT product_id, sku, title, price FROM products "
           "WHERE price LIKE '%申请%' OR price = '' OR price IS NULL")
    rows = conn.execute(sql).fetchall()
    conn.close()
    items = []
    for r in rows:
        pid = str(r['product_id'])
        sku = str(r['sku'] or '').strip()
        title = str(r['title'] or '')[:40]
        if sku:
            items.append({'product_id': pid, 'sku': sku, 'title': title})
    if dry_run:
        print(f'[*] 待探测保护商品共 {len(items)} 个（dry-run 预览）:')
        for it in items[:20]:
            print(f'    {it["product_id"]} {it["sku"]} | {it["title"]}')
        return items, True
    return items[:limit] if limit else items, False


def save_result(item, lo, hi):
    price = round((lo + hi) / 2, 2)
    conn = sqlite3.connect(Database.get_instance().db_path)
    conn.execute(
        "UPDATE products SET price = ?, status_reason = ? WHERE product_id = ?",
        (str(price), '渠道保护价(搜索筛选二分探测)', item['product_id']))
    conn.commit()
    conn.close()
    print("  >>> " + item['product_id'] + " " + item['sku'] + " => $" + str(price)
          + " (" + str(round(lo, 2)) + "~" + str(round(hi, 2)) + ")")
    return {'product_id': item['product_id'], 'sku': item['sku'], 'title': item['title'],
            'price_low': round(lo, 2), 'price_high': round(hi, 2), 'price': price}


def main():
    ap = argparse.ArgumentParser(description='GigaB2B 渠道保护商品价格探测')
    ap.add_argument('--limit', type=int, default=None, help='只探测前 N 个')
    ap.add_argument('--dry-run', action='store_true', help='只预览名单，不发请求')
    args = ap.parse_args()

    items, is_dry = load_protected_products(limit=args.limit, dry_run=args.dry_run)
    if is_dry:
        return
    if not items:
        print('[+] 数据库中没有待探测的保护商品')
        return

    print(f'[+] 开始探测 {len(items)} 个渠道保护商品（每个约 {BISECT_STEPS + 1} 次请求）')
    s = build_session()
    results = []
    failed = []
    for i, item in enumerate(items, 1):
        print(f'\n[{i}/{len(items)}] {item["product_id"]} SKU={item["sku"]} | {item["title"]}')
        try:
            (lo, hi), status = bisect_price(s, item['sku'])
            if status == 'ok':
                results.append(save_result(item, lo, hi))
            else:
                print(f'  [X] 跳过: {status}')
                failed.append(item['product_id'])
        except KeyboardInterrupt:
            print('\n[!] 用户中断')
            break
        except Exception as e:
            print(f'  [X] 异常: {e}')
            failed.append(item['product_id'])

    os.makedirs('data', exist_ok=True)
    with open('data/protected_prices.json', 'w', encoding='utf-8') as f:
        json.dump({'results': results, 'failed': failed}, f, ensure_ascii=False, indent=2)
    print(f'\n[+] 完成：成功 {len(results)} 个，失败/跳过 {len(failed)} 个')
    print('    结果: data/protected_prices.json（价格已写入数据库）')


if __name__ == '__main__':
    main()
