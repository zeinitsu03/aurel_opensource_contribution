"""High-level repository analysis orchestration."""

from __future__ import annotations

from collections.abc import Callable

from aurel.advisor import build_recommendations
from aurel.checks import analyze_community_signals
from aurel.config import AurelConfig
from aurel.guidance import (
    build_improvement_backlog,
    build_onboarding_plan,
    build_starter_pr_kit,
)
from aurel.models import (
    AnalysisResult,
    CommunitySignal,
    Finding,
    IssueReadiness,
    ProfileResult,
    Repository,
    WorkflowReadiness,
)
from aurel.profiles import detect_profile
from aurel.providers import (
    ProviderError,
    remote_file_content,
    remote_file_exists,
    remote_issue_readiness,
    remote_repository_paths,
)
from aurel.scorer import calculate_score
from aurel.workflow import analyze_workflow_readiness

FileExistsFunc = Callable[[Repository, str], bool]
FileContentFunc = Callable[[Repository, str], str | None]
IssueReadinessFunc = Callable[[Repository], IssueReadiness]

COMMAND_HINTS = {
    "python": {
        "install": (
            "python -m pip install",
            "pip install",
            "uv sync",
            "poetry install",
            "pipenv install",
        ),
        "run": ("python -m", "python ", "uv run", "poetry run"),
        "test": ("python -m pytest", "pytest", "tox", "nox", "unittest"),
        "lint": ("ruff", "flake8", "pylint", "black", "mypy"),
        "build": ("python -m build", "pip wheel", "build ."),
    },
    "javascript": {
        "install": ("npm install", "npm ci", "pnpm install", "yarn install", "bun install"),
        "run": ("npm run dev", "npm start", "pnpm dev", "yarn dev", "bun run"),
        "test": ("npm test", "npm run test", "pnpm test", "yarn test", "bun test"),
        "lint": ("npm run lint", "pnpm lint", "yarn lint", "eslint"),
        "build": ("npm run build", "pnpm build", "yarn build", "vite build"),
    },
    "java": {
        "install": ("mvn install", "gradle build", "./gradlew build"),
        "run": ("mvn spring-boot:run", "gradle run", "./gradlew run", "java -jar"),
        "test": ("mvn test", "gradle test", "./gradlew test"),
        "lint": ("checkstyle", "spotbugs", "pmd"),
        "build": ("mvn package", "mvn build", "gradle build", "./gradlew build"),
    },
    "go": {
        "install": ("go mod download", "go install"),
        "run": ("go run",),
        "test": ("go test",),
        "lint": ("gofmt", "go vet", "golangci-lint"),
        "build": ("go build",),
    },
    "rust": {
        "install": ("rustup", "cargo fetch"),
        "run": ("cargo run",),
        "test": ("cargo test",),
        "lint": ("cargo clippy", "cargo fmt"),
        "build": ("cargo build",),
    },
    "c": {
        "install": ("cmake", "make"),
        "run": ("./", "make run"),
        "test": ("ctest", "make test"),
        "lint": ("clang-format", "clang-tidy", "cppcheck"),
        "build": ("cmake --build", "make", "ninja"),
    },
    "docs": {
        "install": ("pip install", "npm install", "pnpm install"),
        "run": ("mkdocs serve", "sphinx-autobuild", "npm run docs"),
        "test": ("linkcheck", "markdownlint", "vale"),
        "lint": ("markdownlint", "vale"),
        "build": ("mkdocs build", "sphinx-build", "npm run build", "make docs"),
    },
    "general": {
        "install": ("install", "setup", "bootstrap"),
        "run": ("run", "start", "serve"),
        "test": ("test", "check", "verify"),
        "lint": ("lint", "format"),
        "build": ("build", "compile"),
    },
}


