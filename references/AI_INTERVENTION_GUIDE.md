# 威科先行 (law.wkinfo.com.cn) AI 介入操作手册

> 用途：后续要在威科先行做任何自动化操作前，先读这份文档。  
> 状态：截至 2026-07-17 已验证可用，记录了所有踩过的坑。

---

## 0. 一句话总结

威科先行是 JS 重度渲染的 SPA，所有数据都通过 `/csi/*` 后端的 JSON API 暴露。**不需要爬 DOM**，直接调 API 就行；只有需要"反推 UI 操作背后的 API"时才用浏览器（用 CDP 接到隔离 profile 的 Edge 上）。

---

## 1. 三大入口

| 入口 | URL | 用途 |
|------|-----|------|
| 裁判文书搜索 | `/judgment-documents/list` | **真实工作入口**，1.78 亿份判决书/裁定书 |
| 案例评析搜索 | `/case-analysis/list` | 评论文章，不是原始判决书 |
| 详情页 | `/judgment-documents/detail/{base64-id}?searchId=...` | 单条判决书详情 |

**关键区分**：搜索结果会混入"案例评析"（typeOfDecision=008），需要主动排除 `-typeOfDecision:((008))`。

---

## 2. 鉴权：Cookie 共享

威科用 wkinfo-cli 风格的 cookie 鉴权。**整套 17 个 cookie 必须一起注入**，缺一不可：

```
userInfo, userInfoV5, username, loginin, autologin, identification,
acw_tc, connect.sid, cinfo, loginId, Hm_lvt_fecce484974a74c6d10f421b6d3bd395,
HMACCOUNT, CNZZDATA1261306096, Hm_lpvt_fecce484974a74c6d10f421b6d3bd395,
userConfig, check, UM_distinctid
```

**关键 cookie**（其他缺失会失败）：
- `userInfo` 里的 `id` 字段 → 用作请求头 `uid: 1000250387`
- `identification` → 用作请求头 `identification: _79cfe8d0...`
- `connect.sid` → 服务端会话

**推荐做法**：直接共享 `~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json`，自己别维护。

---

## 3. 三大核心 API（已 100% 摸清）

### 3.1 搜索 `POST /csi/search`

**请求体**（最小必需）：
```json
{
  "indexId": "law.case",                    // 必填！不加返回 400
  "query": {
    "queryString": "simple:((建设工程施工合同纠纷))",  // 必须 simple:() 包裹
    "filterDates": [],
    "filterQueries": ["+courtLevel:((1))"]    // Lucene 风格过滤
  },
  "searchScope": {"treeNodeIds": []},
  "relatedIndexQueries": [],
  "sortOrderList": [
    {"sortKey": "score", "sortDirection": "DESC"},   // 必须 score 优先！
    {"sortKey": "judgmentDate", "sortDirection": "DESC"}
  ],
  "pageInfo": {"limit": 100, "offset": 0},
  "chargingInfo": {"useBalance": true},
  "otherOptions": {
    "smartEnabled": true,        // 智能匹配开启
    "synonymEnabled": true,
    "mappingEnabled": true,
    "webSearchEnabled": false,
    ...
  }
}
```

**响应结构**：
```json
{
  "searchMetadata": {
    "searchId": "uuid",           // 下载时必须传回
    "docCount": 168527584,        // 实际匹配数（不是 total）
    "limitCount": 5000,
    ...
  },
  "documentList": [...],
  "resultGroups": [...],
  "relatedIndexCountList": [...]
}
```

### 3.2 计数 `POST /csi/search/doc-count`

请求结构同上，`response.searchMetadata.docCount` 就是匹配数。

### 3.3 下载（三步流程，**0 浏览器**）

```
1. POST /csi/document/downloadLimit  → 检查权限 {result: true/false}
2. POST /csi/document/downloadPath   → 获取 download key (UUID)
3. GET  /api/download?key={uuid}    → 文件二进制流
```

