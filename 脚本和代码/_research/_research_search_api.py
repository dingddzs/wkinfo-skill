# -*- coding: utf-8 -*-
"""调研：搜索 API"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
import requests
from pathlib import Path
from urllib.parse import quote

COOKIE_FILE = Path.home() / ".claude/skills/wkinfo-cli/storage/wkinfo-cookies.json"

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)

cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
uid = "1000250387"
identification = "_79cfe8d062d911f1b542513c0fcf6872"

# 监听搜索时的网络请求
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.set_viewport_size({'width': 1920, 'height': 1080})

    search_apis = []
    page.on("request", lambda req: (
        search_apis.append({"method": req.method, "url": req.url,
                            "headers": dict(req.headers), "post": req.post_data})
        if any(x in req.url for x in ['/search', '/list', '/api/judgment', '/api/case'])
        and '/api/download' not in req.url
        and '/csi/document' not in req.url
        else None
    ))

    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)

    # 用 evaluate 设置关键词 + 按 Enter
    page.evaluate("""() => {
        const input = document.querySelector('input[name="keyword"]');
        input.focus();
        input.value = '建设工程施工合同';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)

    print('===搜索相关 API 调用===')
    for api in search_apis[:30]:
        print(f'\n>>> {api["method"]} {api["url"][:200]}')
        if api.get('post'):
            try:
                post_json = json.loads(api['post'])
                print(f'POST (JSON):\n{json.dumps(post_json, ensure_ascii=False, indent=2)[:800]}')
            except:
                print(f'POST (raw): {api["post"][:500]}')

    # 抓 URL（含 searchId 等参数）
    print(f'\n===页面 URL===\n{page.url[:500]}')

    browser.close()