def analyze_repository(
    repository: Repository,
    config: AurelConfig,
    token: str | None = None,
    file_exists: FileExistsFunc | None = None,
    file_content: FileContentFunc | None = None,
    issue_loader: IssueReadinessFunc | None = None,
) -> AnalysisResult:
    """Run Aurel's context-aware analysis pipeline."""

    provider_token = _token_for_repository(repository, token)
    exists = _cached_file_exists(file_exists, provider_token)
    content = _cached_file_content(file_content, provider_token)

    profile = detect_profile(repository, file_exists=exists)
    workflow_readiness = analyze_workflow_readiness(repository, file_exists=exists)
    community_signals = analyze_community_signals(
        repository,
        config,
        file_exists=exists,
    )
    findings = build_findings(
        repository,
        profile,
        community_signals,
        config=config,
        file_content=content,
    )
    issue_readiness = _load_issue_readiness(
        repository,
        issue_loader,
        provider_token,
        config.beginner_labels,
    )
    findings = (
        *findings,
        *build_workflow_findings(workflow_readiness),
        *build_issue_findings(issue_readiness),
    )
    score = calculate_score(
        community_signals,
        findings=findings,
        issue_readiness=issue_readiness,
        valid_url=True,
    )
    recommendations = build_recommendations(
        community_signals,
        findings,
        issue_readiness,
        score,
    )
    starter_pr_kit = build_starter_pr_kit(community_signals, findings)
    backlog = build_improvement_backlog(community_signals, findings)
    onboarding_plan = build_onboarding_plan(
        community_signals,
        findings,
        starter_pr_kit,
        profile,
    )

    return AnalysisResult(
        repository=repository,
        profile=profile,
        community_signals=community_signals,
        findings=findings,
        issue_readiness=issue_readiness,
        workflow_readiness=workflow_readiness,
        score=score,
        recommendations=recommendations,
        starter_pr_kit=starter_pr_kit,
        backlog=backlog,
        onboarding_plan=onboarding_plan,
    )


def _token_for_repository(repository: Repository, token: str | None) -> str | None:
    if repository.provider == "github":
        return token
    return None


def _cached_file_exists(
    file_exists: FileExistsFunc | None,
    token: str | None,
) -> FileExistsFunc:
    source = file_exists or _remote_file_exists_source(token)
    cache: dict[tuple[str, str, str, str], bool] = {}

    def exists(repo: Repository, path: str) -> bool:
        key = (repo.provider, repo.owner, repo.name, path)
        if key not in cache:
            cache[key] = source(repo, path)
        return cache[key]

    return exists


def _remote_file_exists_source(token: str | None) -> FileExistsFunc:
    path_sets: dict[tuple[str, str, str], frozenset[str] | None] = {}

    def source(repo: Repository, path: str) -> bool:
        key = (repo.provider, repo.owner, repo.name)
        if key not in path_sets:
            path_sets[key] = remote_repository_paths(repo, token=token)

        paths = path_sets[key]
        if paths is not None:
            return path in paths

        return remote_file_exists(repo, path, token=token)

    return source


def _cached_file_content(
    file_content: FileContentFunc | None,
    token: str | None,
) -> FileContentFunc:
    source = file_content or (
        lambda repo, path: remote_file_content(repo, path, token=token)
    )
    cache: dict[tuple[str, str, str, str], str | None] = {}

    def content(repo: Repository, path: str) -> str | None:
        key = (repo.provider, repo.owner, repo.name, path)
        if key not in cache:
            cache[key] = source(repo, path)
        return cache[key]

    return content


def _load_issue_readiness(
    repository: Repository,
    issue_loader: IssueReadinessFunc | None,
    token: str | None,
    beginner_labels: tuple[str, ...],
) -> IssueReadiness:
    loader = issue_loader or (
        lambda repo: remote_issue_readiness(
            repo,
            token=token,
            beginner_labels=beginner_labels,
        )
    )
    try:
        return loader(repository)
    except ProviderError as exc:
        return IssueReadiness(
            checked=False,
            beginner_issue_count=0,
            labels_found=(),
            confidence="Low",
            note=f"Issue readiness check skipped because the provider returned an error: {exc}",
        )


def build_findings(
    repository: Repository,
    profile: ProfileResult,
    community_signals: tuple[CommunitySignal, ...],
    config: AurelConfig | None = None,
    file_content: FileContentFunc | None = None,
    token: str | None = None,
) -> tuple[Finding, ...]:
    """Build evidence-backed findings from signals and content checks."""

    content_loader = file_content or (
        lambda repo, path: remote_file_content(repo, path, token=token)
    )
    findings: list[Finding] = []

    for signal in community_signals:
        if signal.present or not signal.required:
            continue
        findings.append(_missing_signal_finding(signal))

    readme_signal = _signal_by_key(community_signals, "readme")
    if readme_signal and readme_signal.present and readme_signal.matched_path:
        content = content_loader(repository, readme_signal.matched_path)
        findings.extend(_readme_quality_findings(profile, readme_signal, content, config))

    return tuple(findings)


