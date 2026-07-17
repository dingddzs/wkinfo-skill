# -*- coding: utf-8 -*-
"""V7 final: 先展开所有"查看更多"，再逐个点击抓取所有省份"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\province_codes_v7.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# 所有要抓的法院（最高法 + 各省 + 特别区）
COURT_TARGETS = [
    "最高人民法院",
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
    "新疆生产建设兵团", "铁路法院", "海事法院", "军事法院",
]


def reset_page(page):
    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)


def expand_all(page):
    """点所有 li.more 展开"""
    page.evaluate("""() => {
        document.querySelectorAll('li.more').forEach(m => m.click());
    }""")
    page.wait_for_timeout(3000)


def parse_court_fq(url: str) -> str:
    """从 URL 提取 court 字段的 value"""
    qs = parse_qs(urlparse(url).query)
    for fq in qs.get('fq', []):
        if not fq.startswith('court'):
            continue
        rest = fq[len('court'):]
        sep2_idx = rest.rfind('ǂ')
        if sep2_idx == -1:
            value = rest.strip('ǁ')
        else:
            value = rest[:sep2_idx].strip('ǁ')
        return value
    return None


def click_and_capture(page, label_text: str) -> str:
    """点击标签，提取 court code"""
    # 检查目标 y 位置
    target_y = page.evaluate(f"""() => {{
        const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
            .find(l => l.textContent.trim() === {label_text!r});
        return t ? t.getBoundingClientRect().top : null;
    }}""")

    if target_y is None:
        return None

    # 滚到视口内（y=300 左右）
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
        loc = page.locator(f'a.wk-tree-node-label').filter(has_text=label_text).first
        loc.click(timeout=5000)
        page.wait_for_timeout(2500)
        return parse_court_fq(page.url)
    except Exception as e:
        return None


def main():
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})

        # 处理每个目标（每次都 reset_page + expand，确保 URL 是干净的）
        for target in COURT_TARGETS:
            print(f"\n[{target}]", flush=True)
            reset_page(page)
            page.fill('input[name="keyword"]', '合同')
            page.wait_for_timeout(500)
            page.keyboard.press('Enter')
            page.wait_for_timeout(15000)
            expand_all(page)

            code = click_and_capture(page, target)
            if code:
                print(f"  ✓ {code}")
                results[target] = code
            else:
                print(f"  ✗ 失败")

        browser.close()

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"成功: {len(results)} / {len(COURT_TARGETS)}")
    print(f"结果: {OUT_FILE}")


if __name__ == "__main__":
    main()