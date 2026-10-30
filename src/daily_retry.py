"""Hermes 四时段调度：同一报告跨午夜重试，429 和已完成日期均静默。"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import datetime as dt
import fcntl
import io
import json
import logging
import os
from pathlib import Path
import re
import time

import daily_backup as backup

JOB_ID = '023a6e28ecf3'


def target_day(now):
    local = now.astimezone(backup.TZ)
    return local.date() - dt.timedelta(days=1 if local.hour < 12 else 0)


def read_state(day):
    path = backup.STATE / 'days' / (day.isoformat() + '.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def save_state(day, data):
    path = backup.STATE / 'days' / (day.isoformat() + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def report_succeeded(day, text):
    match = re.search(rf'{day} arXiv 日报：math.AP 共 (\d+) 篇，已完成 (\d+) 篇', text)
    return bool(match and int(match[1]) > 0 and match[1] == match[2]
                and f'/report/arxiv_analysis_{day}' in text)


def adopted_completion(day):
    # 部署时旧进程仍可能在运行：其已成功投递的输出同样算完成，不能重复运行。
    folder = Path.home() / '.hermes/cron'
    jobs_path = folder / 'jobs.json'
    if not jobs_path.exists():
        return False
    jobs = json.loads(jobs_path.read_text(encoding='utf-8'))
    jobs = jobs.get('jobs', []) if isinstance(jobs, dict) else jobs
    if not any(j.get('id') == JOB_ID and j.get('last_status') == 'ok' for j in jobs):
        return False
    output = folder / 'output' / JOB_ID
    return any(report_succeeded(day, p.read_text(encoding='utf-8')) for p in output.glob('*.md'))


def run_attempt(day=None, now=None):
    day = day or target_day(now or dt.datetime.now(backup.TZ))
    state = read_state(day)
    # 成功后的路径到这里即结束：不查询作者、不访问远端、不调用模型。
    if state.get('status') == 'complete':
        return 0
    backup.STATE.mkdir(parents=True, exist_ok=True)
    with (backup.STATE / ('attempt-' + day.isoformat() + '.lock')).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        state = read_state(day)
        if state.get('status') == 'complete':
            return 0
        if adopted_completion(day):
            save_state(day, {'status': 'complete', 'adopted': True})
            return 0
        # 原任务未结束时不启动第二个分析，也不产生“正在运行”的消息。
        with (backup.STATE / 'daily.lock').open('a') as active:
            try:
                fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
        if time.time() < state.get('retry_at', 0):
            return 0
        buffer = io.StringIO()
        log_path = backup.STATE / ('attempt-' + day.isoformat() + '.log')
        root = logging.getLogger()
        old_handlers, old_level = root.handlers[:], root.level
        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        root.handlers, root.level = [handler], logging.INFO
        original_authors = backup.author_news
        original_cache = os.environ.get('ARXIV_REUSE_QUERY_CACHE')
        os.environ['ARXIV_REUSE_QUERY_CACHE'] = '1'
        try:
            with log_path.open('a', encoding='utf-8') as log, redirect_stdout(buffer), redirect_stderr(log):
                try:
                    # 作者检索先完成；限流时不发布残缺通知，成功后复用这份结果。
                    news = original_authors(*backup.author_window(day))
                    backup.author_news = lambda *a: news
                    try:
                        backup.main(day)
                    except backup.AlreadyPublished as completed:
                        backup.print_report(completed.day, completed.report)
                except backup.RateLimited as exc:
                    save_state(day, {'status': 'pending', 'reason': '429', 'retry_at': exc.retry_at})
                    logging.info('HTTP 429，本次静默结束，等待下一个时段')
                    return 0
                except Exception as exc:
                    save_state(day, {'status': 'pending', 'reason': type(exc).__name__})
                    logging.exception('本次未完成')
                    raise
            text = buffer.getvalue()
            completed = (report_succeeded(day, text) or
                         (backup.window(day) is None and '周末按原规则跳过' in text) or
                         (backup.schedule_for(day).get('no_announcement') and '官方暂停发布' in text))
            if completed:
                # 只在确认发布（或官方停刊/周末）后写入；失败和部分报告不会误标成功。
                save_state(day, {'status': 'complete', 'finished_at': dt.datetime.now(backup.TZ).isoformat(), 'summary': text})
                print(text, end='')
            return 0
        finally:
            backup.author_news = original_authors
            if original_cache is None:
                os.environ.pop('ARXIV_REUSE_QUERY_CACHE', None)
            else:
                os.environ['ARXIV_REUSE_QUERY_CACHE'] = original_cache
            root.handlers, root.level = old_handlers, old_level
            handler.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=dt.date.fromisoformat)
    args = parser.parse_args()
    raise SystemExit(run_attempt(args.date))
