# -*- coding: utf-8 -*-
"""威科先行 API 客户端（多库支持）

支持的库：
- case: 裁判文书（/judgment-documents/list）
- legislation: 法律法规（/legislation/list）
- penalty: 行政处罚（/administrative-punishment/list）
- commentary: 实务指南（/commentary/list）
- focus: 专题聚焦（/focus/list）

每个库的差异通过 LIBRARIES 注册表配置：
- indexId
- 入口 URL
- 字段名 MAP（field → code）
- 共享搜索/计数/下载 API（只是 indexId 不同）

新库接入方法：往 LIBRARIES 字典加一项 + 配套 MAP，零代码改动。
"""
import json
import re
import urllib.parse
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

WKINFO_DOMAIN = "https://law.wkinfo.com.cn"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"

DEFAULT_COOKIE_FILE = Path.home() / ".claude/skills/wkinfo-cli/storage/wkinfo-cookies.json"


# ============ 库注册表 ============

@dataclass
class Library:
    """单个库的配置"""
    key: str
    name: str
    index_id: str
    list_url: str
    field_maps: dict


# 各库 MAP
CASE_MAPS = {
    "courtLevel": {"最高人民法院": 1, "高级人民法院": 2, "中级人民法院": 3, "基层人民法院": 4, "专门法院": 5},
    "typeOfDecisionCode": {"判决书": "001", "裁定书": "002", "决定书": "003", "调解书": "004", "通知书": "006", "令": "007", "案例评析": "008"},
    "instance": {"一审": "001", "二审": "002", "再审": "003", "破产": "004", "执行": "005", "死刑复核": "006", "公示催告": "007", "督促": "008"},
    "court": {
        "最高人民法院": "001000000最高人民法院", "北京市": "003000000北京市",
        "天津市": "028000000天津市", "上海市": "024000000上海市", "重庆市": "004000000重庆市",
        "河北省": "011000000河北省", "山西省": "025000000山西省", "内蒙古自治区": "016000000内蒙古自治区",
        "辽宁省": "020000000辽宁省", "吉林省": "019000000吉林省", "黑龙江省": "012000000黑龙江省",
        "江苏省": "017000000江苏省", "浙江省": "032000000浙江省", "安徽省": "002000000安徽省",
        "福建省": "005000000福建省", "江西省": "018000000江西省", "山东省": "023000000山东省",
        "河南省": "013000000河南省", "湖北省": "014000000湖北省", "湖南省": "015000000湖南省",
        "广东省": "007000000广东省", "广西壮族自治区": "008000000广西壮族自治区", "海南省": "010000000海南省",
        "四川省": "027000000四川省", "贵州省": "009000000贵州省", "云南省": "031000000云南省",
        "西藏自治区": "029000000西藏自治区", "陕西省": "026000000陕西省", "甘肃省": "006000000甘肃省",
        "青海省": "022000000青海省", "宁夏回族自治区": "021000000宁夏回族自治区",
        "新疆维吾尔自治区": "030000000新疆维吾尔自治区", "新疆生产建设兵团": "033000000新疆生产建设兵团",
        "铁路法院": "090000000铁路法院", "海事法院": "091000000海事法院", "军事法院": "092000000军事法院",
    },
    "causeOfAction": {
        "民事": "01000000000000民事", "刑事": "02000000000000刑事",
        "行政": "03000000000000行政", "国家赔偿": "04000000000000国家赔偿", "执行": "05000000000000执行",
    },
    "industryCode": {
        "农、林、牧、渔业": "A", "采矿业": "B", "制造业": "C",
        "电力、热力、燃气及水生产和供应业": "D", "建筑业": "E",
        "批发和零售业": "F", "交通运输、仓储和邮政业": "G",
        "住宿和餐饮业": "H", "信息传输、软件和信息技术服务业": "I",
        "金融业": "J", "房地产业": "K", "租赁和商务服务业": "L",
        "科学研究和技术服务业": "M", "水利、环境和公共设施管理业": "N",
        "居民服务、修理和其他服务业": "O", "教育": "P",
        "卫生和社会工作": "Q", "文化、体育和娱乐业": "R",
    },
    "referenceLevelNew": {
        "最高检指导性案例": "02", "公报案例": "04", "上海金融法院精选案例": "06",
        "律师评案": "08", "威科推荐案例": "09", "其他": "10",
    },
}

