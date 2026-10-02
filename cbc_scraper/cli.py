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
from rich.panel import Panel
from rich.box import Box

from .client import Client, ScraperError, request_headers
from .auth import find_request, REQUEST_TEMPLATE
from .config import YEAR_TASKS
from .history import browse
from .graphs import graph_menu
from .stats import leaderboard, submissions

from .banner import print_banner


def save(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".cbc-")
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def render(report, args):
    console = Console()
    if not args.no_banner:
        print_banner(console)
    if report["kind"] == "submissions":
        render_submissions(report, console)
    else:
        render_leaderboard(report, args, console)


def render_submissions(report, console):
    show_status = any(row["status"] != "Unknown" for row in report["stats"].values())
    columns = (
        ["Task", "Attempts"]
        + (["Status"] if show_status else [])
        + ["Solve Time", "Total"]
    )
    table = Table(*columns)
    for task, row in report["stats"].items():
        cells = [task, str(row["attempts"])]
        if show_status:
            cells.append(
                row["status"] if row["status"] != "Unknown" else "Not provided"
            )
        table.add_row(*cells, row["task_interval"], row["since_task0"])
    console.print(table)
    console.print(
        "Baseline: first task0 submission. Solve Time: previous task’s last submission to this task’s last submission (task0 starts at the baseline). Includes breaks; last submissions are approximate task boundaries. N/A means a missing or out-of-order boundary."
    )


def render_leaderboard(report, args, console):
    stats = report["stats"]
    console.print(
        f"{report['year']} | {stats['participants']:,} participants | {stats['school_count']:,} schools",
        markup=False,
    )
    table = Table("Task", "Solvers", "Solve rate", "Schools solving")
    for task, row in stats["tasks"].items():
        table.add_row(
            task,
            str(row["solvers"]),
            f"{row['solve_rate']}%" if row["solve_rate"] is not None else "N/A",
            str(len(row["schools"])),
        )
    console.print(table)
    for task, row in stats["tasks"].items():
        if args.task and task.casefold() != args.task.casefold():
            continue
        table = Table(title=f"{task} — earliest school solves", show_lines=False)
        for column in (
            "Rank",
            "School",
            "First solve (UTC)",
            "Solvers",
            "School solve rate",
        ):
            table.add_column(column)
        ranked = list(enumerate(row["fastest"], 1))
        if args.school:
            ranked = [
                (rank, school_entry)
                for rank, school_entry in ranked
                if args.school.casefold() in school_entry["school"].casefold()
            ]
        for rank, school in ranked[: args.top]:
            table.add_row(
                str(rank),
                school["school"],
                school["first_solve"],
                str(school["solvers"]),
                (
                    f"{school['solve_rate']}%"
                    if school["solve_rate"] is not None
                    else "N/A"
                ),
            )
        console.print(table)
    console.print(
        "Fastest = earliest recorded first solve, not duration spent solving. Missing timestamps are excluded."
    )


def parser():
    argument_parser = argparse.ArgumentParser(
        description="Unofficial NSA Codebreaker statistics"
    )
    argument_parser.add_argument(
        "command",
        choices=[
            "leaderboard",
            "submissions",
            "setup",
            "menu",
            "offline",
            "history",
            "graphs",
        ],
        nargs="?",
        default="leaderboard",
    )
    argument_parser.add_argument(
        "--year", type=int, help="Archived challenge year (omit for current board)"
    )
    argument_parser.add_argument(
        "--all-years", action="store_true", help="Fetch known archived configurations"
    )
    argument_parser.add_argument(
        "--tasks", help='Comma-separated current task labels, e.g. "Task 0,Task 1"'
    )
    argument_parser.add_argument(
        "--request-file", help="Browser request file (normally found automatically)"
    )
    argument_parser.add_argument(
        "--template",
        action="store_true",
        help="Create an ignored edit_this_request.txt login guide (setup only)",
    )
    argument_parser.add_argument(
        "--display", action="store_true", help="Analyze cache without network access"
    )
    argument_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    argument_parser.add_argument("--top", type=int, default=5)
    argument_parser.add_argument("--school", help="Case-insensitive school filter")
    argument_parser.add_argument(
        "--task", help="Task to show in rankings or submission history"
    )
    argument_parser.add_argument(
        "--page", type=int, default=1, help="Submission history page (20 entries each)"
    )
    argument_parser.add_argument(
        "--format", choices=["table", "json", "csv"], default="table"
    )
    argument_parser.add_argument(
        "--output", type=Path, help="Export destination (JSON or CSV)"
    )
    argument_parser.add_argument("--no-banner", action="store_true")
    return argument_parser


