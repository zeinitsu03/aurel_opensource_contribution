"""Remote repository provider helpers."""

from __future__ import annotations

import base64
import binascii
from urllib.parse import quote

from aurel.models import IssueReadiness, Repository


class ProviderError(RuntimeError):
    """Raised when a remote provider request cannot be completed."""


USER_AGENT = "Aurel/1.0"
MAX_REMOTE_CONTENT_BYTES = 512_000
BEGINNER_LABELS = ("good first issue", "help wanted")
ISSUE_DETAIL_HINTS = (
    "acceptance",
    "command",
    "context",
    "docs",
    "expected",
    "steps",
    "reproduce",
    "setup",
    "files",
    "implementation",
    "test",
)


def remote_file_exists(
    repository: Repository,
    path: str,
    token: str | None = None,
    timeout: int = 10,
) -> bool:
    """Return True when a file exists in a supported remote repository."""

    if repository.provider == "github":
        return _github_file_exists(repository, path, token, timeout)
    if repository.provider == "gitlab":
        return _gitlab_file_exists(repository, path, token, timeout)
    if repository.provider == "bitbucket":
        return _bitbucket_file_exists(repository, path, token, timeout)

    raise ProviderError(f"Unsupported repository provider: {repository.provider}")


def remote_file_content(
    repository: Repository,
    path: str,
    token: str | None = None,
    timeout: int = 10,
) -> str | None:
    """Return decoded file content, or None when the file is not found."""

    if repository.provider == "github":
        return _github_file_content(repository, path, token, timeout)
    if repository.provider == "gitlab":
        return _gitlab_file_content(repository, path, token, timeout)
    if repository.provider == "bitbucket":
        return _bitbucket_file_content(repository, path, token, timeout)

    raise ProviderError(f"Unsupported repository provider: {repository.provider}")


def remote_repository_paths(
    repository: Repository,
    token: str | None = None,
    timeout: int = 10,
) -> frozenset[str] | None:
    """Return known repository paths when a provider supports efficient listing.

    ``None`` means the provider cannot list paths cheaply or listing was blocked,
    so callers should fall back to targeted file checks.
    """

    if repository.provider == "github":
        return _github_repository_paths(repository, token, timeout)
    return None


def remote_issue_readiness(
    repository: Repository,
    token: str | None = None,
    timeout: int = 10,
    beginner_labels: tuple[str, ...] | None = None,
) -> IssueReadiness:
    """Return beginner-friendly issue readiness for supported providers."""

    labels = tuple(beginner_labels or BEGINNER_LABELS)

    if repository.provider == "github":
        return _github_issue_readiness(repository, token, timeout, labels)
    if repository.provider == "gitlab":
        return _gitlab_issue_readiness(repository, token, timeout, labels)
    if repository.provider == "bitbucket":
        return _bitbucket_issue_readiness(repository, token, timeout, labels)

    return IssueReadiness(
        checked=False,
        beginner_issue_count=0,
        labels_found=(),
        confidence="Low",
        note="Beginner issue checks are not available for this provider.",
    )


def _github_file_exists(
    repository: Repository,
    path: str,
    token: str | None,
    timeout: int,
) -> bool:
    requests = _load_requests()
    encoded_path = quote(path, safe="/")
    url = (
        f"https://api.github.com/repos/{repository.owner}/{repository.name}"
        f"/contents/{encoded_path}"
    )

    response = _get(requests, url, headers=_github_headers(token), timeout=timeout)
    if response.status_code == 403:
        return _github_raw_file_exists(requests, repository, path, timeout)
    return _exists_from_status(response.status_code, "GitHub")


def _github_file_content(
    repository: Repository,
    path: str,
    token: str | None,
    timeout: int,
) -> str | None:
    requests = _load_requests()
    encoded_path = quote(path, safe="/")
    url = (
        f"https://api.github.com/repos/{repository.owner}/{repository.name}"
        f"/contents/{encoded_path}"
    )

    response = _get(requests, url, headers=_github_headers(token), timeout=timeout)
    if response.status_code == 404:
        return None
    if response.status_code == 403:
        return _github_raw_file_content(requests, repository, path, timeout)
    _raise_unexpected_status(response.status_code, "GitHub")

    payload = _json_payload(response, "GitHub")
    if payload.get("type") != "file" or "content" not in payload:
        return None
    if _too_large(payload.get("size")):
        return None

    encoded_content = payload["content"].replace("\n", "")
    return _decode_base64_content(encoded_content, "GitHub")


