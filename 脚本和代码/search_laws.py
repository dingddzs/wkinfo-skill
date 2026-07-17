# -*- coding: utf-8 -*-
"""法律法规检索 CLI（薄壳：复用 wkinfo_api.py + nl_parser.py + search_cases.py 模式）

用法：
  # 按标题搜
  python search_laws.py --query "公司法" --mode few --target 3

  # 加上过滤
  python search_laws.py --query "商标法" --legal-level 法律 --validity 现行有效 --year 2024
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nl_parser import ParamParser, SearchParams
from wkinfo_api import WkinfoClient, parse_search_results, LIBRARIES, build_filter_queries, build_judgment_year_filter


def run_search(args) -> int:
    parser_obj = ParamParser()
    client = WkinfoClient()

    params = parser_obj.parse(args.query or "")

    # CLI 参数覆盖
    if args.legal_level:
        # 法律层级（newLevelEffect）
        from wkinfo_api import LEGISLATION_MAPS
        if args.legal_level in LEGISLATION_MAPS.get("newLevelEffect", {}):
            params.extra_keywords.append(args.legal_level)
    if args.validity:
        from wkinfo_api import LEGISLATION_MAPS
        if args.validity in LEGISLATION_MAPS.get("validityStatus", {}):
            params.extra_keywords.append(args.validity)
    if args.jurisdiction:
        from wkinfo_api import LEGISLATION_MAPS
        if args.jurisdiction in LEGISLATION_MAPS.get("jurisdiction", {}):
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
    print(f"库: 法律法规")
    print(f"查询: {params.query}")
    print(f"模式: {params.mode}")
    if params.year_from or params.year_to:
        print(f"时间: {params.year_from or '*'} - {params.year_to or '*'}")
    print("=" * 60)

    # 构造 filter_queries
    fqs = []
    from wkinfo_api import LEGISLATION_MAPS
    if "newLevelEffect" in LEGISLATION_MAPS and any(
        params.extra_keywords and kw in LEGISLATION_MAPS["newLevelEffect"]
        for kw in params.extra_keywords
    ):
        for kw in params.extra_keywords:
            if kw in LEGISLATION_MAPS["newLevelEffect"]:
                code = LEGISLATION_MAPS["newLevelEffect"][kw]
                fqs.append(f"+newLevelEffect:(({code}))")
                break  # 只用第一个匹配的
    if "validityStatus" in LEGISLATION_MAPS and any(
        kw in LEGISLATION_MAPS["validityStatus"] for kw in params.extra_keywords
    ):
        for kw in params.extra_keywords:
            if kw in LEGISLATION_MAPS["validityStatus"]:
                code = LEGISLATION_MAPS["validityStatus"][kw]
                fqs.append(f"+validityStatus:(({code}))")
                break
    if "jurisdiction" in LEGISLATION_MAPS and any(
        kw in LEGISLATION_MAPS["jurisdiction"] for kw in params.extra_keywords
    ):
        for kw in params.extra_keywords:
            if kw in LEGISLATION_MAPS["jurisdiction"]:
                code = LEGISLATION_MAPS["jurisdiction"][kw]
                fqs.append(f"+jurisdiction:(({code}))")
                break

    # 日期过滤
    year_fq = build_judgment_year_filter(params.year_from, params.year_to)
    if year_fq:
        fqs.append(year_fq)

    print(f"过滤器: {fqs}")

    # 搜索
    query_string = params.query
    if params.mode == "few":
        target = args.target or 5
        resp = client.search(
            query_string=query_string, filter_queries=fqs,
            page_limit=target, library="legislation"
        )
    else:
        # 简化版：先拿前 max_count 条
        resp = client.search(
            query_string=query_string, filter_queries=fqs,
            page_limit=args.max or 200, library="legislation"
        )

    results = parse_search_results(resp, library="legislation")
    total = resp.get("searchMetadata", {}).get("docCount", 0)
    print(f"命中: {total:,} | 返回: {len(results)} 条")

    for i, r in enumerate(results[:10], 1):
        af = r.get("additionalFields", {})
        print(f"\n[{i}] {r.get('title', '?')[:60]}")
        print(f"    编号: {af.get('documentNumber', '?')}")
        print(f"    颁布: {af.get('promulgatingDate', '?')}")
        print(f"    效力: {af.get('validityStatus', '?')}")
        print(f"    docId: {r.get('docId', '?')}")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"query": params.query, "total": total, "results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n[+] 保存到: {args.output}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="威科法律法规检索")
    parser.add_argument("--query", "-q", help="检索关键词/标题")
    parser.add_argument("--mode", choices=["few", "list"], help="检索模式")
    parser.add_argument("--target", type=int, help="few 模式目标数量")
    parser.add_argument("--max", type=int, help="list 模式最大数量")
    parser.add_argument("--legal-level", help="法律层级（法律/行政法规/司法解释/部门规章/地方法规等）")
    parser.add_argument("--validity", help="效力状态（现行有效/失效/废止/已被修订/部分失效/尚未生效/草案/征求意见稿）")
    parser.add_argument("--jurisdiction", help="地域（全国/北京市/上海市 等）")
    parser.add_argument("--year", type=int, help="年份")
    parser.add_argument("--output", "-o", help="结果输出 JSON 文件")
    args = parser.parse_args()
    return run_search(args)


if __name__ == "__main__":
    sys.exit(main())
