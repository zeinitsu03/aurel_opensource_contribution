from aurel import providers
from aurel.analyzer import analyze_repository
from aurel.config import AurelConfig
from aurel.models import Repository


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {}

    def json(self):
        return self._payload


class FakeRequests:
    class RequestException(Exception):
        pass

    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "gitlab.com/api/v4/projects/" in url:
            return FakeResponse(404)
        return FakeResponse(404)


def test_github_token_is_not_sent_to_gitlab(monkeypatch):
    fake_requests = FakeRequests()
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    analyze_repository(
        Repository(provider="gitlab", owner="group", name="project"),
        AurelConfig(),
        token="fake-github-token",
        file_content=lambda repo, path: None,
    )

    assert fake_requests.calls
    assert all(
        "PRIVATE-TOKEN" not in call[1]["headers"]
        for call in fake_requests.calls
        if "gitlab.com" in call[0]
    )


def test_github_token_is_not_sent_to_bitbucket(monkeypatch):
    fake_requests = FakeRequests()
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    analyze_repository(
        Repository(provider="bitbucket", owner="team", name="project"),
        AurelConfig(),
        token="fake-github-token",
        file_content=lambda repo, path: None,
    )

    assert fake_requests.calls
    assert all(
        "Authorization" not in call[1]["headers"]
        for call in fake_requests.calls
        if "bitbucket.org" in call[0]
    )


def test_github_token_is_sent_to_github(monkeypatch):
    fake_requests = FakeRequests()
    monkeypatch.setattr(providers, "_load_requests", lambda: fake_requests)

    analyze_repository(
        Repository(provider="github", owner="owner", name="repo"),
        AurelConfig(),
        token="fake-github-token",
        file_content=lambda repo, path: None,
    )

    assert any(
        call[1]["headers"].get("Authorization") == "Bearer fake-github-token"
        for call in fake_requests.calls
        if "api.github.com" in call[0]
    )