def _missing_signal_finding(signal: CommunitySignal) -> Finding:
    score_caps = {
        "readme": 65,
        "contributing": 75,
        "license": 82,
        "security": 89,
        "code_of_conduct": 89,
    }
    return Finding(
        title=f"{signal.label} not detected",
        detail=(
            f"Aurel checked {', '.join(signal.searched_paths)} and did not find "
            f"this guidance. This is an improvement suggestion, not a verdict."
        ),
        recommendation=_missing_signal_recommendation(signal.key),
        severity="Medium" if signal.key in {"readme", "contributing"} else "Low",
        confidence=signal.confidence,
        evidence=signal.searched_paths,
        category=_category_for_signal(signal.key),
        score_cap=score_caps.get(signal.key, 89),
    )


def build_issue_findings(issue_readiness: IssueReadiness) -> tuple[Finding, ...]:
    """Return findings based on beginner-friendly issue availability."""

    if not issue_readiness.checked:
        return ()
    if issue_readiness.beginner_issue_count > 0:
        if issue_readiness.vague_issue_count >= issue_readiness.beginner_issue_count:
            return (
                Finding(
                    title="Beginner issue details look too thin",
                    detail=(
                        "Aurel found beginner-friendly issue labels, but the sampled "
                        "issues appear to lack enough description or acceptance detail."
                    ),
                    recommendation=(
                        "Add expected files, context, acceptance criteria, and setup "
                        "notes to beginner-friendly issues."
                    ),
                    severity="Low",
                    confidence=issue_readiness.confidence,
                    evidence=issue_readiness.quality_notes or issue_readiness.labels_found,
                    category="Issue Readiness",
                    score_cap=89,
                ),
            )
        return ()

    labels = issue_readiness.searched_labels or ("good first issue", "help wanted")
    return (
        Finding(
            title="Beginner-friendly issue path not detected",
            detail=(
                "Aurel did not find open issues with beginner-friendly labels "
                f"or keywords: {_label_phrase(labels)}. Beginners may struggle "
                "to choose a safe first task."
            ),
            recommendation=(
                "Label a few small, well-scoped issues with beginner-friendly labels "
                "and include enough context for a first-time contributor."
            ),
            severity="Medium",
            confidence=issue_readiness.confidence,
            evidence=labels,
            category="Issue Readiness",
            score_cap=89,
        ),
    )


def build_workflow_findings(
    workflow_readiness: WorkflowReadiness,
) -> tuple[Finding, ...]:
    """Return findings for missing contribution workflow templates."""

    findings: list[Finding] = []
    if not workflow_readiness.issue_template_found:
        findings.append(
            Finding(
                title="Issue templates not detected",
                detail=(
                    "Issue templates help maintainers receive bug reports and feature "
                    "requests with enough context for triage."
                ),
                recommendation=(
                    "Add issue templates for bug reports and feature requests with "
                    "context, reproduction steps, and expected behavior fields."
                ),
                severity="Low",
                confidence=workflow_readiness.confidence,
                evidence=workflow_readiness.searched_issue_template_paths,
                category="Contributor Workflow",
                score_cap=89,
            )
        )

    if not workflow_readiness.pull_request_template_found:
        findings.append(
            Finding(
                title="Pull request template not detected",
                detail=(
                    "A pull request template helps contributors explain what changed, "
                    "how they tested it, and what reviewers should check."
                ),
                recommendation=(
                    "Add a pull request template with summary, testing, related issue, "
                    "and checklist sections."
                ),
                severity="Low",
                confidence=workflow_readiness.confidence,
                evidence=workflow_readiness.searched_pull_request_template_paths,
                category="Contributor Workflow",
                score_cap=89,
            )
        )

    return tuple(findings)


