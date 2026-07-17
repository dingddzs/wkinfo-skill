# -*- coding: utf-8 -*-
"""V6: 重跑剩余省份，每次都先 scroll + 用修好的 parser"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\province_codes_v6.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

PROVINCES = [
    # 已成功（前 9 个）
    # "北京市", "天津市", "上海市", "重庆市",
    # "河北省", "山西省", "内蒙古自治区",
    # "辽宁省", "吉林省",
    # 剩余
    "黑龙江省", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
]

# 已知的省份代码（从前一轮 v5 提取）
KNOWN = {
    "最高人民法院": "001000000",
    "北京市": "003000000",
    "天津市": "028000000",
    "上海市": "024000000",
    "重庆市": "004000000",
    "河北省": "011000000",
    "山西省": "025000000",
    "内蒙古自治区": "016000000",
    "辽宁省": "020000000",
    "吉林省": "019000000",
    "黑龙江省": "012000000",  # 之前用户给的
}


def reset_page(page):
    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)


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


def main():
    results = dict(KNOWN)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})

        for province in PROVINCES:
            if province in KNOWN and KNOWN[province] != "012000000":
                # 跳过已知的（黑龙江已存但前面报 not_in_dom，重新尝试）
                pass

            print(f"\n[{province}]", flush=True)
            reset_page(page)
            page.fill('input[name="keyword"]', '合同')
            page.wait_for_timeout(500)
            page.keyboard.press('Enter')
            page.wait_for_timeout(15000)

            # 检查目标是否在 DOM
            target_y = page.evaluate(f"""() => {{
                const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                    .find(l => l.textContent.trim() === {province!r});
                return t ? t.getBoundingClientRect().top : null;
            }}""")

            if target_y is None:
                # 滚动页面（mouse.wheel 真实事件）
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(2000)
                target_y = page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {province!r});
                    return t ? t.getBoundingClientRect().top : null;
                }}""")

            if target_y is None:
                # 再滚
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(2000)
                target_y = page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {province!r});
                    return t ? t.getBoundingClientRect().top : null;
                }}""")

            if target_y is None:
                print(f"  ✗ DOM 中找不到")
                results[province] = results.get(province) + '-fail' if province in results else 'fail'
                continue

            # 滚到目标位置
            if target_y > 1080 or target_y < 0:
                # window scrollTo 让目标到 y=300
                page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {province!r});
                    if (t) {{
                        const rect = t.getBoundingClientRect();
                        window.scrollTo(0, window.scrollY + rect.top - 300);
                    }}
                }}""")
                page.wait_for_timeout(1500)

            # 点击
            try:
                loc = page.locator(f'a.wk-tree-node-label').filter(has_text=province).first
                loc.click(timeout=5000)
                page.wait_for_timeout(2500)

                # 提取
                code = parse_court_fq(page.url)
                if code:
                    print(f"  ✓ {code}")
                    results[province] = code
                else:
                    print(f"  ✗ URL 中无 court fq: {page.url[:150]}")
            except Exception as e:
                print(f"  ✗ 点击失败: {str(e)[:80]}")
                results[province] = results.get(province, 'fail')

        browser.close()

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success = sum(1 for v in results.values() if v not in ('fail',) and '-fail' not in str(v))
    print(f"\n{'='*60}\n成功: {success}\n结果: {OUT_FILE}")


if __name__ == "__main__":
    main()