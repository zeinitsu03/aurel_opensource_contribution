"""Terminal and Markdown report formatting for Aurel."""

from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any

from aurel import __version__
from aurel.models import AnalysisResult


def analysis_to_dict(analysis: AnalysisResult) -> dict[str, Any]:
    """Return an automation-friendly representation of an analysis."""

    return {
        "schema_version": "1.0",
        "aurel_version": __version__,
        "repository": {
            "provider": analysis.repository.provider,
            "owner": analysis.repository.owner,
            "name": analysis.repository.name,
            "full_name": analysis.repository.full_name,
            "display_name": analysis.repository.display_name,
        },
        "profile": {
            "name": analysis.profile.name,
            "confidence": analysis.profile.confidence,
            "evidence": _evidence_items(analysis.profile.evidence),
        },
        "score": {
            "value": analysis.score.value,
            "max_value": analysis.score.max_value,
            "percentage": analysis.score.percentage,
            "label": analysis.score.label,
            "uncapped_value": analysis.score.uncapped_value,
            "applied_cap": _cap_to_dict(analysis.score.applied_cap),
            "categories": [
                {
                    "name": category.name,
                    "value": category.value,
                    "max_value": category.max_value,
                    "percentage": category.percentage,
                }
                for category in analysis.score.categories
            ],
            "caps": [_cap_to_dict(cap) for cap in analysis.score.caps],
        },
        "issue_readiness": {
            "checked": analysis.issue_readiness.checked,
            "beginner_issue_count": analysis.issue_readiness.beginner_issue_count,
            "labels_found": list(analysis.issue_readiness.labels_found),
            "searched_labels": list(analysis.issue_readiness.searched_labels),
            "confidence": analysis.issue_readiness.confidence,
            "note": analysis.issue_readiness.note,
            "vague_issue_count": analysis.issue_readiness.vague_issue_count,
            "quality_notes": list(analysis.issue_readiness.quality_notes),
        },
        "workflow_readiness": {
            "issue_template_found": analysis.workflow_readiness.issue_template_found,
            "pull_request_template_found": (
                analysis.workflow_readiness.pull_request_template_found
            ),
            "issue_template_path": analysis.workflow_readiness.issue_template_path,
            "pull_request_template_path": (
                analysis.workflow_readiness.pull_request_template_path
            ),
            "confidence": analysis.workflow_readiness.confidence,
            "note": analysis.workflow_readiness.note,
        },
        "signals": [
            {
                "key": signal.key,
                "label": signal.label,
                "present": signal.present,
                "required": signal.required,
                "weight": signal.weight,
                "matched_path": signal.matched_path,
                "searched_paths": _evidence_items(signal.searched_paths),
                "confidence": signal.confidence,
                "note": signal.note,
            }
            for signal in analysis.community_signals
        ],
        "findings": [_finding_to_dict(finding) for finding in analysis.findings],
        "recommendations": [
            _recommendation_to_dict(recommendation)
            for recommendation in analysis.recommendations
        ],
        "starter_pr_kit": {
            "contribution": analysis.starter_pr_kit.contribution,
            "reason": analysis.starter_pr_kit.reason,
            "pr_title": analysis.starter_pr_kit.pr_title,
            "commit_message": analysis.starter_pr_kit.commit_message,
            "checklist": list(analysis.starter_pr_kit.checklist),
            "confidence": analysis.starter_pr_kit.confidence,
        },
        "backlog": [
            {
                "id": _stable_id("backlog", item.title, item.suggested_issue_title),
                "title": item.title,
                "description": item.description,
                "suggested_issue_title": item.suggested_issue_title,
                "priority": item.priority,
                "audience": item.audience,
                "acceptance_criteria": list(item.acceptance_criteria),
            }
            for item in analysis.backlog
        ],
        "onboarding_plan": {
            "read_first": list(analysis.onboarding_plan.read_first),
            "run_first": list(analysis.onboarding_plan.run_first),
            "change_first": list(analysis.onboarding_plan.change_first),
        },
    }


