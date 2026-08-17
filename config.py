import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGE_DIR = os.path.join(BASE_DIR, "images")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# 网站配置
BASE_URL = "https://www.gigab2b.com"
CATEGORY_URL = f"{BASE_URL}/index.php?route=product/category"
SEARCH_URL = f"{BASE_URL}/index.php?route=product/search"

# 请求头配置
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="124", "Microsoft Edge";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

# 爬虫参数
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
RETRY_DELAY = 2  # 重试间隔(秒)
REQUEST_DELAY = 0.5  # 每次请求间隔(秒)
MAX_WORKERS = 5  # 详情页爬取并发线程数

# Cookie 存储路径
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.json")
COOKIE_TXT_FILE = os.path.join(BASE_DIR, "cookie.txt")
CRAWLED_ID_FILE = os.path.join(CACHE_DIR, "crawled_ids.txt")
DATA_CACHE_FILE = os.path.join(CACHE_DIR, "scraped_products.jsonl")
