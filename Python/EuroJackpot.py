# Eurojackpot
import math
import random
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

console = Console()

PRIMARY_COUNT = 5
SECONDARY_COUNT = 2
DEFAULT_PRIMARY_MAX = 50
DEFAULT_SECONDARY_MAX = 12  # EuroJackpot euro numbers are 1–12 since 2022
DRAWS_PER_YEAR = 104  # typically Tue + Fri


def gen(primary_max, secondary_max):
    return (
        random.sample(range(1, primary_max + 1), PRIMARY_COUNT),
        random.sample(range(1, secondary_max + 1), SECONDARY_COUNT),
    )


def format_line(primary, secondary):
    p = ", ".join(f"{n:02d}" for n in sorted(primary))
    s = ", ".join(f"{n:02d}" for n in sorted(secondary))
    return f"{p}  |  {s}"


def parse_numbers(raw, count, max_n, label):
    """Parse comma-separated numbers; return a list or exit on error."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != count:
        console.print(f"[red]Invalid {label} length (need {count} numbers).[/red]")
        sys.exit(1)

    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        console.print(f"[red]Invalid {label}: all values must be integers.[/red]")
        sys.exit(1)

    if any(n < 1 or n > max_n for n in numbers):
        console.print(f"[red]Invalid {label}: numbers must be between 1 and {max_n}.[/red]")
        sys.exit(1)

    if len(set(numbers)) != len(numbers):
        console.print(f"[red]Invalid {label}: duplicates are not allowed.[/red]")
        sys.exit(1)

    return numbers


def is_jackpot(primary_hits, secondary_hits):
    return primary_hits >= PRIMARY_COUNT and secondary_hits >= SECONDARY_COUNT


def combination_count(primary_max, secondary_max):
    return (
        math.comb(primary_max, PRIMARY_COUNT)
        * math.comb(secondary_max, SECONDARY_COUNT)
    )


def unique_line_count(lines):
    return len({(frozenset(p), frozenset(s)) for p, s in lines})


def format_odds(one_in):
    if one_in >= 1_000_000:
        return f"1 in {one_in:,.0f}"
    if one_in >= 100:
        return f"1 in {one_in:,.2f}"
    return f"1 in {one_in:.4f}"


def format_probability(p):
    if p <= 0:
        return "0%"
    if p >= 1:
        return "100%"
    pct = p * 100
    if pct >= 1:
        return f"{pct:.4f}%"
    return f"{pct:.6e}%"


def print_probability_info(lines, primary_max, secondary_max):
    total = combination_count(primary_max, secondary_max)
    unique_lines = unique_line_count(lines)
    line_count = len(lines)

    # One winning combination per draw; duplicates do not improve odds.
    p_single = 1 / total
    p_ticket = unique_lines / total
    expected_draws = total / unique_lines
    expected_years = expected_draws / DRAWS_PER_YEAR

    table = Table(
        title=f"Jackpot probability ({PRIMARY_COUNT}+{SECONDARY_COUNT})",
        box=box.ROUNDED,
        show_header=False,
        pad_edge=False,
        expand=False,
    )
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold")

    table.add_row("Setup", f"{PRIMARY_COUNT} from 1–{primary_max}, {SECONDARY_COUNT} from 1–{secondary_max}")
    table.add_row("Total combinations", f"{total:,}")
    table.add_row("Lines on ticket", f"{line_count} ({unique_lines} unique)")
    table.add_row("Single-line odds", f"{format_odds(1 / p_single)}  ({format_probability(p_single)})")
    table.add_row("Your ticket odds", f"{format_odds(1 / p_ticket)}  ({format_probability(p_ticket)})")
    table.add_row("Expected draws", f"{expected_draws:,.1f}")
    table.add_row("Expected years", f"{expected_years:,.2f}  ({DRAWS_PER_YEAR} draws/year)")

    console.print()
    console.print(table)
    console.print()


def print_ticket(lines):
    table = Table(title="Your ticket", box=box.SIMPLE_HEAVY, pad_edge=False)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Primary", style="cyan")
    table.add_column("Secondary", style="magenta")

    for i, (primary, secondary) in enumerate(lines, start=1):
        table.add_row(
            str(i),
            ", ".join(f"{n:02d}" for n in sorted(primary)),
            ", ".join(f"{n:02d}" for n in sorted(secondary)),
        )

    console.print(table)


def collect_lines(line_count, primary_max, secondary_max, autogen_all=False):
    lines = []
    for i in range(line_count):
        if autogen_all:
            primary, secondary = gen(primary_max, secondary_max)
            lines.append((primary, secondary))
            continue

        console.print(
            Panel(
                f"Enter comma-separated numbers, or leave blank to auto-generate.\n"
                f"[bold]{PRIMARY_COUNT}[/bold] primary numbers (1–{primary_max}), "
                f"[bold]{SECONDARY_COUNT}[/bold] secondary (1–{secondary_max}).\n"
                f"Example: [cyan]10, 23, 24, 43, 49[/cyan]  then  [magenta]3, 10[/magenta]",
                title=f"Line {i + 1}",
                border_style="cyan",
            )
        )

        raw_primary = Prompt.ask(f"Line {i + 1} primary", default="").strip()
        raw_secondary = Prompt.ask(f"Line {i + 1} secondary", default="").strip()

        if not raw_primary or not raw_secondary:
            auto_primary, auto_secondary = gen(primary_max, secondary_max)
            if not raw_primary:
                raw_primary = ", ".join(map(str, auto_primary))
                console.print(f"[dim]Generated primary:[/dim] [cyan]{raw_primary}[/cyan]")
            if not raw_secondary:
                raw_secondary = ", ".join(map(str, auto_secondary))
                console.print(f"[dim]Generated secondary:[/dim] [magenta]{raw_secondary}[/magenta]")

        primary = parse_numbers(raw_primary, PRIMARY_COUNT, primary_max, "primary")
        secondary = parse_numbers(raw_secondary, SECONDARY_COUNT, secondary_max, "secondary")
        lines.append((primary, secondary))

    return lines


def simulate(lines, primary_max, secondary_max):
    attempts = 0
    ticket_sets = [(set(p), set(s)) for p, s in lines]

    console.print("[bold]Simulating draws…[/bold] [dim](progress every 1,000,000 attempts)[/dim]")

    while True:
        drawn_primary, drawn_secondary = gen(primary_max, secondary_max)
        drawn_p, drawn_s = set(drawn_primary), set(drawn_secondary)
        attempts += 1

        for (primary, secondary), (p_set, s_set) in zip(lines, ticket_sets):
            primary_hits = len(drawn_p & p_set)
            secondary_hits = len(drawn_s & s_set)

            if is_jackpot(primary_hits, secondary_hits):
                years = attempts / DRAWS_PER_YEAR
                body = Text()
                body.append(f"Attempt #{attempts:,}\n\n", style="bold")
                body.append("Your line:   ", style="dim")
                body.append(format_line(primary, secondary) + "\n", style="cyan")
                body.append("Drawn:       ", style="dim")
                body.append(format_line(drawn_primary, drawn_secondary) + "\n", style="green")
                body.append("Matches:     ", style="dim")
                body.append(f"{primary_hits} + {secondary_hits}\n\n", style="bold yellow")
                body.append(
                    f"At {DRAWS_PER_YEAR} draws/year this would take about {years:,.2f} years.",
                    style="italic",
                )
                console.print(
                    Panel(body, title="[bold green]JACKPOT[/bold green]", border_style="green")
                )
                return attempts

        if attempts % 1_000_000 == 0:
            console.print(f"[red]Attempt #{attempts:,}[/red] — no jackpot yet")


def main():
    console.print(
        Panel.fit(
            "[bold]EuroJackpot simulator[/bold]\n"
            f"Match [cyan]{PRIMARY_COUNT}[/cyan] primary + [magenta]{SECONDARY_COUNT}[/magenta] secondary to win",
            border_style="yellow",
        )
    )

    line_count = IntPrompt.ask("How many lines", default=5)
    primary_max = IntPrompt.ask("Primary max number", default=DEFAULT_PRIMARY_MAX)
    secondary_max = IntPrompt.ask("Secondary max number", default=DEFAULT_SECONDARY_MAX)

    if primary_max < PRIMARY_COUNT:
        console.print(f"[red]Primary max must be at least {PRIMARY_COUNT}.[/red]")
        sys.exit(1)
    if secondary_max < SECONDARY_COUNT:
        console.print(f"[red]Secondary max must be at least {SECONDARY_COUNT}.[/red]")
        sys.exit(1)

    autogen_all = Confirm.ask("Autogenerate all lines?", default=True)
    lines = collect_lines(line_count, primary_max, secondary_max, autogen_all=autogen_all)
    print_ticket(lines)
    print_probability_info(lines, primary_max, secondary_max)
    simulate(lines, primary_max, secondary_max)


if __name__ == "__main__":
    main()
