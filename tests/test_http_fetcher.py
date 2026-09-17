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

    def get(self, url: str, timeout: int):
        self.calls += 1
        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def make_fetcher(outcomes: list[object]) -> tuple[HttpFetcher, FakeSession]:
    fetcher = HttpFetcher(timeout=1)
    session = FakeSession(outcomes)
    fetcher._session = session
    return fetcher, session


def test_valid_response_succeeds_without_retry(monkeypatch):
    monkeypatch.setattr("askanu_scraper.common.fetcher.time.sleep", lambda _: None)

    fetcher, session = make_fetcher([FakeResponse("<html>ok</html>")])

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
        ]
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
        ]
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
        ]
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
        ]
    )

    with pytest.raises(FetchError, match="failure three"):
        fetcher.fetch("https://example.com")

    assert session.calls == 3
    assert sleeps == [1.0, 2.0]
