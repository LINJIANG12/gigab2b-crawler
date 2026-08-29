# -*- coding: utf-8 -*-
"""
GigaB2B 交互式登录窗口：弹出 Edge，用户手动输入账号密码登录
登录成功后：在浏览器会话内验证价格接口 + showTieredPrice 阶梯价（渠道保护商品），并保存 Cookie
"""
import sys, os, json, time, asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

BASE = "https://www.gigab2b.com"
WAIT_SECONDS = 900
TEST_PIDS = ['1124034', '1450139', '430318']


def log(msg):
    print(msg, flush=True)


async def fetch_in_page(page, url):
    return await page.evaluate("""async (url) => {
        try {
            const r = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/plain, */*'}});
            const t = await r.text();
            try { return {json: JSON.parse(t)}; } catch (e) { return {text: t.slice(0, 150)}; }
        } catch (e) { return {error: String(e)}; }
    }""", url)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge", headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized", "--new-window"],
        )
        ctx = await browser.new_context(viewport=None)
        try:
            from cookie_manager import load_cookies
            cj = load_cookies()
            await ctx.add_cookies([{"name": k, "value": v, "domain": ".gigab2b.com", "path": "/",
                                    "httpOnly": False, "secure": False, "sameSite": "Lax"} for k, v in cj.items()])
        except Exception:
            pass

        page = await ctx.new_page()
        log("[*] 打开首页...")
        await page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        try:
            await page.evaluate("document.title = 'GigaB2B 登录 - 请在此窗口登录你的账号'")
        except Exception:
            pass
        await page.bring_to_front()

        if "safe/captcha" in page.url:
            log("[!] 出现验证码页，请先在窗口中完成滑块验证")
            deadline = time.time() + WAIT_SECONDS
            while time.time() < deadline and "safe/captcha" in page.url:
                await page.wait_for_timeout(2000)
            if "safe/captcha" in page.url:
                log("[X] 验证码未通过，退出")
                await browser.close()
                return

        clicked = False
        for sel in ["text=Login", "text=登录", "text=Log in", "a[href*='account/login']"]:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    await el.click(timeout=5000)
                    clicked = True
                    log(f"[*] 已点击登录入口 ({sel})")
                    break
            except Exception:
                pass
        if not clicked:
            log("[!] 未自动找到登录按钮，请手动点击页面上的 Login / 登录")
        await page.wait_for_timeout(3000)
        await page.bring_to_front()

        log("=" * 60)
        log("  >>> 请在弹出的 Edge 窗口中操作 <<<")
        log("  1) 输入你的 GigaB2B 账号邮箱和密码并登录（如遇验证码一并完成）")
        log("  2) 登录后请留在该窗口，脚本会自动测试价格接口")
        log(f"  脚本最多等待 {WAIT_SECONDS} 秒")
        log("=" * 60)

        deadline = time.time() + WAIT_SECONDS
        logged = False
        while time.time() < deadline:
            await page.wait_for_timeout(2500)
            try:
                cookies_js = await page.evaluate("document.cookie")
            except Exception:
                cookies_js = ""
            if "login_flag=1" in cookies_js.replace(" ", ""):
                log("[+] 检测到登录态 Cookie (login_flag=1)！")
                logged = True
                break
            left = int(deadline - time.time())
            if left % 30 < 3:
                log(f"    ...等待登录（剩余 {left}s）")

        if not logged:
            log("[X] 等待超时，未检测到登录。窗口即将关闭。")
            await page.wait_for_timeout(3000)
            await browser.close()
            return

        await page.wait_for_timeout(3000)
        log("\n[*] 登录成功！浏览器会话内测试（窗口保持打开，稍后自动关闭）:")

        # 1) 普通价格接口
        for pid in TEST_PIDS:
            r = await fetch_in_page(page, f"{BASE}/index.php?route=product/info/price/list&product_id={pid}")
            j = r.get("json") or {}
            d = j.get("data") or {}
            bp = d.get("base_price_info") or {}
            log(f"    price/list {pid}: code={j.get('code')} pv={d.get('price_visible')} price={bp.get('price')}")

        # 2) 阶梯价接口（渠道保护商品的关键）
        for pid in TEST_PIDS:
            r = await fetch_in_page(page, f"{BASE}/index.php?route=product/product/showTieredPrice&product_id={pid}")
            if r.get("json") is not None:
                j = r["json"]
                d = j.get("data") or {}
                if j.get("code") == 200 and d.get("tiered_price_list"):
                    log(f"    tiered {pid}: code=200 current_price={d.get('current_price')} tiers={json.dumps(d.get('tiered_price_list'), ensure_ascii=False)[:300]}")
                else:
                    log(f"    tiered {pid}: code={j.get('code')} msg={j.get('msg')} data={json.dumps(d, ensure_ascii=False)[:150]}")
            else:
                log(f"    tiered {pid}: {json.dumps(r, ensure_ascii=False)[:150]}")

        # 保存 Cookie
        cookies = await ctx.cookies()
        cookie_dict = {}
        for c in cookies:
            if c["domain"].endswith("gigab2b.com"):
                cookie_dict[c["name"]] = c["value"]
        from cookie_manager import save_cookies
        save_cookies(cookie_dict)
        log(f"\n[*] 已保存 {len(cookie_dict)} 个 Cookie; login_flag={cookie_dict.get('login_flag')!r}")
        log("[*] 窗口保持 20 秒后自动关闭（如需在窗口内补充账户资料请抓紧操作）")
        await page.wait_for_timeout(20000)
        await browser.close()
        log("[*] 浏览器已关闭")
        log("[done]")


if __name__ == "__main__":
    asyncio.run(main())
