#!/usr/bin/env python3

import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from crawler import _fetch_arxiv_response


def test_fetch_arxiv_response_retries_on_503():
    bad = Mock(status_code=503)
    good = Mock(status_code=200)

    with patch("crawler.requests.get", side_effect=[bad, bad, good]) as mocked_get, \
         patch("crawler.time.sleep"):
        response = _fetch_arxiv_response("https://export.arxiv.org/api/query?test=1", max_retries=4, timeout=5)

    assert response is good
    assert mocked_get.call_count == 3


if __name__ == "__main__":
    test_fetch_arxiv_response_retries_on_503()
    print("crawler retry tests passed")
