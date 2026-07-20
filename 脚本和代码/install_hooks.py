# -*- coding: utf-8 -*-
"""
一次性安装 Git 钩子（post-commit 自动同步）

运行：python scripts/install_hooks.py
效果：在 .git/hooks/post-commit 创建符号链接/复制 → 指向 scripts/hooks/post-commit
之后每次 git commit 后会自动跑 sync.py 推送到 skill 安装位置。

卸载：python scripts/install_hooks.py --uninstall
"""
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOKS_SOURCE_DIR = PROJECT_ROOT / "脚本和代码" / "hooks"
GIT_HOOKS_DIR = PROJECT_ROOT / ".git" / "hooks"

HOOKS = ["post-commit", "pre-commit"]  # 预留 pre-commit 位置


def install():
    GIT_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for name in HOOKS:
        src = HOOKS_SOURCE_DIR / name
        dst = GIT_HOOKS_DIR / name

        if not src.exists():
            print(f"[!] 源钩子不存在: {src}，跳过")
            continue

        # 已有钩子 → 备份
        if dst.exists() or dst.is_symlink():
            backup = dst.with_suffix(dst.suffix + ".bak")
            if backup.exists():
                backup.unlink()
            dst.rename(backup)
            print(f"[*] 已备份旧钩子: {dst.name} -> {dst.name}.bak")

        # Windows 下 shutil.copy 不用 symlink，更稳
        shutil.copy2(src, dst)
        # 让 Git 识别为可执行
        if hasattr(os, "chmod"):
            os.chmod(dst, 0o755)
        print(f"[+] 已安装钩子: {dst.name} -> {src.relative_to(PROJECT_ROOT)}")

    print()
    print("[OK] 安装完成。测试一下:")
    print("     git commit --allow-empty -m 'test hook'")
    print("     应该看到 [post-commit-hook] auto-sync: ... 的输出")


def uninstall():
    for name in HOOKS:
        dst = GIT_HOOKS_DIR / name
        if dst.is_symlink() or dst.exists():
            dst.unlink()
            print(f"[-] 已卸载: {dst.name}")
        bak = dst.with_suffix(dst.suffix + ".bak")
        if bak.exists():
            bak.rename(dst)
            print(f"[+] 恢复备份: {dst.name}")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
