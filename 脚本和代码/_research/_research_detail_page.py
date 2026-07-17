# -*- coding: utf-8 -*-
"""调研：判决书详情页结构和下载入口"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import time
from playwright.sync_api import sync_playwright

OUT_DIR = r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图"

# 第一个判决书详情 URL（来自上一轮搜索结果）
DETAIL_URL = (
    "https://law.wkinfo.com.cn/judgment-documents/detail/"
    "MjA0MTUzMjY0NDg%3D?searchId=414d083230784dcfb945e42824384f25&index=1"
)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    # 监听下载事件
    downloads = []
    page.on("download", lambda d: downloads.append({
        "url": d.url, "suggested_filename": d.suggested_filename
    }))

    # 监听新 tab 打开事件（可能 PDF 下载会开新 tab）
    new_pages = []

    def on_page(p):
        new_pages.append({"url": p.url, "title": p.title()})
    ctx.on("page", on_page)

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    page.screenshot(path=f'{OUT_DIR}/18-judgment-detail.png', full_page=False)
    page.screenshot(path=f'{OUT_DIR}/19-judgment-detail-full.png', full_page=True)

    # 抓页面所有可见按钮
    all_btns = page.evaluate("""() => {
        const result = [];
        document.querySelectorAll('a, button, [role=button], .cg-icon, [class*=icon], i, span').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.width < 100 && r.height < 100) {
                const t = el.textContent.trim();
                const title = el.title || '';
                const aria = el.getAttribute('aria-label') || '';
                const cls = (el.className && typeof el.className === 'string') ? el.className.slice(0, 60) : '';
                const combined = (t + ' ' + title + ' ' + aria + ' ' + cls).toLowerCase();
                if (combined.includes('下载') || combined.includes('导出') ||
                    combined.includes('打印') || combined.includes('pdf') ||
                    combined.includes('word') || combined.includes('excel') ||
                    combined.includes('download') || combined.includes('export') ||
                    combined.includes('print')) {
                    result.push({
                        tag: el.tagName, text: t.slice(0, 30),
                        title: title.slice(0, 30), aria: aria.slice(0, 30),
                        cls: cls, x: Math.round(r.x), y: Math.round(r.y)
                    });
                }
            }
        });
        return result;
    }""")
    print('===下载相关元素===')
    seen = set()
    for b in all_btns[:30]:
        key = (b['tag'], b['cls'], b['x'], b['y'])
        if key not in seen:
            seen.add(key)
            print(b)

    # 抓顶部工具栏的所有可点击元素（按位置在 y=80-130 的范围）
    toolbar = page.evaluate("""() => {
        const result = [];
        document.querySelectorAll('a, button, span, div, i').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.y > 80 && r.y < 140 && r.width < 60 && r.height < 60) {
                result.push({
                    tag: el.tagName,
                    text: el.textContent.trim().slice(0, 20),
                    title: (el.title || '').slice(0, 30),
                    cls: ((el.className || '') + '').slice(0, 60),
                    x: Math.round(r.x), y: Math.round(r.y)
                });
            }
        });
        return result;
    }""")
    print('===顶部工具栏所有元素===')
    for t in toolbar[:30]:
        print(t)

    # 抓页面正文的case_no、title等元数据
    meta = page.evaluate("""() => {
        const result = {};
        // 案号、标题可能在特定class中
        const titleEl = document.querySelector('h1, .case-title, [class*=title], [class*=case-name]');
        if (titleEl) result.title = titleEl.innerText;
        const noEl = document.querySelector('.case-no, [class*=case-no], [class*=number]');
        if (noEl) result.caseNo = noEl.innerText;
        return result;
    }""")
    print('===元数据===')
    print(meta)

    # 抓页面主要文本
    text = page.evaluate('() => document.body.innerText')
    with open(f'{OUT_DIR}/18-judgment-detail-text.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    print('页面文本长度:', len(text))

    browser.close()

    print('===下载监听===')
    for d in downloads:
        print(d)
    print('===新窗口===')
    for p in new_pages:
        print(p)