def export(report, output_format):
    if output_format == "json":
        return json.dumps(report, indent=2) + "\n"
    output_buffer = io.StringIO()
    writer = csv.writer(output_buffer)
    if report["kind"] == "leaderboard":
        writer.writerow(
            [
                "year",
                "task",
                "school",
                "solvers",
                "school_solve_rate",
                "first_solve_utc",
            ]
        )
        for task, row in report["stats"]["tasks"].items():
            for school in row["schools"]:
                writer.writerow(
                    [
                        report["year"],
                        task,
                        school["school"],
                        school["solvers"],
                        school["solve_rate"],
                        school["first_solve"],
                    ]
                )
    else:
        fields = [
            "attempts",
            "status",
            "first_attempt",
            "last_attempt",
            "attempt_span_hours",
            "attempt_span_seconds",
            "attempt_span",
            "task_interval_start",
            "task_interval_seconds",
            "task_interval",
            "since_task0_seconds",
            "since_task0",
        ]
        writer.writerow(["task"] + fields)
        for task, row in report["stats"].items():
            writer.writerow([task] + [row[field] for field in fields])
    return output_buffer.getvalue()


def create_request_template(console):
    path = Path("edit_this_request.txt")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        status = "edit_this_request.txt already exists. Open it to update your login; it has not been overwritten."
    else:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(REQUEST_TEMPLATE)
        status = "Created edit_this_request.txt in this folder. After saving it, choose an option from the menu."
    instructions = (
        "1. Log in at https://nsa-codebreaker.org in your browser.\n\n"
        "2. Open Developer Tools → Network, then reload the page.\n\n"
        "3. Right-click a request to nsa-codebreaker.org → Copy as cURL.\n\n"
        "4. Paste it into [bold]edit_this_request.txt[/bold], replacing the Cookie line, and save it."
    )
    console.print()
    console.print(
        Panel(
            instructions + "\n\n[dim]" + status + "[/dim]",
            title="[bold cyan]LOGIN SETUP INSTRUCTIONS[/bold cyan]",
            box=Box("####\n#  #\n####\n#  #\n####\n####\n#  #\n####\n", ascii=True),
            safe_box=False,
            border_style="bold cyan",
            padding=(1, 2),
        )
    )
    console.print()
    return 0


def setup(args):
    console = Console(stderr=True)
    if args.template:
        return create_request_template(console)
    console.print("One-time browser login setup", style="bold cyan")
    console.print(
        "1. Log in at https://nsa-codebreaker.org in your browser.\n"
        "2. Open Developer Tools → Network, then reload the page.\n"
        "3. Right-click a request to nsa-codebreaker.org → Copy as cURL.\n"
        "4. Paste it into a text file and save it."
    )
    source = args.request_file
    if not source:
        if not sys.stdin.isatty():
            raise ScraperError(
                "Provide the saved file: cbc-scraper setup --request-file /path/to/request.txt"
            )
        source = input(
            "Path to that file, or type template for a cookie paste guide (Enter to cancel): "
        ).strip()
        if source.lower() == "template":
            return create_request_template(console)
        if not source:
            return 0
    try:
        text = Path(source).expanduser().read_text()
        headers = request_headers(text)
    except (OSError, ValueError):
        raise ScraperError(
            "Could not read that browser request. Check the file path and copy it as cURL."
        ) from None
    if not headers.get("cookie"):
        raise ScraperError(
            "This request has no Cookie header. Log in, reload, and copy a new request."
        )
    destination = args.data_dir / "request.txt"
    save(destination, text)
    # Prevent stale login shadowing.
    if Path("edit_this_request.txt").is_file():
        save(Path("edit_this_request.txt"), text)
    console.print(
        "Login request saved locally. Next time, just run python scrape_submissions.py or cbc-scraper.",
        markup=False,
    )
    return 0


