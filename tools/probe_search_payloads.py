import requests
import json
from cookie_manager import get_authenticated_session

session = get_authenticated_session()
session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"

# 先获取分类树
res = session.post(url, json={"page": 1, "limit": 10, "search_dimension": 1, "scene": 1}).json()
cat_tree = res.get('data', {}).get('category', [])

print("Top level category structure:")
for root in cat_tree[:2]:
    print(f"Root: {root.get('name')} (ID: {root.get('category_id')})")
    for sub in root.get('children', [])[:2]:
        print(f"  Sub: {sub.get('name')} (ID: {sub.get('category_id')})")
        for leaf in sub.get('children', [])[:2]:
            print(f"    Leaf: {leaf.get('name')} (ID: {leaf.get('category_id')})")
            
            # 测试不同的传参格式
            for scene in [1, 2]:
                for payload in [
                    {"page": 1, "limit": 10, "search_dimension": 1, "scene": scene, "product_category_id": [leaf.get('category_id')]},
                    {"page": 1, "limit": 10, "search_dimension": 1, "scene": scene, "category_id": leaf.get('category_id')},
                    {"page": 1, "limit": 10, "search_dimension": 1, "scene": scene, "filter_category_id": [leaf.get('category_id')]},
                    {"page": 1, "limit": 10, "search_dimension": 1, "scene": scene, "categories": [leaf.get('category_id')]},
                ]:
                    r = session.post(url, json=payload).json()
                    p_list = r.get('data', {}).get('product_list', [])
                    total = r.get('data', {}).get('pagination', {}).get('total', 0)
                    if p_list or total:
                        print(f"      [Match] scene={scene} payload={list(payload.keys())} -> total={total}, pids={len(p_list)}")
