# -*- coding: utf-8 -*-
"""调研：点击判决书详情页工具栏按钮，找到下载/导出入口"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

OUT_DIR = r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图"

DETAIL_URL = (
    "https://law.wkinfo.com.cn/judgment-documents/detail/"
    "MjA0MTUzMjY0NDg%3D?searchId=414d083230784dcfb945e42824384f25&index=1"
)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    downloads = []
    page.on("download", lambda d: downloads.append({
        "url": d.url, "filename": d.suggested_filename
    }))

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 抓所有可见工具栏按钮的 HTML（包含 innerHTML 看是否有svg title等线索）
    toolbar_html = page.evaluate("""() => {
        const result = [];
        const elements = document.querySelectorAll('.folding-tool, .wkb-href-icon, [class*=icon], a[href]');
        elements.forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.y > 80 && r.y < 150 && r.width < 50 && r.height < 50) {
                result.push({
                    tag: el.tagName,
                    cls: (el.className || '').toString().slice(0, 80),
                    href: el.href || '',
                    text: el.textContent.trim().slice(0, 30),
                    innerHTML: el.innerHTML.slice(0, 300),
                    rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width)}
                });
            }
        });
        return result;
    }""")
    print('===工具栏元素（含innerHTML）===')
    for t in toolbar_html:
        print(t)
        print('---')

    # 点 "更多" 按钮（folding-tool）
    more_btn = page.locator('.folding-tool').first
    print('\n===点 更多 按钮===')
    more_btn.click()
    page.wait_for_timeout(3000)

    # 看弹出的菜单项
    menu_items = page.evaluate("""() => {
        const result = [];
        // 找所有弹出层、下拉菜单
        document.querySelectorAll('[class*=dropdown], [class*=menu], [class*=popup], [class*=popover], [role=menu], [class*=flyout], ul li').forEach(el => {
            const t = el.textContent.trim();
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && t.length < 30 && t.length > 0) {
                result.push({
                    tag: el.tagName,
                    text: t,
                    cls: (el.className || '').toString().slice(0, 60),
                    rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}
                });
            }
        });
        return result;
    }""")
    print('===更多菜单项===')
    for m in menu_items[:30]:
        print(m)

    page.screenshot(path=f'{OUT_DIR}/20-more-menu-opened.png', full_page=False)

    browser.close()
    print('\n===下载监听===')
    for d in downloads:
        print(d)