def _missing_signal_recommendation(key: str) -> str:
    recommendations = {
        "readme": (
            "Add a project overview or point contributors to the main docs entry "
            "point with setup and usage guidance."
        ),
        "license": (
            "Clarify licensing or document why the repository does not accept "
            "external reuse or contributions."
        ),
        "contributing": (
            "Add contribution instructions covering setup, tests, branch naming, "
            "and pull request expectations."
        ),
        "security": (
            "Add responsible disclosure instructions or explain where security "
            "reports should go."
        ),
        "code_of_conduct": (
            "Add community behavior expectations if the project accepts external "
            "participation."
        ),
    }
    return recommendations.get(key, "Document this contributor-readiness signal.")


def _label_phrase(labels: tuple[str, ...]) -> str:
    return ", ".join(labels)


def _readme_quality_findings(
    profile: ProfileResult,
    signal: CommunitySignal,
    content: str | None,
    config: AurelConfig | None = None,
) -> tuple[Finding, ...]:
    if content is None:
        return ()

    normalized = content.lower()
    commands = _profile_command_hints(profile.name)
    required_commands = _required_commands_for_profile(profile.name, config)
    checked_commands = set(config.command_checks if config else COMMAND_HINTS["general"])
    checked_commands.update(required_commands)
    findings: list[Finding] = []

    if len(content.strip()) < 120:
        findings.append(
            Finding(
                title="README looks very short",
                detail=(
                    f"{signal.matched_path} exists, but it may not give beginners "
                    "enough context to evaluate the project."
                ),
                recommendation=(
                    "Add a short purpose statement, basic setup steps, usage example, "
                    "and where contributors should start."
                ),
                severity="Medium",
                confidence="Medium",
                evidence=(signal.matched_path or "README",),
                category="Documentation Quality",
                score_cap=84,
            )
        )

    placeholder_words = ("todo", "lorem ipsum", "coming soon", "under construction")
    if any(word in normalized for word in placeholder_words):
        findings.append(
            Finding(
                title="README appears to contain placeholder text",
                detail=(
                    "Placeholder wording can confuse contributors because it is "
                    "unclear which instructions are reliable."
                ),
                recommendation=(
                    "Replace placeholder text with concrete project purpose, setup, "
                    "usage, and contribution guidance."
                ),
                severity="Medium",
                confidence="High",
                evidence=(signal.matched_path or "README",),
                category="Documentation Quality",
                score_cap=79,
            )
        )

    has_setup_path = _contains_any(
        normalized,
        ("install", "setup", "quick start", "getting started"),
    )
    has_install_command = _has_command(normalized, commands["install"])
    has_run_command = _has_command(normalized, commands["run"])
    has_test_command = _has_command(normalized, commands["test"])
    has_lint_command = _has_command(normalized, commands["lint"])
    has_build_command = _has_command(normalized, commands["build"])

    if "install" in checked_commands and not has_setup_path and not has_install_command:
        findings.append(
            Finding(
                title="Setup path is not obvious from the README",
                detail=(
                    "Beginners usually need an installation or setup path before "
                    "they can make a safe first contribution."
                ),
                recommendation=_profile_setup_recommendation(profile.name),
                severity="Medium",
                confidence="Medium",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=80,
            )
        )
    elif "install" in checked_commands and not has_install_command:
        findings.append(
            Finding(
                title="Install command is not obvious from the README",
                detail=(
                    "The README mentions setup, but Aurel could not identify a "
                    "concrete dependency installation command for this ecosystem."
                ),
                recommendation=_profile_install_command_recommendation(profile.name),
                severity="Medium",
                confidence="Medium",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=80,
            )
        )

    if "run" in checked_commands and (
        not _contains_any(normalized, ("usage", "example", "run", "command"))
        and not has_run_command
    ):
        findings.append(
            Finding(
                title="Usage example is not obvious from the README",
                detail=(
                    "A small usage example helps beginners understand what the "
                    "project does before they inspect the code."
                ),
                recommendation="Add one minimal command, screenshot, or example workflow.",
                severity="Low",
                confidence="Medium",
                evidence=(signal.matched_path or "README",),
                category="Documentation Quality",
                score_cap=_command_score_cap("run", required_commands) or 88,
            )
        )
    elif "run" in checked_commands and not has_run_command:
        findings.append(
            Finding(
                title="Local run command is not obvious from the README",
                detail=(
                    "The README gives usage context, but it does not clearly show "
                    "the smallest command to run the project locally."
                ),
                recommendation=_profile_run_command_recommendation(profile.name),
                severity="Medium" if "run" in required_commands else "Low",
                confidence="Medium",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=_command_score_cap("run", required_commands),
            )
        )

    if "test" in checked_commands and (
        not _contains_any(normalized, ("test", "pytest", "npm test", "cargo test", "go test"))
        and not has_test_command
    ):
        findings.append(
            Finding(
                title="Testing instructions are not obvious from the README",
                detail=(
                    "A first-time contributor needs to know how to verify that a "
                    "small change did not break the project."
                ),
                recommendation=_profile_test_recommendation(profile.name),
                severity="Low",
                confidence="Medium",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=85,
            )
        )
    elif "test" in checked_commands and not has_test_command:
        findings.append(
            Finding(
                title="Test command is not obvious from the README",
                detail=(
                    "The README mentions testing or verification, but Aurel could "
                    "not identify the exact command contributors should run."
                ),
                recommendation=_profile_test_recommendation(profile.name),
                severity="Low",
                confidence="Medium",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=85,
            )
        )

    if "lint" in checked_commands and not has_lint_command:
        findings.append(
            Finding(
                title="Lint command is not obvious from the README",
                detail=(
                    "A lint or formatting command helps contributors make small "
                    "changes that match the project style."
                ),
                recommendation=_profile_lint_command_recommendation(profile.name),
                severity="Low" if "lint" in required_commands else "Info",
                confidence="Medium" if "lint" in required_commands else "Low",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=_command_score_cap("lint", required_commands),
            )
        )

    if "build" in checked_commands and not has_build_command:
        findings.append(
            Finding(
                title="Build command is not obvious from the README",
                detail=(
                    "A build command helps contributors verify packaging, docs, "
                    "or compiled assets before review."
                ),
                recommendation=_profile_build_command_recommendation(profile.name),
                severity="Low" if "build" in required_commands else "Info",
                confidence="Medium" if "build" in required_commands else "Low",
                evidence=(signal.matched_path or "README", profile.name),
                category="Setup & Testing Clarity",
                score_cap=_command_score_cap("build", required_commands),
            )
        )

    return tuple(findings)


