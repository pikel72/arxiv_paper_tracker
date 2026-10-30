import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
pytest.importorskip('fcntl')
import daily_backup as backup


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'STATE', tmp_path / 'state')


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
        return SimpleNamespace(status_code=200, content=b'feed', raise_for_status=lambda: None)
    monkeypatch.setattr(backup.requests, 'get', get)
    monkeypatch.setattr(backup.feedparser, 'parse', lambda _: feeds.pop(0))
    monkeypatch.setattr(backup.time, 'sleep', lambda _: None)
    start = dt.datetime(2026, 10, 26, 18, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 10, 27, 18, tzinfo=dt.timezone.utc)
    assert len(backup.query('cat:math.AP', start, end, 2)) == 2
    assert calls == [0, 2]


def test_author_search_has_no_category_filter_and_deduplicates(tmp_path, monkeypatch):
    (tmp_path / 'authors.json').write_text('[{"name":"Yongzhong Sun","aliases":["Y. Sun"]}]', encoding='utf-8')
    monkeypatch.setenv('ARXIV_AUTHORS_FILE', str(tmp_path / 'authors.json'))
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


def response(status, headers=None):
    result = backup.requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = b'feed'
    return result


def test_rate_limit_defers_without_in_process_retry(monkeypatch):
    calls = []
    def get(*a, **kw):
        calls.append(1)
        return response(429, {'Retry-After': '180'})
    monkeypatch.setattr(backup.requests, 'get', get)
    with pytest.raises(backup.RateLimited) as limited:
        backup.api_response({})
    assert limited.value.retry_at >= backup.time.time() + 179
    assert len(calls) == 1
    with pytest.raises(backup.RateLimited):
        backup.api_response({'search_query': 'another date'})
    assert len(calls) == 1


def test_retry_after_http_date():
    from email.utils import format_datetime
    after = format_datetime(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10))
    assert backup.retry_delay(response(429, {'Retry-After': after}), 0) > 590


def test_repeated_429_is_failure_not_empty_result(monkeypatch):
    calls = []
    def get(*args, **kwargs):
        calls.append(1)
        return response(429)
    monkeypatch.setattr(backup.requests, 'get', get)
    monkeypatch.setattr(backup.time, 'sleep', lambda _: None)
    with pytest.raises(backup.RateLimited):
        backup.api_response({})
    assert len(calls) == 1


def test_non_retryable_error_fails_immediately(monkeypatch):
    calls = []
    def get(*args, **kwargs):
        calls.append(1)
        return response(400)
    monkeypatch.setattr(backup.requests, 'get', get)
    with pytest.raises(backup.requests.HTTPError):
        backup.api_response({})
    assert len(calls) == 1


def test_full_published_report_skips_api(monkeypatch):
    day = dt.date(2026, 10, 29)
    report = (Path('report.md'), {'selection_capped': 'false', 'total_papers': '42'})
    bounds = backup.window(day)
    monkeypatch.setattr(backup, 'window', lambda _: bounds)
    monkeypatch.setattr(backup, 'sync_pages', lambda: None)
    monkeypatch.setattr(backup, 'report_for', lambda *a: report)
    monkeypatch.setattr(backup, 'query', lambda *a: pytest.fail('已发布的全量日报不应再次抓取'))
    printed = []
    monkeypatch.setattr(backup, 'print_report', lambda *a: printed.append(a))
    backup.main(day)
    assert printed[0][0] == day
    assert printed[0][1] == report


def test_author_failure_preserves_report_summary(monkeypatch, capsys):
    def unavailable(*a):
        raise RuntimeError('429')
    monkeypatch.setattr(backup, 'author_news', unavailable)
    backup.print_report(dt.date(2026, 10, 29), (Path('report.md'), {'total_papers': '42', 'completed_papers': '42'}))
    text = capsys.readouterr().out
    assert '共 42 篇' in text
    assert '无法确认是否有新论文' in text
    assert '本期没有匹配' not in text


def test_maintenance_backlog_included_in_next_report():
    day = dt.date(2026, 10, 30)
    expected_start = dt.datetime(2026, 10, 27, 18, tzinfo=dt.timezone.utc)
    assert backup.window(day)[0] == expected_start
    assert backup.author_window(day)[0] == expected_start
    assert backup.window(day)[1] == dt.datetime(2026, 10, 29, 18, tzinfo=dt.timezone.utc)


def test_confirmed_maintenance_empty_is_explained(monkeypatch, capsys):
    monkeypatch.setattr(backup, 'sync_pages', lambda: None)
    monkeypatch.setattr(backup, 'report_for', lambda *a: None)
    monkeypatch.setattr(backup, 'query', lambda *a: [])
    monkeypatch.setattr(backup, 'schedule_for', lambda _: {
        'no_announcement': True, 'reason': '数据库迁移暂停发布', 'source': 'https://status.arxiv.org/'})
    monkeypatch.setattr(backup, 'print_author_updates', lambda *a: None)
    monkeypatch.setattr(backup, 'window', lambda _: (
        dt.datetime(2026, 10, 27, 18, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 10, 28, 18, tzinfo=dt.timezone.utc)))
    backup.main()
    assert '官方暂停发布' in capsys.readouterr().out


def test_unexplained_empty_still_fails(monkeypatch):
    monkeypatch.setattr(backup, 'sync_pages', lambda: None)
    monkeypatch.setattr(backup, 'report_for', lambda *a: None)
    monkeypatch.setattr(backup, 'query', lambda *a: [])
    monkeypatch.setattr(backup, 'schedule_for', lambda _: {})
    monkeypatch.setattr(backup, 'window', lambda _: (
        dt.datetime(2026, 10, 27, 18, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 10, 28, 18, tzinfo=dt.timezone.utc)))
    with pytest.raises(RuntimeError, match='没有检索到论文'):
        backup.main()


def test_backup_pdf_uses_https():
    entry = SimpleNamespace(title='Test', authors=[], published='2026-10-27T17:00:00Z',
        tags=[], id='http://arxiv.org/abs/2610.37653v1', summary='Test')
    assert backup.backup_paper(entry).entry_id == 'https://arxiv.org/abs/2610.37653v1'
    assert entry.id.startswith('http://')


def test_git_timeout_terminates_inherited_pipe_children(tmp_path, monkeypatch):
    import os
    import subprocess
    import time
    command = tmp_path / 'git'
    pidfile = tmp_path / 'child.pid'
    command.write_text('#!/usr/bin/python3\nimport subprocess,time\n'
        'p=subprocess.Popen(["/bin/sleep","60"])\n'
        f'open({str(pidfile)!r},"w").write(str(p.pid))\n'
        'time.sleep(60)\n', encoding='utf-8')
    command.chmod(0o700)
    monkeypatch.setenv('PATH', str(tmp_path) + ':' + os.environ['PATH'])
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        backup.git('fetch', timeout=0.5, attempts=1)
    assert time.monotonic() - started < 5
    state = Path('/proc') / pidfile.read_text() / 'stat'
    assert not state.exists() or state.read_text().split()[2] in {'Z', 'X'}
