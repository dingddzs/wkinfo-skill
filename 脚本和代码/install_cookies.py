#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
威科先行 Cookie 注入脚本 (Python 版, 跨平台)

功能:
    1. 启动一个独立的浏览器实例（带远程调试端口 9222），使用隔离 profile
       - 不影响用户现有的浏览器窗口
       - 跨平台：Windows 用 Edge，macOS 用 Chrome，Linux 用 Chromium
    2. 注入 wkinfo-cli skill 共享的 cookies
    3. 验证登录状态；登录失败时引导用户手动登录并捕获新 cookie 写回 storage

使用:
    python install_cookies.py                       # 自动检测系统浏览器并启动
    python install_cookies.py --browser chrome      # 强制用 Chrome
    python install_cookies.py --browser edge        # 强制用 Edge
    python install_cookies.py --browser chromium    # 强制用 Playwright 自带 Chromium
    python install_cookies.py --kill               # 杀全部浏览器后再启动（破坏性）
    python install_cookies.py --verify             # 只验证当前浏览器是否已登录
    python install_cookies.py --wait-login         # 注入失败时挂起等待手动登录

前置条件:
    - pip install playwright requests
    - playwright install chromium
    - Windows 默认 Edge / macOS 默认 Chrome / Linux 装 Chromium

与 wkinfo-cli/Scripts/install_cookies.js 的差异:
    - Python 实现，跨平台
    - 从 wkinfo-cli/storage/wkinfo-cookies.json 读取完整 17 个 cookie
    - 支持 --browser 参数跨平台切换
