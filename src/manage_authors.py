"""Hermes 作者库管理命令；默认只修改服务器个人库，不修改 Git 中的种子。"""
import argparse
import json
from pathlib import Path

from author_store import change_authors, library_path, load_authors, normalize


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', help='指定库文件，通常使用默认服务器个人库')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['list', 'validate', 'path', 'init']:
        commands.add_parser(name)
    for name in ['add', 'remove', 'enable', 'disable', 'rename', 'alias-add', 'alias-remove', 'note']:
        p = commands.add_parser(name)
        p.add_argument('name')
        if name == 'add':
            p.add_argument('--alias', action='append', default=[])
            p.add_argument('--note', default='')
        if name in ['rename', 'alias-add', 'alias-remove', 'note']:
            p.add_argument('value')
    args = parser.parse_args(argv)
    path = args.file or library_path()
    if args.command == 'path':
        print(path)
        return
    if args.command == 'init' and Path(path).exists():
        load_authors(path)
        print('作者库已存在，保留现有名单：' + str(path))
        return
    if args.command in ['list', 'validate']:
        authors = load_authors(path)
        print(json.dumps(authors, ensure_ascii=False, indent=2) if args.command == 'list'
              else f'作者库有效：{len(authors)} 人，{sum(a.get("enabled", True) for a in authors)} 人启用')
        return

    def edit(authors):
        if args.command == 'init':
            return
        matches = [a for a in authors if normalize(a['name']) == normalize(args.name)]
        if args.command == 'add':
            if matches:
                raise ValueError('作者已存在，请使用 alias-add 或 note 修改')
            authors.append({'name': args.name.strip(), 'aliases': args.alias, 'enabled': True, 'notes': args.note})
            return
        if len(matches) != 1:
            raise ValueError('未找到唯一作者: ' + args.name)
        author = matches[0]
        if args.command == 'remove':
            authors.remove(author)
        elif args.command in ['enable', 'disable']:
            author['enabled'] = args.command == 'enable'
        elif args.command == 'rename':
            author['name'] = args.value.strip()
        elif args.command == 'note':
            author['notes'] = args.value
        elif args.command == 'alias-add':
            author.setdefault('aliases', []).append(args.value.strip())
        elif args.command == 'alias-remove':
            aliases = author.get('aliases', [])
            found = [a for a in aliases if normalize(a) == normalize(args.value)]
            if not found:
                raise ValueError('未找到该别名')
            author['aliases'] = [a for a in aliases if a not in found]

    change_authors(edit, path)
    print('作者库已保存：' + str(path))


if __name__ == '__main__':
    main()
