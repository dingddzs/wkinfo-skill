#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
威科先行登录脚本（每个用户必须自己跑一次）

用途：在用户机器上第一次安装时，跑这个脚本来：
  1. 启动隔离 profile 的浏览器
  2. 弹出威科首页
  3. 等待用户手动登录
  4. 登录成功后自动捕获 cookie 并保存到 ~/.claude/skills/wkinfo-cli/storage/

**重要**：
- 绝对不要从别人那里拿 cookies.json 复制到自己机器上
- cookies 跟登录账号绑定，混用会失效
- cookies 大约 1 天过期，到期再跑一次这个脚本

使用：
    python login_wkinfo.py                          # 自动检测浏览器（推荐）
    python login_wkinfo.py --browser chrome         # 强制 Chrome（macOS/Linux）
    python login_wkinfo.py --browser edge           # 强制 Edge（Windows）
    python login_wkinfo.py --browser chromium       # 强制 Playwright 自带 Chromium
    python login_wkinfo.py --max-wait 600           # 最长等 10 分钟（默认 5 分钟）
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

# Windows 控制台编码修复
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[X] Playwright 未安装")
    print("    请先: pip install playwright && playwright install chromium")
    sys.exit(1)


# 共享 wkinfo-cli skill 的 cookie 存储
COOKIE_FILE = Path.home() / ".claude" / "skills" / "wkinfo-cli" / "storage" / "wkinfo-cookies.json"

# 隔离 profile（不污染用户主浏览器）
PROFILE_DIR = Path.home() / ".cache" / "wkinfo-skill-profile"

WKINFO_DOMAIN = "https://law.wkinfo.com.cn"
USERNAME_MARKER = "jtnfawkwechat"
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
    },
    "darwin": {
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
    },
    "linux": {
        "chrome": ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/opt/google/chrome/chrome"],
        "chromium": ["/usr/bin/chromium", "/usr/bin/chromium-browser"],
        "edge": ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"],
    },
}


def log(level: str, msg: str) -> None:
    icons = {"info": "[*]", "ok": "[+]", "warn": "[!]", "err": "[X]"}
    print(f"{icons.get(level, '[*]')} {msg}")


def find_browser_path(browser: str):
    paths = DEFAULT_BROWSER_PATHS.get(sys.platform, {}).get(browser, [])
    if not paths:
        return None
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


def launch_browser(browser: str, profile_dir: Path):
    """跨平台启动浏览器"""
    profile_dir.mkdir(parents=True, exist_ok=True)
    browser_path = find_browser_path(browser)

    if not browser_path:
        log("warn", f"本系统未找到 {browser}，改用 Playwright 自带 Chromium")
        return None

    args = [
        browser_path, f"--remote-debugging-port={CDP_PORT}",
        "--no-first-run", "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
    ]
    if sys.platform == "win32":
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for_login_and_save(max_wait: int = 300) -> bool:
    """等用户登录 + 自动捕获 cookies"""
    deadline = time.time() + max_wait
    log("info", f"等待登录（最长 {max_wait // 60} 分钟）...")
    log("info", "请在打开的浏览器窗口里:")
    log("info", "  1. 进入威科先行首页")
    log("info", "  2. 用你的账号登录")
    log("info", "  3. 登录成功会自动检测")
    log("info", "  4. 关闭浏览器或 Ctrl+C 退出")
    print()

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]

        # 开新页面
        page = ctx.new_page()
        page.goto(WKINFO_DOMAIN, wait_until="domcontentloaded", timeout=60000)

        last_status = False
        while time.time() < deadline:
            time.sleep(3)
            try:
                page.reload(wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                body = page.text_content("body") or ""
                logged_in = USERNAME_MARKER in body

                if logged_in and not last_status:
                    log("ok", f"检测到登录成功（{USERNAME_MARKER}）")
                    last_status = True
                    # 抓 cookie
                    cookies = ctx.cookies()
                    wkinfo_cookies = [c for c in cookies if "wkinfo" in (c.get("domain") or "")]
                    if wkinfo_cookies:
                        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                            json.dump(wkinfo_cookies, f, ensure_ascii=False, indent=2)
                        log("ok", f"已保存 {len(wkinfo_cookies)} 个 cookie 到:")
                        log("ok", f"  {COOKIE_FILE}")
                    else:
                        log("err", "未找到 wkinfo cookie，请确认登录成功")
                        return False

                if logged_in and time.time() < deadline - 30:
                    # 留 30 秒让用户浏览 / 关闭浏览器
                    continue
            except KeyboardInterrupt:
                log("info", "用户中断")
                return last_status
            except Exception as e:
                log("warn", f"等待出错: {e}")

        if last_status:
            log("ok", "登录完成，cookie 已保存！")
            log("ok", "下次 cookie 过期时，再跑本脚本即可")
        else:
            log("err", f"{max_wait // 60} 分钟内未检测到登录")
        return last_status


def main():
    parser = argparse.ArgumentParser(
        description="威科先行登录 + 捕获 cookie",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--browser", "-b",
                        choices=["auto", "edge", "chrome", "chromium"],
                        default="auto",
                        help="浏览器类型（默认 auto：Win→Edge, Mac/Linux→Chrome）")
    parser.add_argument("--max-wait", type=int, default=300,
                        help="最长等待登录时间（秒），默认 300")
    args = parser.parse_args()

    print("=" * 60)
    print("  威科先行登录 + Cookie 捕获")
    print("=" * 60)
    print()
    print("⚠  重要：每个用户必须自己登录一次，cookie 跟账号绑定。")
    print("   绝对不要从别人那里复制 cookies.json 到自己机器！")
    print()
    print(f"系统: {sys.platform} ({platform.system()} {platform.release()})")
    print(f"Python: {sys.version.split()[0]}")
    if args.browser == "auto":
        default = "edge" if sys.platform == "win32" else "chrome"
        print(f"浏览器: auto → {default}")
    else:
        print(f"浏览器: {args.browser}")
    print()

    if COOKIE_FILE.exists():
        log("info", f"Cookie 文件已存在: {COOKIE_FILE}")
        log("info", "  （如果你的 cookie 没过期，可以直接用 install_cookies.py --verify 验证）")
        log("info", "  （要重新登录就继续；cookie 会被覆盖）")
        print()

    if wait_for_port(CDP_URL, 2000):
        log("ok", "浏览器调试端口已运行，直接连上")
    else:
        browser = args.browser
        if browser == "auto":
            browser = "edge" if sys.platform == "win32" else "chrome"
        if browser == "chromium":
            log("err", "chromium 模式请用 install_cookies.py --browser chromium")
            return 1
        log("info", f"启动 {browser}（隔离 profile: {PROFILE_DIR}）...")
        proc = launch_browser(browser, PROFILE_DIR)
        if proc is None:
            log("err", "未找到浏览器，请用 --browser 指定")
            return 1
        if not wait_for_port(CDP_URL, 45000):
            log("err", "浏览器启动超时（45秒）")
            return 1
        log("ok", "浏览器已就绪")

    success = wait_for_login_and_save(args.max_wait)
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[中断] 用户按 Ctrl+C 退出")
        sys.exit(1)
