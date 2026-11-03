"""以公告日 ID 清单确定日报范围，不用首次提交时间推测公告归属。"""
import datetime as dt
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import feedparser


def short_id(value):
    return re.sub(r'v\d+$', '', value.rsplit('/', 1)[-1])


class ListingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.heading = self.buffer = ''
        self.days = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'h3':
            self.active = True
            self.buffer = ''
        if tag == 'a' and self.heading in self.days:
            href = dict(attrs).get('href', '')
            if href.startswith('/abs/'):
                self.days[self.heading]['ids'].append(short_id(href))

    def handle_data(self, text):
        if self.active:
            self.buffer += text

    def handle_endtag(self, tag):
        if tag == 'h3':
            self.active = False
            self.heading = ' '.join(self.buffer.split())
            match = re.match(r'\w+, (\d+ \w+ \d+) \(showing (?:first \d+|\d+) of (\d+) entries', self.heading)
            if match:
                self.days[self.heading] = {'date': dt.datetime.strptime(match[1], '%d %b %Y').date().isoformat(),
                                           'expected': int(match[2]), 'ids': []}


def parse_listing(html, day):
    parser = ListingParser()
    parser.feed(html)
    matches = [v for v in parser.days.values() if v['date'] == str(day)]
    if len(matches) != 1:
        raise ValueError('官方列表中没有唯一的目标公告日，不能回退到提交时间猜测')
    result = matches[0]
    if len(result['ids']) != result['expected'] or len(set(result['ids'])) != result['expected']:
        raise ValueError('官方列表分页不全或 ID 重复，禁止生成完成标记')
    result['sha256'] = hashlib.sha256('\n'.join(sorted(result['ids'])).encode()).hexdigest()
    result['source'] = 'https://arxiv.org/list/math.AP/recent?show=2000'
    return result


def manifest(day):
    import daily_backup as backup
    path = backup.STATE / 'announcements' / (str(day) + '.json')
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    # 与 Atom API 共用连接锁、速率间隔和 429 冷却规则。
    response = backup.api_response({'show': 2000}, url='https://arxiv.org/list/math.AP/recent')
    result = parse_listing(response.content.decode('utf-8'), day)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    return result


def entries_for(data):
    import daily_backup as backup
    found = {}
    for offset in range(0, len(data['ids']), 100):
        ids = data['ids'][offset:offset + 100]
        path = backup.STATE / 'announcements' / (data['date'] + '-' + str(offset) + '.xml')
        if path.exists():
            content = path.read_bytes()
        else:
            content = backup.api_response({'id_list': ','.join(ids), 'max_results': len(ids)}).content
        feed = feedparser.parse(content)
        by_id = {short_id(e.id): e for e in feed.entries}
        if feed.bozo or set(by_id) != set(ids):
            raise ValueError('API 按 ID 补取结果不全，不能将部分元数据当成完整日报')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        found.update(by_id)
    return [found[i] for i in data['ids']]


def report_ids(text):
    return [short_id(i) for i in re.findall(r'^\*\*arXiv ID\*\*:\s*(\S+)', text, re.M)]


def verify(text, data):
    ids = report_ids(text)
    return len(ids) == data['expected'] and len(set(ids)) == len(ids) and set(ids) == set(data['ids'])
