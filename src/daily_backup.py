"""Hermes 备用日报：核对远端、补跑并检索关注作者。"""
import datetime as dt
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse

import feedparser
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
STATE = Path.home() / '.local/state/arxiv-paper-tracker'
PAGES = STATE / 'pages'
API = 'https://export.arxiv.org/api/query'
TZ = dt.timezone(dt.timedelta(hours=8))


class AlreadyPublished(BaseException):
    def __init__(self, day, report):
        self.day, self.report = day, report


def git(*args, cwd=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', '-c', 'credential.helper=!gh auth git-credential', *args],
                          cwd=cwd, env=env, text=True, capture_output=True, check=True, timeout=120).stdout.strip()


def window(day):
    # 与现有定时任务的 UTC 提交区间一致，周一和周二分别覆盖周末。
    if day.weekday() >= 5:
        return None
    days = (4, 4, 2, 2, 2)[day.weekday()]
    end_days = (3, 1, 1, 1, 1)[day.weekday()]
    at = lambda n: dt.datetime.combine(day - dt.timedelta(days=n), dt.time(18), dt.timezone.utc)
    return at(days), at(end_days)


def query(search, start, end, page_size=200):
    items, offset = [], 0
    while True:
        params = {'search_query': search, 'start': offset, 'max_results': page_size,
                  'sortBy': 'submittedDate', 'sortOrder': 'descending'}
        for attempt in range(3):
            try:
                response = requests.get(API, params=params, timeout=60)
                response.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        feed = feedparser.parse(response.content)
        if feed.bozo:
            raise RuntimeError('arXiv 返回无法解析的结果')
        total = int(feed.feed.get('opensearch_totalresults', len(feed.entries)))
        for entry in feed.entries:
            published = dt.datetime.fromisoformat(entry.published.replace('Z', '+00:00'))
            if start <= published < end:
                items.append(entry)
        offset += len(feed.entries)
        if offset >= total:
            return items
        if not feed.entries:
            raise RuntimeError('arXiv 分页提前结束')
        time.sleep(3)


def date_query(start, end):
    return 'submittedDate:[%s TO %s]' % (start.strftime('%Y%m%d%H%M'), end.strftime('%Y%m%d%H%M'))


def author_news(start, end):
    authors = json.loads((ROOT / 'authors.json').read_text(encoding='utf-8'))
    found = {}
    for author in authors:
        for name in [author['name'], *author.get('aliases', [])]:
            # API 作者查询可能返回同名者；再核对完整姓名，仍提醒读者确认身份。
            entries = query('au:"%s" AND %s' % (name.replace('"', ''), date_query(start, end)), start, end)
            for entry in entries:
                norm = lambda s: ' '.join(re.sub(r'[^\w ]', ' ', s.casefold()).split())
                if any(norm(a.name) == norm(name) for a in entry.authors):
                    item = found.setdefault(entry.id, {'entry': entry, 'matched': set()})
                    item['matched'].add(author['name'])
            time.sleep(3)
    return found


def sync_pages():
    STATE.mkdir(parents=True, exist_ok=True)
    if not PAGES.exists():
        git('clone', 'https://github.com/pikel72/pages_src.git', str(PAGES))
    if git('status', '--porcelain', cwd=PAGES):
        raise RuntimeError('备用发布目录有未提交修改，停止以保护数据')
    git('fetch', 'origin', 'main', cwd=PAGES)
    git('checkout', '--detach', 'origin/main', cwd=PAGES)


def report_for(day, expected=None):
    folder = PAGES / 'content/report' / day.strftime('%Y/%m')
    candidates = list(folder.glob('arxiv_analysis_' + day.isoformat() + '*.md')) if folder.exists() else []
    candidates += list((PAGES / 'content/report').glob('arxiv_analysis_' + day.isoformat() + '*.md'))
    for path in sorted(candidates):
        text = path.read_text(encoding='utf-8')
        head = text.split('---', 2)[1] if text.startswith('---') else ''
        fields = dict(re.findall(r'^(\w+):\s*(.*)$', head, re.M))
        try:
            complete = (fields.get('partial_run', '').lower() == 'false'
                        and int(fields['total_papers']) == int(fields['completed_papers'])
                        and int(fields['skipped_papers']) == 0
                        and (expected is None or int(fields['total_papers']) == expected))
        except (KeyError, ValueError):
            complete = False
        report_date = fields.get('report_date', fields.get('date', '')[:10])
        if complete and report_date == day.isoformat():
            return path, fields
    return None