def format_json_report(analysis: AnalysisResult) -> str:
    """Build a JSON report for automation and CI."""

    return json.dumps(analysis_to_dict(analysis), indent=2, sort_keys=True)


def format_html_report(analysis: AnalysisResult) -> str:
    """Build a lightweight standalone HTML report."""

    data = analysis_to_dict(analysis)
    score = data["score"]
    findings = data["findings"]
    recommendations = data["recommendations"]
    signals = data["signals"]

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>Aurel report: {html.escape(data['repository']['display_name'])}</title>",
            "<style>",
            (
                "body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;"
                "line-height:1.5;margin:2rem;max-width:1100px;color:#17202a}"
            ),
            "h1,h2{line-height:1.2} table{border-collapse:collapse;width:100%}",
            "th,td{border:1px solid #d8dee4;padding:.5rem;text-align:left}",
            ".score{font-size:2rem;font-weight:700}.muted{color:#57606a}",
            ".item{border:1px solid #d8dee4;border-radius:6px;padding:1rem;margin:1rem 0}",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Aurel Contributor Readiness Report</h1>",
            f"<p class=\"muted\">Repository: {html.escape(data['repository']['display_name'])}</p>",
            (
                f"<p class=\"score\">{score['value']}/{score['max_value']} "
                f"({score['percentage']}%)</p>"
            ),
            f"<p>Label: <strong>{html.escape(score['label'])}</strong></p>",
            (
                f"<p>Profile: <strong>{html.escape(data['profile']['name'])}</strong> "
                f"({html.escape(data['profile']['confidence'])} confidence)</p>"
            ),
            "<h2>Score Categories</h2>",
            _html_table(
                ("Category", "Score"),
                (
                    (
                        category["name"],
                        f"{category['value']}/{category['max_value']}",
                    )
                    for category in score["categories"]
                ),
            ),
            "<h2>Top Fixes To Reach 90</h2>",
            _html_items(
                (
                    recommendation["title"],
                    (
                        f"{recommendation['priority']}, "
                        f"+{recommendation['estimated_score_gain']}: "
                        f"{recommendation['action']}"
                    ),
                )
                for recommendation in recommendations
            ),
            "<h2>Contributor Signals</h2>",
            _html_table(
                ("Signal", "Status"),
                (
                    (
                        signal["label"],
                        "found" if signal["present"] else "not detected",
                    )
                    for signal in signals
                ),
            ),
            "<h2>Findings</h2>",
            _html_items(
                (
                    finding["title"],
                    f"{finding['severity']}: {finding['recommendation']}",
                )
                for finding in findings
            ),
            "<h2>Starter PR Kit</h2>",
            f"<p>{html.escape(data['starter_pr_kit']['contribution'])}</p>",
            (
                f"<p><strong>PR title:</strong> "
                f"{html.escape(data['starter_pr_kit']['pr_title'])}</p>"
            ),
            "</body>",
            "</html>",
        ]
    )


def format_report_comparison(
    previous_report: dict[str, Any],
    current_report: dict[str, Any],
) -> str:
    """Compare two JSON report dictionaries."""

    previous_score = _score_value(previous_report)
    current_score = _score_value(current_report)
    previous_findings = _items_by_id(previous_report.get("findings", []))
    current_findings = _items_by_id(current_report.get("findings", []))
    previous_recommendations = _items_by_id(previous_report.get("recommendations", []))
    current_recommendations = _items_by_id(current_report.get("recommendations", []))

    lines = ["Report Comparison:"]
    if previous_score is None or current_score is None:
        lines.append("- Score: unavailable in one of the reports")
    else:
        delta = current_score - previous_score
        sign = "+" if delta >= 0 else ""
        lines.append(f"- Score: {previous_score} -> {current_score} ({sign}{delta})")

    lines.extend(
        _comparison_lines(
            "Findings",
            previous_findings,
            current_findings,
        )
    )
    lines.extend(
        _comparison_lines(
            "Recommendations",
            previous_recommendations,
            current_recommendations,
        )
    )
    return "\n".join(lines)


