import pytest

from aurel.config import AurelConfig
from aurel.guidance import build_starter_pr_kit
from aurel.models import CommunitySignal, Finding
from aurel.scorer import (
    calculate_score,
    get_score_label,
)


def test_calculate_score_with_all_mvp_signals():
    file_results = {
        "README.md": True,
        "LICENSE": True,
        "CONTRIBUTING.md": True,
        "SECURITY.md": True,
        "CODE_OF_CONDUCT.md": True,
    }

    score = calculate_score(file_results, valid_url=True)

    assert score.value == 100
    assert score.max_value == 100
    assert score.percentage == 100
    assert score.label == "Excellent contributor readiness"


def test_calculate_score_with_missing_files():
    file_results = {
        "README.md": True,
        "LICENSE": True,
        "CONTRIBUTING.md": False,
        "SECURITY.md": False,
        "CODE_OF_CONDUCT.md": False,
    }

    score = calculate_score(file_results, valid_url=True)

    assert score.value == 55
    assert score.max_value == 100
    assert score.percentage == 55
    assert score.label == "Needs improvement"


def test_calculate_score_uses_configured_weights():
    config = AurelConfig(
        signal_paths={
            "readme": ("README.md",),
            "contributing": ("docs/CONTRIBUTING.md",),
        },
        signal_weights={"readme": 50, "contributing": 40},
    )

    file_results = {
        "README.md": True,
        "docs/CONTRIBUTING.md": False,
    }

    score = calculate_score(file_results, valid_url=True, config=config)

    assert score.value == 60
    assert score.max_value == 100
    assert score.label == "Needs improvement"


def test_score_deducts_existing_content_quality_findings():
    signals = (
        _signal("readme", True, 25),
        _signal("license", True, 20),
    )
    findings = (
        Finding(
            title="README looks very short",
            detail="The README is short.",
            recommendation="Add setup and usage details.",
            severity="Medium",
            confidence="Medium",
            evidence=("README.md",),
        ),
    )

    score = calculate_score(signals, findings=findings)

    assert score.value == 85
    assert score.max_value == 100
    assert score.categories[0].name == "Documentation Quality"
    assert score.categories[0].value == 17


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (100, "Excellent contributor readiness"),
        (90, "Excellent contributor readiness"),
        (89, "Very beginner-friendly"),
        (85, "Very beginner-friendly"),
        (84, "Good for beginners"),
        (70, "Good for beginners"),
        (69, "Needs improvement"),
        (50, "Needs improvement"),
        (49, "Difficult for beginners"),
        (0, "Difficult for beginners"),
    ],
)
def test_score_label_boundaries(score, label):
    assert get_score_label(score) == label


def test_starter_pr_kit_prioritizes_contributing_guide():
    file_results = {
        "README.md": False,
        "LICENSE": False,
        "CONTRIBUTING.md": False,
        "SECURITY.md": False,
        "CODE_OF_CONDUCT.md": False,
    }

    kit = build_starter_pr_kit(file_results)

    assert "contributor instructions" in kit.contribution
    assert kit.pr_title == "docs: add contributing guide for new contributors"
    assert kit.commit_message == "docs: add CONTRIBUTING guide"
    assert kit.confidence == "High"


def test_starter_pr_kit_suggests_setup_docs_when_no_files_are_missing():
    file_results = {
        "README.md": True,
        "LICENSE": True,
        "CONTRIBUTING.md": True,
        "SECURITY.md": True,
        "CODE_OF_CONDUCT.md": True,
    }

    kit = build_starter_pr_kit(file_results)

    assert "setup" in kit.contribution.lower()
    assert kit.pr_title == "docs: clarify setup steps for new contributors"


ALL_FILES_PRESENT = {
    "README.md": True,
    "LICENSE": True,
    "CONTRIBUTING.md": True,
    "SECURITY.md": True,
    "CODE_OF_CONDUCT.md": True,
}


def test_starter_pr_kit_skips_findings_only_maintainers_can_fix():
    issue_finding = _finding(
        "Beginner-friendly issue path not detected", "Issue Readiness", 89
    )

    kit = build_starter_pr_kit(ALL_FILES_PRESENT, (issue_finding,))

    assert kit.pr_title == "docs: clarify setup steps for new contributors"
    assert "Label" not in kit.contribution


def test_starter_pr_kit_uses_action_title_for_strictest_fixable_finding():
    findings = (
        _finding("Beginner-friendly issue path not detected", "Issue Readiness", 89),
        _finding("Test command is not obvious from the README", "Setup & Testing Clarity", 85),
        _finding(
            "Install command is not obvious from the README", "Setup & Testing Clarity", 80
        ),
    )

    kit = build_starter_pr_kit(ALL_FILES_PRESENT, findings)

    assert kit.pr_title == "docs: add install command to README"
    assert kit.commit_message == "docs: add install command to README"
    assert kit.contribution == "Fix: Install command is not obvious from the README"


def _finding(title, category, score_cap):
    return Finding(
        title=title,
        detail=f"Detail: {title}",
        recommendation=f"Fix: {title}",
        severity="Medium",
        confidence="Medium",
        evidence=("README.md",),
        category=category,
        score_cap=score_cap,
    )


def _signal(key, present, weight):
    return CommunitySignal(
        key=key,
        label=key,
        present=present,
        required=True,
        weight=weight,
        matched_path=f"{key}.md" if present else None,
        searched_paths=(f"{key}.md",),
        confidence="High" if present else "Medium",
        note="test signal",
    )
