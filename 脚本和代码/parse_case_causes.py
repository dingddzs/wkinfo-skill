# -*- coding: utf-8 -*-
"""解析《民事案件案由规定》(2025版) 全文 -> 结构化 JSON

输入: 临时资源/OCR/案由规定_2025版_全文.txt (antiword 提取的文本)
输出: 处理后文件/民事案由_2025.json

JSON 结构:
[
  {
    "part": "第一部分",
    "part_name": "人格权纠纷",
    "categories": [
      {
        "code": "一",
        "name": "人格权纠纷",
        "causes": [
          {
            "code": "1",
            "name": "生命权、身体权、健康权纠纷",
            "aliases": ["生命权纠纷", "身体权纠纷", "健康权纠纷"],
            "sub_causes": []
          },
          {
            "code": "8",
            "name": "隐私权、个人信息保护纠纷",
            "aliases": ["隐私权纠纷", "个人信息保护纠纷"],
            "sub_causes": [
              {"code": "1", "name": "隐私权纠纷"},
              {"code": "2", "name": "个人信息保护纠纷"}
            ]
          }
        ]
      }
    ]
  }
]
"""
import json
import re
from pathlib import Path

INPUT = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\OCR\案由规定_2025版_全文.txt")
OUTPUT = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\处理后文件\民事案由_2025.json")

# 正则模式
PART_PATTERN = re.compile(r"^第([一二三四五六七八九十百]+)部分\s+(.+)$")
LEVEL2_PATTERN = re.compile(r"^([一二三四五六七八九十]{1,3})\s*[、\.]\s*(.+)$")  # 一、二、三... 用作第二级，允许空格
LEVEL3_PATTERN = re.compile(r"^(\d+)\s*\.\s*(.+)$")  # 允许数字和点之间的空格
LEVEL4_PATTERN = re.compile(r"^（(\d+)）\s*(.+)$")

# 正文开始标记（"规定如下："之后的"第一部分"才是真正的案由体系）
BODY_START_MARKER = "规定如下"


def split_alternative_names(name: str) -> tuple:
    """拆分顿号分隔的并列名称，返回 (主名, [别名])"""
    if "、" in name:
        parts = [p.strip() for p in name.split("、")]
        main = parts[0] + "纠纷"  # 第一个作为主名，加"纠纷"后缀
        # 实际上原文可能是 "生命权、身体权、健康权纠纷"，主名是整段
        # 别名是各种拆法
        aliases = []
        for p in parts:
            if not p.endswith("纠纷"):
                p += "纠纷"
            aliases.append(p)
        return name, aliases
    return name, []


def main():
    if not INPUT.exists():
        print(f"[X] 输入文件不存在: {INPUT}")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    parts = []  # 最终结构
    current_part = None
    current_category = None
    current_cause = None
    in_body = False  # 是否已到达正文

    with open(INPUT, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.rstrip()
            if not line.strip():
                continue

            # 检测正文开始标记
            if not in_body:
                if BODY_START_MARKER in line:
                    in_body = True
                continue  # 跳过目录部分

            # 试匹配 Part
            m = PART_PATTERN.match(line.strip())
            if m:
                part_num_cn = m.group(1)
                part_name = m.group(2).strip()
                current_part = {
                    "part": f"第{part_num_cn}部分",
                    "part_name": part_name,
                    "categories": []
                }
                parts.append(current_part)
                current_category = None
                current_cause = None
                continue

            # 试匹配 Level 2 (一二三...、)
            m = LEVEL2_PATTERN.match(line.strip())
            if m and not LEVEL3_PATTERN.match(line.strip()):
                cat_code = m.group(1)
                cat_name = m.group(2).strip()
                if current_part is None:
                    continue
                current_category = {
                    "code": cat_code,
                    "name": cat_name,
                    "causes": []
                }
                current_part["categories"].append(current_category)
                current_cause = None
                continue

            # 试匹配 Level 3 (1. 2. 3.)
            m = LEVEL3_PATTERN.match(line.strip())
            if m:
                cause_code = m.group(1)
                cause_name = m.group(2).strip()
                main_name, aliases = split_alternative_names(cause_name)
                if current_category is None:
                    continue
                current_cause = {
                    "code": cause_code,
                    "name": main_name,
                    "raw_name": cause_name,
                    "aliases": aliases,
                    "sub_causes": []
                }
                current_category["causes"].append(current_cause)
                continue

            # 试匹配 Level 4 (（1）（2）)
            m = LEVEL4_PATTERN.match(line.strip())
            if m:
                sub_code = m.group(1)
                sub_name = m.group(2).strip()
                if current_cause is None:
                    continue
                current_cause["sub_causes"].append({
                    "code": sub_code,
                    "name": sub_name
                })
                continue

    # 写 JSON
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(parts, f, ensure_ascii=False, indent=2)

    # 统计
    total_parts = len(parts)
    total_categories = sum(len(p["categories"]) for p in parts)
    total_causes = sum(len(c["causes"]) for p in parts for c in p["categories"])
    total_subs = sum(
        len(s["sub_causes"]) for p in parts for c in p["categories"] for s in c["causes"]
    )

    print(f"[OK] 写入: {OUTPUT}")
    print(f"  - Part (第一级): {total_parts}")
    print(f"  - Category (第二级): {total_categories}")
    print(f"  - Cause (第三级): {total_causes}")
    print(f"  - Sub-cause (第四级): {total_subs}")

    # 验证: 找建设工程相关
    for p in parts:
        for c in p["categories"]:
            for cause in c["causes"]:
                if "建设工程" in cause["name"] or "建设工程" in cause.get("raw_name", ""):
                    print(f'\n[匹配] Part: {p["part"]} {p["part_name"]}')
                    print(f'       Category: {c["code"]}、{c["name"]}')
                    print(f'       Cause: {cause["code"]}.{cause["name"]}')
                    for sub in cause["sub_causes"]:
                        print(f'         ({sub["code"]}) {sub["name"]}')


if __name__ == "__main__":
    main()