def format_text_report(analysis: AnalysisResult) -> str:
    """Build a plain text report suitable for saving as a .txt document."""

    return format_terminal_report(analysis)


SUMMARY_TOP_FIXES = 3


def format_summary_report(analysis: AnalysisResult) -> str:
    """Build the short default terminal report: score, top fixes, first PR."""

    score = analysis.score
    lines = [
        f"Repository: {analysis.repository.display_name}",
        f"Profile: {analysis.profile.name} ({analysis.profile.confidence} confidence)",
        "",
        f"Score: {score.value}/{score.max_value} - {score.label}",
    ]
    if score.applied_cap:
        reason = score.applied_cap.reason.rstrip(".")
        lines.append(
            f"Biggest blocker: {reason} (score can't exceed {score.applied_cap.limit} "
            "until fixed)"
        )

    lines.extend(["", "Top fixes:"])
    shown = analysis.recommendations[:SUMMARY_TOP_FIXES]
    if shown:
        for index, item in enumerate(shown, start=1):
            lines.append(
                f"{index}. {item.title} (+{item.estimated_score_gain}, {item.priority} priority)"
            )
            lines.append(f"   {item.action}")
        hidden = len(analysis.recommendations) - len(shown)
        if hidden:
            lines.append(f"   ...and {hidden} more with --detailed")
    else:
        lines.append("- No priority fixes suggested")

    kit = analysis.starter_pr_kit
    lines.extend(
        [
            "",
            "Your first contribution:",
            f"- Change: {kit.contribution}",
            f"- Why: {kit.reason}",
            f"- PR title: {kit.pr_title}",
            f"- Commit message: {kit.commit_message}",
        ]
    )

    if not analysis.issue_readiness.checked:
        lines.extend(["", f"Note: {analysis.issue_readiness.note}"])

    lines.extend(
        [
            "",
            (
                "Run again with --detailed for findings, the onboarding path, backlog, "
                "and maintainer notes."
            ),
        ]
    )
    return "\n".join(lines)


