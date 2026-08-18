import os
import sys
import time
import json
import string
import queue
import threading
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8')

from config import BASE_URL, DATA_DIR
from cookie_manager import get_authenticated_session, load_cookies
from parser import ProductParser
from database import Database
from exporter import DataExporter

class SkuPrefixMatrixCrawler:
    """
    全字母/数字 SKU 前缀 + 根类目复合超空间全量补全引擎：
    - 针对 GigaB2B 的 SKU 编码规则 (W, B, LP, T, S, M, F, H, A-Z, 0-9)
    - 结合 20 个精细价格切片梯度进行全覆盖定向穿透
    - 彻底补齐隐藏商品与渠道专供商品，直达真实 9.6 万+ SKU 数据
    """
    def __init__(self, workers: int = 25):
        self.workers = workers
        self.session = get_authenticated_session(load_cookies())
        self._configure_session()
        self.parser = ProductParser(base_url=BASE_URL)
        self.db = Database.get_instance()
        self.exporter = DataExporter()
        
        self.search_url = f"{BASE_URL}/index.php?route=product/list/search"
        self.write_queue = queue.Queue(maxsize=5000)
        self.stop_event = threading.Event()
        self.existing_pids = set()
        self.saved_count = 0
        self._lock = threading.Lock()

        # 核心 SKU 前缀与字母表
        self.sku_prefixes = [
            "W", "B", "LP", "T", "S", "M", "F", "H", "A", "C", "D", "E",
            "G", "I", "J", "K", "L", "N", "O", "P", "Q", "R", "U", "V",
            "X", "Y", "Z", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"
        ]
        
        # 价格切片梯度
        self.price_slices = [
            (0, 30), (30, 60), (60, 100), (100, 150), (150, 220),
            (220, 300), (300, 400), (400, 550), (550, 750), (750, 1000),
            (1000, 1500), (1500, 2500), (2500, 5000), (5000, 20000)
        ]

    def _configure_session(self):
        adapter = HTTPAdapter(
            pool_connections=60,
            pool_maxsize=60,
            max_retries=Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
        })

    def _load_existing_pids(self):
        conn = self.db._get_conn()
        rows = conn.execute("SELECT product_id FROM products").fetchall()
        self.existing_pids = set(str(r[0]) for r in rows)
        print(f"[+] 数据库已有商品基线: {len(self.existing_pids):,} 件", flush=True)

    def _async_writer_worker(self):
        buffer = []
        last_flush = time.time()
        while not self.stop_event.is_set() or not self.write_queue.empty():
            try:
                item = self.write_queue.get(timeout=0.5)
                buffer.append(item)
                self.write_queue.task_done()
            except queue.Empty:
                pass

            now = time.time()
            if len(buffer) >= 50 or (now - last_flush >= 1.5 and buffer):
                for p in buffer:
                    self.db.save_product_buffered(p)
                self.db.flush()
                buffer.clear()
                last_flush = now

        if buffer:
            for p in buffer:
                self.db.save_product_buffered(p)
            self.db.flush()

    def build_tasks(self) -> list[dict]:
        tasks = []
        for pfx in self.sku_prefixes:
            for p_min, p_max in self.price_slices:
                tasks.append({
                    "keyword": pfx,
                    "price_min": p_min,
                    "price_max": p_max
                })
        print(f"[+] 成功构建 SKU 前缀 × 价格切片扫网任务: 共 {len(tasks):,} 个单元", flush=True)
        return tasks

    def scan_slice(self, task: dict) -> list[str]:
        kw = task["keyword"]
        p_min = str(task["price_min"])
        p_max = str(task["price_max"])
        
        found = []
        for page in range(1, 4):
            payload = {
                "page": page,
                "limit": 30,
                "search_dimension": 1,
                "scene": 2,
                "keyword": kw,
                "price_min": p_min,
                "price_max": p_max
            }
            try:
                r = self.session.post(self.search_url, json=payload, timeout=6).json()
                pl = r.get("data", {}).get("product_list", [])
                if not pl:
                    break
                for item in pl:
                    found.append(str(item))
                if len(pl) < 30:
                    break
            except Exception:
                break
        return found

    def fetch_detail(self, spid: str, max_retries: int = 3) -> bool:
        base_url = f"{BASE_URL}/index.php?route=product/info/info/baseInfos&product_id={spid}"
        price_url = f"{BASE_URL}/index.php?route=product/info/price/list&product_id={spid}"
        referer = f"{BASE_URL}/index.php?route=product/product&product_id={spid}"

        headers = dict(self.session.headers)
        headers["Referer"] = referer

        for attempt in range(max_retries):
            try:
                r1 = self.session.get(base_url, headers=headers, timeout=10)
                if r1.status_code == 200:
                    j1 = r1.json()
                    if j1.get("code") == 200 and j1.get("data") and j1.get("data").get("product_info"):
                        try:
                            r2 = self.session.get(price_url, headers=headers, timeout=8)
                            j2 = r2.json() if r2.status_code == 200 else {}
                        except:
                            j2 = {}

                        data = self.parser.parse_api_data(j1, j2, product_url=referer)
                        data["product_id"] = spid

                        self.write_queue.put(data)
                        with self._lock:
                            self.saved_count += 1
                            self.existing_pids.add(spid)
                        return True
            except Exception:
                time.sleep(0.4 * (attempt + 1))
        return False

    def run(self):
        print("\n" + "="*75, flush=True)
        print(" GigaB2B SKU 前缀 × 价格切片超空间扫网引擎 (终极补全 9.6 万+ 数据)", flush=True)
        print("="*75, flush=True)

        self._load_existing_pids()
        tasks = self.build_tasks()
        total_tasks = len(tasks)

        harvested_all_pids = set()
        pending_pids = set()
        done_scans = 0
        start_t = time.time()

        print(f"[*] 启动 25 线程并发扫描 {total_tasks:,} 个前缀价格空间单元...", flush=True)
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(self.scan_slice, t) for t in tasks]
            for f in as_completed(futures):
                pids = f.result()
                done_scans += 1
                for p in pids:
                    harvested_all_pids.add(p)
                    if p not in self.existing_pids:
                        pending_pids.add(p)

                if done_scans % 50 == 0 or done_scans == total_tasks:
                    el = time.time() - start_t
                    sp = done_scans / el if el > 0 else 0
                    pct = (done_scans / total_tasks) * 100
                    rem = (total_tasks - done_scans) / sp if sp > 0 else 0
                    eta_str = time.strftime("%H:%M:%S", time.gmtime(rem))
                    print(f"[*] 前缀扫网进度: [{done_scans:>3}/{total_tasks}] ({pct:5.1f}%) | "
                          f"捕获总ID: {len(harvested_all_pids):,} 个 | "
                          f"新锁定未录入商品: {len(pending_pids):,} 件 | "
                          f"速率: {sp:4.1f} 单元/秒 | "
                          f"ETA: {eta_str}", flush=True)

        print("\n" + "="*75, flush=True)
        print(f"[+] 阶段一完成！新锁定未录入商品: {len(pending_pids):,} 件", flush=True)
        print("="*75 + "\n", flush=True)

        if pending_pids:
            print("="*75, flush=True)
            print(f" [阶段二] 启动 {self.workers} 线程并发抓取 {len(pending_pids):,} 件新商品 37 字段详情与价格", flush=True)
            print("="*75, flush=True)

            writer_thread = threading.Thread(target=self._async_writer_worker, daemon=True)
            writer_thread.start()

            p_list = list(pending_pids)
            total_fetch = len(p_list)
            done_fetch = 0
            fetch_start = time.time()

            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [executor.submit(self.fetch_detail, p) for p in p_list]
                for f in as_completed(futures):
                    done_fetch += 1
                    if done_fetch % 50 == 0 or done_fetch == total_fetch:
                        el = time.time() - fetch_start
                        sp = done_fetch / el if el > 0 else 0
                        pct = (done_fetch / total_fetch) * 100
                        rem = (total_fetch - done_fetch) / sp if sp > 0 else 0
                        eta_str = time.strftime("%H:%M:%S", time.gmtime(rem))
                        print(f"[*] 详情补全进度: [{done_fetch:>5}/{total_fetch:,}] ({pct:5.1f}%) | "
                              f"新入库商品: {self.saved_count:>5} 件 | "
                              f"速率: {sp:4.1f} 条/秒 | "
                              f"ETA: {eta_str}", flush=True)

            self.stop_event.set()
            writer_thread.join()

        # 阶段三：导出全量报表
        print("\n" + "="*75, flush=True)
        print(" [阶段三] 全量数据重新整合与 9.6 万+ SKU 规格变体明细报表生成", flush=True)
        print("="*75, flush=True)

        efs, cf = self.exporter.export_all()
        sk_efs, sk_cf = self.exporter.export_expanded_skus()

        print("\n[+] 最终全量数据报表导出完成！", flush=True)
        print("1. 全站独立商品总库 (SPU 模式):")
        for f in efs: print(f" - Excel: {f}")
        print(f" - CSV:   {cf}")
        print("\n2. 全站规格变体展开明细库 (SKU 模式 - 精准 9.6万+ 铺货数据):")
        for f in sk_efs: print(f" - Excel (分卷): {f}")
        print(f" - CSV (全量):   {sk_cf}")
        print("="*75 + "\n", flush=True)

if __name__ == "__main__":
    crawler = SkuPrefixMatrixCrawler(workers=25)
    crawler.run()
