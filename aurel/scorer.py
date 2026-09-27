"""Rigorous score calculation for Aurel."""

from __future__ import annotations

from collections.abc import Mapping

from aurel.config import DEFAULT_FILE_WEIGHTS, VALID_URL_POINTS, AurelConfig
from aurel.models import (
    CommunitySignal,
    Finding,
    IssueReadiness,
    ScoreCap,
    ScoreCategory,
    ScoreResult,
)

DEFAULT_ISSUE_READINESS = IssueReadiness(
    checked=False,
    beginner_issue_count=0,
    labels_found=(),
    confidence="Low",
    note="Issue readiness was not checked.",
)


def calculate_score(
    file_results: Mapping[str, bool] | tuple[CommunitySignal, ...],
    valid_url: bool = True,
    config: AurelConfig | None = None,
    findings: tuple[Finding, ...] = (),
    issue_readiness: IssueReadiness = DEFAULT_ISSUE_READINESS,
) -> ScoreResult:
    """Calculate the contributor-readiness score."""

    if isinstance(file_results, tuple):
        return _calculate_rigorous_score(
            file_results,
            findings=findings,
            issue_readiness=issue_readiness,
            valid_url=valid_url,
        )

    max_score, score = _score_legacy_files(file_results, valid_url, config)
    score = min(max_score, max(0, score - _legacy_finding_penalty(findings)))

    return ScoreResult(
        value=score,
        max_value=max_score,
        label=get_score_label(score, max_score),
        uncapped_value=score,
    )


def _calculate_rigorous_score(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
    issue_readiness: IssueReadiness,
    valid_url: bool,
) -> ScoreResult:
    if not valid_url:
        return ScoreResult(
            value=0,
            max_value=100,
            label=get_score_label(0),
            categories=(),
            caps=(ScoreCap(0, "Repository URL was not valid.", ()),),
            uncapped_value=0,
        )

    categories = (
        _documentation_category(signals, findings),
        _contributor_workflow_category(signals, findings),
        _setup_testing_category(signals, findings),
        _issue_readiness_category(issue_readiness),
        _community_safety_category(signals),
    )
    uncapped_value = sum(category.value for category in categories)
    caps = _score_caps(signals, findings, issue_readiness)
    strongest_cap = min((cap.limit for cap in caps), default=100)
    value = min(uncapped_value, strongest_cap, 100)

    return ScoreResult(
        value=value,
        max_value=100,
        label=get_score_label(value),
        categories=categories,
        caps=caps,
        uncapped_value=uncapped_value,
    )


def _documentation_category(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
) -> ScoreCategory:
    readme = _signal(signals, "readme")
    value = 25 if _satisfied(readme) else 0
    value -= _finding_penalties(
        findings,
        {
            "README looks very short": 8,
            "README appears to contain placeholder text": 10,
            "Usage example is not obvious from the README": 4,
        },
    )
    return _category("Documentation Quality", value, 25)


def _contributor_workflow_category(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
) -> ScoreCategory:
    contributing = _signal(signals, "contributing")
    value = 25 if _satisfied(contributing) else 0
    value -= _finding_penalties(
        findings,
        {
            "Beginner-friendly issue path not detected": 5,
            "Issue templates not detected": 3,
            "Pull request template not detected": 3,
        },
    )
    return _category("Contributor Workflow", value, 25)


def _setup_testing_category(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
) -> ScoreCategory:
    readme = _signal(signals, "readme")
    value = 20 if _satisfied(readme) else 5
    value -= _finding_penalties(
        findings,
        {
            "Setup path is not obvious from the README": 10,
            "Install command is not obvious from the README": 10,
            "Testing instructions are not obvious from the README": 8,
            "Test command is not obvious from the README": 8,
        },
    )
    return _category("Setup & Testing Clarity", value, 20)


