"""Repository profile detection for language-agnostic analysis."""

from __future__ import annotations

from collections.abc import Callable

from aurel.models import ProfileResult, Repository
from aurel.providers import remote_file_exists

FileExistsFunc = Callable[[Repository, str], bool]

PROFILE_SIGNALS = {
    "Python project": (
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "setup.cfg",
        "tox.ini",
        "noxfile.py",
    ),
    "JavaScript or TypeScript project": (
        "package.json",
        "tsconfig.json",
        "vite.config.js",
        "vite.config.ts",
        "next.config.js",
        "next.config.ts",
    ),
    "Java project": ("pom.xml", "build.gradle", "settings.gradle", "gradlew"),
    "Go project": ("go.mod", "go.sum"),
    "Rust project": ("Cargo.toml", "Cargo.lock"),
    "C or C++ project": ("CMakeLists.txt", "Makefile", "configure.ac"),
    "Documentation project": (
        "docs",
        "docs/index.md",
        "mkdocs.yml",
        "docusaurus.config.js",
        "sphinx",
        "readthedocs.yml",
        ".readthedocs.yaml",
    ),
    "GitHub community repository": (
        ".github",
        ".github/ISSUE_TEMPLATE",
        ".github/pull_request_template.md",
        ".github/workflows",
    ),
    "Template or starter repository": (
        "template.json",
        "cookiecutter.json",
        ".github/template-cleanup",
    ),
}


def detect_profile(
    repository: Repository,
    file_exists: FileExistsFunc | None = None,
    token: str | None = None,
) -> ProfileResult:
    """Detect the most likely repository profile from common file signals."""

    exists = file_exists or (
        lambda repo, path: remote_file_exists(repo, path, token=token)
    )
    scored_profiles: list[tuple[int, str, tuple[str, ...]]] = []

    for profile_name, paths in PROFILE_SIGNALS.items():
        evidence = tuple(path for path in paths if exists(repository, path))
        if evidence:
            scored_profiles.append((len(evidence), profile_name, evidence))

    if not scored_profiles:
        return ProfileResult(
            name="General repository",
            confidence="Low",
            evidence=(
                "No strong language or framework files were detected in common locations.",
            ),
        )

    scored_profiles.sort(key=lambda item: item[0], reverse=True)
    count, profile_name, evidence = scored_profiles[0]

    if count >= 3:
        confidence = "High"
    elif count == 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    return ProfileResult(name=profile_name, confidence=confidence, evidence=evidence)
