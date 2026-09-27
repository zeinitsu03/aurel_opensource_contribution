"""Actionable contributor guidance for Aurel reports."""

from __future__ import annotations

from collections.abc import Mapping

from aurel.models import (
    BacklogItem,
    CommunitySignal,
    Finding,
    OnboardingPlan,
    ProfileResult,
    StarterPrKit,
)

SUGGESTION_PRIORITY = (
    "contributing",
    "readme",
    "license",
    "security",
    "code_of_conduct",
)

STARTER_PR_KITS = {
    "contributing": StarterPrKit(
        contribution=(
            "Add or improve contributor instructions with setup, branch naming, "
            "testing steps, and pull request guidelines."
        ),
        reason=(
            "A clear contributing guide helps new developers understand how to "
            "make their first change without guessing the workflow."
        ),
        pr_title="docs: add contributing guide for new contributors",
        commit_message="docs: add CONTRIBUTING guide",
        checklist=(
            "Read the README and note any setup commands already documented.",
            "Write short setup, testing, branch, and pull request sections.",
            "Keep instructions beginner-friendly and project-specific.",
        ),
        confidence="High",
    ),
    "readme": StarterPrKit(
        contribution=(
            "Add or improve the project overview or docs entry point so beginners "
            "can understand purpose, setup, usage, and support paths."
        ),
        reason=(
            "The README is usually the first file a beginner reads before "
            "deciding whether the project is approachable."
        ),
        pr_title="docs: add project README",
        commit_message="docs: add README",
        checklist=(
            "Summarize the project in plain language.",
            "Add installation and basic usage steps.",
            "Link to contribution and support information if available.",
        ),
        confidence="High",
    ),
    "license": StarterPrKit(
        contribution=(
            "Ask the maintainer which open-source license they prefer, then add "
            "the LICENSE file they choose."
        ),
        reason=(
            "A license tells contributors how the project can be used and shared, "
            "but the maintainer should choose it."
        ),
        pr_title="docs: add project license",
        commit_message="docs: add LICENSE",
        checklist=(
            "Open an issue or discussion asking which license is intended.",
            "Use the exact license text the maintainer confirms.",
            "Mention the license in the README if appropriate.",
        ),
        confidence="Medium",
    ),
    "security": StarterPrKit(
        contribution=(
            "Add a SECURITY.md file explaining how people should report security "
            "issues responsibly."
        ),
        reason=(
            "Security reporting instructions help contributors avoid exposing "
            "sensitive bugs in public issues."
        ),
        pr_title="docs: add security policy",
        commit_message="docs: add SECURITY policy",
        checklist=(
            "Check whether the project already lists a security contact.",
            "Write clear reporting steps and expected response guidance.",
            "Avoid promising response times the maintainers did not approve.",
        ),
        confidence="Medium",
    ),
    "code_of_conduct": StarterPrKit(
        contribution=(
            "Add a CODE_OF_CONDUCT.md file that sets basic expectations for "
            "respectful community participation."
        ),
        reason=(
            "A code of conduct helps beginners understand the project culture "
            "and what behavior is expected."
        ),
        pr_title="docs: add code of conduct",
        commit_message="docs: add code of conduct",
        checklist=(
            "Check whether the maintainers prefer a standard template.",
            "Keep the language clear and respectful.",
            "Add contact or enforcement details only with maintainer approval.",
        ),
        confidence="Medium",
    ),
}

DEFAULT_STARTER_PR_KIT = StarterPrKit(
    contribution=(
        "Improve setup or testing documentation for new contributors by adding "
        "one small clarification to the README or contributing guide."
    ),
    reason=(
        "Even healthy repositories can be easier for beginners when setup and "
        "testing steps are precise."
    ),
    pr_title="docs: clarify setup steps for new contributors",
    commit_message="docs: clarify contributor setup",
    checklist=(
        "Run the documented setup steps locally.",
        "Note one unclear or missing instruction.",
        "Open a small documentation PR with the clarification.",
    ),
    confidence="Low",
)

