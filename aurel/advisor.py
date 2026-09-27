"""Contributor-readiness recommendation engine.

The deterministic advisor is the default reliability layer. Future advisor
extensions can use the same input/output shape, but core scoring must stay
transparent, testable, and free to run.
"""

from __future__ import annotations

from typing import Protocol

from aurel.models import CommunitySignal, Finding, IssueReadiness, Recommendation, ScoreResult

TARGET_EXCELLENT_SCORE = 90
HIGH_SEVERITY_CAP = 89
BEGINNER_ISSUE_FINDING = "Beginner-friendly issue path not detected"
DEDICATED_RECOMMENDATION_FINDINGS = {
    "Project overview or docs entry point not detected",
    "License information not detected",
    "Contribution guide not detected",
    "Security reporting instructions not detected",
    "Community behavior expectations not detected",
    BEGINNER_ISSUE_FINDING,
}


class Advisor(Protocol):
    """Protocol for recommendation engines."""

    def recommend(
        self,
        signals: tuple[CommunitySignal, ...],
        findings: tuple[Finding, ...],
        issue_readiness: IssueReadiness,
        score: ScoreResult,
    ) -> tuple[Recommendation, ...]:
        """Return prioritized improvement suggestions."""


class DeterministicAdvisor:
    """Evidence-backed advisor that does not require an ML model."""

    def recommend(
        self,
        signals: tuple[CommunitySignal, ...],
        findings: tuple[Finding, ...],
        issue_readiness: IssueReadiness,
        score: ScoreResult,
    ) -> tuple[Recommendation, ...]:
        caps_by_finding = {finding.title: _effective_cap(finding) for finding in findings}
        recommendations: list[Recommendation] = []
        recommendations.extend(_missing_signal_recommendations(signals, caps_by_finding))
        recommendations.extend(_finding_recommendations(findings))
        recommendations.extend(_issue_recommendations(issue_readiness, caps_by_finding))

        if score.value >= TARGET_EXCELLENT_SCORE and not recommendations:
            return (
                Recommendation(
                    title="Keep contributor guidance current",
                    action=(
                        "Periodically verify setup, testing, and contribution "
                        "instructions against the current project workflow."
                    ),
                    reason=(
                        "Aurel did not find major readiness gaps. Maintenance keeps "
                        "the repository approachable as it evolves."
                    ),
                    priority="Low",
                    effort="Small",
                    confidence="Medium",
                    estimated_score_gain=0,
                    evidence=("score >= 90",),
                    source="deterministic-advisor",
                ),
            )

        return tuple(_top_ranked(_dedupe(recommendations), limit=5))


def build_recommendations(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
    issue_readiness: IssueReadiness,
    score: ScoreResult,
    advisor: Advisor | None = None,
) -> tuple[Recommendation, ...]:
    """Build top recommendations using the configured advisor."""

    engine = advisor or DeterministicAdvisor()
    return engine.recommend(signals, findings, issue_readiness, score)


def _missing_signal_recommendations(
    signals: tuple[CommunitySignal, ...],
    caps_by_finding: dict[str, int | None],
) -> tuple[Recommendation, ...]:
    recommendations: list[Recommendation] = []
    for signal in signals:
        if signal.present or not signal.required:
            continue
        recommendations.append(
            Recommendation(
                title=f"Add {signal.label.lower()}",
                action=_missing_signal_action(signal.key),
                reason=signal.note,
                priority="High" if signal.key in {"readme", "contributing"} else "Medium",
                effort="Medium" if signal.key in {"readme", "contributing"} else "Small",
                confidence=signal.confidence,
                estimated_score_gain=signal.weight,
                evidence=signal.searched_paths,
                source="missing-signal",
                score_cap=caps_by_finding.get(f"{signal.label} not detected"),
            )
        )
    return tuple(recommendations)


