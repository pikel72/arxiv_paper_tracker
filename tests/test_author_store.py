import json
from pathlib import Path
import sys

import pytest
pytest.importorskip('fcntl')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import author_store as store
import manage_authors as cli
import daily_backup as backup


@pytest.fixture
def library(tmp_path, monkeypatch):
    path = tmp_path / 'authors.json'
    path.write_text('[{"name":"Shaoqing Chen","aliases":[]},{"name":"Yongzhong Sun","aliases":[]}]')
    monkeypatch.setenv('ARXIV_AUTHORS_FILE', str(path))
    return path


def test_crud_aliases_and_backup(library, capsys):
    cli.main(['add', 'Test Author', '--alias', 'Published Name', '--note', 'test'])
    cli.main(['disable', 'Test Author'])
    cli.main(['rename', 'Test Author', 'New Name'])
    cli.main(['alias-add', 'New Name', 'Second Alias'])
    assert store.load_authors()[-1] == {'name': 'New Name', 'aliases': ['Published Name', 'Second Alias'], 'enabled': False, 'notes': 'test'}
    cli.main(['alias-remove', 'New Name', 'Second Alias'])
    cli.main(['enable', 'New Name'])
    assert store.load_authors()[-1]['enabled']
    cli.main(['remove', 'New Name'])
    assert len(store.load_authors()) == 2
    assert len(list((library.parent / 'authors-backups').glob('*.json'))) == 7


def test_duplicate_rejected_without_changing_file(library):
    original = library.read_bytes()
    with pytest.raises(ValueError, match='重复'):
        cli.main(['add', 'Another Name', '--alias', 'Shaoqing Chen'])
    assert library.read_bytes() == original
    assert not (library.parent / 'authors-backups').exists()


def test_explicit_missing_file_never_silently_uses_seed(tmp_path, monkeypatch):
    monkeypatch.setenv('ARXIV_AUTHORS_FILE', str(tmp_path / 'typo.json'))
    with pytest.raises(FileNotFoundError):
        store.load_authors()


def test_daily_reads_server_library_and_ignores_disabled(library, monkeypatch):
    cli.main(['disable', 'Shaoqing Chen'])
    queried = []
    monkeypatch.setattr(backup, 'query', lambda query, *a: queried.append(query) or [])
    monkeypatch.setattr(backup.time, 'sleep', lambda _: None)
    import datetime as dt
    now = dt.datetime(2026, 10, 30, tzinfo=dt.timezone.utc)
    backup.author_news(now, now + dt.timedelta(days=1))
    assert len(queried) == 1 and 'Yongzhong Sun' in queried[0]
    assert 'cat:' not in queried[0]