BACKLOG_ITEMS = {
    "readme": BacklogItem(
        title="Clarify project overview or docs entry point",
        description="Explain the project purpose, setup, usage, and support path.",
        suggested_issue_title="docs: improve project overview for new contributors",
        priority="High",
        audience="beginners, maintainers, programs",
        acceptance_criteria=(
            "The README or docs entry explains what the project does.",
            "Setup, usage, testing, and contribution links are easy to find.",
        ),
    ),
    "license": BacklogItem(
        title="Choose and add a license",
        description="Clarify how contributors and users may use the project.",
        suggested_issue_title="docs: add project license",
        priority="Medium",
        audience="maintainers, programs",
        acceptance_criteria=(
            "The license file uses maintainer-approved license text.",
            "The README or project metadata points to the license when appropriate.",
        ),
    ),
    "contributing": BacklogItem(
        title="Add contributor instructions",
        description="Document setup, testing, branch naming, and pull request steps.",
        suggested_issue_title="docs: add contributing guide",
        priority="High",
        audience="beginners, maintainers, programs",
        acceptance_criteria=(
            "The guide includes setup, test, branch, and pull request steps.",
            "The guide names the smallest safe first contribution path.",
        ),
    ),
    "security": BacklogItem(
        title="Add a security reporting policy",
        description="Tell users how to report sensitive issues responsibly.",
        suggested_issue_title="docs: add security policy",
        priority="Medium",
        audience="maintainers, programs",
        acceptance_criteria=(
            "The policy explains where to report sensitive issues.",
            "The policy avoids response-time promises maintainers did not approve.",
        ),
    ),
    "code_of_conduct": BacklogItem(
        title="Add community behavior expectations",
        description="Set expectations for respectful participation.",
        suggested_issue_title="docs: add code of conduct",
        priority="Medium",
        audience="beginners, maintainers, programs",
        acceptance_criteria=(
            "The file sets basic participation expectations.",
            "Contact or enforcement details are maintainer-approved.",
        ),
    ),
}


QUALITY_FINDING_KIT = StarterPrKit(
    contribution=(
        "Improve the existing documentation by clarifying the highest-impact "
        "finding in the report."
    ),
    reason=(
        "Aurel found an existing contributor-facing document, but the report "
        "shows one place where beginners may still get stuck."
    ),
    pr_title="docs: clarify contributor onboarding",
    commit_message="docs: clarify contributor onboarding",
    checklist=(
        "Read the finding and inspect the referenced file.",
        "Add one small, concrete clarification.",
        "Keep the PR focused on the documented contributor friction.",
    ),
    confidence="Medium",
)


def build_starter_pr_kit(
    file_results: Mapping[str, bool] | tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...] = (),
) -> StarterPrKit:
    """Return the highest-value first contribution suggestion."""

    signal_results = _signal_results(file_results)

    for signal in SUGGESTION_PRIORITY:
        if not signal_results.get(signal, False):
            return STARTER_PR_KITS[signal]

    if findings:
        finding = findings[0]
        return StarterPrKit(
            contribution=finding.recommendation,
            reason=finding.detail,
            pr_title=_pr_title_from_finding(finding),
            commit_message="docs: improve contributor guidance",
            checklist=QUALITY_FINDING_KIT.checklist,
            confidence=finding.confidence,
        )

    return DEFAULT_STARTER_PR_KIT


def build_improvement_backlog(
    file_results: Mapping[str, bool] | tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...] = (),
) -> tuple[BacklogItem, ...]:
    """Return actionable backlog items for missing contributor-readiness files."""

    signal_results = _signal_results(file_results)
    items = [
        BACKLOG_ITEMS[signal]
        for signal in SUGGESTION_PRIORITY
        if not signal_results.get(signal, False) and signal in BACKLOG_ITEMS
    ]

    if items:
        return tuple(items)

    if findings:
        return tuple(_backlog_item_from_finding(finding) for finding in findings)

    return (
        BacklogItem(
            title="Clarify setup and testing instructions",
            description=(
                "Run the documented setup locally and add one improvement that "
                "reduces confusion for first-time contributors."
            ),
            suggested_issue_title="docs: clarify setup and test instructions",
            priority="Low",
            audience="beginners, maintainers, programs",
            acceptance_criteria=(
                "At least one setup or test command is easier to follow.",
                "The change is small and verified against the current docs.",
            ),
        ),
    )


