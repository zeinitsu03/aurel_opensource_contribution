from aurel.advisor import build_recommendations
from aurel.models import CommunitySignal, Finding, IssueReadiness, ScoreResult


def test_advisor_prioritizes_high_impact_missing_signals():
    recommendations = build_recommendations(
        signals=(
            _signal("readme", False, 25),
            _signal("contributing", False, 20),
            _signal("license", True, 20),
        ),
        findings=(),
        issue_readiness=_issue_readiness(0),
        score=ScoreResult(value=40, max_value=100, label="Difficult for beginners"),
    )

    assert recommendations[0].title == "Add project overview or docs entry point"
    assert recommendations[0].estimated_score_gain == 25
    assert any(item.title == "Create beginner-friendly issue paths" for item in recommendations)


def test_advisor_turns_quality_finding_into_actionable_fix():
    findings = (
        Finding(
            title="Testing instructions are not obvious from the README",
            detail="A contributor needs a verification path.",
            recommendation="Add the smallest test command contributors should run.",
            severity="Low",
            confidence="Medium",
            evidence=("README.md",),
            category="Setup & Testing Clarity",
            score_cap=85,
        ),
    )

    recommendations = build_recommendations(
        signals=(_signal("readme", True, 25),),
        findings=findings,
        issue_readiness=_issue_readiness(2),
        score=ScoreResult(value=85, max_value=100, label="Very beginner-friendly"),
    )

    assert recommendations[0].title == "Testing instructions are not obvious from the README"
    assert recommendations[0].estimated_score_gain == 8
    assert recommendations[0].source == "finding"


def test_advisor_does_not_repeat_dedicated_issue_recommendation():
    findings = (
        Finding(
            title="Beginner-friendly issue path not detected",
            detail="No labeled issues were found.",
            recommendation="Label small issues for beginners.",
            severity="Medium",
            confidence="Medium",
            evidence=("good first issue", "help wanted"),
            category="Issue Readiness",
            score_cap=89,
        ),
    )

    recommendations = build_recommendations(
        signals=(_signal("readme", True, 25),),
        findings=findings,
        issue_readiness=_issue_readiness(0),
        score=ScoreResult(value=80, max_value=100, label="Good for beginners"),
    )

    titles = [item.title for item in recommendations]
    assert titles.count("Create beginner-friendly issue paths") == 1
    assert "Beginner-friendly issue path not detected" not in titles


def test_advisor_ranks_fix_for_strictest_score_cap_first():
    install_finding = Finding(
        title="Install command is not obvious from the README",
        detail="Contributors cannot find the install step.",
        recommendation="Add the install command.",
        severity="Medium",
        confidence="Medium",
        evidence=("README.md",),
        category="Setup & Testing Clarity",
        score_cap=80,
    )
    security_finding = Finding(
        title="Security reporting instructions not detected",
        detail="No security policy.",
        recommendation="Add a security policy.",
        severity="Low",
        confidence="Medium",
        evidence=("security.md",),
        category="Community & Safety",
        score_cap=89,
    )

    recommendations = build_recommendations(
        signals=(_signal("readme", True, 25), _signal("security", False, 15)),
        findings=(security_finding, install_finding),
        issue_readiness=_issue_readiness(2),
        score=ScoreResult(value=56, max_value=100, label="Needs improvement"),
    )

    assert recommendations[0].title == "Install command is not obvious from the README"
    assert recommendations[0].score_cap == 80
    assert recommendations[1].title == "Add security reporting instructions"
    assert recommendations[1].score_cap == 89


def test_advisor_treats_high_severity_finding_as_capped():
    finding = Finding(
        title="README appears to contain placeholder text",
        detail="Placeholder text found.",
        recommendation="Replace the placeholder text.",
        severity="High",
        confidence="High",
        evidence=("README.md",),
        category="Documentation Quality",
    )

    recommendations = build_recommendations(
        signals=(_signal("readme", True, 25),),
        findings=(finding,),
        issue_readiness=_issue_readiness(2),
        score=ScoreResult(value=80, max_value=100, label="Good for beginners"),
    )

    assert recommendations[0].score_cap == 89


def _signal(key, present, weight):
    return CommunitySignal(
        key=key,
        label={
            "readme": "Project overview or docs entry point",
            "contributing": "Contribution guide",
            "license": "License information",
            "security": "Security reporting instructions",
        }.get(key, key),
        present=present,
        required=True,
        weight=weight,
        matched_path=f"{key}.md" if present else None,
        searched_paths=(f"{key}.md",),
        confidence="High" if present else "Medium",
        note="test signal",
    )


def _issue_readiness(count):
    return IssueReadiness(
        checked=True,
        beginner_issue_count=count,
        labels_found=("good first issue",) if count else (),
        confidence="High" if count else "Medium",
        note="test issue readiness",
    )
