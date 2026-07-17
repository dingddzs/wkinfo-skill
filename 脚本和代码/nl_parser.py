# -*- coding: utf-8 -*-
"""自然语言 -> 检索参数（结构化）

输入：用户自然语言请求（如"建设工程实际施工人向发包人请求付款的案例"）
输出：结构化的 SearchParams（案由、时间、法院、审级、文书类型、地域、模式等）

核心：
- 案由匹配基于《民事案件案由规定》(2025) 的 514 个第三级案由 + 470 个第四级案由
- 其他参数用规则 + 关键词词典解析
"""
import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

# 案由词典路径：优先用项目本地，否则用 skill 安装目录
_DEFAULT_PROJECT_PATH = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\处理后文件\民事案由_2025.json")
_DEFAULT_SKILL_PATH = Path.home() / ".claude" / "skills" / "威科案例检索和下载" / "民事案由_2025.json"
CASE_CAUSE_JSON = _DEFAULT_PROJECT_PATH if _DEFAULT_PROJECT_PATH.exists() else _DEFAULT_SKILL_PATH


# ============ 数据类 ============

@dataclass
class CaseCauseMatch:
    """案由匹配结果"""
    part: str                  # 第X部分
    part_name: str             # 例如 "人格权纠纷"
    category_code: str         # 一、二、三...
    category_name: str         # 例如 "人格权纠纷"
    cause_code: str            # 第三级数字编号，如 "120"
    cause_name: str            # 第三级案由，如 "建设工程合同纠纷"
    sub_cause_code: Optional[str] = None    # 第四级编号，如 "3"
    sub_cause_name: Optional[str] = None   # 第四级案由，如 "建设工程施工合同纠纷"
    match_score: float = 0.0              # 匹配分数 (0-1)
    matched_keywords: list = field(default_factory=list)


@dataclass
class SearchParams:
    """搜索参数"""
    query: str = ""                       # 原始查询
    mode: str = "list"                    # "few" (几个, PDF) / "list" (清单, Excel)
    target_count: int = 5                 # few 模式的目标数量
    max_count: int = 200                  # list 模式的最大数量

    # 案由
    case_cause: Optional[CaseCauseMatch] = None

    # 时间范围
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    date_filter_text: str = ""            # 原始时间表述（如 "近三年"）

    # 法院
    court_level: Optional[str] = None     # 最高人民法院/高级人民法院/中级人民法院/基层人民法院/专门法院
    court_name: Optional[str] = None      # 具体法院（如 "北京市第二中级人民法院"）
    court_text: str = ""                  # 原始法院表述

    # 审级
    trial_procedure: Optional[str] = None # 一审/二审/再审/破产/执行

    # 文书类型
    doc_type: Optional[str] = None        # 判决书/裁定书/决定书/调解书
    doc_type_text: str = ""

    # 地域
    region: Optional[str] = None          # 北京/上海/...

    # 案由顶级
    cause_of_action: Optional[str] = None  # 民事/刑事/行政/国家赔偿/执行

    # 行业
    industry: Optional[str] = None         # 金融业/建筑业/...

    # 参照级别
    reference_level: Optional[str] = None   # 公报案例/官方典型案例/...

    # 关键词补充
    extra_keywords: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        # case_cause 也转 dict
        return d


# ============ 案由词典加载 ============

