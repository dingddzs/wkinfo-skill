# -*- coding: utf-8 -*-
"""测试：点击下载按钮，处理确认modal，捕获真实下载URL"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
from playwright.sync_api import sync_playwright

OUT_DIR = r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源"
DL_DIR = OUT_DIR + "/downloads"
os.makedirs(DL_DIR, exist_ok=True)

DETAIL_URL = (
    "https://law.wkinfo.com.cn/judgment-documents/detail/"
    "MjA0MTUzMjY0NDg%3D?searchId=414d083230784dcfb945e42824384f25&index=1"
)

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    cdp_session = ctx.new_cdp_session(page)
    cdp_session.send("Browser.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": DL_DIR
    })

    downloads = []
    page.on("download", lambda d: downloads.append({
        "url": d.url, "filename": d.suggested_filename,
        "save_as": lambda p=d.save_as: p
    }))

    requests_log = []
    page.on("request", lambda req: requests_log.append({
        "type": "req", "url": req.url, "method": req.method
    }))
    page.on("response", lambda res: requests_log.append({
        "type": "res", "url": res.url, "status": res.status,
        "content_type": res.headers.get('content-type', ''),
        "content_disp": res.headers.get('content-disposition', '')
    }))

    page.goto(DETAIL_URL, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    case_id = page.evaluate("""() => {
        const fav = document.querySelector('a[id^=favorites]');
        return fav ? fav.id.replace('favorites', '') : null;
    }""")
    print(f'caseId: {case_id}')

    # 点 下载Pdf
    page.locator(f'#pdf{case_id}').click()
    page.wait_for_timeout(3000)

    # 抓 modal 内容
    modal_info = page.evaluate("""() => {
        const overlay = document.querySelector('.cg-modal-overlay');
        const modal = document.querySelector('.cg-modal, [class*=modal-], [role=dialog]');
        const result = {};
        if (overlay) {
            const allModal = document.querySelectorAll('[class*=modal], [role=dialog]');
            result.modals = Array.from(allModal).map(m => ({
                cls: m.className.toString().slice(0,80),
                text: m.innerText.slice(0, 500)
            }));
        }
        // 抓按钮
        const buttons = document.querySelectorAll('button');
        result.buttons = Array.from(buttons).filter(b => {
            const r = b.getBoundingClientRect();
            return r.width > 0 && b.innerText && b.innerText.length < 10;
        }).map(b => ({text: b.innerText.trim(), cls: b.className.slice(0,60)}));
        return result;
    }""")
    print('\n===Modal 信息===')
    print(modal_info)

    # 清空请求日志
    requests_log.clear()

    # 点"下载"按钮（在modal里找 - 不是"取消"）
    confirm_clicked = page.evaluate("""() => {
        const buttons = document.querySelectorAll('.cg-modal-footer-1-8-0 button, .modal-footer-container button');
        for (const b of buttons) {
            const t = b.innerText.trim();
            if (t === '下载') {
                b.click();
                return true;
            }
        }
        return false;
    }""")
    print(f'\n下载按钮点击: {confirm_clicked}')

    page.wait_for_timeout(15000)

    print('\n===确认后的网络请求===')
    for r in requests_log:
        print(r)

    print('\n===下载事件===')
    for d in downloads:
        print(d)

    # 检查下载目录
    files = os.listdir(DL_DIR) if os.path.exists(DL_DIR) else []
    print(f'\n===下载目录文件===\n路径: {DL_DIR}\n文件: {files}')

    page.screenshot(path=f'{OUT_DIR}/截图/23-after-confirm.png', full_page=False)
    browser.close()