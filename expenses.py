"""
Personal Expense Tracker with Charts
------------------------------------
Log what you spend from the terminal, check it against monthly budgets,
and turn it into a visual report.

  python3 expenses.py add 12.50 food "Chipotle"
  python3 expenses.py list --month 2026-11
  python3 expenses.py summary --month 2026-11
  python3 expenses.py budget food 250
  python3 expenses.py chart --month 2026-11
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime

EXPENSES_FILE = "expenses.csv"
BUDGETS_FILE = "budgets.json"
CHARTS_DIR = "charts"
CATEGORIES = ["rent", "bills", "food", "groceries", "transport", "entertainment", "shopping", "other"]
FIELDS = ["id", "date", "amount", "category", "description"]


# ---------- Reading and writing data ----------

def load_expenses(path=EXPENSES_FILE):
    """Read all expenses from the CSV file. Returns an empty list if the file doesn't exist yet."""
    if not os.path.exists(path):
        return []
    expenses = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            row["id"] = int(row["id"])
            row["amount"] = float(row["amount"])
            expenses.append(row)
    return expenses


def save_expenses(expenses, path=EXPENSES_FILE):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for e in expenses:
            writer.writerow({**e, "amount": f"{e['amount']:.2f}"})


def load_budgets(path=BUDGETS_FILE):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_budgets(budgets, path=BUDGETS_FILE):
    with open(path, "w") as f:
        json.dump(budgets, f, indent=2, sort_keys=True)


# ---------- Helpers ----------

def current_month():
    return date.today().strftime("%Y-%m")


def in_month(expense, month):
    """True if the expense's date (YYYY-MM-DD) is in the given month (YYYY-MM)."""
    return month is None or expense["date"].startswith(month)


def totals_by_category(expenses):
    totals = defaultdict(float)
    for e in expenses:
        totals[e["category"]] += e["amount"]
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))


def bar(fraction, width=20):
    """Draw a text progress bar, e.g. ██████░░░░ for 60%."""
    filled = min(width, round(fraction * width))
    return "█" * filled + "░" * (width - filled)


def valid_month(text):
    try:
        datetime.strptime(text, "%Y-%m")
        return text
    except ValueError:
        raise argparse.ArgumentTypeError("month must look like 2026-11")


def valid_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return text
    except ValueError:
        raise argparse.ArgumentTypeError("date must look like 2026-11-15")


def positive_amount(text):
    try:
        value = float(text.replace("$", "").replace(",", ""))
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number")
    if value <= 0:
        raise argparse.ArgumentTypeError("amount must be more than 0")
    return round(value, 2)


def category_name(text):
    text = text.lower().strip()
    if text not in CATEGORIES:
        raise argparse.ArgumentTypeError(f"category must be one of: {', '.join(CATEGORIES)}")
    return text


# ---------- Commands ----------

def cmd_add(args):
    expenses = load_expenses()
    new_id = max((e["id"] for e in expenses), default=0) + 1
    expense = {"id": new_id, "date": args.date or date.today().isoformat(),
               "amount": args.amount, "category": args.category, "description": args.description}
    expenses.append(expense)
    expenses.sort(key=lambda e: (e["date"], e["id"]))
    save_expenses(expenses)
    print(f"✅ Added #{new_id}: ${args.amount:.2f} for {args.category} ({args.description}) on {expense['date']}")

    # Warn right away if this expense pushed the category over its budget
    month = expense["date"][:7]
    budget = load_budgets().get(args.category)
    if budget:
        spent = sum(e["amount"] for e in expenses if in_month(e, month) and e["category"] == args.category)
        if spent > budget:
            print(f"⚠️  You are now ${spent - budget:.2f} OVER your ${budget:.0f} {args.category} budget for {month}.")
        elif spent > 0.8 * budget:
            print(f"🟡 Heads up: {spent / budget:.0%} of your {args.category} budget is used.")


def cmd_delete(args):
    expenses = load_expenses()
    remaining = [e for e in expenses if e["id"] != args.id]
    if len(remaining) == len(expenses):
        print(f"No expense with id #{args.id}.")
        return
    save_expenses(remaining)
    print(f"🗑️  Deleted expense #{args.id}.")


def cmd_list(args):
    rows = [e for e in load_expenses() if in_month(e, args.month)
            and (args.category is None or e["category"] == args.category)]
    if not rows:
        print("No expenses found.")
        return
    print(f"{'ID':>4}  {'DATE':<10}  {'AMOUNT':>9}  {'CATEGORY':<13}  DESCRIPTION")
    print("-" * 62)
    for e in rows[-args.last:] if args.last else rows:
        print(f"{e['id']:>4}  {e['date']:<10}  ${e['amount']:>8.2f}  {e['category']:<13}  {e['description']}")
    print("-" * 62)
    print(f"{len(rows)} expenses, total ${sum(e['amount'] for e in rows):,.2f}")