**fileType 映射**（注意 xls 不是 xls）：
- `pdf` → 响应 `application/pdf`
- `docx` → 响应 Word 文档
- `xls` / `excel` → 响应 .xls（用 `fileType: "excel"`）

**Excel/Word 必需 `cellList`**（24 个字段名）：
```
title,documentnumber,court,territory,typeofcase,causeofaction,
judgmentdatestr,instance,typeofdecision,subjectFee,
courtAcceptanceFee,judgmentReason,judgmentResult,judges,
plaintiff,defendant,thirdParty,trialProcess,
plaintiffattorney,defendantattorney,thirdpartyattorney,
plaintiffagent,defendantagent,thirdpartyagent
```

**文件名**：从 `Content-Disposition` 的 `filename*=UTF-8''...` 段拿（`filename=` 段是 latin-1 解码会乱码）。

---

## 4. URL 参数结构（侧边栏过滤器的"真相之源"）

**这是反推 API 语法的金矿**。每次点击侧边栏项，URL 会追加：

```
?fq=<field>Ɓ<value>ƁƂ<label>&fq=...
```

分隔符：
- `Ɓ` = `ǁ`（字段/值分隔）
- `Ƃ` = `ǂ`（值/标签分隔）

URL 解码示例：
```
fq=court%C7%81003000000%E5%8C%97%E4%BA%AC%E5%B8%82%C7%81%C7%82%E5%8C%97%E4%BA%AC%E5%B8%82
↓
courtƁ003000000北京市ƁƂ北京市
↓
field=court, value=003000000北京市, label=北京市
```

**注意**：value 字段里也可能含 `Ɓ`（多层案由路径），所以解析要用 `rfind('ǂ')` 切最后一个 `Ƃ`。

**为什么这个 insight 至关重要**：威科的 filter 字段名（`judgmentYear` vs `judgmentDate`、`courtText` vs `court`）和编码（`001` vs `01` vs `1`）非常不直观，盲猜 API 字段会浪费几小时。直接看 URL 变化 5 分钟搞定。

---

## 5. 已验证的所有过滤器（直接抄）

### 5.1 法院级别 `courtLevel`（单数字）
```python
COURT_LEVEL_MAP = {
    "最高人民法院": 1, "高级人民法院": 2, "中级人民法院": 3,
    "基层人民法院": 4, "专门法院": 5,
}
# 语法: +courtLevel:((1))
```

### 5.2 文书类型 `typeOfDecisionCode`（3 位数字）
```python
DOC_TYPE_MAP = {
    "判决书": "001", "裁定书": "002", "决定书": "003",
    "调解书": "004", "通知书": "006", "令": "007", "案例评析": "008",
}
# 语法: +typeOfDecisionCode:((001))
```

### 5.3 审级 `instance`（3 位数字）
```python
INSTANCE_MAP = {
    "一审": "001", "二审": "002", "再审": "003", "破产": "004",
    "执行": "005", "死刑复核": "006", "公示催告": "007", "督促": "008",
}
# 语法: +instance:((002))
```

### 5.4 裁判日期 `judgmentYear`（Lucene 范围，**唯一正确方式**）
```python
# 语法: +judgmentYear:([YYYY TO YYYY+1])   ← YYYY+1 是闭区间开
# 语法: +judgmentYear:([* TO YYYY])
# 语法: +judgmentYear:([YYYY TO *])
# 注意: filterDates 字段不能用，会 500
```

实测各选项对应的语法：
| 侧边栏选项 | API 语法 |
|-----------|---------|
| 最近1年 | `+judgmentYear:([2025 TO 2027])` |
| 最近3年 | `+judgmentYear:([2023 TO 2027])` |
| 最近5年 | `+judgmentYear:([2021 TO 2027])` |
| 2026年 | `+judgmentYear:([2026 TO 2027])` |
| 2001年至2021年 | `+judgmentYear:([* TO 2022])` |
| 近三年（日期）| `+judgmentYear:([2024.07.16 TO 2026.07.17])` |

