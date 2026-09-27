"""Shared data models for Aurel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Repository:
    """A parsed remote repository identifier."""

    provider: str
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        """Return the owner/name form used in reports."""

        return f"{self.owner}/{self.name}"

    @property
    def display_name(self) -> str:
        """Return a provider-qualified repository name."""

        return f"{self.provider}:{self.full_name}"


@dataclass(frozen=True)
class ScoreCategory:
    """A named part of the readiness score."""

    name: str
    value: int
    max_value: int

    @property
    def percentage(self) -> int:
        """Return the rounded percentage for this category."""

        if self.max_value == 0:
            return 0
        return round((self.value / self.max_value) * 100)


@dataclass(frozen=True)
class ScoreCap:
    """A maximum score caused by a significant readiness gap."""

    limit: int
    reason: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class ScoreResult:
    """A numeric readiness score and label."""

    value: int
    max_value: int
    label: str
    categories: tuple[ScoreCategory, ...] = ()
    caps: tuple[ScoreCap, ...] = ()
    uncapped_value: int | None = None

    @property
    def percentage(self) -> int:
        """Return the rounded percentage score."""

        if self.max_value == 0:
            return 0
        return round((self.value / self.max_value) * 100)

    @property
    def applied_cap(self) -> ScoreCap | None:
        """Return the strongest score cap, if any."""

        if not self.caps:
            return None
        return min(self.caps, key=lambda cap: cap.limit)


@dataclass(frozen=True)
class ProfileResult:
    """Detected repository type and evidence."""

    name: str
    confidence: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class CommunitySignal:
    """A flexible contributor-readiness signal."""

    key: str
    label: str
    present: bool
    required: bool
    weight: int
    matched_path: str | None
    searched_paths: tuple[str, ...]
    confidence: str
    note: str


@dataclass(frozen=True)
class Finding:
    """A concrete observation with evidence and a recommendation."""

    title: str
    detail: str
    recommendation: str
    severity: str
    confidence: str
    evidence: tuple[str, ...]
    category: str = "General"
    score_cap: int | None = None


@dataclass(frozen=True)
class IssueReadiness:
    """Beginner-friendly issue signal summary."""

    checked: bool
    beginner_issue_count: int
    labels_found: tuple[str, ...]
    confidence: str
    note: str
    vague_issue_count: int = 0
    quality_notes: tuple[str, ...] = ()
    searched_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowReadiness:
    """Contribution workflow templates detected in a repository."""

    issue_template_found: bool
    pull_request_template_found: bool
    issue_template_path: str | None
    pull_request_template_path: str | None
    searched_issue_template_paths: tuple[str, ...]
    searched_pull_request_template_paths: tuple[str, ...]
    confidence: str
    note: str


@dataclass(frozen=True)
class StarterPrKit:
    """A practical first contribution suggestion for a beginner."""

    contribution: str
    reason: str
    pr_title: str
    commit_message: str
    checklist: tuple[str, ...]
    confidence: str


@dataclass(frozen=True)
class BacklogItem:
    """An actionable improvement item for a maintainer or contributor."""

    title: str
    description: str
    suggested_issue_title: str
    priority: str
    audience: str
    acceptance_criteria: tuple[str, ...] = ()


@dataclass(frozen=True)
class OnboardingPlan:
    """A short path that tells a newcomer what to read, run, and change first."""

    read_first: tuple[str, ...]
    run_first: tuple[str, ...]
    change_first: tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    """A prioritized improvement suggestion with evidence."""

    title: str
    action: str
    reason: str
    priority: str
    effort: str
    confidence: str
    estimated_score_gain: int
    evidence: tuple[str, ...]
    source: str
    score_cap: int | None = None


@dataclass(frozen=True)
class AnalysisResult:
    """Complete analysis output used by terminal and Markdown reports."""

    repository: Repository
    profile: ProfileResult
    community_signals: tuple[CommunitySignal, ...]
    findings: tuple[Finding, ...]
    issue_readiness: IssueReadiness
    workflow_readiness: WorkflowReadiness
    score: ScoreResult
    recommendations: tuple[Recommendation, ...]
    starter_pr_kit: StarterPrKit
    backlog: tuple[BacklogItem, ...]
    onboarding_plan: OnboardingPlan

    @property
    def file_results(self) -> dict[str, bool]:
        """Return legacy signal booleans for older callers."""

        return {signal.key: signal.present for signal in self.community_signals}
