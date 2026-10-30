import datetime as dt
import hashlib
import sys
from pathlib import Path

import pytest
pytest.importorskip('fcntl')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import daily_backup as backup
import daily_retry as retry
import tracker_ops as ops

DAY = dt.date(2026, 10, 30)
TEXT = '---\nreport_date: 2026-10-30\npartial_run: False\nselection_capped: false\ntotal_papers: 3\ncompleted_papers: 3\nskipped_papers: 0\n---\nReport\n'


@pytest.fixture
def pending(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'STATE', tmp_path)
    p = ops.pending_path(DAY)
    p.parent.mkdir(parents=True)
    p.write_text(TEXT, encoding='utf-8')
    return p


def test_publish_checks_content_before_marking_complete(pending, monkeypatch):
    calls = []
    blob = TEXT.encode()
    sha = hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
    def api(path, payload=None):
        calls.append((path, payload))
        if payload is not None:
            return {'commit': {'sha': 'new-commit'}}
        return {'sha': sha} if path.endswith('.md') else []
    monkeypatch.setattr(ops, 'gh_api', api)
    assert ops.publish(DAY)['status'] == 'complete'
    assert retry.read_state(DAY)['commit'] == 'new-commit'
    assert len(calls) == 3
    assert ops.publish(DAY)['status'] == 'already_complete'
    assert len(calls) == 3


def test_partial_report_never_reaches_network(pending, monkeypatch):
    pending.write_text(TEXT.replace('completed_papers: 3', 'completed_papers: 2'))
    monkeypatch.setattr(ops, 'gh_api', lambda *a: pytest.fail('部分报告不能发布'))
    with pytest.raises(ValueError, match='拒绝发布'):
        ops.publish(DAY)
    assert retry.read_state(DAY) == {}


def test_remote_hash_mismatch_leaves_pending(pending, monkeypatch):
    def api(path, payload=None):
        if payload is not None:
            return {'commit': {'sha': 'new-commit'}}
        return {'sha': 'wrong'} if path.endswith('.md') else []
    monkeypatch.setattr(ops, 'gh_api', api)
    with pytest.raises(RuntimeError, match='校验失败'):
        ops.publish(DAY)
    assert retry.read_state(DAY) == {}