def _finding_recommendations(findings: tuple[Finding, ...]) -> tuple[Recommendation, ...]:
    recommendations: list[Recommendation] = []
    for finding in findings:
        if finding.title in DEDICATED_RECOMMENDATION_FINDINGS:
            continue
        recommendations.append(
            Recommendation(
                title=finding.title,
                action=finding.recommendation,
                reason=finding.detail,
                priority=finding.severity,
                effort=_effort_for_finding(finding),
                confidence=finding.confidence,
                estimated_score_gain=_estimated_gain_for_finding(finding),
                evidence=finding.evidence,
                source="finding",
                score_cap=_effective_cap(finding),
            )
        )
    return tuple(recommendations)


def _issue_recommendations(
    issue_readiness: IssueReadiness,
    caps_by_finding: dict[str, int | None],
) -> tuple[Recommendation, ...]:
    if not issue_readiness.checked or issue_readiness.beginner_issue_count > 0:
        return ()

    labels = issue_readiness.searched_labels or ("good first issue", "help wanted")
    label_text = ", ".join(f"'{label}'" for label in labels)
    return (
        Recommendation(
            title="Create beginner-friendly issue paths",
            action=(
                f"Label a few small, well-scoped issues with {label_text}, "
                "and include expected files, acceptance criteria, "
                "and setup notes."
            ),
            reason=issue_readiness.note,
            priority="Medium",
            effort="Small",
            confidence=issue_readiness.confidence,
            estimated_score_gain=11,
            evidence=labels,
            source="issue-readiness",
            score_cap=caps_by_finding.get(BEGINNER_ISSUE_FINDING),
        ),
    )


def _missing_signal_action(key: str) -> str:
    actions = {
        "readme": (
            "Add a discoverable README or docs entry point with project purpose, "
            "setup, usage, testing, and contribution links."
        ),
        "license": "Add or document license information approved by the maintainers.",
        "contributing": (
            "Add contributor instructions covering setup, tests, branch naming, "
            "review expectations, and first PR guidance."
        ),
        "security": "Add responsible disclosure instructions or a security contact path.",
        "code_of_conduct": (
            "Add community behavior expectations if the project accepts external contributors."
        ),
    }
    return actions.get(key, "Document this contributor-readiness signal.")


def _effective_cap(finding: Finding) -> int | None:
    """Return the strictest score cap this finding places on the score."""

    caps = [finding.score_cap] if finding.score_cap is not None else []
    if finding.severity == "High":
        caps.append(HIGH_SEVERITY_CAP)
    return min(caps, default=None)


def _effort_for_finding(finding: Finding) -> str:
    if "README" in finding.title or "Setup" in finding.title:
        return "Small"
    if finding.severity == "High":
        return "Medium"
    return "Small"


def _estimated_gain_for_finding(finding: Finding) -> int:
    gains = {
        "README looks very short": 8,
        "README appears to contain placeholder text": 10,
        "Setup path is not obvious from the README": 10,
        "Install command is not obvious from the README": 10,
        "Usage example is not obvious from the README": 4,
        "Local run command is not obvious from the README": 4,
        "Testing instructions are not obvious from the README": 8,
        "Test command is not obvious from the README": 8,
        "Lint command is not obvious from the README": 3,
        "Build command is not obvious from the README": 3,
        "Issue templates not detected": 4,
        "Pull request template not detected": 4,
        "Beginner issue details look too thin": 6,
        "Beginner-friendly issue path not detected": 11,
    }
    if finding.title.endswith("not detected"):
        return 10
    return gains.get(finding.title, 5)


def _dedupe(recommendations: list[Recommendation]) -> tuple[Recommendation, ...]:
    seen: set[str] = set()
    unique: list[Recommendation] = []
    for recommendation in recommendations:
        key = recommendation.title.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(recommendation)
    return tuple(unique)


def _top_ranked(
    recommendations: tuple[Recommendation, ...],
    limit: int,
) -> tuple[Recommendation, ...]:
    """Rank fixes so the one lifting the strictest score cap comes first.

    The score can never exceed its strictest cap, so fixing anything else first
    would not move the score. Priority and estimated gain break ties.
    """

    priority_rank = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}
    no_cap = 101
    return tuple(
        sorted(
            recommendations,
            key=lambda item: (
                item.score_cap if item.score_cap is not None else no_cap,
                priority_rank.get(item.priority, 4),
                -item.estimated_score_gain,
                item.effort,
                item.title,
            ),
        )[:limit]
    )
