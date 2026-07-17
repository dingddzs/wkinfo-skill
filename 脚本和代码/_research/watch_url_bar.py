# -*- coding: utf-8 -*-
"""调试：观察点击侧边栏后 URL 栏的变化（用户的关键提示）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    # 1. 初始 URL
    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)
    print("===初始 URL===")
    print(page.url)
    print()

    # 2. 点搜索（输入"合同"）
    page.evaluate("""() => {
        const input = document.querySelector('input[name="keyword"]');
        input.focus();
        input.value = '合同';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)
    print("===搜索 '合同' 后 URL===")
    print(page.url)
    print()

    # 3. 点击 "最高人民法院" 侧边栏项
    click = page.evaluate("""() => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === '最高人民法院') {
                const r = l.getBoundingClientRect();
                if (r.width > 0) {
                    l.click();
                    return {clicked: true};
                }
            }
        }
        return {clicked: false};
    }""")
    print(f"===点击 '最高人民法院': {click}===")
    page.wait_for_timeout(3000)
    print("URL:")
    print(page.url)
    print()

    # 4. 点击 "判决书"
    page.evaluate("""() => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === '判决书') { l.click(); return; }
        }
    }""")
    page.wait_for_timeout(3000)
    print("===点击 '判决书' 后 URL===")
    print(page.url)
    print()

    # 5. 点击 "最近3年" 裁判日期
    page.evaluate("""() => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === '最近3年') { l.click(); return; }
        }
    }""")
    page.wait_for_timeout(3000)
    print("===点击 '最近3年' 后 URL===")
    print(page.url)
    print()

    # 6. 点击 "二审" 审判程序
    page.evaluate("""() => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === '二审') { l.click(); return; }
        }
    }""")
    page.wait_for_timeout(3000)
    print("===点击 '二审' 后 URL===")
    print(page.url)
    print()

    # 7. 点 "北京市" 审理法院
    page.evaluate("""() => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === '北京市') { l.click(); return; }
        }
    }""")
    page.wait_for_timeout(3000)
    print("===点击 '北京市' 后 URL===")
    print(page.url)
    print()

    # 8. 点 "民事" 案由
    page.evaluate("""() => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === '民事') { l.click(); return; }
        }
    }""")
    page.wait_for_timeout(3000)
    print("===点击 '民事' 后 URL===")
    print(page.url)
    print()

    # 截图最终状态
    page.screenshot(path=r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\url_after_clicks.png", full_page=False)

    browser.close()