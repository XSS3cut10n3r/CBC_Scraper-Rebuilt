"""Bounded, chronological browsing of personal submission payloads."""
import re
import sys
from datetime import datetime, timezone

from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from .client import ScraperError
from .stats import timestamp

PAGE_SIZE = 20
PREVIEW_SIZE = 240


def literal(value):
    # Preserve newlines and tabs, but remove terminal control characters.
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]', '', str(value if value is not None else ''))


def payload(row):
    value = row.get('hexdata', '')
    if isinstance(value, str):
        try:
            return literal(bytes.fromhex(value).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            pass
    return literal(value)


def ordered(rows):
    return sorted(rows, key=lambda row: timestamp(row.get('at')) or datetime.max.replace(tzinfo=timezone.utc))


def page_table(task, rows, page):
    total_pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    if not 1 <= page <= total_pages:
        raise ScraperError(f'Page must be between 1 and {total_pages}.')
    table = Table(title=Text(f'{task} — {len(rows)} submissions — page {page}/{total_pages}'), show_lines=True)
    table.add_column('#', no_wrap=True)
    table.add_column('Submitted (UTC)', width=19)
    table.add_column('Submission', ratio=1)
    table.add_column('API response', ratio=1)
    for i, row in enumerate(rows[(page-1)*PAGE_SIZE:page*PAGE_SIZE], (page-1)*PAGE_SIZE+1):
        at = timestamp(row.get('at'))
        cells = [payload(row), literal(row.get('response', ''))]
        previews = [cell if len(cell) <= PREVIEW_SIZE else cell[:PREVIEW_SIZE] + '… [open entry for full text]' for cell in cells]
        table.add_row(str(i), at.strftime('%Y-%m-%d %H:%M:%S') if at else 'Unknown', *(Text(cell) for cell in previews))
    return table


def browse(rows, args, console):
    groups = {}
    for row in rows:
        groups.setdefault(str(row.get('task', 'Unknown')), []).append(row)
    tasks = sorted(groups, key=lambda name: [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in re.split(r'(\d+)', name)])
    if not tasks:
        console.print('No submissions yet.')
        return
    interactive = sys.stdin.isatty()
    if not interactive and not args.task:
        console.print('Available tasks: ' + ', '.join(tasks), markup=False)
        console.print('Choose one with: cbc-scraper history --task task0 (add --display for saved data).')
        return
    selected = args.task
    while True:
        if selected is None:
            table = Table('Choose task', 'Task', 'Submissions')
            task_choices = {}
            for task in tasks:
                match = re.fullmatch(r'task\s*(\d+[a-z]?)', task, re.I)
                key = match.group(1) if match else task
                task_choices[key] = task
                table.add_row(Text(key), Text(task), str(len(groups[task])))
            console.print(table)
            choice = Prompt.ask('Enter the task number to view its submissions (q to return to the main menu)', choices=list(task_choices) + ['q'], show_choices=False, console=console)
            if choice == 'q':
                return
            selected = task_choices[choice]
        task = next((t for t in tasks if t.replace(' ', '').casefold() == selected.replace(' ', '').casefold()), None)
        if task is None:
            raise ScraperError('No submissions for that task. Run cbc-scraper history to choose a task.')
        entries = ordered(groups[task])
        page = args.page if args.task and selected == args.task else 1
        while True:
            console.print(page_table(task, entries, page))
            console.print('Oldest first · Up to 20 per page · Enter a submission # for full text.')
            if not interactive:
                console.print('Use --page N for another page; run in a terminal to open full entries.')
                return
            pages = max(1, (len(entries)+PAGE_SIZE-1)//PAGE_SIZE)
            choices = ['t', 'q'] + (['n'] if page < pages else []) + (['p'] if page > 1 else [])
            choices += [str(i) for i in range((page-1)*PAGE_SIZE+1, min(page*PAGE_SIZE, len(entries))+1)]
            navigation = (['n: Next page'] if page < pages else []) + (['p: Previous page'] if page > 1 else [])
            navigation += ['t: Change task', 'q: Main menu']
            console.print(' · '.join(navigation))
            action = Prompt.ask('Submission # or shortcut', choices=choices, show_choices=False, console=console)
            if action == 'q':
                return
            if action == 't':
                selected = None
                break
            if action in ('n', 'p'):
                page += 1 if action == 'n' else -1
                continue
            row = entries[int(action)-1]
            console.print(f'Submission #{action}', style='bold cyan')
            console.print(Text(payload(row)))
            console.print('API response', style='bold cyan')
            console.print(Text(literal(row.get('response', ''))))
            Prompt.ask('Press Enter to return to the table', default='', console=console)
