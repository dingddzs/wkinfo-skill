# 威科案例检索和下载 Skill — 项目说明文档

> 用途：让任何新成员能**快速看懂本项目**，知道在哪儿改、如何加新功能、踩过什么坑。  
> 读者画像：接手维护的工程师 / 需要扩展功能的工程师  
> 项目版本：v1.3.0（5 库版本）  
> 最后更新：2026-07-17

---

## 0. 一句话介绍

本项目是 **Claude Code Skill `威科案例检索和下载`** 的开发仓库，覆盖威科先行（`law.wkinfo.com.cn`）的 **5 个内容库**（裁判文书、法律法规、行政处罚、实务指南、专题聚焦），提供：
- 自然语言 → 结构化检索参数
- 侧边栏筛选（30+ 维度，37 个法院全集）
- 单 PDF 下载 + 批量 Excel 导出
- **5 库并行"研究"工作流** —— 用户调研法律问题时一键拉全库信源

底层完全走 JSON API，**不依赖浏览器**（生产路径只用 cookies）。

---

## 1. 项目结构

```
威科案例检索和下载-20260716/
├── PROJECT_GUIDE.md            ← 你正在读的（项目说明）
├── SKILL.md                    ← Claude 看到的触发词文档
├── 脚本和代码/                 ← 所有 Python 脚本
│   ├── wkinfo_api.py          ★ 核心：API 客户端 + 5 库 LIBRARIES 注册表
│   ├── search_cases.py        ← 案例库检索 CLI
│   ├── search_laws.py         ← 法规库检索 CLI
│   ├── search_penalties.py    ← 处罚库检索 CLI
│   ├── research.py            ★ 核心：5 库并行"调研"工作流
│   ├── nl_parser.py           ← 自然语言 → SearchParams
│   ├── parse_case_causes.py   ← 案由 JSON 一次性生成
│   ├── download.py            ← 案例 PDF/Word/Excel 下载
│   ├── highlight_pdf.py       ← PDF 标黄
│   ├── install_cookies.py     ← Edge debug + Cookie 注入
│   └── _research/             ← 一次性调研脚本（不要直接调用）
├── references/                 ← 文档（开发者参考）
│   ├── AI_INTERVENTION_GUIDE.md  ★ 必读：所有 API 字段/坑/反推流程
│   ├── wkinfo-cases-page.md     ← case 库专项（早期调研产出）
│   └── nl-patterns.md           ← nl_parser 的正则词典
└── 临时资源/
    └── edge-debug-profile/    ← Playwright 隔离 Edge profile（运行 cookie 注入时生成）
```

> **已安装到 Claude**：所有 `脚本和代码/*.py` 加上 `references/*` 都同步到 `~/.claude/skills/威科案例检索和下载/`。Skill 实际从那里加载。

---

## 2. 核心文件详解（按重要性）

### 2.1 `脚本和代码/wkinfo_api.py` ★ 核心
- 唯一与威科后端通信的文件
- 类 `WkinfoClient` 提供 `search / doc_count / download_file` 三个方法
- 全局字典 `LIBRARIES` 集中配置所有库：
  ```python
  LIBRARIES = {
      "case":       Library(...),  # 裁判文书
      "legislation":Library(...),  # 法律法规
      "penalty":    Library(...),  # 行政处罚
      "commentary": Library(...),  # 实务指南
      "focus":      Library(...),  # 专题聚焦
  }
  ```
- 每个 `Library` 含：`index_id`（库 ID）、`list_url`、`field_maps`（字段名→MAP）
- 库专属 MAP（如 `CASE_MAPS`）也在此文件，按"库名_MAP"的命名约定
- 不同库的 sort 字段名不同（`judgmentDate` / `promulgatingDate` / `orderPriority` 等），由 `build_search_body` 内自动切换

### 2.2 `脚本和代码/research.py` ★ 核心
- 5 库并行搜索，按命中数排序输出"信源汇总"
- 两个模式：`summary`（仅计数）/ `detail`（含每库前 5 条）
- 输出 JSON 可直接喂给 Claude 起草法律文书
- **新加库的入口**：只要在 `LIBRARIES` 加新库，本脚本自动覆盖