LEGISLATION_MAPS = {
    "newLevelEffect": {
        "法律": "101", "行政法规": "105", "司法解释": "110",
        "监察法规": "115", "部门规章": "120", "政党及组织文件": "122",
        "行业规范": "124", "地方法规": "125", "地方司法文件": "130",
        "军事法规": "140", "国际条约": "150", "国家标准": "151",
    },
    "jurisdiction": {
        "全国": "01010000000", "北京市": "02030000000", "上海市": "03270000000",
    },
    "validityStatus": {
        "现行有效": "001", "失效/废止": "002", "已被修订": "003",
        "部分失效/废止": "004", "尚未生效": "005", "草案/征求意见稿": "006",
    },
}

PENALTY_MAPS = {
    "industryCode": CASE_MAPS["industryCode"],
    "jurisdiction": LEGISLATION_MAPS["jurisdiction"],
    "topicClassification": {
        "市场监管": "D010", "财税": "D020", "医疗卫生": "D030",
        "金融": "D040", "知识产权": "D050", "网络安全": "D055",
        "环保": "D060", "安全监管": "D070", "土地城建": "D080",
        "司法": "D090", "劳动人事": "D100", "海关、海事": "D110",
        "文化传媒": "D120", "交通运输": "D130", "工信": "D140",
    },
}

# 实务指南库
COMMENTARY_MAPS = {
    "lang": {"英文": "EN", "中文": "CN"},
    "lastReviewYear": {  # Lucene 范围
        # 年份在 API 中用 range 表达，MAP 仅供提示
    },
    "groupLevel": {  # 律所/发布机构
        # 完整编码需进一步调研
    },
}

# 专题聚焦库
FOCUS_MAPS = {
    "newTopicClassification": {
        # 专题类型（部分）
        "公司治理": "B255", "劳动法": "BXXX", "金融与资管": "BXXX",
        "新规与热点解读系列": "BXXX", "双周动态精华系列": "BXXX",
    },
    "groupLevel": {},  # 律所
    "promulgatingYear": {},  # 年份
}


# ============ 库注册表 ============

LIBRARIES = {
    "case": Library(
        key="case", name="裁判文书",
        index_id="law.case", list_url="/judgment-documents/list",
        field_maps=CASE_MAPS,
    ),
    "legislation": Library(
        key="legislation", name="法律法规",
        index_id="law.legislation", list_url="/legislation/list",
        field_maps=LEGISLATION_MAPS,
    ),
    "penalty": Library(
        key="penalty", name="行政处罚",
        index_id="law.administrativeSupervision", list_url="/administrative-punishment/list",
        field_maps=PENALTY_MAPS,
    ),
    "commentary": Library(
        key="commentary", name="实务指南",
        index_id="law.commentaryB", list_url="/commentary/list",
        field_maps=COMMENTARY_MAPS,
    ),
    "focus": Library(
        key="focus", name="专题聚焦",
        index_id="law.specialTopic", list_url="/focus/list",
        field_maps=FOCUS_MAPS,
    ),
}


# ============ 客户端 ============

