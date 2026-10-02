from datetime import datetime, timezone
from collections import defaultdict
from html import unescape
import re


def clean(value):
    return unescape(re.sub('<[^>]+>', '', str(value)))


def timestamp(value):
    if value is None or value == '':
        return None
    try:
        if isinstance(value, (int, float)) or str(value).replace('.', '', 1).isdigit():
            return datetime.fromtimestamp(float(value), timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def count(value):
    return int(clean(value).replace(',', ''))


def leaderboard(raw, year):
    participants = {clean(row[0]): count(row[1]) for row in raw.get('Participants', [])}
    total = sum(participants.values())
    tasks = {}
    for name, rows in raw.items():
        if name == 'Participants':
            continue
        schools = []
        for row in rows:
            solvers = count(row[1 if year >= 2022 else 2])
            if solvers <= 0:
                continue
            school = clean(row[0])
            first = timestamp(row[3]) if len(row) > 3 else None
            enrolled = participants.get(school, 0)
            schools.append({'school': school, 'solvers': solvers,
                            'solve_rate': round(100 * solvers / enrolled, 2) if enrolled else None,
                            'first_solve': first.isoformat() if first else None})
        schools.sort(key=lambda s: (-s['solvers'], s['school']))
        fastest = sorted((s for s in schools if s['first_solve']), key=lambda s: (s['first_solve'], s['school']))
        solves = sum(s['solvers'] for s in schools)
        tasks[name] = {'solvers': solves, 'solve_rate': round(100 * solves / total, 2) if total else None,
                       'schools': schools, 'fastest': fastest}
    return {'participants': total, 'school_count': len(participants), 'tasks': tasks}


def format_duration(seconds):
    if seconds is None:
        return 'N/A'
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}h {minutes:02d}m {seconds:02d}s'


def submissions(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.get('task', 'Unknown'))].append(row)
    result = {}
    for task, attempts in sorted(groups.items()):
        times = sorted(t for t in (timestamp(r.get('at')) for r in attempts) if t)
        successes = [r for r in attempts if r.get('success') is True or r.get('passed') is True or r.get('status') in ('correct', 'passed', 'success')]
        span = (times[-1] - times[0]).total_seconds() if times else None
        result[task] = {'attempts': len(attempts), 'status': 'Passed' if successes else 'Unknown',
                        'first_attempt': times[0].isoformat() if times else None,
                        'last_attempt': times[-1].isoformat() if times else None,
                        'attempt_span_hours': round(span / 3600, 2) if span is not None else None,
                        'attempt_span_seconds': span,
                        'attempt_span': format_duration(span)}
    return result