class CaseCauseDict:
    """案由词典，支持快速模糊匹配"""

    def __init__(self, json_path: Path = CASE_CAUSE_JSON):
        self.json_path = json_path
        self.parts = []
        self._index = {}  # keyword -> [(part, category, cause, sub_cause, score_template), ...]
        self._load()

    def _load(self):
        if not self.json_path.exists():
            print(f"[!] 案由词典未找到: {self.json_path}")
            print(f"    请先运行 parse_case_causes.py")
            return

        with open(self.json_path, "r", encoding="utf-8") as f:
            self.parts = json.load(f)

        # 构建倒排索引：每个关键词 -> 所有可能的案由条目
        for part in self.parts:
            for cat in part["categories"]:
                for cause in cat["causes"]:
                    # 索引案由全名
                    self._add_to_index(cause["name"], part, cat, cause, None, score=1.0)
                    # 索引拆分别名
                    for alias in cause.get("aliases", []):
                        self._add_to_index(alias, part, cat, cause, None, score=0.9)
                    # 索引第四级
                    for sub in cause["sub_causes"]:
                        self._add_to_index(sub["name"], part, cat, cause, sub, score=1.0)

        # 加载用户自定义案由同义词（可选，文件不存在则优雅跳过）
        self._load_user_synonyms()

    def _load_user_synonyms(self):
        """从 references/extra-synonyms.json 加载用户累积的案由同义词

        支持两种格式：
          简单：{"实际施工人": "建设工程施工合同纠纷"}
                （值若为 sub_cause 名，自动索引到其父 cause）
          复杂：{"实际施工人": {"cause": "...", "sub_cause": "...", "score": 0.95}}
                （cause+sub_cause 双定位，精度更高）

        文件不存在或格式错误时优雅降级，不影响主流程。
        """
        user_path = Path(__file__).parent.parent / "references" / "extra-synonyms.json"
        if not user_path.exists():
            return
        try:
            with open(user_path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            # 先扁平化所有 cause/sub_cause 节点，便于查找
            all_causes = []    # [(part, cat, cause, None), ...]
            all_subs = []      # [(part, cat, cause, sub), ...]
            for part in self.parts:
                for cat in part["categories"]:
                    for cause in cat["causes"]:
                        all_causes.append((part, cat, cause, None))
                        for sub in cause.get("sub_causes", []):
                            all_subs.append((part, cat, cause, sub))

            for kw, target in user_data.items():
                if isinstance(target, str):
                    cname, sname, sc = target, None, 0.95
                else:
                    cname = target.get("cause", "")
                    sname = target.get("sub_cause")
                    sc = target.get("score", 0.95)
                if not cname:
                    continue
                injected = False
                if sname:
                    # 双定位：cause 名 + sub_cause 名
                    for part, cat, cause, sub in all_subs:
                        if cause["name"] == cname and sub["name"] == sname:
                            self._add_to_index(kw, part, cat, cause, sub, score=sc)
                            injected = True
                            break
                else:
                    # 单定位：先找 sub_cause（更具体），再找 cause
                    for part, cat, cause, sub in all_subs:
                        if sub["name"] == cname:
                            self._add_to_index(kw, part, cat, cause, sub, score=sc)
                            injected = True
                            break
                    if not injected:
                        for part, cat, cause, _ in all_causes:
                            if cause["name"] == cname:
                                self._add_to_index(kw, part, cat, cause, None, score=sc)
                                injected = True
                                break
                if not injected:
                    print(f"[!] extra-synonyms: 关键词 \"{kw}\" 指向 \"{cname}\" 未在案由词典中找到")
        except Exception as e:
            print(f"[!] extra-synonyms.json 加载失败（已跳过）: {e}")

    def _add_to_index(self, keyword, part, cat, cause, sub, score):
        if not keyword:
            return
        # 提取核心词（去掉"纠纷"后缀做匹配）
        for kw in [keyword, keyword.replace("纠纷", "")]:
            if not kw or len(kw) < 2:
                continue
            if kw not in self._index:
                self._index[kw] = []
            self._index[kw].append({
                "part": part, "category": cat, "cause": cause,
                "sub_cause": sub, "score_base": score
            })

    def search(self, text: str, top_k: int = 5) -> list:
        """从文本中匹配案由，返回 top_k 个候选

        匹配策略:
        - 在 text 中找每个索引关键词
        - 优先匹配第四级（最具体）
        - 累积分数，取最高
        """
        if not self.parts:
            return []

        text_lower = text
        candidates = {}  # (part_name, cat_name, cause_name, sub_name) -> score

        for keyword, entries in self._index.items():
            if keyword in text_lower:
                for entry in entries:
                    key = (
                        entry["part"]["part_name"],
                        entry["category"]["name"],
                        entry["cause"]["name"],
                        entry["sub_cause"]["name"] if entry["sub_cause"] else None
                    )
                    # 分数：基础分 + 关键词长度加成
                    score = entry["score_base"] + len(keyword) * 0.01
                    if key in candidates:
                        candidates[key] += score
                    else:
                        candidates[key] = score

        # 转 list 排序
        results = []
        for key, score in candidates.items():
            part_name, cat_name, cause_name, sub_name = key
            # 找到对应的 part
            for part in self.parts:
                if part["part_name"] == part_name:
                    for cat in part["categories"]:
                        if cat["name"] == cat_name:
                            for cause in cat["causes"]:
                                if cause["name"] == cause_name:
                                    # 构造匹配结果
                                    sub_cause = None
                                    sub_code = None
                                    if sub_name:
                                        for s in cause["sub_causes"]:
                                            if s["name"] == sub_name:
                                                sub_cause = s["name"]
                                                sub_code = s["code"]
                                                break
                                    results.append(CaseCauseMatch(
                                        part=part["part"],
                                        part_name=part["part_name"],
                                        category_code=cat["code"],
                                        category_name=cat["name"],
                                        cause_code=cause["code"],
                                        cause_name=cause["name"],
                                        sub_cause_code=sub_code,
                                        sub_cause_name=sub_cause,
                                        match_score=score,
                                        matched_keywords=[]
                                    ))
                                    break
                            break
                    break

        results.sort(key=lambda x: -x.match_score)
        return results[:top_k]


# ============ 参数解析器 ============

class ParamParser:
    """从自然语言查询中抽取结构化参数"""

    # 时间关键词
    # 中文数字 0-99 映射
    CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    YEAR_PATTERNS = [
        (r"近\s*([\d零一二三四五六七八九十两]+)\s*年", "near"),
        (r"最近\s*([\d零一二三四五六七八九十两]+)\s*年", "near"),
        (r"过去\s*([\d零一二三四五六七八九十两]+)\s*年", "near"),
        (r"(\d{4})\s*[-~到至]\s*(\d{4})", "range"),  # 2022-2025
        (r"(\d{4})\s*年\s*[-~到至]\s*(\d{4})\s*年?", "range_year"),  # 2022年-2025年
        (r"(\d{4})\s*年\s*以后", "from"),
        (r"(\d{4})\s*年\s*之前", "before"),
        (r"(\d{4})\s*年", "year_only"),
    ]

    # 法院级别
    COURT_LEVEL_MAP = {
        "最高法院": "最高人民法院",
        "最高法": "最高人民法院",
        "高院": "高级人民法院",
        "高级法院": "高级人民法院",
        "中院": "中级人民法院",
        "中级法院": "中级人民法院",
        "基层法院": "基层人民法院",
        "基层": "基层人民法院",
        "专门法院": "专门法院",
    }

    # 审级
    PROCEDURE_MAP = {
        "一审": "一审", "第一审": "一审",
        "二审": "二审", "上诉": "二审", "第二审": "二审",
        "再审": "再审", "申诉": "再审", "审判监督": "再审",
        "破产": "破产",
        "执行": "执行",
        "死刑复核": "死刑复核",
    }

    # 文书类型
    DOC_TYPE_MAP = {
        "判决": "判决书", "判决书": "判决书",
        "裁定": "裁定书", "裁定书": "裁定书",
        "决定": "决定书", "决定书": "决定书",
        "调解": "调解书", "调解书": "调解书",
        "通知书": "通知书",
    }

    # 地域（省/直辖市）
    REGIONS = [
        "北京", "上海", "天津", "重庆",
        "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西", "山东",
        "河南", "湖北", "湖南", "广东", "广西", "海南",
        "四川", "贵州", "云南", "西藏", "陕西", "甘肃",
        "青海", "宁夏", "新疆",
    ]

    # 模式识别
    FEW_PATTERNS = ["几个", "几份", "几个案例", "几个判决", "挑几个", "找几个", "搜索几个", "要几个"]
    LIST_PATTERNS = ["清单", "汇总", "全部", "所有", "整理", "列表", "一批", "下载"]

    def __init__(self):
        self.case_dict = CaseCauseDict()

    def parse(self, text: str) -> SearchParams:
        params = SearchParams(query=text)

        # 模式识别
        params.mode = self._detect_mode(text)
        if params.mode == "few":
            params.target_count = self._extract_count(text, default=5)
        else:
            params.max_count = self._extract_count(text, default=200)

        # 案由
        params.case_cause = self._extract_case_cause(text)

        # 时间
        params.year_from, params.year_to, params.date_filter_text = self._extract_time(text)

        # 法院
        params.court_level, params.court_name, params.court_text = self._extract_court(text)

        # 审级
        params.trial_procedure = self._extract_procedure(text)

        # 文书类型
        params.doc_type, params.doc_type_text = self._extract_doc_type(text)

        # 地域
        params.region = self._extract_region(text)

        # 案由顶级
        params.cause_of_action = self._extract_cause_of_action(text)

        # 行业
        params.industry = self._extract_industry(text)

        # 参照级别
        params.reference_level = self._extract_reference_level(text)

        # 额外关键词
        params.extra_keywords = self._extract_extra_keywords(text, params)

        return params

    def _detect_mode(self, text: str) -> str:
        for p in self.FEW_PATTERNS:
            if p in text:
                return "few"
        for p in self.LIST_PATTERNS:
            if p in text:
                return "list"
        # 默认：如果有关键词"几个/几份"也是 few，否则 list
        if any(w in text for w in ["挑", "要"]):
            return "few"
        return "list"

    def _extract_count(self, text: str, default: int) -> int:
        m = re.search(r"(\d+)\s*(?:个|份|条|起)", text)
        if m:
            return int(m.group(1))
        return default

    def _extract_case_cause(self, text: str) -> Optional[CaseCauseMatch]:
        results = self.case_dict.search(text, top_k=1)
        return results[0] if results else None

    def _extract_time(self, text: str) -> tuple:
        from datetime import datetime
        for pattern, kind in self.YEAR_PATTERNS:
            m = re.search(pattern, text)
            if m:
                # 中文数字 → 阿拉伯数字
                def to_int(s: str) -> int:
                    if s.isdigit():
                        return int(s)
                    # 简单中文数字转换（支持 0-19）
                    if s in self.CN_NUM:
                        return self.CN_NUM[s]
                    if s.startswith("十"):
                        rest = s[1:]
                        if not rest:
                            return 10
                        if rest in self.CN_NUM:
                            return 10 + self.CN_NUM[rest]
                    if "十" in s:
                        idx = s.index("十")
                        left = self.CN_NUM.get(s[:idx], 1)
                        right = self.CN_NUM.get(s[idx+1:], 0)
                        return left * 10 + right
                    return 0
                if kind == "near":
                    n = to_int(m.group(1))
                    now = datetime.now().year
                    return now - n, now, m.group(0)
                elif kind == "range":
                    return int(m.group(1)), int(m.group(2)), m.group(0)
                elif kind == "from":
                    return int(m.group(1)), None, m.group(0)
                elif kind == "before":
                    return None, int(m.group(1)), m.group(0)
                elif kind == "year_only":
                    y = int(m.group(1))
                    return y, y, m.group(0)
        return None, None, ""

    def _extract_court(self, text: str) -> tuple:
        """同时提取法院级别（最高/高院/中院/基层）和具体省/直辖市

        返回 (court_level, court_name, court_text)
        - court_level: 级别（"最高人民法院"/"高级人民法院"/"中级人民法院"/"基层人民法院"/"专门法院"）
        - court_name: 省/直辖市名（"上海市"/"北京市"等）
        - court_text: 原文中匹配到的法院描述（用于回显）
        """
        court_level = None
        court_name = None
        court_text = ""

        # 1. 提取法院级别
        # 优先匹配最长的（"最高人民法院" 优先于 "最高法"）
        for key in sorted(self.COURT_LEVEL_MAP.keys(), key=len, reverse=True):
            if key in text:
                court_level = self.COURT_LEVEL_MAP[key]
                court_text = key
                break

        # 2. 提取具体省/直辖市（与级别独立，可同时存在）
        try:
            from wkinfo_api import COURT_MAP
            # 优先匹配最长的（"新疆维吾尔自治区" 优先于 "新疆"）
            for province in sorted(COURT_MAP.keys(), key=len, reverse=True):
                if province in text:
                    court_name = province
                    if not court_text:
                        court_text = province
                    break
        except ImportError:
            pass

        # 3. 短简称 fallback（如果 COURT_MAP 没匹配上）
        if not court_name:
            SHORT_NAMES = {
                "上海": "上海市", "北京": "北京市", "天津": "天津市", "重庆": "重庆市",
                "广东": "广东省", "江苏": "江苏省", "浙江": "浙江省", "山东": "山东省",
                "河南": "河南省", "湖北": "湖北省", "湖南": "湖南省", "河北": "河北省",
                "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省", "黑龙江": "黑龙江省",
                "安徽": "安徽省", "福建": "福建省", "江西": "江西省", "陕西": "陕西省",
                "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "海南": "海南省",
                "甘肃": "甘肃省", "青海": "青海省", "宁夏": "宁夏回族自治区",
                "新疆": "新疆维吾尔自治区", "西藏": "西藏自治区",
                "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区",
            }
            for short, full in SHORT_NAMES.items():
                if short in text:
                    court_name = full
                    if not court_text:
                        court_text = full
                    break

        return court_level, court_name, court_text

    def _extract_procedure(self, text: str) -> Optional[str]:
        for key, val in self.PROCEDURE_MAP.items():
            if key in text:
                return val
        return None

    def _extract_doc_type(self, text: str) -> tuple:
        for key, val in self.DOC_TYPE_MAP.items():
            if key in text:
                return val, key
        return None, ""

    def _extract_region(self, text: str) -> Optional[str]:
        for r in self.REGIONS:
            if r in text:
                return r
        return None

    def _extract_extra_keywords(self, text: str, params: SearchParams) -> list:
        """抽取案由外的补充关键词（用于构建 queryString）"""
        keywords = []
        if params.case_cause:
            cc = params.case_cause
            if cc.sub_cause_name:
                keywords.append(cc.sub_cause_name)
            else:
                keywords.append(cc.cause_name)
        return keywords

    def _extract_cause_of_action(self, text: str) -> Optional[str]:
        """抽取案由顶级（民事/刑事/行政/国家赔偿/执行）"""
        # 按特定模式匹配
        if "民事" in text and "刑事" not in text:
            return "民事"
        if "刑事" in text:
            return "刑事"
        if "行政" in text:
            return "行政"
        if "国家赔偿" in text:
            return "国家赔偿"
        if "执行" in text:
            return "执行"
        return None

    def _extract_industry(self, text: str) -> Optional[str]:
        """抽取行业"""
        INDUSTRY_KEYWORDS = {
            "金融": "金融业",
            "银行": "金融业",
            "保险": "金融业",
            "证券": "金融业",
            "建筑": "建筑业",
            "房地产": "房地产业",
            "地产": "房地产业",
            "制造": "制造业",
            "工厂": "制造业",
            "采矿": "采矿业",
            "电力": "电力、热力、燃气及水生产和供应业",
            "信息传输": "信息传输、软件和信息技术服务业",
            "互联网": "信息传输、软件和信息技术服务业",
            "批发": "批发和零售业",
            "零售": "批发和零售业",
            "交通运输": "交通运输、仓储和邮政业",
            "物流": "交通运输、仓储和邮政业",
            "教育": "教育",
            "学校": "教育",
            "医疗": "卫生和社会工作",
            "卫生": "卫生和社会工作",
            "文化": "文化、体育和娱乐业",
            "体育": "文化、体育和娱乐业",
            "娱乐": "文化、体育和娱乐业",
            "农林牧渔": "农、林、牧、渔业",
            "农业": "农、林、牧、渔业",
        }
        for kw, industry in INDUSTRY_KEYWORDS.items():
            if kw in text:
                return industry
        return None

    def _extract_reference_level(self, text: str) -> Optional[str]:
        """抽取参照级别"""
        if "公报案例" in text or "公报" in text:
            return "公报案例"
        if "最高法指导性案例" in text or "指导性案例" in text:
            return "最高检指导性案例"  # 注：01 未验证，先返回 02
        if "最高检指导性案例" in text:
            return "最高检指导性案例"
        if "入库案例" in text:
            return None  # 03 未验证
        if "官方典型案例" in text or "典型案例" in text:
            return None  # 05 未验证
        if "上海金融法院" in text:
            return "上海金融法院精选案例"
        if "法官评案" in text:
            return None  # 07 未验证
        if "律师评案" in text:
            return "律师评案"
        if "威科推荐" in text:
            return "威科推荐案例"
        return None


# ============ CLI ============

def main():
    import sys
    parser = ParamParser()
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "建设工程实际施工人向发包人请求付款的案例，最高法院近三年判决"
    print(f'原始查询: {query}\n')

    params = parser.parse(query)
    print(json.dumps(params.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()