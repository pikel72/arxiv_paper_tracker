import datetime as dt
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
pytest.importorskip('fcntl')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import announcements as a
import daily_backup as b


def test_announcement_ids_include_late_announced_and_ignore_other_day():
    html = '<h3>Tue, 3 Nov 2026 (showing 3 of 3 entries )</h3>'
    html += ''.join(f'<a href="/abs/{i}">Abstract</a>' for i in ['2611.00137','2611.03640','2611.03642'])
    html += '<h3>Mon, 2 Nov 2026 (showing 1 of 1 entries )</h3><a href="/abs/2611.00001">Abstract</a>'
    result = a.parse_listing(html, dt.date(2026,11,3))
    assert result['expected'] == 3 and result['ids'] == ['2611.00137','2611.03640','2611.03642']


@pytest.mark.parametrize('links', ['<a href="/abs/2611.00001">a</a>', '<a href="/abs/2611.00001">a</a>'*2])
def test_partial_or_duplicate_list_rejected(links):
    with pytest.raises(ValueError):
        a.parse_listing('<h3>Tue, 3 Nov 2026 (showing 2 of 2 entries )</h3>'+links, dt.date(2026,11,3))


def test_40_completed_is_not_131_covered():
    data = {'expected':131,'ids':[f'2611.{i:05d}' for i in range(131)]}
    text = 'completed_papers: 40\n'+''.join(f'**arXiv ID**: 2611.{i:05d}v1\n' for i in range(40))
    assert not a.verify(text,data)
    text += ''.join(f'**arXiv ID**: 2611.{i:05d}v1\n' for i in range(40,131))
    assert a.verify(text,data)
    assert not a.verify(text+'**arXiv ID**: 2611.00000v1\n',data)


def test_winter_cutoff_and_dst_transition():
    assert b.window(dt.date(2026,11,3)) == (dt.datetime(2026,10,30,18,tzinfo=dt.timezone.utc),dt.datetime(2026,11,2,19,tzinfo=dt.timezone.utc))
    assert b.author_window(dt.date(2026,11,3))[1] == dt.datetime(2026,11,2,19,tzinfo=dt.timezone.utc)


def test_id_hydration_fetches_all_131_without_timestamp_filter(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'STATE',tmp_path)
    ids=[f'2611.{i:05d}' for i in range(131)]
    responses=[]
    def api(params):
        selected=params['id_list'].split(',');responses.append(selected)
        assert 'search_query' not in params
        return SimpleNamespace(content=','.join(selected).encode())
    monkeypatch.setattr(b,'api_response',api)
    monkeypatch.setattr(a.feedparser,'parse',lambda content:SimpleNamespace(bozo=False,entries=[SimpleNamespace(id='https://arxiv.org/abs/'+i+'v1',published='2026-10-29T18:38:00Z') for i in content.decode().split(',')]))
    assert len(a.entries_for({'ids':ids,'date':'2026-11-03'})) == 131
    assert [len(x) for x in responses] == [100,31]


def test_old_complete_40_report_is_archived_and_cannot_skip_repair(tmp_path,monkeypatch):
    day=dt.date(2026,11,3)
    monkeypatch.setattr(b,'STATE',tmp_path)
    old='---\nselection_capped: false\ntotal_papers: 40\ncompleted_papers: 40\n---\n'+''.join(f'**arXiv ID**: 2611.{i:05d}v1\n' for i in range(40))
    saved=tmp_path/'pending'/f'arxiv_analysis_{day}_12-00-00.md'
    saved.parent.mkdir();saved.write_text(old)
    remote=tmp_path/'remote.md';remote.write_text(old)
    monkeypatch.setattr(a,'manifest',lambda _: {'expected':131,'ids':[f'2611.{i:05d}' for i in range(131)]})
    monkeypatch.setattr(b,'sync_pages',lambda **kw:None)
    monkeypatch.setattr(b,'report_for',lambda *args:(remote,{'selection_capped':'false'}))
    def hydrate(data):
        raise LookupError('must rehydrate official 131 IDs')
    monkeypatch.setattr(a,'entries_for',hydrate)
    with pytest.raises(LookupError,match='131'):
        b.main(day)
    assert not saved.exists()
    assert len(list((tmp_path/'backups').rglob('*.md'))) == 1
