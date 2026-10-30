import datetime as dt
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip('fcntl')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import daily_retry as retry
import daily_backup as backup


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'STATE', tmp_path)
    monkeypatch.setattr(retry, 'adopted_completion', lambda _: False)


def moment(day, hour):
    return dt.datetime(2026, 10, day, hour, tzinfo=backup.TZ)


def success(day):
    print(f'📚 {day} arXiv 日报：math.AP 共 115 篇，已完成 115 篇。')
    print(f'报告：https://pikel72.github.io/report/arxiv_analysis_{day}_12-00-00/')


def test_four_slots_target_same_report_date():
    assert [retry.target_day(t) for t in [moment(30, 12), moment(30, 18), moment(31, 0), moment(31, 6)]] == [dt.date(2026, 10, 30)] * 4
    assert retry.target_day(moment(31, 12)) == dt.date(2026, 10, 31)


def test_12_rate_limited_18_success_midnight_and_6_do_nothing(monkeypatch, capsys):
    attempts = []
    authors = []
    def main(day):
        attempts.append(day)
        if len(attempts) == 1:
            raise backup.RateLimited(0)
        success(day)
    monkeypatch.setattr(backup, 'main', main)
    monkeypatch.setattr(backup, 'author_news', lambda *a: authors.append(a) or {})
    retry.run_attempt(now=moment(30, 12))
    assert capsys.readouterr().out == ''
    assert retry.read_state(dt.date(2026, 10, 30))['status'] == 'pending'
    retry.run_attempt(now=moment(30, 18))
    assert '115 篇' in capsys.readouterr().out
    def forbidden(*a, **kw):
        pytest.fail('成功后不应执行任何外部操作')
    for name in ['main', 'author_news', 'sync_pages', 'query', 'git']:
        monkeypatch.setattr(backup, name, forbidden)
    monkeypatch.setattr(retry, 'adopted_completion', forbidden)
    retry.run_attempt(now=moment(31, 0))
    retry.run_attempt(now=moment(31, 6))
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''
    assert len(attempts) == len(authors) == 2


def test_all_four_429_remain_pending_and_silent(monkeypatch, capsys):
    def unavailable(*a):
        raise backup.RateLimited(0)
    monkeypatch.setattr(backup, 'author_news', unavailable)
    monkeypatch.setattr(backup, 'main', lambda *a: pytest.fail('作者限流后不应继续执行'))
    for now in [moment(30, 12), moment(30, 18), moment(31, 0), moment(31, 6)]:
        assert retry.run_attempt(now=now) == 0
    text = capsys.readouterr()
    assert text.out == text.err == ''
    assert retry.read_state(dt.date(2026, 10, 30))['status'] == 'pending'


def test_retry_after_prevents_early_network_call(monkeypatch, capsys):
    day = dt.date(2026, 10, 30)
    retry.save_state(day, {'status': 'pending', 'retry_at': time.time() + 86400})
    monkeypatch.setattr(backup, 'author_news', lambda *a: pytest.fail('Retry-After 尚未到期'))
    retry.run_attempt(day)
    assert capsys.readouterr().out == ''


def test_partial_output_cannot_mark_complete(monkeypatch, capsys):
    monkeypatch.setattr(backup, 'author_news', lambda *a: {})
    monkeypatch.setattr(backup, 'main', lambda day: print(f'{day} arXiv 日报：math.AP 共 115 篇，已完成 80 篇。'))
    retry.run_attempt(dt.date(2026, 10, 30))
    assert retry.read_state(dt.date(2026, 10, 30)).get('status') != 'complete'
    assert capsys.readouterr().out == ''


def test_active_original_job_is_not_interrupted_or_duplicated(monkeypatch, capsys):
    import fcntl
    with (backup.STATE / 'daily.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(backup, 'author_news', lambda *a: pytest.fail('原任务仍在运行'))
        assert retry.run_attempt(dt.date(2026, 10, 30)) == 0
    assert capsys.readouterr().out == ''


def test_already_published_completes_once(monkeypatch, capsys):
    day = dt.date(2026, 10, 30)
    monkeypatch.setattr(backup, 'author_news', lambda *a: {})
    def published(day):
        raise backup.AlreadyPublished(day, (Path(f'arxiv_analysis_{day}_12-00-00.md'),
            {'total_papers': '115', 'completed_papers': '115'}))
    monkeypatch.setattr(backup, 'main', published)
    retry.run_attempt(day)
    assert '115 篇' in capsys.readouterr().out
    assert retry.read_state(day)['status'] == 'complete'
    retry.run_attempt(day)
    assert capsys.readouterr().out == ''
