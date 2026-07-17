# -*- coding: utf-8 -*-
"""PDF 高亮标注工具

在 PDF 文档首页添加一个黄色标签注释，标注：
- 匹配关键字
- 搜索查询
- 时间戳

用法：
  python highlight_pdf.py ./原始文件/案例/pdfs/*.pdf --keyword "实际施工人"
  python highlight_pdf.py ./原始文件/案例/pdfs/ --keyword "实际施工人"
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        RectangleObject, NameObject, NumberObject,
        TextStringObject, DictionaryObject, ArrayObject,
        BooleanObject,
    )
except ImportError:
    print("[X] pypdf 未安装: pip install pypdf")
    sys.exit(1)


def add_sticky_note(
    pdf_path: Path,
    output_path: Optional[Path] = None,
    note_text: str = "✓ 匹配",
    page_index: int = 0,
    position: tuple = (400, 700),  # x, y (PDF 坐标，从左下角起)
) -> bool:
    """在 PDF 指定页添加黄色便签注释"""
    if output_path is None:
        output_path = pdf_path.parent / (pdf_path.stem + "_highlighted.pdf")

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # 创建便签注释（sticky note）
    note = DictionaryObject()
    note[NameObject("/Type")] = NameObject("/Annot")
    note[NameObject("/Subtype")] = NameObject("/Text")
    note[NameObject("/Rect")] = RectangleObject([
        position[0], position[1],
        position[0] + 24, position[1] + 24
    ])
    note[NameObject("/Contents")] = TextStringObject(note_text)
    note[NameObject("/Open")] = BooleanObject(True)  # 修复 pypdf 5.0+ 兼容性
    note[NameObject("/Color")] = ArrayObject([
        NumberObject(255),
        NumberObject(255),
        NumberObject(0)  # Yellow
    ])
    # 在首页添加
    if page_index < len(writer.pages):
        first_page = writer.pages[page_index]
        if "/Annots" not in first_page:
            first_page[NameObject("/Annots")] = ArrayObject()
        first_page["/Annots"].append(note)

    with open(output_path, "wb") as f:
        writer.write(f)

    return True


def highlight_files(file_paths: list, keyword: str = "", output_dir: Optional[Path] = None) -> dict:
    """批量高亮 PDF 文件"""
    stats = {"success": 0, "failed": 0, "files": []}
    note_text = f"✓ 匹配: {keyword}" if keyword else "✓ 匹配"
    note_text += f"\n[{datetime.now().strftime('%Y-%m-%d')}]"

    for pdf in file_paths:
        pdf_path = Path(pdf)
        if not pdf_path.exists():
            print(f"[X] 文件不存在: {pdf}")
            stats["failed"] += 1
            continue

        try:
            out = None
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                # 避免重复添加 [匹配]_ 前缀
                base = pdf_path.name
                if not base.startswith("[匹配]_"):
                    base = f"[匹配]_{base}"
                out = output_dir / base
            if add_sticky_note(pdf_path, output_path=out, note_text=note_text):
                print(f"[+] {pdf_path.name}")
                stats["success"] += 1
                stats["files"].append(str(out or pdf_path))
        except Exception as e:
            print(f"[X] {pdf_path.name}: {e}")
            stats["failed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="PDF 高亮标注工具")
    parser.add_argument("inputs", nargs="+", help="PDF 文件或目录路径")
    parser.add_argument("--keyword", "-k", default="", help="匹配关键词（写入便签文本）")
    parser.add_argument("--output-dir", "-o", help="输出目录（默认覆盖源文件）")
    args = parser.parse_args()

    # 收集所有 PDF 文件
    pdfs = []
    for inp in args.inputs:
        p = Path(inp)
        if p.is_dir():
            pdfs.extend(p.glob("*.pdf"))
        elif p.suffix.lower() == ".pdf":
            pdfs.append(p)
        else:
            print(f"[!] 跳过: {p}")

    if not pdfs:
        print("[X] 未找到 PDF 文件")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else None
    stats = highlight_files(pdfs, keyword=args.keyword, output_dir=output_dir)

    print()
    print(f"完成: {stats['success']} 成功, {stats['failed']} 失败")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())