def _github_issue_readiness(
    repository: Repository,
    token: str | None,
    timeout: int,
    beginner_labels: tuple[str, ...],
) -> IssueReadiness:
    requests = _load_requests()
    headers = _github_headers(token)

    labels_found: list[str] = []
    issues_by_key: dict[str, dict] = {}

    for label in beginner_labels:
        url = f"https://api.github.com/repos/{repository.owner}/{repository.name}/issues"
        response = _get(
            requests,
            url,
            headers=headers,
            params={"state": "open", "labels": label, "per_page": 5},
            timeout=timeout,
        )
        if response.status_code == 404:
            continue
        if response.status_code == 403:
            return _skipped_issue_readiness(
                "GitHub",
                403,
                beginner_labels,
            )
        _raise_unexpected_status(response.status_code, "GitHub")
        issues = [
            item for item in _json_payload(response, "GitHub")
            if "pull_request" not in item
        ]
        if issues:
            labels_found.append(label)
            for item in issues:
                issues_by_key[_issue_key(item)] = item

    if issues_by_key:
        return _issue_readiness_from_issues(
            provider_name="GitHub",
            labels_found=tuple(labels_found),
            issues=tuple(issues_by_key.values()),
            confidence="High",
            searched_labels=beginner_labels,
        )

    return IssueReadiness(
        checked=True,
        beginner_issue_count=0,
        labels_found=(),
        confidence="Medium",
        note=(
            f"Aurel did not find open issues labeled {_label_phrase(beginner_labels)}. "
            "This can make it harder for beginners to choose a first task."
        ),
        searched_labels=beginner_labels,
    )


def _gitlab_issue_readiness(
    repository: Repository,
    token: str | None,
    timeout: int,
    beginner_labels: tuple[str, ...],
) -> IssueReadiness:
    requests = _load_requests()
    project_path = quote(repository.full_name, safe="")
    headers = _gitlab_headers(token)

    labels_found: list[str] = []
    issues_by_key: dict[str, dict] = {}
    for label in beginner_labels:
        url = f"https://gitlab.com/api/v4/projects/{project_path}/issues"
        response = _get(
            requests,
            url,
            headers=headers,
            params={"state": "opened", "labels": label, "per_page": 5},
            timeout=timeout,
        )
        if response.status_code == 404:
            continue
        _raise_unexpected_status(response.status_code, "GitLab")
        issues = _json_payload(response, "GitLab")
        if issues:
            labels_found.append(label)
            for item in issues:
                issues_by_key[_issue_key(item)] = item

    if issues_by_key:
        return _issue_readiness_from_issues(
            provider_name="GitLab",
            labels_found=tuple(labels_found),
            issues=tuple(issues_by_key.values()),
            confidence="High",
            searched_labels=beginner_labels,
        )

    return IssueReadiness(
        checked=True,
        beginner_issue_count=0,
        labels_found=(),
        confidence="Medium",
        note=(
            f"Aurel did not find open GitLab issues labeled {_label_phrase(beginner_labels)}."
        ),
        searched_labels=beginner_labels,
    )


def _bitbucket_issue_readiness(
    repository: Repository,
    token: str | None,
    timeout: int,
    beginner_labels: tuple[str, ...],
) -> IssueReadiness:
    requests = _load_requests()
    url = (
        f"https://api.bitbucket.org/2.0/repositories/{repository.owner}/"
        f"{repository.name}/issues"
    )
    headers = _bitbucket_headers(token)

    response = _get(
        requests,
        url,
        headers=headers,
        params={"state": "open", "pagelen": 10},
        timeout=timeout,
    )
    if response.status_code == 404:
        return IssueReadiness(
            checked=False,
            beginner_issue_count=0,
            labels_found=(),
            confidence="Low",
            note="Bitbucket issue data was not available for this repository.",
        )
    _raise_unexpected_status(response.status_code, "Bitbucket")
    payload = _json_payload(response, "Bitbucket")
    issues: list[dict] = []
    labels_found: list[str] = []
    for item in payload.get("values", ()):
        matched_labels = _beginner_keywords_in_text(_issue_text(item), beginner_labels)
        if not matched_labels:
            continue
        issues.append(item)
        for label in matched_labels:
            if label not in labels_found:
                labels_found.append(label)

    if issues:
        return _issue_readiness_from_issues(
            provider_name="Bitbucket",
            labels_found=tuple(f"{label} keyword" for label in labels_found),
            issues=tuple(issues),
            confidence="Medium",
            searched_labels=beginner_labels,
        )

    return IssueReadiness(
        checked=True,
        beginner_issue_count=0,
        labels_found=(),
        confidence="Low",
        note=(
            "Aurel checked Bitbucket open issue text for beginner-friendly keywords, "
            "but did not find obvious first-issue candidates."
        ),
        searched_labels=beginner_labels,
    )


