"""PR 增量覆盖率脚本的文件筛选回归测试。"""

from types import SimpleNamespace

from scripts import check_diff_coverage


def test_changed_py_files_skips_deleted_files(monkeypatch, tmp_path):
    """删除文件不能进入后续 read_text，否则纯删除 PR 会让 CI 崩溃。"""
    monkeypatch.setattr(check_diff_coverage, "ROOT", tmp_path)
    for relative in ("backend/existing.py", "backend/new.py", "scripts/helper.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n", encoding="utf-8")

    def fake_git(args: list[str]) -> str:
        if args[:2] == ["diff", "--name-only"]:
            return (
                "backend/existing.py\n"
                "backend/deleted.py\n"
                "scripts/helper.py\n"
                "tests/unit/test_example.py\n"
            )
        if args[:2] == ["ls-files", "--others"]:
            return "backend/new.py\nbackend/missing_untracked.py\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(check_diff_coverage, "_git", fake_git)

    assert check_diff_coverage.changed_py_files("base") == [
        "backend/existing.py",
        "backend/new.py",
    ]


def test_git_decodes_diff_output_as_utf8(monkeypatch):
    """中文 diff 在 Windows 默认 GBK 环境下也不能破坏覆盖率门禁。"""
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(stdout="中文 diff")

    monkeypatch.setattr(check_diff_coverage.subprocess, "run", fake_run)

    assert check_diff_coverage._git(["diff", "--name-only"]) == "中文 diff"
    assert captured["command"] == ["git", "diff", "--name-only"]
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_coverage_xml_normalizes_windows_paths(tmp_path):
    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text(
        """<coverage><packages><package><classes>
        <class filename="backend\\routers\\research.py">
          <lines><line number="3" hits="1" /><line number="4" hits="0" /></lines>
        </class>
        </classes></package></packages></coverage>""",
        encoding="utf-8",
    )

    assert check_diff_coverage.load_coverage_xml(coverage_xml) == {
        "backend/routers/research.py": {3: True, 4: False}
    }
