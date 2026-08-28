"""
批量导入宏观经济指标 CSV 文件

用法：
  python scripts/import_macro_data.py            # 直接导入
  python scripts/import_macro_data.py --preview  # 仅预览并检查代码唯一性

时间窗口：202407 ~ 202606（最近24个月）
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.common.database import DatabaseConfig, execute_update, init_database
from backend.config.config import MYSQL_CONFIG

TIME_WINDOW_START = "202407"
TIME_WINDOW_END = "202606"

MONTH_HEADER_RE = re.compile(r"(\d{4})年(\d{1,2})月")


def month_header_to_datestr(header: str) -> str:
    m = MONTH_HEADER_RE.match(header.strip())
    if not m:
        raise ValueError(f"无法解析月份列名: {header!r}")
    return f"{m[1]}{int(m[2]):02d}"


def in_time_window(datestr: str) -> bool:
    return TIME_WINDOW_START <= datestr <= TIME_WINDOW_END


# ============================================================
# 代码生成：两级匹配 + 后缀
# 第1级：大类确定前缀
# 第2级：子类确定细分
# 第3级：后缀区分指标类型（YOY/YTD/MOM/CUM/空）
# ============================================================

# 大类模式
BASE_PATTERNS: list[tuple[str, str]] = [
    # ── PMI ──
    ("制造业采购经理指数", "PMI"),
    ("非制造业采购经理指数", "NONMFG_PMI"),
    ("综合PMI产出指数", "PMI_COMP"),
    # ── CPI / PPI ──
    ("居民消费价格分类指数", "CPI"),
    ("工业生产者出厂价格指数", "PPI_EX"),
    ("工业生产者购进价格指数", "PPI_IM"),
    ("工业企业", "IND"),
    # 缩略形式
    ("购进价格指数", "PPI_IM"),
    ("出厂价格指数", "PPI_EX"),
    ("居民消费价格", "CPI"),
    ("商品零售价格指数", "RPI"),
    ("居民消费价格指数", "CPI"),
    # ── 工业 ──
    ("工业增加值增长速度", "IND_VA"),
    ("电力、热力、燃气及水", "UTILITY"),
    ("工业出口交货值", "IND_EXPORT"),
    ("房地产开发投资", "RE_DEV"),
    ("其他采矿业", "MINING"),
    ("工业增加值", "IND_VA"),
    ("工业企业", "IND"),
    ("采矿业", "MINING"),
    ("制造业", "MANUFACTURING"),
    ("电力燃气水", "UTILITY"),
    # ── 贸易 ──
    ("进出口差额", "TRADE_BAL"),
    ("口岸进出口总额", "PORT_TRADE"),
    ("进出口额", "TRADE"),
    ("进出口", "TRADE"),
    ("出口额", "EXPORT"),
    ("进口额", "IMPORT"),
    # ── 财政 ──
    ("国家财政支出", "FISCAL_EXP"),
    ("国家财政收入", "FISCAL_REV"),
    # ── 消费 ──
    ("社会消费品零售总额", "RETAIL"),
    ("限额以上单位商品零售额", "RETAIL_LIMIT"),
    # ── 房地产 ──
    ("房地产投资", "RE_INV"),
    ("商品住宅销售额", "HOME_SALES"),
    ("商品住宅销售面积", "HOME_AREA"),
    # ── 投资/就业 ──
    ("固定资产投资", "FAI"),
    ("服务业生产指数", "SVC_PROD"),
    ("城镇调查失业率", "UNEMPLOY"),
    # ── 货币 ──
    ("货币和准货币", "M2"),
    ("流通中现金", "M0"),
    ("货币", "M1"),
    # ── 实体经济 ──
    ("发电量", "POWER_GEN"),
    ("货物运输量", "FREIGHT"),
    ("外商直接投资", "FDI"),
]

# 子类模式（仅从剩余文本中匹配）
SUB_PATTERNS: list[tuple[str, str]] = [
    # 按长度降序（长词优先匹配）
    ("电力、热力生产和供应业", "POWER"),
    ("文教、工美、体育和娱乐用品制造业", "CULTURE"),
    ("铁路、船舶、航空航天和其他运输设备制造业", "TRANS_EQP"),
    ("铁路船舶航空航天及运输设备制造业", "TRANS_EQP"),
    ("计算机、通信和其他电子设备制造业", "IT"),
    ("计算机通信及电子设备制造业", "IT"),
    ("皮革、毛皮、羽毛及其制品和制鞋业", "LEATHER"),
    ("石油、煤炭及其他燃料加工业", "PETRO"),
    ("石油加工、炼焦和核燃料加工业", "PETRO"),
    ("化学原料和化学制品制造业", "CHEM_MFG"),
    ("化学原料及化学制品", "CHEM_MFG"),
    ("木材加工和木、竹、藤、棕、草制品业", "WOOD_PROC"),
    ("木材加工及木竹藤棕草制品业", "WOOD_PROC"),
    ("有色金属冶炼和压延加工业", "NF_SMELT"),
    ("有色金属冶炼及压延加工业", "NF_SMELT"),
    ("黑色金属冶炼和压延加工业", "STEEL"),
    ("黑色金属冶炼及压延加工业", "STEEL"),
    ("酒、饮料和精制茶制造业", "DRINK"),
    ("电气机械和器材制造业", "ELEC_EQP"),
    ("电气机械及器材制造业", "ELEC_EQP"),
    ("印刷和记录媒介复制业", "PRINT"),
    ("印刷及记录媒介复制业", "PRINT"),
    ("造纸和纸制品业", "PAPER"),
    ("造纸及纸制品业", "PAPER"),
    ("纺织服装、服饰业", "GARMENT"),
    ("纺织服装及服饰业", "GARMENT"),
    ("外商及港澳台投资企业", "FOREIGN"),
    ("外商和港澳台投资企业", "FOREIGN"),
    ("商业营业用房投资", "SHOP"),
    ("建筑材料及非金属矿类", "BUILD"),
    ("建筑材料及非金属矿", "BUILD"),
    ("开采专业及辅助性活动", "MINE_AUX"),
    ("金属制品、机械和设备修理业", "REPAIR"),
    ("房地产投资", "RE_INV"),
    ("国有控股企业", "STATE"),
    ("非金属矿物制品业", "NONMETAL"),
    ("石油和天然气开采业", "OILGAS"),
    ("废弃资源综合利用业", "RECYCLE"),
    ("黑色金属矿采选业", "FE_MINE"),
    ("有色金属矿采选业", "NF_MINE"),
    ("农副食品加工业", "AGRI_PROC"),
    ("燃气生产和供应业", "GAS"),
    ("水的生产和供应业", "WATER"),
    ("其他采矿业", "OTH_MINE"),
    ("非金属矿采选业", "NM_MINE"),
    ("教育文化和娱乐及用品", "EDU"),
    ("教育文化娱乐", "EDU"),
    ("化学纤维制造业", "CHEM_FIB"),
    ("通用设备制造业", "GEN_EQP"),
    ("专用设备制造业", "SPEC_EQP"),
    ("橡胶和塑料制品业", "RUBBER"),
    ("仪器仪表制造业", "METER"),
    ("煤炭开采和洗选业", "COAL"),
    ("房地产投资", "RE_INV"),
    ("家具制造业", "FURNITURE"),
    ("医药制造业", "PHARMA"),
    ("食品制造业", "FOOD_MFG"),
    ("汽车制造业", "AUTO"),
    ("金属制品业", "METAL"),
    ("纺织业", "TEXTILE"),
    ("烟草制品业", "TOBACCO"),
    # 三大门类及通用行业子类
    ("电力、热力、燃气及水的生产和供应业", "UTILITY"),
    ("电力燃气水供应", "UTILITY"),
    ("制造业", "MANUFACTURING"),
    ("采矿业", "MINING"),
    # CPI/PPI 子类
    ("食品烟酒及用品", "FOOD"),
    ("交通通信及用品", "TRANS"),
    ("生活用品及服务", "HOME"),
    ("衣着及用品", "CLOTHES"),
    ("居住及用品", "HOUSE"),
    ("医疗保健及用品", "MED"),
    ("其他用品和服务", "OTH"),
    ("其他用品及服务", "OTH"),
    ("非食品及能源", "CORE"),
    ("扣除食品和能源", "CORE"),
    ("服务项目", "SERVICE"),
    ("其他制造业", "OTH_MFG"),
    ("食品烟酒", "FOOD"),
    ("交通和通信", "TRANS"),
    ("非食品", "NONFOOD"),
    ("消费品", "GOODS"),
    # PPI
    ("燃料动力类", "FUEL"),
    ("燃料、动力类", "FUEL"),
    ("黑色金属材料类", "FERROUS"),
    ("黑色金属材料", "FERROUS"),
    ("有色金属材料和电线类", "NF_METAL"),
    ("有色金属材料及电线", "NF_METAL"),
    ("化工原料类", "CHEM"),
    ("木材及纸浆类", "WOOD"),
    ("其它工业原材料及半成品类", "OTHER"),
    ("农副产品类", "AGRI"),
    ("纺织原料类", "TEX_RAW"),
    ("一般日用品类", "DAILY"),
    ("耐用消费品类", "DUR"),
    ("生产资料", "PROD"),
    ("生活资料", "CONS"),
    ("采掘业", "MINE"),
    ("原料业", "RAW"),
    ("加工业", "PROC"),
    ("食品类", "FOOD"),
    ("衣着类", "CLOTH"),
    # 企业类型
    ("私营企业", "PRIVATE"),
    ("股份制企业", "STOCK"),
    # 财政
    ("债务还本", "DEBT_PAY"),
    ("债务付息", "DEBT_INT"),
    # 房地产
    ("住宅投资", "HOME"),
    ("办公楼投资", "OFFICE"),
    ("本年资金来源小计", "FUNDS"),
    ("国内贷款", "LOAN"),
    ("利用外资", "FORCAP"),
    ("自筹资金", "SELF"),
]

# 按长度降序排列
BASE_PATTERNS.sort(key=lambda x: -len(x[0]))
SUB_PATTERNS.sort(key=lambda x: -len(x[0]))

# 后缀模式：决定指标类型
SUFFIX_PATTERNS = [
    (r"累计增长\s*\(%\)", "_YOY_CUM"),
    (r"同比增长\s*\(%\)", "_YOY"),
    (r"累计增长", "_YOY_CUM"),
    (r"同比增长", "_YOY"),
    (r"累计值", "_CUM"),
    (r"当月值", ""),
    (r"上年同月\s*=\s*100", "_YOY"),
    (r"上年同期\s*=\s*100", "_YTD"),
    (r"上月\s*=\s*100", "_MOM"),
]


def generate_code(name: str) -> str:
    """根据中文指标名自动生成唯一的英文代码"""
    clean = name.replace("（", "(").replace("）", ")")
    clean = re.sub(r"\s+", "", clean).strip()

    # 1. 匹配大类前缀
    prefix = ""
    subs = []
    for pattern, code in BASE_PATTERNS:
        if pattern in clean:
            prefix = code
            remaining = clean.replace(pattern, "\x00", 1)
            break
    else:
        # 没匹配到大类，尝试匹配子类工业行业名（说明是工业增加值相关，只是CSV省略了"工业增加值"）
        remaining = clean
        for pattern, code in SUB_PATTERNS:
            if pattern in remaining and len(pattern) >= 3:
                prefix = "IND_VA"
                remaining = remaining.replace(pattern, "\x00", 1)
                subs.append(code)
                break

    # 2. 继续匹配剩余子类
    for pattern, code in SUB_PATTERNS:
        if pattern in remaining:
            subs.append(code)
            remaining = remaining.replace(pattern, "\x00", 1)

    # 3. 后缀
    suffix = ""
    for pat, code in SUFFIX_PATTERNS:
        if re.search(pat, clean):
            suffix = code
            break

    # 4. 组装
    if prefix:
        parts = [prefix] + subs
        code = "_".join(parts)
    else:
        # 回退：取中文名的拼音首字母缩写
        code = _pinyin_fallback(clean)

    code = code.strip("_") + suffix
    return code[:50]


def _pinyin_fallback(text: str) -> str:
    """回退：将中文名转为拼音缩写"""
    from text_unidecode import unidecode
    # 去掉括号内容及其中文字的 unidecode
    base = re.sub(r"\([^)]*\)", "", text)
    # 用 unidecode 转为拼音 → 取各词首字母大写
    pinyin = unidecode(base)
    # 提取单词首字母
    words = pinyin.split()
    initials = "".join(w[0].upper() if w else "" for w in words)
    return initials[:35] if initials else "UNKNOWN"


# ── 脚注过滤 ──
def is_footnote(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if t[0] == "注":
        return True
    if "数据来源" in t[:5]:
        return True
    if re.match(r"^\d+[\.、]", t):
        return True
    return False


# ============================================================
# 导入逻辑
# ============================================================
INSERT_SQL = """INSERT INTO macro_indicator_data (zbcode, name, datestr, value)
    VALUES (%(zbcode)s, %(name)s, %(datestr)s, %(value)s)
    ON DUPLICATE KEY UPDATE name = VALUES(name), value = VALUES(value)"""


def import_all_csvs(data_dir: str = ".") -> int:
    csv_files = sorted(glob.glob(str(Path(data_dir) / "月度数据*.csv")))
    if not csv_files:
        print("未找到月度数据*.csv 文件")
        return 0

    print(f"找到 {len(csv_files)} 个 CSV 文件")
    print(f"时间窗口: {TIME_WINDOW_START} ~ {TIME_WINDOW_END}\n")

    total_count = 0
    file_count = 0
    code_map: dict[str, str] = {}
    skipped = 0

    for fpath in csv_files:
        fname = Path(fpath).name
        with open(fpath, encoding="utf-8-sig") as f:
            raw = f.read()

        lines = raw.strip().split("\n")
        if len(lines) < 4:
            skipped += 1
            continue

        header = [h.strip().strip(",") for h in lines[2].split("\t")]
        month_cols: dict[int, str] = {}
        for i, h in enumerate(header[1:], start=1):
            if h:
                try:
                    ds = month_header_to_datestr(h)
                    if in_time_window(ds):
                        month_cols[i] = ds
                except ValueError:
                    pass

        if not month_cols:
            skipped += 1
            continue

        data_rows = []
        for line in lines[3:]:
            if not line.strip():
                break
            cells = [c.strip().strip(",") for c in line.split("\t")]
            if not cells or not cells[0]:
                break
            if is_footnote(cells[0]):
                break
            data_rows.append(cells)

        # 先收集所有指标名，建立代码映射
        for cells in data_rows:
            raw_name = cells[0].strip()
            if raw_name and not is_footnote(raw_name) and raw_name not in code_map:
                code_map[raw_name] = generate_code(raw_name)

    # 解决重复代码：同名代码追加序号
    reverse: dict[str, list[str]] = {}
    for name, code in code_map.items():
        reverse.setdefault(code, []).append(name)
    for code, names in reverse.items():
        if len(names) > 1:
            for i, name in enumerate(names):
                code_map[name] = f"{code}_{i + 1}"
    del reverse

    # 导入数据
    for fpath in csv_files:
        fname = Path(fpath).name
        with open(fpath, encoding="utf-8-sig") as f:
            raw = f.read()

        lines = raw.strip().split("\n")
        if len(lines) < 4:
            skipped += 1
            continue

        header = [h.strip().strip(",") for h in lines[2].split("\t")]
        month_cols: dict[int, str] = {}
        for i, h in enumerate(header[1:], start=1):
            if h:
                try:
                    ds = month_header_to_datestr(h)
                    if in_time_window(ds):
                        month_cols[i] = ds
                except ValueError:
                    pass

        if not month_cols:
            skipped += 1
            continue

        data_rows = []
        for line in lines[3:]:
            if not line.strip():
                break
            cells = [c.strip().strip(",") for c in line.split("\t")]
            if not cells or not cells[0]:
                break
            if is_footnote(cells[0]):
                break
            data_rows.append(cells)

        file_count += 1
        row_count = 0
        for cells in data_rows:
            raw_name = cells[0].strip()
            if not raw_name or is_footnote(raw_name):
                continue

            if raw_name not in code_map:
                continue  # 不应该发生，已在第一遍扫描中注册
            zbcode = code_map[raw_name]

            for col_idx, datestr in month_cols.items():
                val_str = cells[col_idx].strip() if col_idx < len(cells) else ""
                if not val_str:
                    continue
                try:
                    execute_update(INSERT_SQL, {
                        "zbcode": zbcode,
                        "name": raw_name,
                        "datestr": datestr,
                        "value": float(val_str.replace(",", "")),
                    })
                    row_count += 1
                except Exception as e:
                    print(f"  [FAIL] {zbcode} {datestr}: {e}")

        total_count += row_count
        print(f"  [OK] {fname}: {len(data_rows)}指标 {len(month_cols)}月 {row_count}条")

    if skipped:
        print(f"  跳过 {skipped} 个文件（无数据或无时间窗口内列）")
    print(f"\n完成: {file_count}有效文件 {total_count}条 {len(code_map)}个唯一指标")
    return total_count


# ============================================================
# 命令行
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--preview", "-p"):
        csv_files = sorted(glob.glob("月度数据*.csv"))
        all_names = set()
        for fpath in csv_files:
            with open(fpath, encoding="utf-8-sig") as f:
                raw = f.read()
            lines = raw.strip().split("\n")
            if len(lines) < 4:
                continue
            for line in lines[3:]:
                cells = [c.strip().strip(",") for c in line.split("\t")]
                if not cells or not cells[0]:
                    break
                if is_footnote(cells[0]):
                    break
                name = cells[0].strip()
                if name and name not in all_names:
                    all_names.add(name)

        # 检查重复
        codes = {}
        for name in sorted(all_names):
            c = generate_code(name)
            codes.setdefault(c, []).append(name)
        dups = {c: ns for c, ns in codes.items() if len(ns) > 1}
        uniq = {c: ns for c, ns in codes.items() if len(ns) == 1}

        print(f"总计 {len(all_names)} 个指标，唯一代码 {len(codes)} 个")
        if dups:
            print(f"\n[WARNING] {len(dups)} 个重复代码:")
            for c, ns in list(dups.items()):
                print(f"\n  {c}:")
                for n in ns:
                    print(f"    ← {n}")
        else:
            print("\n[OK] 所有代码唯一")

        print("\n--- 代码映射预览（前30条）---")
        for name in sorted(all_names)[:30]:
            print(f"  {generate_code(name):<40} | {name}")
        sys.exit(0)

    print("批量导入宏观经济指标数据")
    db_config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(db_config)
    print(f"已连接: {MYSQL_CONFIG['database']}")

    n = import_all_csvs()
    print(f"\n总计: {n} 条")
