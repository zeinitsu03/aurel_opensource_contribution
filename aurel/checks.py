"""Community-file checks for remote repositories."""

from __future__ import annotations

from collections.abc import Callable

from aurel.config import DEFAULT_COMMUNITY_FILES, DEFAULT_SIGNAL_LABELS, AurelConfig
from aurel.models import CommunitySignal, Repository
from aurel.providers import remote_file_exists

COMMUNITY_FILES = DEFAULT_COMMUNITY_FILES

FileExistsFunc = Callable[[Repository, str], bool]


def check_community_files(
    repository: Repository,
    file_exists: FileExistsFunc | None = None,
    filenames: tuple[str, ...] | list[str] | None = None,
    token: str | None = None,
) -> dict[str, bool]:
    """Check whether important community files exist in a repository."""

    files_to_check = tuple(filenames or COMMUNITY_FILES)
    exists = file_exists or (
        lambda repo, path: remote_file_exists(repo, path, token=token)
    )

    return {filename: exists(repository, filename) for filename in files_to_check}


def analyze_community_signals(
    repository: Repository,
    config: AurelConfig,
    file_exists: FileExistsFunc | None = None,
    token: str | None = None,
) -> tuple[CommunitySignal, ...]:
    """Analyze flexible contributor-readiness signals.

    A signal can be satisfied by several equivalent locations. For example,
    the README signal can be satisfied by README.md, README.rst, docs/index.md,
    or another configured docs entry point.
    """

    exists = file_exists or (
        lambda repo, path: remote_file_exists(repo, path, token=token)
    )
    signals: list[CommunitySignal] = []

    for key, paths in config.signal_paths.items():
        searched_paths = _merge_paths(paths, _extra_paths_for_signal(key, config))
        matched_path = _first_existing_path(repository, searched_paths, exists)
        required = config.required_signals.get(key, True)
        present = matched_path is not None

        signals.append(
            CommunitySignal(
                key=key,
                label=DEFAULT_SIGNAL_LABELS.get(key, key.replace("_", " ").title()),
                present=present,
                required=required,
                weight=config.signal_weights.get(key, 0),
                matched_path=matched_path,
                searched_paths=searched_paths,
                confidence="High" if present else "Medium",
                note=_signal_note(key, present, required, matched_path),
            )
        )

    return tuple(signals)


def _first_existing_path(
    repository: Repository,
    paths: tuple[str, ...],
    exists: FileExistsFunc,
) -> str | None:
    for path in paths:
        if exists(repository, path):
            return path
    return None


def _extra_paths_for_signal(key: str, config: AurelConfig) -> tuple[str, ...]:
    if key == "readme":
        return config.documentation_paths
    return ()


def _merge_paths(primary: tuple[str, ...], extra: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for path in [*primary, *extra]:
        if path not in seen:
            seen.add(path)
            merged.append(path)
    return tuple(merged)


def _signal_note(
    key: str,
    present: bool,
    required: bool,
    matched_path: str | None,
) -> str:
    if present:
        return f"Detected at {matched_path}."
    if not required:
        return "Not detected, but this signal is optional for this configuration."
    return (
        "Not detected in common locations. This may be acceptable if the "
        "project documents the same guidance elsewhere."
    )
