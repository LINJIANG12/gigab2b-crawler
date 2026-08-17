import os
import sys
import time
import random
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8')

from config import (
    BASE_URL, SEARCH_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, DEFAULT_WORKERS,
    POOL_CONNECTIONS, POOL_MAXSIZE
)
from cookie_manager import get_authenticated_session, check_login_status, load_cookies
from parser import ProductParser
from exporter import DataExporter
from database import Database

class GigaB2BCrawler:
    """
    GigaB2B 全站商品全量挖掘与采集调度引擎（复合矩阵超空间扫描版）：
    - 矩阵 1：4,800 个微切片价格网格 ($0.01 ~ $6,000)
    - 矩阵 2：217 个全站分类树全覆盖遍历
    - 矩阵 3：全字母 SKU 前缀与品类热词深度探测
    - 阶段二：多线程详情深度采集 + HTTP 连接池复用 + 实时仪表盘 (ETA) + 内存缓冲批量持久化
    - 阶段三：分卷 Excel 与 UTF-8 BOM CSV 全量导出
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/index.php?route=product/list/list",
            "Connection": "keep-alive"
        })

    def fetch_json_api(self, url: str, params: dict = None, json_payload: dict = None, method: str = "GET") -> dict:
        """带自动重连、指数退避与风控检测的 JSON API 请求"""
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
                        if data.get('code') in [403, 429] or 'captcha' in str(data).lower():
                            time.sleep(1.5 * attempt)
                            continue
                        return data
                    except Exception:
                        return {}
                elif resp.status_code in [429, 403]:
                    time.sleep(1.5 * attempt)
            except Exception:
                if attempt == MAX_RETRIES:
                    return {}
                self._configure_connection_pool()
                time.sleep(RETRY_DELAY * attempt + random.uniform(0.05, 0.2))
        return {}

    def fetch_category_tree(self) -> list[dict]:
        """获取全站完整的分类树"""
        url = SEARCH_URL
        payload = {
            "page": 1,
            "limit": 1,
            "search_dimension": 1,
            "scene": 1
        }
        res = self.fetch_json_api(url, json_payload=payload, method="POST")
        cat_tree = res.get('data', {}).get('category', [])
        return self.parser.parse_category_tree(cat_tree)

    def scan_search_space(self, payload_dict: dict) -> list[dict]:
        """通用空间探测器：翻 1~3 页抓取商品"""
        url = SEARCH_URL
        discovered = []
        for page in [1, 2, 3]:
            body = dict(payload_dict)
            body["page"] = page
            body["limit"] = 30
            body["search_dimension"] = 1
            if "scene" not in body:
                body["scene"] = 1
            res = self.fetch_json_api(url, json_payload=body, method="POST")
            p_list = res.get('data', {}).get('product_list', [])
            for pid in p_list:
                discovered.append({
                    "product_id": pid,
                    "url": f"{BASE_URL}/index.php?route=product/product&product_id={pid}"
                })
            if len(p_list) < 12:
                break
        return discovered

    def populate_all_tasks_concurrent(self, limit: int = None):
        """全并发三维复合矩阵空间扫描，彻底构建全站全量商品任务池"""
        print("\n" + "="*65, flush=True)
        print(" [阶段一] 三维复合矩阵空间全并发探测 (挖掘全站 9 万+ 全部商品)", flush=True)
        print("="*65, flush=True)

        tasks_queue = []

        # 1. 价格微切片网格 (约 4,800 个)
        for i in range(0, 1500):
            p1 = i / 10.0
            tasks_queue.append({"price_min": round(p1, 2), "price_max": round(p1 + 0.09, 2), "scene": 1})
        for i in range(1500, 4000, 25):
            p1 = i / 10.0
            tasks_queue.append({"price_min": round(p1, 2), "price_max": round(p1 + 0.24, 2), "scene": 1})
        for i in range(4000, 10000, 50):
            p1 = i / 10.0
            tasks_queue.append({"price_min": round(p1, 2), "price_max": round(p1 + 0.49, 2), "scene": 1})
        for p in range(1000, 2500, 2):
            tasks_queue.append({"price_min": p + 0.01, "price_max": p + 1.99, "scene": 1})
        for p in range(2500, 6000, 10):
            tasks_queue.append({"price_min": p + 0.01, "price_max": p + 9.99, "scene": 1})

        # 2. 217 个分类树直接遍历
        leaf_cats = self.fetch_category_tree()
        for cat in leaf_cats:
            tasks_queue.append({"product_category_id": [cat["category_id"]], "scene": 2})

        # 3. 26 个字母 SKU 前缀与品类核心词
        prefixes = ['W', 'B', 'T', 'S', 'M', 'C', 'D', 'A', 'P', 'H', 'L', 'F', 'G', 'E', 'R', 'N', 'K', 'J', 'O', 'I', 'U', 'V', 'X', 'Y', 'Z', 'Q']
        keywords = ['Table', 'Chair', 'Desk', 'Sofa', 'Cabinet', 'Bed', 'Light', 'Storage', 'Metal', 'Wood', 'Mirror', 'Stand', 'Rack', 'Stool', 'Bench', 'Frame', 'Box', 'Cart', 'Shelf', 'Set']
        for pre in prefixes + keywords:
            tasks_queue.append({"search": pre, "scene": 1})

        print(f"[+] 成功生成复合探测网格: 共 {len(tasks_queue):,} 个空间单元 (价格切片 + 217分类 + SKU前缀/品类词)", flush=True)
        print(f"[*] 正在以 {self.max_workers} 线程并发扫描全站商品索引...", flush=True)

        start_time = time.time()
        total_discovered = 0
        completed_units = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_unit = {
                executor.submit(self.scan_search_space, u): u
                for u in tasks_queue
            }
            for future in as_completed(future_to_unit):
                completed_units += 1
                try:
                    unit_tasks = future.result()
                    new_added = self.db.add_tasks_batch(unit_tasks)
                    total_discovered += new_added
                    if completed_units % 50 == 0 or completed_units == len(tasks_queue):
                        pct = completed_units / len(tasks_queue) * 100
                        print(f"[*] 复合网格进度 [{completed_units:04d}/{len(tasks_queue):,}] ({pct:5.1f}%) | 累计已索引: {total_discovered:,} 件商品", flush=True)
                except Exception:
                    pass

                if limit and total_discovered >= limit:
                    break

        elapsed = time.time() - start_time
        print(f"\n[+] 全站商品索引网格探测完毕！用时 {elapsed:.1f} 秒，累计建立任务: {total_discovered:,} 件", flush=True)

    def crawl_single_product_detail(self, task: dict, download_images: bool = False) -> bool:
        """获取单个商品全量 37 字段并存入内存缓冲队列"""
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
        is_ok, msg = check_login_status(self.session)
        print(f"[*] 登录凭据状态: {msg}", flush=True)

        if scan_index:
            self.populate_all_tasks_concurrent(limit=limit)

        stats = self.db.get_stats()
        total_target = limit if limit else stats["total_tasks"]
        print("\n" + "="*65, flush=True)
        print(f" [阶段二] 启动全站多线程并发详情采集引擎", flush=True)
        print(f"  - 任务总池: {stats['total_tasks']:,} 件商品 (已完成: {stats['done_tasks']:,} 件 | 待抓取: {stats['pending_tasks']:,} 件)", flush=True)
        print(f"  - 并发线程: {self.max_workers} 线程 (连接池深度复用)", flush=True)
        print(f"  - 存储引擎: SQLite WAL 模式 (内存缓冲批量刷盘)", flush=True)
        print("="*65 + "\n", flush=True)

        start_time = time.time()
        completed_in_session = 0
        batch_size = 100

        while True:
            fetch_limit = min(batch_size, limit - completed_in_session) if limit else batch_size
            if fetch_limit <= 0:
                break

            pending_tasks = self.db.get_pending_tasks(limit=fetch_limit)
            if not pending_tasks:
                break

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.crawl_single_product_detail, t, download_images): t for t in pending_tasks}
                for f in as_completed(futures):
                    if f.result():
                        completed_in_session += 1
                        if limit and completed_in_session >= limit:
                            break

            self.db.flush()

            elapsed = time.time() - start_time
            speed = completed_in_session / elapsed if elapsed > 0 else 0
            cur_stats = self.db.get_stats()
            done_count = cur_stats["done_tasks"]
            total_tasks = cur_stats["total_tasks"]
            progress_pct = (done_count / total_tasks * 100) if total_tasks > 0 else 0
            remaining_items = total_tasks - done_count
            eta_seconds = (remaining_items / speed) if speed > 0 else 0
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))

            bar_len = 25
            filled_len = int(bar_len * done_count / total_tasks) if total_tasks > 0 else 0
            bar = '█' * filled_len + '░' * (bar_len - filled_len)

            print(f"[*] 进度: [{bar}] {progress_pct:5.1f}% ({done_count:,}/{total_tasks:,}) | "
                  f"速率: {speed:4.1f} 条/秒 | "
                  f"已耗时: {time.strftime('%H:%M:%S', time.gmtime(elapsed))} | "
                  f"ETA: {eta_str}", flush=True)

            if limit and completed_in_session >= limit:
                break

        self.db.flush()

        print("\n" + "="*65, flush=True)
        print(" [阶段三] 全量数据报表生成与分卷导出", flush=True)
        print("="*65, flush=True)

        filename_prefix = f"gigab2b_sample_{limit}" if limit else "gigab2b_products"
        excel_files, csv_file = self.exporter.export_all(
            excel_filename=f"{filename_prefix}.xlsx",
            csv_filename=f"{filename_prefix}.csv"
        )

        final_stats = self.db.get_stats()
        total_time = time.time() - start_time
        print(f"\n[+] 全站采集圆满完成！", flush=True)
        print(f" - 本次完成抓取: {completed_in_session:,} 件商品", flush=True)
        print(f" - 数据库累计总量: {final_stats['total_products']:,} 件商品", flush=True)
        print(f" - 总耗时: {time.strftime('%H:%M:%S', time.gmtime(total_time))}", flush=True)
        for ef in excel_files:
            print(f" - Excel 报表: {ef}", flush=True)
        if csv_file:
            print(f" - CSV  文件: {csv_file}", flush=True)
        print("="*65, flush=True)
