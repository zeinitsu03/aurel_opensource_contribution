"""Contribution workflow template checks."""

from __future__ import annotations

from collections.abc import Callable

from aurel.models import Repository, WorkflowReadiness
from aurel.providers import remote_file_exists

FileExistsFunc = Callable[[Repository, str], bool]

ISSUE_TEMPLATE_PATHS = (
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE.md",
    "ISSUE_TEMPLATE.md",
    "docs/ISSUE_TEMPLATE.md",
    ".gitlab/issue_templates/Bug.md",
    ".gitlab/issue_templates/Feature.md",
    ".gitlab/issue_templates/bug.md",
    ".gitlab/issue_templates/feature.md",
)

PULL_REQUEST_TEMPLATE_PATHS = (
    ".github/pull_request_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "pull_request_template.md",
    "PULL_REQUEST_TEMPLATE.md",
    "docs/pull_request_template.md",
    ".gitlab/merge_request_templates/default.md",
    ".gitlab/merge_request_templates/Default.md",
    ".gitlab/merge_request_templates/merge_request.md",
)


def analyze_workflow_readiness(
    repository: Repository,
    file_exists: FileExistsFunc | None = None,
    token: str | None = None,
) -> WorkflowReadiness:
    """Check issue and pull request template readiness."""

    exists = file_exists or (
        lambda repo, path: remote_file_exists(repo, path, token=token)
    )
    issue_template = _first_existing_path(repository, ISSUE_TEMPLATE_PATHS, exists)
    pull_request_template = _first_existing_path(
        repository,
        PULL_REQUEST_TEMPLATE_PATHS,
        exists,
    )

    if issue_template and pull_request_template:
        confidence = "High"
        note = "Issue and pull request templates were detected."
    elif issue_template or pull_request_template:
        confidence = "Medium"
        note = "One contribution workflow template was detected, but the workflow is incomplete."
    else:
        confidence = "Medium"
        note = "Issue and pull request templates were not detected in common locations."

    return WorkflowReadiness(
        issue_template_found=issue_template is not None,
        pull_request_template_found=pull_request_template is not None,
        issue_template_path=issue_template,
        pull_request_template_path=pull_request_template,
        searched_issue_template_paths=ISSUE_TEMPLATE_PATHS,
        searched_pull_request_template_paths=PULL_REQUEST_TEMPLATE_PATHS,
        confidence=confidence,
        note=note,
    )


def _first_existing_path(
    repository: Repository,
    paths: tuple[str, ...],
    exists: FileExistsFunc,
) -> str | None:
    for path in paths:
        if exists(repository, path):
            return path
    return None
