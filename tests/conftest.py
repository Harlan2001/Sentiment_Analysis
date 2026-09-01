"""
root conftest：在任何 backend 模块被 import 之前注入测试环境兜底值。

pytest 收集测试时先加载本文件，再 import 被测模块。backend/config/config.py
在模块导入时即读取 MYSQL_* 必填项（`_require_env_str`，缺 env 直接 RuntimeError），
而 CI 的 backend job 不带 .env 文件，因此这里用 setdefault 注入兜底值保证导入不崩。

约定（必须遵守）：
- 一律用 setdefault，CI / 显式设置的环境变量优先，绝不覆盖显式值。
- **绝不注入 MYSQL_TEST_DATABASE**：集成测试要求显式声明测试库，未声明即 skip，
  这是防止测试误连生产库 Sentiment_analysis 的第一道闸。
- 兜底的 MYSQL_DATABASE 指向测试库名，万一有测试意外触发数据库逻辑，
  落点也是测试库，而不是生产库。
"""

import os


def _seed_default_env() -> None:
    defaults = {
        # MySQL 兜底指向「测试库」：Sentiment_analysis 是生产库，测试不得触碰。
        # 密码用 ci-dummy 值，仅为让 config 导入不崩；单元测试不连真实 DB。
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "root",
        "MYSQL_PASSWORD": "ci-dummy-password",
        "MYSQL_DATABASE": "Sentiment_analysis_test",
        "MYSQL_CHARSET": "utf8mb4",
        # LLM 兜底：analyzer 等模块导入期可能读 key；CI 无 .env 时不能崩。
        # （真正调用 LLM 的用例一律用 respx/MockTransport mock，见 P2 的 unit conftest。）
        "LLM_API_KEY": "ci-dummy-key",
        "LLM_BASE_URL": "https://ci-dummy.example.com/v1",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


_seed_default_env()
