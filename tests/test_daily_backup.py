import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
pytest.importorskip('fcntl')
import daily_backup as backup


def test_windows_match_original_weekday_logic():
    assert backup.window(dt.date(2026, 10, 26)) == (
        dt.datetime(2026, 10, 22, 18, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 10, 23, 18, tzinfo=dt.timezone.utc))
    assert backup.window(dt.date(2026, 10, 27)) == (
        dt.datetime(2026, 10, 23, 18, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 10, 26, 18, tzinfo=dt.timezone.utc))
    assert backup.window(dt.date(2026, 10, 25)) is None


def test_only_complete_report_skips_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'PAGES', tmp_path)
    path = tmp_path / 'content/report/2026/10/arxiv_analysis_2026-10-27_10-40-00.md'
    path.parent.mkdir(parents=True)
    path.write_text('---\nreport_date: 2026-10-27\npartial_run: False\ntotal_papers: 12\ncompleted_papers: 11\nskipped_papers: 1\n---\n', encoding='utf-8')
    assert backup.report_for(dt.date(2026, 10, 27)) is None
    path.write_text('---\nreport_date: 2026-10-27\npartial_run: False\ntotal_papers: 12\ncompleted_papers: 12\nskipped_papers: 0\n---\n', encoding='utf-8')
    assert backup.report_for(dt.date(2026, 10, 27))[0] == path


def test_query_fetches_all_pages_and_excludes_end(monkeypatch):
    calls = []
    feeds = [
        SimpleNamespace(bozo=False, feed={'opensearch_totalresults': '3'}, entries=[
            SimpleNamespace(published='2026-10-26T19:00:00Z'),
            SimpleNamespace(published='2026-10-26T20:00:00Z')]),
        SimpleNamespace(bozo=False, feed={'opensearch_totalresults': '3'}, entries=[
            SimpleNamespace(published='2026-10-27T18:00:00Z')]),
    ]
    def get(url, params, timeout):
        calls.append(params['start'])
        return SimpleNamespace(content=b'feed', raise_for_status=lambda: None)
    monkeypatch.setattr(backup.requests, 'get', get)
    monkeypatch.setattr(backup.feedparser, 'parse', lambda _: feeds.pop(0))
    monkeypatch.setattr(backup.time, 'sleep', lambda _: None)
    start = dt.datetime(2026, 10, 26, 18, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 10, 27, 18, tzinfo=dt.timezone.utc)
    assert len(backup.query('cat:math.AP', start, end, 2)) == 2
    assert calls == [0, 2]


def test_author_search_has_no_category_filter_and_deduplicates(tmp_path, monkeypatch):
    (tmp_path / 'authors.json').write_text('[{"name":"Yongzhong Sun","aliases":["Y. Sun"]}]', encoding='utf-8')
    monkeypatch.setattr(backup, 'ROOT', tmp_path)
    entry = SimpleNamespace(id='http://arxiv.org/abs/1234.56789', title='Example',
        authors=[SimpleNamespace(name='Yongzhong Sun'), SimpleNamespace(name='Y. Sun')],
        tags=[SimpleNamespace(term='math.DG')])
    queries = []
    def query(search, start, end):
        queries.append(search)
        return [entry]
    monkeypatch.setattr(backup, 'query', query)
    monkeypatch.setattr(backup.time, 'sleep', lambda _: None)
    now = dt.datetime(2026, 10, 27, tzinfo=dt.timezone.utc)
    result = backup.author_news(now, now + dt.timedelta(days=1))
    assert len(result) == 1
    assert all('cat:' not in query for query in queries)
    assert result[entry.id]['matched'] == {'Yongzhong Sun'}
