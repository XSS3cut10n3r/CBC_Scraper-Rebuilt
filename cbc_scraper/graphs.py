import math

from rich import box
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from .client import ScraperError
from .stats import clean, count, format_duration, leaderboard, submissions, task_order


def bar(value, maximum, width, scale="linear"):
    if value is None:
        return "?".ljust(width)
    if value <= 0 or maximum <= 0:
        return " " * width
    ratio = (
        math.log1p(value) / math.log1p(maximum)
        if scale == "logarithmic"
        else value / maximum
    )
    length = int(min(ratio, 1) * width)
    return ("#" * length if length else ".").ljust(width)


def chart(
    console,
    title,
    entries,
    maximum,
    scale_label,
    style="cyan",
    scale="linear",
    group_size=1,
):
    console.print()
    console.print(title, style="bold cyan", markup=False)
    if not entries:
        console.print("No data available.")
        return
    label_width = max(4, max(len(label) for label, _, _ in entries))
    value_width = max(5, max(len(value) for _, _, value in entries))
    width = max(4, min(42, console.width - label_width - value_width - 10))
    console.print(f"Scale: {scale} | 0 to {scale_label}", style="dim", markup=False)
    table = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan")
    table.add_column("Task", width=label_width, no_wrap=True)
    table.add_column("Graph", width=width, no_wrap=True)
    table.add_column("Value", width=value_width, no_wrap=True)
    bars = []
    for index, (label, value, formatted) in enumerate(entries):
        bar_text = bar(value, maximum, width, scale)
        bars.append(bar_text)
        bar_style = style(label) if callable(style) else style
        table.add_row(
            Text(label),
            Text(bar_text, style=bar_style),
            Text(formatted),
            end_section=(index + 1) % group_size == 0,
        )
    console.print(table)
    legend = []
    if any(bar_text.startswith(".") for bar_text in bars):
        legend.append(". = less than one bar character")
    if any(value is None for _, value, _ in entries):
        legend.append("? = unavailable")
    if legend:
        console.print(" | ".join(legend), style="dim")


def overall_graph(raw_data, year, console):
    stats = leaderboard(raw_data, year)
    console.print(
        f'Overall | {year} | {stats["participants"]:,} participants | {stats["school_count"]:,} schools',
        markup=False,
    )
    entries = []
    for task in sorted(stats["tasks"], key=task_order):
        row = stats["tasks"][task]
        rate = row["solve_rate"]
        value = f"{rate:.2f}%" if rate is not None else "N/A"
        entries.append((task, rate, f'{value}  ({row["solvers"]:,} solvers)'))
    chart(console, "Task solve rates", entries, 100, "100%")
    console.print(
        "Each rate uses all registered challenge participants as its denominator.",
        style="dim",
    )


def personal_graph(raw_data, console, scale="linear"):
    stats = submissions(raw_data)
    if not stats:
        console.print("No submissions yet.")
        return
    console.print("My graph", style="bold cyan")
    for title, field in [
        ("Solve Time per task", "task_interval_seconds"),
        ("Total since first task0 submission", "since_task0_seconds"),
    ]:
        entries = [
            (task, row[field], format_duration(row[field]))
            for task, row in stats.items()
        ]
        maximum = max(
            (value for _, value, _ in entries if value is not None), default=0
        )
        chart(console, title, entries, maximum, format_duration(maximum), scale=scale)
    if scale == "logarithmic":
        console.print(
            "Logarithmic bars compress long durations; the times shown remain exact.",
            style="dim",
        )
    console.print(
        "Solve Time uses consecutive tasks' last submissions; Total starts at your first task0 submission. Includes breaks.",
        style="dim",
    )


def school_entries(raw_data, year, school):
    participants = {
        clean(row[0]): count(row[1]) for row in raw_data.get("Participants", [])
    }
    registered = participants.get(school)
    overall = leaderboard(raw_data, year)
    entries = []
    for task in sorted(overall["tasks"], key=task_order):
        row = next((row for row in raw_data[task] if clean(row[0]) == school), None)
        solvers = count(row[1 if year >= 2022 else 2]) if row is not None else None
        rate = (
            100 * solvers / registered if registered and solvers is not None else None
        )
        entries.append((task, solvers, rate, overall["tasks"][task]["solve_rate"]))
    return registered, entries


