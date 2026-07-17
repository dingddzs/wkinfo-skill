# -*- coding: utf-8 -*-
"""Phase 2: 法律法规详情页工具栏（顶部图标按钮）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\ai/Claudecode/威科案例检索和下载-20260716/临时资源/截图")
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

    # 抓详情页工具栏（顶部图标按钮）
    info = page.evaluate("""() => {
        // 找顶部工具栏区域的元素
        const results = [];
        // 找所有 a 和 button 在 top 200px 内
        document.querySelectorAll('a, button').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && r.y < 250 && r.x > 1000) {
                const txt = el.textContent.trim();
                // 找 icon 元素或带特定类
                const hasIcon = el.querySelector('svg, i, [class*=icon]');
                results.push({
                    tag: el.tagName,
                    text: txt.slice(0, 20),
                    title: el.title || '',
                    href: el.getAttribute('href') || '',
                    cls: (el.className || '').toString().slice(0, 60),
                    id: el.id || '',
                    hasIcon: !!hasIcon,
                    rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}
                });
            }
        });
        return results;
    }""")

    print(f'顶部右侧可点击元素 ({len(info)} 个):')
    for i in info:
        marker = ''
        for k in ['下载', 'PDF', 'Word', 'Excel', '导出', '打印', 'Print', '邮件', 'Email']:
            if k in i['text'] or k in i['title'] or k in i['cls']:
                marker = '↓'
                break
        print(f'  {marker} [{i["tag"]:6s}] text=\"{i["text"]:15s}\" title=\"{i["title"]:15s}\" id={i["id"]:20s} cls={i["cls"]:30s}')

    # 滚动到顶部，确保看到工具栏
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT_DIR / 'legislation-detail-toolbar.png'), full_page=False)

    # 尝试找到 ID 模式为 pdf{caseId}, word{caseId}, excel{caseId} 的按钮
    print('\n===按ID模式找下载按钮===')
    downloads = page.evaluate("""() => {
        const buttons = ['pdf', 'word', 'excel', 'docx', 'xls', 'print', 'email'];
        const found = [];
        buttons.forEach(key => {
            // 找 id 以这些前缀开头的元素
            document.querySelectorAll(`[id^=${key}]`).forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > 0) {
                    found.push({
                        key, id: el.id,
                        tag: el.tagName,
                        text: el.textContent.trim().slice(0, 20),
                        title: el.title || ''
                    });
                }
            });
        });
        return found;
    }""")
    for d in downloads:
        print(f'  {d["key"]:8s} {d["id"]:30s} tag={d["tag"]} text="{d["text"]}"')

    # 也找带图标 + title 含下载/导出/PDF 的
    print('\n===找所有 title 含下载的按钮===')
    titled = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a, button'))
            .filter(el => {
                const title = el.title || '';
                return /下载|PDF|Word|Excel|打印|导出|Print|Email/.test(title);
            })
            .map(el => ({
                tag: el.tagName,
                id: el.id,
                title: el.title,
                text: el.textContent.trim().slice(0, 20),
                cls: (el.className || '').toString().slice(0, 60),
                href: el.getAttribute('href') || ''
            }));
    }""")
    for t in titled:
        print(f'  [{t["tag"]:6s}] title=\"{t["title"]}\" id={t["id"]} text=\"{t["text"]}\" cls={t["cls"]}')

    b.close()