@dataclass
class WkinfoClient:
    """威科 API 客户端（多库）"""
    cookie_file: Path = DEFAULT_COOKIE_FILE
    _session: Optional[requests.Session] = None
    _cookie_str: str = ""
    _uid: str = ""
    _identification: str = ""

    def __post_init__(self):
        self._session = requests.Session()
        self._load_cookies()

    def _load_cookies(self):
        if not self.cookie_file.exists():
            raise FileNotFoundError(f"Cookie 文件不存在: {self.cookie_file}")
        with open(self.cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        self._cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        for c in cookies:
            if c["name"] == "userInfo":
                decoded = urllib.parse.unquote(c["value"])
                m = re.search(r'"id"\s*:\s*"(\d+)"', decoded)
                if m:
                    self._uid = m.group(1)
            elif c["name"] == "identification":
                self._identification = urllib.parse.unquote(c["value"]).strip('"')

    def _headers(self) -> dict:
        return {
            "cookie": self._cookie_str, "uid": self._uid, "identification": self._identification,
            "module": "", "user-agent": USER_AGENT,
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "referer": f"{WKINFO_DOMAIN}/judgment-documents/list",
        }

    def build_search_body(
        self, query_string="*:*", filter_queries=None, filter_dates=None,
        tree_node_ids=None, page_offset=0, page_limit=100, library="case",
    ) -> dict:
        library_obj = LIBRARIES.get(library)
        if library_obj is None:
            raise ValueError(f"未知 library: {library}")
        if filter_queries is None: filter_queries = []
        if filter_dates is None: filter_dates = []
        if tree_node_ids is None: tree_node_ids = []
        if query_string and not query_string.startswith("simple:") and query_string != "*:*":
            query_string = f"simple:(({query_string}))"
        # 各库的日期/时间排序字段名不同：
        # case 用 judgmentDate
        # legislation 用 promulgatingDate
        # penalty 用 orderPriority / score / superviseDate
        # commentary 用 lastReviewDate
        # focus 用 promulgatingDate
        if library == "legislation":
            sort_list = [
                {"sortKey": "score", "sortDirection": "DESC"},
                {"sortKey": "promulgatingDate", "sortDirection": "DESC"},
            ]
        elif library == "penalty":
            sort_list = [
                {"sortKey": "orderPriority", "sortDirection": "ASC"},
                {"sortKey": "score", "sortDirection": "DESC"},
                {"sortKey": "superviseDate", "sortDirection": "DESC"},
            ]
        elif library == "commentary":
            sort_list = [
                {"sortKey": "score", "sortDirection": "DESC"},
                {"sortKey": "lastReviewDate", "sortDirection": "DESC"},
            ]
        elif library == "focus":
            sort_list = [
                {"sortKey": "score", "sortDirection": "DESC"},
                {"sortKey": "promulgatingDate", "sortDirection": "DESC"},
            ]
        else:  # case
            sort_list = [
                {"sortKey": "score", "sortDirection": "DESC"},
                {"sortKey": "judgmentDate", "sortDirection": "DESC"},
            ]
        return {
            "indexId": library_obj.index_id,
            "query": {"queryString": query_string, "filterDates": filter_dates, "filterQueries": filter_queries},
            "searchScope": {"treeNodeIds": tree_node_ids}, "relatedIndexQueries": [],
            "sortOrderList": sort_list,
            "pageInfo": {"limit": page_limit, "offset": page_offset},
            "chargingInfo": {"useBalance": True},
            "otherOptions": {
                "requireLanguage": "cn", "relatedIndexEnabled": True, "groupEnabled": False,
                "smartEnabled": True, "buy": False, "summaryLengthLimit": 100,
                "synonymEnabled": True, "advanced": False, "isHideBigLib": 0,
                "relatedIndexFetchRows": 5, "proximateCourtID": "", "module": "",
                "correctEnabled": True, "mappingEnabled": True,
                "webSearchEnabled": False, "defaultSearch": False, "rankKeyword": "",
            },
        }

    def search(self, query_string="*:*", filter_queries=None, filter_dates=None,
               tree_node_ids=None, page_offset=0, page_limit=100, library="case") -> dict:
        body = self.build_search_body(query_string, filter_queries, filter_dates,
                                     tree_node_ids, page_offset, page_limit, library)
        headers = {**self._headers(), "content-type": "application/json;charset=UTF-8"}
        r = self._session.post(f"{WKINFO_DOMAIN}/csi/search", headers=headers, json=body, timeout=30)
        r.raise_for_status()
        return r.json()

    def doc_count(self, query_string="*:*", filter_queries=None, filter_dates=None,
                  tree_node_ids=None, library="case") -> int:
        body = self.build_search_body(query_string, filter_queries, filter_dates,
                                     tree_node_ids, 0, 1, library)
        headers = {**self._headers(), "content-type": "application/json;charset=UTF-8"}
        r = self._session.post(f"{WKINFO_DOMAIN}/csi/search", headers=headers, json=body, timeout=30)
        if r.ok:
            return int(r.json().get("searchMetadata", {}).get("docCount", 0))
        return 0

    def download_file(self, doc_id, file_type="pdf", filename=None, search_id="",
                      contain_link=True, output_path=None, cell_list=None, library="case") -> dict:
        library_obj = LIBRARIES.get(library)
        if library_obj is None:
            return {"success": False, "error": f"未知 library: {library}"}
        API_FILE_TYPE = {"pdf": "pdf", "docx": "docx", "xls": "excel", "excel": "excel"}
        api_type = API_FILE_TYPE.get(file_type.lower(), file_type)
        if api_type not in ("pdf", "docx", "excel"):
            return {"success": False, "error": f"不支持的文件类型: {file_type}"}
        if not filename:
            filename = f"doc_{doc_id}.{file_type}"
        headers = {**self._headers(), "content-type": "application/json;charset=UTF-8"}
        cell_list_value = cell_list if cell_list is not None else (
            DEFAULT_CELL_LIST if api_type in ("docx", "excel") else None
        )
        try:
            r1 = self._session.post(f"{WKINFO_DOMAIN}/csi/document/downloadLimit", headers=headers,
                json={"indexId": library_obj.index_id, "fileType": api_type, "docId": doc_id,
                      "showType": 0, "module": "", "cellList": cell_list_value}, timeout=30)
            r1.raise_for_status()
            if not r1.json().get("result", False):
                return {"success": False, "error": f"downloadLimit 拒绝: {r1.json()}"}
        except Exception as e:
            return {"success": False, "error": f"downloadLimit 失败: {e}"}
        try:
            body = {"indexId": library_obj.index_id, "fileType": api_type, "docId": doc_id,
                    "showType": 0, "filename": filename, "module": "", "searchId": search_id,
                    "containLink": contain_link}
            if cell_list_value is not None:
                body["cellList"] = cell_list_value
            r2 = self._session.post(f"{WKINFO_DOMAIN}/csi/document/downloadPath",
                headers=headers, json=body, timeout=30)
            r2.raise_for_status()
            key = r2.json()["data"]["key"]
            actual_filename = r2.json()["data"]["filename"]
        except Exception as e:
            return {"success": False, "error": f"downloadPath 失败: {e}"}
        try:
            r3 = self._session.get(f"{WKINFO_DOMAIN}/api/download?key={key}",
                headers=self._headers(), timeout=60, stream=True)
            r3.raise_for_status()
            cd = r3.headers.get("content-disposition", "")
            m = re.search(r"filename\*=UTF-8''([^;]+)", cd)
            if m:
                actual_filename = urllib.parse.unquote(m.group(1))
            if output_path is None:
                output_path = Path.cwd() / actual_filename
            elif output_path.is_dir():
                output_path = output_path / actual_filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in r3.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            return {"success": True, "path": str(output_path), "filename": actual_filename,
                    "size": output_path.stat().st_size}
        except Exception as e:
            return {"success": False, "error": f"/api/download 失败: {e}"}


# case 库用 Excel/Word 下载的字段列表
DEFAULT_CELL_LIST = (
    "title,documentnumber,court,territory,typeofcase,causeofaction,"
    "judgmentdatestr,instance,typeofdecision,subjectFee,"
    "courtAcceptanceFee,judgmentReason,judgmentResult,judges,"
    "plaintiff,defendant,thirdParty,trialProcess,"
    "plaintiffattorney,defendantattorney,thirdpartyattorney,"
    "plaintiffagent,defendantagent,thirdpartyagent"
)


# ============ 向后兼容：旧版 MAP 名称 ============
# 旧版 wkinfo_api.py 导出独立的 MAP 名称，新版用 CASE_MAPS 嵌套结构
# 这里保留旧名称以兼容 search_cases.py 等旧代码
COURT_LEVEL_MAP = CASE_MAPS["courtLevel"]
DOC_TYPE_MAP = CASE_MAPS["typeOfDecisionCode"]
INSTANCE_MAP = CASE_MAPS["instance"]
COURT_MAP = CASE_MAPS["court"]
CAUSE_OF_ACTION_MAP = CASE_MAPS["causeOfAction"]
INDUSTRY_MAP = CASE_MAPS["industryCode"]
REFERENCE_LEVEL_MAP = CASE_MAPS["referenceLevelNew"]


def parse_search_results(resp_json, library="case"):
    return resp_json.get("documentList", []) or []


def build_filter_queries(library="case", filters=None):
    if filters is None:
        return []
    library_obj = LIBRARIES.get(library)
    if library_obj is None:
        return []
    fqs = []
    for field, value in filters.items():
        if value is None or value == "":
            continue
        field_map = library_obj.field_maps.get(field, {})
        if isinstance(field_map, dict) and value in field_map:
            code = field_map[value]
            fqs.append(f"+{field}:(({code}))")
        else:
            fqs.append(f"+{field}:(({value}))")
    return fqs


def build_judgment_year_filter(year_from=None, year_to=None):
    if year_from and year_to:
        return f"+judgmentYear:([{year_from} TO {year_to + 1}])"
    if year_from:
        return f"+judgmentYear:([{year_from} TO *])"
    if year_to:
        return f"+judgmentYear:([* TO {year_to + 1}])"
    return None