### 5.5 审理法院 `court`（9 位数字 + 中文名，37 个全覆盖）

完整列表见 `wkinfo_api.py:COURT_MAP`。**编码不按地理位置顺序**（北京=003, 上海=024, 广东=007），是 wkinfo 内部 ID。  
**语法**: `+court:((024000000上海市))`

### 5.6 案由顶级 `causeOfAction`（14 位数字 + 中文名）
```python
CAUSE_OF_ACTION_MAP = {
    "民事": "01000000000000民事", "刑事": "02000000000000刑事",
    "行政": "03000000000000行政", "国家赔偿": "04000000000000国家赔偿",
    "执行": "05000000000000执行",
}
# 语法: +causeOfAction:((01000000000000民事))
# 子案由需要完整路径：
# +causeOfAction:((01000000000000民事/01030000000000物权纠纷))
```

### 5.7 行业 `industryCode`（单字母，A-R 已验证）
```python
INDUSTRY_MAP = {
    "农、林、牧、渔业": "A", "采矿业": "B", "制造业": "C",
    "电力、热力、燃气及水生产和供应业": "D", "建筑业": "E",
    "批发和零售业": "F", "交通运输、仓储和邮政业": "G",
    "住宿和餐饮业": "H", "信息传输、软件和信息技术服务业": "I",
    "金融业": "J", "房地产业": "K", "租赁和商务服务业": "L",
    "科学研究和技术服务业": "M", "水利、环境和公共设施管理业": "N",
    "居民服务、修理和其他服务业": "O", "教育": "P",
    "卫生和社会工作": "Q", "文化、体育和娱乐业": "R",
}
# 语法: +industryCode:((J))
```

### 5.8 参照级别 `referenceLevelNew`（2 位数字）
```python
REFERENCE_LEVEL_MAP = {
    "最高检指导性案例": "02", "公报案例": "04",
    "上海金融法院精选案例": "06", "律师评案": "08",
    "威科推荐案例": "09", "其他": "10",
}
# 语法: +referenceLevelNew:((04))
```

---

## 6. 关键请求头（缺一会被拦）

```python
headers = {
    "cookie": "<从 wkinfo-cookies.json 拼接的字符串>",
    "uid": "1000250387",                          # 从 userInfo.id 提取
    "identification": "_79cfe8d062d911f1...",   # 从 identification cookie 提取
    "module": "",                                 # 空字符串
    "user-agent": "Mozilla/5.0 ... Chrome/150 ...",  # 用真实浏览器 UA
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://law.wkinfo.com.cn/judgment-documents/list",
    "content-type": "application/json;charset=UTF-8",  # 仅 POST 需要
}
```

---

## 7. 实战中最容易踩的坑（按踩坑频率排）

### 7.1 致命坑
- ❌ **`queryString` 没包 `simple:((...))`** → 返回 score=0 的无关结果
- ❌ **`indexId` 字段缺失** → 返回 400 "indexId不能为空"
- ❌ **没按 `score` 排序** → 返回 score=0 的无意义结果
- ❌ **`filterDates` 字段** → 500，必须用 `judgmentYear` 范围
- ❌ **`uid` 头缺失**（从 userInfo 解码）→ 请求被拦
- ❌ **cookie value 是 URL-encoded** → 必须先 `urllib.parse.unquote` 才能 regex

### 7.2 沉默坑（不报错但结果不对）
- ⚠️ 用户原话里的过滤词（"最高法"、"二审"、"近三年判决"）如果放在 `queryString` 里，会被当成额外关键词强制匹配，导致命中数变 0。**必须剥掉这些词**
- ⚠️ `judgmentYear:([2024-01-01 TO 2026-12-31])`（ISO 日期带连字符）→ 返 0，必须用 `TO` 关键字
- ⚠️ `instanceCode:((001))`、`trialProcedure:((001))`、`procedure:((001))` 都是 0 — 真实字段是 `instance`（不带 Code）
- ⚠️ `court:((最高人民法院))` → 0，必须用 `001000000最高人民法院` 编码形式
- ⚠️ `causeOfAction:((01030000000000物权纠纷))` 单独用是 0，必须带顶层路径 `01000000000000民事/01030000000000物权纠纷`