def cmd_summary(args):
    month = args.month or current_month()
    rows = [e for e in load_expenses() if in_month(e, month)]
    if not rows:
        print(f"No expenses for {month}.")
        return
    budgets = load_budgets()
    total = sum(e["amount"] for e in rows)
    days = len({e["date"] for e in rows})

    print(f"\n📊 Spending summary for {month}")
    print("=" * 66)
    print(f"{'CATEGORY':<14}{'SPENT':>10}{'SHARE':>8}   {'BUDGET':>8}  USED")
    for cat, spent in totals_by_category(rows).items():
        budget = budgets.get(cat)
        if budget:
            flag = "⚠️ over" if spent > budget else ""
            used = f"{bar(spent / budget, 12)} {spent / budget:>4.0%} {flag}"
            budget_text = f"${budget:>7.0f}"
        else:
            used, budget_text = "", "       -"
        print(f"{cat:<14}${spent:>9.2f}{spent / total:>8.0%}   {budget_text}  {used}")
    print("-" * 66)
    print(f"{'TOTAL':<14}${total:>9.2f}")
    print(f"\nDays with spending: {days}   |   Average per spending day: ${total / days:.2f}")

    print("\n💸 Biggest expenses (excluding rent):")
    for e in sorted((e for e in rows if e["category"] != "rent"), key=lambda e: e["amount"], reverse=True)[:3]:
        print(f"   ${e['amount']:>7.2f}  {e['description']} ({e['date']})")


def cmd_budget(args):
    budgets = load_budgets()
    if args.category and args.amount:
        budgets[args.category] = args.amount
        save_budgets(budgets)
        print(f"✅ Monthly budget for {args.category} set to ${args.amount:.0f}")
    elif not budgets:
        print("No budgets yet. Example: python3 expenses.py budget food 250")
    else:
        for cat, amount in budgets.items():
            print(f"  {cat:<14} ${amount:,.0f}/month")


def cmd_chart(args):
    try:
        import matplotlib
        matplotlib.use("Agg")  # draw to a file, no window needed
        import matplotlib.pyplot as plt
    except ImportError:
        sys.exit("Charts need matplotlib. Install it with:  pip3 install matplotlib")

    expenses = load_expenses()
    month = args.month or current_month()
    rows = [e for e in expenses if in_month(e, month)]
    if not rows:
        sys.exit(f"No expenses for {month}.")
    budgets = load_budgets()

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
    fig.suptitle(f"Spending report: {month}", fontsize=16, fontweight="bold")
    colors = {c: plt.cm.tab10(i) for i, c in enumerate(CATEGORIES)}

    # 1) Pie chart: where the money went this month
    cat_totals = totals_by_category(rows)
    # Only print % on slices of 5% or more so small slices don't overlap; names go in the legend
    axes[0].pie(cat_totals.values(), autopct=lambda p: f"{p:.0f}%" if p >= 5 else "", startangle=90,
                colors=[colors[c] for c in cat_totals], wedgeprops={"edgecolor": "white"}, pctdistance=0.75)
    axes[0].legend([f"{c} (${v:,.0f})" for c, v in cat_totals.items()], fontsize=8,
                   loc="center left", bbox_to_anchor=(0.92, 0.5))
    axes[0].set_title("Share by category")

    # 2) Stacked bars: every month side by side
    months = sorted({e["date"][:7] for e in expenses})
    bottom = [0.0] * len(months)
    for cat in CATEGORIES:
        values = [sum(e["amount"] for e in expenses if e["category"] == cat and e["date"].startswith(m))
                  for m in months]
        if any(values):
            axes[1].bar(months, values, bottom=bottom, label=cat, color=colors[cat])
            bottom = [b + v for b, v in zip(bottom, values)]
    axes[1].set_title("Monthly totals")
    axes[1].set_ylabel("Dollars ($)")
    axes[1].legend(fontsize=8, ncol=2)

    # 3) Line: cumulative spending through the month vs. total budget
    daily = defaultdict(float)
    for e in rows:
        daily[int(e["date"][8:10])] += e["amount"]
    last_day = max(daily)
    running, xs, ys = 0.0, [], []
    for day in range(1, last_day + 1):
        running += daily.get(day, 0)
        xs.append(day)
        ys.append(running)
    axes[2].plot(xs, ys, marker="o", markersize=3, label="Spent so far")
    if budgets:
        total_budget = sum(budgets.values())
        axes[2].axhline(total_budget, color="red", linestyle="--", label=f"Total budget ${total_budget:,.0f}")
    axes[2].set_title("Cumulative spending")
    axes[2].set_xlabel("Day of month")
    axes[2].set_ylabel("Dollars ($)")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    os.makedirs(CHARTS_DIR, exist_ok=True)
    path = os.path.join(CHARTS_DIR, f"report_{month}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"📈 Chart saved to {path}")
    if args.open:
        os.system(f'open "{path}"' if sys.platform == "darwin" else f'start "" "{path}"')


# ---------- Command-line setup ----------

def main():
    parser = argparse.ArgumentParser(description="Track expenses, budgets and charts from the terminal.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="add an expense")
    p.add_argument("amount", type=positive_amount)
    p.add_argument("category", type=category_name)
    p.add_argument("description")
    p.add_argument("--date", type=valid_date, help="YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("delete", help="delete an expense by id")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("list", help="show expenses")
    p.add_argument("--month", type=valid_month)
    p.add_argument("--category", type=category_name)
    p.add_argument("--last", type=int, help="only show the last N")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("summary", help="totals by category vs. budget")
    p.add_argument("--month", type=valid_month)
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("budget", help="set or show monthly budgets")
    p.add_argument("category", type=category_name, nargs="?")
    p.add_argument("amount", type=positive_amount, nargs="?")
    p.set_defaults(func=cmd_budget)

    p = sub.add_parser("chart", help="save a chart report as a PNG")
    p.add_argument("--month", type=valid_month)
    p.add_argument("--open", action="store_true", help="open the chart after saving")
    p.set_defaults(func=cmd_chart)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
