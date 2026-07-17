# -*- coding: utf-8 -*-
"""调研：仔细看工具栏 A 标签按钮"""
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

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 详细抓工具栏 A 标签 (1330-1570 x 范围)
    icons = page.evaluate("""() => {
        const result = [];
        document.querySelectorAll('a, button').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.x > 1330 && r.x < 1570 && r.y > 80 && r.y < 150) {
                result.push({
                    tag: el.tagName,
                    href: el.href || '',
                    title: el.title || '',
                    aria: el.getAttribute('aria-label') || '',
                    cls: (el.className || '').toString().slice(0, 80),
                    html: el.outerHTML.slice(0, 600),
                    rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}
                });
            }
        });
        return result;
    }""")
    print('===工具栏 A 按钮详细===')
    for i, ic in enumerate(icons):
        print(f'[{i+1}] x={ic["rect"]["x"]} cls={ic["cls"]}')
        print(f'    title="{ic["title"]}" aria="{ic["aria"]}"')
        print(f'    href="{ic["href"]}"')
        print(f'    html={ic["html"][:300]}')
        print()

    # 滚到顶部工具栏，让hover生效
    page.evaluate('window.scrollTo(0, 0)')
    page.wait_for_timeout(500)

    # 逐个hover 看tooltip
    for i, ic in enumerate(icons):
        x = ic['rect']['x'] + 18
        y = ic['rect']['y'] + 14
        page.mouse.move(x, y)
        page.wait_for_timeout(1500)
        tooltip = page.evaluate("""() => {
            // 找可能的tooltip
            const tt = document.querySelector('[role=tooltip], .tooltip, [class*=tooltip], .cg-tooltip, [class*=popper]');
            return tt ? tt.innerText : null;
        }""")
        print(f'Hover [{i+1}] x={x} tooltip={tooltip!r}')

    page.screenshot(path=f'{OUT_DIR}/21-toolbar-hovered.png', full_page=False)
    browser.close()