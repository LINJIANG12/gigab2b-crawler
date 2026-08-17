import requests
import json
from cookie_manager import get_authenticated_session

session = get_authenticated_session()
session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*"
})

url = "https://www.gigab2b.com/index.php?route=product/list/search"
res = session.post(url, json={"page": 1, "limit": 10, "search_dimension": 1, "scene": 1}).json()
print("Response code:", res.get('code'))
print("Response msg:", res.get('msg'))
print("Data keys:", list(res.get('data', {}).keys()))
print("product_list len:", len(res.get('data', {}).get('product_list', [])))
