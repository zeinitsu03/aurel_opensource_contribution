import json

from aurel.analyzer import analyze_repository
from aurel.config import AurelConfig
from aurel.models import IssueReadiness, Repository
from aurel.report import (
    analysis_to_dict,
    format_html_report,
    format_json_report,
    format_markdown_report,
    format_report_comparison,
    format_summary_report,
    format_terminal_report,
    format_text_report,
)


def test_terminal_report_includes_backlog_and_score():
    analysis = _analysis()

    report = format_terminal_report(analysis)

    assert "Repository: github:owner/repo" in report
    assert "Detected Profile: Python project" in report
    assert "Contributor Readiness Score: 58/100 (58%)" in report
    assert "Score Categories:" in report
    assert "Issue Readiness:" in report
    assert "Workflow Templates:" in report
    assert "Top Fixes To Reach 90:" in report
    assert "Newcomer Onboarding Path:" in report
    assert "Contributor Signals:" in report
    assert "Findings:" in report
    assert "Improvement Backlog:" in report
    assert "Maintainer Guidance:" in report
    assert "Program Organizer Notes:" in report
    assert "Acceptance:" in report
    assert "docs: add contributing guide" in report


def test_summary_report_shows_score_top_fixes_and_first_pr():
    analysis = _analysis()

    report = format_summary_report(analysis)

    assert report.startswith("Repository: github:owner/repo")
    assert "Score: 58/100 - Needs improvement" in report
    assert "Held back by:" in report
    assert "Top fixes:\n1. " in report
    assert f"- PR title: {analysis.starter_pr_kit.pr_title}" in report
    assert "Note: test skipped issue readiness" in report
    assert "Findings:" not in report
    assert "Improvement Backlog:" not in report


def test_summary_report_limits_top_fixes_and_points_to_detailed():
    analysis = _analysis(found={"pyproject.toml"})
    assert len(analysis.recommendations) > 3

    report = format_summary_report(analysis)

    assert "\n3. " in report
    assert "\n4. " not in report
    assert f"...and {len(analysis.recommendations) - 3} more with --detailed" in report


def test_text_report_is_plain_text_document():
    report = format_text_report(_analysis())

    assert report.startswith("Repository: github:owner/repo")
    assert "Starter PR Kit:" in report
    assert "# Aurel Contributor Readiness Report" not in report
    assert "<!doctype html>" not in report


def test_markdown_report_includes_starter_pr_kit_and_backlog():
    analysis = _analysis()

    report = format_markdown_report(analysis)

    assert "# Aurel Contributor Readiness Report" in report
    assert "## Detected Profile" in report
    assert "## Workflow Templates" in report
    assert "## Top Fixes To Reach 90" in report
    assert "## Newcomer Onboarding Path" in report
    assert "## Contributor Signals" in report
    assert "## Findings" in report
    assert "## Starter PR Kit" in report
    assert "## Improvement Backlog" in report
    assert "## Maintainer Guidance" in report
    assert "## Program Organizer Notes" in report
    assert "`docs: add CONTRIBUTING guide`" in report


def test_json_report_includes_stable_ids_and_structured_evidence():
    data = json.loads(format_json_report(_analysis()))

    assert data["schema_version"] == "1.0"
    assert data["aurel_version"] == "1.0.0"
    assert data["repository"]["display_name"] == "github:owner/repo"
    assert data["findings"][0]["id"].startswith("finding.")
    assert data["findings"][0]["evidence"][0]["kind"] in {"path", "text"}
    assert data["recommendations"][0]["id"].startswith("recommendation.")


def test_json_report_marks_sentence_evidence_as_text():
    data = json.loads(format_json_report(_analysis(found={"README.md"})))

    assert data["profile"]["evidence"] == [
        {
            "kind": "text",
            "value": "No strong language or framework files were detected in common locations.",
        }
    ]


def test_html_report_is_dependency_free_standalone_output():
    report = format_html_report(_analysis())

    assert "<!doctype html>" in report
    assert "Aurel Contributor Readiness Report" in report
    assert "github:owner/repo" in report


def test_report_comparison_summarizes_score_and_changed_findings():
    current = analysis_to_dict(_analysis())
    previous = {
        **current,
        "score": {**current["score"], "value": 40},
        "findings": [],
        "recommendations": [],
    }

    comparison = format_report_comparison(previous, current)

    assert "Score: 40 -> 58 (+18)" in comparison
    assert "Findings: 0 ->" in comparison
    assert "Recommendations: 0 ->" in comparison


def _analysis(found=None):
    found = found or {"pyproject.toml", "README.md", "LICENSE"}

    def fake_file_exists(repo, path):
        return path in found

    def fake_file_content(repo, path):
        return (
            "# Example\n\n"
            "Install the project with `python -m pip install -r requirements.txt`. "
            "Run the usage example with `aurel https://github.com/owner/repo`. "
            "Execute tests with `python -m pytest`, lint with `ruff check .`, "
            "and build with `python -m build`. "
            "This README gives beginners enough context to understand the project "
            "purpose, contributor workflow, and verification path."
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
