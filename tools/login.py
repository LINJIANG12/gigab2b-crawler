# -*- coding: utf-8 -*-
"""
GigaB2B 模拟真实登录脚本

逆向结论（已实测）：
- 登录接口: POST /index.php?route=account/login
- 请求头:   X-CSRF-TOKEN: <token>   （从任意页面 HTML 的
            window.oriCsrfToken.init('X-CSRF-TOKEN', '<token>') 中提取）
- 请求体:   JSON {"email": "<邮箱>", "password": "<密码>"}
- 无验证码、无图形滑块；连错 6 次也不触发风控（已实测）
- 缺字段:   "Error: The email/password field is required."
- 凭据错误: "Incorrect login information, please try again."

用法:
  py -3.14 login.py --email your@mail.com --password yourpass
  py -3.14 login.py --email your@mail.com            # 密码从环境变量 GIGA_PASSWORD 读
登录成功后自动:
  1) 保存登录态到 cookies.json / cookie.txt（后续 main.py / crawler 直接复用）
  2) 调用 check_login_status 验证
  3) 探测 3 个此前价格隐藏的商品，报告登录后价格是否可见
"""
import argparse
import sys
import os
import re
import json
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import COOKIE_FILE, COOKIE_TXT_FILE, BASE_URL
from cookie_manager import (
    get_authenticated_session, load_cookies, save_cookies,
    parse_raw_cookie_string, check_login_status
)

LOGIN_URL = f"{BASE_URL}/index.php?route=account/login"
PRICE_URL = f"{BASE_URL}/index.php?route=product/info/price/list"

# 此前实测为价格隐藏的样本（登录后应变为可见）
HIDDEN_TEST_PIDS = ['1124034', '1450139', '430318']


def get_csrf_token(session) -> str:
    """从首页 HTML 提取 X-CSRF-TOKEN"""
    r = session.get(f"{BASE_URL}/", timeout=20)
    m = re.search(r"oriCsrfToken\.init\('X-CSRF-TOKEN', '([^']+)'\)", r.text)
    if not m:
        raise RuntimeError("无法从页面提取 CSRF Token")
    return m.group(1)


def do_login(session, email: str, password: str) -> dict:
    csrf = get_csrf_token(session)
    print(f"[*] CSRF Token: {csrf[:16]}...")
    session.headers.update({
        "X-CSRF-TOKEN": csrf,
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    })
    r = session.post(LOGIN_URL, json={"email": email, "password": password}, timeout=20)
    try:
        j = r.json()
    except Exception:
        print(f"[!] 登录返回非 JSON (HTTP {r.status_code}, url={r.url[:100]})")
        return {}
    code = j.get("code")
    msg = j.get("msg") or j.get("error") or ""
    if code == 200:
        print(f"[+] 登录接口返回成功 (code=200)")
        return j
    print(f"[X] 登录失败: {msg}")
    d = j.get("data") or {}
    if d.get("attribute"):
        print(f"    缺失/错误字段: {d['attribute']}")
    return {}


def probe_hidden_prices(session):
    """登录后探测此前价格隐藏的商品"""
    print("\n[*] 探测登录后的价格可见性:")
    for pid in HIDDEN_TEST_PIDS:
        try:
            j = session.get(f"{PRICE_URL}&product_id={pid}", timeout=15).json()
            d = j.get("data") or {}
            bp = d.get("base_price_info") or {}
            pv = d.get("price_visible")
            price = bp.get("price") if bp else None
            print(f"    pid {pid}: price_visible={pv} price={price} is_cooperate={d.get('is_cooperate')}")
        except Exception as e:
            print(f"    pid {pid}: EXC {e}")


def main():
    ap = argparse.ArgumentParser(description="GigaB2B 模拟真实登录")
    ap.add_argument("--email", required=True, help="登录邮箱")
    ap.add_argument("--password", default=None, help="登录密码（缺省读环境变量 GIGA_PASSWORD）")
    args = ap.parse_args()

    password = args.password or os.environ.get("GIGA_PASSWORD")
    if not password:
        print("[!] 未提供密码：请用 --password 传入，或设置环境变量 GIGA_PASSWORD")
        sys.exit(1)

    session = get_authenticated_session(load_cookies())
    result = do_login(session, args.email, password)
    if not result:
        sys.exit(1)

    # 保存登录后的 Cookie
    cookie_dict = dict(session.cookies)
    save_cookies(cookie_dict)
    print(f"[+] 已保存登录态 Cookie 到 {COOKIE_FILE} / {COOKIE_TXT_FILE}")

    # 验证登录态
    ok, msg = check_login_status(session)
    print(f"[*] 登录态验证: {'[有效]' if ok else '[无效]'} {msg}")

    # 重新走一遍完整的登录会话（带新 CSRF），确认 cookie 已持久化可复用
    s2 = get_authenticated_session(load_cookies())
    ok2, msg2 = check_login_status(s2)
    print(f"[*] 重载 Cookie 后验证: {'[有效]' if ok2 else '[无效]'} {msg2}")

    if ok:
        probe_hidden_prices(session)
        print("\n[+] 完成！现在可以运行 py -3.14 main.py 全量采集（登录态价格）")
    else:
        print("\n[!] 登录态验证未通过，请检查账号或网络。")


if __name__ == "__main__":
    main()
