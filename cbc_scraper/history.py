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
            for index, task in enumerate(tasks, 1):
                table.add_row(str(index), Text(task), str(len(groups[task])))
            console.print(table)
            choice = Prompt.ask('Task number (0 to return)', choices=['0']+[str(i) for i in range(1, len(tasks)+1)], console=console)
            if choice == '0':
                return
            selected = tasks[int(choice)-1]
        task = next((t for t in tasks if t.replace(' ', '').casefold() == selected.replace(' ', '').casefold()), None)
        if task is None:
            raise ScraperError('No submissions for that task. Run cbc-scraper history to choose a task.')
        entries = ordered(groups[task])
        page = args.page
        while True:
            console.print(page_table(task, entries, page))
            console.print('Earliest first. 20 entries per page; long text is previewed. UTF-8 hex is decoded; other payloads are shown as supplied.')
            if not interactive:
                console.print('Use --page N for another page; run in a terminal to open full entries.')
                return
            pages = max(1, (len(entries)+PAGE_SIZE-1)//PAGE_SIZE)
            choices = ['t', 'q'] + (['n'] if page < pages else []) + (['p'] if page > 1 else [])
            choices += [str(i) for i in range((page-1)*PAGE_SIZE+1, min(page*PAGE_SIZE, len(entries))+1)]
            action = Prompt.ask('n next / p previous / entry number for full text / t tasks / q return', choices=choices, show_choices=False, console=console)
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
