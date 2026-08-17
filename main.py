import argparse
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True, encoding='utf-8')

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
            print(f"[+] 检测到剪贴板中的登录凭据，已自动导入并保存 {len(parsed)} 个 Cookie！", flush=True)
            return parsed
    return {}

def interactive_setup_cookie():
    """交互式引导配置 Cookie"""
    print("\n" + "="*55, flush=True)
    print("       GigaB2B 全站数据采集系统 - 登录凭据配置", flush=True)
    print("="*55, flush=True)
    print("由于 GigaB2B 商品详情与批发价需要会员登录态，", flush=True)
    print("请选择以下一种方式提供您已登录的 Edge 凭据：", flush=True)
    print(" [1] 手动粘贴 Cookie 字符串 (最推荐，无需关闭 Edge)", flush=True)
    print("     -> 在 Edge 按 F12 -> 打开控制台 Console -> 输入: copy(document.cookie)", flush=True)
    print(" [2] 自动从本地 Edge 提取 (需要您先临时关闭 Edge 浏览器 3 秒钟)", flush=True)
    print(" [3] 稍后在 cookie.txt 中手动编辑", flush=True)
    print("="*55, flush=True)

    choice = input("请输入选项编号 (1/2/3): ").strip()

    if choice == "1":
        print("\n请在 Edge 中按 F12 -> 切换到 Console -> 运行 copy(document.cookie)", flush=True)
        raw_cookie = input("然后在此处粘贴 Cookie 字符串并按回车: ").strip()
        if raw_cookie:
            cookies = parse_raw_cookie_string(raw_cookie)
            save_cookies(cookies)
            print(f"[+] 成功保存 {len(cookies)} 项 Cookie！", flush=True)
            return cookies

    elif choice == "2":
        print("[*] 正在尝试从 Edge 数据库提取 Cookie...", flush=True)
        try:
            cookies = extract_cookies_from_edge()
            if cookies:
                save_cookies(cookies)
                print(f"[+] 成功从 Edge 提取并保存了 {len(cookies)} 项 Cookie！", flush=True)
                return cookies
        except Exception as e:
            print(f"[!] 提取失败: {e}", flush=True)

    elif choice == "3":
        print(f"[*] 请直接在 {COOKIE_TXT_FILE} 文件中粘贴您的 Cookie 字符串。", flush=True)

    return load_cookies()

def main():
    parser = argparse.ArgumentParser(description="GigaB2B 跨境大件平台工业级数据采集系统")
    parser.add_argument("--workers", type=int, default=20, help="并发线程数 (默认: 20)")
    parser.add_argument("--limit", type=int, default=None, help="限制最大采集商品数 (用于快速测试，默认全量)")
    parser.add_argument("--images", action="store_true", help="是否下载全量商品高清主图与轮播副图到本地")
    parser.add_argument("--no-scan", action="store_true", help="跳过微切片索引扫描，直接基于数据库已有任务继续采集")
    parser.add_argument("--export-only", action="store_true", help="仅从已有数据库导出 Excel 与 CSV 报表")
    parser.add_argument("--check-cookie", action="store_true", help="检查当前保存的 Cookie 登录态有效性")
    parser.add_argument("--status", action="store_true", help="查看数据库任务与已采集商品统计")
    parser.add_argument("--setup-cookie", action="store_true", help="进入 Cookie 交互式配置模式")

    args = parser.parse_args()

    db = Database.get_instance()

    # 1. 仅查看状态
    if args.status:
        stats = db.get_stats()
        print("\n" + "="*40, flush=True)
        print("        GigaB2B 数据库当前状态", flush=True)
        print("="*40, flush=True)
        print(f" - 任务总数:     {stats['total_tasks']:,}", flush=True)
        print(f" - 已完成详情:   {stats['done_tasks']:,}", flush=True)
        print(f" - 待抓取队列:   {stats['pending_tasks']:,}", flush=True)
        print(f" - 失败需重试:   {stats['failed_tasks']:,}", flush=True)
        print(f" - 已入库商品数: {stats['total_products']:,}", flush=True)
        print("="*40 + "\n", flush=True)
        return

    # 2. 仅重新导出报表
    if args.export_only:
        exporter = DataExporter()
        excel_files, csv_file = exporter.export_all()
        print(f"\n[+] 成功从数据库导出全量数据：", flush=True)
        for ef in excel_files:
            print(f" - Excel: {ef}", flush=True)
        if csv_file:
            print(f" - CSV:   {csv_file}", flush=True)
        return

    # 3. Cookie 配置模式
    if args.setup_cookie:
        interactive_setup_cookie()
        return

    # 4. 自动检测剪贴板 Cookie
    check_and_auto_import_clipboard()

    # 5. 加载 Cookie 并校验登录态
    cookies = load_cookies()
    session = get_authenticated_session(cookies)

    is_valid, msg = check_login_status(session)
    if args.check_cookie:
        print(f"[*] 登录态检查结果: {msg}", flush=True)
        return

    if not is_valid and not cookies:
        print(f"[!] 未检测到有效登录 Cookie: {msg}", flush=True)
        cookies = interactive_setup_cookie()
        session = get_authenticated_session(cookies)

    # 6. 启动采集引擎
    crawler = GigaB2BCrawler(session=session, max_workers=args.workers)
    crawler.run_full_crawl(
        download_images=args.images,
        scan_index=not args.no_scan,
        limit=args.limit
    )

if __name__ == "__main__":
    main()
