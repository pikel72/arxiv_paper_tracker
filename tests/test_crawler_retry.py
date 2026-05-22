#!/usr/bin/env python3

import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from crawler import _fetch_arxiv_response, _get_retry_after_seconds, get_recent_papers


def test_fetch_arxiv_response_retries_on_503():
    bad = Mock(status_code=503)
    good = Mock(status_code=200)

    with patch("crawler.requests.get", side_effect=[bad, bad, good]) as mocked_get, \
         patch("crawler.time.sleep"):
        response = _fetch_arxiv_response("https://export.arxiv.org/api/query?test=1", max_retries=4, timeout=5)

    assert response is good
    assert mocked_get.call_count == 3


def test_retry_after_uses_header_when_larger():
    response = Mock(headers={"Retry-After": "30"})

    assert _get_retry_after_seconds(response, 10) == 30


def test_get_recent_papers_uses_exact_submission_window():
    atom = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2605.00001v1</id>
    <updated>2026-05-20T00:55:30Z</updated>
    <published>2026-05-20T00:55:30Z</published>
    <title>Too early</title>
    <summary>Outside the exact window.</summary>
    <author><name>Alice</name></author>
    <category term="math.AP" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2605.00002v1</id>
    <updated>2026-05-20T18:32:09Z</updated>
    <published>2026-05-20T18:32:09Z</published>
    <title>Inside window</title>
    <summary>Inside the exact window.</summary>
    <author><name>Bob</name></author>
    <category term="math.AP" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""
    response = Mock(content=atom)

    with patch("crawler._fetch_arxiv_response", return_value=response) as mocked_fetch:
        papers = get_recent_papers(["math.AP"], max_results=100, target_date="2026-05-21")

    url = mocked_fetch.call_args.args[0]
    assert "submittedDate:[202605201800 TO 202605211800]" in url
    assert "sortBy=submittedDate" in url
    assert [paper.title for paper in papers] == ["Inside window"]


if __name__ == "__main__":
    test_fetch_arxiv_response_retries_on_503()
    test_retry_after_uses_header_when_larger()
    test_get_recent_papers_uses_exact_submission_window()
    print("crawler retry tests passed")
