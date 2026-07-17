# -*- coding: utf-8 -*-
"""捕获浏览器点击侧边栏过滤器时的 API 调用"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    requests_log = []
    page.on("request", lambda req: (
        requests_log.append({"method": req.method, "url": req.url,
                             "post": req.post_data})
        if '/csi/search' in req.url
        else None
    ))

    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)

    # 先输入关键词
    page.evaluate("""() => {
        const input = document.querySelector('input[name="keyword"]');
        input.focus();
        input.value = '建设工程';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)

    print('===关键词搜索后的请求===')
    for r in requests_log:
        if r.get('post'):
            try:
                body = json.loads(r['post'])
                fqs = body.get('query', {}).get('filterQueries', [])
                if fqs:
                    print(f'\nURL: {r["url"][:100]}')
                    print(f'filterQueries: {fqs}')
            except:
                pass

    # 清空记录，点侧边栏"最高人民法院"
    requests_log.clear()
    print('\n===点击最高人民法院===')
    page.evaluate("""() => {
        document.querySelectorAll('label, span, div').forEach(el => {
            if (el.textContent.trim() === '最高人民法院' &&
                el.getBoundingClientRect().width > 0 &&
                el.closest('.wk-tree-node-content')) {
                el.click();
                return;
            }
        });
    }""")
    page.wait_for_timeout(15000)

    for r in requests_log:
        if r.get('post'):
            try:
                body = json.loads(r['post'])
                fqs = body.get('query', {}).get('filterQueries', [])
                if fqs:
                    print(f'\nURL: {r["url"][:100]}')
                    print(f'filterQueries: {fqs}')
            except:
                pass

    browser.close()