### 2.3 `脚本和代码/inject_cookies.py`
- 启动隔离 profile 的 Edge + 注入 wkinfo-cli 共享的 17 个 cookie
- 默认 `--no-kill` 不杀用户主 Edge
- 详细 header 见 `~/.claude/skills/wkinfo-cli/SKILL.md`

### 2.4 `脚本和代码/search_*.py`
- 每个库一个薄壳 CLI（5-7 行 argparse + 调 client.search）
- 模板直接复制 `search_cases.py` 改最下面几行即可新建

### 2.5 `脚本和代码/nl_parser.py`
- 用户原话 → `SearchParams` 结构体
- 用正则提取时间、法院、审级、文书类型等
- 案由自动匹配《民事案件案由规定》词典

### 2.6 `references/AI_INTERVENTION_GUIDE.md` ★ 必读
**这是接手前必须读的唯一文档**。包含：
- 5 个库的 API 完整规格
- 所有过滤项的字段名 + 编码
- 致命坑（`filterDates` 不能用 / `queryString` 必须 `simple:()` 等）
- 调浏览器反推 API 的标准流程
- 加新库的完整 SOP

### 2.7 `_research/` 一次性调研脚本
调研时用、不再运行。保留是因为里面有 `commentary_focus_capture.py` 这种可以参考的"反推 API"模板。

---

## 3. 快速上手

### 3.1 安装依赖
```bash
pip install playwright requests
python -m playwright install chromium  # 如果没装
```

### 3.2 一次性登录
```bash
python 脚本和代码/install_cookies.py
# Edge debug 实例启动 + 17 个 cookie 注入
# 输出：[OK] 已登录 (jtnfawkwechat)
```

> Cookie 来源：`~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json`（共享 wkinfo-cli skill 的登录态）

### 3.3 跑三个常用命令

```bash
# 单库检索（few 模式：找 3 条匹配）
python 脚本和代码/search_cases.py \
  --query "建设工程施工合同纠纷，最高法，二审，近三年判决" \
  --mode few --target 3

# 单库下载（list 模式 → xls）
python 脚本和代码/download.py \
  --input ./result.json --format xls --output-dir ./原始文件/

# 跨 5 库调研（核心工作流）
python 脚本和代码/research.py --query "公司法 股东代表诉讼" --mode detail
```

---

## 4. 架构图

```
用户原话
   │
   ▼
nl_parser.py          ← 正则抽取时间/法院/审级/...
   │        自动匹配《案由规定》词典
   ▼
SearchParams { court_level, doc_type, year_from, ... }
   │
   ▼
search_cases.py / search_laws.py / ...    ← 薄壳 CLI（按 library 选一个）
   │
   ▼
research.py            ← 或直接跨 5 库并行
   │
   ▼
wkinfo_api.WkinfoClient.search(library="case", ...)
   │
   ▼
JSON 请求 → /csi/search?indexId=law.X
   │   body: { queryString: "simple:((XX))", filterQueries: [...] }
   ▼
JSON 响应 → documentList[]
   │
   ▼
download.py → wkinfo_api.download_file() → /csi/document/* 三步流
```

---

## 5. 如何扩展（最常见任务）

### 5.1 加一个新库（5 步 SOP）

**SOP 完全对应 `AI_INTERVENTION_GUIDE.md` 第 8 节"加新库"**，简要：

1. **发现按钮**：打开 `https://law.wkinfo.com.cn/`，找按钮文字 + 点击看 URL
2. **抓 indexId**：用 Playwright 拦截浏览器实际请求，从 body 拿 `indexId: "law.X"` ——**不要猜**
3. **抓 sidebar**：用 CDP 自动化点击每个侧边栏项 → 看 URL `fq` → 解析出 `field:value:label`
4. **写入配置**（仅 5 行）：
   ```python
   NEW_LIB_MAPS = {"xxxField": {"值1": "code1", ...}}
   LIBRARIES["newkey"] = Library(
       key="newkey", name="新库名",
       index_id="law.X", list_url="/xxx/list",
       field_maps=NEW_LIB_MAPS,
   )
   ```
5. **加 CLI 薄壳**：复制 `search_laws.py`，改 `library="legislation"` 为 `library="newkey"`

`research.py` 自动覆盖新库，无需修改。

