---
name: 威科案例检索和下载
description: |
  威科先行（law.wkinfo.com.cn）智能检索与下载工具，覆盖五大库：

  【案例库】裁判文书 — 用户说"威科找案例"、"威科下载判决书"、"找建设工程施工合同纠纷的案例，最高法近三年二审"时触发。
  【法规库】法律法规 — 用户说"威科查法律"、"找公司法"、"查商标法"、"现行有效的XX法律"时触发。
  【处罚库】行政处罚 — 用户说"威科查处罚"、"上市公司处罚"、"金融业行政处罚"时触发。
  【实务库】实务指南（编辑部文章）— 用户说"威科实务"、"威科实务指南"、"实务文章"时触发。
  【专题库】专题聚焦（专题报告）— 用户说"威科专题"、"专题聚焦"、"威科报告"时触发。

  通用能力：自然语言 → 结构化参数 → 侧边栏筛选 → 标题搜索 → 单 PDF 下载 + 批量 Excel 导出。
  共享 wkinfo-cli skill 的 cookies，无需重复登录。

  【法律研究信源】当用户问"调研XX法律问题"、"分析XX"、"研究XX"、"找XX依据"、"找XX的判例和法条"等
  需要多类型依据支撑的任务时，本 skill 自动从 5 个库并行检索，输出结构化信源汇总，
  让 Claude 在写法律文书/回答法律问题时能引用到最完整的依据。

  触发关键词：
  - 检索类："威科找"、"威科搜"、"威科查"、"威科下载"、"威科案例"、"威科法律"、"威科处罚"、"威科实务"、"威科专题"
  - 研究类："调研XX"、"分析XX"、"研究XX"、"找XX依据"、"调研法律问题"、"为XX案找材料"
  - 写文书类："写XX诉状"、"起草XX答辩状"、"为XX案件准备诉讼材料"

  核心能力：
  - 自然语言 → 结构化参数（案由/法院/审级/时间/文书类型/法律层级/效力状态/处罚类型/实务专题）
  - 渐进式逼近（few 模式找几个，list 模式收窄到 ≤200 条）
  - 三种格式下载（PDF / Word / Excel）
  - PDF 标黄（自动添加黄色便签注释）
  - 跨库并行研究（research.py）— 一键拉 5 库信源
  - 框架可扩展：往 LIBRARIES 字典加一项即可接入新库

metadata:
  version: "1.5.0"
  author: 数字生命卡兹克 + Claude
  created: 2026-07-16
  updated: 2026-07-18
  changelog: |
    v1.5 - 新增 scripts/sync.py：双向同步项目↔skill 安装位置（hash 对比，硬排除临时资源/原始文件/处理后文件）
           新增 research.py --mode iterative：往返事实/规范迭代检索（法条抽取作锚点）
           research.py 输出 items 加 url / cited_laws / cited_articles 字段（条文一字不漏 + 详情页链接）
           references/retrieval-tips.md 加 tip：下载格式默认 PDF（仅批量筛选时用 xls）
           PROJECT_GUIDE.md 新增第 14 节：sync.py 工作流
           修复 v1.4 漏同步到 skill 安装位置
    v1.4 - 新增 references/retrieval-tips.md：4 段分类累积用户检索经验（query 增强 / filter 维度 / 案由别名 / 反模式）
           新增 scripts/nl_parser.py _load_user_synonyms() 方法：可选加载 references/extra-synonyms.json
           SKILL.md 核心流程图插入 step 1.5 "Load retrieval-tips.md"，末尾新增"经验维护"小节
    v1.3 - 加实务指南库（/commentary/list，indexId=law.commentaryB）和专题聚焦库（/focus/list，indexId=law.specialTopic）
           新增 research.py：跨 5 库并行搜索，输出结构化信源汇总
           触发词扩展：覆盖"调研XX"、"研究XX"等研究性场景
    v1.2 - 扩展支持法律法规库（/legislation/list）和行政处罚库（/administrative-punishment/list）
           重构为 LIBRARIES 注册表，新增库只需 5 行配置
           各库独立 indexId 和排序字段
    v1.1 - 补完侧边栏所有过滤器
    v1.0 - 初版：裁判文书检索 + 下载
    v1.1 - 补完侧边栏所有过滤器（法院/时间/审级/案由/行业/参照级别）
           自适应渐进式逼近（跳过 0 命中和无效过滤）
    v1.0 - 初版：裁判文书检索 + PDF/Word/Excel 下载 + 标黄
