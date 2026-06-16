import argparse
from datetime import datetime, timedelta
from pathlib import Path
import requests
from backend.config.config import BOND_XLSX, MYSQL_CONFIG
from backend.common.database import DatabaseConfig, init_database, get_db_connection
from backend.yield_db import import_yield_data_from_excel

def date_diff(end_date, start_date):
    """
    计算两个日期相差天数（和JS的dateDiff逻辑一致）
    """
    fmt = "%Y-%m-%d"  # 根据你页面日期格式调整，通常是这个
    d1 = datetime.strptime(end_date, fmt)
    d2 = datetime.strptime(start_date, fmt)
    return (d1 - d2).days

def download_history_excel(
    start_date,
    end_date,
    gjqx,
    locale="zh_CN",
    name_type="1",
    output_path=BOND_XLSX,
):
    """
    下载历史收益率Excel文件
    :param start_date: 开始日期，格式 yyyy-mm-dd
    :param end_date: 结束日期，格式 yyyy-mm-dd
    :param gjqx: 勾选的周期值（对应JS里的checkBoxValue）
    :param locale: 语言，默认zh_CN
    :param name_type: 名称类型，默认1
    :param output_path: 保存文件路径，默认 data/GovernmentBonds.xlsx
    :return: 保存文件
    """
    # 1. 校验时间不能超过1年
    if date_diff(end_date, start_date) >= 365:
        print("❌ 下载时间段不能超过1年")
        return

    # 2. 拼接请求URL（和JS完全一样）
    base_url = "https://yield.chinabond.com.cn/cbweb-czb-web/czb/historyDown"
    params = {
        "startDate": start_date,
        "endDate": end_date,
        "gjqx": gjqx,
        "locale": locale,
        "nameType": name_type,
        "qxmc": name_type
    }

    try:
        # 3. 发送请求下载文件
        print("🔽 正在下载文件...")
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()

        # 4. 保存Excel文件
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"✅ 下载完成！文件保存为：{output_path}")
        return output_path

    except Exception as e:
        print(f"❌ 下载失败：{str(e)}")
        raise


def download_latest_history_excel(
    output_path=BOND_XLSX,
    days=365,
    gjqx="0",
    locale="zh_CN",
    name_type="1",
):
    """
    下载最近一段时间的收益率Excel，默认覆盖到 data/GovernmentBonds.xlsx。
    """
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days - 1)
    return download_history_excel(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        gjqx=gjqx,
        locale=locale,
        name_type=name_type,
        output_path=output_path,
    )


def update_yield_data(
    excel_path=BOND_XLSX,
    days=365,
    gjqx="0",
    locale="zh_CN",
    name_type="1",
):
    """
    下载最新收益率 Excel，并将内容增量导入数据库。
    """
    # 脚本独立运行时需要先初始化数据库配置和连接池。
    init_database(DatabaseConfig(**MYSQL_CONFIG))

    downloaded_path = download_latest_history_excel(
        output_path=excel_path,
        days=days,
        gjqx=gjqx,
        locale=locale,
        name_type=name_type,
    )
    if not downloaded_path:
        raise RuntimeError("yield excel download did not produce a file")
    
    with get_db_connection() as conn:
        conn.commit()

    import_yield_data_from_excel(Path(downloaded_path))


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Download latest yield excel and import new rows into database."
    )
    parser.add_argument(
        "--excel-path",
        default=str(BOND_XLSX),
        help="Output path for the downloaded Excel file.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="How many recent calendar days to request.",
    )
    parser.add_argument(
        "--gjqx",
        default="0",
        help="Term selection parameter passed to Chinabond download API.",
    )
    parser.add_argument("--locale", default="zh_CN")
    parser.add_argument("--name-type", default="1")
    return parser


def main():
    args = build_arg_parser().parse_args()
    update_yield_data(
        excel_path=args.excel_path,
        days=args.days,
        gjqx=args.gjqx,
        locale=args.locale,
        name_type=args.name_type,
    )


if __name__ == '__main__':
    main()