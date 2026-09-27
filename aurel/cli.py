"""Command-line interface for Aurel."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from aurel import __version__
from aurel.analyzer import analyze_repository
from aurel.config import ConfigError, load_config
from aurel.parser import RepositoryUrlError, parse_repository_url
from aurel.providers import ProviderError
from aurel.report import (
    analysis_to_dict,
    format_html_report,
    format_json_report,
    format_markdown_report,
    format_report_comparison,
    format_summary_report,
    format_terminal_report,
    format_text_report,
)


def startup_banner() -> str:
    """Return the terminal banner shown for human CLI runs."""

    return "\n".join(
        [
            "    ___    __  ______  ________ ",
            "   /   |  / / / / __ \\/ ____/ / ",
            "  / /| | / / / / /_/ / __/ / /  ",
            " / ___ |/ /_/ / _, _/ /___/ /___",
            "/_/  |_|\\____/_/ |_/_____/_____/",
            "",
            f"AUREL v{__version__}",
            "Contributor Readiness CLI",
            "Analyze remote repositories for beginner contribution readiness.",
            "Profiles docs, workflow templates, issue quality, scoring, and first-PR guidance.",
            "Free deterministic core. No hosted AI or repository write access required.",
            "",
        ]
    )


QUICK_START = """\
Check whether a GitHub, GitLab, or Bitbucket repository is ready for
new contributors, and get a suggested first pull request.

Try it:
  aurel https://github.com/owner/repo

Useful options:
  --detailed              show the full report
  --output report.md      save a report (.md, .txt, .json, .html)
  --github-token TOKEN    avoid GitHub rate limits (or set GITHUB_TOKEN)

All options: aurel --help"""


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the Aurel argument parser."""

    parser = argparse.ArgumentParser(
        prog="aurel",
        description="Analyze whether a remote repository is ready for contributors.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  aurel start\n"
            "  aurel https://github.com/owner/repo\n"
            "  aurel https://github.com/owner/repo --detailed\n"
            "  aurel https://github.com/owner/repo --output report.txt"
        ),
    )
    parser.add_argument(
        "repository_url",
        nargs="?",
        help=(
            "GitHub, GitLab, or Bitbucket repository URL, for example "
            "https://github.com/owner/repo"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help=(
            "Show the full terminal report. By default the terminal shows a short "
            "summary; saved and non-terminal formats always include everything."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Write a report to this path. When --format is omitted, .txt, .json, "
            ".html, and .md extensions choose the matching output format."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("terminal", "text", "markdown", "json", "html"),
        help="Report format for stdout and --output. Defaults to terminal output.",
    )
    parser.add_argument(
        "--compare",
        help="Compare this run with a previous JSON report file.",
    )
    parser.add_argument(
        "--min-score",
        type=_score_threshold,
        help="Exit with code 3 if the contributor-readiness score is below this value.",
    )
    parser.add_argument(
        "--config",
        help="Path to an Aurel config file. Defaults to aurel.yml if present.",
    )
    parser.add_argument(
        "--github-token",
        default=os.getenv("GITHUB_TOKEN"),
        help="Optional GitHub token. Defaults to the GITHUB_TOKEN environment variable.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Aurel CLI."""

    args_list = sys.argv[1:] if argv is None else list(argv)
    if not args_list:
        print(startup_banner())
        print(QUICK_START)
        return 0
    if args_list[0].lower() == "start":
        if len(args_list) > 1:
            print("Error: 'aurel start' does not accept extra arguments.", file=sys.stderr)
            return 2
        print(startup_banner())
        print(QUICK_START)
        return 0

    arg_parser = build_arg_parser()
    args = arg_parser.parse_args(args_list)

    if not args.repository_url:
        arg_parser.error(
            "a repository URL is required, for example: aurel https://github.com/owner/repo"
        )

    try:
        config = load_config(args.config)
        repository = parse_repository_url(args.repository_url)
    except (ConfigError, RepositoryUrlError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        analysis = analyze_repository(
            repository,
            config,
            token=args.github_token,
        )
    except ProviderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    report_format = args.format or "terminal"
    print(_format_report(analysis, report_format, args.detailed))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_format = _output_format(args.format, output_path)
        output_path.write_text(
            _format_report(analysis, output_format, args.detailed),
            encoding="utf-8",
        )
        print(f"{output_format.title()} report written to {output_path}", file=sys.stderr)

    if args.compare:
        try:
            previous_report = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error: Could not read comparison report: {exc}", file=sys.stderr)
            return 2
        print()
        print(format_report_comparison(previous_report, analysis_to_dict(analysis)))

    if args.min_score is not None and analysis.score.value < args.min_score:
        print(
            (
                f"Error: Score {analysis.score.value} is below required minimum "
                f"{args.min_score}."
            ),
            file=sys.stderr,
        )
        return 3

    return 0


def _format_report(analysis, report_format: str, detailed: bool = False) -> str:
    if report_format == "terminal":
        if detailed:
            return format_terminal_report(analysis)
        return format_summary_report(analysis)
    if report_format == "text":
        return format_text_report(analysis)
    if report_format == "markdown":
        return format_markdown_report(analysis)
    if report_format == "json":
        return format_json_report(analysis)
    if report_format == "html":
        return format_html_report(analysis)
    raise ValueError(f"Unsupported report format: {report_format}")


def _output_format(report_format: str | None, output_path: Path) -> str:
    if report_format:
        return report_format

    formats_by_suffix = {
        ".txt": "text",
        ".text": "text",
        ".md": "markdown",
        ".markdown": "markdown",
        ".json": "json",
        ".html": "html",
        ".htm": "html",
    }
    return formats_by_suffix.get(output_path.suffix.lower(), "markdown")


def _score_threshold(value: str) -> int:
    try:
        score = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer from 0 to 100") from exc
    if score < 0 or score > 100:
        raise argparse.ArgumentTypeError("must be from 0 to 100")
    return score


if __name__ == "__main__":
    raise SystemExit(main())
