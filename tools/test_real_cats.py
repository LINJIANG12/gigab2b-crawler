import requests
from cookie_manager import load_cookies
from parser import ProductParser

s = requests.Session()
s.cookies.update(load_cookies())
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.gigab2b.com/index.php?route=product/list/list"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 获取分类树
r = s.post(url, json={"page": 1, "limit": 1, "search_dimension": 1, "scene": 1}).json()
cat_tree = r.get('data', {}).get('category', [])

parser = ProductParser()
leaf_cats = parser.parse_category_tree(cat_tree)
print(f"Total leaf categories: {len(leaf_cats)}")

# 测试前 10 个分类在 scene: 2 下的真实商品列表
for cat in leaf_cats[:10]:
    cid = cat['category_id']
    name = cat['name']
    res = s.post(url, json={"page": 1, "limit": 30, "search_dimension": 1, "scene": 2, "product_category_id": [cid]}).json()
    d = res.get('data', {})
    pl = d.get('product_list', [])
    tot = d.get('pagination', {}).get('total', 0)
    print(f"Cat [{cid:>6}] {name:<35} -> Total: {tot:>4}, PIDs returned: {len(pl)}")
    if pl:
        print(f"   PIDs: {pl[:4]}")
