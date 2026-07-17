# -*- coding: utf-8 -*-
"""案例下载 CLI

支持格式：pdf / docx / xls
输入：搜索结果 JSON（来自 search_cases.py --output）或单独的 docId 列表

用法：
  # 下载搜索结果中的所有 PDF
  python download.py --input ./原始文件/建设工程实际施工人_20260716/search_result.json --format pdf --highlight

  # 下载指定案号列表
  python download.py --query "..." --format xls --output ./原始文件/案例清单_20260716.xls
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from wkinfo_api import WkinfoClient


def load_results(input_path: str) -> list:
    """从 search_cases.py 输出的 JSON 加载结果列表"""
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    raise ValueError(f"无法识别的 JSON 结构")


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """清理文件名（去掉非法字符）"""
    import re
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    if len(name) > max_len:
        name = name[:max_len]
    return name


def download_results(
    results: list,
    client: WkinfoClient,
    output_dir: Path,
    file_type: str = "pdf",
    highlight: bool = False,
    verbose: bool = True,
) -> dict:
    """下载结果列表中的所有文档

    返回 {"success": N, "failed": M, "files": [...]}
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failed_count = 0
    downloaded_files = []

    for i, r in enumerate(results, 1):
        doc_id = r.get("docId")
        if not doc_id:
            if verbose:
                print(f"[{i}/{len(results)}] 跳过（无 docId）")
            failed_count += 1
            continue

        # 构造文件名
        af = r.get("additionalFields", {})
        case_no = af.get("documentNumber", doc_id)[:30]
        title = r.get("title", "")[:50]
        basename = sanitize_filename(f"{case_no}_{title}") if title else sanitize_filename(case_no)
        if highlight:
            basename = f"[匹配]_{i:03d}_{basename}"
        else:
            basename = f"{i:03d}_{basename}"
        filename = f"{basename}.{file_type}"

        if verbose:
            print(f"[{i}/{len(results)}] {filename}")

        # 调用下载
        result = client.download_file(
            doc_id=doc_id,
            file_type=file_type,
            filename=filename,
            search_id=r.get("searchId", ""),
            output_path=output_dir / filename
        )

        if result["success"]:
            success_count += 1
            downloaded_files.append({
                "docId": doc_id,
                "caseNo": af.get("documentNumber"),
                "title": r.get("title"),
                "filename": result["filename"],
                "path": result["path"],
                "size": result["size"],
                "matched": highlight,
                "score": r.get("score")
            })
            if verbose:
                print(f"  [+] {result['size']:,} bytes")
        else:
            failed_count += 1
            if verbose:
                print(f"  [X] {result.get('error', '未知错误')}")

    return {
        "success": success_count,
        "failed": failed_count,
        "files": downloaded_files
    }


def generate_index(output_dir: Path, downloaded: list, query: str = "", mode: str = "") -> Path:
    """生成索引 README.md（包含匹配标记和文件清单）"""
    if not downloaded:
        return None

    lines = ["# 检索结果索引", ""]
    if query:
        lines.append(f"**检索条件**: {query}")
    if mode:
        lines.append(f"**模式**: {mode}")
    lines.append(f"**生成时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**文件数**: {len(downloaded)}")
    lines.append("")
    lines.append("| # | 文件名 | 案号 | 标题 | 大小 | 匹配 | 相关度 |")
    lines.append("|---|--------|------|------|------|------|--------|")

    for i, f in enumerate(downloaded, 1):
        matched_mark = "✓" if f.get("matched") else ""
        size_kb = f.get("size", 0) / 1024
        score = f.get("score", 0)
        lines.append(
            f"| {i} | [{f['filename']}](./{f['filename']}) | "
            f"{f.get('caseNo', '?')} | "
            f"{(f.get('title') or '')[:40]} | "
            f"{size_kb:.1f} KB | "
            f"{matched_mark} | {score:.2f} |"
        )
    lines.append("")

    # 写入文件
    index_path = output_dir / "README.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return index_path


def main():
    parser = argparse.ArgumentParser(
        description="威科案例下载 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", "-i", help="搜索结果 JSON 文件路径")
    parser.add_argument("--query", help="（可选）新搜索并下载，如 '建设工程施工合同纠纷'")
    parser.add_argument("--format", "-f", choices=["pdf", "docx", "xls"],
                        default="pdf", help="下载格式（默认 pdf）")
    parser.add_argument("--output-dir", "-o", required=True, help="输出目录")
    parser.add_argument("--highlight", action="store_true",
                        help="（PDF 模式）添加匹配标记 / 文件名前缀加 [匹配]")
    parser.add_argument("--limit", type=int, help="限制下载数量")
    parser.add_argument("--index", action="store_true", help="生成 README.md 索引")
    args = parser.parse_args()

    # 1. 加载结果
    if args.input:
        results = load_results(args.input)
    elif args.query:
        # 直接搜索
        from search_cases import progressive_search
        client = WkinfoClient()
        fqs, _, count, _ = progressive_search(client, args.query, args.limit or 200, verbose=True)
        resp = client.search(
            query_string=args.query, filter_queries=fqs,
            page_limit=args.limit or 200
        )
        from wkinfo_api import parse_search_results
        results = parse_search_results(resp)
    else:
        print("[X] 必须指定 --input 或 --query")
        return 1

    if args.limit:
        results = results[:args.limit]
    print(f"\n准备下载 {len(results)} 个文件")
    print(f"格式: {args.format}")
    print(f"输出目录: {args.output_dir}")
    print("=" * 60)

    # 2. 下载
    client = WkinfoClient()
    output_dir = Path(args.output_dir)
    stats = download_results(
        results, client, output_dir,
        file_type=args.format,
        highlight=args.highlight,
        verbose=True,
    )

    print()
    print("=" * 60)
    print(f"完成: {stats['success']} 成功, {stats['failed']} 失败")

    # 3. 生成索引
    if args.index:
        index_path = generate_index(
            output_dir, stats["files"],
            query=args.query or "",
            mode=f"{args.format} ({len(results)} 个)"
        )
        if index_path:
            print(f"[+] 索引: {index_path}")

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())