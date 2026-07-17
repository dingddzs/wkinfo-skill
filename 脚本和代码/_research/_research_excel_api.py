# -*- coding: utf-8 -*-
"""捕获浏览器 Excel 下载 API 调用"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
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

    requests_log = []
    page.on("request", lambda req: (
        requests_log.append({"method": req.method, "url": req.url,
                             "headers": dict(req.headers), "post": req.post_data})
        if '/csi/document' in req.url or '/api/download' in req.url
        else None
    ))

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    case_id = page.evaluate("""() => {
        const fav = document.querySelector('a[id^=favorites]');
        return fav ? fav.id.replace('favorites', '') : null;
    }""")
    print(f'caseId: {case_id}')

    # 点 Excel 下载
    page.locator(f'#excel{case_id}').click()
    page.wait_for_timeout(2000)

    # 点确认
    page.evaluate("""() => {
        document.querySelectorAll('.cg-modal-footer-1-8-0 button').forEach(b => {
            if (b.innerText.trim() === '下载') b.click();
        });
    }""")
    page.wait_for_timeout(10000)

    print('===Excel 下载请求===')
    for r in requests_log:
        print(f'\n{r["method"]} {r["url"][:200]}')
        if r.get('post'):
            try:
                body = json.loads(r['post'])
                print(f'Body:\n{json.dumps(body, ensure_ascii=False, indent=2)}')
            except:
                print(f'Post: {r["post"][:300]}')

    browser.close()