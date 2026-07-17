# -*- coding: utf-8 -*-
"""
威科先行 Cookie 注入脚本 (Python 版)

功能:
    1. 启动一个独立的 Edge 实例（带远程调试端口 9222），使用隔离 profile
       - 不影响用户现有的 Edge 窗口
       - 与用户 Edge 共享登录态需要注入 cookie
    2. 注入 wkinfo-cli skill 共享的 cookies
    3. 验证登录状态；登录失败时引导用户手动登录并捕获新 cookie 写回 storage

使用:
    python install_cookies.py             # 启动/复用 Edge，注入 cookie
    python install_cookies.py --kill      # 杀全部 Edge 后再启动（破坏性）
    python install_cookies.py --verify    # 只验证当前 Edge 是否已登录
    python install_cookies.py --wait-login # 注入失败时挂起等待手动登录

前置条件:
    - pip install playwright
    - Edge 浏览器已安装

与 wkinfo-cli/Scripts/install_cookies.js 的差异:
    - Python 实现，统一项目脚本栈
    - 从 wkinfo-cli/storage/wkinfo-cookies.json 读取完整 17 个 cookie（更全）
    - 使用 Start-Process 启 Edge（兼容 Windows 锁定 profile 场景）
    - 支持挂起等待用户手动登录后写回新 cookie
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

# Windows 控制台编码修复（避免中文乱码）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[X] Playwright 未安装，请先运行: pip install playwright")
    sys.exit(1)


# ============ 配置 ============

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"

# 共享 wkinfo-cli skill 的 cookie 存储
WKINFO_COOKIE_FILE = Path.home() / ".claude" / "skills" / "wkinfo-cli" / "storage" / "wkinfo-cookies.json"

# 本项目独立 Edge profile（与用户主 Edge 隔离）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EDGE_PROFILE = PROJECT_ROOT / "临时资源" / "edge-debug-profile"

WKINFO_DOMAIN = "https://law.wkinfo.com.cn"
USERNAME_MARKER = "jtnfawkwechat"


# ============ 辅助函数 ============

def log(level: str, msg: str) -> None:
    icons = {"info": "[*]", "ok": "[+]", "warn": "[!]", "err": "[X]"}
    print(f"{icons.get(level, '[*]')} {msg}")


def run_powershell(cmd: str, timeout: int = 30) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def wait_for_port(url: str, timeout_ms: int = 45000) -> bool:
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            with urlopen(url + "/json/version", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (URLError, Exception):
            pass
        time.sleep(1)
    return False


def load_cookies_from_storage() -> list:
    if not WKINFO_COOKIE_FILE.exists():
        log("err", f"Cookie 文件不存在: {WKINFO_COOKIE_FILE}")
        sys.exit(1)

    with open(WKINFO_COOKIE_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    log("ok", f"从 {WKINFO_COOKIE_FILE} 加载 {len(cookies)} 个 cookie")
    return cookies


def save_cookies_to_storage(cookies: list) -> None:
    WKINFO_COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WKINFO_COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    log("ok", f"已写回 {len(cookies)} 个 cookie 到 {WKINFO_COOKIE_FILE}")


# ============ Edge 生命周期 ============

def kill_all_edge() -> None:
    log("warn", "关闭所有 Edge 进程...")
    run_powershell("Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force")
    time.sleep(2)
    remaining = run_powershell("(Get-Process msedge -ErrorAction SilentlyContinue | Measure-Object).Count")
    log("info", f"   剩余 msedge.exe 进程: {remaining or '0'}")


def start_isolated_edge_with_debug() -> None:
    """启动隔离 profile 的 Edge，带调试端口。不杀现有 Edge。"""
    if wait_for_port(CDP_URL, 2000):
        log("ok", "CDP 端口已运行，直接复用")
        return

    if not Path(EDGE_PATH).exists():
        log("err", f"Edge 未找到: {EDGE_PATH}")
        sys.exit(1)

    EDGE_PROFILE.mkdir(parents=True, exist_ok=True)

    # 用 PowerShell Start-Process 启动（Python Popen 在 Windows 上对 Edge 不友好）
    args = (
        f'Start-Process "{EDGE_PATH}" '
        f'-ArgumentList '
        f'"--remote-debugging-port={CDP_PORT}",'
        f'"--no-first-run",'
        f'"--no-default-browser-check",'
        f'"--user-data-dir={EDGE_PROFILE}" '
        f'-WindowStyle Hidden'
    )
    log("info", f"启动隔离 Edge（profile: {EDGE_PROFILE}）...")
    run_powershell(args, timeout=10)

    if not wait_for_port(CDP_URL, 45000):
        log("err", "Edge 启动超时（45秒）")
        sys.exit(1)
    log("ok", "Edge 已就绪")


# ============ Cookie 注入与验证 ============

def inject_cookies_and_verify(cookies: list, wait_for_login: bool = False) -> bool:
    log("info", "连接 Edge 并注入 Cookies...")
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]

        old_wkinfo = [c for c in context.cookies() if "wkinfo" in (c.get("domain") or "")]
        if old_wkinfo:
            context.clear_cookies(domain=".law.wkinfo.com.cn")
            log("info", f"   已清除旧 wkinfo cookies: {len(old_wkinfo)} 个")

        now = int(time.time())
        formatted = []
        for c in cookies:
            formatted.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".law.wkinfo.com.cn"),
                "path": c.get("path", "/"),
                "expires": now + 86400 * 365,
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": c.get("sameSite", "Lax"),
            })
        context.add_cookies(formatted)
        log("ok", f"   已注入 {len(formatted)} 个 cookies")

        page = context.new_page()
        page.goto(WKINFO_DOMAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        body_text = page.text_content("body") or ""
        logged_in = USERNAME_MARKER in body_text

        print()
        print("=" * 60)
        print(f"  登录状态: {'[OK] 已登录 (' + USERNAME_MARKER + ')' if logged_in else '[X] 未登录'}")
        print("=" * 60)

        if not logged_in:
            if wait_for_login:
                print()
                print("[!] 存储的 cookie 已过期。请在打开的 Edge 中手动登录威科先行。")
                print("    登录成功后，本脚本会自动捕获新 cookie 并写回 storage。")
                print("    等待登录（最长 5 分钟）...")

                deadline = time.time() + 300
                while time.time() < deadline:
                    time.sleep(5)
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2000)
                        body_text = page.text_content("body") or ""
                        if USERNAME_MARKER in body_text:
                            logged_in = True
                            break
                    except Exception:
                        continue

                if logged_in:
                    print("[OK] 检测到登录成功!")
                    new_cookies = context.cookies()
                    wkinfo_cookies = [c for c in new_cookies if "wkinfo" in (c.get("domain") or "")]
                    if wkinfo_cookies:
                        save_cookies_to_storage(wkinfo_cookies)
                else:
                    print("[X] 5 分钟内未检测到登录，请稍后手动重试。")
            else:
                print()
                print("[!] 存储的 cookie 已过期，请使用 --wait-login 参数等待手动登录。")

        if logged_in:
            print()
            print("Cookie 注入成功!Edge 调试实例可继续用于威科自动化。")

        print()
        print("Edge 调试实例保持运行中（独立 profile），可直接使用。")

        return logged_in


def verify_only() -> bool:
    """只验证当前 Edge 是否已登录（不注入）"""
    if not wait_for_port(CDP_URL, 2000):
        log("err", f"CDP 端口 {CDP_PORT} 未启动，请先运行 install_cookies.py")
        return False

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_PORT)
        context = browser.contexts[0]
        page = context.new_page()
        page.goto(WKINFO_DOMAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        body_text = page.text_content("body") or ""
        logged_in = USERNAME_MARKER in body_text
        print(f"登录状态: {'已登录' if logged_in else '未登录'}")
        return logged_in


# ============ 主函数 ============

def main() -> int:
    parser = argparse.ArgumentParser(
        description="威科先行 Cookie 注入工具 (Python 版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--kill", action="store_true",
                        help="关闭所有 Edge 进程再启动（破坏性，慎用）")
    parser.add_argument("--verify", action="store_true",
                        help="只验证当前 Edge 是否已登录（不注入）")
    parser.add_argument("--wait-login", action="store_true",
                        help="登录失败时挂起等待手动登录，登录成功自动写回新 cookie")
    args = parser.parse_args()

    print("威科先行 Cookie 注入工具 (Python 版)")
    print("=" * 60)

    if args.verify:
        return 0 if verify_only() else 1

    if not WKINFO_COOKIE_FILE.exists():
        log("err", f"Cookie 文件不存在: {WKINFO_COOKIE_FILE}")
        return 1

    try:
        cookies = load_cookies_from_storage()
        if args.kill:
            kill_all_edge()
        start_isolated_edge_with_debug()
        success = inject_cookies_and_verify(cookies, wait_for_login=args.wait_login)
        return 0 if success else 1
    except Exception as e:
        log("err", f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())