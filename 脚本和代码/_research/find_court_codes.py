# -*- coding: utf-8 -*-
"""v12：找出主要省份的法院编码 + 案由顶级层次"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r"D:\ai/Claudecode/威科案例检索和下载-20260716/脚本和代码")
from wkinfo_api import WkinfoClient

client = WkinfoClient()
BASE = client.doc_count(query_string="合同")


def test_court(code, name):
    fq = f"+court:(({code}{name}))"
    try:
        c = client.doc_count(query_string="合同", filter_queries=[fq])
        return c
    except:
        return -1


def test_cause(code, name):
    fq = f"+causeOfAction:(({code}{name}))"
    try:
        c = client.doc_count(query_string="合同", filter_queries=[fq])
        return c
    except:
        return -1


# 1. 主要省份法院编码 - 测试前10个候选
print("=== 主要省份法院编码扫描 ===")
for province, candidates in [
    ("上海", ["003100000", "005000000", "031000000", "031100000"]),
    ("广东", ["003200000", "005100000", "022000000", "051000000"]),
    ("江苏", ["003300000", "005200000", "013000000", "032000000"]),
    ("浙江", ["003400000", "005300000", "014000000"]),
    ("四川", ["003700000", "005500000", "025000000"]),
]:
    print(f"\n[{province}]:")
    for code in candidates:
        c = test_court(code, province)
        marker = "✓" if 0 < c < BASE else "✗"
        print(f"  {marker} {code} → {c:,}")

# 2. 案由 - 顶级 民事/刑事/行政 测试
print("\n\n=== 案由顶级（民事/刑事/行政等）===")
for code, name in [
    ("01000000000000", "民事"),
    ("02000000000000", "刑事"),
    ("03000000000000", "行政"),
    ("04000000000000", "国家赔偿"),
    ("05000000000000", "执行"),
]:
    c = test_cause(code, name)
    print(f"  causeOfAction {code}{name}: {c:,}")

# 3. 案由 - 物权纠纷不同形式
print("\n=== 案由 - 物权纠纷不同形式 ===")
for fq in [
    "+causeOfAction:((01030000000000物权纠纷))",  # 已知是0
    "+causeOfAction:((01030000000000))",            # 不带中文
    "+causeOfAction:((01030000物权纠纷))",         # 短码
    "+causeOfAction:((01000000000000民事/01030000000000物权纠纷))",  # 已知OK
]:
    try:
        c = client.doc_count(query_string="合同", filter_queries=[fq])
        print(f"  {fq}: {c:,}")
    except Exception as e:
        print(f"  {fq}: ERR {e}")