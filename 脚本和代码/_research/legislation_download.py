# -*- coding: utf-8 -*-
"""Phase 2: 查找法律法规的 PDF 下载入口（详情页 + 批量）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图")
OUT_DIR.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = b.contexts[0]
    for p in ctx.pages[:]:
        if 'wkinfo.com.cn' not in p.url:
            p.close()
    seen = set()
    for p in ctx.pages[:]:
        if 'judgment-documents' in p.url:
            p.close()
        elif p.url in seen:
            p.close()
        else:
            seen.add(p.url)

    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    # 搜索"公司法"
    page.goto('https://law.wkinfo.com.cn/legislation/list', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)
    page.fill('input[name="keyword"]', '公司法')
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)
    page.screenshot(path=str(OUT_DIR / 'legislation-search-result.png'), full_page=False)

    # 抓搜索结果列表项
    print('===搜索结果列表项===')
    items = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href*=\"/legislation/detail\"]'))
            .slice(0, 5)
            .map(a => {
                const rect = a.getBoundingClientRect();
                return {
                    href: a.href,
                    text: a.textContent.trim().slice(0, 60),
                    x: Math.round(rect.x), y: Math.round(rect.y)
                };
            });
    }""")
    for it in items:
        print(f'  {it["text"]:50s} | {it["href"][:100]}')

    # 抓页面所有按钮 + 可能含"下载/导出"
    print('\n===页面所有按钮===')
    btns = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, a[class*=btn], a[class*=button], [role=button]'))
            .filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0;
            })
            .map(el => ({
                tag: el.tagName,
                text: el.textContent.trim().slice(0, 30),
                cls: (el.className || '').toString().slice(0, 50),
                href: el.getAttribute('href') || ''
            }))
            .filter(b => b.text.length > 0 && b.text.length < 30);
    }""")
    for b in btns[:20]:
        print(f'  [{b["tag"]:6s}] {b["text"]:20s} | cls={b["cls"]}')

    # 点第一条进详情
    if items:
        page.goto(items[0]['href'], wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(15000)
        page.screenshot(path=str(OUT_DIR / 'legislation-detail.png'), full_page=False)

        # 抓详情页所有可点击元素（含下载按钮）
        print('\n===详情页可点击元素===')
        detail_btns = page.evaluate("""() => {
            const all = document.querySelectorAll('button, a, [role=button], [class*=download], [class*=export]');
            return Array.from(all).filter(el => {
                const r = el.getBoundingClientRect();
                const txt = el.textContent.trim();
                return r.width > 0 && txt.length > 0 && txt.length < 30;
            }).map(el => ({
                tag: el.tagName,
                text: el.textContent.trim(),
                cls: (el.className || '').toString().slice(0, 60),
                href: el.getAttribute('href') || '',
                id: el.id || ''
            }));
        }""")
        for b in detail_btns[:30]:
            mark = '↓' if any(k in b['text'] for k in ['下载', '导出', 'PDF', 'Excel', 'Word']) else ' '
            print(f'  {mark} [{b["tag"]:6s}] {b["text"]:25s} | id={b["id"]:20s}')

    b.close()