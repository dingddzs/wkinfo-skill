# -*- coding: utf-8 -*-
"""临时调研脚本：查看威科案例搜索结果结构（仅用于阶段 2）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

OUT_DIR = r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图"

# 以字符串变量传递，避免编码问题
KEYWORD = "建设工程施工合同"  # 建设工程施工合同

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)

    # 点判决书复选框
    page.evaluate("""() => {
        document.querySelectorAll('label, span, div').forEach(el => {
            if (el.textContent.trim() === '判决书') {
                const r = el.getBoundingClientRect();
                if (r.width > 0) { el.click(); return; }
            }
        });
    }""")
    page.wait_for_timeout(3000)

    # 设置关键词（用 evaluate 模拟键盘事件，绕过 Angular 的可交互性问题）
    page.evaluate(f"""(kw) => {{
        const input = document.querySelector('input[name="keyword"]');
        if (!input) return false;
        input.focus();
        input.value = kw;
        // 触发 Angular 的 change 检测
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
    }}""", KEYWORD)
    page.wait_for_timeout(1000)
    # 用键盘 Enter 触发搜索（比点击更可靠）
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)

    items = page.evaluate("""() => {
        const result = [];
        const containers = document.querySelectorAll('.wk-search-list, [class*=result-list], [class*=search-result]');
        for (const c of containers) {
            const its = c.querySelectorAll('[class*=item], li, tr');
            for (let i = 0; i < Math.min(3, its.length); i++) {
                result.push({
                    html: its[i].outerHTML.slice(0, 1500),
                    text: its[i].innerText.slice(0, 300)
                });
            }
        }
        return result;
    }""")
    print('===结果列表结构（前3条）===')
    for i, it in enumerate(items[:3]):
        print(f'--- Item {i+1} ---')
        print(f'文本: {it["text"]}')
        print(f'HTML: {it["html"][:800]}')
        print()

    links = page.evaluate("""() => {
        const result = [];
        document.querySelectorAll('a[href]').forEach(a => {
            const t = a.textContent.trim();
            const href = a.href;
            if (href.includes('judgment') || href.includes('case') || href.includes('detail')) {
                result.push({text: t.slice(0,40), href: href.slice(0,200)});
            }
        });
        return result;
    }""")
    print('===结果项链接===')
    for l in links[:10]:
        print(l)

    print('===完整 URL===')
    print(page.url)

    page.screenshot(path=f'{OUT_DIR}/17-search-result-list.png', full_page=False)
    browser.close()