def _gitlab_file_exists(
    repository: Repository,
    path: str,
    token: str | None,
    timeout: int,
) -> bool:
    requests = _load_requests()
    project_path = quote(repository.full_name, safe="")
    headers = _gitlab_headers(token)
    default_branch = _gitlab_default_branch(requests, project_path, headers, timeout)
    if default_branch is None:
        return False

    file_path = quote(path, safe="")
    file_url = (
        f"https://gitlab.com/api/v4/projects/{project_path}/repository/files/"
        f"{file_path}"
    )
    response = _get(
        requests,
        file_url,
        headers=headers,
        params={"ref": default_branch},
        timeout=timeout,
    )
    return _exists_from_status(response.status_code, "GitLab")


def _gitlab_file_content(
    repository: Repository,
    path: str,
    token: str | None,
    timeout: int,
) -> str | None:
    requests = _load_requests()
    project_path = quote(repository.full_name, safe="")
    headers = _gitlab_headers(token)

    default_branch = _gitlab_default_branch(requests, project_path, headers, timeout)
    if default_branch is None:
        return None

    file_path = quote(path, safe="")
    file_url = (
        f"https://gitlab.com/api/v4/projects/{project_path}/repository/files/"
        f"{file_path}"
    )
    response = _get(
        requests,
        file_url,
        headers=headers,
        params={"ref": default_branch},
        timeout=timeout,
    )
    if response.status_code == 404:
        return None
    _raise_unexpected_status(response.status_code, "GitLab")

    payload = _json_payload(response, "GitLab")
    if _too_large(payload.get("size")):
        return None
    encoded_content = payload.get("content")
    if not encoded_content:
        return None
    return _decode_base64_content(encoded_content, "GitLab")


def _bitbucket_file_exists(
    repository: Repository,
    path: str,
    token: str | None,
    timeout: int,
) -> bool:
    requests = _load_requests()
    encoded_path = quote(path, safe="/")
    url = (
        f"https://api.bitbucket.org/2.0/repositories/{repository.owner}/"
        f"{repository.name}/src/HEAD/{encoded_path}"
    )

    response = _get(requests, url, headers=_bitbucket_headers(token), timeout=timeout)
    return _exists_from_status(response.status_code, "Bitbucket")


def _bitbucket_file_content(
    repository: Repository,
    path: str,
    token: str | None,
    timeout: int,
) -> str | None:
    requests = _load_requests()
    encoded_path = quote(path, safe="/")
    url = (
        f"https://api.bitbucket.org/2.0/repositories/{repository.owner}/"
        f"{repository.name}/src/HEAD/{encoded_path}"
    )

    response = _get(
        requests,
        url,
        headers=_bitbucket_headers(token),
        timeout=timeout,
        stream=True,
    )
    if response.status_code == 404:
        return None
    _raise_unexpected_status(response.status_code, "Bitbucket")
    return _limited_response_text(response)


def _exists_from_status(status_code: int, provider_name: str) -> bool:
    if status_code == 200:
        return True
    if status_code == 404:
        return False
    if status_code in {401, 403}:
        raise ProviderError(
            f"{provider_name} returned {status_code}. Check token access or rate limits."
        )
    raise ProviderError(f"{provider_name} returned unexpected status {status_code}.")


def _raise_unexpected_status(status_code: int, provider_name: str) -> None:
    if status_code == 200:
        return
    if status_code in {401, 403}:
        raise ProviderError(
            f"{provider_name} returned {status_code}. Check token access or rate limits."
        )
    raise ProviderError(f"{provider_name} returned unexpected status {status_code}.")


