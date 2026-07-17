# -*- coding: utf-8 -*-
"""v9：API 穷举测试每个维度的字段名+编码（纯 API，不需要浏览器）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
from pathlib import Path
sys.path.insert(0, r"D:\ai\Claudecode\威科案例检索和下载-20260716\脚本和代码")
from wkinfo_api import WkinfoClient

OUT_FILE = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\调试\api_field_discovery.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

client = WkinfoClient()
BASE_QUERY = "合同"  # 通用关键词

# (字段名, 候选值, 描述) — 测试每个维度的可能字段名
TESTS = {
    "审级/审判程序": [
        ("instance", "001", "instance 3位 一审"),
        ("instance", "002", "instance 3位 二审"),
        ("instance", "003", "instance 3位 再审"),
        ("instance", "01", "instance 2位"),
        ("instanceCode", "001", "instanceCode 一审"),
        ("trialProcedure", "001", "trialProcedure 一审"),
        ("procedure", "001", "procedure 一审"),
    ],
    "裁判日期(judgmentDate)": [
        ("judgmentDate", "[2024 TO 2026]", "Lucene 范围"),
        ("judgmentDate", "[2024-01-01 TO 2026-12-31]", "ISO 范围"),
        ("judgmentdatestr", "[2024 TO 2026]", "小写str"),
        ("judgmentDate", "2024", "单值"),
        ("judgmentDate", "[2024-01-01 TO *]", "开口"),
    ],
    "裁判日期(filterDates字段)": [
        # filterDates 是单独的字段，不是 filterQueries
    ],
    "审理法院(URL已知: court)": [
        ("court", "最高人民法院", "URL字段 court"),
        ("court", "北京市", "URL字段 court"),
        ("courtText", "最高人民法院", "courtText"),
    ],
    "案由(URL已知: causeOfAction)": [
        ("causeOfAction", "民事", "URL字段"),
        ("caseCause", "民事", "caseCause"),
        ("caseCauseText", "民事", "caseCauseText"),
    ],
    "地域": [
        ("region", "北京", "region"),
        ("territory", "北京", "territory"),
        ("province", "北京", "province"),
    ],
    "行业": [
        ("industry", "金融业", "industry"),
        ("industryText", "金融业", "industryText"),
    ],
    "参照级别": [
        ("referenceLevelNew", "01", "最高法指导性案例"),
        ("referenceLevel", "01", "referenceLevel"),
    ],
    "文书类型(URL已知: typeOfDecision)": [
        ("typeOfDecision", "判决书", "URL字段"),
        ("typeOfDecisionCode", "001", "code 3位"),
    ],
    "法院级别(URL已知: courtLevel)": [
        ("courtLevel", "1", "URL字段"),
    ],
}


def test_field(field: str, value: str) -> int:
    fq = f"+{field}:(({value}))"
    try:
        return client.doc_count(query_string=BASE_QUERY, filter_queries=[fq])
    except Exception as e:
        return -1


def main():
    base_count = client.doc_count(query_string=BASE_QUERY)
    print(f"基准 '{BASE_QUERY}': {base_count:,}")
    print("=" * 80)

    results = {"base_count": base_count}

    for dim, tests in TESTS.items():
        print(f"\n=== {dim} ===")
        results[dim] = {}

        for field, value, desc in tests:
            count = test_field(field, value)
            # 有效 = count > 0 AND count < base_count
            effective = 0 < count < base_count
            results[dim][f"{field}:{value}"] = {
                "desc": desc, "count": count, "effective": effective
            }
            marker = "✓" if effective else ("✗0" if count == 0 else f"✗{count}")
            print(f"  {marker:6s} {field}:(({value})) [{desc}]")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果: {OUT_FILE}")


if __name__ == "__main__":
    main()