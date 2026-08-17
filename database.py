import os
import sqlite3
import json
import threading
from config import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, "gigab2b.db")

class Database:
    """
    SQLite 高性能持久化数据库：支持 37 个全量字段存储、去重与断点续爬
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self.init_db()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA synchronous=NORMAL;")
        return self._local.conn

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_tasks (
            product_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            category TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            retries INTEGER DEFAULT 0,
            last_error TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON crawl_tasks(status);")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            sku TEXT,
            title TEXT,
            category_path TEXT,
            store_name TEXT,
            store_code TEXT,
            product_status TEXT,
            status_reason TEXT,
            price TEXT,
            discount_price TEXT,
            original_price TEXT,
            moq TEXT,
            currency TEXT,
            total_stock INTEGER DEFAULT 0,
            inventory_warehouses TEXT,
            drop_ship_fee TEXT,
            cloud_freight_range TEXT,
            handling_time TEXT,
            delivery_time TEXT,
            is_ltl TEXT,
            total_weight TEXT,
            total_volume TEXT,
            main_color TEXT,
            main_material TEXT,
            origin_place TEXT,
            upc TEXT,
            product_dimensions TEXT,
            package_size TEXT,
            rating TEXT,
            sales_count TEXT,
            reviews_count TEXT,
            shipping_and_services TEXT,
            documents TEXT,
            bullet_points TEXT,
            description_text TEXT,
            description_html TEXT,
            main_image TEXT,
            gallery_images TEXT,
            variants TEXT,
            url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 动态补齐缺失的列
        existing_cols = [r[1] for r in cursor.execute("PRAGMA table_info(products)").fetchall()]
        new_cols = [
            ("store_name", "TEXT"),
            ("store_code", "TEXT"),
            ("product_status", "TEXT"),
            ("status_reason", "TEXT"),
            ("discount_price", "TEXT"),
            ("drop_ship_fee", "TEXT"),
            ("cloud_freight_range", "TEXT"),
            ("handling_time", "TEXT"),
            ("delivery_time", "TEXT"),
            ("is_ltl", "TEXT"),
            ("total_weight", "TEXT"),
            ("total_volume", "TEXT"),
            ("documents", "TEXT"),
            ("main_color", "TEXT"),
            ("main_material", "TEXT"),
            ("origin_place", "TEXT"),
            ("upc", "TEXT"),
            ("product_dimensions", "TEXT"),
            ("package_size", "TEXT"),
            ("total_stock", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type};")
                except Exception:
                    pass

        conn.commit()
        conn.close()

    def add_tasks_batch(self, task_list: list[dict]) -> int:
        if not task_list:
            return 0
        conn = self._get_conn()
        data_tuples = [(str(t['product_id']), t['url'], t.get('category', '')) for t in task_list if t.get('product_id') and t.get('url')]
        try:
            cursor = conn.executemany(
                "INSERT OR IGNORE INTO crawl_tasks (product_id, url, category, status) VALUES (?, ?, ?, 'pending')",
                data_tuples
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            return 0

    def get_pending_tasks(self, limit: int = 1000) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT product_id, url, category, retries FROM crawl_tasks WHERE status IN ('pending', 'failed') AND retries < 5 LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_task_status(self, product_id: str, status: str, error_msg: str = ""):
        conn = self._get_conn()
        conn.execute(
            "UPDATE crawl_tasks SET status = ?, last_error = ?, retries = retries + 1, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
            (status, error_msg, str(product_id))
        )
        conn.commit()

    def save_product(self, data: dict):
        pid = str(data.get("product_id") or data.get("sku") or "")
        if not pid:
            return
        conn = self._get_conn()

        conn.execute("""
        INSERT OR REPLACE INTO products (
            product_id, sku, title, category_path, store_name, store_code,
            product_status, status_reason,
            price, discount_price, original_price, moq, currency,
            total_stock, inventory_warehouses,
            drop_ship_fee, cloud_freight_range, handling_time, delivery_time,
            is_ltl, total_weight, total_volume,
            main_color, main_material, origin_place, upc,
            product_dimensions, package_size,
            rating, sales_count, reviews_count,
            shipping_and_services, documents,
            bullet_points, description_text, description_html,
            main_image, gallery_images, variants,
            url, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            pid,
            data.get("sku", ""),
            data.get("title", ""),
            data.get("category_path", ""),
            data.get("store_name", ""),
            data.get("store_code", ""),
            data.get("product_status", ""),
            data.get("status_reason", ""),
            data.get("price", ""),
            data.get("discount_price", ""),
            data.get("original_price", ""),
            data.get("moq", ""),
            data.get("currency", "$"),
            data.get("total_stock", 0),
            json.dumps(data.get("inventory_warehouses", {}), ensure_ascii=False),
            data.get("drop_ship_fee", ""),
            data.get("cloud_freight_range", ""),
            data.get("handling_time", ""),
            data.get("delivery_time", ""),
            data.get("is_ltl", "否"),
            data.get("total_weight", ""),
            data.get("total_volume", ""),
            data.get("main_color", ""),
            data.get("main_material", ""),
            data.get("origin_place", ""),
            data.get("upc", ""),
            data.get("product_dimensions", ""),
            data.get("package_size", ""),
            data.get("rating", ""),
            data.get("sales_count", ""),
            data.get("reviews_count", ""),
            json.dumps(data.get("shipping_and_services", {}), ensure_ascii=False),
            data.get("documents", ""),
            json.dumps(data.get("bullet_points", []), ensure_ascii=False),
            data.get("description_text", ""),
            data.get("description_html", ""),
            data.get("main_image", ""),
            json.dumps(data.get("gallery_images", []), ensure_ascii=False),
            json.dumps(data.get("variants", []), ensure_ascii=False),
            data.get("url", "")
        ))

        conn.execute("UPDATE crawl_tasks SET status = 'done', updated_at = CURRENT_TIMESTAMP WHERE product_id = ?", (pid,))
        conn.commit()

    def get_all_products(self) -> list[dict]:
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM products ORDER BY scraped_at DESC")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            for field in ['gallery_images', 'bullet_points', 'variants']:
                try:
                    d[field] = json.loads(d.get(field) or '[]')
                except Exception:
                    d[field] = []
            for field in ['specifications', 'inventory_warehouses', 'shipping_and_services']:
                try:
                    d[field] = json.loads(d.get(field) or '{}')
                except Exception:
                    d[field] = {}
            results.append(d)
        return results

    def get_stats(self) -> dict:
        conn = self._get_conn()
        total_tasks = conn.execute("SELECT COUNT(*) FROM crawl_tasks").fetchone()[0]
        done_tasks = conn.execute("SELECT COUNT(*) FROM crawl_tasks WHERE status = 'done'").fetchone()[0]
        pending_tasks = conn.execute("SELECT COUNT(*) FROM crawl_tasks WHERE status = 'pending'").fetchone()[0]
        failed_tasks = conn.execute("SELECT COUNT(*) FROM crawl_tasks WHERE status = 'failed'").fetchone()[0]
        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        return {
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "pending_tasks": pending_tasks,
            "failed_tasks": failed_tasks,
            "total_products": total_products
        }