### 7.3 中文数字陷阱
- ⚠️ 正则 `\d+` 不匹配"三"（中文数字）。匹配"近三年"需要 `[\d零一二三四五六七八九十两]+`
- ⚠️ 用户说"近N年" 时 `from=now-N, to=now`（包含当前年）

---

## 3.5 多库架构（LIBRARIES 注册表）

威科先行有 5 个库（案例/法规/处罚/实务/专题），但底层 API 是一致的。差异通过 `LIBRARIES` 注册表配置：

```python
@dataclass
class Library:
    key: str                       # 短代码（"case" / "legislation" / "penalty" / "commentary" / "focus"）
    name: str                      # 中文名
    index_id: str                  # API 用的 indexId（每个库不同！）
    list_url: str                  # 列表页 URL
    field_maps: dict               # 字段名 → MAP（{字段名: {值: 代码}}）

LIBRARIES = {
    "case": Library("case", "裁判文书", "law.case", "/judgment-documents/list", CASE_MAPS),
    "legislation": Library("legislation", "法律法规", "law.legislation", "/legislation/list", LEGISLATION_MAPS),
    "penalty": Library("penalty", "行政处罚", "law.administrativeSupervision", "/administrative-punishment/list", PENALTY_MAPS),
    "commentary": Library("commentary", "实务指南", "law.commentaryB", "/commentary/list", COMMENTARY_MAPS),
    "focus": Library("focus", "专题聚焦", "law.specialTopic", "/focus/list", FOCUS_MAPS),
}
```

### 五库的 indexId、排序字段、内容类型都不同

| 库 | indexId | 排序字段 | URL | 内容类型 |
|---|---|---|---|---|
| 案例 (case) | `law.case` | `score DESC, judgmentDate DESC` | `/judgment-documents/list` | 原始判决书 |
| 法规 (legislation) | `law.legislation` | `score DESC, promulgatingDate DESC` | `/legislation/list` | 法律全文 |
| 处罚 (penalty) | `law.administrativeSupervision` | `orderPriority ASC, score DESC, superviseDate DESC` | `/administrative-punishment/list` | 处罚决定 |
| 实务 (commentary) | `law.commentaryB` | `score DESC, lastReviewDate DESC` | `/commentary/list` | 编辑部实务文章 |
| 专题 (focus) | `law.specialTopic` | `score DESC, promulgatingDate DESC` | `/focus/list` | 专题报告 |
| 处罚 (penalty) | `law.administrativeSupervision` | `orderPriority ASC, score DESC, superviseDate DESC` | `/administrative-punishment/list` |

### 三大库入口在首页搜索框下方那行按钮里

点击"法律法规"按钮 → 跳到 `/legislation/list`  
点击"行政处罚"按钮 → 跳到 `/administrative-punishment/list`  
案例库"裁判文书"是搜索结果默认进入的（也是首页默认）

### 加新库的标准流程

加新库（如"行业资讯"、"法规速递"）只需：

1. **首页按钮调研**：调试 Edge 打开首页，找搜索框下方的按钮列表，记录每个按钮的 URL
2. **侧边栏 + API 反推**：按"场景 A"流程反推每个过滤项的 URL fq，确定字段名和编码
3. **抓真实请求的 indexId**：用 Playwright 拦截浏览器实际请求，从 body 拿到 indexId（**不是猜的！**）
4. **wkinfo_api.py 加 LIBRARY 配置**：
   ```python
   NEW_LIB_MAPS = {
       "xxxField": {"值1": "code1", "值2": "code2"},
       ...
   }
   LIBRARIES["newkey"] = Library(
       key="newkey", name="新库名",
       index_id="law.xxx", list_url="/xxx/list",
       field_maps=NEW_LIB_MAPS,
   )
   ```
