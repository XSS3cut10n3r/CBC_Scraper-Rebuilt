import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .client import Client, ScraperError
from .config import YEAR_TASKS
from .stats import leaderboard, submissions

BANNER = r'''
     .-------------------------------.
     |   N   S   A  /  CODEBREAKER    |
     |       /\         /\           |
     |  ____/  \_______/  \____      |
     |  \        CBC          /      |
     |   \_____  /\  ________/       |
     |         \/  \/                |
     '-------------------------------'
         UNOFFICIAL STATS TERMINAL
'''


def save(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.cbc-')
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def render(report, args):
    console = Console()
    if not args.no_banner:
        console.print(BANNER, style='bold cyan', markup=False)
    if report['kind'] == 'submissions':
        table = Table('Task', 'Attempts', 'Status', 'Attempt span (hours)')
        for task, row in report['stats'].items():
            table.add_row(task, str(row['attempts']), row['status'], str(row['attempt_span_hours']))
        console.print(table)
        console.print('Attempt span is elapsed time between submissions, not active solving time. Unknown means no explicit success field.')
        return
    stats = report['stats']
    console.print(f"{report['year']} | {stats['participants']:,} participants | {stats['school_count']:,} schools", markup=False)
    table = Table('Task', 'Solvers', 'Solve rate', 'Schools solving')
    for task, row in stats['tasks'].items():
        table.add_row(task, str(row['solvers']), f"{row['solve_rate']}%" if row['solve_rate'] is not None else 'N/A', str(len(row['schools'])))
    console.print(table)
    for task, row in stats['tasks'].items():
        if args.task and task.casefold() != args.task.casefold():
            continue
        table = Table(title=f'{task} — earliest school solves', show_lines=False)
        for column in ('Rank', 'School', 'First solve (UTC)', 'Solvers', 'School solve rate'):
            table.add_column(column)
        ranked = list(enumerate(row['fastest'], 1))
        if args.school:
            ranked = [(rank, s) for rank, s in ranked if args.school.casefold() in s['school'].casefold()]
        for rank, school in ranked[:args.top]:
            table.add_row(str(rank), school['school'], school['first_solve'], str(school['solvers']),
                          f"{school['solve_rate']}%" if school['solve_rate'] is not None else 'N/A')
        console.print(table)
    console.print('Fastest = earliest recorded first solve, not duration spent solving. Missing timestamps are excluded.')


def parser():
    p = argparse.ArgumentParser(description='Unofficial NSA Codebreaker statistics')
    p.add_argument('command', choices=['leaderboard', 'submissions'], nargs='?', default='leaderboard')
    p.add_argument('--year', type=int, help='Archived challenge year (omit for current board)')
    p.add_argument('--all-years', action='store_true', help='Fetch known archived configurations')
    p.add_argument('--tasks', help='Comma-separated current task labels, e.g. "Task 0,Task 1"')
    p.add_argument('--request-file', help='Local copied cURL request; never executed')
    p.add_argument('--display', action='store_true', help='Analyze cache without network access')
    p.add_argument('--data-dir', type=Path, default=Path('data'))
    p.add_argument('--top', type=int, default=5)
    p.add_argument('--school', help='Case-insensitive school filter')
    p.add_argument('--task', help='Task label to show in earliest-solves tables')
    p.add_argument('--format', choices=['table', 'json', 'csv'], default='table')
    p.add_argument('--output', type=Path, help='Export destination (JSON or CSV)')
    p.add_argument('--no-banner', action='store_true')
    return p


def export(report, fmt):
    if fmt == 'json':
        return json.dumps(report, indent=2) + '\n'
    out = io.StringIO()
    writer = csv.writer(out)
    if report['kind'] == 'leaderboard':
        writer.writerow(['year', 'task', 'school', 'solvers', 'school_solve_rate', 'first_solve_utc'])
        for task, row in report['stats']['tasks'].items():
            for school in row['schools']:
                writer.writerow([report['year'], task, school['school'], school['solvers'], school['solve_rate'], school['first_solve']])
    else:
        writer.writerow(['task', 'attempts', 'status', 'first_attempt', 'last_attempt', 'attempt_span_hours'])
        for task, row in report['stats'].items():
            writer.writerow([task] + list(row.values()))
    return out.getvalue()


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.top < 1:
        p.error('--top must be positive')
    if args.output and args.format == 'table':
        p.error('--output requires --format json or csv')
    if args.all_years and (args.year or args.command == 'submissions' or args.output or args.format != 'table'):
        p.error('--all-years requires leaderboard table output without --year or --output')
    try:
        years = sorted(YEAR_TASKS) if args.all_years else [args.year or datetime.now(timezone.utc).year]
        client = None
        for year in years:
            path = args.data_dir / (f'leaderboard_stats_{year}.json' if args.command == 'leaderboard' else 'submission_stats.json')
            if args.display:
                cached = json.loads(path.read_text())
                raw = cached.get('raw_data') if args.command == 'leaderboard' else cached.get('all_submissions')
                if raw is None:
                    raise ScraperError('Cache does not contain raw data.')
            else:
                labels = [s.strip() for s in args.tasks.split(',') if s.strip()] if args.tasks else YEAR_TASKS.get(year)
                if client is None:
                    client = Client(args.request_file)
                    html = client.bootstrap()
                if args.command == "leaderboard" and not args.year and not args.all_years and not args.tasks:
                    labels = list(dict.fromkeys(re.findall(r"Task\s+[0-9]+[ab]?", html)))
                if args.command == "leaderboard" and not labels:
                    raise ScraperError(f"Task layout for {year} is unknown. Supply --tasks.")
                if args.command == 'leaderboard':
                    historical = year if args.year or args.all_years else None
                    raw = {'Participants': client.board(1, 0, historical)}
                    for i, label in enumerate(labels):
                        x, y = (2, i) if year <= 2021 else (3 + i, 0)
                        raw[label] = client.board(x, y, historical)
                else:
                    raw = client.submissions()
            stats = leaderboard(raw, year) if args.command == 'leaderboard' else submissions(raw)
            report = {'kind': args.command, 'year': year, 'stats': stats}
            if not args.display:
                report['fetched_at'] = datetime.now(timezone.utc).isoformat()
                report['raw_data' if args.command == 'leaderboard' else 'all_submissions'] = raw
                save(path, json.dumps(report, indent=2))
            if args.format == 'table':
                render(report, args)
            else:
                content = export(report, args.format)
                if args.output:
                    save(args.output, content)
                else:
                    print(content, end='')
        return 0
    except ScraperError as error:
        Console(stderr=True).print(str(error), markup=False)
        return 1
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        # Never echo exceptions from parsing credential files or remote data.
        Console(stderr=True).print('Unable to complete operation. Check authentication, cache/API schema, year/task layout, and file paths.', markup=False)
        return 1