### 5.2 改某个过滤器的语法

1. 看 `references/AI_INTERVENTION_GUIDE.md` 第 5 节找到对应 MAP
2. 看 `脚本和代码/wkinfo_api.py` 的 MAP（`CASE_MAPS["X"]`）
3. 直接改 MAP 后**跑端到端**：
   ```bash
   python -c "
   from wkinfo_api import WkinfoClient
   c = WkinfoClient()
   print(c.doc_count(query_string='XX', filter_queries=['+X:((Y))'], library='case'))
   "
   ```

### 5.3 改 nl_parser 抽取规则

1. 看 `脚本和代码/nl_parser.py` 的正则（顶部 `YEAR_PATTERNS` 等）
2. 加新规则，例如"识别'最高院第一巡回法庭'"：
   ```python
   patterns.append((r"最高院第[一二三四]巡回", lambda m: {"court_name": m.group(0)}))
   ```
3. 同步更新 `references/nl-patterns.md`

---

## 6. 已知边界（不要试图扩展这些）

| 不做 | 原因 |
|------|------|
| 爬详情页 HTML | 走 API + 三步下载流；HTML 不稳定 |
| 实现评论 / 点赞 | wkinfo 没有社交功能 |
| 突破付费下载 | 用户明确说有权限，不需要绕 |
| 实现 PDF 水印 / 合并 | 保持简洁，下游工具（`case-retrieval`）做 |
| 自定义 cookie 维护 | 共享 `wkinfo-cli` skill 的 storage |

---

## 7. 浏览器内存管理（**硬约束**）

所有 `_research/*.py` 和调试脚本**必须**在结束前清理标签：

```python
# 关掉非 wkinfo 标签
for p in ctx.pages[:]:
    if 'wkinfo.com.cn' not in p.url:
        p.close()
# 同一域去重
seen = set()
for p in ctx.pages[:]:
    if p.url.split('?')[0] in seen:
        p.close()
    else:
        seen.add(p.url.split('?')[0])
```

**禁止** `page.wait_for_timeout(20000)` 之类的长等待——Edge debug 实例会挂掉。

---

## 8. 未来工作（待办）

| 任务 | 优先级 | 备注 |
|------|--------|------|
| `commentary`/`focus` 库的专题分类 MAP（具体编码）| 低 | 当前只有 `lang/groupLevel/lastReviewYear` 通用字段 |
| `search_commentary.py` / `search_focus.py` 薄壳 | 中 | 复制 `search_laws.py` 改 5 行 |
| nl_parser 加"调研模式"自动识别（触发词 → research.py）| 高 | 这是 SKILL.md trigger 真正工作的关键 |
| 单元测试覆盖各 MAP | 中 | 现在每个改动都靠手动端到端测试 |
| `download.py` 适配 5 库（目前只支持 case 库）| 中 | legislation/penalty 的下载按钮 ID 模式应该类似但需验证 |

---

## 9. 验收清单（修改后必跑）

```bash
# 1. 单库端到端
python 脚本和代码/search_cases.py --query "公司" --mode few --target 3
python 脚本和代码/search_laws.py --query "商标法" --mode few --target 3
python 脚本和代码/research.py --query "公司法" --mode detail

# 2. 5 库 + indexId 一致性
python -c "
from wkinfo_api import WkinfoClient, LIBRARIES
c = WkinfoClient()
for k, v in LIBRARIES.items():
    n = c.doc_count(query_string='公司', library=k)
    print(f'{k:12s} {v.name:8s} {v.index_id:30s} {n:,}')
"

# 3. 下载链路
python 脚本和代码/install_cookies.py
# 然后随便搜一条案例下载 PDF
```

---

## 10. 常见报错速查

| 报错 | 原因 | 修复 |
|------|------|------|
| `400 "indexId不能为空"` | `WkinfoClient.build_search_body` 没传 `library` 或 `library` 不在 `LIBRARIES` | 拼写错误或漏配注册 |
| `400 "搜索结果为空"` | sort 字段名错（如 legislation 用 `judgmentDate` 而非 `promulgatingDate`） | 见各库的 `sortOrderList` 注释 |
| `doc_count` 一直返回 0 | 用 `/csi/search/doc-count` 端点会失灵——本项目改用 `/csi/search` 拿 `searchMetadata.docCount` | 已修复 |
| `uid` header 空 | `userInfo.id` 没正确解析（cookie value 是 URL-encoded） | `urllib.parse.unquote()` 后再 regex |
| Edge debug 挂 | 标签太多没关 | 严格按第 7 节 |

