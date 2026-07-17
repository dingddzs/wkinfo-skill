# -*- coding: utf-8 -*-
"""调试 v5：完整抓取侧边栏结构"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)

    # 抓取侧边栏所有分组 + 每组前3个选项的 DOM 结构
    result = page.evaluate("""() => {
        const out = [];
        // 找到所有 "过滤条件" 下的组
        const groups = document.querySelectorAll('.wk-filter-tree-node, .filter-group, [class*=tree-node]');
        const seen = new Set();
        for (const g of groups) {
            const text = g.textContent.trim().slice(0, 30);
            if (seen.has(text)) continue;
            seen.add(text);

            // 取组标题
            const titleEl = g.querySelector('.wk-tree-node-label, .tree-label, h3, h4, .filter-title');
            const title = titleEl ? titleEl.textContent.trim() : text.slice(0, 20);

            // 取前3个选项
            const items = [];
            const itemEls = g.querySelectorAll('.wk-tree-node, .filter-item, li, a, label');
            for (let i = 0; i < Math.min(3, itemEls.length); i++) {
                const el = itemEls[i];
                const t = el.textContent.trim().slice(0, 30);
                if (!t || items.find(x => x.text === t)) continue;
                items.push({
                    text: t,
                    tag: el.tagName,
                    cls: (el.className || '').toString().slice(0, 60),
                    hasInput: !!el.querySelector('input'),
                    inputType: el.querySelector('input')?.type
                });
            }
            out.push({title, items});
        }
        return out;
    }""")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])

    # 也抓取"裁判日期"那一组的完整结构（之前可能因为有空格匹配问题没找到）
    print("\n===裁判日期 区域单独查看===")
    date_area = page.evaluate("""() => {
        // 找包含 "裁判日期" 的最近祖先
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.children.length === 0 && el.textContent.trim() === '裁判日期') {
                // 找到组容器（往上一层）
                let container = el.parentElement;
                for (let i = 0; i < 3; i++) container = container?.parentElement;
                if (!container) continue;
                // 抓这个容器的子项
                const items = container.querySelectorAll('.wk-tree-node-content, .filter-item, a, label, div');
                const out = [];
                items.forEach(it => {
                    const t = it.textContent.trim();
                    if (t && t.length < 20 && !out.find(x => x.text === t)) {
                        out.push({
                            text: t,
                            tag: it.tagName,
                            cls: (it.className || '').toString().slice(0, 50),
                            outerHTML: it.outerHTML.slice(0, 300)
                        });
                    }
                });
                return out.slice(0, 10);
            }
        }
        return [];
    }""")
    print(json.dumps(date_area, ensure_ascii=False, indent=2)[:3000])

    browser.close()