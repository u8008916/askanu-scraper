import requests
import pytest

from askanu_scraper.common.fetcher import FetchError, HttpFetcher


class FakeResponse:
    def __init__(self, text: str, error: Exception | None = None) -> None:
        self.text = text
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error


class FakeSession:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.headers = {}

    def get(self, url: str, timeout: int):
        self.calls += 1
        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def make_fetcher(
    outcomes: list[object],
    monkeypatch,
) -> tuple[HttpFetcher, FakeSession]:
    fetcher = HttpFetcher(timeout=1)
    session = FakeSession(outcomes)
    fetcher._session = session
    monkeypatch.setattr(fetcher, "_reset_session", lambda: None)
    return fetcher, session


def test_valid_response_succeeds_without_retry(monkeypatch):
    monkeypatch.setattr("askanu_scraper.common.fetcher.time.sleep", lambda _: None)

    fetcher, session = make_fetcher(
        [FakeResponse("<html>ok</html>")],
        monkeypatch,
    )

    assert fetcher.fetch("https://example.com") == "<html>ok</html>"
    assert session.calls == 1


def test_empty_response_retries_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.time.sleep",
        lambda delay: sleeps.append(delay),
    )

    fetcher, session = make_fetcher(
        [
            FakeResponse(""),
            FakeResponse("<html>ok</html>"),
        ],
        monkeypatch,
    )

    assert fetcher.fetch("https://example.com") == "<html>ok</html>"
    assert session.calls == 2
    assert sleeps == [1.0]


def test_request_exception_retries_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.time.sleep",
        lambda delay: sleeps.append(delay),
    )

    fetcher, session = make_fetcher(
        [
            requests.ConnectionError("temporary failure"),
            FakeResponse("<html>ok</html>"),
        ],
        monkeypatch,
    )

    assert fetcher.fetch("https://example.com") == "<html>ok</html>"
    assert session.calls == 2
    assert sleeps == [1.0]


def test_empty_response_exhausts_retry_budget(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.time.sleep",
        lambda delay: sleeps.append(delay),
    )

    fetcher, session = make_fetcher(
        [
            FakeResponse(""),
            FakeResponse("   "),
            FakeResponse(""),
        ],
        monkeypatch,
    )

    with pytest.raises(FetchError, match="empty response body"):
        fetcher.fetch("https://example.com")

    assert session.calls == 3
    assert sleeps == [1.0, 2.0]


def test_request_exception_exhausts_retry_budget(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.time.sleep",
        lambda delay: sleeps.append(delay),
    )

    fetcher, session = make_fetcher(
        [
            requests.ConnectionError("failure one"),
            requests.ConnectionError("failure two"),
            requests.ConnectionError("failure three"),
        ],
        monkeypatch,
    )

    with pytest.raises(FetchError, match="failure three"):
        fetcher.fetch("https://example.com")

    assert session.calls == 3
    assert sleeps == [1.0, 2.0]


def test_reset_session_replaces_session_and_preserves_user_agent(monkeypatch):
    created_sessions = []

    class ReplacementSession:
        def __init__(self):
            self.headers = {}
            created_sessions.append(self)

    fetcher = HttpFetcher(user_agent="AskANU-Test/1.0", timeout=1)
    original_session = fetcher._session

    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.requests.Session",
        ReplacementSession,
    )

    fetcher._reset_session()

    assert fetcher._session is not original_session
    assert fetcher._session is created_sessions[0]
    assert fetcher._session.headers["User-Agent"] == "AskANU-Test/1.0"


def test_empty_response_resets_session_before_retry(monkeypatch):
    sleeps = []
    replacement = FakeSession([FakeResponse("<html>ok</html>")])

    class ReplacementSessionFactory:
        def __call__(self):
            return replacement

    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.time.sleep",
        lambda delay: sleeps.append(delay),
    )

    fetcher = HttpFetcher(user_agent="AskANU/0.1", timeout=1)
    first_session = FakeSession([FakeResponse("")])
    fetcher._session = first_session

    monkeypatch.setattr(
        "askanu_scraper.common.fetcher.requests.Session",
        ReplacementSessionFactory(),
    )

    assert fetcher.fetch("https://example.com") == "<html>ok</html>"

    assert first_session.calls == 1
    assert replacement.calls == 1
    assert replacement.headers["User-Agent"] == "AskANU/0.1"
    assert sleeps == [1.0]
