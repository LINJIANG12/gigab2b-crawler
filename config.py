import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据存储目录
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGE_DIR = os.path.join(BASE_DIR, "images")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
TMP_DIR = os.path.join(BASE_DIR, "_tmp")

# 确保目录存在
for directory in [DATA_DIR, IMAGE_DIR, CACHE_DIR, TMP_DIR]:
    os.makedirs(directory, exist_ok=True)

# 目标网站基础配置
BASE_URL = "https://www.gigab2b.com"
SEARCH_URL = f"{BASE_URL}/index.php?route=product/list/search"
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.json")
COOKIE_TXT_FILE = os.path.join(BASE_DIR, "cookie.txt")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest"
}

# 网络请求与连接池高并发极速调优 (针对 9 万+ 工业级全量采集)
DEFAULT_WORKERS = 40          # 默认并发线程数（调优为 40 线程高吞吐）
POOL_CONNECTIONS = 100        # HTTP 连接池连接数
POOL_MAXSIZE = 100            # HTTP 连接池最大复用数
REQUEST_TIMEOUT = 12          # 请求超时时间（秒）
MAX_RETRIES = 3               # 失败最大重试次数
RETRY_DELAY = 0.5             # 失败重试基础间隔（秒）
REQUEST_DELAY_MIN = 0.0       # 极速零等待
REQUEST_DELAY_MAX = 0.02      # 极小抖动

# 数据库与批量异步写入性能调优
DB_BATCH_SIZE = 100           # 内存缓冲批量写入阈值（每 100 条写入一次数据库）
DB_FLUSH_INTERVAL = 1.5       # 缓冲刷新时间间隔（秒）
DB_CACHE_SIZE_MB = 128        # SQLite WAL 内存缓存大小 (128MB)

# Excel 分卷阈值
EXCEL_CHUNK_SIZE = 50000      # 每个 Excel 分卷最大商品数
AUTO_SNAPSHOT_INTERVAL = 5000 # 每采集 5000 条自动记录检查点
