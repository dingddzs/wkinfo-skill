# -*- coding: utf-8 -*-
"""Phase 2: 找批量 Excel 导出按钮"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

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

    # 搜索
    page.goto('https://law.wkinfo.com.cn/legislation/list', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)
    page.fill('input[name="keyword"]', '公司法')
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)

    # 监听下载请求
    downloads = []
    def on_request(req):
        if '/csi/document' in req.url or '/api/download' in req.url:
            downloads.append({'url': req.url, 'method': req.method, 'post': req.post_data})
    page.on('request', on_request)

    # 找所有可能含"导出/批量/Excel"的按钮
    btns = page.evaluate("""() => {
        const all = document.querySelectorAll('button, a, [class*=export], [class*=batch]');
        return Array.from(all).filter(el => {
            const r = el.getBoundingClientRect();
            const txt = el.textContent.trim();
            return r.width > 0 && txt.length > 0 && txt.length < 20;
        }).map(el => ({
            tag: el.tagName,
            text: el.textContent.trim(),
            cls: (el.className || '').toString().slice(0, 50),
            id: el.id || '',
            href: el.getAttribute('href') || ''
        }));
    }""")
    print('===所有按钮===')
    for b in btns:
        mark = '↓' if any(k in b['text'] for k in ['导出', '批量', 'Excel', '下载']) else ' '
        print(f'  {mark} {b["text"]:20s} | id={b["id"]:15s} cls={b["cls"]}')

    # 试点击"导出Excel"或类似
    print('\n=== 试点击 Excel 导出 ===')
    excel_clicked = page.evaluate("""() => {
        const all = document.querySelectorAll('button, a');
        for (const el of all) {
            const txt = el.textContent.trim();
            if (/(导出|Excel|批量)/.test(txt) && txt.length < 15) {
                const r = el.getBoundingClientRect();
                if (r.width > 0) {
                    el.click();
                    return {clicked: true, text: txt};
                }
            }
        }
        return {clicked: false};
    }""")
    print(f'Excel click: {excel_clicked}')
    page.wait_for_timeout(5000)

    # 看下载请求
    print(f'\n=== 下载请求 ({len(downloads)} 个) ===')
    for d in downloads:
        print(f'\n{d["method"]} {d["url"][:200]}')
        if d.get('post'):
            try:
                body = json.loads(d['post'])
                print(f'Body: {json.dumps(body, ensure_ascii=False)[:400]}')
            except:
                print(f'Post: {d["post"][:200]}')

    b.close()

import json