---

## 11. 关联资源

- **Skill 安装位置**：`~/.claude/skills/威科案例检索和下载/`
- **共享 cookie**：`~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json`
- **下游 skill**：`case-retrieval`（消费本 skill 输出的 Excel 做 AI 分析）
- **Git 仓库**：本项目未初始化 git，需要时 `git init` + push 到远程
- **Windows 系统提醒**：避免 `p.wait_for_timeout(20000+)`，Edge 会断连

---

## 12. 联系方式

遇到问题或要加新功能时，先看：
1. **`references/AI_INTERVENTION_GUIDE.md`**（最权威）
2. **本文件"未来工作"节**（可能你做的就是你看到的 TODO）
3. **本文件"常见报错速查"**

如果还是不清楚，开个 issue（仓库里没有，但项目根有 `SKILL.md` 可作为入口）。

---

## 12. GitHub 管理与代码-文档同步规则

### 12.1 Git 初始化（已完成）

```bash
git init                                                  # 本项目根（已做）
git config user.name "Your Name"                            # 一次性
git config user.email "you@example.com"
```

### 12.2 连接 GitHub remote（待你执行）

```bash
# 1. 在 GitHub 网页创建新 repo（建议私有，名字：wkinfo-skill）
# 2. 加 remote
git remote add origin git@github.com:<your-username>/<repo>.git
# 3. 推送
git push -u origin main
```

### 12.3 提交规范（Conventional Commits）

```bash
feat(case): 加 37 个法院编码
fix(legislation): 用 promulgatingDate 替代 judgmentDate  
docs: 更新 v1.3 changelog 和 PROJECT_GUIDE
chore: 更新 .gitignore
test: 加 research.py 端到端测试
```

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 / 新库 / 新字段 |
| `fix` | bug 修复 / API 错误修正 |
| `docs` | 文档更新（不改代码） |
| `refactor` | 代码重构（不改功能） |
| `chore` | 构建 / 配置 / 杂项 |
| `test` | 测试代码 |

### 12.4 **代码-文档同步规则（硬约束）**

> **每次代码改动必须同步更新以下 4 个文件**：

| 文件 | 何时更新 | 示例 |
|------|---------|------|
| **`CHANGELOG.md`** | 任何用户可见的改动 | 加一段新版本号，列改动点 |
| **`SKILL.md`** `metadata.version` + `changelog:` | 改了触发词、新增库、新增 CLI | `version: "1.4.0"` |
| **`PROJECT_GUIDE.md`** | 改了架构、加了文件、改了流程 | 修改对应章节 |
| **`references/*.md`** | 改了对应库/字段的 API 规范 | 修改具体 MAP 表 |

### 12.5 发布流程（每次更新都跑一遍）

```bash
# 1. 改代码 + 改文档
# 2. 跑验收
python 脚本和代码/research.py --query "公司" --mode detail
# 3. 更新 4 个文档
# 4. 提交
git add -A
git commit -m "feat(...): ..."
git push origin main  # 可选
```

### 12.6 版本号规则

- **MAJOR** (v1→v2)：不兼容改动（删库、改 API 形态、破坏现有用户配置）
- **MINOR** (v1.2→v1.3)：新增库 / 新功能 / 新 CLI / 新触发词
- **PATCH** (v1.3.0→v1.3.1)：bug 修复 / MAP 增补 / 小文档修正

### 12.7 .gitignore 已配置

排除不进版本控制的大文件 / 用户数据 / Edge 隔离 profile。详见 `.gitignore`。

**已 commit 的内容**（未来你 push 时都会带）：
- `脚本和代码/*.py`
- `references/*.md`
- `SKILL.md`、`PROJECT_GUIDE.md`、`CHANGELOG.md`、`.gitignore`
- `临时资源/edge-debug-profile/` **排除**（100+ MB）

