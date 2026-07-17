# -*- coding: utf-8 -*-
"""V3: 边跑边存，Edge 挂了也不丢数据"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
import os
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\commentary_focus_filters.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
# 初始化空文件
if not OUT_FILE.exists():
    OUT_FILE.write_text("{}", encoding="utf-8")


def parse_fqs(url):
    qs = parse_qs(urlparse(url).query)
    parsed = []
    for fq in qs.get('fq', []):
        try:
            decoded = fq.encode('latin-1').decode('utf-8')
        except:
            decoded = unquote(fq)
        if 'ǁ' not in decoded:
            continue
        field, rest = decoded.split('ǁ', 1)
        sep2_idx = rest.rfind('ǂ')
        if sep2_idx == -1:
            value = rest.strip('ǁ')
            label = ''
        else:
            value = rest[:sep2_idx].strip('ǁ')
            label = rest[sep2_idx + 1:]
        parsed.append({"field": field, "value": value, "label": label})
    return parsed


def save_result(lib, dim, opt, result):
    """增量保存"""
    with open(OUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if lib not in data:
        data[lib] = {}
    if dim not in data[lib]:
        data[lib][dim] = {}
    data[lib][dim][opt] = result
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 极简测试
TESTS = [
    ("commentary", "https://law.wkinfo.com.cn/commentary/list", [
        ("英文", "语言"), ("财税", "专题"), ("金杜律师事务所", "律所"), ("2026年", "年份"),
    ]),
    ("focus", "https://law.wkinfo.com.cn/focus/list", [
        ("公司治理", "专题类型"), ("金杜律师事务所", "律所"), ("2026年", "年份"),
    ]),
]


def main():
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = b.contexts[0]
        for p in ctx.pages[:]:
            if 'wkinfo.com.cn' not in p.url:
                p.close()
        page = ctx.pages[0]
        page.set_viewport_size({'width': 1920, 'height': 1080})

        for lib_key, url, options in TESTS:
            for option, dimension in options:
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    page.wait_for_timeout(2000)
                    page.evaluate("document.querySelectorAll('li.more').forEach(m => m.click());")
                    page.wait_for_timeout(800)
                    page.fill('input[name="keyword"]', '公司')
                    page.wait_for_timeout(300)
                    page.keyboard.press('Enter')
                    page.wait_for_timeout(3000)

                    target_y = page.evaluate(f"""() => {{
                        const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                            .find(l => l.textContent.trim() === {option!r});
                        return t ? t.getBoundingClientRect().top : null;
                    }}""")

                    if target_y is None:
                        save_result(lib_key, dimension, option, {'error': 'not_in_dom'})
                        print(f"  ✗ {lib}/{dim}/{opt}: not in DOM")
                        continue

                    if target_y < 100 or target_y > 900:
                        page.evaluate(f"""() => {{
                            const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                                .find(l => l.textContent.trim() === {option!r});
                            if (t) {{
                                const rect = t.getBoundingClientRect();
                                window.scrollTo(0, window.scrollY + rect.top - 300);
                            }}
                        }}""")
                        page.wait_for_timeout(800)

                    loc = page.locator('a.wk-tree-node-label').filter(has_text=option).first
                    loc.click(timeout=5000)
                    page.wait_for_timeout(1500)
                    fqs = parse_fqs(page.url)
                    match = next((f for f in fqs if f['label'] == option), None)
                    if match:
                        save_result(lib_key, dimension, option, match)
                        print(f"  ✓ {lib_key}/{dimension}/{option}: {match['field']}:(({match['value']}))")
                    else:
                        save_result(lib_key, dimension, option, {'error': 'no_match', 'fqs': fqs})
                        print(f"  ✗ {lib_key}/{dimension}/{option}: no match")
                except Exception as e:
                    save_result(lib_key, dimension, option, {'error': str(e)[:80]})
                    print(f"  ✗ {lib_key}/{dimension}/{option}: ERR {str(e)[:60]}")

        try:
            b.close()
        except:
            pass

    print(f'\n已存: {OUT_FILE}')


if __name__ == "__main__":
    main()