5. **加 search_xxx.py 薄壳**（参考 search_laws.py）
6. **测试 + 更新 SKILL.md 触发词**

整个过程**不需要修改** WkinfoClient/search/nl_parser — 它们已经按库通用设计。

### 各库的 sort 字段差异坑

错误信息通常是 `{"code":"E_000_006","message":"搜索结果为空"}` — 这往往不是真的没结果，而是 **secondary sort 字段名错误**。

解决：抓浏览器实际请求（用 `page.on("request")` 监听），看浏览器用的 `sortOrderList` 是什么，照抄。

---

## 8. 推荐工作流（按场景选）

### 场景 A: 实现一个新过滤器（最常见）
**最快路径**（5-10 分钟）：
1. 用户给一个真实查询的需求描述（如"广东金融业近三年")
2. **不要盲猜 API 字段**！直接在调试 Edge 里操作一次：
   - 打开 `/judgment-documents/list`
   - 设置关键词 + Enter 触发搜索
   - 点击对应侧边栏项
   - **复制 URL** 给我
3. 解析 URL 的 `fq` 段，提取 `field:value:label` 三元组
4. 用 `requests` 直接验证 `field:value` 格式是否有效
5. 写入 `wkinfo_api.py` 的对应 MAP
6. 接入 `nl_parser.py` 的抽取逻辑
7. 端到端测试

### 场景 B: 实现新的搜索维度（如"开庭公告"、"庭审视频"）
1. 在调试 Edge 点击该维度项
2. URL 变化但**没显示 fq 参数** → 说明是前端本地过滤，不是 API 过滤
3. 检查搜索结果的 `documentList[i].additionalFields` 字段，看是否能用作后过滤
4. 如果需要，扩展 `search.py` 在拿到结果后用 additionalFields 做 Python 端过滤

### 场景 C: 批量下载（大量 PDF）
1. 用 `/csi/search` 拿第一页（page_limit=100）
2. 循环 `page_offset` 直到拿完所有结果
3. 对每条结果：
   - 下载三步 API（注意限频，加 `time.sleep(0.5)`）
   - 文件名从 `Content-Disposition.filename*=UTF-8''...` 取
4. 用 pypdf 或 reportlab 后处理（标黄、合并、加书签）

### 场景 D: 登录态失效
1. 跑 `install_cookies.py --wait-login`（自动引导手动登录并写回 cookie）
2. 手动登录后 cookie 自动保存
3. 验证：`python wkinfo_api.py "<关键词>"` 命中数 > 0

---

## 9. 浏览器自动化要点（如果非要用）

### 9.1 Edge 隔离 profile 启动（不打扰用户主 Edge）
```powershell
Start-Process 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' `
  -ArgumentList '--remote-debugging-port=9222',`
               '--no-first-run',`
               '--no-default-browser-check',`
               '--user-data-dir=D:\ai\Claudecode\<项目>\临时资源\edge-debug-profile'
```

用户主 Edge 不动，调试 Edge 独立。

### 9.2 CDP 连接 + 关闭多余标签
```python
b = pw.chromium.connect_over_cdp('http://localhost:9222')
# 关闭非 wkinfo 的标签页节省内存
for p in ctx.pages[:]:
    if 'wkinfo.com.cn' not in p.url:
        p.close()
```