**有意排除**：
- `原始文件/`（用户下载）
- `处理后文件/`（AI 处理结果）
- `__pycache__/`（运行时）
- `临时资源/edge-debug-profile/`、`临时资源/截图/`、`临时资源/调试/`

---

## 13. 已交付状态检查表

接手项目时按顺序跑这些，确认当前状态：

- [x] Git 初始化（2026-07-17）
- [x] `.gitignore` 配置
- [x] `PROJECT_GUIDE.md` 写入
- [x] `CHANGELOG.md` 写入（含 v1.0/v1.1/v1.2/v1.3 历史）
- [ ] 远端 GitHub repo 创建 + `git push`（**待用户执行**）
- [ ] CI workflow（如需要：lint、自动化验收）

---


## 14. sync.py 双向同步（v1.5+）

**问题**：项目文件夹（开发版）和 `~/.claude/skills/...`（Claude 实际加载）有结构差异：
- 项目：`脚本和代码/`、`references/`、`SKILL.md`
- skill 安装：`scripts/`、`references/`、`SKILL.md`

手动 cp 容易漏，且 e1e0949（v1.4.0）就漏了。

**解决**：`scripts/sync.py` 双向同步 + hash 对比。

### 用法
```bash
python scripts/sync.py             # 项目 -> skill（默认 push）
python scripts/sync.py --pull      # skill -> 项目
python scripts/sync.py --check     # 只比较不复制
```

### 硬排除（不会被 sync 过去）
- `.git/`、`__pycache__/`（运行时产物）
- `临时资源/`（含 Edge profile 1.4GB + 截图 + 调试日志）
- `原始文件/`、`处理后文件/`（用户数据）
- 项目独有：`PROJECT_GUIDE.md`、`CHANGELOG.md`、`开发日志.md`、`README.md`、`.gitignore`、`.gitattributes`

### 何时跑
- **每次 commit 前**：确保 skill 安装位置同步了最新代码
- **克隆项目到新机器时**：clone → 跑 sync → 装依赖 → 跑验收
- **修了代码后忘了 commit**：先 commit 再 sync

### 不在 sync 范围
- Skill install 位置独有的动态加载文件（如有）
- 临时资源 / 用户数据（设计原则：永远不离开用户机器）


## 15. GitHub 管理 + 自动同步（v1.5.1）

**仓库**：https://github.com/dingddzs/wkinfo-skill （私有）

**完整工作流**（3 步搞定一切）：

```bash
# 1. 改代码
python scripts/research.py --query "公司法" --mode detail  # 验证 OK
echo "" >> SKILL.md                                        # 改代码

# 2. 提交（post-commit 钩子自动同步到 ~/.claude/skills/）
git add -A
git commit -m "feat: xxx"
# → 终端会输出 [post-commit-hook] auto-synced N file(s)

# 3. 推送到 GitHub
git push origin master
```

**首次在另一台机器上 clone**：
```bash
git clone https://github.com/dingddzs/wkinfo-skill.git
cd wkinfo-skill
# 改名：项目文件夹是 "威科案例检索和下载-20260716"，clone 后是 "wkinfo-skill"
mv wkinfo-skill 威科案例检索和下载-20260716
# 装钩子
python 脚本和代码/install_hooks.py
# 装依赖
pip install playwright requests
```

**钩子行为**（`scripts/hooks/post-commit`）：
- 每次 commit 后自动跑 `sync.py`（项目→skill 安装）
- 跳过 sync 自身/hook 改动（避免无限循环）
- 支持 `SKIP_AUTO_SYNC=1` 手动跳过
- 终端输出 `[post-commit-hook] auto-synced N file(s): ...`

**何时手动跑 sync**（不走钩子）：
- `python 脚本和代码/sync.py --pull` — 从 skill 反向同步到项目
- `python 脚本和代码/sync.py --check` — 只看差异不写
- `SKIP_AUTO_SYNC=1 git commit -m "x"` — 临时跳过钩子

**远程 URL 设置**（已配）：
- 仓库：https://github.com/dingddzs/wkinfo-skill
- 协议：HTTPS（gh CLI 默认）
- 凭证：gh CLI keyring 缓存的 token

**未来扩展**（可选）：
- GitHub Actions：在 push 时跑 lint/测试/自动发版
- pre-commit 钩子：跑单元测试
- changelog 自动生成

