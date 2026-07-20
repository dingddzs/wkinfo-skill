# -*- coding: utf-8 -*-
"""
项目 <-> Skill 安装位置同步脚本

解决问题：代码修改在项目文件夹，Claude 实际从 ~/.claude/skills/ 加载。
两者结构不同（脚本和代码/ vs scripts/，处理后文件/ 在 skill 里是 *.*），
手动 cp 容易漏。

用法：
    python scripts/sync.py             # 项目 -> skill 安装（默认 push）
    python scripts/sync.py --push      # 项目 -> skill 安装（显式）
    python scripts/sync.py --pull      # skill 安装 -> 项目
    python scripts/sync.py --check     # 只比较不复制，显示差异
    python scripts/sync.py --dry-run   # 比较但不写

文件映射（硬编码）：
    脚本和代码/*.py     ->  scripts/*.py
    references/*.md      ->  references/*.md
    SKILL.md             ->  SKILL.md
    处理后文件/*.json    ->  *.json          （案由词典等）
"""
import argparse
import filecmp
import hashlib
import shutil
import sys
from pathlib import Path

# Windows 控制台编码修复
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = Path.home() / ".claude" / "skills" / "威科案例检索和下载"

# 路径级硬排除（不被 .gitignore 干扰的"绝对不进"列表）
# 涵盖 gitignore 没覆盖但不应该 sync 的：
#   - .git 目录（git 内部）
#   - __pycache__（运行时）
#   - 临时资源/ 整体（Edge profile + 截图，100+ MB）
#   - 原始文件/ 处理后文件/（用户数据）
HARD_EXCLUDE_TOPDIRS = {
    ".git", "__pycache__",
    "临时资源",   # 包含 edge-debug-profile/截图/调试日志
    "原始文件",   # 用户产出
    "处理后文件", # AI 处理输出
}

# 项目 -> skill 文件映射
# key: project-relative path   value: skill-relative path
PROJECT_TO_SKILL = {
    "脚本和代码": "scripts",
    "references": "references",
    "处理后文件": ".",  # 平铺到 skill 根
    "SKILL.md": "SKILL.md",
}

# 这些文件**不进** skill（只属于项目）
SKIP_FROM_SYNC = {
    "PROJECT_GUIDE.md", "CHANGELOG.md", "README.md",
    "开发日志.md",
    ".gitignore", ".gitattributes",
    ".git",
}

# skill 安装位置独有的（不需要从项目 sync 过去）
SKILL_ONLY = {
    "script-development-log.md",  # 动态加载日志（如有）
}


def is_excluded(rel: Path) -> bool:
    """统一排除规则：硬排除 + 名称级跳过（递归检查所有父目录）"""
    parts = rel.parts
    if not parts:
        return True
    # 递归：路径任何一段是排除目录，就跳过
    for p in parts:
        if p in HARD_EXCLUDE_TOPDIRS:
            return True
    # 名称级跳过
    if rel.name in SKIP_FROM_SYNC:
        return True
    return False


def files_equal(p1: Path, p2: Path) -> bool:
    """比较两个文件内容是否完全相同（用 filecmp，效率高且能比较整个文件）"""
    try:
        return filecmp.cmp(str(p1), str(p2), shallow=False)
    except Exception:
        return False


