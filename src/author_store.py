"""服务器作者库独立于 Git 工作区，原子替换并保留每次修改前的副本。"""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = Path.home() / '.config/arxiv-paper-tracker/authors.json'


def normalize(name):
    return ' '.join(re.sub(r'[^\w ]', ' ', name.casefold()).split())


def library_path():
    override = os.environ.get('ARXIV_AUTHORS_FILE')
    return Path(override).expanduser() if override else DEFAULT_PATH


def validate(authors):
    if not isinstance(authors, list):
        raise ValueError('作者库必须是 JSON 数组')
    names = set()
    for author in authors:
        if not isinstance(author, dict) or not isinstance(author.get('name'), str) or not normalize(author['name']):
            raise ValueError('每位作者必须有非空 name')
        aliases = author.get('aliases', [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) or not normalize(a) for a in aliases):
            raise ValueError('aliases 必须是非空姓名字符串组成的数组')
        if not isinstance(author.get('enabled', True), bool) or not isinstance(author.get('notes', ''), str):
            raise ValueError('enabled 必须是布尔值，notes 必须是字符串')
        for name in [author['name'], *aliases]:
            key = normalize(name)
            if key in names:
                raise ValueError('姓名或别名重复: ' + name)
            names.add(key)
    return authors


def load_authors(path=None):
    path = Path(path) if path else library_path()
    # 未安装个人库时兼容仓库种子；显式配置路径写错必须报错，不能悄悄换库。
    if not path.exists() and path == DEFAULT_PATH and not os.environ.get('ARXIV_AUTHORS_FILE'):
        path = ROOT / 'authors.json'
    return validate(json.loads(path.read_text(encoding='utf-8-sig')))


def change_authors(edit, path=None):
    path = Path(path) if path else library_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        authors = load_authors(path) if path.exists() else load_authors(ROOT / 'authors.json')
        edit(authors)
        validate(authors)
        if path.exists():
            backups = path.parent / 'authors-backups'
            backups.mkdir(exist_ok=True)
            stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            shutil.copy2(path, backups / ('authors-' + stamp + '.json'))
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(authors, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(path)
    return authors
