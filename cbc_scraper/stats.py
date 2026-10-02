from datetime import datetime, timezone
from collections import defaultdict
from html import unescape
import re


def clean(value):
    return unescape(re.sub("<[^>]+>", "", str(value)))


def timestamp(value):
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(value), timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (
            parsed.replace(tzinfo=timezone.utc)
            if parsed.tzinfo is None
            else parsed.astimezone(timezone.utc)
        )
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def count(value):
    return int(clean(value).replace(",", ""))


def leaderboard(raw_data, year):
    participants = {
        clean(row[0]): count(row[1]) for row in raw_data.get("Participants", [])
    }
    total = sum(participants.values())
    tasks = {}
    for name, rows in raw_data.items():
        if name == "Participants":
            continue
        schools = []
        for row in rows:
            solvers = count(row[1 if year >= 2022 else 2])
            if solvers <= 0:
                continue
            school = clean(row[0])
            first_solve = timestamp(row[3]) if len(row) > 3 else None
            participant_count = participants.get(school, 0)
            schools.append(
                {
                    "school": school,
                    "solvers": solvers,
                    "solve_rate": (
                        round(100 * solvers / participant_count, 2)
                        if participant_count
                        else None
                    ),
                    "first_solve": first_solve.isoformat() if first_solve else None,
                }
            )
        schools.sort(
            key=lambda school_entry: (-school_entry["solvers"], school_entry["school"])
        )
        fastest = sorted(
            (school_entry for school_entry in schools if school_entry["first_solve"]),
            key=lambda school_entry: (
                school_entry["first_solve"],
                school_entry["school"],
            ),
        )
        solves = sum(school_entry["solvers"] for school_entry in schools)
        tasks[name] = {
            "solvers": solves,
            "solve_rate": round(100 * solves / total, 2) if total else None,
            "schools": schools,
            "fastest": fastest,
        }
    return {"participants": total, "school_count": len(participants), "tasks": tasks}


def format_duration(seconds):
    if seconds is None:
        return "N/A"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s"


def task_order(name):
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", name)
    )


def submissions(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.get("task", "Unknown"))].append(row)
    result = {}
    for task in sorted(groups, key=task_order):
        result[task] = summarize_attempts(groups[task])
    add_task_intervals(result)
    return result


def summarize_attempts(attempts):
    times = sorted(
        submitted_at
        for submitted_at in (timestamp(attempt.get("at")) for attempt in attempts)
        if submitted_at
    )
    successes = [
        attempt
        for attempt in attempts
        if attempt.get("success") is True
        or attempt.get("passed") is True
        or attempt.get("status") in ("correct", "passed", "success")
    ]
    attempt_span = (times[-1] - times[0]).total_seconds() if times else None
    return {
        "attempts": len(attempts),
        "status": "Passed" if successes else "Unknown",
        "first_attempt": times[0].isoformat() if times else None,
        "last_attempt": times[-1].isoformat() if times else None,
        "attempt_span_hours": (
            round(attempt_span / 3600, 2) if attempt_span is not None else None
        ),
        "attempt_span_seconds": attempt_span,
        "attempt_span": format_duration(attempt_span),
    }


def add_task_intervals(result):
    baseline = next(
        (
            timestamp(row["first_attempt"])
            for task, row in result.items()
            if re.fullmatch(r"task\s*0", task, re.I)
        ),
        None,
    )
    numbered_tasks = {
        int(match.group(1)): row
        for task, row in result.items()
        if (match := re.fullmatch(r"task\s*(\d+)", task, re.I))
    }
    for task, row in result.items():
        match = re.fullmatch(r"task\s*(\d+)", task, re.I)
        task_number = int(match.group(1)) if match else None
        previous = (
            numbered_tasks.get(task_number - 1) if task_number is not None else None
        )
        start = (
            baseline
            if task_number == 0
            else timestamp(previous["last_attempt"]) if previous else None
        )
        end = timestamp(row["last_attempt"])
        interval = (
            (end - start).total_seconds() if start and end and end >= start else None
        )
        elapsed = (
            (end - baseline).total_seconds()
            if baseline and end and end >= baseline
            else None
        )
        row.update(
            {
                "task_interval_start": start.isoformat() if start else None,
                "task_interval_seconds": interval,
                "task_interval": format_duration(interval),
                "since_task0_seconds": elapsed,
                "since_task0": format_duration(elapsed),
            }
        )
