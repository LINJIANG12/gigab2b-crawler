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

test_pids = [1352390, 1328868, 1125049, 927024]
print("="*65)
print(" 深入解剖 302 商品在各个 API 接口下的真实数据响应:")
print("="*65)

for pid in test_pids:
    # 1. 尝试 baseInfos (禁止自动重定向)
    u1 = f"https://www.gigab2b.com/index.php?route=product/info/info/baseInfos&product_id={pid}"
    r1 = s.get(u1, allow_redirects=False)
    loc = r1.headers.get("Location", "")
    print(f"\n[PID: {pid}]")
    print(f" - baseInfos (allow_redirects=False) -> Status: {r1.status_code}, Location: {loc}")

    # 2. 尝试价格接口
    u2 = f"https://www.gigab2b.com/index.php?route=product/info/price/list&product_id={pid}"
    r2 = s.get(u2, allow_redirects=False)
    print(f" - price/list -> Status: {r2.status_code}")

    # 3. 尝试搜索接口查询该 PID
    u3 = "https://www.gigab2b.com/index.php?route=product/list/search"
    r3 = s.post(u3, json={"page": 1, "limit": 10, "search_dimension": 1, "scene": 2, "keyword": str(pid)}).json()
    p_info_search = r3.get("data", {})
    print(f" - search by keyword -> Code: {r3.get('code')}, Found items: {p_info_search.get('pagination', {}).get('total')}")
