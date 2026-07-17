# -*- coding: utf-8 -*-
"""案例搜索 CLI：自然语言 → 渐进式逼近 → 搜索结果

两种模式：
  mode=few    "几个/几份" → 返回前 N 条匹配（默认 5），PDF 下载标黄
  mode=list   "清单/汇总" → 渐进式逼近到 ≤N 条（默认 200），Excel 下载

用法：
  python search_cases.py --query "建设工程实际施工人向发包人请求付款" --mode few
  python search_cases.py --query "股东代表诉讼" --mode list --max 200
  python search_cases.py --query "..." --keyword "..." --court-level "最高人民法院" --year-from 2023
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# 添加 scripts 目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from nl_parser import ParamParser, SearchParams
from wkinfo_api import WkinfoClient, parse_search_results


# ============ 参数构造 ============

def _strip_filter_words(params: SearchParams) -> str:
    """从 query 中去掉已被提取的过滤词，避免污染 queryString"""
    import re as _re
    q = params.query
    if params.court_level:
        for k in ["最高人民法院", "最高法", "高级人民法院", "高院", "中级人民法院",
                  "中院", "基层人民法院", "基层"]:
            q = q.replace(k, "")
    if params.court_name:
        q = q.replace(params.court_name, "")
    if params.trial_procedure:
        for k in ["一审", "二审", "再审", "破产程序", "执行程序"]:
            q = q.replace(k, "")
    if params.doc_type:
        for k in ["判决书", "裁定书", "决定书", "调解书", "通知书"]:
            q = q.replace(k, "")
    if params.year_from or params.year_to:
        q = _re.sub(r"近[一二三四五六七八九十两\d]+\s*年", "", q)
        q = _re.sub(r"最近[一二三四五六七八九十两\d]+\s*年", "", q)
        q = _re.sub(r"\d{4}\s*年\s*[-~到至]?\s*\d{0,4}\s*年?", "", q)
    q = _re.sub(r"[，。；,;]", " ", q)
    q = _re.sub(r"\s+", " ", q).strip()
    return q if q else params.query


def build_filter_queries(params: SearchParams, extra_filters: Optional[list] = None) -> list:
    """从 SearchParams 构造 Lucene filter_queries

    支持字段（已验证）：
    - courtLevel: 单数字 (1=最高, 2=高院, 3=中院, 4=基层, 5=专门)
    - typeOfDecisionCode: 3 位数字 (001=判决书, 002=裁定书, ...)
    - instance: 3 位数字 (001=一审, 002=二审, 003=再审, ...)
    - court: 9位数字+中文名 (001000000最高人民法院, 003000000北京市, ...)
    - causeOfAction: 14位数字+中文名 (01000000000000民事, ...)
    - industryCode: 单字母 (A=农林牧渔, ..., J=金融业, K=房地产业)
    - referenceLevelNew: 2位数字 (02=最高检, 04=公报, 06=上海金融, ...)
    - judgmentYear: Lucene 范围 ([YYYY TO YYYY+1])
    """
    fqs = []

    # 法院级别
    if params.court_level:
        from wkinfo_api import COURT_LEVEL_MAP
        if params.court_level in COURT_LEVEL_MAP:
            fqs.append(f"+courtLevel:(({COURT_LEVEL_MAP[params.court_level]}))")

    # 文书类型
    if params.doc_type:
        from wkinfo_api import DOC_TYPE_MAP
        if params.doc_type in DOC_TYPE_MAP:
            fqs.append(f"+typeOfDecisionCode:(({DOC_TYPE_MAP[params.doc_type]}))")

    # 审级
    if params.trial_procedure:
        from wkinfo_api import INSTANCE_MAP
        if params.trial_procedure in INSTANCE_MAP:
            fqs.append(f"+instance:(({INSTANCE_MAP[params.trial_procedure]}))")

    # 具体法院
    if params.court_name:
        from wkinfo_api import COURT_MAP
        if params.court_name in COURT_MAP:
            fqs.append(f"+court:(({COURT_MAP[params.court_name]}))")

    # 案由顶级
    if params.cause_of_action:
        from wkinfo_api import CAUSE_OF_ACTION_MAP
        if params.cause_of_action in CAUSE_OF_ACTION_MAP:
            fqs.append(f"+causeOfAction:(({CAUSE_OF_ACTION_MAP[params.cause_of_action]}))")

    # 行业
    if params.industry:
        from wkinfo_api import INDUSTRY_MAP
        if params.industry in INDUSTRY_MAP:
            fqs.append(f"+industryCode:(({INDUSTRY_MAP[params.industry]}))")

    # 参照级别
    if params.reference_level:
        from wkinfo_api import REFERENCE_LEVEL_MAP
        if params.reference_level in REFERENCE_LEVEL_MAP:
            fqs.append(f"+referenceLevelNew:(({REFERENCE_LEVEL_MAP[params.reference_level]}))")

    # 时间范围
    from wkinfo_api import build_judgment_year_filter
    year_fq = build_judgment_year_filter(params.year_from, params.year_to)
    if year_fq:
        fqs.append(year_fq)

    if extra_filters:
        fqs.extend(extra_filters)
    return fqs


def build_filter_dates_deprecated():
    """已废弃：威科 API 不接受 filterDates 字段，请用 judgmentYear 范围语法"""
    return []


# ============ 渐进式逼近 ============

# 可选补充过滤项（按"过滤效力"排序：效力越强越靠前）
# 这些是用户没指定时，按优先级依次尝试
SUPPLEMENTARY_FILTERS = [
    # (filter_query, 描述, 跳过条件 — 如果是用户已指定的过滤类型)
    ("+typeOfDecisionCode:((001))", "判决书", "doc_type"),
    ("+courtLevel:((1 OR 2 OR 3))", "中级法院及以上", "court_level"),
    ("+judgmentYear:([2024 TO 2027])", "近3年(2024+)", "year_recent"),
    ("+judgmentYear:([2023 TO 2027])", "近5年(2023+)", "year_recent"),
    ("+referenceLevelNew:((08))", "律师评案", "reference_level"),
]


def progressive_search(
    client: WkinfoClient,
    query_string: str,
    max_count: int,
    params: SearchParams = None,
    verbose: bool = True
) -> tuple:
    """自适应渐进式逼近

    1. 先应用用户指定的过滤（如法院/时间/审级/文书类型）
    2. 检查命中数
    3. ≤ max: 返回
    4. > max: 按优先级依次尝试 SUPPLEMENTARY_FILTERS
       - 跳过用户已指定的过滤类型
       - 跳过导致 0 命中的过滤（避免交集为空）
    5. 仍 > max: 按 score+judgmentDate DESC 截取前 max 条

    返回 (filter_queries, doc_count, is_capped)
    """
    # 阶段 0: 应用用户的过滤
    if params is None:
        user_fqs = []
    else:
        user_fqs = build_filter_queries(params)

    if verbose:
        print(f"\n[Stage 0] 用户指定过滤: {user_fqs if user_fqs else '(无)'}")
    count = client.doc_count(query_string=query_string, filter_queries=user_fqs)
    if verbose:
        print(f"  命中: {count:,}")
    if count <= max_count:
        return user_fqs, count, False

    # 阶段 1+: 按优先级补充过滤
    current_fqs = list(user_fqs)
    prev_count = count
    for fq, desc, skip_key in SUPPLEMENTARY_FILTERS:
        # 跳过用户已指定的过滤
        if params and _filter_already_specified(params, skip_key):
            continue

        candidate_fqs = current_fqs + [fq]
        new_count = client.doc_count(query_string=query_string, filter_queries=candidate_fqs)

        if verbose:
            print(f"\n[Stage +] 加 {desc}: {fq}")
            print(f"  命中: {new_count:,}")

        # 跳过导致 0 命中或未减少的过滤（无效过滤）
        if new_count == 0:
            if verbose:
                print(f"  [!] 跳过（交集为空）")
            continue
        if new_count >= prev_count:
            if verbose:
                print(f"  [!] 跳过（未减少命中）")
            continue

        current_fqs = candidate_fqs
        prev_count = new_count
        if new_count <= max_count:
            return current_fqs, new_count, False

    # 阶段 N: 不再逼近，按 judgmentDate DESC 截取 max_count
    if verbose:
        print(f"\n[Stage N] 不再逼近，按 judgmentDate DESC 截取前 {max_count} 条")
    return current_fqs, max_count, True


def _filter_already_specified(params: SearchParams, skip_key: str) -> bool:
    """检查用户是否已指定某类过滤"""
    mapping = {
        "doc_type": params.doc_type,
        "court_level": params.court_level,
        "year_recent": params.year_from or params.year_to,
        "reference_level": params.reference_level,
    }
    return bool(mapping.get(skip_key))


# ============ 主流程 ============

def run_search(args) -> int:
    parser_obj = ParamParser()
    client = WkinfoClient()

    # 1. 参数解析
    if args.query:
        params = parser_obj.parse(args.query)
    else:
        # 用结构化参数构造伪 query
        params = SearchParams(query=" ".join(filter(None, [
            args.keyword, args.case_cause_sub
        ])))

    # CLI 参数覆盖
    if args.keyword:
        params.query = args.keyword
    if args.court_level:
        params.court_level = args.court_level
    if args.doc_type:
        params.doc_type = args.doc_type
    if args.year_from:
        params.year_from = args.year_from
    if args.year_to:
        params.year_to = args.year_to
    if args.mode:
        params.mode = args.mode
    if args.max:
        params.max_count = args.max

    print("=" * 60)
    print(f"原始查询: {params.query}")
    print(f"模式: {params.mode}")
    if params.case_cause:
        cc = params.case_cause
        print(f"猜测案由: {cc.part_name} > {cc.category_name} > {cc.cause_name}"
              + (f" > {cc.sub_cause_name}" if cc.sub_cause_name else "")
              + f" (score={cc.match_score:.2f})")
    if params.year_from or params.year_to:
        print(f"时间范围: {params.year_from or '不限'} - {params.year_to or '不限'}")
    if params.court_level:
        print(f"法院级别: {params.court_level}")
    if params.doc_type:
        print(f"文书类型: {params.doc_type}")
    print("=" * 60)

    # 2. 构造 filter_queries
    fqs = build_filter_queries(params)

    # 3. queryString: 提取核心关键词（案由名），不要把过滤参数混入 queryString
    # 否则 wkinfo 会把"最高法" "二审" 等当成额外关键词，导致命中为 0
    if params.case_cause:
        cc = params.case_cause
        # 优先用最具体的案由名（sub_cause > cause）
        if cc.sub_cause_name:
            query_string = cc.sub_cause_name
        elif cc.cause_name:
            query_string = cc.cause_name
        else:
            # 去掉从原文里提取的过滤词
            query_string = _strip_filter_words(params)
    else:
        # 无案由匹配时，从原文中去掉明显的过滤词
        query_string = _strip_filter_words(params)

    print(f"核心关键词: {query_string}")

    # 4. 搜索模式分支
    if params.mode == "list":
        # 渐进式逼近
        final_fqs, final_count, is_capped = progressive_search(
            client, query_string, params.max_count, params=params, verbose=args.verbose
        )
        if args.verbose:
            print(f"\n最终命中: {final_count:,} ({'截取' if is_capped else '实际'})")
            print(f"最终 filter: {final_fqs}")

        # 取前 max_count 条结果
        all_results = []
        page_limit = 100
        page_offset = 0
        while len(all_results) < min(final_count, params.max_count):
            batch_size = min(page_limit, params.max_count - len(all_results))
            resp = client.search(
                query_string=query_string,
                filter_queries=final_fqs,
                
                page_offset=page_offset,
                page_limit=batch_size,
            )
            results = parse_search_results(resp)
            if not results:
                break
            all_results.extend(results)
            if len(results) < batch_size:
                break
            page_offset += batch_size

        print(f"\n共 {len(all_results)} 条结果")
    else:
        # few 模式: 取前 N 条匹配
        target_n = args.target if args.target else params.target_count
        resp = client.search(
            query_string=query_string,
            filter_queries=fqs,
            
            page_limit=target_n,
        )
        all_results = parse_search_results(resp)
        print(f"\n匹配 {len(all_results)} 条 (目标 {target_n})")

    # 5. 展示结果
    if all_results:
        for i, r in enumerate(all_results[:20], 1):
            af = r.get('additionalFields', {})
            print(f"\n[{i}] {r.get('title', '?')[:80]}")
            print(f"    案号: {af.get('documentNumber', '?')}")
            print(f"    法院: {af.get('courtText', '?')}")
            print(f"    案由: {af.get('causeOfActionText', '?')}")
            print(f"    类型: {af.get('typeofdecision', '?')}")
            print(f"    日期: {af.get('judgmentDate', '?')}")
            print(f"    docId: {r.get('docId', '?')}")

        if len(all_results) > 20:
            print(f"\n... 共 {len(all_results)} 条，仅展示前 20 条")

    # 6. 输出 JSON 文件
    if args.output:
        out = {
            "query": params.query,
            "params": params.to_dict(),
            "results": all_results
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n[+] 结果已保存到: {args.output}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="威科案例检索 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--query", help="自然语言查询（如 '建设工程实际施工人向发包人请求付款'）")
    parser.add_argument("--keyword", help="直接指定关键词（覆盖 query 解析）")
    parser.add_argument("--mode", choices=["few", "list"], help="检索模式")
    parser.add_argument("--target", type=int, help="few 模式目标数量")
    parser.add_argument("--max", type=int, help="list 模式最大数量")
    parser.add_argument("--court-level", help="法院级别（最高人民法院/高级人民法院/...）")
    parser.add_argument("--doc-type", help="文书类型（判决书/裁定书/...）")
    parser.add_argument("--year-from", type=int, help="起始年份")
    parser.add_argument("--year-to", type=int, help="结束年份")
    parser.add_argument("--case-cause-sub", help="直接指定案由子项（如 '建设工程施工合同纠纷'）")
    parser.add_argument("--output", help="结果输出 JSON 文件路径")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    try:
        return run_search(args)
    except Exception as e:
        print(f"[X] 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())