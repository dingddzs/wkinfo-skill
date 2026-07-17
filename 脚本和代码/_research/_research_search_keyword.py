# -*- coding: utf-8 -*-
"""捕获浏览器搜索时的完整请求体"""
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
                             "headers": dict(req.headers), "post": req.post_data})
        if '/csi/search' in req.url or '/csi/document' in req.url
        else None
    ))

    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)

    # 等页面 ready
    page.evaluate("""() => {
        const input = document.querySelector('input[name="keyword"]');
        input.focus();
        input.value = '建设工程施工合同纠纷';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(20000)

    print('===搜索相关请求===')
    for i, r in enumerate(requests_log):
        if '/search' in r['url'] and 'doc-count' not in r['url']:
            print(f'\n--- Request {i} ---')
            print(f'Method: {r["method"]}')
            print(f'URL: {r["url"][:300]}')
            if r.get('post'):
                try:
                    body = json.loads(r['post'])
                    print(f'Body:')
                    print(json.dumps(body, ensure_ascii=False, indent=2)[:3000])
                except:
                    print(f'Body (raw): {r["post"][:1000]}')
            # 关键 header
            for k in ['content-type', 'cookie']:
                if k in r['headers']:
                    h = r['headers'][k]
                    if k == 'cookie':
                        h = h[:80] + '...' if len(h) > 80 else h
                    print(f'  {k}: {h}')

    browser.close()