"""
import argparse
import json
import os
import platform
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


# ============ 跨平台配置 ============

CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"

# 各平台默认浏览器路径
DEFAULT_BROWSER_PATHS = {
    "win32": {
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "chromium": None,  # 用 Playwright 自带
    },
    "darwin": {  # macOS
        "chrome": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ],
        "edge": [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
        "chromium": None,
    },
    "linux": {
        "chrome": [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/opt/google/chrome/chrome",
        ],
        "chromium": [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ],
        "edge": [
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
        ],
    },
}

# 共享 wkinfo-cli skill 的 cookie 存储
WKINFO_COOKIE_FILE = Path.home() / ".claude" / "skills" / "wkinfo-cli" / "storage" / "wkinfo-cookies.json"

# 本项目隔离 profile（避免污染用户主浏览器）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = PROJECT_ROOT / "临时资源" / "browser-debug-profile"

WKINFO_DOMAIN = "https://law.wkinfo.com.cn"
USERNAME_MARKER = "jtnfawkwechat"


# ============ 辅助函数 ============

def log(level: str, msg: str) -> None:
    icons = {"info": "[*]", "ok": "[+]", "warn": "[!]", "err": "[X]"}
    print(f"{icons.get(level, '[*]')} {msg}")


def find_browser_path(browser: str) -> "str | None":
    """根据浏览器类型 + 当前系统，找可执行文件路径"""
    paths = DEFAULT_BROWSER_PATHS.get(sys.platform, {}).get(browser, [])
    if paths is None:
        return None  # 用 Playwright 自带
    for p in paths:
        if Path(p).exists():
            return p
    return None


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


# ============ 浏览器生命周期（跨平台） ============

def kill_browsers(browser: str = "all") -> None:
    """关闭所有指定浏览器进程"""
    processes_by_browser = {
        "edge": {
            "win32": ["msedge.exe"],
            "darwin": ["Microsoft Edge"],
            "linux": ["microsoft-edge", "microsoft-edge-stable"],
        },
        "chrome": {
            "win32": ["chrome.exe"],
            "darwin": ["Google Chrome"],
            "linux": ["google-chrome", "google-chrome-stable", "chrome"],
        },
        "chromium": {
            "win32": ["chromium.exe"],
            "darwin": ["Chromium"],
            "linux": ["chromium", "chromium-browser"],
        },
    }

    if browser == "all":
        targets = set()
        for browser_procs in processes_by_browser.values():
            for proc in browser_procs.get(sys.platform, []):
                targets.add(proc)
        targets = list(targets)
    else:
        targets = processes_by_browser.get(browser, {}).get(sys.platform, [])

    log("warn", f"关闭 {len(targets)} 个浏览器进程...")
    for proc in targets:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", proc],
                              capture_output=True, timeout=10)
            else:
                subprocess.run(["pkill", "-9", "-f", proc], capture_output=True, timeout=10)
        except Exception:
            pass
    time.sleep(2)


def launch_browser_subprocess(browser_path: str, profile_dir: Path) -> subprocess.Popen:
    """跨平台启动浏览器（用 subprocess.Popen，不用 PowerShell）"""
    profile_dir.mkdir(parents=True, exist_ok=True)

    args = [
        browser_path,
        f"--remote-debugging-port={CDP_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
    ]

    # Windows：CREATE_NO_WINDOW 隐藏控制台
    if sys.platform == "win32":
        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    # macOS：直接启动 .app 内的二进制
    elif sys.platform == "darwin" and ".app/Contents/MacOS/" in browser_path:
        return subprocess.Popen(
            [browser_path] + args[1:],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    # Linux：直接启动
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def start_browser_with_debug(args) -> None:
    """启动隔离 profile 的浏览器，带调试端口"""
    if wait_for_port(CDP_URL, 2000):
        log("ok", "CDP 端口已运行，直接复用")
        return

    # 决定用哪个浏览器
    browser = args.browser
    if browser == "auto":
        browser = "edge" if sys.platform == "win32" else "chrome"

    browser_path = find_browser_path(browser)

    if browser_path:
        log("info", f"启动 {browser}（{browser_path}）...")
        try:
            launch_browser_subprocess(browser_path, PROFILE_DIR)
        except Exception as e:
            log("err", f"启动失败: {e}")
            log("info", "fallback: 改用 Playwright 自带 Chromium")
            browser_path = None
    else:
        if browser != "chromium":
            log("warn", f"本系统未找到 {browser}，fallback 到 Playwright 自带 Chromium")
        browser_path = None

    if not browser_path:
        # 用 Playwright 自带 Chromium
        try:
            log("info", "启动 Playwright 自带 Chromium...")
            with sync_playwright() as pw:
                browser_obj = pw.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    headless=False,
                    args=[f"--remote-debugging-port={CDP_PORT}"],
                )
                # Chromium 启动了，但当前实现仍走 connect_over_cdp，所以这个分支只占位
        except Exception as e:
            log("err", f"Playwright Chromium 启动失败: {e}")
            log("err", "请先: playwright install chromium")
            sys.exit(1)

    if not wait_for_port(CDP_URL, 45000):
        log("err", f"浏览器启动超时（45秒）")
        sys.exit(1)
    log("ok", "浏览器已就绪")


# ============ Cookie 注入与验证 ============

def inject_cookies_and_verify(cookies: list, wait_for_login: bool = False) -> bool:
    log("info", "连接浏览器并注入 Cookies...")
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
                print("[!] 存储的 cookie 已过期。请在打开的浏览器中手动登录威科先行。")
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
                print("[!] 存储的 cookie 已过期。请使用 --wait-login 引导手动登录。")
                print("    或者手动登录威科后将 cookies.json 写到:", WKINFO_COOKIE_FILE)

        print()
        print("浏览器保持运行中（隔离 profile），可直接使用。")

        return logged_in


def verify_only() -> bool:
    if not wait_for_port(CDP_URL, 2000):
        log("err", f"CDP 端口 {CDP_PORT} 未启动，请先运行 install_cookies.py")
        return False
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.goto(WKINFO_DOMAIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        body_text = page.text_content("body") or ""
        logged_in = USERNAME_MARKER in body_text
        log("ok" if logged_in else "err", f"登录状态: {'已登录' if logged_in else '未登录'}")
        return logged_in


def main():
    parser = argparse.ArgumentParser(
        description="威科先行 Cookie 注入工具（跨平台）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--browser", "-b",
                        choices=["auto", "edge", "chrome", "chromium"],
                        default="auto",
                        help="浏览器类型：auto=按系统默认，edge=Edge，chrome=Chrome，chromium=Playwright 自带")
    parser.add_argument("--kill", action="store_true",
                        help="关闭所有浏览器进程后再启动（破坏性）")
    parser.add_argument("--verify", action="store_true",
                        help="只验证当前浏览器是否已登录")
    parser.add_argument("--wait-login", action="store_true",
                        help="注入失败时挂起等待手动登录")
    args = parser.parse_args()

    print("威科先行 Cookie 注入工具（Python 版, 跨平台）")
    print("=" * 60)
    print(f"系统: {sys.platform} ({platform.system()} {platform.release()})")
    print(f"Python: {sys.version.split()[0]}")
    if args.browser == "auto":
        default = "edge" if sys.platform == "win32" else "chrome"
        print(f"浏览器: auto → {default}")
    else:
        print(f"浏览器: {args.browser}")
    print("=" * 60)

    if args.verify:
        return 0 if verify_only() else 1

    if not WKINFO_COOKIE_FILE.exists():
        log("err", f"Cookie 文件不存在: {WKINFO_COOKIE_FILE}")
        log("err", "请先从有 cookie 的机器复制 wkinfo-cookies.json 到此位置")
        return 1

    try:
        cookies = load_cookies_from_storage()
        if args.kill:
            kill_browsers()
        start_browser_with_debug(args)
        success = inject_cookies_and_verify(cookies, wait_for_login=args.wait_login)
        return 0 if success else 1
    except Exception as e:
        log("err", f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
