# -*- coding: utf-8 -*-
"""Phase 2: 法律法规库侧边栏结构"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\legislation_sidebar.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = b.contexts[0]

    # 清理标签
    for p in ctx.pages[:]:
        if 'wkinfo.com.cn' not in p.url:
            p.close()
    pages = ctx.pages
    seen = set()
    for p in pages[:]:
        if p.url in seen or 'judgment-documents' in p.url:
            p.close()
        else:
            seen.add(p.url)

    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.goto('https://law.wkinfo.com.cn/legislation/list', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    page.screenshot(path=str(OUT_DIR / 'legislation-list.png'), full_page=False)

    # 抓页面主要结构
    structure = page.evaluate("""() => {
        const text = document.body.innerText.slice(0, 3000);
        const title = document.title;

        // 抓所有侧边栏 a.wk-tree-node-label
        const labels = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .map(l => {
                const r = l.getBoundingClientRect();
                return {
                    text: l.textContent.trim().slice(0, 30),
                    visible: r.width > 0 && r.height > 0,
                    rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width)}
                };
            })
            .filter(l => l.visible)
            .slice(0, 30);

        // 输入框
        const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
            name: i.name, type: i.type, placeholder: i.placeholder
        })).slice(0, 10);

        return {title, text_preview: text, sidebar_labels: labels, inputs};
    }""")

    print(f'标题: {structure["title"]}')
    print(f'\n侧边栏 label ({len(structure["sidebar_labels"])} 个):')
    for l in structure['sidebar_labels']:
        print(f'  {l["text"]:30s} (x={l["rect"]["x"]}, w={l["rect"]["w"]})')

    print(f'\n输入框: {structure["inputs"]}')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    # 展开所有"查看更多"
    print('\n=== 展开"查看更多" ===')
    page.evaluate("document.querySelectorAll('li.more').forEach(m => m.click());")
    page.wait_for_timeout(3000)

    labels_expanded = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .filter(l => l.offsetParent !== null)
            .map(l => l.textContent.trim().slice(0, 30));
    }""")
    print(f'展开后 {len(labels_expanded)} 个 label')
    for l in labels_expanded:
        print(f'  {l}')

    b.close()