---

# 威科案例检索和下载

## 工作流

### 1. 触发条件识别

用户说类似以下内容时触发本 skill：
- "从威科找几个建设工程施工合同的案例"
- "威科检索：股东代表诉讼，最高法近三年判决"
- "在威科下载一份 XX 案例清单"
- "我要威科的 XX 案例（清单/几个/几份）"

### 2. 两种工作模式

| 模式 | 触发词 | 输出 | 数量上限 | 典型用途 |
|------|--------|------|---------|---------|
| **few**（"几个"模式）| "几个/几份/挑几个/要几个" | PDF（标黄匹配项）| 默认 5 | 找少量具体案例用于研究 |
| **list**（"清单"模式）| "清单/汇总/全部/整理/一批/下载" | Excel (.xls) | 渐进式逼近 ≤200 | 整理一批案例用于综述 |

### 3. 核心流程

```
用户自然语言查询
    ↓
[agent] step 1.5：Load references/retrieval-tips.md
        ├─ Section A：改写 --query 参数（query 增强）
        ├─ Section B：拼接 --filter-queries 参数（filter 维度）
        ├─ Section D：避开反模式组合
        └─ Section C：暂不应用（待升级到代码层）
    ↓
[nl_parser.py] 抽取结构化参数（案由、时间、法院、审级、文书类型）
    ↓
[search_cases.py] 调威科 API 搜索（自动包 simple:() 格式、按 score 排序）
    ↓
if mode=list:
    [渐进式逼近] 宽 → 窄 → 窄  → 截取前 N 条 → 输出 JSON
elif mode=few:
    [取前 N 条按 score 排序] → 输出 JSON
    ↓
[download.py] 调三步下载 API（Limit → Path → /api/download）保存文件
    ↓
if mode=few:
    [highlight_pdf.py] 在每份 PDF 首页添加黄色便签注释，文件名加 [匹配]_ 前缀
[生成 README.md 索引]
```

### 4. 关键参数说明

| 参数 | 来源 | 传给威科 |
|------|------|---------|
| **案由** | nl_parser 在 `民事案由_2025.json` 中找最匹配的案由 | 作为 hint 加入 queryString |
| **时间范围** | "近三年" / "2022-2025" 等 | `filterDates: [{start, end}]` |
| **法院级别** | "最高法院"/"高院"等 | `+courtLevel:((1))` (1=最高, 4=基层) |
| **文书类型** | "判决"/"裁定"等 | `+typeOfDecisionCode:((001))` (001=判决) |
| **原始 query** | 用户原话 | `simple:((query))` 让威科 smart matching 处理 |

### 5. 前置条件

- ✅ 已安装 wkinfo-cli skill（共享 cookie 源：`~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json`）
- ✅ 用户在威科已登录（cookie 有效）
- ⏳ 如果 cookie 失效：先跑 `python scripts/install_cookies.py --wait-login`

---

## 使用方法

### 完整流程（推荐）

```bash
cd ~/.claude/skills/威科案例检索和下载
```

#### 步骤 1：注入/验证 cookie（仅在登录失效时）

```bash
python scripts/install_cookies.py            # 注入现有 cookie
python scripts/install_cookies.py --wait-login  # 失效时引导手动登录
```

#### 步骤 2：搜索（输出 JSON 含完整元数据）

```bash
# 检索几个匹配案例
python scripts/search_cases.py \
  --query "建设工程实际施工人向发包人请求付款的案例，最高法院近三年判决" \
  --mode few --target 5 \
  --output ./原始文件/建设工程实际施工人_20260716/search_result.json

# 检索清单 (渐进式逼近 ≤200)
python scripts/search_cases.py \
  --query "股东代表诉讼的案例" \
  --mode list --max 200 \
  --output ./原始文件/股东代表诉讼_20260716/search_result.json
```

#### 步骤 3：下载（PDF/Word/Excel 三选一）

