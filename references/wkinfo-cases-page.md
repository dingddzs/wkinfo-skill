# 威科案例检索和下载 — 调研文档

> 调研时间：2026-07-16
> 调研人：Claude + 用户
> 调研方法：通过 CDP 连接到隔离 Edge 实例，监听真实交互下的网络请求

---

## 1. 关键 URL 路径

| 名称 | URL |
|------|-----|
| 案例搜索页 | `https://law.wkinfo.com.cn/judgment-documents/list` |
| 案例详情页 | `https://law.wkinfo.com.cn/judgment-documents/detail/{base64-doc-id}?searchId=...&index=...&q=...&module=` |
| 案例评析页（不是判决文书，搜索结果里会混入）| `https://law.wkinfo.com.cn/case-analysis/list` |
| 案例评析详情 | `https://law.wkinfo.com.cn/case-analysis/detail/{base64-id}` |

**重要**：`/judgment-documents/list` 是裁判文书搜索页，`/case-analysis/list` 是案例评析（评论文章）搜索页，两者**不要混淆**。

---

## 2. 搜索页结构（`/judgment-documents/list`）

### 2.1 搜索框

```html
<input id="keyword" name="keyword" type="search" maxlength="50"
       placeholder="在裁判文书中搜索..." class="ng-untouched ng-pristine ng-valid">
```

- 仅标题复选框：`<input type="checkbox" name="isTitleExtend">`
- 显示摘要复选框：`<input type="checkbox" name="showAbstract">`
- 搜索按钮：`.search-btn`（div）或 `.wk-banner-action-bar-item`（button）
- 高级搜索按钮：`.advanced-search-btn`

### 2.2 侧边栏过滤维度（按页面顺序）

| 维度 | 文案 | 数量级（参考）|
|------|------|-------------|
| 法院级别 | 最高人民法院/高级人民法院/中级人民法院/基层人民法院/专门法院 | 165k ~ 155M |
| 参照级别 | 最高法指导性案例/最高检指导性案例/入库案例/公报案例/官方典型案例/上海金融法院精选案例/法官评案/律师评案/威科推荐案例/其他 | 256 ~ 178M |
| 行业 | 金融业/制造业/房地产业/建筑业/信息传输.../批发零售... | 295k ~ 16M |
| 审理法院 | 最高人民法院/北京市/天津市/...（省级 + "查看更多"展开）| 80 ~ 8M |
| 案由 | 民事/刑事/行政/国家赔偿/执行/其他 | 8 ~ 150M |
| 审判程序 | 一审/二审/再审/破产/执行/死刑复核/公示催告/督促/其他 | 4k ~ 106M |
| 裁判日期 | 最近1年/最近3年/最近5年/2026年/2025年/.../2001年之前 | 1.6M ~ 138M |
| 文书类型 | 判决书/裁定书/决定书/调解书/其他/通知书/令/开庭公告/案例评析 | 47k ~ 82M |
| 文书篇幅 | 500字以上/500字以下 | 76M ~ 101M |
| 标的额 | 50万元以上/50万元以下 | 5M ~ 32M |
| 案件受理费 | 1000元以上/1000元以下 | 29M ~ 38M |
| 文书公开程度 | 全文公开/非全文公开 | 22M ~ 143M |
| 庭审视频 | 是 | 3M |
| 刑罚 | 主刑/附加刑/缓刑/执行变更/免予刑事处罚/无罪 | 5k ~ 5M |
| 法律法规 | 裁判文书 / 行政监管 / 专业解读 | - |

每个过滤器元素是 `<div class="wk-tree-node-content">` 包裹的 label/span，点击会触发过滤。

### 2.3 搜索结果项

每条结果的 HTML 结构（示意）：
```html
<div class="wk-search-list-item">
  <a href="https://law.wkinfo.com.cn/judgment-documents/detail/MjA0MTUzMjY0NDg%3D?searchId=...&index=1&q=...">
    <div class="result-title">某保险公司与孙某保证保险合同纠纷一案</div>
    <div class="result-meta">山东省平度市人民法院(2026)鲁0283民初2978号2026.07.13 裁判</div>
    <div class="result-summary">中国裁判文书网 ...</div>
  </a>
</div>
```

URL 中的 `{base64-doc-id}` 解码后是数字 ID（如 `MjA0MTUzMjY0NDg=` = `20415326448`）。

