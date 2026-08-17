import os
import sys
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import (
    BASE_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY, REQUEST_DELAY, MAX_WORKERS
)
from cookie_manager import get_authenticated_session, check_login_status
from parser import ProductParser
from exporter import DataExporter
from database import Database

class GigaB2BCrawler:
    """
    GigaB2B 全站高效商品爬虫调度引擎：
    采用官方 JSON API 驱动、全站递归分类树、多线程并发详情采集、SQLite 持久化与分卷导出
    """
    def __init__(self, session: requests.Session = None, max_workers: int = 10):
        self.session = session or get_authenticated_session()
        self.session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*"
        })
        self.max_workers = max_workers
        self.parser = ProductParser(base_url=BASE_URL)
        self.db = Database.get_instance()
        self.exporter = DataExporter()

    def fetch_json_api(self, url: str, params: dict = None, json_payload: dict = None, method: str = "GET") -> dict:
        """带智能重试与风控保护的 JSON API 请求"""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(REQUEST_DELAY + random.uniform(0.05, 0.15))
                if method.upper() == "POST":
                    resp = self.session.post(url, params=params, json=json_payload, timeout=REQUEST_TIMEOUT)
                else:
                    resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        return {}
            except Exception as e:
                if attempt == MAX_RETRIES:
                    return {}
                time.sleep(RETRY_DELAY * attempt)
        return {}

    def fetch_category_tree_and_initial_search(self) -> tuple[list[dict], list[int]]:
        """通过 search 接口获取全站完整的分类树及初始商品列表"""
        url = f"{BASE_URL}/index.php?route=product/list/search"
        payload = {
            "page": 1,
            "limit": 30,
            "search_dimension": 1,
            "scene": 1
        }
        res = self.fetch_json_api(url, json_payload=payload, method="POST")
        data = res.get('data', {})
        cat_tree = data.get('category', [])
        leaf_cats = self.parser.parse_category_tree(cat_tree)
        product_list = data.get('product_list', [])
        return leaf_cats, product_list

    def scan_category_products(self, category_id: int = None, max_pages: int = 100, limit: int = None) -> list[int]:
        """
        分页遍历某个分类下的所有商品 ID
        """
        url = f"{BASE_URL}/index.php?route=product/list/search"
        page = 1
        discovered_ids = []

        while page <= max_pages:
            payload = {
                "page": page,
                "limit": 30,
                "search_dimension": 1,
                "scene": 2
            }
            if category_id:
                payload["product_category_id"] = [category_id]

            res = self.fetch_json_api(url, json_payload=payload, method="POST")
            data = res.get('data', {})
            p_list = data.get('product_list', [])
            if not p_list:
                break

            for pid in p_list:
                if pid not in discovered_ids:
                    discovered_ids.append(pid)

            if limit and len(discovered_ids) >= limit:
                break

            page += 1

        return discovered_ids

    def populate_all_tasks(self, limit: int = None):
        """
        扫描全站所有分类并将商品 ID 生成待抓取任务
        """
        print("\n" + "="*50)
        print(" [阶段一] 扫描全站分类与建立商品索引")
        print("="*50)

        leaf_cats, initial_pids = self.fetch_category_tree_and_initial_search()
        print(f"[+] 成功获取全站末级分类数: {len(leaf_cats)} 个")

        initial_tasks = [{"product_id": pid, "url": f"{BASE_URL}/index.php?route=product/product&product_id={pid}"} for pid in initial_pids]
        added = self.db.add_tasks_batch(initial_tasks)
        print(f"[*] 初始商品索引入库: {added} 个")

        if limit and added >= limit:
            print(f"[+] 已达到目标任务数量: {limit}")
            return

        for idx, cat in enumerate(leaf_cats, 1):
            c_id = cat["category_id"]
            c_name = cat["name"]
            print(f"[*] 扫描分类 [{idx}/{len(leaf_cats)}]: {c_name} (ID: {c_id})")
            pids = self.scan_category_products(category_id=c_id, limit=limit)
            tasks = [{"product_id": pid, "url": f"{BASE_URL}/index.php?route=product/product&product_id={pid}", "category": c_name} for pid in pids]
            new_added = self.db.add_tasks_batch(tasks)
            print(f"    - 发现 {len(pids)} 个商品 (新增任务 {new_added} 个)")

            stats = self.db.get_stats()
            if limit and stats["total_tasks"] >= limit:
                print(f"[+] 已达到目标任务数量: {limit}")
                break

    def crawl_single_product_detail(self, task: dict, download_images: bool = False) -> bool:
        """
        通过官方 API 获取商品详情全字段并存库
        """
        pid = str(task["product_id"])
        url = task.get("url") or f"{BASE_URL}/index.php?route=product/product&product_id={pid}"

        base_info_url = f"{BASE_URL}/index.php?route=product/info/info/baseInfos&product_id={pid}"
        price_list_url = f"{BASE_URL}/index.php?route=product/info/price/list&product_id={pid}"

        try:
            base_res = self.fetch_json_api(base_info_url)
            price_res = self.fetch_json_api(price_list_url)

            if not base_res or base_res.get('code') != 200:
                self.db.mark_task_status(pid, "failed", base_res.get('msg', 'Failed to fetch baseInfos'))
                print(f"  [X 失败] ID: {pid} -> {base_res.get('msg')}")
                return False

            product_data = self.parser.parse_api_data(base_res, price_res, product_url=url)
            product_data["product_id"] = pid
            if not product_data.get("category_path") and task.get("category"):
                product_data["category_path"] = task["category"]

            self.db.save_product(product_data)

            if download_images:
                self.exporter.download_product_images(product_data, self.session)

            title_preview = (product_data.get('title') or 'Unknown')[:35]
            price_preview = f"{product_data.get('currency', '$')}{product_data.get('price', '-')}"
            sku_preview = product_data.get('sku') or '-'
            print(f"  [+] ID:{pid} | SKU:{sku_preview} | 价格:{price_preview} | {title_preview}")
            return True
        except Exception as e:
            self.db.mark_task_status(pid, "failed", str(e))
            print(f"  [X 失败] ID:{pid} | 异常: {e}")
            return False

    def run_full_crawl(self, download_images: bool = False, scan_index: bool = True, limit: int = None):
        """
        运行爬虫流程
        """
        # 1. 验证登录状态
        is_ok, msg = check_login_status(self.session)
        print(f"[*] 登录态检查: {msg}")

        # 2. 建立索引
        if scan_index:
            self.populate_all_tasks(limit=limit)

        # 3. 并发采集详情
        print("\n" + "="*50)
        target_count = limit if limit else "全量"
        print(f" [阶段二] 并发采集商品详情全字段 (目标: {target_count} 个 | 线程数: {self.max_workers})")
        print("="*50)

        completed_in_run = 0
        batch_size = min(50, limit) if limit else 200

        while True:
            fetch_limit = min(batch_size, limit - completed_in_run) if limit else batch_size
            if fetch_limit <= 0:
                break

            pending_tasks = self.db.get_pending_tasks(limit=fetch_limit)
            if not pending_tasks:
                break

            stats = self.db.get_stats()
            print(f"\n[*] 当前进度: 已完成 {stats['done_tasks']}/{stats['total_tasks']} | 正在处理批次 ({len(pending_tasks)} 个)...")

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.crawl_single_product_detail, t, download_images): t for t in pending_tasks}
                for f in as_completed(futures):
                    if f.result():
                        completed_in_run += 1
                        if limit and completed_in_run >= limit:
                            break

            if limit and completed_in_run >= limit:
                break

        # 4. 导出
        print("\n" + "="*50)
        print(" [阶段三] 全量数据报表生成与导出")
        print("="*50)

        filename_prefix = f"gigab2b_sample_{limit}" if limit else "gigab2b_products"
        excel_files, csv_file = self.exporter.export_all(
            excel_filename=f"{filename_prefix}.xlsx",
            csv_filename=f"{filename_prefix}.csv"
        )

        stats = self.db.get_stats()
        print(f"\n[+] 采集完成！")
        print(f" - 本次完成采集: {completed_in_run} 个商品")
        print(f" - 数据库累计入库: {stats['total_products']} 个商品")
        for ef in excel_files:
            print(f" - Excel 报表已生成: {ef}")
        if csv_file:
            print(f" - CSV 报表已生成:   {csv_file}")
        print("="*50)
