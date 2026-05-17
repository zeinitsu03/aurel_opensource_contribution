# AGENTS.md

This file helps future Codex sessions and contributors work on Aurel consistently.

## Project Goal

Aurel is a contributor-readiness CLI for beginners, maintainers, and open-source programs. It analyzes remote repositories and explains whether they are approachable for contribution.

The signature feature is the Starter PR Kit: a practical first contribution suggestion with a PR title, commit message, checklist, and confidence level. v0.8 includes a deterministic advisor that produces top fixes to reach 90+ with effort, confidence, evidence, estimated score gain, a newcomer onboarding path, workflow-template checks, issue-quality hints, and maintainer/program guidance. Transparent deterministic analysis is the default and must remain free to run.

## Repo Layout

- `aurel/`: CLI source code.
- `tests/`: pytest tests.
- `examples/`: sample reports and config examples.
- `.github/workflows/`: GitHub Actions CI.
- `.github/ISSUE_TEMPLATE/`: issue templates.
- `README.md`: user-facing overview and usage.
- `CONTRIBUTING.md`: contribution guide.
- `SECURITY.md`: responsible disclosure policy.
- `docs/ARCHITECTURE.md`: system flow and extension points.
- `docs/CI_USAGE.md`: CI score gates and automation examples.
- `docs/EXTENDING.md`: contributor-facing extension guide.
- `docs/REPORT_SCHEMA.md`: JSON output contract for automation.
- `docs/screenshots/`: reusable README and documentation visuals.
- `ROADMAP.md`: staged future work.

## Coding Rules

- Keep the code original and written from scratch.
- Keep functions small and readable for beginners.
- Prefer standard library tools when they are enough.
- Use `argparse` for the CLI.
- Keep remote provider calls isolated in `providers.py`.
- Keep config parsing in `config.py`.
- Keep repository profile detection in `profiles.py`.
- Keep issue and pull request template checks in `workflow.py`.
- Keep orchestration in `analyzer.py`.
- Keep report formatting in `report.py`.
- Keep score categories and caps in `scorer.py`.
- Keep suggestion ranking and advisor extension points in `advisor.py`.
- Do not make paid APIs, hosted AI services, or secrets required for core analysis.
- Keep GitHub tokens scoped to GitHub requests unless explicit provider-specific token support is added.
- Optional integrations must be additive, documented, and disabled by default.
- Avoid complex architecture until there is a clear need.

## Testing Rules

- Use pytest.
- Do not make tests depend on live remote API calls.
- Mock or fake file-existence checks in tests.
- Add tests when parser, scoring, config, profile detection, issue readiness, analyzer, advisor suggestions, or report behavior changes.
- Run `pytest` before committing.

## Originality Rules

- Do not copy code, scoring logic, report wording, or structure from existing repo health tools, OpenSSF Scorecard, Repolinter, or similar projects.
- It is fine to use official documentation and normal Python libraries.
- Keep Aurel focused on contributor readiness and practical next steps, not general repository scoring.
- Prefer transparent deterministic analysis first. Optional local/offline advisor adapters may be added later, but they must be explainable and must not become the core scoring authority.

## Commit Message Style

Use these prefixes:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` tests
- `ci:` GitHub Actions
- `chore:` setup or maintenance
- `refactor:` code cleanup

## Definition Of Done

A change is done when:

- The CLI still runs locally.
- Relevant tests are added or updated.
- `pytest` passes.
- Documentation is updated when behavior changes.
- Screenshots or sample report snippets are updated when user-facing output changes.
- The change stays within the current planned version scope.
