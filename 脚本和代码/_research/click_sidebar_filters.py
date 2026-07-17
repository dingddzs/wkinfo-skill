# -*- coding: utf-8 -*-
"""v8：用 evaluate click + 同时抓 URL 和 API body"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# URL 解析 - separator is U+0181 (Ɓ)
SEP1 = "Ɓ"  # Ɓ = \xC7\x81
SEP2 = "Ƃ"  # Ƃ = \xC7\x82


def reset_and_setup(page, keyword: str = "合同"):
    page.goto('https://law.wkinfo.com.cn/judgment-documents/list',
              wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(10000)
    page.fill('input[name="keyword"]', keyword)
    page.wait_for_timeout(500)
    page.keyboard.press('Enter')
    page.wait_for_timeout(15000)


def click_label_eval(page, text: str) -> dict:
    """evaluate-based click — 之前 v6 用这个对部分 label 有效"""
    return page.evaluate("""(targetText) => {
        const labels = document.querySelectorAll('a.wk-tree-node-label');
        for (const l of labels) {
            const t = l.textContent.trim();
            if (t === targetText || t.startsWith(targetText + ' ')) {
                const r = l.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    l.click();
                    return {clicked: true, text: t};
                }
            }
        }
        return {clicked: false};
    }""", text)


def parse_url_fqs(url: str) -> list:
    """从 URL fq 参数解析"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    fqs = qs.get("fq", [])
    parsed_fqs = []
    for fq in fqs:
        try:
            decoded = fq.encode('latin-1').decode('utf-8')
        except:
            decoded = unquote(fq)
        # Split by SEP1
        parts = decoded.split(SEP1)
        if len(parts) >= 2:
            field = parts[0]
            rest = SEP1.join(parts[1:])
            # Find SEP2 to get value/label
            sep2_idx = rest.find(SEP2)
            if sep2_idx >= 0:
                value = rest[:sep2_idx]
                label = rest[sep2_idx + 1:]
            else:
                value = rest
                label = ""
            parsed_fqs.append({"field": field, "value": value.strip(), "label": label.strip()})
    return parsed_fqs


def test_dimension(page, dimension: str, options: list, results: dict):
    print(f"\n{'='*60}\n维度: {dimension}\n{'='*60}")
    results[dimension] = {}

    for option in options:
        print(f"\n  [{option}]", flush=True)
        reset_and_setup(page)

        # 监听 API 请求
        api_bodies = []
        def on_request(req):
            if '/csi/search' in req.url and 'doc-count' not in req.url:
                try:
                    api_bodies.append({"url": req.url, "body": json.loads(req.post_data) if req.post_data else None})
                except:
                    pass
        page.on("request", on_request)

        # 点击
        click_result = click_label_eval(page, option)
        page.wait_for_timeout(3000)  # 等 URL 更新和 API

        page.remove_listener("request", on_request)

        url_after = page.url
        url_fqs = parse_url_fqs(url_after)
        api_fqs = []
        api_dates = []
        for ab in api_bodies:
            if ab.get("body"):
                api_fqs.extend(ab["body"].get("query", {}).get("filterQueries", []))
                api_dates.extend(ab["body"].get("query", {}).get("filterDates", []))

        # 输出
        print(f"    click: {click_result}")
        print(f"    URL fqs ({len(url_fqs)}): {[f['field'] + ':' + f['value'] for f in url_fqs]}")
        print(f"    API fqs: {api_fqs}")
        if api_dates: print(f"    API dates: {api_dates}")

        # 存有用的（URL 变化或 API 变化）
        if url_fqs or any(f != "-typeOfDecision:((008))" for f in api_fqs) or api_dates:
            results[dimension][option] = {
                "url_fqs": url_fqs,
                "api_fqs": api_fqs,
                "api_dates": api_dates,
                "source": "url" if url_fqs else "api"
            }
        else:
            results[dimension][option] = {"error": "no_change"}


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp('http://localhost:9222')
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.set_viewport_size({'width': 1920, 'height': 1080})

        results = {}

        tests = {
            "法院级别": ["最高人民法院", "高级人民法院", "中级人民法院", "基层人民法院", "专门法院"],
            "参照级别": ["最高法指导性案例", "公报案例", "入库案例", "官方典型案例"],
            "行业": ["金融业", "建筑业", "房地产业", "制造业"],
            "审理法院": ["最高人民法院", "北京市", "上海市", "广东省"],
            "案由": ["民事", "刑事", "行政", "国家赔偿"],
            "审判程序": ["一审", "二审", "再审", "破产"],
            "裁判日期": ["最近1年", "最近3年", "最近5年", "2026年", "2025年", "2024年"],
            "文书类型": ["判决书", "裁定书", "调解书", "决定书", "通知书"],
            "文书公开程度": ["全文公开", "非全文公开"],
            "文书篇幅": ["500字以上", "500字以下（含500字）"],
            "标的额": ["50万元以上", "50万元以下（含50万元）"],
        }

        for dim, opts in tests.items():
            test_dimension(page, dim, opts, results)

        browser.close()

    out_file = OUT_DIR / "url_filter_syntax_v8.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n完成: {out_file}")


if __name__ == "__main__":
    main()