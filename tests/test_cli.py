import json
from pathlib import Path

import pytest

from aurel import __main__ as package_main
from aurel import cli
from aurel.analyzer import analyze_repository
from aurel.config import AurelConfig
from aurel.models import IssueReadiness, Repository

TEST_ARTIFACTS = Path(".test_artifacts")


def test_main_shows_aurel_banner_for_terminal_output(monkeypatch, capsys):
    analysis = _analysis()
    monkeypatch.setattr(cli, "load_config", lambda path=None: AurelConfig())
    monkeypatch.setattr(
        cli,
        "parse_repository_url",
        lambda url: Repository(provider="github", owner="owner", name="repo"),
    )
    monkeypatch.setattr(
        cli,
        "analyze_repository",
        lambda repository, config, token=None: analysis,
    )

    exit_code = cli.main(["https://github.com/owner/repo"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AUREL v1.0.0" in output
    assert "Contributor Readiness CLI" in output
    assert "Repository: github:owner/repo" in output


def test_main_start_command_shows_banner_without_repository(capsys):
    exit_code = cli.main(["start"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AUREL v1.0.0" in output
    assert "Contributor Readiness CLI" in output
    assert "Aurel is ready" in output


def test_main_rejects_start_alias_flags(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--start"])

    captured = capsys.readouterr()
    assert "unrecognized arguments: --start" in captured.err


def test_main_keeps_json_output_machine_readable(monkeypatch, capsys):
    analysis = _analysis()
    monkeypatch.setattr(cli, "load_config", lambda path=None: AurelConfig())
    monkeypatch.setattr(
        cli,
        "parse_repository_url",
        lambda url: Repository(provider="github", owner="owner", name="repo"),
    )
    monkeypatch.setattr(
        cli,
        "analyze_repository",
        lambda repository, config, token=None: analysis,
    )

    exit_code = cli.main(["https://github.com/owner/repo", "--format", "json"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.lstrip().startswith("{")
    assert "Contributor Readiness CLI" not in output


def test_main_keeps_json_stdout_machine_readable_when_writing_output(
    monkeypatch,
    capsys,
):
    analysis = _analysis()
    monkeypatch.setattr(cli, "load_config", lambda path=None: AurelConfig())
    monkeypatch.setattr(
        cli,
        "parse_repository_url",
        lambda url: Repository(provider="github", owner="owner", name="repo"),
    )
    monkeypatch.setattr(
        cli,
        "analyze_repository",
        lambda repository, config, token=None: analysis,
    )
    output_path = TEST_ARTIFACTS / "cli-report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exit_code = cli.main(
        [
            "https://github.com/owner/repo",
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["repository"]["display_name"] == "github:owner/repo"
    assert "Json report written" in captured.err
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_main_writes_explicit_text_report(monkeypatch, capsys):
    analysis = _analysis()
    monkeypatch.setattr(cli, "load_config", lambda path=None: AurelConfig())
    monkeypatch.setattr(
        cli,
        "parse_repository_url",
        lambda url: Repository(provider="github", owner="owner", name="repo"),
    )
    monkeypatch.setattr(
        cli,
        "analyze_repository",
        lambda repository, config, token=None: analysis,
    )
    output_path = TEST_ARTIFACTS / "cli-report-explicit.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exit_code = cli.main(
        [
            "https://github.com/owner/repo",
            "--format",
            "text",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    saved_report = output_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert captured.out.startswith("Repository: github:owner/repo")
    assert "AUREL v1.0.0" not in captured.out
    assert saved_report.startswith("Repository: github:owner/repo")
    assert "Starter PR Kit:" in saved_report
    assert "Text report written" in captured.err


def test_main_infers_text_report_from_txt_output(monkeypatch, capsys):
    analysis = _analysis()
    monkeypatch.setattr(cli, "load_config", lambda path=None: AurelConfig())
    monkeypatch.setattr(
        cli,
        "parse_repository_url",
        lambda url: Repository(provider="github", owner="owner", name="repo"),
    )
    monkeypatch.setattr(
        cli,
        "analyze_repository",
        lambda repository, config, token=None: analysis,
    )
    output_path = TEST_ARTIFACTS / "cli-report-inferred.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    exit_code = cli.main(["https://github.com/owner/repo", "--output", str(output_path)])

    captured = capsys.readouterr()
    saved_report = output_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "AUREL v1.0.0" in captured.out
    assert saved_report.startswith("Repository: github:owner/repo")
    assert "# Aurel Contributor Readiness Report" not in saved_report
    assert "Text report written" in captured.err


def test_min_score_rejects_out_of_range_threshold():
    parser = cli.build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["https://github.com/owner/repo", "--min-score", "101"])


def test_help_mentions_start_command_and_text_output(capsys):
    parser = cli.build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    output = capsys.readouterr().out
    assert "aurel start" in output
    assert "--output report.txt" in output


def test_package_module_entrypoint_uses_cli_main():
    assert package_main.main is cli.main


def _analysis():
    found = {"pyproject.toml", "README.md", "LICENSE"}

    def fake_file_exists(repo, path):
        return path in found

    def fake_file_content(repo, path):
        return (
            "# Example\n\n"
            "Install with `python -m pip install -r requirements.txt`. "
            "Run with `aurel https://github.com/owner/repo`. "
            "Test with `python -m pytest`, lint with `ruff check .`, "
            "and build with `python -m build`."
        )

    return analyze_repository(
        Repository(provider="github", owner="owner", name="repo"),
        AurelConfig(),
        file_exists=fake_file_exists,
        file_content=fake_file_content,
        issue_loader=lambda repo: IssueReadiness(
            checked=False,
            beginner_issue_count=0,
            labels_found=(),
            confidence="Low",
            note="test skipped issue readiness",
        ),
    )