def format_terminal_report(analysis: AnalysisResult) -> str:
    """Build the full terminal report for the CLI (shown with --detailed)."""

    lines = [
        f"Repository: {analysis.repository.display_name}",
        f"Detected Profile: {analysis.profile.name} ({analysis.profile.confidence} confidence)",
        "",
        (
            "Contributor Readiness Score: "
            f"{analysis.score.value}/{analysis.score.max_value} "
            f"({analysis.score.percentage}%)"
        ),
        f"Label: {analysis.score.label}",
    ]

    if (
        analysis.score.uncapped_value is not None
        and analysis.score.uncapped_value != analysis.score.value
    ):
        lines.append(f"Uncapped Score: {analysis.score.uncapped_value}/{analysis.score.max_value}")

    if analysis.score.applied_cap:
        lines.append(
            f"Applied Score Cap: {analysis.score.applied_cap.limit} "
            f"({analysis.score.applied_cap.reason})"
        )

    lines.extend(["", "Score Categories:"])
    if analysis.score.categories:
        lines.extend(
            f"- {category.name}: {category.value}/{category.max_value}"
            for category in analysis.score.categories
        )
    else:
        lines.append("- Category scoring is not available for this analysis")

    lines.extend(
        [
            "",
            "Issue Readiness:",
            (
                f"- Checked: {'yes' if analysis.issue_readiness.checked else 'no'}; "
                f"beginner-friendly issues found: "
                f"{analysis.issue_readiness.beginner_issue_count}; "
                f"thin sampled issues: {analysis.issue_readiness.vague_issue_count}; "
                f"confidence: {analysis.issue_readiness.confidence}"
            ),
            f"- {analysis.issue_readiness.note}",
            "",
            "Workflow Templates:",
            (
                "- Issue templates: "
                f"{_template_status(analysis.workflow_readiness.issue_template_path)}"
            ),
            (
                "- Pull request template: "
                f"{_template_status(analysis.workflow_readiness.pull_request_template_path)}"
            ),
            f"- {analysis.workflow_readiness.note}",
            "",
            "Top Fixes To Reach 90:",
        ]
    )

    if analysis.recommendations:
        lines.extend(
            (
                f"- [{item.priority}, +{item.estimated_score_gain}] {item.title}: "
                f"{item.action}"
            )
            for item in analysis.recommendations
        )
    else:
        lines.append("- No priority fixes suggested")

    lines.extend(["", "Newcomer Onboarding Path:", "Read First:"])
    lines.extend(f"- {item}" for item in analysis.onboarding_plan.read_first)
    lines.append("Run First:")
    lines.extend(f"- {item}" for item in analysis.onboarding_plan.run_first)
    lines.append("Change First:")
    lines.extend(f"- {item}" for item in analysis.onboarding_plan.change_first)

    lines.extend(
        [
            "",
            "Profile Evidence:",
        ]
    )

    lines.extend(f"+ {item}" for item in analysis.profile.evidence)
    lines.extend(["", "Contributor Signals:"])

    for signal in analysis.community_signals:
        marker = "+" if signal.present else "?"
        status = f"found at {signal.matched_path}" if signal.present else "not detected"
        requirement = "required" if signal.required else "optional"
        lines.append(f"{marker} {signal.label}: {status} ({requirement})")

    lines.extend(["", "Findings:"])

    if analysis.findings:
        for finding in analysis.findings:
            cap = f"; cap {finding.score_cap}" if finding.score_cap is not None else ""
            lines.append(
                f"- [{finding.severity}, {finding.confidence} confidence] "
                f"{finding.title}{cap}: {finding.recommendation}"
            )
    else:
        lines.append("- No contributor-readiness issues detected from configured checks")

    kit = analysis.starter_pr_kit
    lines.extend(
        [
            "",
            "Starter PR Kit:",
            f"Recommended First Contribution: {kit.contribution}",
            f"Why This Helps: {kit.reason}",
            f"Confidence: {kit.confidence}",
            "",
            "Beginner Checklist:",
        ]
    )

    lines.extend(f"- {item}" for item in kit.checklist)

    lines.extend(["", "Improvement Backlog:"])
    for item in analysis.backlog:
        lines.append(f"- [{item.priority}] {item.title}: {item.suggested_issue_title}")
        lines.extend(f"  - Acceptance: {criterion}" for criterion in item.acceptance_criteria)

    lines.extend(["", "Maintainer Guidance:"])
    lines.extend(f"- {item}" for item in _maintainer_guidance(analysis))
    lines.extend(["", "Program Organizer Notes:"])
    lines.extend(f"- {item}" for item in _program_organizer_notes(analysis))

    lines.extend(
        [
            "",
            f"Suggested PR Title: {kit.pr_title}",
            f"Suggested Commit Message: {kit.commit_message}",
        ]
    )

    return "\n".join(lines)