def build_onboarding_plan(
    signals: tuple[CommunitySignal, ...],
    findings: tuple[Finding, ...],
    starter_pr_kit: StarterPrKit,
    profile: ProfileResult,
) -> OnboardingPlan:
    """Build a short read/run/change path for a first-time contributor."""

    return OnboardingPlan(
        read_first=_read_first(signals, profile),
        run_first=_run_first(findings, profile),
        change_first=_change_first(findings, starter_pr_kit),
    )


def _signal_results(
    file_results: Mapping[str, bool] | tuple[CommunitySignal, ...],
) -> dict[str, bool]:
    if isinstance(file_results, tuple):
        return {signal.key: signal.present or not signal.required for signal in file_results}

    legacy_map = dict(file_results)
    return {
        "readme": legacy_map.get("readme", legacy_map.get("README.md", False)),
        "license": legacy_map.get("license", legacy_map.get("LICENSE", False)),
        "contributing": legacy_map.get(
            "contributing", legacy_map.get("CONTRIBUTING.md", False)
        ),
        "security": legacy_map.get("security", legacy_map.get("SECURITY.md", False)),
        "code_of_conduct": legacy_map.get(
            "code_of_conduct", legacy_map.get("CODE_OF_CONDUCT.md", False)
        ),
    }


def _read_first(
    signals: tuple[CommunitySignal, ...],
    profile: ProfileResult,
) -> tuple[str, ...]:
    readme = _signal(signals, "readme")
    contributing = _signal(signals, "contributing")
    items: list[str] = []

    if readme and readme.present and readme.matched_path:
        items.append(f"Read {readme.matched_path} for project purpose and setup context.")
    else:
        items.append("Find the main docs entry point or repository overview first.")

    if contributing and contributing.present and contributing.matched_path:
        items.append(
            f"Read {contributing.matched_path} for workflow and pull request expectations."
        )
    else:
        items.append("Check issues, docs, or maintainer notes for contribution workflow.")

    items.append(f"Use the detected profile as context: {profile.name}.")
    return tuple(items)


def _run_first(
    findings: tuple[Finding, ...],
    profile: ProfileResult,
) -> tuple[str, ...]:
    titles = {finding.title for finding in findings}
    items: list[str] = []

    if "Install command is not obvious from the README" in titles:
        items.append("Identify the dependency install command before editing code.")
    else:
        items.append("Run the documented install or setup command.")

    if "Local run command is not obvious from the README" in titles:
        items.append("Find the smallest local run command or document it if missing.")
    else:
        items.append("Run the smallest documented example or local start command.")

    if "Test command is not obvious from the README" in titles:
        items.append("Find the smallest verification command before opening a PR.")
    else:
        items.append("Run the documented test command after making a change.")

    if "Python" in profile.name:
        items.append(
            "For Python projects, prefer commands that work from a clean virtual environment."
        )

    return tuple(items)


def _change_first(
    findings: tuple[Finding, ...],
    starter_pr_kit: StarterPrKit,
) -> tuple[str, ...]:
    items = [starter_pr_kit.contribution]
    if findings:
        items.append(f"Start with this report finding: {findings[0].title}.")
    items.append("Keep the first pull request small, documented, and easy to review.")
    return tuple(items)


def _signal(signals: tuple[CommunitySignal, ...], key: str) -> CommunitySignal | None:
    for signal in signals:
        if signal.key == key:
            return signal
    return None


def _pr_title_from_finding(finding: Finding) -> str:
    title = finding.title.lower().replace("readme", "README")
    return f"docs: {title}"


def _backlog_item_from_finding(finding: Finding) -> BacklogItem:
    return BacklogItem(
        title=finding.title,
        description=finding.recommendation,
        suggested_issue_title=_pr_title_from_finding(finding),
        priority=finding.severity,
        audience="beginners, maintainers, programs",
        acceptance_criteria=(
            "The documented gap from the finding is addressed.",
            "The report evidence would no longer trigger the same finding.",
        ),
    )