def _required_commands_for_profile(
    profile_name: str,
    config: AurelConfig | None,
) -> set[str]:
    required = set(config.required_commands if config else ())
    normalized = profile_name.lower()

    if "python" in normalized:
        required.update(("install", "test"))
    elif "javascript" in normalized or "typescript" in normalized:
        required.update(("install", "run", "test", "build"))
    elif "java project" in normalized:
        required.update(("install", "test", "build"))
    elif "go project" in normalized or "rust" in normalized:
        required.update(("test", "build"))
    elif "c or c++" in normalized:
        required.update(("build", "test"))
    elif "documentation" in normalized:
        required.update(("run", "build"))

    return required


def _command_score_cap(command: str, required_commands: set[str]) -> int | None:
    if command not in required_commands:
        return None
    return {
        "install": 80,
        "run": 85,
        "test": 85,
        "lint": 89,
        "build": 88,
    }.get(command, 89)


def _profile_setup_recommendation(profile_name: str) -> str:
    if "Python" in profile_name:
        return "Document Python setup, dependency installation, and how to run the project."
    if "JavaScript" in profile_name:
        return "Document package manager setup and the command used to run the app or package."
    if "Java project" in profile_name:
        return "Document the build tool and the command used to compile or run the project."
    if "Go project" in profile_name:
        return "Document Go version expectations and the command used to build or run the project."
    if "Rust project" in profile_name:
        return "Document Rust toolchain expectations and the Cargo command to run the project."
    if "Documentation" in profile_name:
        return "Document how to preview or build the documentation locally."
    return "Document the setup path for the detected project type."


