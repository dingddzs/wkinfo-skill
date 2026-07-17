# 威科案例检索和下载 Skill

> 开发日期：2026-07-16  
> 状态：可工作，端到端通过（PDF/Excel/Word 三种格式下载）

---

## 项目目标

让用户用自然语言描述案例检索需求（如"建设工程实际施工人向发包人请求付款的案例，最高法院近三年判决"），自动从威科先行（law.wkinfo.com.cn）检索并下载案例文档（PDF / Word / Excel）。

## 双模式工作流

| 模式 | 触发词 | 输出 | 数量上限 |
|------|--------|------|---------|
| **few** | "几个/几份/挑几个" | PDF（每份标黄）| 默认 5，可指定 |
| **list** | "清单/汇总/全部" | Excel (xls) | 渐进式逼近 ≤200 |

## 项目结构

```
威科案例检索和下载-20260716/
├── README.md                     # 本文件
├── 开发日志.md                    # 阶段性进展记录
├── 脚本和代码/                    # 生产脚本
│   ├── install_cookies.py         # Cookie 注入（共享 wkinfo-cli storage）
│   ├── wkinfo_api.py              # 威科 API 客户端（搜索/计数/下载）
│   ├── nl_parser.py               # 自然语言 → 结构化检索参数
│   ├── parse_case_causes.py       # 解析《民事案件案由规定》(2025版) → JSON
│   ├── search_cases.py            # 搜索 CLI（含渐进式逼近）
│   ├── download.py                # 下载 CLI（PDF/DOCX/XLS）
│   ├── highlight_pdf.py           # PDF 标黄工具
│   └── _research/                 # 开发期调研脚本（保留供参考）
├── 处理后文件/
│   └── 民事案由_2025.json         # 案由词典（514 第三级 + 470 第四级）
├── 原始文件/                      # 用户原始文件 + 下载结果
├── 临时资源/
│   ├── OCR/                       # 案由规定全文 OCR
│   ├── 截图/                      # 页面调研截图
│   └── 网络请求/                   # 调研抓的 API 请求样例
└── references/                    # 调研产出文档
    ├── wkinfo-cases-page.md       # 威科页面结构 + API 文档
    └── nl-patterns.md             # 自然语言抽取规则
```

## 快速使用

### 1. 注入登录态（一次）

```bash
cd "D:/ai/Claudecode/威科案例检索和下载-20260716/脚本和代码"
python install_cookies.py
```

启动一个隔离 profile 的 Edge（不影响用户现有 Edge），注入 wkinfo-cli 的 cookies。

### 2. 搜索案例

```bash
# 检索几个匹配案例 (few 模式, 输出 JSON 含结果列表)
python search_cases.py --query "建设工程实际施工人向发包人请求付款，最高法近三年判决" --mode few --target 5 --output ./原始文件/result.json

# 检索清单 (list 模式, 渐进式逼近 ≤200)
python search_cases.py --query "股东代表诉讼" --mode list --max 200 --output ./原始文件/result.json
```

### 3. 下载文件

```bash
# 从 JSON 下载 PDF + 标黄
python download.py --input ./原始文件/result.json --format pdf --output-dir ./原始文件/pdfs/ --highlight --index

# 下载 Excel
python download.py --input ./原始文件/result.json --format xls --output-dir ./原始文件/excel/

# 一体化：搜索 + 下载
python download.py --query "建设工程施工合同纠纷" --format xls --output-dir ./原始文件/ --limit 50
```

## 技术亮点

1. **无需浏览器**：搜索和下载均走威科 API（基于 `wkinfo-cookies.json`），速度快且稳定
2. **基于《案由规定》(2025)**：用官方 514+470 个案由做关键词匹配，匹配精度高
3. **渐进式逼近**：list 模式下，宽→窄自动迭代逼近 ≤200 条
4. **PDF 标黄**：自动添加黄色便签注释 + 文件名前缀
5. **共享 Cookie 源**：复用 `wkinfo-cli` skill 的 cookies，无重复维护

## 已知限制

- `trialProcedure`（审级）字段在威科 API 中未确认（用了 `instanceCode` 也未匹配），目前未注入
- 部分检索维度（行业、地域）未实现 filter
- PDF 标黄依赖 pypdf 5.0+，已处理兼容性问题

## 下一步改进方向

- [ ] 调研 `instanceCode` 实际字段名（捕获浏览器点击"一审"/"二审"时的 API）
- [ ] 添加"行业"、"地域"过滤器
- [ ] 实现真正的"语义匹配"模式（用户场景描述 → 自动找案由）
- [ ] PDF 内容搜索（在已下载的 PDFs 中找关键字）
- [ ] 配合 `case-retrieval` skill 做端到端流水线