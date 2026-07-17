# -*- coding: utf-8 -*-
"""测试：点击下载按钮，看触发什么（下载/新tab/API）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import time
from playwright.sync_api import sync_playwright

OUT_DIR = r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源"
DL_DIR = OUT_DIR + "/downloads"

DETAIL_URL = (
    "https://law.wkinfo.com.cn/judgment-documents/detail/"
    "MjA0MTUzMjY0NDg%3D?searchId=414d083230784dcfb945e42824384f25&index=1"
)

import os
os.makedirs(DL_DIR, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    # 配置下载路径
    cdp_session = ctx.new_cdp_session(page)
    cdp_session.send("Browser.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": DL_DIR
    })

    # 监听下载事件
    downloads = []
    page.on("download", lambda d: downloads.append({
        "url": d.url, "filename": d.suggested_filename
    }))

    # 监听请求/响应
    requests_log = []
    page.on("request", lambda req: requests_log.append({
        "type": "req", "url": req.url, "method": req.method,
        "headers": dict(req.headers) if req.headers else {}
    }))
    page.on("response", lambda res: requests_log.append({
        "type": "res", "url": res.url, "status": res.status,
        "headers": dict(res.headers) if res.headers else {}
    }))

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)
    print('页面加载完成')

    # 抓 caseId
    case_id = page.evaluate("""() => {
        const fav = document.querySelector('a[id^=favorites]');
        return fav ? fav.id.replace('favorites', '') : null;
    }""")
    print('caseId:', case_id)

    # 清空监听日志（只看点击后的请求）
    requests_log.clear()

    # 点击"下载Pdf"
    print('\n===点击 下载Pdf===')
    pdf_btn = page.locator(f'#pdf{case_id}')
    print('按钮存在:', pdf_btn.count() > 0)
    pdf_btn.click()
    page.wait_for_timeout(8000)

    print('\n===点击后的网络请求===')
    for r in requests_log[-30:]:
        print(r)

    print('\n===下载文件===')
    for d in downloads:
        print(d)

    page.screenshot(path=f'{OUT_DIR}/截图/22-after-pdf-click.png', full_page=False)

    # 再点 Excel
    print('\n===点击 下载Excel===')
    requests_log.clear()
    excel_btn = page.locator(f'#excel{case_id}')
    excel_btn.click()
    page.wait_for_timeout(8000)

    print('===Excel点击后的网络请求===')
    for r in requests_log[-20:]:
        print(r)

    print('\n===所有下载===')
    for d in downloads:
        print(d)

    # 检查文件
    import os
    files = os.listdir(DL_DIR) if os.path.exists(DL_DIR) else []
    print('\n===下载目录===')
    print(f'路径: {DL_DIR}')
    print(f'文件: {files}')

    browser.close()