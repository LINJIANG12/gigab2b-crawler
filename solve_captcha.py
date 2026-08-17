# -*- coding: utf-8 -*-
"""
GigaB2B WAF(阿里云验证码) 人机协作解封脚本

背景（已实测）：
- 站点 JSON API 受阿里云 WAF 保护，探测过频后 price/list、baseInfos、search 等
  接口返回 code=302 + redirect=/index.php?route=safe/captcha&vk=...
- 挑战为阿里云验证码 2.0 滑块拼图（SceneId: ocas5jlr, popup 模式）
- 手动完成一次滑块后服务端放行；放行绑定浏览器会话且时效较短，
  因此关键操作应尽快在浏览器会话内完成

用法（二选一）：
1) 直接在终端运行（推荐）:
   py -3.14 solve_captcha.py
   —— 屏幕弹出 Edge 窗口，点击 Verify 并拖动滑块完成拼图，
      脚本自动检测放行、保存 Cookie 并验证价格接口。

2) 从后台环境拉起窗口（如本 GUI 会话）:
   schtasks /Create /TN GigaCaptcha /TR "cmd /c cd /d <项目目录> && py -3.14 -u solve_captcha.py > _tmp/captcha.log 2>&1" /SC ONCE /ST 00:00 /IT /F
   schtasks /Run /TN GigaCaptcha
   —— 以交互式任务运行，窗口会显示在用户桌面。

说明：全程只在本机浏览器完成一次人工验证，不涉及账号密码。
"""
import sys
import os
import json
import time
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

BASE = "https://www.gigab2b.com"
PRICE_URL = f"{BASE}/index.php?route=product/info/price/list&product_id=1124034"
WAIT_SECONDS = 600  # 最多等 10 分钟


def log(msg):
    print(msg, flush=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized", "--new-window"],
        )
        ctx = await browser.new_context(viewport=None)
        try:
            from cookie_manager import load_cookies
            cj = load_cookies()
            await ctx.add_cookies([{"name": k, "value": v, "domain": ".gigab2b.com", "path": "/",
                                    "httpOnly": False, "secure": False, "sameSite": "Lax"} for k, v in cj.items()])
        except Exception as e:
            log(f"[!] 载入 Cookie 失败(忽略): {e}")

        page = await ctx.new_page()
        log("[*] 打开价格接口(将跳转验证码页)...")
        await page.goto(PRICE_URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(4000)
        try:
            await page.evaluate("document.title = 'GigaB2B 验证码 - 请拖动滑块'")
        except Exception:
            pass
        await page.bring_to_front()
        log(f"[*] 当前页面: {page.url[:110]}")

        if "safe/captcha" not in page.url:
            log("[+] 没有触发验证码（可能已解封），直接进入保存流程")
        else:
            log("=" * 60)
            log("  >>> 请在屏幕上的 Edge 窗口中操作 <<<")
            log("  1) 点击页面上的 Verify 按钮")
            log("  2) 拖动滑块，把拼图块对准缺口")
            log("  3) 通过后页面会自动跳转到商品价格 JSON")
            log(f"  脚本最多等待 {WAIT_SECONDS} 秒")
            log("=" * 60)

            deadline = time.time() + WAIT_SECONDS
            solved = False
            while time.time() < deadline:
                await page.wait_for_timeout(2000)
                try:
                    await page.bring_to_front()
                except Exception:
                    pass
                url_now = page.url
                cookies = await ctx.cookies()
                names = [c["name"] for c in cookies]
                if "safe/captcha" not in url_now:
                    log(f"[+] 已通过验证！当前页面: {url_now[:110]}")
                    solved = True
                    break
                if "acw_sc__v2" in names:
                    log("[+] 检测到放行 Cookie acw_sc__v2")
                    solved = True
                    break
                left = int(deadline - time.time())
                if left % 30 < 2:
                    log(f"    ...仍在等待操作（剩余 {left}s）")
            if not solved:
                log("[X] 等待超时，未检测到通过。窗口即将关闭。")

        await page.wait_for_timeout(2000)
        cookies = await ctx.cookies()
        cookie_dict = {}
        for c in cookies:
            if c["domain"].endswith("gigab2b.com"):
                cookie_dict[c["name"]] = c["value"]
        from cookie_manager import save_cookies
        save_cookies(cookie_dict)
        sc2 = [c["name"] for c in cookies if "acw_sc" in c["name"]]
        log(f"[*] 已保存 {len(cookie_dict)} 个 Cookie; WAF 放行 Cookie: {sc2 or '无'}")
        await browser.close()
        log("[*] 浏览器已关闭")

    # 验证价格接口
    log("")
    log("[*] 用保存的 Cookie 验证价格接口:")
    from cookie_manager import get_authenticated_session, load_cookies
    s = get_authenticated_session(load_cookies())
    s.headers.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"})
    r = s.get(PRICE_URL, timeout=15)
    try:
        j = r.json()
        d = j.get("data") or {}
        if j.get("code") == 200:
            bp = d.get("base_price_info") or {}
            log(f"    [OK] code=200 pv={d.get('price_visible')} price={bp.get('price')}")
        else:
            log(f"    [X] code={j.get('code')} msg={j.get('msg')} redirect={(j.get('redirect') or '')[:50]}")
    except Exception as e:
        log(f"    [X] EXC {e}")
    log("[done]")


if __name__ == "__main__":
    asyncio.run(main())
