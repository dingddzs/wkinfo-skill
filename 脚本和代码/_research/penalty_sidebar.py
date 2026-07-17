# -*- coding: utf-8 -*-
"""行政处罚库 sidebar + API 反推 (单页 goto 版本)"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\截图")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\penalty_filters.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

FILTERS_TO_TEST = {
    "处罚类型": ["罚款", "警告", "责令停产停业"],
    "行业领域": ["金融业", "建筑业"],
    "地域": ["全国", "北京市"],
    "处罚日期": ["最近1个月", "最近1年", "5年以前"],
    "处罚机关": ["国家市场监督管理总局", "证监会"],
}


def parse_fqs(url):
    qs = parse_qs(urlparse(url).query)
    fqs_raw = qs.get('fq', [])
    parsed = []
    for fq in fqs_raw:
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


def main():
    results = {}
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = b.contexts[0]
        # 不关任何标签

        # 用首页标签做跳转（避免新建）
        page = ctx.pages[0]
        page.set_viewport_size({'width': 1920, 'height': 1080})

        # 先看 sidebar 结构
        page.goto('https://law.wkinfo.com.cn/administrative-punishment/list',
                  wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(15000)
        page.evaluate("document.querySelectorAll('li.more').forEach(m => m.click());")
        page.wait_for_timeout(3000)

        structure = page.evaluate("""() => {
            const labels = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                .filter(l => l.offsetParent !== null)
                .map(l => l.textContent.trim().slice(0, 25));
            return {labels: labels.slice(0, 60), total: labels.length};
        }""")
        print(f'行政处罚侧边栏 ({structure["total"]} label):')
        for l in structure['labels']:
            print(f'  {l}')

        # 截图
        page.screenshot(path=str(OUT_DIR / 'penalty-list.png'), full_page=False)

        # 测试过滤器
        for dimension, options in FILTERS_TO_TEST.items():
            print(f'\n=== {dimension} ===')
            results[dimension] = {}
            for option in options:
                page.goto('https://law.wkinfo.com.cn/administrative-punishment/list',
                          wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(15000)
                page.evaluate("document.querySelectorAll('li.more').forEach(m => m.click());")
                page.wait_for_timeout(3000)
                page.fill('input[name="keyword"]', '处罚')
                page.wait_for_timeout(500)
                page.keyboard.press('Enter')
                page.wait_for_timeout(15000)

                # 找目标
                target_y = page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {option!r});
                    return t ? t.getBoundingClientRect().top : null;
                }}""")
                if target_y is None:
                    print(f'  ✗ {option:20s} → 不在 DOM')
                    results[dimension][option] = {'error': 'not_in_dom'}
                    continue

                # 滚到视口内
                page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {option!r});
                    if (t) {{
                        const rect = t.getBoundingClientRect();
                        window.scrollTo(0, window.scrollY + rect.top - 300);
                    }}
                }}""")
                page.wait_for_timeout(1500)

                try:
                    loc = page.locator('a.wk-tree-node-label').filter(has_text=option).first
                    loc.click(timeout=5000)
                    page.wait_for_timeout(2500)
                    url_after = page.url
                    fqs = parse_fqs(url_after)
                    match = next((f for f in fqs if f['label'] == option), None)
                    if match:
                        print(f'  ✓ {option:20s} → {match["field"]}:(({match["value"]}))')
                        results[dimension][option] = match
                    else:
                        print(f'  ✗ {option:20s} → URL 无匹配')
                        results[dimension][option] = {'error': 'no_match'}
                except Exception as e:
                    print(f'  ✗ {option:20s} → {str(e)[:50]}')
                    results[dimension][option] = {'error': 'click_failed'}

        b.close()

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n结果: {OUT_FILE}')


if __name__ == "__main__":
    main()