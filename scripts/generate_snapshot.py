"""
【临时兼容】快照生成脚本
在内网环境运行以生成策略/标的 API 快照文件，供 SaaS 环境无法访问内网时使用。

运行方式：
    python scripts/generate_snapshot.py

前置条件：
    已配置 .env 中的内网 API 相关变量（STRATEGY_API_BASE_URL、BOND_API_BASE_URL、
    QUANT_STRATEGY_BASE_URL、QUANT_STRATEGY_TOKEN、KINGSTAR_EMPLOYEE_NO）

输出文件：
    - data/snapshots/trading_strategies.json  （交易策略列表）
    - data/snapshots/quant_strategies.json    （量化策略列表）
    - data/snapshots/targets.json             （债券标的列表）
"""

import json
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

# 加载 .env 配置（内网 API 地址等），但不覆盖已有的环境变量
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

# 导入后强制关闭离线模式，否则函数会尝试读取不存在的快照文件
from backend.config import config
config.USE_LOCAL_SNAPSHOT = False

from backend.strategy.strategy_recommendation import (
    get_available_strategies,
    get_available_quant_strategies,
    get_available_targets,
)


def main() -> None:
    # 确保快照目录存在
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 交易策略
    print("正在获取交易策略列表...")
    try:
        trading_strategies = get_available_strategies()
        trading_path = config.SNAPSHOT_DIR / "trading_strategies.json"
        with open(trading_path, "w", encoding="utf-8") as f:
            json.dump(trading_strategies, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 交易策略: {len(trading_strategies)} 条 -> {trading_path}")
    except Exception as exc:
        print(f"  [FAIL] 交易策略获取失败: {exc}")
        trading_strategies = None

    # 2. 量化策略
    print("正在获取量化策略列表...")
    try:
        quant_strategies = get_available_quant_strategies(page_size=100, page_num=1)
        quant_path = config.SNAPSHOT_DIR / "quant_strategies.json"
        with open(quant_path, "w", encoding="utf-8") as f:
            json.dump(quant_strategies, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 量化策略: {len(quant_strategies)} 条 -> {quant_path}")
    except Exception as exc:
        print(f"  [FAIL] 量化策略获取失败: {exc}")
        quant_strategies = None

    # 3. 债券标的
    print("正在获取债券标的列表...")
    try:
        targets = get_available_targets()
        targets_path = config.SNAPSHOT_DIR / "targets.json"
        with open(targets_path, "w", encoding="utf-8") as f:
            json.dump(targets, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 债券标的: {len(targets)} 条 -> {targets_path}")
    except Exception as exc:
        print(f"  [FAIL] 债券标的获取失败: {exc}")
        targets = None

    # 汇总
    print("\n===== 快照生成完成 =====")
    all_ok = all(
        x is not None for x in (trading_strategies, quant_strategies, targets)
    )
    if all_ok:
        print("所有快照文件均已成功生成。")
        print("将 data/snapshots/ 目录部署到 SaaS 环境，并设置 USE_LOCAL_SNAPSHOT=true 即可使用。")
    else:
        print("部分快照生成失败，请检查内网 API 连接和凭据配置后重试。")


if __name__ == "__main__":
    main()
