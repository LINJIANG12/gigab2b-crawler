import argparse
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import COOKIE_FILE, COOKIE_TXT_FILE
from cookie_manager import (
    extract_cookies_from_edge,
    parse_raw_cookie_string,
    save_cookies,
    load_cookies,
    get_authenticated_session,
    check_login_status,
    get_clipboard_text
)
from database import Database
from crawler import GigaB2BCrawler
from exporter import DataExporter

def check_and_auto_import_clipboard():
    """检测剪贴板中是否包含 Cookie 并自动导入"""
    clip = get_clipboard_text()
    if clip and ('=' in clip) and ('PHPSESSID' in clip or '_yzc' in clip or 'token' in clip or 'giga' in clip.lower() or 'csrf' in clip.lower()):
        parsed = parse_raw_cookie_string(clip)
        if len(parsed) >= 2:
            save_cookies(parsed)
            print(f"[+] 检测到剪贴板中的登录凭据，已自动导入并保存 {len(parsed)} 个 Cookie！")
            return parsed
    return {}

def interactive_setup_cookie():
    """交互式引导配置 Cookie"""
    print("\n" + "="*55)
    print("       GigaB2B 全站数据采集系统 - 登录凭据配置")
    print("="*55)
    print("由于 GigaB2B 商品详情与批发价需要会员登录态，")
    print("请选择以下一种方式提供您已登录的 Edge 凭据：")
    print(" [1] 手动粘贴 Cookie 字符串 (最推荐，无需关闭 Edge)")
    print("     -> 在 Edge 按 F12 -> 打开控制台 Console -> 输入: copy(document.cookie)")
    print(" [2] 自动从本地 Edge 提取 (需要您先临时关闭 Edge 浏览器 3 秒钟)")
    print(" [3] 稍后在 cookie.txt 中手动编辑")
    print("="*55)

    choice = input("请输入选项编号 (1/2/3): ").strip()

    if choice == "1":
        print("\n请在 Edge 中按 F12 -> 切换到 Console -> 运行 copy(document.cookie)")
        raw_cookie = input("然后在此处粘贴 Cookie 字符串并按回车: ").strip()
        if raw_cookie:
            cookies = parse_raw_cookie_string(raw_cookie)
            save_cookies(cookies)
            print(f"[+] 成功保存 {len(cookies)} 项 Cookie！")
            return cookies

    elif choice == "2":
        print("[*] 正在尝试从 Edge 数据库提取 Cookie...")
        try:
            cookies = extract_cookies_from_edge()
            if cookies:
                save_cookies(cookies)
                print(f"[+] 成功提取到 {len(cookies)} 个 Cookie 并保存！")
                return cookies
            else:
                print("[!] 未在 Edge 中找到 gigab2b.com 的 Cookie，请确认已在 Edge 登录该网站。")
        except PermissionError as e:
            print(f"[!] 提取失败: {e}")
        except Exception as e:
            print(f"[!] 提取异常: {e}")

    return load_cookies()

def main():
    parser = argparse.ArgumentParser(description="GigaB2B 全站商品全字段大规模数据采集系统")
    parser.add_argument("--extract-cookie", action="store_true", help="从本地 Edge 浏览器自动提取解密 Cookie")
    parser.add_argument("--set-cookie", type=str, help="手动指定 Cookie 字符串并保存")
    parser.add_argument("--check-cookie", action="store_true", help="测试当前保存的 Cookie 登录态有效性")
    parser.add_argument("--export-only", action="store_true", help="仅从 SQLite 数据库重新生成 Excel 和 CSV 报表")
    parser.add_argument("--download-images", action="store_true", help="下载全站商品高清主图和副图到本地 images/ 目录")
    parser.add_argument("--skip-scan", action="store_true", help="跳过全站分类索引阶段，直接执行待抓取队列")
    parser.add_argument("--limit", type=int, default=None, help="限制采集数量（例如 100 条示例）")
    parser.add_argument("--workers", type=int, default=10, help="并发线程数 (默认 10)")
    parser.add_argument("--status", action="store_true", help="查看当前数据库中的任务与商品统计")

    args = parser.parse_args()
    db = Database.get_instance()

    # 1. 查看数据库状态
    if args.status:
        stats = db.get_stats()
        print("\n" + "="*40)
        print("        GigaB2B 数据库当前状态")
        print("="*40)
        print(f" - 任务总数:     {stats['total_tasks']}")
        print(f" - 已完成详情:   {stats['done_tasks']}")
        print(f" - 待抓取队列:   {stats['pending_tasks']}")
        print(f" - 失败需重试:   {stats['failed_tasks']}")
        print(f" - 已入库商品数: {stats['total_products']}")
        print("="*40)
        return

    # 2. 自动提取 Cookie
    if args.extract_cookie:
        print("[*] 正在从 Edge 提取 Cookie...")
        try:
            cookies = extract_cookies_from_edge()
            if cookies:
                save_cookies(cookies)
                print(f"[+] 成功提取并保存 {len(cookies)} 个 Cookie 到 {COOKIE_FILE} 和 {COOKIE_TXT_FILE}")
            else:
                print("[!] 未找到 gigab2b.com 相关的 Cookie。")
        except Exception as e:
            print(f"[!] 提取失败: {e}")
        return

    # 3. 手动设置 Cookie
    if args.set_cookie:
        cookies = parse_raw_cookie_string(args.set_cookie)
        save_cookies(cookies)
        print(f"[+] 已成功保存 {len(cookies)} 项 Cookie！")
        return

    # 4. 仅导出报表
    if args.export_only:
        exporter = DataExporter()
        excel_files, csv_file = exporter.export_all()
        if not excel_files and not csv_file:
            print("[!] 数据库中暂无已采集的商品数据。")
            return
        print(f"[+] 成功从数据库导出全量数据：")
        for ef in excel_files:
            print(f" - Excel: {ef}")
        if csv_file:
            print(f" - CSV:   {csv_file}")
        return

    # 5. 自动检查剪贴板
    check_and_auto_import_clipboard()

    # 6. 检查登录态
    cookies = load_cookies()
    session = get_authenticated_session(cookies)

    if args.check_cookie:
        is_ok, msg = check_login_status(session)
        print(f"[*] 登录态检查结果: {'[有效]' if is_ok else '[失效]'} {msg}")
        return

    is_ok, msg = check_login_status(session)
    if not is_ok:
        print(f"\n[!] 提示: 当前尚未配置有效登录凭据 ({msg})")
        cookies = interactive_setup_cookie()
        session = get_authenticated_session(cookies)

    # 7. 启动爬虫
    target_desc = f"{args.limit} 个示例商品" if args.limit else "全站所有商品"
    print("\n" + "="*50)
    print(f"      启动 GigaB2B 数据采集引擎 (目标: {target_desc})")
    print("="*50)
    crawler = GigaB2BCrawler(session=session, max_workers=args.workers)
    crawler.run_full_crawl(download_images=args.download_images, scan_index=not args.skip_scan, limit=args.limit)

if __name__ == "__main__":
    main()