def _github_repository_paths(
    repository: Repository,
    token: str | None,
    timeout: int,
) -> frozenset[str] | None:
    requests = _load_requests()
    headers = _github_headers(token)
    repository_url = f"https://api.github.com/repos/{repository.owner}/{repository.name}"
    repository_response = _get(requests, repository_url, headers=headers, timeout=timeout)
    if repository_response.status_code == 404:
        return frozenset()
    if repository_response.status_code in {401, 403}:
        return None
    _raise_unexpected_status(repository_response.status_code, "GitHub")

    default_branch = _json_payload(repository_response, "GitHub").get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        return None

    encoded_branch = quote(default_branch, safe="")
    tree_url = (
        f"https://api.github.com/repos/{repository.owner}/{repository.name}"
        f"/git/trees/{encoded_branch}"
    )
    tree_response = _get(
        requests,
        tree_url,
        headers=headers,
        params={"recursive": "1"},
        timeout=timeout,
    )
    if tree_response.status_code in {404, 409}:
        return frozenset()
    if tree_response.status_code in {401, 403}:
        return None
    _raise_unexpected_status(tree_response.status_code, "GitHub")

    payload = _json_payload(tree_response, "GitHub")
    tree = payload.get("tree")
    if not isinstance(tree, list):
        return None

    paths: set[str] = set()
    for item in tree:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if isinstance(path, str) and path:
            paths.add(path)
    return frozenset(paths)


def _github_raw_file_exists(
    requests,
    repository: Repository,
    path: str,
    timeout: int,
) -> bool:
    response = _get(
        requests,
        _github_raw_url(repository, path),
        headers=_plain_headers(),
        timeout=timeout,
        stream=True,
        allow_redirects=True,
    )
    try:
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        raise _raw_fallback_error(response.status_code)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _github_raw_file_content(
    requests,
    repository: Repository,
    path: str,
    timeout: int,
) -> str | None:
    response = _get(
        requests,
        _github_raw_url(repository, path),
        headers=_plain_headers(),
        timeout=timeout,
        stream=True,
        allow_redirects=True,
    )
    if response.status_code != 200:
        close = getattr(response, "close", None)
        if callable(close):
            close()
        if response.status_code == 404:
            return None
        raise _raw_fallback_error(response.status_code)
    return _limited_response_text(response)


def _raw_fallback_error(status_code: int) -> ProviderError:
    """Fail loudly so a blocked fallback is never reported as a missing file."""

    return ProviderError(
        f"GitHub API returned 403 and the raw file fallback returned {status_code}. "
        "This usually means a rate limit or a network proxy is blocking GitHub; "
        "set GITHUB_TOKEN or pass --github-token and try again."
    )


def _github_raw_url(repository: Repository, path: str) -> str:
    encoded_path = quote(path, safe="/")
    return (
        f"https://github.com/{repository.owner}/{repository.name}"
        f"/raw/HEAD/{encoded_path}"
    )


def _github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _plain_headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