def main():
    day = dt.datetime.now(TZ).date()
    bounds = window(day)
    if not bounds:
        # 关注作者仍逐日检查，不受 math.AP 周末跳过规则限制。
        end = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(18), dt.timezone.utc)
        news = author_news(end - dt.timedelta(days=1), end)
        print(f'📚 {day} arXiv 日报：math.AP 周末按原规则跳过。')
        print_author_news(news)
        return
    start, end = bounds
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'daily.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('📚 论文日报已有服务器任务正在运行。')
            return
        entries = query('(cat:math.AP) AND ' + date_query(start, end), start, end)
        if not entries:
            raise RuntimeError('没有检索到论文，请核对 arXiv 公告和网络状态')
        try:
            sync_pages()
            report = report_for(day, len(entries))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # 网站暂时不可达时仍生成待发布文件；发布前必须再次核对远端。
            logging.warning('暂时无法检查网站，先生成本地待发布报告')
            report = None
        if not report:
            # 单独保存运行日志，避免把模型内容或凭据混入 Hermes 消息。
            load_dotenv(ROOT / '.env', override=True)
            # 专用凭据文件避免依赖服务器上过时的同步副本。
            load_dotenv(Path.home() / '.config/arxiv-paper-tracker/runtime.env', override=True)
            values = json.loads(subprocess.check_output(['gh', 'variable', 'list', '--repo',
                'pikel72/arxiv_paper_tracker', '--json', 'name,value'], text=True))
            for value in values:
                if value['value']:
                    os.environ[value['name']] = value['value']
            os.environ.update(SEARCH_DAYS='1', LITELLM_LOCAL_MODEL_COST_MAP='True')
            import main as tracker
            from models import SimplePaper
            pending = STATE / 'pending' / ('arxiv_analysis_' + day.isoformat() + '_12-00-00.md')
            if pending.exists():
                text = pending.read_text(encoding='utf-8')
            else:
                tracker.get_recent_papers = lambda *a, **k: [SimplePaper(e) for e in entries]
                original_record = tracker.record_paper_result
                last_check = time.monotonic()

                def record_with_check(*args):
                    nonlocal last_check
                    # 其他链路完成后不再派发新论文，正在执行的请求允许收尾。
                    if time.monotonic() - last_check >= 120:
                        last_check = time.monotonic()
                        try:
                            sync_pages()
                            current = report_for(day, len(entries))
                        except Exception as exc:
                            logging.warning('检查远端日报失败，稍后重试: %s', exc)
                        else:
                            if current:
                                raise AlreadyPublished(day, current)
                    return original_record(*args)

                tracker.record_paper_result = record_with_check
                existing = set((ROOT / 'results').glob('arxiv_analysis_*.md'))
                sys.argv = ['main.py', '--date', (start.date() + dt.timedelta(days=1)).isoformat() + ':' + end.date().isoformat(), '--no-email', '--no-thinking']
                with (STATE / ('run-' + day.isoformat() + '.log')).open('a', encoding='utf-8') as log:
                    old = sys.stdout
                    try:
                        sys.stdout = log
                        tracker.main()
                    finally:
                        for handler in logging.getLogger().handlers:
                            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                                handler.setStream(old)
                        sys.stdout = old
                new = sorted(set((ROOT / 'results').glob('arxiv_analysis_*.md')) - existing)
                if len(new) != 1:
                    raise RuntimeError('没有生成唯一的完整报告')
                text = new[0].read_text(encoding='utf-8')
                text = re.sub(r'^title: .*$', f'title: "{day:%Y年%m月%d日}论文分析"', text, count=1, flags=re.M)
                text = re.sub(r'^date: .*$', f'date: {day} 12:00:00', text, count=1, flags=re.M)
                text = text.replace('---\n', f'---\nreport_date: {day}\n', 1)
            head = dict(re.findall(r'^(\w+):\s*(.*)$', text.split('---', 2)[1], re.M))
            if int(head.get('completed_papers', -1)) != len(entries) or int(head.get('skipped_papers', -1)) != 0:
                raise RuntimeError('报告未全部完成，保留本地结果并停止发布')
            pending.parent.mkdir(parents=True, exist_ok=True)
            if not pending.exists():
                pending.write_text(text, encoding='utf-8')
            sync_pages()
            report = report_for(day, len(entries))
            if not report:
                target = PAGES / 'content/report' / day.strftime('%Y/%m') / pending.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8')
                git('add', '--', str(target.relative_to(PAGES)), cwd=PAGES)
                git('-c', 'user.name=pikel72', '-c', 'user.email=github-actions[bot]@users.noreply.github.com',
                    'commit', '-m', '[✨ 新增] 补充每日 arXiv 论文报告', cwd=PAGES)
                try:
                    git('push', 'origin', 'HEAD:main', cwd=PAGES)
                except subprocess.CalledProcessError:
                    # 其他链路抢先推送时重新检查，不能盲目覆盖。
                    git('fetch', 'origin', 'main', cwd=PAGES)
                    git('checkout', '--detach', 'origin/main', cwd=PAGES)
                    if not report_for(day, len(entries)):
                        raise
                report = report_for(day, len(entries))
        print_report(day, report)


def print_author_news(news):
    print('\n关注作者新论文（覆盖所有 arXiv 分类，过去一个 UTC 提交日；同名需核实）：')
    if not news:
        print('本期没有匹配的新论文。')
    for item in news.values():
        entry = item['entry']
        print('\n📝 ' + ', '.join(sorted(item['matched'])) + '：' + ' '.join(entry.title.split()))
        print('作者：' + ', '.join(a.name for a in entry.authors))
        print('分类：' + ', '.join(t.term for t in entry.tags))
        print(entry.id)


def print_report(day, report):
    path, fields = report
    author_end = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(18), dt.timezone.utc)
    news = author_news(author_end - dt.timedelta(days=1), author_end)
    print(f'📚 {day} arXiv 日报：math.AP 共 {fields["total_papers"]} 篇，已完成 {fields["completed_papers"]} 篇。')
    print('报告：https://pikel72.github.io/report/' + path.stem + '/')
    print_author_news(news)


if __name__ == '__main__':
    try:
        if sys.argv[1:2] == ['--check']:
            day = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) == 3 else dt.datetime.now(TZ).date()
            bounds = window(day)
            if not bounds:
                print('true')
            else:
                start, end = bounds
                entries = query('(cat:math.AP) AND ' + date_query(start, end), start, end)
                if not entries:
                    raise RuntimeError('arXiv 未返回论文，无法判断日报是否完成')
                sync_pages()
                print('true' if report_for(day, len(entries)) else 'false')
        else:
            main()
    except AlreadyPublished as completed:
        print_report(completed.day, completed.report)
    except Exception as exc:
        logging.exception('日报失败')
        print('❌ arXiv 日报失败：' + str(exc))
        sys.exit(1)