```bash
# few 模式：下载 PDF + 标黄
python scripts/download.py \
  --input ./原始文件/建设工程实际施工人_20260716/search_result.json \
  --format pdf --highlight --index \
  --output-dir ./原始文件/建设工程实际施工人_20260716/pdfs/

# list 模式：下载 Excel
python scripts/download.py \
  --input ./原始文件/股东代表诉讼_20260716/search_result.json \
  --format xls \
  --output-dir ./原始文件/股东代表诉讼_20260716/

# 一体化：搜索 + 下载
python scripts/download.py \
  --query "建设工程施工合同纠纷" --format xls \
  --output-dir ./原始文件/清单_20260716/ --limit 50
```

### Cookie 失效处理

如果出现以下情况，需要重新登录：
- `downloadPath` 返回 401/403
- `downloadLimit` 返回 `{result: false}`
- 搜索返回的 `score` 都是 0

处理：
```bash
python scripts/install_cookies.py --wait-login
# 浏览器弹出 → 手动登录威科 → 自动捕获新 cookie 并写回 storage
```

---

## 产出文件

| 文件 | 说明 |
|------|------|
| `<output-dir>/001_*.pdf` | 第一个案例的 PDF（自动编号 + 标黄） |
| `<output-dir>/README.md` | 索引文件（含匹配标记、大小、相关度） |
| `<output-dir>/search_result.json` | 搜索结果完整 JSON（含元数据） |
| `scripts/_research/` | 开发期调研脚本（仅供参考） |

---

## 复用关系

| 依赖 | 来源 |
|------|------|
| Cookie 源 | `~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json` |
| Edge 调试模式 | 由本 skill 自启（隔离 profile，不影响用户主 Edge） |
| 浏览器自动化 | CDP 协议（Playwright `connect_over_cdp`） |
| 中文编码规范 | CLAUDE.md 全局规范 |
| 项目文件夹规范 | CLAUDE.md 工作习惯（项目名-日期，4 个子目录） |

---

## 已知限制

1. **审级（trialProcedure / instanceCode）字段名未确认**，目前未在过滤器中实现
2. **部分维度（行业、地域）未实现**，依赖用户原话 smart matching
3. **PDF 标黄**依赖 pypdf 5.0+，已处理兼容性问题
4. **Wkinco 限频**：大量下载时需加 time.sleep，目前未内置
5. **中文 skill 命名**：与 skill-manager 兼容性未验证；如未来用 skill-manager 跟踪，可能需要改成 kebab-case

---

## 经验维护（tips 累积机制）

本 skill 通过 `references/retrieval-tips.md` 累积用户使用过程中的检索经验。每次调用 skill 前 agent 会自动 Read 该文件，应用 Section A 改写 query、Section B 拼接 filter、Section D 避开反模式。

### 何时追加 tip
- 用户口头补充具体经验（如"医疗期解除要加'另行安排工作'"）→ agent 自动 append 到对应段并回读确认

### 何时升级到代码层
- Section C 同 tip 出现 ≥2 次
- 或用户明示"以后都这样"、"记住这个"
→ agent 提示确认后，修改 `references/extra-synonyms.json`（新建）或 `民事案由_2025.json` 的 aliases 字段

### Review 节奏
- 每月 1 次 review Section D 反模式是否需要进 SKILL.md"已知限制"
- 不做自动批量升级，避免误升级导致回归

---

## 进阶：直接用 Python API

```python
import sys
sys.path.insert(0, '/root/.claude/skills/威科案例检索和下载/scripts')
from wkinfo_api import WkinfoClient, parse_search_results

client = WkinfoClient()
resp = client.search(query_string="建设工程施工合同纠纷", page_limit=10)
results = parse_search_results(resp)

for r in results:
    print(r['additionalFields']['documentNumber'], r['title'][:50])

# 下载第一个
client.download_file(
    doc_id=results[0]['docId'],
    file_type='pdf',
    search_id=results[0].get('searchId', ''),
    output_path='./out.pdf'
)
```

---

## 相关 skill

- **wkinfo-cli**: 共享 cookies，提供 `/csi/legislation/` 等法规检索
- **case-retrieval**: 接收本 skill 输出的 Excel，做 AI 分析 + 出报告
- **case-search**: 裁判文书网 / 人民法院案例库搜索（不同数据库）

