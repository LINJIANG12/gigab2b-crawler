import os
import sys
import time
import queue
import threading
import argparse
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8')

from config import (
    BASE_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY,
    DEFAULT_WORKERS, POOL_CONNECTIONS, POOL_MAXSIZE, DB_BATCH_SIZE
)
from cookie_manager import get_authenticated_session, load_cookies
from parser import ProductParser
from database import Database
from exporter import DataExporter

class FastRangeCrawler:
    """
    GigaB2B 商品 ID 连续空间极速全量采集引擎：
    - 40 线程高吞吐连接池深度复用
    - 专用后台异步写入守护线程 (Zero-Lock Async Writer)
    - 自动跳过数据库已存在的商品 (精确去重)
    - 毫秒级流式控制台仪表盘与 ETA 预估
    """
    def __init__(self, start_id: int = 400000, end_id: int = 1600000, workers: int = 40, download_images: bool = False):
        self.start_id = start_id
        self.end_id = end_id
        self.workers = workers
        self.download_images = download_images
        self.session = get_authenticated_session(load_cookies())
        self._configure_pool()
        self.parser = ProductParser(base_url=BASE_URL)
        self.db = Database.get_instance()
        self.exporter = DataExporter()

        self.write_queue = queue.Queue(maxsize=2000)
        self.stop_event = threading.Event()
        self.existing_pids = set()
        self.scanned_count = 0
        self.saved_count = 0
        self._lock = threading.Lock()

    def _configure_pool(self):
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
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive"
        })

    def _load_existing_pids(self):
        """预先载入数据库中已存在的全部商品 ID（避免重复请求）"""
        print("[*] 正在加载数据库已有商品索引...", flush=True)
        conn = self.db._get_conn()
        rows = conn.execute("SELECT product_id FROM products").fetchall()
        self.existing_pids = {str(r[0]) for r in rows}
        print(f"[+] 数据库已有商品: {len(self.existing_pids):,} 件 (自动跳过，实现断点续爬)", flush=True)

    def _async_writer_worker(self):
        """专用后台异步落盘线程：批量写 SQLite，零阻塞工作线程"""
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
            if len(buffer) >= DB_BATCH_SIZE or (now - last_flush >= 1.5 and buffer):
                for p in buffer:
                    self.db.save_product_buffered(p)
                self.db.flush()
                buffer.clear()
                last_flush = now

        if buffer:
            for p in buffer:
                self.db.save_product_buffered(p)
            self.db.flush()

    def _fetch_single_pid(self, pid: int):
        """极速单个商品详情与价格采集"""
        spid = str(pid)
        if spid in self.existing_pids:
            with self._lock:
                self.scanned_count += 1
            return

        base_url = f"{BASE_URL}/index.php?route=product/info/info/baseInfos&product_id={spid}"
        price_url = f"{BASE_URL}/index.php?route=product/info/price/list&product_id={spid}"

        try:
            r1 = self.session.get(base_url, timeout=REQUEST_TIMEOUT)
            if r1.status_code == 200:
                j1 = r1.json()
                if j1.get("code") == 200 and j1.get("data") and j1.get("data").get("product_info"):
                    # 获取价格
                    try:
                        r2 = self.session.get(price_url, timeout=REQUEST_TIMEOUT)
                        j2 = r2.json() if r2.status_code == 200 else {}
                    except Exception:
                        j2 = {}

                    product_url = f"{BASE_URL}/index.php?route=product/product&product_id={spid}"
                    data = self.parser.parse_api_data(j1, j2, product_url=product_url)
                    data["product_id"] = spid

                    if self.download_images:
                        self.exporter.download_product_images(data, self.session)

                    self.write_queue.put(data)
                    with self._lock:
                        self.saved_count += 1
                        self.existing_pids.add(spid)
        except Exception:
            pass
        finally:
            with self._lock:
                self.scanned_count += 1

    def run(self):
        print("\n" + "="*65, flush=True)
        print("     GigaB2B 商品 ID 空间极速全量采集引擎 (40 线程极速版)", flush=True)
        print("="*65, flush=True)
        print(f" - 扫描区间:   ID [{self.start_id:,} ~ {self.end_id:,}] (共 {self.end_id - self.start_id:,} 个号段)", flush=True)
        print(f" - 并发线程:   {self.workers} 线程 (连接池深度复用)", flush=True)
        print(f" - 写入模式:   后台专用异步守护线程 (Zero-Wait WAL Batch)", flush=True)
        print("="*65 + "\n", flush=True)

        self._load_existing_pids()

        # 启动异步写入线程
        writer_thread = threading.Thread(target=self._async_writer_worker, daemon=True)
        writer_thread.start()

        all_pids = list(range(self.start_id, self.end_id + 1))
        total_pids = len(all_pids)
        start_time = time.time()

        print(f"[*] 正在高速并发扫描商品 ID 空间...", flush=True)

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # 批次分派
            chunk_size = 500
            for i in range(0, total_pids, chunk_size):
                chunk = all_pids[i:i+chunk_size]
                list(executor.map(self._fetch_single_pid, chunk))

                elapsed = time.time() - start_time
                scan_speed = self.scanned_count / elapsed if elapsed > 0 else 0
                pct = (self.scanned_count / total_pids) * 100
                rem_time = (total_pids - self.scanned_count) / scan_speed if scan_speed > 0 else 0
                eta_str = time.strftime("%H:%M:%S", time.gmtime(rem_time))

                bar_len = 20
                filled = int(bar_len * self.scanned_count / total_pids)
                bar = '█' * filled + '░' * (bar_len - filled)

                print(f"[*] 进度: [{bar}] {pct:5.1f}% | "
                      f"已扫: {self.scanned_count:,}/{total_pids:,} | "
                      f"有效入库: {self.saved_count:,} 件 | "
                      f"速率: {scan_speed:5.1f} ID/秒 | "
                      f"ETA: {eta_str}", flush=True)

        self.stop_event.set()
        writer_thread.join()

        total_time = time.time() - start_time
        print("\n" + "="*65, flush=True)
        print(f"[+] 商品 ID 空间扫描与采集圆满完成！", flush=True)
        print(f" - 总耗时:       {time.strftime('%H:%M:%S', time.gmtime(total_time))}", flush=True)
        print(f" - 本次新入库:   {self.saved_count:,} 件商品", flush=True)
        print(f" - 数据库累计:   {len(self.existing_pids):,} 件商品", flush=True)
        print("="*65, flush=True)

        # 导出数据
        print("[*] 正在导出最新全量 Excel 与 CSV 报表...", flush=True)
        efs, csv_f = self.exporter.export_all()
        for ef in efs:
            print(f" - Excel: {ef}", flush=True)
        if csv_f:
            print(f" - CSV:   {csv_f}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="GigaB2B 商品 ID 空间极速采集器")
    parser.add_argument("--start", type=int, default=400000, help="起始商品 ID (默认: 400000)")
    parser.add_argument("--end", type=int, default=1600000, help="结束商品 ID (默认: 1600000)")
    parser.add_argument("--workers", type=int, default=40, help="并发线程数 (默认: 40)")
    parser.add_argument("--images", action="store_true", help="是否下载高清主副图到本地")

    args = parser.parse_args()
    crawler = FastRangeCrawler(
        start_id=args.start,
        end_id=args.end,
        workers=args.workers,
        download_images=args.images
    )
    crawler.run()

if __name__ == "__main__":
    main()