def _issue_readiness_category(issue_readiness: IssueReadiness) -> ScoreCategory:
    if not issue_readiness.checked:
        return ScoreCategory("Issue Readiness", 8, 15)
    if issue_readiness.beginner_issue_count >= 3:
        value = 15
    elif issue_readiness.beginner_issue_count > 0:
        value = 12
    else:
        value = 4

    if issue_readiness.beginner_issue_count > 0:
        value -= min(issue_readiness.vague_issue_count * 2, 5)

    return ScoreCategory("Issue Readiness", max(value, 0), 15)


def _community_safety_category(signals: tuple[CommunitySignal, ...]) -> ScoreCategory:
    value = 0
    for key in ("license", "security", "code_of_conduct"):
        signal = _signal(signals, key)
        if _satisfied(signal):
            value += 5
    return ScoreCategory("Community & Safety", value, 15)


def _score_caps(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
    issue_readiness: IssueReadiness,
) -> tuple[ScoreCap, ...]:
    caps: list[ScoreCap] = []

    cap_by_missing_signal = {
        "readme": (65, "No project overview or docs entry point was detected."),
        "contributing": (75, "No contribution workflow guidance was detected."),
        "license": (82, "No license signal was detected."),
        "security": (89, "No security reporting guidance was detected."),
        "code_of_conduct": (89, "No community behavior expectations were detected."),
    }
    for signal in signals:
        if signal.present or not signal.required:
            continue
        limit, reason = cap_by_missing_signal.get(
            signal.key,
            (89, f"{signal.label} was not detected."),
        )
        caps.append(ScoreCap(limit=limit, reason=reason, evidence=signal.searched_paths))

    for finding in findings:
        if finding.score_cap is not None:
            caps.append(
                ScoreCap(
                    limit=finding.score_cap,
                    reason=finding.title,
                    evidence=finding.evidence,
                )
            )
        if finding.severity == "High":
            caps.append(
                ScoreCap(
                    limit=89,
                    reason=f"High-severity finding: {finding.title}",
                    evidence=finding.evidence,
                )
            )

    if issue_readiness.checked and issue_readiness.beginner_issue_count == 0:
        labels = issue_readiness.searched_labels or ("good first issue", "help wanted")
        caps.append(
            ScoreCap(
                limit=89,
                reason="No beginner-friendly open issues were detected.",
                evidence=labels,
            )
        )

    return tuple(caps)


def _score_legacy_files(
    file_results: Mapping[str, bool],
    valid_url: bool,
    config: AurelConfig | None,
) -> tuple[int, int]:
    file_weights = config.file_weights if config else DEFAULT_FILE_WEIGHTS
    max_score = VALID_URL_POINTS + sum(
        file_weights.get(filename, 0) for filename in file_results
    )
    score = VALID_URL_POINTS if valid_url else 0

    for filename, exists in file_results.items():
        if exists:
            score += file_weights.get(filename, 0)

    return max_score, score


def _legacy_finding_penalty(findings: tuple[Finding, ...]) -> int:
    penalties = {"High": 10, "Medium": 5, "Low": 2, "Info": 0}
    return sum(
        penalties.get(finding.severity, 0)
        for finding in findings
        if not finding.title.endswith("not detected")
    )


def _finding_penalties(findings: tuple[Finding, ...], penalties: dict[str, int]) -> int:
    return sum(penalties.get(finding.title, 0) for finding in findings)


def _category(name: str, value: int, max_value: int) -> ScoreCategory:
    return ScoreCategory(name=name, value=min(max(value, 0), max_value), max_value=max_value)


def _signal(signals: tuple[CommunitySignal, ...], key: str) -> CommunitySignal | None:
    for signal in signals:
        if signal.key == key:
            return signal
    return None


def _satisfied(signal: CommunitySignal | None) -> bool:
    return signal is None or signal.present or not signal.required


def get_score_label(score: int, max_score: int = 100) -> str:
    """Return the score label for a contributor-readiness score."""

    percentage = round((score / max_score) * 100) if max_score else 0

    if percentage >= 90:
        return "Excellent contributor readiness"
    if percentage >= 85:
        return "Very beginner-friendly"
    if percentage >= 70:
        return "Good for beginners"
    if percentage >= 50:
        return "Needs improvement"
    return "Difficult for beginners"
