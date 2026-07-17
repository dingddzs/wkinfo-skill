# -*- coding: utf-8 -*-
"""Phase 2: 抓法律法规 PDF 下载的实际 API"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

DETAIL_URL = "https://law.wkinfo.com.cn/legislation/detail/MTAxMDA0OTcwODI="

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
    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 监听下载请求
    downloads = []
    def on_request(req):
        if '/csi/document' in req.url or '/api/download' in req.url:
            downloads.append({
                'url': req.url,
                'method': req.method,
                'headers': dict(req.headers),
                'post': req.post_data
            })
    page.on('request', on_request)

    # 抓 caseId
    case_id = page.evaluate("""() => {
        const fav = document.querySelector('a[id^=favorites]');
        return fav ? fav.id.replace('favorites', '') : null;
    }""")
    print(f'caseId: {case_id}')

    # 点 PDF 下载
    page.locator(f'#pdf{case_id}').click()
    page.wait_for_timeout(3000)

    # 看 modal
    modal = page.evaluate("""() => {
        const overlay = document.querySelector('.cg-modal-overlay');
        const modal = document.querySelector('.cg-modal-content');
        const result = {};
        if (overlay || modal) {
            result.has_modal = true;
            if (modal) result.text = modal.innerText.slice(0, 500);
        }
        // 找所有可点击按钮
        const btns = Array.from(document.querySelectorAll('.cg-modal-footer-1-8-0 button, .modal-footer-container button'))
            .map(b => b.innerText.trim());
        result.buttons = btns;
        return result;
    }""")
    print(f'\nModal: {modal}')

    # 点"下载"按钮（确认 modal 内的）
    print('\n=== 点击 modal 内"下载"按钮 ===')
    clicked = page.evaluate("""() => {
        const btns = document.querySelectorAll('.cg-modal-footer-1-8-0 button, .modal-footer-container button');
        for (const b of btns) {
            if (b.innerText.trim() === '下载') {
                b.click();
                return true;
            }
        }
        return false;
    }""")
    print(f'点击 modal 下载按钮: {clicked}')
    page.wait_for_timeout(10000)

    print(f'\n=== 下载请求 ({len(downloads)} 个) ===')
    for d in downloads:
        print(f'\n{d["method"]} {d["url"][:200]}')
        if d.get('post'):
            try:
                body = json.loads(d['post'])
                print(f'Body: {json.dumps(body, ensure_ascii=False)[:500]}')
            except:
                print(f'Post: {d["post"][:300]}')

    b.close()

import json