# -*- coding: utf-8 -*-
"""Phase 1 v3: 点击每个库按钮，捕获目标 URL"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\homepage_buttons_v3.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# 候选按钮文字（从首页截图可见）
BUTTON_TEXTS = ["法律法规", "案例评析", "案例", "资讯", "文书", "行政处罚", "监管", "法规速递", "裁判文书"]

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = b.contexts[0]

    # 关掉非 wkinfo 标签
    for p in ctx.pages[:]:
        if 'wkinfo.com.cn' not in p.url:
            p.close()

    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})
    page.goto('https://law.wkinfo.com.cn/', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 找按钮的实际 DOM 结构
    structure = page.evaluate("""() => {
        // 找所有可点击元素（含 Angular 组件）
        const all = document.querySelectorAll('a, button, [role=button], [ng-click], [click], div[class*=entry], div[class*=button]');
        const out = [];
        all.forEach(el => {
            const text = el.textContent.trim().slice(0, 30);
            // 限制文字长度
            if (text && text.length <= 5 && text.length > 0) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    out.push({
                        text,
                        tag: el.tagName,
                        cls: (el.className || '').toString().slice(0, 60),
                        attrs: {
                            href: el.getAttribute('href') || '',
                            routerlink: el.getAttribute('routerlink') || el.getAttribute('ng-reflect-router-link') || '',
                            ngclick: el.getAttribute('ng-click') || '',
                        },
                        rect: {x: Math.round(rect.x), y: Math.round(rect.y)}
                    });
                }
            }
        });
        return out;
    }""")
    print(f'扫描到 {len(structure)} 个短文本可点击元素')
    for s in structure[:30]:
        if s['text'] in ['搜索', 'EN', '产品菜单', '退出', '推送', '帮助', '手机版', '反馈', '客服', '分享', 'APP', '模块介绍', '返回首页', '进入易读']:
            continue
        print(f'  {s["text"]:8s} | tag={s["tag"]:6s} | routerlink={s["attrs"]["routerlink"][:30]} | href={s["attrs"]["href"][:50]}')

    # 试着点击"法律法规"
    print('\n=== 点击"法律法规" ===')
    # 关闭已开的标签，单独开新标签观察 URL
    for p in ctx.pages[:]:
        if 'wkinfo.com.cn' in p.url and p.url != 'https://law.wkinfo.com.cn/':
            p.close()

    # 找按钮的 selector
    btn_handle = page.evaluate_handle("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.children.length === 0 && el.textContent.trim() === '法律法规') {
                return el.parentElement || el;
            }
        }
        return null;
    }""")
    btn = btn_handle.as_element()

    if btn:
        before_url = page.url
        # 用 evaluate 点击
        page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            for (const el of all) {
                if (el.children.length === 0 && el.textContent.trim() === '法律法规') {
                    el.click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(5000)
        after_url = page.url
        print(f'点击前: {before_url}')
        print(f'点击后: {after_url}')
    else:
        print('找不到"法律法规"按钮')

    # 截图
    page.screenshot(path=str(Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图\after-click-legislation.png")), full_page=False)

    # 尝试点击"案例评析"
    print('\n=== 点击"案例评析" ===')
    # 先回首页
    page.goto('https://law.wkinfo.com.cn/', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    clicked = page.evaluate("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.children.length === 0 && el.textContent.trim() === '案例评析') {
                el.click();
                return true;
            }
        }
        return false;
    }""")
    page.wait_for_timeout(5000)
    print(f'点击后: {page.url}')

    b.close()