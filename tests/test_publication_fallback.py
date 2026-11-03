import datetime as dt
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest
pytest.importorskip('fcntl')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import daily_backup as backup
import daily_retry as retry
import tracker_ops as ops

DAY = dt.date(2026, 11, 3)
TEXT = '---\nreport_date: 2026-11-03\npartial_run: False\nselection_capped: false\ntotal_papers: 40\ncompleted_papers: 40\nskipped_papers: 0\n---\nExisting complete report\n'


@pytest.fixture
def pending(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'STATE', tmp_path)
    monkeypatch.setattr(retry, 'adopted_completion', lambda _: False)
    monkeypatch.setattr(backup, 'author_news', lambda *a: {})
    monkeypatch.setattr(backup, 'query', lambda *a: pytest.fail('复用成品时不能重新抓取/分析'))
    def git_unavailable(*a, **kw):
        raise subprocess.TimeoutExpired('git fetch', 20)
    monkeypatch.setattr(backup, 'sync_pages', git_unavailable)
    path = ops.pending_path(DAY)
    path.parent.mkdir(parents=True)
    path.write_text(TEXT, encoding='utf-8')
    return path


def working_api(calls):
    blob = TEXT.encode()
    sha = hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
    def api(path, payload=None):
        calls.append((path, payload))
        if payload is not None:
            return {'commit': {'sha': 'automatic-fallback-commit'}}
        return {'sha': sha} if path.endswith('.md') else []
    return api


def test_automatic_git_timeout_uses_api_under_existing_locks(pending, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ops, 'gh_api', working_api(calls))
    assert retry.run_attempt(DAY) == 0
    assert '共 40 篇，已完成 40 篇' in capsys.readouterr().out
    assert retry.read_state(DAY)['status'] == 'complete'
    assert len(calls) == 3
    assert pending.read_text() == TEXT
    retry.run_attempt(DAY)
    assert capsys.readouterr().out == '' and len(calls) == 3


def test_both_transports_fail_silently_then_next_slot_only_publishes(pending, monkeypatch, capsys):
    def offline(*a, **kw):
        raise backup.PublicationDeferred('network unavailable')
    monkeypatch.setattr(ops, 'gh_api', offline)
    assert retry.run_attempt(DAY) == 0
    text = capsys.readouterr()
    assert text.out == text.err == ''
    assert retry.read_state(DAY) == {'status': 'pending', 'reason': 'publication_network'}
    assert pending.read_text() == TEXT
    calls = []
    monkeypatch.setattr(ops, 'gh_api', working_api(calls))
    retry.run_attempt(DAY)
    assert '40 篇' in capsys.readouterr().out
    assert retry.read_state(DAY)['status'] == 'complete'


@pytest.mark.parametrize('error', ['connection timed out', 'HTTP 429', 'HTTP 503'])
def test_api_transient_errors_are_deferred(monkeypatch, error):
    monkeypatch.setattr(ops.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', error))
    with pytest.raises(backup.PublicationDeferred):
        ops.gh_api('repos/pikel72/pages_src/contents/content/report')


def test_permission_errors_are_not_silently_hidden(monkeypatch):
    monkeypatch.setattr(ops.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', 'HTTP 401 Bad credentials'))
    with pytest.raises(RuntimeError) as exc:
        ops.gh_api('repos/pikel72/pages_src/contents/content/report')
    assert not isinstance(exc.value, backup.PublicationDeferred)