def menu():
    from rich.prompt import Prompt

    console = Console()
    print_banner(console)
    while True:
        console.print(
            "\n1. My submissions\n"
            "2. Browse submission text by task\n3. School leaderboards and fastest solves\n"
            "4. View graphs\n5. View all saved results (offline)\n6. Set up / refresh browser login\n0. Exit"
        )
        choice = Prompt.ask(
            "Choose", choices=["1", "2", "3", "4", "5", "6", "0"], default="1"
        )
        if choice == "0":
            return 0
        commands = {
            "1": ["submissions"],
            "2": ["history"],
            "3": ["leaderboard"],
            "4": ["graphs"],
            "5": ["offline"],
            "6": ["setup", "--template"],
        }
        main(commands[choice])


def offline(args):
    console = Console()
    found = False
    errors = 0
    for path in sorted(args.data_dir.glob("leaderboard_stats_*.json")):
        match = re.fullmatch(r"leaderboard_stats_(\d{4})\.json", path.name)
        if not match:
            continue
        found = True
        console.print(f"Saved leaderboard — {match.group(1)}", style="bold cyan")
        errors += main(
            [
                "leaderboard",
                "--display",
                "--year",
                match.group(1),
                "--data-dir",
                str(args.data_dir),
                "--no-banner",
            ]
        )
    if (args.data_dir / "submission_stats.json").is_file():
        found = True
        console.print("Saved submission statistics", style="bold cyan")
        errors += main(
            [
                "submissions",
                "--display",
                "--data-dir",
                str(args.data_dir),
                "--no-banner",
            ]
        )
        console.print("To browse saved submission text: cbc-scraper history --display")
    if not found:
        console.print(
            "No saved results yet. Fetch leaderboards or submissions from the main menu first."
        )
    return 1 if errors else 0


def load_cached_data(path, command):
    if not path.is_file():
        raise ScraperError(
            "No saved results yet. Run cbc-scraper "
            + command
            + " first to download them."
        )
    cached = json.loads(path.read_text())
    raw_data = (
        cached.get("raw_data")
        if command == "leaderboard"
        else cached.get("all_submissions")
    )
    if raw_data is None:
        raise ScraperError("Cache does not contain raw data.")
    return raw_data


def fetch_data(client, leaderboard_html, labels, args, year):
    if (
        args.command == "leaderboard"
        and not args.year
        and not args.all_years
        and not args.tasks
    ):
        labels = list(
            dict.fromkeys(re.findall(r"Task\s+[0-9]+[ab]?", leaderboard_html))
        )
    if args.command == "leaderboard" and not labels:
        raise ScraperError(f"Task layout for {year} is unknown. Supply --tasks.")
    if args.command == "leaderboard":
        historical = year if args.year or args.all_years else None
        raw_data = {"Participants": client.board(1, 0, historical)}
        for task_index, label in enumerate(labels):
            board_column, board_row = (
                (2, task_index) if year <= 2021 else (3 + task_index, 0)
            )
            raw_data[label] = client.board(board_column, board_row, historical)
    else:
        raw_data = client.submissions()
    return raw_data


def display_report(report, raw_data, args):
    if args.command == "history":
        browse(raw_data, args, Console())
    elif args.format == "table":
        render(report, args)
    else:
        content = export(report, args.format)
        if args.output:
            save(args.output, content)
        else:
            print(content, end="")


def validate_arguments(argument_parser, args):
    if args.template and args.command != "setup":
        argument_parser.error("--template is only available with setup")
    if args.page < 1:
        argument_parser.error("--page must be positive")
    if args.command in ("offline", "history", "graphs") and (
        args.format != "table" or args.output or args.all_years
    ):
        argument_parser.error(
            "offline, history, and graphs use table output; export through leaderboard or submissions"
        )
    if args.top < 1:
        argument_parser.error("--top must be positive")
    if args.output and args.format == "table":
        argument_parser.error("--output requires --format json or csv")
    if args.all_years and (
        args.year
        or args.command == "submissions"
        or args.output
        or args.format != "table"
    ):
        argument_parser.error(
            "--all-years requires leaderboard table output without --year or --output"
        )


