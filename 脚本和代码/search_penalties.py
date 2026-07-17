# -*- coding: utf-8 -*-
"""行政处罚检索 CLI（薄壳）

用法：
  python search_penalties.py --query "上市公司" --mode few --target 3
  python search_penalties.py --query "市场监管" --topic 市场监管 --industry 金融业
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nl_parser import ParamParser, SearchParams
from wkinfo_api import WkinfoClient, parse_search_results, build_judgment_year_filter


def run_search(args) -> int:
    parser_obj = ParamParser()
    client = WkinfoClient()

    params = parser_obj.parse(args.query or "")

    if args.industry:
        params.industry = args.industry
    if args.topic:
        params.extra_keywords.append(args.topic)
    if args.jurisdiction:
        params.extra_keywords.append(args.jurisdiction)
    if args.year:
        params.year_from = args.year
        params.year_to = args.year
    if args.mode:
        params.mode = args.mode
    if args.target:
        params.target_count = args.target
    if args.max:
        params.max_count = args.max

    print("=" * 60)
    print("库: 行政处罚")
    print(f"查询: {params.query}")
    print(f"模式: {params.mode}")
    if params.industry:
        print(f"行业: {params.industry}")
    print("=" * 60)

    fqs = []
    from wkinfo_api import PENALTY_MAPS
    if params.industry and params.industry in PENALTY_MAPS.get("industryCode", {}):
        code = PENALTY_MAPS["industryCode"][params.industry]
        fqs.append(f"+industryCode:(({code}))")
    if "topicClassification" in PENALTY_MAPS:
        for kw in params.extra_keywords:
            if kw in PENALTY_MAPS["topicClassification"]:
                code = PENALTY_MAPS["topicClassification"][kw]
                fqs.append(f"+topicClassification:(({code}))")
                break
    if "jurisdiction" in PENALTY_MAPS:
        for kw in params.extra_keywords:
            if kw in PENALTY_MAPS["jurisdiction"]:
                code = PENALTY_MAPS["jurisdiction"][kw]
                fqs.append(f"+jurisdiction:(({code}))")
                break
    year_fq = build_judgment_year_filter(params.year_from, params.year_to)
    if year_fq:
        fqs.append(year_fq)

    print(f"过滤器: {fqs}")

    query_string = params.query
    if params.mode == "few":
        target = args.target or 5
        resp = client.search(
            query_string=query_string, filter_queries=fqs,
            page_limit=target, library="penalty"
        )
    else:
        resp = client.search(
            query_string=query_string, filter_queries=fqs,
            page_limit=args.max or 200, library="penalty"
        )

    results = parse_search_results(resp, library="penalty")
    total = resp.get("searchMetadata", {}).get("docCount", 0)
    print(f"命中: {total:,} | 返回: {len(results)} 条")

    for i, r in enumerate(results[:10], 1):
        af = r.get("additionalFields", {})
        print(f"\n[{i}] {r.get('title', '?')[:60]}")
        print(f"    编号: {af.get('documentNumber', '?')}")
        print(f"    机关: {af.get('punishAgency', af.get('issuingAuthority', '?'))}")
        print(f"    日期: {af.get('promulgatingDate', af.get('decisionDate', '?'))}")
        print(f"    docId: {r.get('docId', '?')}")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"query": params.query, "total": total, "results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n[+] 保存到: {args.output}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="威科行政处罚检索")
    parser.add_argument("--query", "-q", help="检索关键词")
    parser.add_argument("--mode", choices=["few", "list"], help="检索模式")
    parser.add_argument("--target", type=int, help="few 模式目标数量")
    parser.add_argument("--max", type=int, help="list 模式最大数量")
    parser.add_argument("--industry", help="行业领域（金融业/建筑业 等）")
    parser.add_argument("--topic", help="监管领域（市场监管/财税/金融/知识产权/环保 等）")
    parser.add_argument("--jurisdiction", help="地域（全国/北京市 等）")
    parser.add_argument("--year", type=int, help="年份")
    parser.add_argument("--output", "-o", help="结果输出 JSON 文件")
    args = parser.parse_args()
    return run_search(args)


if __name__ == "__main__":
    sys.exit(main())