def format_markdown_report(analysis: AnalysisResult) -> str:
    """Build a Markdown report suitable for saving to a file."""

    kit = analysis.starter_pr_kit
    backlog_lines = [
        (
            f"- **{item.priority}: {item.title}**  \n"
            f"  Audience: {item.audience}  \n"
            f"  Suggested issue: `{item.suggested_issue_title}`  \n"
            f"  {item.description}"
            f"{_acceptance_criteria_markdown(item.acceptance_criteria)}"
        )
        for item in analysis.backlog
    ]
    checklist_lines = [f"- {item}" for item in kit.checklist]

    return "\n".join(
        [
            "# Aurel Contributor Readiness Report",
            "",
            f"Repository: `{analysis.repository.display_name}`",
            "",
            "## Detected Profile",
            "",
            f"**{analysis.profile.name}** ({analysis.profile.confidence} confidence)",
            "",
            "Evidence:",
            "",
            "\n".join(f"- `{item}`" for item in analysis.profile.evidence),
            "",
            "## Score",
            "",
            (
                f"**{analysis.score.value}/{analysis.score.max_value}** "
                f"({analysis.score.percentage}%)"
            ),
            "",
            f"Label: **{analysis.score.label}**",
            "",
            _score_cap_markdown(analysis),
            "",
            "## Score Categories",
            "",
            _score_category_rows(analysis),
            "",
            "## Issue Readiness",
            "",
            _issue_readiness_markdown(analysis),
            "",
            "## Workflow Templates",
            "",
            _workflow_readiness_markdown(analysis),
            "",
            "## Top Fixes To Reach 90",
            "",
            _recommendation_rows(analysis),
            "",
            "## Newcomer Onboarding Path",
            "",
            _onboarding_plan_markdown(analysis),
            "",
            "## Contributor Signals",
            "",
            _signal_rows(analysis),
            "",
            "## Findings",
            "",
            _finding_rows(analysis),
            "",
            "## Starter PR Kit",
            "",
            f"**Recommended first contribution:** {kit.contribution}",
            "",
            f"**Why this helps:** {kit.reason}",
            "",
            f"**Confidence:** {kit.confidence}",
            "",
            "### Beginner Checklist",
            "",
            "\n".join(checklist_lines),
            "",
            f"**Suggested PR title:** `{kit.pr_title}`",
            "",
            f"**Suggested commit message:** `{kit.commit_message}`",
            "",
            "## Improvement Backlog",
            "",
            "\n\n".join(backlog_lines),
            "",
            "## Maintainer Guidance",
            "",
            "\n".join(f"- {item}" for item in _maintainer_guidance(analysis)),
            "",
            "## Program Organizer Notes",
            "",
            "\n".join(f"- {item}" for item in _program_organizer_notes(analysis)),
            "",
        ]
    )


def _cap_to_dict(cap) -> dict[str, Any] | None:
    if cap is None:
        return None
    return {
        "limit": cap.limit,
        "reason": cap.reason,
        "evidence": _evidence_items(cap.evidence),
    }


def _evidence_items(evidence: tuple[str, ...]) -> list[dict[str, str]]:
    return [{"kind": _evidence_kind(item), "value": item} for item in evidence]


def _finding_to_dict(finding) -> dict[str, Any]:
    return {
        "id": _stable_id("finding", finding.category, finding.title, *finding.evidence),
        "title": finding.title,
        "detail": finding.detail,
        "recommendation": finding.recommendation,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "category": finding.category,
        "score_cap": finding.score_cap,
        "evidence": _evidence_items(finding.evidence),
    }


def _recommendation_to_dict(recommendation) -> dict[str, Any]:
    return {
        "id": _stable_id(
            "recommendation",
            recommendation.source,
            recommendation.title,
            *recommendation.evidence,
        ),
        "title": recommendation.title,
        "action": recommendation.action,
        "reason": recommendation.reason,
        "priority": recommendation.priority,
        "effort": recommendation.effort,
        "confidence": recommendation.confidence,
        "estimated_score_gain": recommendation.estimated_score_gain,
        "evidence": _evidence_items(recommendation.evidence),
        "source": recommendation.source,
        "score_cap": recommendation.score_cap,
    }


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "\0".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    words = re.sub(r"[^a-z0-9]+", "-", " ".join(parts).lower()).strip("-")
    slug = words[:40].strip("-") or prefix
    return f"{prefix}.{slug}.{digest}"


def _evidence_kind(value: str) -> str:
    if "/" in value or "\\" in value:
        return "path"
    if value in {"README", "LICENSE", "COPYING"}:
        return "path"
    if re.fullmatch(r"[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+", value):
        return "path"
    return "text"


def _html_table(headers: tuple[str, ...], rows) -> str:
    row_html = []
    for row in rows:
        row_html.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row)
            + "</tr>"
        )
    if not row_html:
        row_html.append(
            f"<tr><td colspan=\"{len(headers)}\">No rows available.</td></tr>"
        )
    return "\n".join(
        [
            "<table>",
            "<thead><tr>"
            + "".join(f"<th>{html.escape(header)}</th>" for header in headers)
            + "</tr></thead>",
            "<tbody>",
            *row_html,
            "</tbody>",
            "</table>",
        ]
    )


