# 威科 Skill 安装指南（跨平台）

> **你的朋友读这份**：5 分钟装好。

---

## ⚠️ 安全警告（必读）

**每个用户必须自己登录一次威科，保存自己的 cookie。绝对不要从别人那里拿 cookie 复制到本机！**

**原因**：
1. Cookie 跟登录账号绑定——A 用户的 cookie 在 B 机器上用会失效
2. Cookie 是身份凭证——共享 cookie 等于把账号交出去
3. 威科 cookie 大约 1 天过期，**必须支持每用户自刷新**（所以有 login 脚本）

**正确流程**：
- ✅ 自己跑 `python login_wkinfo.py` → 手动登录 → 自动保存到 `~/.claude/skills/wkinfo-cli/storage/`
- ❌ 不要从朋友那里要 cookies.json
- ❌ 不要把 cookies.json 提交到 git（已在 `.gitignore` 排除）

---

## 0. 仓库地址

- **GitHub**：https://github.com/dingddzs/wkinfo-skill
- **版本**：v1.5.2（5 库 + 自动同步钩子 + 跨平台 + 登录脚本）

## 1. 系统要求

| 项 | 要求 | 备注 |
|---|------|------|
| **OS** | Windows 10+ / macOS 11+ / Ubuntu 20.04+ | 全部支持 |
| **Python** | 3.8 或更高（推荐 3.11+） | `python --version` 验证 |
| **磁盘** | ~500 MB（Playwright 浏览器） | |
| **网络** | 稳定（首次安装下载大） | |

**不需要的**：
- ❌ 不需要 Microsoft Edge（macOS/Linux）
- ❌ 不需要 WSL 或虚拟机
- ❌ 不需要管理员权限

## 2. 安装步骤

### 2.1 克隆仓库

```bash
git clone https://github.com/dingddzs/wkinfo-skill.git
cd wkinfo-skill
mv wkinfo-skill 威科案例检索和下载-20260716
cd 威科案例检索和下载-20260716
```

### 2.2 安装 Python 依赖

```bash
pip install playwright requests pypdf
playwright install chromium
```

**注意**：
- `pypdf` 是 PDF 标黄用，不装也能用 skill 的搜索/下载
- `playwright install chromium` 必须跑（下载约 200MB 浏览器）
- macOS 上 `playwright install` 会自动选 macOS 平台

### 2.3 首次登录威科（⚠️ 必须用自己的账号）

```bash
# Windows / macOS / Linux 都一样：
python 脚本和代码/login_wkinfo.py
```

这个脚本会：
1. 启动隔离 profile 的浏览器（不影响你主浏览器）
2. 打开威科首页
3. **你在弹出的浏览器里手动登录**（用自己的威科账号）
4. 登录成功后自动捕获 cookie 并保存到：
   ```
   ~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json
   ```
5. cookie 大约 1 天过期，过期时再跑一次这个脚本重新登录

**绝对不要**：
- ❌ 把你的 cookies.json 发给朋友
- ❌ 把朋友的 cookies.json 复制到你机器上
- ❌ 把 cookies.json 提交到 git（已在 `.gitignore` 排除）

### 2.4 装 Git 钩子（自动同步到 skill 安装位置）

```bash
python 脚本和代码/install_hooks.py
```

之后每次 `git commit` 都会自动跑 sync.py 推到 `~/.claude/skills/威科案例检索和下载/`。

### 2.5 登录 Edge/Chrome（首次需要）

```bash
# 自动检测：Windows→Edge, macOS/Linux→Chrome
python 脚本和代码/install_cookies.py --wait-login
# 浏览器弹出后手动登录威科
# 登录成功后脚本自动写回 cookies.json
```

指定浏览器类型：
```bash
python 脚本和代码/install_cookies.py --browser edge       # Windows Edge
python 脚本和代码/install_cookies.py --browser chrome     # macOS Chrome / Linux Chrome
python 脚本和代码/install_cookies.py --browser chromium   # Playwright 自带 Chromium
```

### 2.6 验证

```bash
python 脚本和代码/install_cookies.py --verify
# 应该输出：[OK] 已登录 (jtnfawkwechat)
```

### 2.7 测试搜索

```bash
# few 模式（找 5 条匹配）
python 脚本和代码/search_cases.py \
  --query "建设工程施工合同纠纷，最高法，二审，近三年判决" \
  --mode few --target 5

# 5 库并行研究
python 脚本和代码/research.py --query "公司法 关联交易" --mode detail

# 迭代检索（往返事实/规范）
python 脚本和代码/research.py --query "建设工程实际施工人" --mode iterative
```

## 3. 浏览器兼容性

| 平台 | 默认浏览器 | 备选 |
|------|----------|------|
| **Windows 10/11** | Microsoft Edge | Chrome / Chromium |
| **macOS 11+** | Google Chrome | Edge / Chromium |
| **Linux (Ubuntu 20.04+)** | Chromium | Chrome / Edge（需装 .deb） |

