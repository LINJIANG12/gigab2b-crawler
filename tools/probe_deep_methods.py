import requests
import json
import time
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

# 测试分类 10015 (Beds, 5000 件商品)
# 我们测试不同的 scene 和 参数组合，看看怎样能真正翻到第 10, 20, 30, 40, 50 页！
cid = 10015

print("="*60)
print(" 方案 A: 测试不同的 scene 和 分页参数在分类 10015 下的真实深度翻页")
print("="*60)

# 测试 scene=2, scene=1, scene=6, scene=0
for scene_val in [2, 1, 6]:
    unique_pids = set()
    for p in range(1, 11):
        payload = {
            "page": p,
            "limit": 30,
            "search_dimension": 1,
            "scene": scene_val,
            "product_category_id": [cid]
        }
        r = s.post(url, json=payload).json()
        d = r.get('data', {})
        pl = d.get('product_list', [])
        for pid in pl:
            unique_pids.add(pid)
    print(f"Scene={scene_val} -> 10 页累计获取独立商品: {len(unique_pids)} 个")

print("\n" + "="*60)
print(" 方案 B: 探测其他可能的批量列表与分类 API")
print("="*60)

test_routes = [
    "product/category",
    "product/list/all",
    "product/list/category_products",
    "product/info/list",
    "catalog/product/list",
]
for route in test_routes:
    r = s.get(f"https://www.gigab2b.com/index.php?route={route}&category_id={cid}&page=1").json() if 'json' in str(s) else None
    try:
        res = s.get(f"https://www.gigab2b.com/index.php?route={route}&category_id={cid}").json()
        print(f"Route {route:<30} -> Code: {res.get('code')}, Keys: {list(res.get('data', {}).keys()) if isinstance(res.get('data'), dict) else type(res.get('data'))}")
    except Exception as e:
        print(f"Route {route:<30} -> Error or not JSON")