def _gitlab_headers(token: str | None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["PRIVATE-TOKEN"] = token
    return headers


def _bitbucket_headers(token: str | None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gitlab_default_branch(
    requests,
    project_path: str,
    headers: dict[str, str],
    timeout: int,
):
    project_url = f"https://gitlab.com/api/v4/projects/{project_path}"
    project_response = _get(requests, project_url, headers=headers, timeout=timeout)
    if project_response.status_code == 404:
        return None
    _raise_unexpected_status(project_response.status_code, "GitLab")
    default_branch = _json_payload(project_response, "GitLab").get("default_branch")
    if not default_branch:
        raise ProviderError("GitLab API response did not include a default branch.")
    return default_branch


def _load_requests():
    try:
        import requests
    except ImportError as exc:
        raise ProviderError(
            "The requests package is required. Install dependencies first."
        ) from exc
    return requests


def _get(requests, url: str, **kwargs):
    kwargs.setdefault("allow_redirects", False)
    timeout = kwargs.pop("timeout", 10)
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise ProviderError(f"Could not reach remote provider: {exc}") from exc


def _json_payload(response, provider_name: str):
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(f"{provider_name} returned invalid JSON.") from exc


def _decode_base64_content(encoded_content: str, provider_name: str) -> str:
    try:
        normalized_content = "".join(encoded_content.split())
        decoded = base64.b64decode(normalized_content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProviderError(f"{provider_name} returned invalid file content.") from exc
    return decoded.decode("utf-8", errors="replace")


def _too_large(size: object) -> bool:
    return isinstance(size, int) and size > MAX_REMOTE_CONTENT_BYTES


def _content_length_too_large(response) -> bool:
    raw_length = getattr(response, "headers", {}).get("Content-Length")
    if raw_length is None:
        return False
    try:
        return int(raw_length) > MAX_REMOTE_CONTENT_BYTES
    except ValueError:
        return False


def _limited_response_text(response) -> str | None:
    if _content_length_too_large(response):
        return None

    iter_content = getattr(response, "iter_content", None)
    if not callable(iter_content):
        text = getattr(response, "text", "")
        return text if len(text.encode("utf-8")) <= MAX_REMOTE_CONTENT_BYTES else None

    content = bytearray()
    try:
        for chunk in iter_content(chunk_size=65_536):
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > MAX_REMOTE_CONTENT_BYTES:
                return None
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()

    encoding = getattr(response, "encoding", None) or "utf-8"
    return bytes(content).decode(encoding, errors="replace")


def _issue_readiness_from_issues(
    provider_name: str,
    labels_found: tuple[str, ...],
    issues: tuple[dict, ...],
    confidence: str,
    searched_labels: tuple[str, ...] | None = None,
) -> IssueReadiness:
    vague_count = sum(1 for item in issues if _issue_looks_vague(item))
    note = (
        f"Aurel found {provider_name} issues with beginner-friendly signals. Counts "
        "are capped by the small API page size used for fast analysis."
    )
    if vague_count:
        note += " Some sampled issues may need clearer context or acceptance criteria."

    return IssueReadiness(
        checked=True,
        beginner_issue_count=len(issues),
        labels_found=labels_found,
        confidence=confidence,
        note=note,
        vague_issue_count=vague_count,
        quality_notes=_issue_quality_notes(issues),
        searched_labels=searched_labels or labels_found,
    )


def _skipped_issue_readiness(
    provider_name: str,
    status_code: int,
    searched_labels: tuple[str, ...],
) -> IssueReadiness:
    return IssueReadiness(
        checked=False,
        beginner_issue_count=0,
        labels_found=(),
        confidence="Low",
        note=(
            f"{provider_name} issue readiness skipped because the provider returned "
            f"{status_code}. Public API rate limits or token permissions may block "
            "issue checks; set GITHUB_TOKEN or pass --github-token when analyzing "
            "GitHub repositories."
        ),
        searched_labels=searched_labels,
    )


def _issue_key(issue: dict) -> str:
    for key in ("html_url", "web_url", "links", "id", "iid", "number"):
        value = issue.get(key)
        if isinstance(value, dict):
            html = value.get("html", {})
            href = html.get("href") if isinstance(html, dict) else None
            if href:
                return str(href)
        if value:
            return str(value)
    return str(issue.get("title", "issue"))


def _issue_looks_vague(issue: dict) -> bool:
    text = _issue_text(issue)
    words = [word for word in text.split() if word.strip()]
    detail_hits = sum(1 for hint in ISSUE_DETAIL_HINTS if hint in text)
    if len(words) < 12:
        return True
    if len(words) >= 60 or detail_hits >= 2:
        return False
    return not (len(words) >= 20 and detail_hits == 1)


def _issue_quality_notes(issues: tuple[dict, ...]) -> tuple[str, ...]:
    notes: list[str] = []
    for issue in issues:
        if not _issue_looks_vague(issue):
            continue
        title = str(issue.get("title", "untitled issue")).strip()
        notes.append(f"Thin beginner issue detail: {title[:80]}")
    return tuple(notes[:5])


def _issue_text(issue: dict) -> str:
    title = str(issue.get("title", ""))
    body = issue.get("body") or issue.get("description") or ""
    content = issue.get("content")
    if isinstance(content, dict):
        body = body or content.get("raw") or content.get("html") or ""
    return f"{title}\n{body}".lower()


def _beginner_keywords_in_text(
    text: str,
    beginner_labels: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(label for label in beginner_labels if label.lower() in text)


def _label_phrase(beginner_labels: tuple[str, ...]) -> str:
    return " or ".join(f"'{label}'" for label in beginner_labels)
