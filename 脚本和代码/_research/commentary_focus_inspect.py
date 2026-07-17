# -*- coding: utf-8 -*-
"""调研 commentary + focus 库：sidebar 结构 + 实际 API 请求"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\commentary_focus_initial.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

LIBRARIES_TO_INSPECT = [
    ("commentary", "https://law.wkinfo.com.cn/commentary/list"),
    ("focus", "https://law.wkinfo.com.cn/focus/list"),
]


def clean_tabs(ctx):
    for p in ctx.pages[:]:
        if 'wkinfo.com.cn' not in p.url:
            p.close()
    seen = set()
    for p in ctx.pages[:]:
        if p.url.split('?')[0] in seen:
            p.close()
        else:
            seen.add(p.url.split('?')[0])


def main():
    results = {}
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = b.contexts[0]
        clean_tabs(ctx)
        page = ctx.pages[0]
        page.set_viewport_size({'width': 1920, 'height': 1080})

        for lib_key, url in LIBRARIES_TO_INSPECT:
            print(f'\n=== {lib_key}: {url} ===')
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(8000)

            # 抓 sidebar 标签
            labels = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                    .filter(l => l.offsetParent !== null)
                    .map(l => l.textContent.trim().slice(0, 30));
            }""")
            print(f'侧边栏 ({len(labels)} 个):')
            for l in labels[:30]:
                print(f'  {l}')

            # 抓真实 API 请求
            api_calls = []
            def on_request(req):
                if '/csi/search' in req.url and 'doc-count' not in req.url and req.post_data:
                    try:
                        body = json.loads(req.post_data)
                        api_calls.append({'url': req.url, 'body': body})
                    except:
                        pass
            page.on('request', on_request)

            # 搜索关键词
            page.fill('input[name="keyword"]', '建设工程')
            page.wait_for_timeout(500)
            page.keyboard.press('Enter')
            page.wait_for_timeout(8000)

            # 抓到的实际 API
            if api_calls:
                print(f'\\n实际 API ({len(api_calls)} 个):')
                for api in api_calls[-2:]:  # 取最后 2 个
                    print(f'  URL: {api["url"][:80]}')
                    body = api['body']
                    print(f'  indexId: {body.get("indexId")}')
                    qs = body.get('query', {}).get('queryString', '')
                    print(f'  queryString: {qs[:80]}')
                    fqs = body.get('query', {}).get('filterQueries', [])
                    print(f'  filterQueries: {fqs}')
                    sort = body.get('sortOrderList', [])
                    print(f'  sortOrderList: {sort}')

            results[lib_key] = {
                'url': url,
                'sidebar_labels': labels,
                'api_calls': api_calls,
            }
            page.remove_listener("request", on_request)
            clean_tabs(ctx)

        b.close()

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n结果: {OUT_FILE}')


if __name__ == "__main__":
    main()
