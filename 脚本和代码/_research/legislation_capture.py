# -*- coding: utf-8 -*-
"""Phase 2: 批量抓法律法规库的侧边栏过滤器 URL fq"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\legislation_filters.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# 重要过滤器（按维度抽样）
FILTERS_TO_TEST = {
    "法律层级": ["法律", "行政法规", "司法解释", "部门规章", "地方法规", "国际条约", "国家标准"],
    "地域": ["全国", "北京市", "上海市", "广东省"],
    "发布日期": ["最近1个月", "最近1年", "5年以前"],
    "效力状态": ["现行有效", "失效/废止", "尚未生效", "草案/征求意见稿"],
    "发布机关": ["国务院", "最高人民法院", "公安部", "财政部"],
}


def reset_page(page):
    page.goto('https://law.wkinfo.com.cn/legislation/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)
    page.fill('input[name="keyword"]', '公司法')
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)
    # 展开所有"查看更多"
    page.evaluate("document.querySelectorAll('li.more').forEach(m => m.click());")
    page.wait_for_timeout(3000)


def parse_fqs(url: str) -> list:
    """解析 URL 中所有 fq 参数"""
    qs = parse_qs(urlparse(url).query)
    fqs_raw = qs.get('fq', [])
    parsed_fqs = []
    for fq in fqs_raw:
        try:
            decoded = fq.encode('latin-1').decode('utf-8')
        except:
            decoded = unquote(fq)
        # 格式: fieldǁvalueǁǂlabel (value 可能含 ǁ)
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
        parsed_fqs.append({"field": field, "value": value, "label": label})
    return parsed_fqs


def click_and_capture(page, label_text: str) -> str:
    """点击标签，返回 URL"""
    # 检查目标 y
    target_y = page.evaluate(f"""() => {{
        const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .find(l => l.textContent.trim() === {label_text!r});
        return t ? t.getBoundingClientRect().top : null;
    }}""")
    if target_y is None:
        return None

    if target_y < 100 or target_y > 900:
        page.evaluate(f"""() => {{
            const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                .find(l => l.textContent.trim() === {label_text!r});
            if (t) {{
                const rect = t.getBoundingClientRect();
                window.scrollTo(0, window.scrollY + rect.top - 300);
            }}
        }}""")
        page.wait_for_timeout(1500)

    try:
        loc = page.locator('a.wk-tree-node-label').filter(has_text=label_text).first
        loc.click(timeout=5000)
        page.wait_for_timeout(2500)
        return page.url
    except Exception:
        return None


def main():
    results = {}
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = b.contexts[0]

        # 清理标签
        for p in ctx.pages[:]:
            if 'wkinfo.com.cn' not in p.url:
                p.close()
        seen = set()
        for p in ctx.pages[:]:
            if 'judgment-documents' in p.url:
                p.close()
            elif p.url in seen:
                p.close()
            else:
                seen.add(p.url)

        page = ctx.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})

        for dimension, options in FILTERS_TO_TEST.items():
            print(f'\n=== {dimension} ===')
            results[dimension] = {}
            for option in options:
                reset_page(page)
                url_after = click_and_capture(page, option)

                if url_after:
                    fqs = parse_fqs(url_after)
                    # 找该维度的 fq（最后一个，或者匹配 dimension 的）
                    relevant_fq = None
                    for fq in fqs:
                        if fq['label'] == option:
                            relevant_fq = fq
                            break
                    if relevant_fq:
                        print(f'  ✓ {option:20s} → {relevant_fq["field"]}:(({relevant_fq["value"]}))')
                        results[dimension][option] = relevant_fq
                    else:
                        print(f'  ✗ {option:20s} → URL 无匹配 fq: {fqs}')
                        results[dimension][option] = {'error': 'no_match', 'url': url_after}
                else:
                    print(f'  ✗ {option:20s} → 点击失败')
                    results[dimension][option] = {'error': 'click_failed'}

        b.close()

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n结果: {OUT_FILE}')


if __name__ == "__main__":
    main()