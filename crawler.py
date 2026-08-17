import os
import sys
import time
import random
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import (
    BASE_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, DEFAULT_WORKERS,
    POOL_CONNECTIONS, POOL_MAXSIZE, AUTO_SNAPSHOT_INTERVAL
)
from cookie_manager import get_authenticated_session, check_login_status, load_cookies
from parser import ProductParser
from exporter import DataExporter
from database import Database

class GigaB2BCrawler:
    """
    GigaB2B 工业级高并发数据采集调度引擎（性能与稳定性终极优化版）：
    - HTTP 连接池深度复用（50并发复用连接，杜绝频繁握手）
    - 指数退避与抖动重试机制，抗抖动网络与防限流
    - 实时采集仪表盘：进度百分比、实时速率(items/s)、预计剩余时间(ETA)
    - 内存缓冲批量入库 + 定期检查点快照，支持无损断点续爬
    """
    def __init__(self, session: requests.Session = None, max_workers: int = DEFAULT_WORKERS):
        self.session = session or get_authenticated_session(load_cookies())
        self._configure_connection_pool()
        self.max_workers = max_workers
        self.parser = ProductParser(base_url=BASE_URL)
        self.db = Database.get_instance()
        self.exporter = DataExporter()

    def _configure_connection_pool(self):
        """配置高性能 HTTP 连接池与底层 Keep-Alive"""
        adapter = HTTPAdapter(
            pool_connections=POOL_CONNECTIONS,
            pool_maxsize=POOL_MAXSIZE,
            max_retries=Retry(
                total=MAX_RETRIES,
                backoff_factor=RETRY_DELAY,
                status_forcelist=[500, 502, 503, 504],
                raise_on_status=False
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
            "Connection": "keep-alive"
        })

    def fetch_json_api(self, url: str, params: dict = None, json_payload: dict = None, method: str = "GET") -> dict:
        """带指数退避、防限流抖动与风控检测的 JSON API 请求"""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
                if method.upper() == "POST":
                    resp = self.session.post(url, params=params, json=json_payload, timeout=REQUEST_TIMEOUT)
                else:
                    resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        # 检测 WAF 验证码拦截
                        if data.get('code') in [403, 429] or 'captcha' in str(data).lower():
                            time.sleep(2.0 * attempt)
                            continue
                        return data
                    except Exception:
                        return {}
                elif resp.status_code in [429, 403]:
                    time.sleep(2.0 * attempt)
            except (requests.exceptions.RequestException, Exception):
                if attempt == MAX_RETRIES:
                    return {}
                time.sleep(RETRY_DELAY * attempt + random.uniform(0.1, 0.5))
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

    def scan_category_products(self, category_id: int = None, max_pages: int = 150, limit: int = None) -> list[int]:
        """分页遍历某个分类下的所有商品 ID"""
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
        """扫描全站所有分类并将商品 ID 批量建立任务索引"""
        print("\n" + "="*60)
        print(" [阶段一] 扫描全站 217 个分类树并建立待采集商品索引")
        print("="*60)

        leaf_cats, initial_pids = self.fetch_category_tree_and_initial_search()
        print(f"[+] 成功获取全站末级分类数: {len(leaf_cats)} 个")

        initial_tasks = [{"product_id": pid, "url": f"{BASE_URL}/index.php?route=product/product&product_id={pid}"} for pid in initial_pids]
        added = self.db.add_tasks_batch(initial_tasks)
        print(f"[*] 初始商品索引入库: {added} 个")

        if limit and added >= limit:
            print(f"[+] 已达到预设测试上限: {limit}")
            return

        total_discovered = added
        for idx, cat in enumerate(leaf_cats, 1):
            c_id = cat["category_id"]
            c_name = cat["name"]
            pids = self.scan_category_products(category_id=c_id, limit=limit)
            tasks = [{"product_id": pid, "url": f"{BASE_URL}/index.php?route=product/product&product_id={pid}", "category": c_name} for pid in pids]
            new_added = self.db.add_tasks_batch(tasks)
            total_discovered += new_added

            print(f"[*] 分类 [{idx:03d}/{len(leaf_cats)}] {c_name[:35]:<35} -> 发现 {len(pids):>4} 件 (全站累计索引: {total_discovered:,} 件)")

            if limit and total_discovered >= limit:
                print(f"\n[+] 已达到目标任务数量: {limit}")
                break

    def crawl_single_product_detail(self, task: dict, download_images: bool = False) -> bool:
        """通过官方 API 获取商品详情全字段并存入缓冲队列"""
        pid = str(task["product_id"])
        url = task.get("url") or f"{BASE_URL}/index.php?route=product/product&product_id={pid}"

        base_info_url = f"{BASE_URL}/index.php?route=product/info/info/baseInfos&product_id={pid}"
        price_list_url = f"{BASE_URL}/index.php?route=product/info/price/list&product_id={pid}"

        try:
            base_res = self.fetch_json_api(base_info_url)
            price_res = self.fetch_json_api(price_list_url)

            if not base_res or base_res.get('code') != 200:
                self.db.mark_task_status(pid, "failed", base_res.get('msg', 'Failed to fetch baseInfos'))
                return False

            product_data = self.parser.parse_api_data(base_res, price_res, product_url=url)
            product_data["product_id"] = pid
            if not product_data.get("category_path") and task.get("category"):
                product_data["category_path"] = task["category"]

            self.db.save_product_buffered(product_data)

            if download_images:
                self.exporter.download_product_images(product_data, self.session)

            return True
        except Exception as e:
            self.db.mark_task_status(pid, "failed", str(e))
            return False

    def run_full_crawl(self, download_images: bool = False, scan_index: bool = True, limit: int = None):
        """执行全站大规模高并发数据采集主流程"""
        # 1. 登录态预检
        is_ok, msg = check_login_status(self.session)
        print(f"[*] 登录凭据状态: {msg}")

        # 2. 扫描并建立全站索引
        if scan_index:
            self.populate_all_tasks(limit=limit)

        # 3. 统计待处理总量
        stats = self.db.get_stats()
        total_target = limit if limit else stats["total_tasks"]
        print("\n" + "="*60)
        print(f" [阶段二] 启动全站多线程并发详情采集引擎")
        print(f"  - 目标总量: {total_target:,} 件商品")
        print(f"  - 并发线程: {self.max_workers} 线程 (连接池深度复用)")
        print(f"  - 存储引擎: SQLite WAL 模式 (内存缓冲批量刷盘)")
        print("="*60 + "\n")

        start_time = time.time()
        completed_in_session = 0
        batch_size = 200

        while True:
            fetch_limit = min(batch_size, limit - completed_in_session) if limit else batch_size
            if fetch_limit <= 0:
                break

            pending_tasks = self.db.get_pending_tasks(limit=fetch_limit)
            if not pending_tasks:
                break

            # 多线程并发采集批次
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.crawl_single_product_detail, t, download_images): t for t in pending_tasks}
                for f in as_completed(futures):
                    if f.result():
                        completed_in_session += 1
                        if limit and completed_in_session >= limit:
                            break

            # 刷新数据库缓冲区
            self.db.flush()

            # 实时控制台仪表盘与 ETA 计算
            elapsed = time.time() - start_time
            speed = completed_in_session / elapsed if elapsed > 0 else 0
            cur_stats = self.db.get_stats()
            done_count = cur_stats["done_tasks"]
            total_tasks = cur_stats["total_tasks"]
            progress_pct = (done_count / total_tasks * 100) if total_tasks > 0 else 0
            remaining_items = total_tasks - done_count
            eta_seconds = (remaining_items / speed) if speed > 0 else 0
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))

            print(f"[*] 进度: [{done_count:,} / {total_tasks:,}] ({progress_pct:5.1f}%) | "
                  f"速率: {speed:4.1f} 条/秒 | "
                  f"已耗时: {time.strftime('%H:%M:%S', time.gmtime(elapsed))} | "
                  f"预计剩余: {eta_str}")

            if limit and completed_in_session >= limit:
                break

        # 强制刷盘
        self.db.flush()

        # 4. 导出全量报表
        print("\n" + "="*60)
        print(" [阶段三] 全量数据报表生成与分卷导出")
        print("="*60)

        filename_prefix = f"gigab2b_sample_{limit}" if limit else "gigab2b_products"
        excel_files, csv_file = self.exporter.export_all(
            excel_filename=f"{filename_prefix}.xlsx",
            csv_filename=f"{filename_prefix}.csv"
        )

        final_stats = self.db.get_stats()
        total_time = time.time() - start_time
        print(f"\n[+] 全站采集圆满完成！")
        print(f" - 本次完成抓取: {completed_in_session:,} 件商品")
        print(f" - 数据库累计总量: {final_stats['total_products']:,} 件商品")
        print(f" - 总耗时: {time.strftime('%H:%M:%S', time.gmtime(total_time))}")
        for ef in excel_files:
            print(f" - Excel 报表: {ef}")
        if csv_file:
            print(f" - CSV  文件: {csv_file}")
        print("="*60)