def _profile_install_command_recommendation(profile_name: str) -> str:
    if "Python" in profile_name:
        return (
            "Add the exact dependency install command, such as "
            "python -m pip install -r requirements.txt."
        )
    if "JavaScript" in profile_name:
        return (
            "Add the package manager install command, such as npm install, "
            "pnpm install, or yarn install."
        )
    if "Java project" in profile_name:
        return "Add the Maven or Gradle command that prepares dependencies."
    if "Go project" in profile_name:
        return "Add the go mod download or go install command if setup is needed."
    if "Rust project" in profile_name:
        return "Add the rustup or cargo command contributors should run before editing."
    if "Documentation" in profile_name:
        return "Add the command that installs documentation build dependencies."
    return "Add the exact dependency or setup command contributors should run."


def _profile_run_command_recommendation(profile_name: str) -> str:
    if "Python" in profile_name:
        return "Add the smallest python or python -m command that runs the project locally."
    if "JavaScript" in profile_name:
        return "Add the npm, pnpm, yarn, or bun command that starts the app or package."
    if "Java project" in profile_name:
        return "Add the Maven, Gradle, or java command that runs the project locally."
    if "Go project" in profile_name:
        return "Add the go run command contributors should use."
    if "Rust project" in profile_name:
        return "Add the cargo run command contributors should use."
    if "Documentation" in profile_name:
        return "Add the docs preview command contributors should use."
    return "Add the smallest local run command contributors should try first."


def _profile_test_recommendation(profile_name: str) -> str:
    if "Python" in profile_name:
        return "Add the pytest, unittest, tox, or project-specific test command."
    if "JavaScript" in profile_name:
        return "Add the npm, pnpm, yarn, or bun test command."
    if "Java project" in profile_name:
        return "Add the Maven or Gradle test command."
    if "Go project" in profile_name:
        return "Add the go test command contributors should run."
    if "Rust project" in profile_name:
        return "Add the cargo test command contributors should run."
    if "Documentation" in profile_name:
        return "Add the docs preview or link-check command if one exists."
    return "Add the smallest verification command contributors should run."


def _profile_lint_command_recommendation(profile_name: str) -> str:
    if "Python" in profile_name:
        return "Add the ruff, black, mypy, flake8, or project-specific lint command."
    if "JavaScript" in profile_name:
        return "Add the lint command from package scripts or the preferred formatter command."
    if "Go project" in profile_name:
        return "Add gofmt, go vet, or golangci-lint guidance."
    if "Rust project" in profile_name:
        return "Add cargo fmt or cargo clippy guidance."
    return "Add the formatting or lint command contributors should run."


def _profile_build_command_recommendation(profile_name: str) -> str:
    if "Python" in profile_name:
        return "Add the python -m build or package-specific build command if one exists."
    if "JavaScript" in profile_name:
        return "Add the npm, pnpm, yarn, or bun build command."
    if "Java project" in profile_name:
        return "Add the Maven or Gradle build command."
    if "Go project" in profile_name:
        return "Add the go build command contributors should run."
    if "Rust project" in profile_name:
        return "Add the cargo build command contributors should run."
    if "Documentation" in profile_name:
        return "Add the docs build command contributors should run."
    return "Add the build command contributors should run when the project has one."


def _signal_by_key(
    community_signals: tuple[CommunitySignal, ...],
    key: str,
) -> CommunitySignal | None:
    for signal in community_signals:
        if signal.key == key:
            return signal
    return None


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _profile_command_hints(profile_name: str) -> dict[str, tuple[str, ...]]:
    normalized = profile_name.lower()
    if "python" in normalized:
        return COMMAND_HINTS["python"]
    if "javascript" in normalized or "typescript" in normalized:
        return COMMAND_HINTS["javascript"]
    if "java project" in normalized:
        return COMMAND_HINTS["java"]
    if "go project" in normalized:
        return COMMAND_HINTS["go"]
    if "rust" in normalized:
        return COMMAND_HINTS["rust"]
    if "c or c++" in normalized:
        return COMMAND_HINTS["c"]
    if "documentation" in normalized:
        return COMMAND_HINTS["docs"]
    return COMMAND_HINTS["general"]


def _has_command(text: str, commands: tuple[str, ...]) -> bool:
    return any(command.lower() in text for command in commands)


def _category_for_signal(key: str) -> str:
    categories = {
        "readme": "Documentation Quality",
        "contributing": "Contributor Workflow",
        "license": "Community & Safety",
        "security": "Community & Safety",
        "code_of_conduct": "Community & Safety",
    }
    return categories.get(key, "Contributor Readiness")
