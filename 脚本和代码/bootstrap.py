#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
威科 Skill 一键引导（agent / 朋友首次克隆时用）

agent 检测到 wkinfo-cookies.json 不存在时调这个脚本，它会：
  1. 检查 Python 版本（>=3.8）
  2. 自动 pip install playwright requests pypdf
  3. 自动 playwright install chromium（如缺）
  4. 创建 ~/.claude/skills/wkinfo-cli/storage/ 目录
  5. 启动浏览器引导用户登录威科（用户自己输入账号密码）
  6. 自动保存 cookie 到 storage
  7. 装 Git 钩子（post-commit auto-sync）
  8. 跑端到端验证

设计原则：
- agent 调用 = 用户看一行进度信息
- 唯一需要用户亲手做的：在弹出的浏览器里登录威科
- 完成后所有依赖、cookie、钩子、profile 都就位

使用：
  python 脚本和代码/bootstrap.py
  python 脚本和代码/bootstrap.py --check-only   # 只检查，不装
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

# Windows 控制台编码修复
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ["PYTHONIOENCODING"] = "utf-8"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COOKIE_FILE = Path.home() / ".claude" / "skills" / "wkinfo-cli" / "storage" / "wkinfo-cookies.json"
SKILL_INSTALL_DIR = Path.home() / ".claude" / "skills" / "威科案例检索和下载"


# ============ 检查函数 ============

def step(name: str) -> None:
    """打印步骤标题"""
    print()
    print("=" * 60)
    print(f"  [{name}]")
    print("=" * 60)


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def info(msg: str) -> None:
    print(f"  [INFO] {msg}")


def run(cmd: list, check: bool = True, **kwargs) -> bool:
    """运行命令，返回是否成功"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=kwargs.get("timeout", 300))
        if check and result.returncode != 0:
            return False
        return True
    except Exception:
        return False


def check_python_version() -> bool:
    """Python >= 3.8"""
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 8):
        fail(f"Python {v.major}.{v.minor} 太旧，需要 >= 3.8")
        return False
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
    return True


def check_pip_available() -> bool:
    """检查 pip 是否可用"""
    return run([sys.executable, "-m", "pip", "--version"], check=False)


def check_python_packages() -> bool:
    """检查 playwright / requests / pypdf 是否都装了"""
    missing = []
    for pkg in ["playwright", "requests", "pypdf"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        info(f"缺: {', '.join(missing)}")
        return False
    ok("playwright / requests / pypdf 都已装")
    return True


def check_chromium() -> bool:
    """检查 Playwright chromium 是否下载"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            path = pw.chromium.executable_path
            if path and Path(path).exists():
                ok(f"chromium: {path}")
                return True
        fail("chromium 未下载")
        return False
    except Exception as e:
        fail(f"chromium 检查失败: {e}")
        return False


def check_cookies() -> bool:
    """检查 cookies.json 是否存在且非空"""
    if not COOKIE_FILE.exists():
        info(f"Cookie 文件不存在: {COOKIE_FILE}")
        return False
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if not cookies:
            info("Cookie 文件为空")
            return False
        ok(f"Cookie 文件存在，{len(cookies)} 个 cookie")
        return True
    except Exception as e:
        fail(f"Cookie 文件损坏: {e}")
        return False


def check_skill_synced() -> bool:
    """检查 skill 安装目录是否与项目一致"""
    if not SKILL_INSTALL_DIR.exists():
        info(f"Skill 装目录不存在: {SKILL_INSTALL_DIR}")
        return False
    # 对比关键文件
    for rel in ["wkinfo_api.py", "research.py", "sync.py", "SKILL.md"]:
        proj = PROJECT_ROOT / "脚本和代码" / rel if rel.endswith(".py") else PROJECT_ROOT / rel
        if rel in ("wkinfo_api.py", "research.py", "sync.py"):
            skill = SKILL_INSTALL_DIR / "scripts" / rel
        else:
            skill = SKILL_INSTALL_DIR / rel
        if not skill.exists():
            info(f"Skill 缺 {rel}")
            return False
    ok("Skill 装目录齐备")
    return True


def check_git_hook() -> bool:
    """检查 post-commit 钩子是否安装"""
    hook = PROJECT_ROOT / ".git" / "hooks" / "post-commit"
    if not hook.exists():
        info("post-commit 钩子未装")
        return False
    ok(f"post-commit 钩子已装: {hook.name}")
    return True


# ============ 安装动作 ============

def install_python_packages() -> bool:
    step("1/5 安装 Python 包")
    return run([sys.executable, "-m", "pip", "install", "playwright", "requests", "pypdf"], timeout=300)


def install_chromium() -> bool:
    step("2/5 下载 Playwright chromium")
    return run([sys.executable, "-m", "playwright", "install", "chromium"], timeout=300)