def _html_items(items) -> str:
    rows = [
        (
            "<div class=\"item\">"
            f"<strong>{html.escape(str(title))}</strong>"
            f"<p>{html.escape(str(body))}</p>"
            "</div>"
        )
        for title, body in items
    ]
    if not rows:
        return "<p>No items.</p>"
    return "\n".join(rows)


def _score_value(report: dict[str, Any]) -> int | None:
    score = report.get("score")
    if not isinstance(score, dict):
        return None
    value = score.get("value")
    return value if isinstance(value, int) else None


def _items_by_id(items: Any) -> dict[str, str]:
    if not isinstance(items, list):
        return {}
    result: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        title = item.get("title")
        if isinstance(item_id, str) and isinstance(title, str):
            result[item_id] = title
    return result


def _comparison_lines(
    label: str,
    previous_items: dict[str, str],
    current_items: dict[str, str],
) -> list[str]:
    added = sorted(set(current_items) - set(previous_items))
    resolved = sorted(set(previous_items) - set(current_items))
    lines = [
        (
            f"- {label}: {len(previous_items)} -> {len(current_items)} "
            f"({len(added)} new, {len(resolved)} resolved)"
        )
    ]
    for item_id in added[:3]:
        lines.append(f"  - New: {current_items[item_id]}")
    for item_id in resolved[:3]:
        lines.append(f"  - Resolved: {previous_items[item_id]}")
    return lines


def _score_category_rows(analysis: AnalysisResult) -> str:
    if not analysis.score.categories:
        return "- Category scoring is not available for this analysis."
    return "\n".join(
        f"- **{category.name}:** {category.value}/{category.max_value}"
        for category in analysis.score.categories
    )


def _issue_readiness_markdown(analysis: AnalysisResult) -> str:
    labels = ", ".join(analysis.issue_readiness.labels_found) or "none"
    searched = ", ".join(analysis.issue_readiness.searched_labels) or "default labels"
    return "\n".join(
        [
            f"- Checked: **{'yes' if analysis.issue_readiness.checked else 'no'}**",
            (
                "- Beginner-friendly issues found: "
                f"**{analysis.issue_readiness.beginner_issue_count}**"
            ),
            f"- Thin sampled issues: **{analysis.issue_readiness.vague_issue_count}**",
            f"- Labels found: {labels}",
            f"- Labels checked: {searched}",
            f"- Confidence: **{analysis.issue_readiness.confidence}**",
            f"- Note: {analysis.issue_readiness.note}",
        ]
    )


def _workflow_readiness_markdown(analysis: AnalysisResult) -> str:
    workflow = analysis.workflow_readiness
    return "\n".join(
        [
            f"- Issue templates: **{_template_status(workflow.issue_template_path)}**",
            (
                "- Pull request template: "
                f"**{_template_status(workflow.pull_request_template_path)}**"
            ),
            f"- Confidence: **{workflow.confidence}**",
            f"- Note: {workflow.note}",
        ]
    )


def _onboarding_plan_markdown(analysis: AnalysisResult) -> str:
    plan = analysis.onboarding_plan
    return "\n".join(
        [
            "### Read First",
            "",
            "\n".join(f"- {item}" for item in plan.read_first),
            "",
            "### Run First",
            "",
            "\n".join(f"- {item}" for item in plan.run_first),
            "",
            "### Change First",
            "",
            "\n".join(f"- {item}" for item in plan.change_first),
        ]
    )


def _signal_rows(analysis: AnalysisResult) -> str:
    rows = []
    for signal in analysis.community_signals:
        status = f"found at `{signal.matched_path}`" if signal.present else "not detected"
        requirement = "required" if signal.required else "optional"
        rows.append(
            f"- **{signal.label}:** {status} "
            f"({requirement}, {signal.confidence} confidence)  \n"
            f"  {signal.note}"
        )
    return "\n".join(rows)


