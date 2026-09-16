from bs4 import BeautifulSoup

from askanu_scraper.detail_coverage import DetailCandidate, _source_presence


URL = (
    "https://study.anu.edu.au/scholarships/"
    "find-scholarship/test-scholarship"
)


def _candidate() -> DetailCandidate:
    return DetailCandidate(
        entity_class="scholarship",
        identifier="test-scholarship",
        url=URL,
    )


def test_yearless_application_period_is_not_structured_date_evidence() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <h1 class="banner-title">Test Scholarship</h1>
            <div>
              <h2>Application period</h2>
            </div>
            <p>04-Sep to 31-Oct</p>
          </body>
        </html>
        """,
        "lxml",
    )

    presence = _source_presence(_candidate(), soup)

    assert presence["opening_date"] is False
    assert presence["closing_date"] is False


def test_explicit_year_application_period_is_structured_date_evidence() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <h1 class="banner-title">Test Scholarship</h1>
            <div>
              <h2>Application period</h2>
            </div>
            <p>04-Sep-2026 to 31-Oct-2026</p>
          </body>
        </html>
        """,
        "lxml",
    )

    presence = _source_presence(_candidate(), soup)

    assert presence["opening_date"] is True
    assert presence["closing_date"] is True
