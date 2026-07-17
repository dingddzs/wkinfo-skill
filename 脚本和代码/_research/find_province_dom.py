# -*- coding: utf-8 -*-
"""看审理法院的 DOM 结构 - 为什么 click 不生效"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 直接查找所有 "审理法院" 标签 + 它的子项
    info = page.evaluate("""() => {
        const out = {group: null, items: [], sidebar_scroll: null};
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.children.length === 0 && el.textContent.trim() === '审理法院') {
                // 找到组容器
                let container = el;
                for (let i = 0; i < 5; i++) {
                    container = container?.parentElement;
                    if (!container) break;
                }
                if (!container) continue;

                // 看容器结构
                out.group = {
                    text: container.textContent.slice(0, 200),
                    className: container.className.slice(0, 100),
                    childCount: container.children.length
                };

                // 找容器内的所有 a.wk-tree-node-label
                const labels = container.querySelectorAll('a.wk-tree-node-label');
                out.items = Array.from(labels).slice(0, 10).map(l => {
                    const r = l.getBoundingClientRect();
                    return {
                        text: l.textContent.trim(),
                        rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
                        parent: l.parentElement?.className.slice(0, 50),
                        visible: r.width > 0 && r.height > 0
                    };
                });
                break;
            }
        }
        // 找侧边栏滚动容器
        const sbs = document.querySelectorAll('.wk-tree, .filter-tree, [class*=sidebar], [class*=tree-pane]');
        out.sidebar_scroll = Array.from(sbs).slice(0, 3).map(s => ({
            className: s.className.slice(0, 80),
            scrollHeight: s.scrollHeight,
            clientHeight: s.clientHeight,
            scrollTop: s.scrollTop
        }));
        return out;
    }""")
    print(json.dumps(info, ensure_ascii=False, indent=2)[:3000])

    browser.close()