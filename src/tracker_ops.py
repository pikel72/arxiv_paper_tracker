"""Hermes 手动运维：本地状态、作者动态及完整待发布报告的官方 API 发布。"""
import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import json
import re
import subprocess

import daily_backup as backup
import daily_retry as retry
from author_store import library_path


def metadata(text):
    if not text.startswith('---\n'):
        raise ValueError('报告缺少 YAML 元数据')
    return dict(re.findall(r'^(\w+):\s*(.*)$', text.split('---', 2)[1], re.M))


def validate_report(day, text):
    fields = metadata(text)
    total = int(fields.get('total_papers', -1))
    if (fields.get('report_date') != day.isoformat() or total <= 0
            or int(fields.get('completed_papers', -1)) != total
            or int(fields.get('skipped_papers', -1)) != 0
            or fields.get('partial_run', '').lower() != 'false'
            or fields.get('selection_capped', '').lower() != 'false'):
        raise ValueError('报告日期不符、被截断或未完整完成，拒绝发布')
    return fields


def pending_path(day):
    return backup.STATE / 'pending' / f'arxiv_analysis_{day}_12-00-00.md'


def gh_api(path, payload=None):
    command = ['gh', 'api', path]
    if payload is not None:
        command += ['--method', 'PUT', '--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, timeout=90)
    if result.returncode:
        if payload is None and 'HTTP 404' in result.stderr:
            return None
        # 只报告错误类型；不要把凭据、完整报告或服务器配置混入反馈。
        raise RuntimeError('GitHub API 请求失败，请检查 gh 登录、仓库权限和网络')
    return json.loads(result.stdout)


def status(day):
    path = pending_path(day)
    cooldown = backup.STATE / 'api-retry-after'
    return {'report_date': day.isoformat(), 'state': retry.read_state(day),
            'pending_report': str(path) if path.exists() else None,
            'pending_metadata': metadata(path.read_text(encoding='utf-8')) if path.exists() else None,
            'authors_file': str(library_path()),
            'api_retry_after': float(cooldown.read_text()) if cooldown.exists() else None,
            'attempt_log': str(backup.STATE / f'attempt-{day}.log'),
            'analysis_log': str(backup.STATE / f'run-{day}.log')}


def publish(day):
    if retry.read_state(day).get('status') == 'complete':
        return {'report_date': str(day), 'status': 'already_complete', 'state': retry.read_state(day)}
    backup.STATE.mkdir(parents=True, exist_ok=True)
    with (backup.STATE / f'attempt-{day}.lock').open('a') as attempt, (backup.STATE / 'daily.lock').open('a') as active:
        fcntl.flock(attempt, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = pending_path(day)
        text = path.read_text(encoding='utf-8')
        fields = validate_report(day, text)
        folder = f'content/report/{day:%Y/%m}'
        endpoint = 'repos/pikel72/pages_src/contents/'
        files = gh_api(endpoint + folder) or []
        name, commit = path.name, None
        for item in files:
            if not item['name'].startswith(f'arxiv_analysis_{day}') or not item['name'].endswith('.md'):
                continue
            remote = gh_api(endpoint + item['path'])
            if not remote:
                continue
            content = base64.b64decode(remote['content']).decode('utf-8')
            try:
                existing = validate_report(day, content)
            except ValueError:
                if item['name'] == name:
                    raise ValueError('目标文件已存在且不完整；保留它，需明确决定如何替换')
                continue
            if existing['total_papers'] != fields['total_papers']:
                raise ValueError('远端同日报告篇数不同，请先核对，不能自动覆盖或重复发布')
            name = item['name']
            break
        else:
            result = gh_api(endpoint + folder + '/' + name, {
                'message': f'[✨ 新增] 补齐{day}论文分析报告', 'branch': 'main',
                'content': base64.b64encode(text.encode('utf-8')).decode('ascii')})
            commit = result['commit']['sha']
            remote = gh_api(endpoint + folder + '/' + name)
            blob = text.encode('utf-8')
            expected = hashlib.sha1(b'blob ' + str(len(blob)).encode() + b'\0' + blob).hexdigest()
            if not remote or remote['sha'] != expected:
                raise RuntimeError('提交后内容校验失败，未写入完成标记')
        url = 'https://pikel72.github.io/report/' + name[:-3] + '/'
        summary = f'📚 {day} arXiv 日报：math.AP 共 {fields["total_papers"]} 篇，已完成 {fields["completed_papers"]} 篇。\n报告：{url}\n'
        retry.save_state(day, {'status': 'complete', 'finished_at': dt.datetime.now(backup.TZ).isoformat(),
                               'summary': summary, 'manual_publication': True, 'commit': commit})
        return {'report_date': str(day), 'url': url, 'commit': commit, 'status': 'complete'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'authors-news', 'publish', 'summary'])
    parser.add_argument('--date', type=dt.date.fromisoformat)
    args = parser.parse_args(argv)
    day = args.date or retry.target_day(dt.datetime.now(backup.TZ))
    if args.command == 'status':
        print(json.dumps(status(day), ensure_ascii=False, indent=2))
    elif args.command == 'summary':
        print(retry.read_state(day).get('summary', '没有保存摘要；已接纳旧任务时请查看 Hermes cron 输出。'))
    elif args.command == 'publish':
        print(json.dumps(publish(day), ensure_ascii=False, indent=2))
    else:
        try:
            backup.print_author_news(backup.author_news(*backup.author_window(day)))
        except backup.RateLimited:
            print('作者查询当前受到 429 限流，未把失败当作没有新论文；自动任务将在下一时段重试。')


if __name__ == '__main__':
    main()