---

## 3. 搜索 API（直接调用，无需浏览器）

### 3.1 POST `/csi/search`

**请求头**（必需）：
```
cookie: <从 wkinfo-cookies.json 拼接>
content-type: application/json;charset=UTF-8
uid: 1000250387                  # 从 userInfo cookie 解码
identification: _79cfe8d062d911f1b542513c0fcf6872  # 从 identification cookie
module:                          # 留空
user-agent: Mozilla/5.0...
referer: https://law.wkinfo.com.cn/judgment-documents/list
```

**请求体**（示例：搜索"建设工程施工合同"，排除案例评析）：
```json
{
  "query": {
    "queryString": "建设工程施工合同",
    "filterDates": [],
    "filterQueries": [
      "-typeOfDecision:((008))"     // 排除案例评析 (type 008)
    ]
  },
  "searchScope": {
    "treeNodeIds": []
  },
  "relatedIndexQueries": [],
  "sortOrderList": [
    {"sortKey": "judgmentDate", "sortDirection": "DESC"}
  ],
  "pageInfo": {
    "limit": 100,
    "offset": 0
  },
  "chargingInfo": {
    "useBalance": true
  },
  "otherOptions": {
    "requireLanguage": "cn",
    "relatedIndexEnabled": true,
    "groupEnabled": false,
    "smartEnabled": true,
    "buy": false,
    "summaryLengthLimit": 100,
    "synonymEnabled": true,
    "advanced": false,
    "isHideBigLib": 0,
    "relatedIndexFetchRows": 5,
    "proximateCourtID": "",
    "module": "",
    "correctEnabled": true,
    "mappingEnabled": true
  }
}
```

**响应**：JSON，包含搜索结果列表（每项含 `docId`、`title`、`caseNo`、`court`、`judgmentDate` 等）。

### 3.2 POST `/csi/search/doc-count`

请求结构同上，但只返回命中数（用于渐进式逼近时快速判断"是否超过 200 条"）。

### 3.3 过滤器语法（Lucene-like）

| 场景 | filterQueries 写法 |
|------|------------------|
| 排除案例评析 | `["-typeOfDecision:((008))"]` |
| 仅判决书 | 待调研（类似 `+typeOfDecision:((001))`） |
| 指定法院 | 待调研（类似 `+court:((2CO00000076))`） |
| 时间范围 | `filterDates: [{start: "2022-01-01", end: "2025-12-31"}]` |
| 文书类型 | `+typeOfDecision:((001))` |
| 案由 | `+caseCause:((...))` |

---

## 4. 下载 API（核心发现：无需浏览器）

### 4.1 下载流程（3 步）

```
1. POST /csi/document/downloadLimit    → 检查下载权限
2. POST /csi/document/downloadPath    → 获取 download key (UUID)
3. GET  /api/download?key={uuid}      → 实际下载文件
```

### 4.2 Step 1: POST `/csi/document/downloadLimit`

**请求体**：
```json
{
  "indexId": "law.case",
  "fileType": "pdf",        // "pdf" / "docx" / "xls"
  "docId": "MjA0MTUzMjY0NDg=",   // base64 doc id（URL 中的）
  "showType": 0,
  "module": "",
  "cellList": null
}
```

**响应**：`{"state":"SUCCESS","result":true}` 表示可以下载。

### 4.3 Step 2: POST `/csi/document/downloadPath`

**请求体**：
```json
{
  "indexId": "law.case",
  "fileType": "pdf",
  "docId": "MjA0MTUzMjY0NDg=",
  "showType": 0,
  "filename": "某保险公司与孙某保证保险合同纠纷一案_20260716下载.pdf",
  "module": "",
  "searchId": "414d083230784dcfb945e42824384f25",  // 从搜索结果 URL 取
  "containLink": true
}
```

**响应**：
```json
{
  "data": {
    "key": "752f1070-80e9-11f1-804e-3538e8f6f193",
    "filename": "某保险公司与孙某保证保险合同纠纷一案_20260716下载.pdf"
  }
}
```

### 4.4 Step 3: GET `/api/download?key={uuid}`

**响应头**：
```
content-type: application/pdf
content-disposition: attachment; filename*=UTF-8''%E6%9F%90%E4%BF%9D...%E4%B8%8B%E8%BD%BD.pdf
```