def run_reports(args):
    years = (
        sorted(YEAR_TASKS)
        if args.all_years
        else [args.year or datetime.now(timezone.utc).year]
    )
    client = None
    for year in years:
        path = args.data_dir / (
            f"leaderboard_stats_{year}.json"
            if args.command == "leaderboard"
            else "submission_stats.json"
        )
        if args.display:
            raw_data = load_cached_data(path, args.command)
        else:
            labels = (
                [label.strip() for label in args.tasks.split(",") if label.strip()]
                if args.tasks
                else YEAR_TASKS.get(year)
            )
            if client is None:
                request = find_request(args.request_file, args.data_dir)
                if args.format == "table":
                    Console(stderr=True).print(
                        "Using saved browser login. Fetching " + args.command + "…",
                        markup=False,
                    )
                client = Client(request)
                leaderboard_html = client.bootstrap()
            raw_data = fetch_data(client, leaderboard_html, labels, args, year)
        stats = (
            leaderboard(raw_data, year)
            if args.command == "leaderboard"
            else submissions(raw_data)
        )
        report = {
            "kind": "submissions" if args.command == "history" else args.command,
            "year": year,
            "stats": stats,
        }
        if not args.display:
            report["fetched_at"] = datetime.now(timezone.utc).isoformat()
            report[
                "raw_data" if args.command == "leaderboard" else "all_submissions"
            ] = raw_data
            save(path, json.dumps(report, indent=2))
        display_report(report, raw_data, args)
    return 0


def load_graph_data(args, kind, year):
    graph_args = argparse.Namespace(**vars(args))
    graph_args.command = kind
    path = args.data_dir / (
        f"leaderboard_stats_{year}.json"
        if kind == "leaderboard"
        else "submission_stats.json"
    )
    if args.display:
        raw_data = load_cached_data(path, kind)
        fetched_at = json.loads(path.read_text()).get(
            "fetched_at", "timestamp unavailable"
        )
        return raw_data, f"Saved data | {fetched_at}"
    Console(stderr=True).print("Fetching graph data...", style="dim")
    client = Client(find_request(args.request_file, args.data_dir))
    leaderboard_html = client.bootstrap()
    labels = (
        [label.strip() for label in args.tasks.split(",") if label.strip()]
        if args.tasks
        else YEAR_TASKS.get(year)
    )
    raw_data = fetch_data(client, leaderboard_html, labels, graph_args, year)
    stats = (
        leaderboard(raw_data, year) if kind == "leaderboard" else submissions(raw_data)
    )
    fetched_at = datetime.now(timezone.utc).isoformat()
    report = {
        "kind": kind,
        "year": year,
        "stats": stats,
        "fetched_at": fetched_at,
        "raw_data" if kind == "leaderboard" else "all_submissions": raw_data,
    }
    save(path, json.dumps(report, indent=2))
    return raw_data, f"Fetched {fetched_at} | Reopen View graphs to refresh."


def main(argv=None):
    argument_parser = parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    args = argument_parser.parse_args(argv)
    if args.command == "menu" or (not argv and sys.stdin.isatty()):
        if not sys.stdin.isatty():
            argument_parser.error(
                "The menu needs an interactive terminal. Use leaderboard or submissions instead."
            )
        try:
            return menu()
        except (EOFError, KeyboardInterrupt):
            return 0
    validate_arguments(argument_parser, args)
    try:
        if args.command == "setup":
            return setup(args)
        if args.command == "offline":
            return offline(args)
        if args.command == "graphs":
            if not sys.stdin.isatty():
                raise ScraperError(
                    "View graphs needs an interactive terminal. Run cbc-scraper and choose View graphs."
                )
            year = args.year or datetime.now(timezone.utc).year
            return graph_menu(
                lambda kind: load_graph_data(args, kind, year), year, Console()
            )
        return run_reports(args)
    except (EOFError, KeyboardInterrupt):
        return 0
    except ScraperError as error:
        Console(stderr=True).print(str(error), markup=False)
        return 1
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        # Exceptions may contain credentials.
        Console(stderr=True).print(
            "Unable to complete operation. Check authentication, cache/API schema, year/task layout, and file paths.",
            markup=False,
        )
        return 1
