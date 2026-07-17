# 威科案例检索和下载 Skill — 更新日志

> 本日志**每次更新代码必须同步更新**（见 `PROJECT_GUIDE.md` 第 11 节"代码-文档同步规则"）。  
> 格式：每个版本一段，**逆时间序**（最新在上）。  
> 字段：版本号 / 日期 / 主要改动 / 受影响文件。

---

## v1.3.0 — 2026-07-17 — 五库并行研究工作流

**新增**：
- 加 `实务指南`（`/commentary/list`, `indexId=law.commentaryB`）和 `专题聚焦`（`/focus/list`, `indexId=law.specialTopic`）两个研究性库到 `LIBRARIES`
- `research.py` — 跨 5 库并行搜索，输出结构化信源汇总
- `PROJECT_GUIDE.md` — 新人接管项目的路线图
- `CHANGELOG.md` — 本文件

**改动**：
- `wkinfo_api.py` v1.2 → v1.3：新增 `COMMENTARY_MAPS` / `FOCUS_MAPS`，扩展 `LIBRARIES` 注册表
- `SKILL.md` description 加"调研XX"、"研究XX"研究类触发词，加"法律研究信源"段
- `AI_INTERVENTION_GUIDE.md` 表格更新为 5 库

**影响**：
- 写法律文书时，skill 自动从 5 库并行拉信源（之前只能单库）
- `research.py` 是新核心入口，CLI 直接调用

**对应提交**：尚未提交 GitHub（待用户创建 remote）

---

## v1.2.0 — 2026-07-17 — 三库 + 注册表重构

**新增**：
- 加 `法律法规`（`/legislation/list`, `indexId=law.legislation`）库
- 加 `行政处罚`（`/administrative-punishment/list`, `indexId=law.administrativeSupervision`）库
- `search_laws.py` / `search_penalties.py` 薄壳
- LIBRARIES 注册表重构，5 行配置接入新库

**改动**：
- `wkinfo_api.py` v1.1 → v1.2：加 `LEGISLATION_MAPS` / `PENALTY_MAPS`，拆 `field_maps` 进 `Library` 对象
- 各库独立 `sortOrderList`（cases 用 `judgmentDate`、legislation 用 `promulgatingDate`、penalty 用 `orderPriority/superviseDate`）

**影响**：
- 不再盲猜 API 字段名（已建立"从浏览器反向抓取"流程）

---

## v1.1.0 — 2026-07-16 — 案例库字段补完

**新增**：
- 37 个法院编码（`COURT_MAP`）—通过浏览器侧边栏点击抓取，覆盖全国
- 审级（`instance`）、裁判日期（`judgmentYear`）、案由顶级（`causeOfAction`）、行业（`industryCode`）、参照级别（`referenceLevelNew`）字段全部生效
- queryString 剥离过滤词、`filterDates` → `judgmentYear` 范围语法
- 自适应渐进式逼近（跳过 0 命中和无效过滤）

**改动**：
- `wkinfo_api.py` v1.0 → v1.1：加 ~100 行 MAP 定义和 fix bug
- `search_cases.py`：加 `build_filter_queries()` 用 MAP 路径

**关键教训**：
- 同一个 `filterQueries` 内多个过滤项是 AND，**同一字段**多值是 OR
- 同一字段语义可能跨字段名（如 `courtLevel`/`courtText`/`court`）
- 编码格式多样（`1`、`01`、`001`、`D010`、`B255` 等）

---

## v1.0.0 — 2026-07-16 — 初版

**功能**：
- 裁判文书检索（`/judgment-documents/list`）
- 侧边栏筛选（法院级别、文书类型）
- PDF / Word / Excel 三种格式下载（3 步 API：`downloadLimit` → `downloadPath` → `/api/download`）
- 渐进式逼近（宽→窄自动迭代）
- Edge debug 实例 + Cookie 共享

**核心文件**：
- `wkinfo_api.py` — API 客户端
- `search_cases.py` — CLI 入口
- `download.py` — 下载
- `highlight_pdf.py` — PDF 标黄
- `install_cookies.py` — Cookie 注入

**创新**：
- **零浏览器依赖**（生产路径只用 cookies）
- **从 URL 反推 API 字段名**而非盲猜
- **Cookie 共享** `wkinfo-cli` skill

---

## 待发布

无

---

## 维护说明

### 何时新增一段 changelog
- 改了 `wkinfo_api.py`、某个 MAP、新增/删除 library → 必须
- 改了 NL parser 正则 → 必须
- 加了新 CLI 脚本 → 必须
- 改了 SKILL.md 触发词 → 必须
- 文档/小 typo → 可选

### 提交消息约定（用 Conventional Commits）
```
feat(case): 加 37 个法院编码
fix(legislation): 用 promulgatingDate 替代 judgmentDate
docs: 更新 v1.3 changelog
chore: 更新 .gitignore
```

### 版本号
- **MAJOR** v1 → v2：不兼容改动（如删库、改 API 形态）
- **MINOR** v1.2 → v1.3：新增库 / 新功能 / 新 CLI
- **PATCH** v1.3.0 → v1.3.1：bug 修复 / MAP 增补

### 同步发布 checklist
1. 改代码
2. 跑验收清单（见 `PROJECT_GUIDE.md` 第 9 节）
3. 更新 `CHANGELOG.md` 加一段
4. 更新 `SKILL.md` 的 `metadata.version` + `changelog:`
5. 更新 `PROJECT_GUIDE.md`（如果改了架构）
6. `git add -A && git commit -m "feat: ..."`
7. （可选）`git push origin main`
