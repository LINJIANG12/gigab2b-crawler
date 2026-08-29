import requests
import json
from cookie_manager import load_cookies

s = requests.Session()
s.cookies.update(load_cookies())
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 尝试不同的参数组合
payloads = [
    {"name": "scene 1 product_category_id", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "product_category_id": [10015]}},
    {"name": "scene 2 product_category_id", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [10015]}},
    {"name": "scene 1 filter_category_id", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "filter_category_id": [10015]}},
    {"name": "scene 1 category_id int", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "category_id": 10015}},
    {"name": "scene 1 category_id str", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "category_id": "10015"}},
    {"name": "scene 1 setting category", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "setting": {"category": [10015]}}},
    {"name": "scene 1 categories list", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1, "categories": [10015]}},
    {"name": "global search no category", "body": {"page": 1, "limit": 30, "search_dimension": 1, "scene": 1}},
    {"name": "global search page 2", "body": {"page": 2, "limit": 30, "search_dimension": 1, "scene": 1}},
    {"name": "global search page 3", "body": {"page": 3, "limit": 30, "search_dimension": 1, "scene": 1}},
]

for item in payloads:
    r = s.post(url, json=item['body']).json()
    d = r.get('data', {})
    p_list = d.get('product_list', [])
    total = d.get('pagination', {}).get('total', 0)
    print(f"Test [{item['name']}] -> total: {total}, pids: {len(p_list)}")