def setup_wkinfo_cli_skill() -> bool:
    step("3/5 准备 wkinfo-cli skill cookie 目录")
    try:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ok(f"目录就绪: {COOKIE_FILE.parent}")
        return True
    except Exception as e:
        fail(f"创建目录失败: {e}")
        return False


def prompt_user_login() -> bool:
    """引导用户登录威科（调 login_wkinfo.py）"""
    step("4/5 引导用户登录威科")
    print()
    print("  ⚠ 接下来浏览器会自动打开威科首页")
    print("  ⚠ 请在浏览器里用你自己的威科账号登录")
    print("  ⚠ 登录成功会自动检测（约 5-30 秒）")
    print()
    try:
        # 调用 login_wkinfo.py
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "脚本和代码" / "login_wkinfo.py")],
            timeout=600,
        )
        return result.returncode == 0
    except Exception as e:
        fail(f"登录脚本异常: {e}")
        return False


def install_git_hook() -> bool:
    step("5/5 装 Git post-commit 钩子")
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "脚本和代码" / "install_hooks.py")],
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        fail(f"装钩子失败: {e}")
        return False


# ============ 主流程 ============

def run_full_install() -> bool:
    print()
    print("=" * 60)
    print("  威科 Skill 一键引导")
    print("=" * 60)
    print()
    print(f"  项目: {PROJECT_ROOT}")
    print(f"  系统: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version.split()[0]}")
    print()

    # 1. Python 版本
    step("0/5 检查 Python 版本")
    if not check_python_version():
        return False

    # 2. Python 包
    if not check_python_packages():
        if not install_python_packages():
            fail("Python 包安装失败")
            return False
        # 重新检查
        if not check_python_packages():
            fail("Python 包安装后仍缺失")
            return False
    else:
        info("Python 包已就绪")

    # 3. Chromium
    if not check_chromium():
        if not install_chromium():
            fail("chromium 下载失败")
            return False
        if not check_chromium():
            fail("chromium 下载后仍缺失")
            return False
    else:
        info("chromium 已就绪")

    # 4. Skill 同步
    if not check_skill_synced():
        info("Skill 未同步，跑 sync.py")
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "脚本和代码" / "sync.py")],
            timeout=60,
        )
        if result.returncode != 0:
            fail("Skill 同步失败")
            return False
        if not check_skill_synced():
            fail("Skill 同步后仍不完整")
            return False
    else:
        info("Skill 已同步")

    # 5. 引导登录
    if not check_cookies():
        info("Cookie 不存在或为空，引导用户登录...")
        if not setup_wkinfo_cli_skill():
            return False
        if not prompt_user_login():
            fail("登录失败")
            return False
        if not check_cookies():
            fail("登录后 Cookie 仍未保存")
            return False
    else:
        ok("Cookie 已存在，跳过登录")

    # 6. 装钩子
    if not check_git_hook():
        if not install_git_hook():
            fail("钩子安装失败")
            return False
    else:
        info("Git 钩子已装")

    # 总结
    print()
    print("=" * 60)
    print("  ✓ 安装完成！")
    print("=" * 60)
    print()
    print("  下一步:")
    print("  python 脚本和代码/research.py --query \"公司\" --mode detail")
    print()
    return True


def run_check_only() -> bool:
    print()
    print("=" * 60)
    print("  威科 Skill 安装检查（check-only）")
    print("=" * 60)
    print()

    results = []
    results.append(("Python 版本", check_python_version()))
    if not check_python_packages():
        results.append(("Python 包（playwright/requests/pypdf）", False))
    else:
        results.append(("Python 包", True))
    if not check_chromium():
        results.append(("Playwright chromium", False))
    else:
        results.append(("Playwright chromium", True))
    results.append(("wkinfo-cli skill cookie 目录", setup_wkinfo_cli_skill()))
    if not check_cookies():
        results.append(("Cookie 文件", False))
    else:
        results.append(("Cookie 文件", True))
    results.append(("Skill 同步", check_skill_synced()))
    results.append(("Git 钩子", check_git_hook()))

    print()
    print("=" * 60)
    print("  结果")
    print("=" * 60)
    all_ok = True
    for name, ok_ in results:
        mark = "✓" if ok_ else "✗"
        print(f"  [{mark}] {name}")
        if not ok_:
            all_ok = False
    print()
    if all_ok:
        print("  全部就绪！")
    else:
        print("  缺上面 ✗ 项。跑 `python 脚本和代码/bootstrap.py` 装齐。")
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="威科 Skill 一键引导（agent/朋友首次克隆时用）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--check-only", action="store_true",
                        help="只检查环境，不安装")
    args = parser.parse_args()

    if args.check_only:
        return 0 if run_check_only() else 1
    else:
        return 0 if run_full_install() else 1


if __name__ == "__main__":
    sys.exit(main())