### 9.3 点击侧边栏项的正确姿势
**绝对不要只点一次**！必杀技：
```js
// 1. 先点所有 "查看更多" 展开（不然省份/行业等列表被折叠）
document.querySelectorAll('li.more').forEach(m => m.click());

// 2. 用 window.scrollTo 把目标元素滚到视口内（侧边栏不是内部滚动的）
const target = Array.from(document.querySelectorAll('a.wk-tree-node-label'))
  .find(l => l.textContent.trim() === '北京市');
const rect = target.getBoundingClientRect();
window.scrollTo(0, window.scrollY + rect.top - 300);

// 3. Playwright 的 click() 会自动处理可见性（不要 force=True，会跳过事件）
loc = page.locator('a.wk-tree-node-label').filter(has_text='北京市').first
loc.click(timeout=5000);

// 4. URL 变化后立刻读 page.url 提取 fq
```

### 9.4 浏览器交互失败常见原因
| 现象 | 真因 | 解决 |
|------|------|------|
| click 后 URL 不变 | 元素在视口外，没滚动 | 用 `window.scrollTo` |
| 点击后超时 | 元素在"查看更多"折叠里 | 先点 `li.more` |
| locator 找不到元素 | 文本匹配方式错了 | 用 `.filter(has_text='北京市').first` |
| 多次 click 累积 fq | URL 累积不重置 | 每次 `page.goto()` 重新加载 |

---

## 10. 已知未完成 / 边界

| 缺口 | 影响 | 解决方向 |
|------|------|---------|
| `instanceCode`、`trialProcedure` 等字段名返回 0 | 审级只能用 `instance` 字段 | 已知正确，文档已记 |
| 部分 `referenceLevelNew` 值（01/03/05/07）返 0 | 最高法指导性案例、入库案例等过滤不到 | 需要用户手动提供 URL 才能确认 |
| 案由子级（第四级）只能通过完整路径 | 子案由精度受限 | 已知正确，文档已记 |
| 庭审视频、文书篇幅、标的额等维度 | 未实现 | 沿用同样方法：点侧边栏看 URL |
| 多 `fq` 累积解析 | 解析时只取第一个 court | 已用 `rfind('ǂ')` 修 |

---

## 11. 代码组织（已实现的 skill）

| 文件 | 作用 |
|------|------|
| `wkinfo_api.py` | 威科 API 客户端（搜索/计数/下载）+ 所有 MAP |
| `nl_parser.py` | 自然语言 → SearchParams |
| `search_cases.py` | 搜索 CLI（含渐进式逼近）|
| `download.py` | 下载 CLI（PDF/Word/XLS）|
| `highlight_pdf.py` | PDF 标黄 |
| `install_cookies.py` | Cookie 注入 |
| `parse_case_causes.py` | 解析案由 JSON |

---

## 12. 一句话策略

> **要新增任何威科能力，先在调试 Edge 里手动操作一次让 URL 变化，解析 `fq` 参数得到 API 语法，然后 `requests` 验证，5-10 分钟搞定一个完整过滤器。**

不要尝试：
- ❌ 盲猜 API 字段名（会被各种 silent bug 困住）
- ❌ 用 DOM 解析提取数据（Angular 虚拟滚动 + JSX 渲染成本高）
- ❌ 直接爬详情页 HTML（不稳定 + 反爬风险）

始终：
- ✅ API 优先，浏览器仅用于反推
- ✅ Cookie 共享 wkinfo-cli skill 的 storage
- ✅ URL 变化是反推过滤器语法的唯一可靠信号
- ✅ 测试时小批量验证（一次只测一个维度）
- ✅ 失败时打印**响应体**（API 错误信息往往在 body 里）

---

## 13. 验收清单

新过滤器接入后必跑：
```bash
# 1. 单过滤器单元验证
python -c "
from wkinfo_api import WkinfoClient
c = WkinfoClient()
print(c.doc_count(query_string='<测试关键词>', filter_queries=['<新过滤器>']))
"

# 2. 多过滤器组合验证
python search_cases.py --query "<用户原话>" --mode few --target 5 --verbose

# 3. 自然语言抽取验证
python nl_parser.py "<用户原话>"
```

三个都通过 + 实际下载一条文件能打开 = 可发布。