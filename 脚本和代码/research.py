# -*- coding: utf-8 -*-
"""研究模式：跨多库并行搜索（5 个库）

用于法律调研任务：用户问"调研XX法律问题"时，自动从
- 裁判文书（案例）
- 法律法规
- 行政处罚
- 实务指南（编辑部文章）
- 专题聚焦（专题报告）

5 个库并行搜索，输出结构化信源汇总。

用法：
  python research.py --query "建设工程实际施工人向发包人请求付款"
  python research.py --query "公司法司法解释" --libraries case,legislation,commentary
  python research.py --query "上市公司处罚" --mode summary  # 只显示各库命中数
"""
import argparse
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

from wkinfo_api import WkinfoClient, LIBRARIES, parse_search_results


def search_one_library(client: WkinfoClient, lib_key: str, query: str, limit: int = 5) -> dict:
    """单个库搜索（用于并发）"""
    try:
        resp = client.search(
            query_string=f"simple:(({query}))",
            page_limit=limit,
            library=lib_key,
        )
        items = parse_search_results(resp, library=lib_key)[:limit]
        return {
            "name": LIBRARIES[lib_key].name,
            "count": resp.get("searchMetadata", {}).get("docCount", 0),
            "items": items,
            "url": LIBRARIES[lib_key].list_url,
        }
    except Exception as e:
        return {
            "name": LIBRARIES[lib_key].name,
            "error": str(e)[:200],
        }


def research(query: str, libraries: list = None, limit: int = 5) -> dict:
    """跨多库并行搜索"""
    if libraries is None:
        libraries = ["case", "legislation", "penalty", "commentary", "focus"]

    client = WkinfoClient()
    results = {}

    # 并发（5 库各 1 个请求）
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(search_one_library, client, lib, query, limit): lib
            for lib in libraries
            if lib in LIBRARIES
        }
        for future in as_completed(futures):
            lib_key = futures[future]
            results[lib_key] = future.result()

    return {"query": query, "results": results}


def format_summary(r: dict) -> str:
    """格式化输出汇总"""
    lines = [f"\n研究查询: {r['query']}", "=" * 70]
    total = 0
    success = 0
    for lib_key, info in r["results"].items():
        if "error" in info:
            lines.append(f"  [{lib_key:12s}] {info.get('name', '?')}: ERR {info['error'][:60]}")
        else:
            count = info.get("count", 0)
            total += count
            success += 1
            lines.append(f"  [{lib_key:12s}] {info.get('name', '?'):8s}: {count:>10,} 条")
    lines.append("=" * 70)
    lines.append(f"  合计: {total:,} 条 | {success} 库成功")
    return "\n".join(lines)


def format_detail(r: dict) -> str:
    """格式化详细输出（含每条结果）"""
    lines = format_summary(r).split("\n")
    lines.append("\n详细结果:")
    for lib_key, info in r["results"].items():
        if "error" in info:
            continue
        lines.append(f"\n--- {info.get('name', '?')} ({lib_key}, 命中 {info.get('count', 0):,}) ---")
        for i, item in enumerate(info.get("items", [])[:3], 1):
            af = item.get("additionalFields", {})
            title = item.get("title", "?")[:60]
            lines.append(f"  [{i}] {title}")
            # 显示元数据
            meta_fields = ["documentNumber", "court", "courtText", "promulgatingDate", "judgmentDate",
                          "causeOfActionText", "validityStatus", "topicClassification", "groupLevel"]
            meta = []
            for f in meta_fields:
                v = af.get(f)
                if v and str(v) not in ("?", "None", ""):
                    meta.append(f"{v}")
            if meta:
                lines.append(f"      {' | '.join(meta[:3])}")
            docId = item.get("docId", "?")
            lines.append(f"      docId: {docId[:30]}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="威科跨库研究模式")
    parser.add_argument("--query", "-q", required=True, help="调研问题/关键词")
    parser.add_argument("--libraries", help="逗号分隔的库列表（默认全部 5 个）")
    parser.add_argument("--limit", type=int, default=3, help="每库返回条数")
    parser.add_argument("--mode", choices=["summary", "detail"], default="detail",
                        help="输出模式")
    parser.add_argument("--output", "-o", help="结果输出 JSON 文件")
    args = parser.parse_args()

    libraries = args.libraries.split(",") if args.libraries else None
    r = research(args.query, libraries=libraries, limit=args.limit)

    if args.mode == "summary":
        print(format_summary(r))
    else:
        print(format_detail(r))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\n[+] 保存到: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
