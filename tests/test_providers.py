import pytest

from aurel import providers
from aurel.models import Repository
from aurel.providers import (
    MAX_REMOTE_CONTENT_BYTES,
    ProviderError,
    remote_file_content,
    remote_file_exists,
    remote_issue_readiness,
    remote_repository_paths,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, chunks=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self._chunks = chunks
        self.headers = {}
        self.text = ""
        self.closed = False

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=1):
        if self._chunks is None:
            return
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeRequests:
    class RequestException(Exception):
        pass

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_gitlab_issue_readiness_checks_beginner_labels(monkeypatch):
    fake_requests = FakeRequests(
        [
            FakeResponse(
                200,
                [
                    {
                        "iid": 1,
                        "title": "Add docs example",
                        "description": (
                            "Update docs with setup notes, expected files, "
                            "test command, and acceptance criteria."
                        ),
                    }
                ],
            ),
            FakeResponse(200, []),
        ]
    )
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    readiness = remote_issue_readiness(
        Repository(provider="gitlab", owner="group", name="project")
    )

    assert readiness.checked is True
    assert readiness.beginner_issue_count == 1
    assert readiness.labels_found == ("good first issue",)
    assert readiness.vague_issue_count == 0
    assert all("PRIVATE-TOKEN" not in call[1]["headers"] for call in fake_requests.calls)


def test_github_issue_readiness_uses_custom_beginner_labels(monkeypatch):
    fake_requests = FakeRequests(
        [
            FakeResponse(
                200,
                [
                    {
                        "number": 7,
                        "title": "Starter task: improve setup docs",
                        "body": (
                            "Update the README with setup context, expected files, "
                            "test command, and acceptance criteria."
                        ),
                    }
                ],
            )
        ]
    )
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    readiness = remote_issue_readiness(
        Repository(provider="github", owner="owner", name="repo"),
        beginner_labels=("starter task",),
    )

    assert readiness.checked is True
    assert readiness.beginner_issue_count == 1
    assert readiness.labels_found == ("starter task",)
    assert readiness.searched_labels == ("starter task",)
    assert fake_requests.calls[0][1]["params"]["labels"] == "starter task"


def test_github_file_exists_falls_back_to_raw_when_api_is_forbidden(monkeypatch):
    fake_requests = FakeRequests(
        [
            FakeResponse(403),
            FakeResponse(200),
        ]
    )
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    exists = remote_file_exists(
        Repository(provider="github", owner="owner", name="repo"),
        "README.md",
    )

    assert exists is True
    assert fake_requests.calls[0][0] == (
        "https://api.github.com/repos/owner/repo/contents/README.md"
    )
    assert fake_requests.calls[1][0] == (
        "https://github.com/owner/repo/raw/HEAD/README.md"
    )
    assert fake_requests.calls[1][1]["allow_redirects"] is True
    assert fake_requests.calls[1][1]["stream"] is True


def test_github_file_exists_raw_404_means_missing(monkeypatch):
    fake_requests = FakeRequests([FakeResponse(403), FakeResponse(404)])
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    exists = remote_file_exists(
        Repository(provider="github", owner="owner", name="repo"),
        "README.md",
    )

    assert exists is False


@pytest.mark.parametrize("status_code", [403, 429, 500])
def test_github_file_exists_raises_when_raw_fallback_is_blocked(monkeypatch, status_code):
    fake_requests = FakeRequests([FakeResponse(403), FakeResponse(status_code)])
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    with pytest.raises(ProviderError, match="GITHUB_TOKEN"):
        remote_file_exists(
            Repository(provider="github", owner="owner", name="repo"),
            "README.md",
        )


def test_github_file_content_raises_when_raw_fallback_is_blocked(monkeypatch):
    blocked_response = FakeResponse(429)
    fake_requests = FakeRequests([FakeResponse(403), blocked_response])
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    with pytest.raises(ProviderError, match="429"):
        remote_file_content(
            Repository(provider="github", owner="owner", name="repo"),
            "README.md",
        )
    assert blocked_response.closed is True


def test_github_repository_paths_uses_default_branch_tree(monkeypatch):
    fake_requests = FakeRequests(
        [
            FakeResponse(200, {"default_branch": "main"}),
            FakeResponse(
                200,
                {
                    "tree": [
                        {"path": "README.md", "type": "blob"},
                        {"path": ".github/ISSUE_TEMPLATE", "type": "tree"},
                    ]
                },
            ),
        ]
    )
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    paths = remote_repository_paths(
        Repository(provider="github", owner="owner", name="repo")
    )

    assert paths == frozenset({"README.md", ".github/ISSUE_TEMPLATE"})
    assert fake_requests.calls[0][0] == "https://api.github.com/repos/owner/repo"
    assert fake_requests.calls[1][0] == (
        "https://api.github.com/repos/owner/repo/git/trees/main"
    )
    assert fake_requests.calls[1][1]["params"] == {"recursive": "1"}


def test_github_repository_paths_returns_none_when_listing_is_forbidden(monkeypatch):
    fake_requests = FakeRequests([FakeResponse(403)])
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    paths = remote_repository_paths(
        Repository(provider="github", owner="owner", name="repo")
    )

    assert paths is None


def test_github_file_content_falls_back_to_raw_when_api_is_forbidden(monkeypatch):
    fake_response = FakeResponse(200, chunks=[b"# Example\n\nSetup notes."])
    fake_requests = FakeRequests(
        [
            FakeResponse(403),
            fake_response,
        ]
    )
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    content = remote_file_content(
        Repository(provider="github", owner="owner", name="repo"),
        "docs/index.md",
    )

    assert content == "# Example\n\nSetup notes."
    assert fake_requests.calls[1][0] == (
        "https://github.com/owner/repo/raw/HEAD/docs/index.md"
    )
    assert fake_response.closed is True


def test_github_issue_readiness_403_is_nonfatal(monkeypatch):
    fake_requests = FakeRequests([FakeResponse(403)])
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    readiness = remote_issue_readiness(
        Repository(provider="github", owner="owner", name="repo")
    )

    assert readiness.checked is False
    assert readiness.beginner_issue_count == 0
    assert readiness.searched_labels == ("good first issue", "help wanted")
    assert "GitHub issue readiness skipped" in readiness.note


def test_bitbucket_issue_readiness_uses_keyword_scan(monkeypatch):
    fake_requests = FakeRequests(
        [
            FakeResponse(
                200,
                {
                    "values": [
                        {
                            "id": 1,
                            "title": "good first issue: improve docs",
                            "content": {
                                "raw": (
                                    "Add setup notes, expected files, test command, "
                                    "and acceptance criteria for contributors."
                                )
                            },
                        }
                    ]
                },
            )
        ]
    )
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    readiness = remote_issue_readiness(
        Repository(provider="bitbucket", owner="team", name="project")
    )

    assert readiness.checked is True
    assert readiness.beginner_issue_count == 1
    assert readiness.confidence == "Medium"
    assert readiness.labels_found == ("good first issue keyword",)


def test_bitbucket_file_content_streams_with_size_limit(monkeypatch):
    fake_response = FakeResponse(
        200,
        chunks=[b"a" * (MAX_REMOTE_CONTENT_BYTES + 1)],
    )
    fake_requests = FakeRequests([fake_response])
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    content = remote_file_content(
        Repository(provider="bitbucket", owner="team", name="project"),
        "README.md",
    )

    assert content is None
    assert fake_requests.calls[0][1]["stream"] is True
    assert fake_response.closed is True
