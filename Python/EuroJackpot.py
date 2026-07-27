# Eurojackpot
import math
import random
import sys

from utils.textStyle import C as c

PRIMARY_COUNT = 5
SECONDARY_COUNT = 2
DEFAULT_PRIMARY_MAX = 50
DEFAULT_SECONDARY_MAX = 12  # EuroJackpot euro numbers are 1–12 since 2022
DRAWS_PER_YEAR = 104  # typically Tue + Fri


def ask_int(prompt, default):
    raw = input(f"{prompt} [default {default}]: ").strip()
    return int(raw) if raw else default


def ask_yes_no(prompt, default_yes=True):
    hint = "Y/n" if default_yes else "y/N"
    raw = input(f"{prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default_yes
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    print("Please answer yes or no.")
    return ask_yes_no(prompt, default_yes)


def gen(primary_max, secondary_max):
    return (
        random.sample(range(1, primary_max + 1), PRIMARY_COUNT),
        random.sample(range(1, secondary_max + 1), SECONDARY_COUNT),
    )


def parse_numbers(raw, count, max_n, label):
    """Parse comma-separated numbers; return a sorted unique list or exit on error."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != count:
        print(f"Invalid {label} length (need {count} numbers).")
        sys.exit(1)

    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        print(f"Invalid {label}: all values must be integers.")
        sys.exit(1)

    if any(n < 1 or n > max_n for n in numbers):
        print(f"Invalid {label}: numbers must be between 1 and {max_n}.")
        sys.exit(1)

    if len(set(numbers)) != len(numbers):
        print(f"Invalid {label}: duplicates are not allowed.")
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

    print(f"""
{c.WARNING}--- Probability (jackpot: {PRIMARY_COUNT}+{SECONDARY_COUNT}) ---{c.ENDC}
Setup:              {PRIMARY_COUNT} from 1–{primary_max}, {SECONDARY_COUNT} from 1–{secondary_max}
Total combinations: {total:,}
Lines on ticket:    {line_count} ({unique_lines} unique)
Single-line odds:   {format_odds(1 / p_single)}  ({format_probability(p_single)})
Your ticket odds:   {format_odds(1 / p_ticket)}  ({format_probability(p_ticket)})
Expected draws:     {expected_draws:,.1f}
Expected years:     {expected_years:,.2f}  ({DRAWS_PER_YEAR} draws/year)
""")


def collect_lines(line_count, primary_max, secondary_max, autogen_all=False):
    lines = []
    for i in range(line_count):
        if autogen_all:
            primary, secondary = gen(primary_max, secondary_max)
            print(
                f"{c.OKCYAN}Line {i + 1}: "
                f"{', '.join(map(str, primary))} | {', '.join(map(str, secondary))}"
                f"{c.ENDC}"
            )
            lines.append((primary, secondary))
            continue

        print(f"""
{c.OKCYAN}
Enter the numbers you want comma separated. Or leave blank for auto generated lines.
{PRIMARY_COUNT + SECONDARY_COUNT} ({PRIMARY_COUNT}+{SECONDARY_COUNT}) numbers per line.
Primary: {PRIMARY_COUNT} numbers between 1 and {primary_max}
Secondary: {SECONDARY_COUNT} numbers between 1 and {secondary_max}
Example primary:    10, 23, 24, 43, 49
Example secondary:  3, 10
{c.ENDC}""")

        raw_primary = input(f"Line {i + 1} primary: ").strip()
        raw_secondary = input(f"Line {i + 1} secondary: ").strip()

        if not raw_primary or not raw_secondary:
            auto_primary, auto_secondary = gen(primary_max, secondary_max)
            if not raw_primary:
                raw_primary = ", ".join(map(str, auto_primary))
                print(f"Generated primary: {raw_primary}")
            if not raw_secondary:
                raw_secondary = ", ".join(map(str, auto_secondary))
                print(f"Generated secondary: {raw_secondary}")

        primary = parse_numbers(raw_primary, PRIMARY_COUNT, primary_max, "primary")
        secondary = parse_numbers(raw_secondary, SECONDARY_COUNT, secondary_max, "secondary")
        lines.append((primary, secondary))

    return lines


def simulate(lines, primary_max, secondary_max):
    attempts = 0
    ticket_sets = [(set(p), set(s)) for p, s in lines]

    while True:
        drawn_primary, drawn_secondary = gen(primary_max, secondary_max)
        drawn_p, drawn_s = set(drawn_primary), set(drawn_secondary)
        attempts += 1

        for (primary, secondary), (p_set, s_set) in zip(lines, ticket_sets):
            primary_hits = len(drawn_p & p_set)
            secondary_hits = len(drawn_s & s_set)

            if is_jackpot(primary_hits, secondary_hits):
                years = attempts / DRAWS_PER_YEAR
                print(
                    f"{c.OKGREEN}[Attempt #{attempts}] You have numbers: "
                    f"{primary} | {secondary}"
                )
                print(
                    f"[Attempt #{attempts}] The numbers pulled: "
                    f"{drawn_primary} | {drawn_secondary}"
                )
                print(
                    f"[Attempt #{attempts}] Correctness:        "
                    f"{primary_hits} | {secondary_hits}"
                )
                print(
                    f"[Attempt #{attempts}] In reality, this would take about "
                    f"{years:.2f} years to achieve ({DRAWS_PER_YEAR} draws/year)."
                    f"{c.ENDC}"
                )
                return attempts

        if attempts % 1_000_000 == 0:
            print(f"{c.FAIL}[Attempt #{attempts}] No success yet{c.ENDC}")


def main():
    line_count = ask_int("How many lines", 5)
    primary_max = ask_int("Primary max number", DEFAULT_PRIMARY_MAX)
    secondary_max = ask_int("Secondary max number", DEFAULT_SECONDARY_MAX)

    if primary_max < PRIMARY_COUNT:
        print(f"Primary max must be at least {PRIMARY_COUNT}.")
        sys.exit(1)
    if secondary_max < SECONDARY_COUNT:
        print(f"Secondary max must be at least {SECONDARY_COUNT}.")
        sys.exit(1)

    autogen_all = ask_yes_no("Autogenerate all lines?", default_yes=True)
    lines = collect_lines(line_count, primary_max, secondary_max, autogen_all=autogen_all)
    print_probability_info(lines, primary_max, secondary_max)
    simulate(lines, primary_max, secondary_max)


if __name__ == "__main__":
    main()