def school_graph(raw_data, year, school, console):
    registered, tasks = school_entries(raw_data, year, school)
    console.print(
        f'{school} | {year} | {registered if registered is not None else "Unknown"} registered participants',
        style="bold cyan",
        markup=False,
    )
    entries = []
    for task, solvers, rate, overall_rate in tasks:
        formatted = f"{rate:.2f}%" if rate is not None else "N/A"
        solves = (
            f"{solvers}/{registered}"
            if solvers is not None and registered is not None
            else "count unavailable"
        )
        entries.append((task + " school", rate, f"{formatted}  ({solves} solvers)"))
        entries.append(
            (
                task + " overall",
                overall_rate,
                f"{overall_rate:.2f}%" if overall_rate is not None else "N/A",
            )
        )
    chart(
        console,
        "School vs overall solve rates",
        entries,
        100,
        "100%",
        style=lambda label: (
            "bright_black" if label.endswith(" overall") else "bold cyan"
        ),
        group_size=2,
    )
    console.print(
        "School rates use registered challenge participants at this school, not total school enrollment. Missing task rows show N/A.",
        style="dim",
    )


def select_school(raw_data, console):
    schools = sorted(
        {clean(row[0]) for row in raw_data.get("Participants", [])}, key=str.casefold
    )
    if not schools:
        console.print("No school participation data available.")
        return None
    while True:
        query = Prompt.ask(
            "School name to search (q to return)", console=console
        ).strip()
        if query.lower() == "q":
            return None
        matches = [
            school for school in schools if query.casefold() in school.casefold()
        ]
        if not matches:
            console.print("No matches. Try a shorter name.")
            continue
        if len(matches) == 1:
            return matches[0]
        page = 0
        while True:
            table = Table("Choose", "School")
            start = page * 20
            for index, school in enumerate(matches[start : start + 20], start + 1):
                table.add_row(str(index), Text(school))
            console.print(table)
            console.print(
                f"{len(matches)} matches | page {page + 1}/{(len(matches) + 19) // 20}"
            )
            choices = [
                str(index)
                for index in range(start + 1, min(start + 20, len(matches)) + 1)
            ]
            choices += (
                ["s", "q"]
                + (["n"] if start + 20 < len(matches) else [])
                + (["p"] if page else [])
            )
            choice = Prompt.ask(
                "School number / n next / p previous / s search / q return",
                choices=choices,
                show_choices=False,
                console=console,
            )
            if choice == "q":
                return None
            if choice == "s":
                break
            if choice in ("n", "p"):
                page += 1 if choice == "n" else -1
                continue
            return matches[int(choice) - 1]


def graph_menu(load_data, year, console):
    loaded = {}
    while True:
        console.print("\nPROGRESS AND SOLVE-TIME GRAPHS", style="bold cyan")
        console.print(
            "1. Overall graph\n2. My graph\n3. School specific graph\n0. Back"
        )
        choice = Prompt.ask("Choose", choices=["1", "2", "3", "0"], console=console)
        if choice == "0":
            return 0
        kind = "submissions" if choice == "2" else "leaderboard"
        try:
            if kind not in loaded:
                loaded[kind] = load_data(kind)
            raw_data, source = loaded[kind]
            console.print(source, style="dim", markup=False)
            if choice == "1":
                overall_graph(raw_data, year, console)
            elif choice == "2":
                scale = "linear"
                while True:
                    personal_graph(raw_data, console, scale)
                    next_scale = "logarithmic" if scale == "linear" else "linear"
                    action = Prompt.ask(
                        f"s: Switch to {next_scale} scale / Enter: Back to graphs",
                        choices=["s", ""],
                        default="",
                        show_choices=False,
                        console=console,
                    )
                    if action != "s":
                        break
                    scale = next_scale
                continue
            else:
                school = select_school(raw_data, console)
                if school is not None:
                    school_graph(raw_data, year, school, console)
        except (ScraperError, OSError, ValueError, TypeError, KeyError, IndexError):
            console.print(
                "Could not load graph data. Check your login or use cbc-scraper graphs --display for saved results."
            )
        Prompt.ask("Press Enter to return to graphs", default="", console=console)