def sha256_short(path: Path) -> str:
    """快速 hash（只读前 8KB，对调试脚本足够）"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            h.update(f.read(8192))
        return h.hexdigest()[:16]
    except Exception:
        return "????????????????"


def project_to_skill_path(rel: Path) -> Path:
    """把项目内相对路径转成 skill 内路径"""
    parts = rel.parts
    if not parts:
        return SKILL_ROOT

    if parts[0] in PROJECT_TO_SKILL:
        # 第一个段是 mapped 的目录（脚本和代码 / references / 处理后文件）
        target_subdir = PROJECT_TO_SKILL[parts[0]]
        rest = parts[1:]
        if target_subdir == ".":
            return SKILL_ROOT / "/".join(rest) if rest else SKILL_ROOT
        return SKILL_ROOT / target_subdir / "/".join(rest)
    elif parts[0] in SKIP_FROM_SYNC:
        # 这些不应该 sync 到 skill
        return None
    elif "/" not in str(rel):
        # 顶层文件（如 SKILL.md）
        if parts[0] == "SKILL.md":
            return SKILL_ROOT / "SKILL.md"
        return None
    else:
        return None


def skill_to_project_path(rel: Path) -> Path:
    """把 skill 内相对路径转成项目内路径"""
    parts = rel.parts
    if not parts:
        return PROJECT_ROOT

    # 逆向映射
    if parts[0] == "scripts":
        return PROJECT_ROOT / "脚本和代码" / "/".join(parts[1:])
    elif parts[0] == "references":
        return PROJECT_ROOT / "references" / "/".join(parts[1:])
    elif "/" not in str(rel) or len(parts) == 1:
        # 顶层文件
        if parts[0] == "SKILL.md":
            return PROJECT_ROOT / "SKILL.md"
        if parts[0].endswith(".json"):
            return PROJECT_ROOT / "处理后文件" / parts[0]
        # 其他顶层文件（如已删除的旧 json、script-development-log.md）
        return PROJECT_ROOT / parts[0]  # 兜底
    else:
        return None


def sync_push(dry_run: bool = False):
    """项目 -> skill 安装"""
    synced = []
    skipped = []

    for p in PROJECT_ROOT.rglob("*"):
        if not p.is_file():
            continue

        rel = p.relative_to(PROJECT_ROOT)
        if is_excluded(rel):
            continue

        skill_path = project_to_skill_path(rel)
        if skill_path is None:
            continue

        if not skill_path.parent.exists():
            if not dry_run:
                skill_path.parent.mkdir(parents=True, exist_ok=True)

        if skill_path.exists():
            if files_equal(p, skill_path):
                continue  # 一致，跳过

        if dry_run:
            synced.append(f"  would copy: {rel} -> {skill_path.relative_to(SKILL_ROOT)}")
        else:
            shutil.copy2(p, skill_path)
            synced.append(f"  copied: {rel}")

    return synced, skipped


def sync_pull(dry_run: bool = False):
    """skill 安装 -> 项目"""
    synced = []

    for p in SKILL_ROOT.rglob("*"):
        if not p.is_file():
            continue

        rel = p.relative_to(SKILL_ROOT)
        # 排除 skill 独有 / 项目不该有的
        if rel.parts[0] in {".git"} or rel.name in SKILL_ONLY:
            continue
        # 顶层目录硬排除
        if rel.parts[0] in HARD_EXCLUDE_TOPDIRS:
            continue

        proj_path = skill_to_project_path(rel)
        if proj_path is None:
            continue

        if not proj_path.parent.exists():
            if not dry_run:
                proj_path.parent.mkdir(parents=True, exist_ok=True)

        if proj_path.exists():
            if files_equal(p, proj_path):
                continue

        if dry_run:
            synced.append(f"  would copy: {rel} -> {proj_path.relative_to(PROJECT_ROOT)}")
        else:
            shutil.copy2(p, proj_path)
            synced.append(f"  copied: {rel}")

    return synced


def main():
    parser = argparse.ArgumentParser(
        description="项目 <-> Skill 安装位置同步",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--push", action="store_true",
                        help="项目 -> skill 安装（默认）")
    parser.add_argument("--pull", action="store_true",
                        help="skill 安装 -> 项目")
    parser.add_argument("--check", action="store_true",
                        help="只比较不复制")
    parser.add_argument("--dry-run", action="store_true",
                        help="检查会做什么但不写")
    args = parser.parse_args()

    direction = "pull" if args.pull else "push"

    print("=" * 60)
    print(f"项目路径:    {PROJECT_ROOT}")
    print(f"Skill 安装:   {SKILL_ROOT}")
    print(f"方向:        {'项目 -> skill' if direction == 'push' else 'skill -> 项目'}")
    print(f"模式:        {'DRY-RUN' if args.check or args.dry_run else '实际复制'}")
    print("=" * 60)
    print()

    if direction == "push":
        synced, skipped = sync_push(dry_run=args.check or args.dry_run)
    else:
        synced = sync_pull(dry_run=args.check or args.dry_run)

    if synced:
        print("差异文件：")
        for line in synced:
            print(line)
        print()
        if not (args.check or args.dry_run):
            print(f"已同步 {len(synced)} 个文件")
        else:
            print(f"(dry-run，未实际复制)")
    else:
        print("✓ 两个位置已一致，无需同步")

    print()
    return 0 if (synced or not args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
