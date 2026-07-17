# -*- coding: utf-8 -*-
"""调试 v4：检查侧边栏复选框的真实状态"""
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

    # 1. 抓取侧边栏 "案由" 维度的所有 checkbox 状态
    print("===点击前===")
    before = page.evaluate("""() => {
        // 找 "案由" 分类下的所有 checkbox
        const groups = document.querySelectorAll('.wk-tree-node-content');
        const results = [];
        groups.forEach(g => {
            const t = g.textContent.trim();
            if (t.startsWith('民事') || t.startsWith('刑事') || t.startsWith('行政')) {
                const cb = g.querySelector('input[type=checkbox]');
                if (cb) {
                    results.push({
                        text: t.slice(0, 20),
                        checked: cb.checked,
                        ariaChecked: cb.getAttribute('aria-checked'),
                        parentClass: g.className.slice(0, 50)
                    });
                }
            }
        });
        return results;
    }""")
    for r in before[:10]:
        print(f"  {r}")

    # 2. 尝试不同点击方式
    print("\n===尝试点击 '民事' 的 checkbox===")
    click_attempts = [
        ("直接点击 input[type=checkbox]",
         """() => {
             const cb = document.querySelector('.wk-tree-node-content input[type=checkbox]');
             if (cb) { cb.click(); return {clicked: true, wasChecked: cb.checked}; }
             return {clicked: false};
         }"""),
        ("点击包含 '民事' 文本的元素",
         """() => {
             const els = document.querySelectorAll('.wk-tree-node-content *');
             for (const el of els) {
                 if (el.textContent.trim() === '民事' || (el.childNodes.length === 1 && el.childNodes[0].nodeValue === '民事')) {
                     const r = el.getBoundingClientRect();
                     if (r.width > 0 && r.height > 0) {
                         el.click();
                         return {clicked: true, tag: el.tagName, text: el.textContent.trim()};
                     }
                 }
             }
             return {clicked: false};
         }"""),
        ("点击 '民事' 的父节点",
         """() => {
             const all = document.querySelectorAll('*');
             for (const el of all) {
                 if (el.children.length === 0 && el.textContent.trim() === '民事') {
                     el.parentElement.click();
                     return {clicked: true, parent: el.parentElement.tagName, parentClass: el.parentElement.className.slice(0,50)};
                 }
             }
             return {clicked: false};
         }"""),
    ]

    for desc, js in click_attempts:
        result = page.evaluate(js)
        print(f"  {desc}: {result}")
        page.wait_for_timeout(1000)

        # 检查状态
        after = page.evaluate("""() => {
            const cb = document.querySelector('.wk-tree-node-content input[type=checkbox]');
            return cb ? {checked: cb.checked, ariaChecked: cb.getAttribute('aria-checked')} : null;
        }""")
        print(f"    状态: {after}")

    # 截图最终状态
    page.screenshot(path=r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\sidebar_inspect.png", full_page=False)

    browser.close()