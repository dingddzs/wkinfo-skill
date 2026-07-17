# -*- coding: utf-8 -*-
"""捕获 downloadPath API 请求体细节"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

DETAIL_URL = (
    "https://law.wkinfo.com.cn/judgment-documents/detail/"
    "MjA0MTUzMjY0NDg%3D?searchId=414d083230784dcfb945e42824384f25&index=1"
)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    api_calls = []
    page.on("request", lambda req: (
        api_calls.append({
            "method": req.method, "url": req.url,
            "headers": dict(req.headers),
            "post_data": req.post_data
        }) if '/api/download' in req.url or '/csi/document/downloadPath' in req.url or '/csi/document/downloadLimit' in req.url else None
    ))
    page.on("response", lambda res: (
        api_calls.append({
            "type": "res", "url": res.url, "status": res.status,
            "headers": dict(res.headers),
            "body": res.text() if 'downloadPath' in res.url else None
        }) if 'downloadPath' in res.url else None
    ))

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    case_id = page.evaluate("""() => {
        const fav = document.querySelector('a[id^=favorites]');
        return fav ? fav.id.replace('favorites', '') : null;
    }""")
    print(f'caseId: {case_id}\n')

    # 点 PDF 下载
    page.locator(f'#pdf{case_id}').click()
    page.wait_for_timeout(2000)

    # 点下载按钮
    page.evaluate("""() => {
        document.querySelectorAll('.cg-modal-footer-1-8-0 button').forEach(b => {
            if (b.innerText.trim() === '下载') b.click();
        });
    }""")
    page.wait_for_timeout(10000)

    print('===API 调用记录===')
    import json
    for c in api_calls:
        if c.get('type') == 'res':
            print(f'\n>>> RESPONSE: {c["url"]}')
            print(f'Status: {c["status"]}')
            if c.get('body'):
                try:
                    body = json.loads(c['body'])
                    print(f'Body (JSON): {json.dumps(body, ensure_ascii=False, indent=2)}')
                except:
                    print(f'Body (text, first 500): {c["body"][:500]}')
        else:
            print(f'\n>>> REQUEST: {c["method"]} {c["url"]}')
            if c.get('post_data'):
                print(f'POST data: {c["post_data"]}')
            # 关键 header
            for k in ['content-type', 'cookie', 'authorization', 'uid', 'identification', 'module']:
                if k in c['headers']:
                    v = c['headers'][k]
                    if k == 'cookie':
                        v = v[:100] + '...' if len(v) > 100 else v
                    print(f'  {k}: {v}')

    browser.close()