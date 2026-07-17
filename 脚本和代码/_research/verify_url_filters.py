# -*- coding: utf-8 -*-
"""v10：基于用户提供的 URL，提取字段名+编码，直接 API 验证"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sys as _sys
_sys.path.insert(0, r"D:\ai\Claudecode\威科案例检索和下载-20260716\脚本和代码")
from wkinfo_api import WkinfoClient

client = WkinfoClient()
BASE = client.doc_count(query_string="合同")
print(f"基准 '合同': {BASE:,}")
print("=" * 80)

# (filter_query, 描述)
TESTS = [
    # 裁判日期 - judgmentYear
    ("+judgmentYear:([2024 TO 2025])", "2024年整年"),
    ("+judgmentYear:([2023 TO 2024])", "2023年整年"),
    ("+judgmentYear:([2024.07.16 TO 2026.07.17])", "近三年（用日期范围）"),
    ("+judgmentYear:([* TO 2022])", "2022年之前"),
    ("+judgmentYear:([2023 TO *])", "2023年以后"),

    # 审级 - instance
    ("+instance:((001))", "一审"),
    ("+instance:((002))", "二审"),
    ("+instance:((003))", "再审"),

    # 文书类型 - typeOfDecision
    ("+typeOfDecision:((001))", "判决书"),
    ("+typeOfDecision:((002))", "裁定书"),

    # 法院 - court
    ("+court:((003000000北京市))", "北京市"),
    ("+court:((最高人民法院))", "最高人民法院（之前已确认）"),
    ("+courtText:((最高人民法院))", "courtText 写法"),

    # 案由 - causeOfAction
    ("+causeOfAction:((01000000000000民事))", "民事"),
    ("+causeOfAction:((01030000000000物权纠纷))", "物权纠纷"),
    ("+causeOfAction:((01000000000000民事/01030000000000物权纠纷))", "民事/物权纠纷"),

    # 参照级别 - referenceLevelNew
    ("+referenceLevelNew:((08))", "最高法指导性案例(08)"),
    ("+referenceLevelNew:((09))", "最高检指导性案例(09)"),
    ("+referenceLevelNew:((11))", "公报案例"),
    ("+referenceLevelNew:((06))", "官方典型案例"),

    # 行业 - industryCode
    ("+industryCode:((J))", "金融业"),
    ("+industryCode:((K))", "建筑业"),
    ("+industryCode:((L))", "房地产业"),

    # 法院级别 - courtLevel
    ("+courtLevel:((1))", "最高人民法院"),
    ("+courtLevel:((4))", "基层法院"),
]

print(f"\n{'描述':40s} {'filter':50s} {'命中':>12s} {'生效':>4s}")
print("-" * 110)
for fq, desc in TESTS:
    try:
        c = client.doc_count(query_string="合同", filter_queries=[fq])
        effective = "✓" if 0 < c < BASE else "✗"
        print(f"{desc:40s} {fq:50s} {c:>12,} {effective:>4s}")
    except Exception as e:
        print(f"{desc:40s} {fq:50s} {'ERR':>12s}")