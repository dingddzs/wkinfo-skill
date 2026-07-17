# -*- coding: utf-8 -*-
"""V5: 用 page.mouse.wheel 真实滚动 + click"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\province_codes_v5.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

PROVINCES = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
]


def reset_page(page):
    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)


def parse_fqs(url: str) -> list:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    fqs_raw = qs.get("fq", [])
    parsed_fqs = []
    for fq in fqs_raw:
        try:
            decoded = fq.encode('latin-1').decode('utf-8')
        except:
            decoded = unquote(fq)
        parts = decoded.split("Ɓ")
        if len(parts) >= 2:
            field = parts[0]
            rest = "Ɓ".join(parts[1:])
            sep2_idx = rest.find("Ƃ")
            value = rest[:sep2_idx] if sep2_idx >= 0 else rest
            label = rest[sep2_idx + 1:] if sep2_idx >= 0 else ""
            parsed_fqs.append({"field": field, "value": value.strip(), "label": label.strip()})
    return parsed_fqs


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})

        results = {}
        for province in PROVINCES:
            print(f"\n[{province}]", flush=True)
            reset_page(page)
            page.fill('input[name="keyword"]', '合同')
            page.wait_for_timeout(500)
            page.keyboard.press('Enter')
            page.wait_for_timeout(15000)

            # 策略 1: 检查目标是否已在视口内
            target_y = page.evaluate(f"""() => {{
                const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                    .find(l => l.textContent.trim() === {province!r});
                return t ? t.getBoundingClientRect().top : null;
            }}""")

            if target_y is None:
                # 找不到目标 — 可能在 DOM 但还没渲染？等一下再找
                page.wait_for_timeout(2000)
                target_y = page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {province!r});
                    return t ? t.getBoundingClientRect().top : null;
                }}""")

            if target_y is None:
                print(f"  ✗ DOM 中找不到")
                results[province] = {'error': 'not_in_dom'}
                continue

            # 策略 2: 如果目标在视口外，用 mouse.wheel 滚动
            if target_y > 1080 or target_y < 0:
                # 滚到目标位置（留 200px 余量在顶部）
                scroll_to = page.evaluate(f"""() => {{
                    const t = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
                        .find(l => l.textContent.trim() === {province!r});
                    if (!t) return 0;
                    const rect = t.getBoundingClientRect();
                    return window.scrollY + rect.top - 200;
                }}""")
                # 用 mouse.wheel（更可靠）
                current_y = page.evaluate("window.scrollY")
                delta = scroll_to - current_y
                page.mouse.wheel(0, delta)
                page.wait_for_timeout(1500)

            # 点击
            try:
                loc = page.locator(f'a.wk-tree-node-label').filter(has_text=province).first
                loc.click(timeout=5000)
                page.wait_for_timeout(2500)
            except Exception as e:
                print(f"  ✗ 点击失败: {str(e)[:60]}")
                results[province] = {'error': str(e)[:100]}
                continue

            # 提取
            fqs = parse_fqs(page.url)
            court_fq = next((f for f in fqs if f['field'] == 'court'), None)
            if court_fq:
                print(f"  ✓ {court_fq['value']} ({court_fq['label']})")
                results[province] = {'code': court_fq['value']}
            else:
                print(f"  ✗ URL 中无 court fq")
                results[province] = {'error': 'no_court_fq', 'url': page.url[:200]}

        browser.close()

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success = sum(1 for v in results.values() if 'code' in v)
    failed = sum(1 for v in results.values() if 'error' in v)
    print(f"\n{'='*60}\n成功: {success}, 失败: {failed}\n结果: {OUT_FILE}")


if __name__ == "__main__":
    main()