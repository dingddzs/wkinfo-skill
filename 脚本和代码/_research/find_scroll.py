# -*- coding: utf-8 -*-
"""找正确的侧边栏滚动容器"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 找所有可滚动容器
    info = page.evaluate("""() => {
        const target = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .find(l => l.textContent.trim() === '北京市');
        if (!target) return {error: 'target_not_found'};
        const targetRect = target.getBoundingClientRect();

        const out = {target_rect: targetRect, candidates: []};
        let el = target.parentElement;
        for (let i = 0; i < 10; i++) {
            el = el?.parentElement;
            if (!el) break;
            const cs = getComputedStyle(el);
            const sh = el.scrollHeight;
            const ch = el.clientHeight;
            out.candidates.push({
                level: i,
                tag: el.tagName,
                className: el.className.slice(0, 80),
                overflow: cs.overflow,
                overflowY: cs.overflowY,
                scrollHeight: sh,
                clientHeight: ch,
                isScrollable: sh > ch + 10,
                rect: {x: Math.round(el.getBoundingClientRect().x),
                       y: Math.round(el.getBoundingClientRect().y),
                       w: Math.round(el.getBoundingClientRect().width),
                       h: Math.round(el.getBoundingClientRect().height)}
            });
        }
        return out;
    }""")
    import json
    print(json.dumps(info, ensure_ascii=False, indent=2))
    browser.close()