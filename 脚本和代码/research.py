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
  python research.py --query "建设工程实际施工人" --mode iterative  # 往返事实/规范迭代检索
"""
import argparse
import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

from wkinfo_api import WkinfoClient, LIBRARIES, parse_search_results


# ============ 引用法条提取 ============

# 匹配 "《XXX法》" "《XXX条例》" 等中国法律法规名称
_LAW_NAME_PATTERN = re.compile(
    r'《[^》]{2,40}?'
    r'(?:法|条例|规定|办法|解释|细则|规则|意见|条例草案|标准|规范|司法解释|法规)'
    r'(?:（[^）]*）)?'
    r'》'
)

# 匹配具体条款 "第X条" "第X款" "第X章"
_ARTICLE_PATTERN = re.compile(
    r'第[一二三四五六七八九十百千零〇\d]+'
    r'(?:条|款|项|章|节|编)'
    r'(?:第[一二三四五六七八九十百千零〇\d]+'
    r'(?:条|款|项|节))?'
)

def _strip_html(s: str) -> str:
    """去掉 wkinfo summary 里的 <font class="titleHL">XXX</font> 标签"""
    if not s:
        return ""
    # 简单移除 font 标签（wkinfo 高亮关键字用）
    return re.sub(r'<[^>]+>', '', s)


def extract_cited_laws(text: str) -> list:
    """从文本中抽取被引用的法律法规名称（去重保序）"""
    if not text:
        return []
    text = _strip_html(text)
    seen = set()
    result = []
    for m in _LAW_NAME_PATTERN.findall(text):
        name = m.strip('《》')
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def extract_cited_articles(text: str) -> list:
    """从文本中抽取具体条款引用（去重保序）"""
    if not text:
        return []
    text = _strip_html(text)
    seen = set()
    result = []
    for m in _ARTICLE_PATTERN.findall(text):
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


# ============ URL 构造 ============

def make_item_url(library_key: str, doc_id: str) -> str:
    """根据库 + docId 构造详情页 URL"""
    if not doc_id:
        return ""
    lib = LIBRARIES.get(library_key)
    if not lib:
        return ""
    # /judgment-documents/list -> /judgment-documents/detail
    detail_path = lib.list_url.replace("/list", "/detail")
    return f"https://law.wkinfo.com.cn{detail_path}/{doc_id}"


# ============ 检索结果增强 ============

def enrich_item(item: dict, library_key: str) -> dict:
    """给单条结果加 url + cited_laws（不修改原 item，返回新 dict）"""
    if not item:
        return item
    result = dict(item) if isinstance(item, dict) else item

    # 1. URL
    doc_id = item.get("docId") if isinstance(item, dict) else None
    result["url"] = make_item_url(library_key, doc_id)

    # 2. 引用法条（从 title + summary + additionalFields 抽）
    if isinstance(item, dict):
        text_pool = (
            (item.get("title") or "")
            + " " + (item.get("summary") or "")
        )
        # 也从 additionalFields 抽（known 法律名）
        af = item.get("additionalFields", {})
        if isinstance(af, dict):
            known_laws = []
            for k in ("causeOfActionText", "judgeResult", "trialProcess"):
                v = af.get(k)
                if v and isinstance(v, str):
                    known_laws.extend(extract_cited_laws(v))
            if known_laws:
                result["_known_laws"] = known_laws

        result["cited_laws"] = extract_cited_laws(text_pool)
        # 取前 5 个（太多噪音）
        if len(result["cited_laws"]) > 5:
            result["cited_laws"] = result["cited_laws"][:5]

        # 3. 引用条款（条文）—— 用户明确要一字不漏
        result["cited_articles"] = extract_cited_articles(text_pool)
        # 取前 8 个
        if len(result["cited_articles"]) > 8:
            result["cited_articles"] = result["cited_articles"][:8]

    return result


# ============ 核心：单库 + 多库搜索 ============

def search_one_library(client: WkinfoClient, lib_key: str, query: str, limit: int = 5) -> dict:
    """单个库搜索（用于并发）"""
    try:
        resp = client.search(
            query_string=f"simple:(({query}))",
            page_limit=limit,
            library=lib_key,
        )
        items = parse_search_results(resp, library=lib_key)[:limit]
        # 增强 items
        items = [enrich_item(it, lib_key) for it in items]
        return {
            "name": LIBRARIES[lib_key].name,
            "count": resp.get("searchMetadata", {}).get("docCount", 0),
            "items": items,
            "url": LIBRARIES[lib_key].list_url,
            "search_id": resp.get("searchMetadata", {}).get("searchId"),
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


# ============ "往返于事实与规范之间" 迭代检索 ============

def research_iterative(query: str, max_iterations: int = 3, limit: int = 5) -> dict:
    """
    往返于事实和规范之间的迭代检索。

    流程：
    1. Round 0：初始关键词对 5 库搜索
    2. Round 1+：从结果中抽取引用的法条/法规 → 以法条为锚点
       再搜 case/commentary/focus（fact-based 库）
    3. 合并所有轮次的去重结果

    终止：没有发现新法条 OR 达到 max_iterations
    """
    seen_laws = set()
    iteration_log = []
    all_results = {}  # lib_key -> items 累积

    # Round 0
    r0 = research(query, limit=limit)
    new_laws_round = set()
    for lib_key, info in r0["results"].items():
        for item in info.get("items", []):
            cited = item.get("cited_laws", [])
            new_laws_round.update(cited)
            # 累积
            if lib_key not in all_results:
                all_results[lib_key] = list(info.get("items", []))
            else:
                for it in info.get("items", []):
                    if it not in all_results[lib_key]:
                        all_results[lib_key].append(it)
    seen_laws.update(new_laws_round)
    iteration_log.append({
        "round": 0,
        "query": query,
        "new_laws_count": len(new_laws_round),
        "new_laws": sorted(new_laws_round)[:10],
    })

    # Round 1+: 用 laws 作为锚点
    for i in range(1, max_iterations + 1):
        if not seen_laws:
            break
        # 取最新发现的前 5 个法条作为锚点
        anchor_laws = sorted(seen_laws)[:5]
        anchor_query = " ".join(anchor_laws)
        r = research(anchor_query,
                    libraries=["case", "commentary", "focus"],
                    limit=limit)

        new_laws_this_round = set()
        for lib_key, info in r["results"].items():
            for item in info.get("items", []):
                cited = item.get("cited_laws", [])
                new_laws_this_round.update(cited)
                if lib_key not in all_results:
                    all_results[lib_key] = list(info.get("items", []))
                else:
                    if item not in all_results[lib_key]:
                        all_results[lib_key].append(item)

        truly_new = new_laws_this_round - seen_laws
        seen_laws.update(truly_new)
        iteration_log.append({
            "round": i,
            "anchor_laws": anchor_laws,
            "new_laws_count": len(truly_new),
            "new_laws": sorted(truly_new)[:10],
        })
        if not truly_new:
            break

    return {
        "query": query,
        "mode": "iterative",
        "iterations": iteration_log,
        "total_laws_found": len(seen_laws),
        "results": all_results,
    }


# ============ 格式化输出 ============

def _info_count(info) -> int:
    """兼容两种 results 结构（dict 或 list）"""
    if isinstance(info, dict):
        return info.get("count", 0)
    if isinstance(info, list):
        return len(info)
    return 0


def _info_items(info) -> list:
    """从 info 拿 items list（兼容两种结构）"""
    if isinstance(info, dict):
        return info.get("items", []) or []
    if isinstance(info, list):
        return info
    return []


def _info_name(info, fallback: str) -> str:
    if isinstance(info, dict):
        return info.get("name", fallback)
    return fallback


def _info_error(info) -> str:
    if isinstance(info, dict) and "error" in info:
        return info["error"]
    return ""


def format_summary(r: dict) -> str:
    """格式化输出汇总"""
    lines = [f"\n研究查询: {r['query']}", "=" * 70]
    total = 0
    success = 0
    for lib_key, info in r["results"].items():
        if _info_error(info):
            lines.append(f"  [{lib_key:12s}] {_info_name(info, '?')}: ERR {_info_error(info)[:60]}")
        else:
            count = _info_count(info)
            total += count
            success += 1
            lines.append(f"  [{lib_key:12s}] {_info_name(info, '?'):8s}: {count:>10,} 条")
    lines.append("=" * 70)
    lines.append(f"  合计: {total:,} 条 | {success} 库成功")
    if "iterations" in r:
        lines.append(f"\n  迭代轮次: {len(r['iterations'])} 轮 | 共发现法条: {r.get('total_laws_found', 0)} 个")
    return "\n".join(lines)


def format_detail(r: dict) -> str:
    """格式化详细输出"""
    lines = format_summary(r).split("\n")

    # 迭代模式：先显示轨迹
    if r.get("mode") == "iterative":
        lines.append("\n" + "=" * 70)
        lines.append("迭代检索轨迹：")
        for it in r.get("iterations", []):
            lines.append(f"  Round {it['round']}: +{it['new_laws_count']} 法条")
            if it.get("anchor_laws"):
                lines.append(f"    锚点: {', '.join(it['anchor_laws'][:3])}")
            for law in it.get("new_laws", []):
                lines.append(f"    + {law}")
        lines.append("=" * 70)

    lines.append("\n详细结果:")
    for lib_key, info in r["results"].items():
        if _info_error(info):
            continue
        items = _info_items(info)
        count = _info_count(info)
        lines.append(f"\n--- {_info_name(info, '?')} ({lib_key}, 命中 {count:,}) ---")
        for i, item in enumerate(items[:5], 1):
            if not isinstance(item, dict):
                continue
            af = item.get("additionalFields", {})
            title = item.get("title", "?")[:60]
            url = item.get("url", "")
            lines.append(f"  [{i}] {title}")
            if url:
                lines.append(f"      URL: {url}")
            # 引用法条
            cited = item.get("cited_laws", [])
            if cited:
                lines.append(f"      引用法条: {', '.join(cited[:3])}")
            # 引用条款
            articles = item.get("cited_articles", [])
            if articles:
                lines.append(f"      条款: {', '.join(articles[:3])}")
            # 元数据
            meta_fields = ["documentNumber", "courtText", "court",
                          "judgmentdatestr", "promulgatingDate",
                          "causeOfActionText", "validityStatus",
                          "topicClassification", "groupLevel"]
            meta = []
            for f in meta_fields:
                v = af.get(f)
                if v and str(v) not in ("?", "None", ""):
                    meta.append(f"{v}")
            if meta:
                lines.append(f"      {meta[0]}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="威科跨库研究模式")
    parser.add_argument("--query", "-q", required=True, help="调研问题/关键词")
    parser.add_argument("--libraries", help="逗号分隔的库列表（默认全部 5 个）")
    parser.add_argument("--limit", type=int, default=3, help="每库返回条数")
    parser.add_argument("--mode", choices=["summary", "detail", "iterative"], default="detail",
                        help="输出模式（iterative = 往返事实/规范迭代检索）")
    parser.add_argument("--max-iterations", type=int, default=3,
                        help="iterative 模式最大迭代轮数")
    parser.add_argument("--output", "-o", help="结果输出 JSON 文件")
    args = parser.parse_args()

    libraries = args.libraries.split(",") if args.libraries else None

    if args.mode == "iterative":
        r = research_iterative(args.query, max_iterations=args.max_iterations, limit=args.limit)
    else:
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