def _recommendation_rows(analysis: AnalysisResult) -> str:
    if not analysis.recommendations:
        return "- No priority fixes suggested."

    rows = []
    for recommendation in analysis.recommendations:
        evidence = ", ".join(f"`{item}`" for item in recommendation.evidence)
        rows.append(
            f"- **{recommendation.priority}: {recommendation.title}** "
            f"(+{recommendation.estimated_score_gain}, "
            f"{recommendation.effort} effort, "
            f"{recommendation.confidence} confidence)  \n"
            f"  Action: {recommendation.action}  \n"
            f"  Why: {recommendation.reason}  \n"
            f"  Evidence: {evidence}"
        )
    return "\n\n".join(rows)


def _finding_rows(analysis: AnalysisResult) -> str:
    if not analysis.findings:
        return "- No contributor-readiness issues detected from configured checks."

    rows = []
    for finding in analysis.findings:
        evidence = ", ".join(f"`{item}`" for item in finding.evidence)
        cap_text = f"  \n  Score cap: {finding.score_cap}" if finding.score_cap else ""
        rows.append(
            f"- **{finding.severity}: {finding.title}** "
            f"({finding.confidence} confidence)  \n"
            f"  {finding.detail}  \n"
            f"  Recommendation: {finding.recommendation}  \n"
            f"  Category: {finding.category}{cap_text}  \n"
            f"  Evidence: {evidence}"
        )
    return "\n\n".join(rows)


def _score_cap_markdown(analysis: AnalysisResult) -> str:
    if not analysis.score.caps:
        return "No score caps were applied."

    applied = analysis.score.applied_cap
    lines = []
    if analysis.score.uncapped_value is not None:
        lines.append(f"Uncapped score: **{analysis.score.uncapped_value}/100**")
    if applied:
        lines.append(f"Applied cap: **{applied.limit}** because {applied.reason}")
    lines.append("")
    lines.append("All score caps:")
    lines.extend(f"- {cap.limit}: {cap.reason}" for cap in analysis.score.caps)
    return "\n".join(lines)


def _acceptance_criteria_markdown(criteria: tuple[str, ...]) -> str:
    if not criteria:
        return ""
    rows = "".join(f"\n  - Acceptance: {criterion}" for criterion in criteria)
    return rows


def _template_status(path: str | None) -> str:
    return f"found at {path}" if path else "not detected"


def _maintainer_guidance(analysis: AnalysisResult) -> tuple[str, ...]:
    titles = {finding.title for finding in analysis.findings}
    guidance: list[str] = []
    if "Issue templates not detected" in titles:
        guidance.append(
            "Add issue templates so bug reports and feature requests arrive "
            "with triage context."
        )
    if "Pull request template not detected" in titles:
        guidance.append(
            "Add a pull request template with summary, testing, and reviewer "
            "checklist fields."
        )
    if analysis.issue_readiness.checked and analysis.issue_readiness.beginner_issue_count == 0:
        guidance.append("Label a few small issues as good first issue or help wanted.")
    if analysis.issue_readiness.vague_issue_count:
        guidance.append(
            "Expand beginner issues with expected files, acceptance criteria, "
            "and setup notes."
        )
    if not guidance:
        guidance.append(
            "Keep templates, labels, and first-issue guidance current as workflows change."
        )
    return tuple(guidance)


def _program_organizer_notes(analysis: AnalysisResult) -> tuple[str, ...]:
    notes: list[str] = []
    if analysis.score.value < 70:
        notes.append(
            "Use this repository cautiously for cohorts until the high-priority "
            "readiness gaps are addressed."
        )
    else:
        notes.append("This repository has enough structure for guided contributor onboarding.")
    if not analysis.workflow_readiness.issue_template_found:
        notes.append(
            "Ask maintainers to add issue templates before routing many "
            "first-time contributors here."
        )
    if analysis.issue_readiness.beginner_issue_count < 3:
        notes.append(
            "For programs, prepare or request at least three scoped beginner "
            "issues before launch."
        )
    if analysis.issue_readiness.vague_issue_count:
        notes.append(
            "Review beginner issue descriptions before assigning them to students or cohorts."
        )
    return tuple(notes)