**响应体**：PDF / DOCX / XLS 二进制流。

**注意**：filename 头有两份：
- `filename=...`（Latin-1 解码，中文会乱码）
- `filename*=UTF-8''...`（URL-encoded UTF-8，**用这个**）

### 4.5 文件格式

| fileType | 实际文件格式 | 文件名后缀 |
|----------|-------------|-----------|
| `pdf`    | application/pdf | .pdf |
| `docx`   | Word 文档 | .docx |
| `xls`    | Excel | .xls（威科用旧格式）|

### 4.6 已验证可行性

✅ 用 `requests` 库直接调用，**不需要浏览器**，完整三步流程：
- downloadLimit: 200 OK
- downloadPath: 200 OK, 返回 key
- /api/download: 200 OK, 返回 121KB PDF（`%PDF-` 头）

---

## 5. 详情页工具栏（浏览器场景下）

判决书详情页 `/judgment-documents/detail/...` 顶部工具栏有 7 个按钮（按位置 x 排序）：

| x | 元素 ID 模式 | 功能 | 备注 |
|---|------------|------|------|
| 1333 | `favorites{caseId}` | 收藏 | - |
| 1369 | `excel{caseId}` | **下载Excel** | 点击弹出 modal，需确认 |
| 1405 | `word{caseId}` | **下载Word** | 同上 |
| 1441 | `pdf{caseId}` | **下载Pdf** | 同上 |
| 1477 | `print{caseId}` | **打印** | - |
| 1513 | `email{caseId}` | 邮件分享 | - |
| 1549 | - | 加入检索报告 | - |

**下载 Modal**：
- 标题：`下载Pdf`（或 `下载Word` / `下载Excel`）
- 选项：`文档类型：清洁版本 / 带目录版本 / 含链接`（仅 PDF）
- 按钮：`取消` / `下载`（点"下载"才真正触发 API）

**`caseId` 提取**：从 `a[id^=favorites]` 的 ID 中去掉 `favorites` 前缀（如 `favorites6246719150642227` → `6246719150642227`）。

---

## 6. 搜索结果 URL 参数含义

从搜索结果跳转时，URL 形如：
```
/judgment-documents/detail/MjA0MTUzMjY0NDg%3D
  ?searchId=414d083230784dcfb945e42824384f25    // 搜索会话 ID
  &index=1                                       // 结果序号（从 1 开始）
  &q=%E5%BB%BA%E8%AE%BE...                       // URL-encoded 搜索关键词
  &module=                                       // 通常空
```

- `searchId` 必须传给 downloadPath API，否则可能被拒绝
- `index` 仅用于显示
- `q` 是显示用，下载时可不传

---

## 7. 核心实现策略

### 7.1 推荐架构

**搜索和下载均走 API（无需浏览器）**，大幅提升速度：
1. 加载 `~/.claude/skills/wkinfo-cli/storage/wkinfo-cookies.json`
2. 构造 cookie 字符串 + 提取 `uid`、`identification`
3. 调用 `/csi/search` 拿结果（含 docId、searchId、title、caseNo、court 等元数据）
4. 遍历每条结果，调用三步下载 API 保存文件
5. 仅在需要浏览器交互（手动登录、cookie 失效、调试）时才用 Playwright

### 7.2 cookie 失效处理

- `userInfo` cookie 的 `expires` 是 2026-06-07 左右
- `connect.sid` 有效期更短
- 检测方式：调用 `downloadLimit` 看是否返回 `result: false` 或 401/403
- 失效时调用 `install_cookies.py --wait-login` 引导用户手动登录后写回新 cookie

### 7.3 下载限频

- 观察 `downloadLimit` 响应是否有限频信息
- 大批量下载时加 `time.sleep(0.5)` 防止触发限频

---

## 8. 调研产出文件清单

| 文件 | 用途 |
|------|------|
| `临时资源/截图/10-judgment-documents-list.png` | 搜索页初始截图 |
| `临时资源/截图/12-search-result.png` | 搜索结果页截图 |
| `临时资源/截图/18-judgment-detail.png` | 详情页截图 |
| `临时资源/截图/22-after-pdf-click.png` | 下载 Modal 截图 |
| `临时资源/截图/judgment-documents-text.txt` | 搜索页完整文本 |
| `脚本和代码/_research_*.py` | 调研脚本（保留供参考，可删除） |