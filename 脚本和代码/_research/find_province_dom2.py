# -*- coding: utf-8 -*-
"""精确找审理法院组的容器"""
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

    # 找 "审理法院" 标题，找到它的最近祖先容器（用 sibling / parent walk）
    info = page.evaluate("""() => {
        const titles = [];
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length === 0 && el.textContent.trim().length < 20 &&
                ['审理法院', '案由', '审判程序', '裁判日期', '文书类型', '参照级别'].includes(el.textContent.trim())) {
                titles.push(el.textContent.trim());
            }
        });
        return titles;
    }""")
    print('找到的标题:', info)

    # 找"审理法院"组的直接容器（找 a.wk-tree-node-label="北京市" 的最近祖先 .wk-tree-node-content）
    info2 = page.evaluate("""() => {
        // 找 "北京市" 的 a.wk-tree-node-label
        const target = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .find(l => l.textContent.trim() === '北京市');

        if (!target) return {error: 'target_not_found'};

        const rect = target.getBoundingClientRect();
        // 向上找 wk-tree-node 直到 含有 "审理法院" 文本的同级祖先
        let node = target;
        for (let i = 0; i < 8; i++) {
            node = node.parentElement;
            if (!node) break;
            // 看这个父节点是否包含 "审理法院" 标题
            const txt = node.textContent || '';
            if (txt.includes('审理法院') && txt.includes('北京市')) {
                return {
                    found_at_level: i,
                    className: node.className.slice(0, 80),
                    rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    in_viewport: rect.y >= 0 && rect.y < 1080,
                    nearby_titles: Array.from(node.querySelectorAll('*'))
                        .filter(e => e.children.length === 0 && e.textContent.length < 15)
                        .map(e => e.textContent.trim()).slice(0, 10)
                };
            }
        }
        return {error: 'container_not_found', target_rect: rect};
    }""")
    print('北京市 容器查找:', json.dumps(info2, ensure_ascii=False, indent=2))

    # 找 "北京市" 的 label，看是否在视口内
    info3 = page.evaluate("""() => {
        const target = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .find(l => l.textContent.trim() === '北京市');
        if (!target) return null;
        const rect = target.getBoundingClientRect();
        return {
            rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
            in_viewport: rect.y >= 0 && rect.y < 1080 && rect.x >= 0 && rect.x < 1920,
            offsetTop: target.offsetTop,
            scrollY: window.scrollY
        };
    }""")
    print('北京市 元素位置:', json.dumps(info3, ensure_ascii=False, indent=2))

    browser.close()