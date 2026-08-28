"""PR 增量(diff)覆盖率检查。

计算本 PR 新增的 Python 代码里,真正执行过(path 覆盖)的比例,输出逐文件表格。

与"全局覆盖率"的区别:
- 全局覆盖率统计整个后端的行覆盖(XML/Coverage),存量低的模块会把数字拖到极难看。
- diff 覆盖率只针对**你这次 PR 新增**的可执行语句——"改过的代码够不够测?"
  团队约定:新增代码覆盖率应 >=80%,存量债分期另算。

运行前提(与 ci.yml 保持一致):
  pytest 带 --cov-report=xml 生成 coverage.xml(脚本本地也认这个文件)

用法(本地):
  uv run pytest tests/unit --cov=backend --cov-report=xml
  uv run python scripts/check_diff_coverage.py --base origin/main

行为:
- 默认:只报告,不拦截(退出码始终 0)。为了让团队先看到数字再养成习惯。
- DIFF_COVERAGE_MIN 设置后开始拦截:新增代码覆盖率低于该阈值 → 退出码 1。
- DIFF_COVERAGE_STRICT=1 时,新增了"未被 pytest import"的 Python 文件也会失败,
  鼓励把新模块纳入测试。(默认只警告。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIN_COVERAGE = 80


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def resolve_base(explicit: str | None) -> str:
    """确定 diff 基准:优先显式 --base,其次 DIFF_COVERAGE_BASE,最后 origin/main。"""
    if explicit:
        return explicit
    env = os.getenv("DIFF_COVERAGE_BASE")
    if env:
        return env
    try:
        return _git(["rev-parse", "origin/main"]).strip()
    except subprocess.CalledProcessError:
        sys.exit("无法确定 diff 基准:请用 --base <提交> 或设置 DIFF_COVERAGE_BASE")


def changed_py_files(base: str) -> list[str]:
    """base 与**工作树**之间有差异的 .py(含未跟踪的新文件)。

    用 `git diff base`(而非 base...HEAD),这样本地改动没提交也能测;CI 里工作树
    即 PR 检出结果,二者一致。tests/、scripts/ 是非生产代码,不参与统计。
    """
    tracked = _git(["diff", "--name-only", base, "--", "*.py"]).splitlines()
    untracked = _git(["ls-files", "--others", "--exclude-standard", "--", "*.py"]).splitlines()
    return sorted(
        {
            p.strip()
            for p in tracked + untracked
            if p.strip() and not p.startswith(("tests/", "scripts/"))
        }
    )


def added_line_numbers(base: str, path: str) -> set[int]:
    """该文件相对 base 新增的行号;若为未跟踪新文件则整份算新增。

    行号对应工作树版本(= coverage.xml 的行号)。
    """
    if not _git(["ls-files", "--", path]).strip():
        lines = (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
        return set(range(1, len(lines) + 1))

    out = _git(["diff", "-U0", base, "--", path])
    added: set[int] = set()
    for hunk in re.finditer(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@", out, re.M):
        start = int(hunk.group(2))
        count = int(hunk.group(3) or "1")
        added.update(range(start, start + count))
    return added


def load_coverage_xml(path: Path) -> dict[str, dict[int, bool]]:
    """解析 coverage.xml → {文件相对路径: {行号: 是否执行}}。

    仅解析自身引入了行号的 class 文件;不在 XML 里的 .py 视为"未被 pytest 导入"。
    """
    if not path.exists():
        return {}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return {}
    result: dict[str, dict[int, bool]] = {}
    for cls in root.findall(".//class"):
        filename = cls.get("filename")
        if not filename:
            continue
        lines: dict[int, bool] = {}
        for line in cls.findall("./lines/line"):
            number = int(line.get("number", "0"))
            hits = int(line.get("hits", "0"))
            lines[number] = hits > 0
        result[filename] = lines
    return result


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="计算 PR 增量覆盖率")
    parser.add_argument("--base", help="diff 基准提交(默认 origin/main)")
    parser.add_argument(
        "--xml", default=str(ROOT / "coverage.xml"), help="coverage.xml 路径"
    )
    args = parser.parse_args()

    enforce_min = os.getenv("DIFF_COVERAGE_MIN")
    strict = os.getenv("DIFF_COVERAGE_STRICT", "0") == "1"

    base = resolve_base(args.base)
    coverage_by_file = load_coverage_xml(Path(args.xml))
    py_files = changed_py_files(base)
    if not py_files:
        print("本次 PR 没有 Python 文件变更,跳过。")
        return 0
    if not coverage_by_file:
        print(
            f"未找到 {args.xml}(本地先跑:uv run pytest tests/unit "
            "--cov=backend --cov-report=xml),本次跳过拦截。"
        )
        return 0

    rows: list[dict] = []
    total_new = total_covered = 0
    unimported: list[str] = []
    no_new_code: list[str] = []

    for path in py_files:
        added = added_line_numbers(base, path)
        measured = coverage_by_file.get(path)
        if measured is None:
            # 该文件没出现在 coverage.xml —— pytest 压根没 import 它
            if added:
                unimported.append(path)
            continue
        statements = set(measured)
        if not statements:
            no_new_code.append(path)
            continue

        new_statements = added & statements
        if not new_statements:
            no_new_code.append(path)
            continue
        covered = {ln for ln in new_statements if measured[ln]}
        rows.append(
            {
                "file": path,
                "new": len(new_statements),
                "covered": len(covered),
                "pct": len(covered) / len(new_statements) * 100,
            }
        )
        total_new += len(new_statements)
        total_covered += len(covered)

    # ---- 输出 ----
    print(f"\ndiff 基准: {base}  |  变更 .py: {len(py_files)} 个\n")
    if rows:
        rows.sort(key=lambda r: r["pct"])
        print(f"{'文件':<48}{'新增可执行':>10}{'已覆盖':>8}{'覆盖率':>9}")
        print("-" * 80)
        for r in rows:
            print(f"{r['file']:<48}{r['new']:>10}{r['covered']:>8}{r['pct']:>8.1f}%")
        if total_new:
            overall = total_covered / total_new * 100
            print("-" * 80)
            print(f"合计 diff 覆盖率:{overall:.1f}%({total_covered}/{total_new})")
    else:
        print("没有新增可执行语句(新增文件可能未纳入测试或全为注释)。")

    if unimported:
        print("\n⚠ 以下文件被追加但未被 pytest import(coverage.xml 里没有它们):")
        for p in unimported:
            print(f"   {p}")
        print("   建议为其补测试;若依赖 torch/DB 过重,先在 conftest 里做 import 隔离。")

    if no_new_code:
        print(f"\n(信息) 变更但无新增可执行语句的文件: {no_new_code}")

    # ---- 拦截逻辑(默认不拦截,设 DIFF_COVERAGE_MIN 才启用) ----
    if not enforce_min:
        print(
            f"\n[报告模式] 不拦截。将 gate 打开:在 CI 设置 DIFF_COVERAGE_MIN={DEFAULT_MIN_COVERAGE} "
            "(含义:新增代码 8 成要有测试)。"
        )
        return 0

    threshold = float(enforce_min)
    if total_new and overall < threshold:
        print(f"\n❌ diff 覆盖率 {overall:.1f}% < {threshold:.0f}%,合并被拦截。")
        return 1
    if strict and unimported:
        print("\n❌ DIFF_COVERAGE_STRICT:存在未被 import 的新文件。")
        return 1
    print(f"\n✅ diff 覆盖率 {total_covered}/{total_new} 达标 >= {threshold:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())