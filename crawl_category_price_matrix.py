import os
import sys
import time
import json
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

class CategoryPriceMatrixCrawler:
    """
    GigaB2B 217分类 × 25价格切片复合超空间扫网引擎：
    - 5,425 个细分空间单元全并发穿透平台的 3 页翻页截断限制
    - 挖掘全站所有分类深处隐藏的 9.6 万+ 全量商品与变体
    - 自动断点续爬 + 异步零阻塞 WAL 写入
    - 自动导出 9.6 万+ SKU 规格变体明细与 SPU 汇总报表
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

        # 25 个精细价格切片梯度 (覆盖 $0 ~ $10,000)
        self.price_slices = [
            (0, 20), (20, 40), (40, 60), (60, 80), (80, 100),
            (100, 120), (120, 150), (150, 180), (180, 220), (220, 260),
            (260, 300), (300, 350), (350, 400), (400, 460), (460, 530),
            (530, 600), (600, 700), (700, 850), (850, 1000), (1000, 1300),
            (1300, 1700), (1700, 2300), (2300, 3200), (3200, 5000), (5000, 20000)
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
        print(f"[+] 数据库已有商品基线: {len(self.existing_pids):,} 件 (自动跳过已采集数据)", flush=True)

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
            if len(buffer) >= 60 or (now - last_flush >= 1.5 and buffer):
                for p in buffer:
                    self.db.save_product_buffered(p)
                self.db.flush()
                buffer.clear()
                last_flush = now

        if buffer:
            for p in buffer:
                self.db.save_product_buffered(p)
            self.db.flush()

    def build_matrix_tasks(self) -> list[dict]:
        """构建 217 分类 × 25 价格切片 = 5,425 个超空间单元网格"""
        print("[*] 正在加载全站分类树并构建超空间矩阵网格...", flush=True)
        res = self.session.post(self.search_url, json={"page": 1, "limit": 1, "search_dimension": 1, "scene": 1}).json()
        cat_tree = res.get("data", {}).get("category", [])
        leaf_cats = self.parser.parse_category_tree(cat_tree)
        print(f"[+] 解析到末级分类数: {len(leaf_cats)} 个", flush=True)

        grid_tasks = []
        for cat in leaf_cats:
            cid = cat["category_id"]
            cname = cat["name"]
            for p_min, p_max in self.price_slices:
                grid_tasks.append({
                    "category_id": cid,
                    "category_name": cname,
                    "price_min": p_min,
                    "price_max": p_max
                })
        print(f"[+] 成功构建复合空间切片网格: 共 {len(grid_tasks):,} 个细分空间探测单元！", flush=True)
        return grid_tasks

    def scan_single_grid_slice(self, task: dict) -> list[str]:
        """探测单个分类价格切片单元 (翻 1~3 页)"""
        cid = task["category_id"]
        p_min = str(task["price_min"])
        p_max = str(task["price_max"])
        
        found_pids = []
        for page in range(1, 4):
            payload = {
                "page": page,
                "limit": 30,
                "search_dimension": 1,
                "scene": 2,
                "product_category_id": [cid],
                "price_min": p_min,
                "price_max": p_max
            }
            try:
                r = self.session.post(self.search_url, json=payload, timeout=6).json()
                pl = r.get("data", {}).get("product_list", [])
                if not pl:
                    break
                for item in pl:
                    found_pids.append(str(item))
                if len(pl) < 30:
                    break
            except Exception:
                break
        return found_pids

    def fetch_product_detail(self, spid: str, max_retries: int = 3) -> bool:
        """强健商品详情与价格采集 (3 次失败重试)"""
        base_url = f"{BASE_URL}/index.php?route=product/info/info/baseInfos&product_id={spid}"
        price_url = f"{BASE_URL}/index.php?route=product/info/price/list&product_id={spid}"

        for attempt in range(max_retries):
            try:
                r1 = self.session.get(base_url, timeout=10)
                if r1.status_code == 200:
                    j1 = r1.json()
                    if j1.get("code") == 200 and j1.get("data") and j1.get("data").get("product_info"):
                        try:
                            r2 = self.session.get(price_url, timeout=8)
                            j2 = r2.json() if r2.status_code == 200 else {}
                        except:
                            j2 = {}

                        product_url = f"{BASE_URL}/index.php?route=product/product&product_id={spid}"
                        data = self.parser.parse_api_data(j1, j2, product_url=product_url)
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
        print(" GigaB2B 217分类 × 25价格切片复合超空间扫网引擎 (突破 9.6 万全量数据)", flush=True)
        print("="*75, flush=True)

        self._load_existing_pids()
        grid_tasks = self.build_matrix_tasks()
        total_grids = len(grid_tasks)

        # -------------------------------------------------------------
        # 阶段一：5,425 超空间网格并发探测
        # -------------------------------------------------------------
        print("\n" + "="*75, flush=True)
        print(f" [阶段一] 启动 25 线程并发扫描 {total_grids:,} 个分类价格微切片空间单元", flush=True)
        print("="*75, flush=True)

        harvested_all_pids = set()
        pending_pids = set()
        scanned_grids = 0
        start_t = time.time()

        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(self.scan_single_grid_slice, task) for task in grid_tasks]
            for f in as_completed(futures):
                pids = f.result()
                scanned_grids += 1
                for p in pids:
                    harvested_all_pids.add(p)
                    if p not in self.existing_pids:
                        pending_pids.add(p)

                if scanned_grids % 100 == 0 or scanned_grids == total_grids:
                    elapsed = time.time() - start_t
                    speed = scanned_grids / elapsed if elapsed > 0 else 0
                    pct = (scanned_grids / total_grids) * 100
                    rem = (total_grids - scanned_grids) / speed if speed > 0 else 0
                    eta_str = time.strftime("%H:%M:%S", time.gmtime(rem))
                    print(f"[*] 矩阵扫网进度: [{scanned_grids:>4}/{total_grids:,}] ({pct:5.1f}%) | "
                          f"累计捕获唯一商品: {len(harvested_all_pids):,} 个 | "
                          f"新锁定待补商品: {len(pending_pids):,} 件 | "
                          f"速率: {speed:4.1f} 单元/秒 | "
                          f"ETA: {eta_str}", flush=True)

        print("\n" + "="*75, flush=True)
        print(f"[+] 阶段一矩阵扫网圆满完成！", flush=True)
        print(f" - 全站 5,425 切片捕获唯一独立商品: {len(harvested_all_pids):,} 件", flush=True)
        print(f" - 数据库已有基线:                  {len(self.existing_pids):,} 件", flush=True)
        print(f" - 本次锁定新增待抓取商品:          {len(pending_pids):,} 件", flush=True)
        print("="*75 + "\n", flush=True)

        # -------------------------------------------------------------
        # 阶段二：新商品全量详情与价格并发抓取入库
        # -------------------------------------------------------------
        if pending_pids:
            print("="*75, flush=True)
            print(f" [阶段二] 启动 {self.workers} 线程并发采集 {len(pending_pids):,} 件新商品 37 字段详情与价格", flush=True)
            print("="*75, flush=True)

            writer_thread = threading.Thread(target=self._async_writer_worker, daemon=True)
            writer_thread.start()

            tasks_list = list(pending_pids)
            total_fetch = len(tasks_list)
            done_fetch = 0
            fetch_start = time.time()

            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [executor.submit(self.fetch_product_detail, p) for p in tasks_list]
                for f in as_completed(futures):
                    done_fetch += 1
                    if done_fetch % 50 == 0 or done_fetch == total_fetch:
                        el = time.time() - fetch_start
                        sp = done_fetch / el if el > 0 else 0
                        pct = (done_fetch / total_fetch) * 100
                        rm = (total_fetch - done_fetch) / sp if sp > 0 else 0
                        eta_str = time.strftime("%H:%M:%S", time.gmtime(rm))
                        print(f"[*] 详情采集进度: [{done_fetch:>5}/{total_fetch:,}] ({pct:5.1f}%) | "
                              f"本次新入库: {self.saved_count:>5} 件 | "
                              f"速率: {sp:4.1f} 条/秒 | "
                              f"ETA: {eta_str}", flush=True)

            self.stop_event.set()
            writer_thread.join()

        # -------------------------------------------------------------
        # 阶段三：导出全量数据报表
        # -------------------------------------------------------------
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
    crawler = CategoryPriceMatrixCrawler(workers=25)
    crawler.run()