**macOS 用户注意事项**：
- Apple Silicon (M1/M2/M3) 可能需要 Rosetta
- 路径：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- 如 Chrome 未装，先去 https://www.google.com/chrome 下载

**Linux 用户注意事项**：
- `google-chrome` 需从 Google 官网下载 .deb 或 .rpm
- `chromium-browser` 在 Ubuntu 20.04+ 仓库里就有：`sudo apt install chromium-browser`

## 4. 跨平台验证 checklist

在朋友机器上跑这些，**全绿**才算装好：

```bash
# 1. Python + playwright
python -c "import playwright, requests; print('OK')"

# 2. Playwright chromium
python -c "from playwright.sync_api import sync_playwright; print('chromium path:', sync_playwright().start().chromium.executable_path)"

# 3. Cookie 文件存在
ls -la ~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json

# 4. Edge debug 钩子
python 脚本和代码/install_hooks.py
ls -la .git/hooks/post-commit

# 5. 登录态
python 脚本和代码/install_cookies.py --verify
# → [OK] 已登录 (jtnfawkwechat)

# 6. 搜索能跑
python 脚本和代码/research.py --query "test" --mode summary
# → 5 库都有命中
```

## 5. 常见问题

### Q: macOS 报 "developer cannot be verified" 错误
A: 系统设置 → 隐私与安全 → 仍要打开（针对 msedge/Chrome 二进制）

### Q: Linux 缺 libgbm/libnss 等
A:
```bash
sudo apt install libgbm1 libnss3 libxkbcommon0 libasound2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2
```

### Q: "playwright install chromium" 下载慢
A: 设置代理 `HTTPS_PROXY=http://127.0.0.1:7890 playwright install chromium`

### Q: Cookie 总是失效
A: 威科 cookie 大约 1 天过期。重跑 `install_cookies.py --wait-login` 重新捕获。

### Q: 跑命令报 "ModuleNotFoundError: No module named playwright"
A: `pip install playwright`（或 `pip3 install playwright` 看 Python 版本）

### Q: 钩子跑后没输出
A: 检查 `.git/hooks/post-commit` 是否 +x。Windows 上 Git Bash 需 `chmod +x .git/hooks/post-commit`

## 6. 路径差异

| 用途 | Windows | macOS/Linux |
|------|---------|-------------|
| 项目根 | `D:\ai\Claudecode\威科案例检索和下载-20260716` | `~/code/wkinfo-skill` |
| Skill 装位置 | `%USERPROFILE%\.claude\skills\威科案例检索和下载` | `~/.claude/skills/威科案例检索和下载` |
| 浏览器 profile | `D:\…\临时资源\browser-debug-profile` | `~/.../临时资源/browser-debug-profile` |
| Cookie 共享 | `%USERPROFILE%\.claude\skills\wkinfo-cli\storage\wkinfo-cookies.json` | `~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json` |

中文文件夹名 Windows + Linux 都正常（Python 3 默认 UTF-8）。

## 7. 完整命令清单（copy-paste 安装）

**Windows PowerShell / macOS / Linux Bash 共用**：

```bash
# 1. 克隆
git clone https://github.com/dingddzs/wkinfo-skill.git
cd wkinfo-skill
mv wkinfo-skill 威科案例检索和下载-20260716
cd 威科案例检索和下载-20260716

# 2. Python 依赖
pip install playwright requests pypdf
playwright install chromium

# 3. 装 wkinfo-cli skill 的 cookie 目录
mkdir -p ~/.claude/skills/wkinfo-cli/storage

# 4. ⚠️ 自己登录威科（不要复制别人的 cookie！）
python 脚本和代码/login_wkinfo.py
#   浏览器弹出 → 用你的威科账号登录 → 自动保存 cookie
#   cookie 大约 1 天过期，过期再跑一次

# 5. 装 Git 钩子
python 脚本和代码/install_hooks.py

# 6. 验证
python 脚本和代码/install_cookies.py --verify
# → 应该输出 [OK] 已登录 (jtnfawkwechat)
python 脚本和代码/research.py --query "公司" --mode summary
# → 5 库都有命中

# 7. 以后改代码，自动同步
# 直接：git add -A && git commit -m "xxx"
# 钩子会：项目→~/.claude/skills/... 自动同步
# 然后：git push origin master（推 GitHub）
```

## 8. cookie 过期了怎么办

威科 cookie 大约 **1 天**过期。到期症状：
- `install_cookies.py --verify` 输出 `[X] 未登录`
- 搜索返回 score 都是 0

修复（不要复制朋友的 cookie）：
```bash
python 脚本和代码/login_wkinfo.py
# 浏览器弹出 → 用你的账号重新登录
```

## 8. 不需要知道的事

- ❌ Edge debug 端口 9222 的原理（钩子自动处理）
- ❌ Playwright API 细节
- ❌ Git 钩子语法（脚本已装好）
- ❌ Cookie 怎么从浏览器抓（用 `install_cookies.py --wait-login` 一步到位）

只管：写代码 → `git add` → `git commit` → 钩子自动同步 → 推 GitHub。完事。
