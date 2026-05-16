#!/usr/bin/env python3
"""
Analyze a pretty-printed FI dump (as produced by other reporting tools).

Reads a table with columns:
    #, Key, Summary, Assignee, Priority, Status, Case Status, Etrack Incident

and provides:
    - Report formats: executive, action, team, risk (or all)
    - Human-readable executive summary (quick stats, aging buckets, top owners)
  - Counts: total / with-etrack / without-etrack
  - Group-by breakdowns (status, priority, case-status, assignee, etrack)
  - Filter & list (e.g. only without-etrack, only Critical, by assignee)
  - Live cross-reference via Jira (current status, assignee, updated, age)
  - Stale FI detection (not updated for N days) via live lookup

Input:
    -i / --input FILE   path to the dump file (default: stdin)

Examples:
    j.fi.rpt.py -i /Users/me/op/dump.ready.1
    j.fi.rpt.py -i /Users/me/op/dump.ready.1 --human-summary --no-counts
    j.fi.rpt.py -i /Users/me/op/dump.ready.1 --report-format action
    j.fi.rpt.py -i /Users/me/op/dump.ready.1 --report-format all --no-counts
    cat dump.ready.1 | j.fi.rpt.py --without-etrack --list
    j.fi.rpt.py -i dump.ready.1 --group-by status,priority
    j.fi.rpt.py -i dump.ready.1 --live --stale-days 30 --list
"""

import argparse
import importlib.util
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# UTF-8-safe stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover
    tabulate = None


# --------------------------------------------------------------------------- #
# Parsing of the pretty-printed dump
# --------------------------------------------------------------------------- #

EXPECTED_COLUMNS = [
    "#", "Key", "Summary", "Assignee", "Priority",
    "Status", "Case Status", "Etrack Incident",
]


def _read_input(path: Optional[str]) -> str:
    if path and path != "-":
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return sys.stdin.read()


def _split_row(line: str) -> List[str]:
    # rows look like: | val | val | ... |
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    parts = [cell.strip() for cell in stripped.strip("|").split("|")]
    return parts


def parse_dump(text: str) -> List[Dict[str, str]]:
    """Parse a prettytable-style dump into a list of dicts keyed by column name.

    Some Summary cells can contain literal ``|`` characters (e.g. ``[EMEA] (|) [Flex]``)
    which makes a naive split produce too many cells. We resolve this by re-joining
    any overflow cells into the Summary column (assumed to be at index 2).
    """
    headers: List[str] = []
    summary_idx: int = -1
    rows: List[Dict[str, str]] = []

    for raw_line in text.splitlines():
        # Skip separator lines: +-----+-----+...
        if raw_line.lstrip().startswith("+"):
            continue
        cells = _split_row(raw_line)
        if not cells:
            continue

        if not headers:
            # First content row is the header.
            headers = cells
            try:
                summary_idx = headers.index("Summary")
            except ValueError:
                summary_idx = -1
            continue

        # Re-join overflow cells back into Summary when literal '|' is in the text.
        if len(cells) > len(headers) and summary_idx >= 0:
            overflow = len(cells) - len(headers)
            merged_summary = " | ".join(
                cells[summary_idx: summary_idx + overflow + 1]
            )
            cells = (
                cells[:summary_idx]
                + [merged_summary]
                + cells[summary_idx + overflow + 1:]
            )

        if len(cells) != len(headers):
            # Skip malformed lines.
            continue

        # Skip a row whose cells exactly equal the header text (some files repeat headers).
        if cells == headers:
            continue

        record = dict(zip(headers, cells))
        # Only keep rows that look like an FI issue.
        if re.match(r"^[A-Z][A-Z0-9_]*-\d+$", record.get("Key", "")):
            rows.append(record)

    return rows


def normalize_record(record: Dict[str, str]) -> Dict[str, str]:
    """Trim values and normalize empties to '-' (except Etrack Incident kept as '')."""
    out: Dict[str, str] = {}
    for key, value in record.items():
        value = (value or "").strip()
        if key == "Etrack Incident":
            out[key] = value
        else:
            out[key] = value if value else "-"
    return out


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #

def _matches_filter(record: Dict[str, str], filters: Dict[str, str]) -> bool:
    for field, expected in filters.items():
        actual = record.get(field, "").strip()
        # Substring, case-insensitive
        if expected.lower() not in actual.lower():
            return False
    return True


def apply_filters(
    records: List[Dict[str, str]],
    with_etrack: bool,
    without_etrack: bool,
    status: Optional[str],
    priority: Optional[str],
    case_status: Optional[str],
    assignee: Optional[str],
    assignee_manager: Optional[str],
    summary: Optional[str],
) -> List[Dict[str, str]]:
    filters: Dict[str, str] = {}
    if status:
        filters["Status"] = status
    if priority:
        filters["Priority"] = priority
    if case_status:
        filters["Case Status"] = case_status
    if assignee:
        filters["Assignee"] = assignee
    if assignee_manager:
        filters["Assignee Manager"] = assignee_manager
    if summary:
        filters["Summary"] = summary

    out: List[Dict[str, str]] = []
    for record in records:
        if with_etrack and not record.get("Etrack Incident", "").strip():
            continue
        if without_etrack and record.get("Etrack Incident", "").strip():
            continue
        if not _matches_filter(record, filters):
            continue
        out.append(record)
    return out


# --------------------------------------------------------------------------- #
# Counts & group-by
# --------------------------------------------------------------------------- #

GROUP_BY_FIELD_MAP = {
    "status": "Status",
    "priority": "Priority",
    "case-status": "Case Status",
    "case_status": "Case Status",
    "assignee": "Assignee",
    "etrack": "__etrack_presence__",
}


def _print_table(
    headers: List[str],
    rows: List[List[Any]],
    tablefmt: str = "simple",
) -> None:
    if not rows:
        print("  (no rows)")
        return
    if tabulate:
        print(tabulate(rows, headers=headers, tablefmt=tablefmt, disable_numparse=True))
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = " | ".join("{{:<{}}}".format(w) for w in widths)
    print(fmt.format(*headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def print_counts(records: List[Dict[str, str]]) -> None:
    total = len(records)
    with_et = sum(1 for r in records if r.get("Etrack Incident", "").strip())
    without_et = total - with_et

    def pct(n: int) -> str:
        return f"{(100.0 * n / total):.1f}%" if total else "0.0%"

    print("\n=== Counts ===")
    _print_table(
        ["Bucket", "Count", "%"],
        [
            ["Total", total, "100.0%"],
            ["With etrack", with_et, pct(with_et)],
            ["Without etrack", without_et, pct(without_et)],
        ],
    )


def _safe_pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return (100.0 * part) / whole


def _priority_rank(priority: str) -> int:
    p = (priority or "").strip().lower()
    if p in ("blocker", "p1"):
        return 5
    if p in ("critical", "p2"):
        return 4
    if p == "major":
        return 3
    if p in ("minor", "p3"):
        return 2
    return 1


def _bucketize_age(days: Optional[int]) -> str:
    if days is None:
        return "unknown"
    if days <= 7:
        return "0-7d"
    if days <= 14:
        return "8-14d"
    if days <= 30:
        return "15-30d"
    if days <= 60:
        return "31-60d"
    return "60d+"


def _render_kpi_line(label: str, value: str) -> str:
    return f"{label:<38} {value}"


def print_human_summary(records: List[Dict[str, str]]) -> None:
    """Print a compact executive summary optimized for quick reading."""
    total = len(records)
    if total == 0:
        print("\n=== Executive Summary ===")
        print("No records after filters.")
        return

    status_counter: Counter = Counter(r.get("Status", "-") for r in records)
    priority_counter: Counter = Counter(r.get("Priority", "-") for r in records)
    case_counter: Counter = Counter(r.get("Case Status", "-") for r in records)

    with_et = sum(1 for r in records if r.get("Etrack Incident", "").strip())
    without_et = total - with_et
    crit_blocker = sum(
        1
        for r in records
        if (r.get("Priority", "").strip().lower() in ("critical", "blocker", "p1", "p2"))
    )
    in_progress = status_counter.get("In Progress", 0)
    waiting = status_counter.get("Waiting on Support", 0)
    customer_wait = case_counter.get("Customer pending", 0)
    eng_pending = case_counter.get("Engineering pending", 0)

    updated_ages: List[int] = []
    created_ages: List[int] = []
    for r in records:
        up = _age_days(r.get("Updated", ""))
        cr = _age_days(r.get("Created", ""))
        if up is not None:
            updated_ages.append(up)
        if cr is not None:
            created_ages.append(cr)

    stale_7 = sum(1 for d in updated_ages if d >= 7)
    stale_14 = sum(1 for d in updated_ages if d >= 14)
    stale_30 = sum(1 for d in updated_ages if d >= 30)

    print("\n=== Executive Summary (Quick Stats) ===")
    print(_render_kpi_line("Total FIs", str(total)))
    print(_render_kpi_line("Etrack coverage", f"{with_et} ({_safe_pct(with_et, total):.1f}%)"))
    print(_render_kpi_line("Without etrack", f"{without_et} ({_safe_pct(without_et, total):.1f}%)"))
    print(_render_kpi_line("Critical/Blocker/P1/P2", f"{crit_blocker} ({_safe_pct(crit_blocker, total):.1f}%)"))
    print(_render_kpi_line("In Progress", f"{in_progress} ({_safe_pct(in_progress, total):.1f}%)"))
    print(_render_kpi_line("Waiting on Support", f"{waiting} ({_safe_pct(waiting, total):.1f}%)"))
    print(_render_kpi_line("Engineering pending", f"{eng_pending} ({_safe_pct(eng_pending, total):.1f}%)"))
    print(_render_kpi_line("Customer pending", f"{customer_wait} ({_safe_pct(customer_wait, total):.1f}%)"))
    if created_ages:
        print(_render_kpi_line("Created age range", f"{min(created_ages)}d to {max(created_ages)}d"))
    if updated_ages:
        print(_render_kpi_line("Days since update (max)", f"{max(updated_ages)}d"))
        print(_render_kpi_line("Stale >=7d / >=14d / >=30d", f"{stale_7} / {stale_14} / {stale_30}"))

    print("\n=== Aging Buckets (Created Age) ===")
    created_buckets: Counter = Counter(_bucketize_age(_age_days(r.get("Created", ""))) for r in records)
    bucket_order = ["0-7d", "8-14d", "15-30d", "31-60d", "60d+", "unknown"]
    _print_table(
        ["Bucket", "Count", "%"],
        [[b, created_buckets.get(b, 0), f"{_safe_pct(created_buckets.get(b, 0), total):.1f}%"] for b in bucket_order if created_buckets.get(b, 0)],
    )

    print("\n=== Top Workload Owners (Top 10 Assignees) ===")
    assignee_counter: Counter = Counter(r.get("Assignee", "-") for r in records)
    _print_table(
        ["Assignee", "Count", "%"],
        [[name, count, f"{_safe_pct(count, total):.1f}%"] for name, count in assignee_counter.most_common(10)],
    )

    print("\n=== Top Risk Owners (Top 10 Assignee Managers) ===")
    manager_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "high": 0, "stale": 0, "no_et": 0, "risk": 0})
    for r in records:
        manager = r.get("Assignee Manager", "-")
        if not manager:
            manager = "-"
        stat = manager_stats[manager]
        stat["total"] += 1
        if _priority_rank(r.get("Priority", "")) >= 4:
            stat["high"] += 1
        if not r.get("Etrack Incident", "").strip():
            stat["no_et"] += 1
        upd_age = _age_days(r.get("Updated", ""))
        if upd_age is not None and upd_age >= 7:
            stat["stale"] += 1

    for stat in manager_stats.values():
        stat["risk"] = (stat["high"] * 3) + (stat["stale"] * 2) + stat["no_et"]

    ranked_mgr = sorted(
        manager_stats.items(),
        key=lambda kv: (kv[1]["risk"], kv[1]["total"]),
        reverse=True,
    )
    _print_table(
        ["Assignee Manager", "Total", "HighPrio", "Stale>=7d", "NoEtrack", "RiskScore"],
        [
            [mgr, s["total"], s["high"], s["stale"], s["no_et"], s["risk"]]
            for mgr, s in ranked_mgr[:10]
        ],
    )

    print("\n=== Focus Areas ===")
    top_case = case_counter.most_common(3)
    top_pri = priority_counter.most_common(3)
    top_status = status_counter.most_common(3)
    if top_status:
        print("- Dominant statuses: " + ", ".join(f"{k} ({v})" for k, v in top_status))
    if top_case:
        print("- Dominant case statuses: " + ", ".join(f"{k} ({v})" for k, v in top_case))
    if top_pri:
        print("- Dominant priorities: " + ", ".join(f"{k} ({v})" for k, v in top_pri))
    if without_et > 0:
        print(f"- Action: backfill etrack for {without_et} issue(s) without etrack.")
    if stale_14 > 0:
        print(f"- Action: review {stale_14} issue(s) stale for >=14 days.")


def _join_keys(records: List[Dict[str, str]], limit: int = 25) -> str:
    keys = [r.get("Key", "-") for r in records if r.get("Key")]
    if len(keys) <= limit:
        return ",".join(keys)
    return ",".join(keys[:limit]) + f"... (+{len(keys) - limit} more)"


def print_action_report(records: List[Dict[str, str]], stale_days: int = 14) -> None:
    """Action-focused report similar to j.et.rpt.py action format."""
    print("\n=== Action Report ===")
    if not records:
        print("No records after filters.")
        return

    no_etrack = [r for r in records if not r.get("Etrack Incident", "").strip()]
    stale = [r for r in records if (_age_days(r.get("Updated", "")) or -1) >= stale_days]
    high_priority = [r for r in records if _priority_rank(r.get("Priority", "")) >= 4]
    customer_pending = [r for r in records if "customer pending" in r.get("Case Status", "").lower()]
    waiting_support = [r for r in records if "waiting on support" in r.get("Status", "").lower()]

    sections = [
        ("CRITICAL: Missing Etrack", no_etrack, "Backfill Etrack Incident and triage owner."),
        (f"HIGH: Stale >= {stale_days}d", stale, "Review updates and unblock next action."),
        ("HIGH: Critical/Blocker/P1/P2", high_priority, "Prioritize daily review until mitigated."),
        ("MEDIUM: Customer Pending", customer_pending, "Chase customer response / clarify blockers."),
        ("MEDIUM: Waiting on Support", waiting_support, "Validate whether workflow/status needs update."),
    ]

    rows = []
    for title, items, action in sections:
        rows.append([title, len(items), action])
    _print_table(["Category", "Count", "Recommended Action"], rows)

    for title, items, _ in sections:
        if not items:
            continue
        print(f"\n- {title}: {_join_keys(items)}")


def print_team_report(records: List[Dict[str, str]], stale_days: int = 7) -> None:
    """Team dashboard report similar to j.et.rpt.py team format."""
    print("\n=== Team Report ===")
    if not records:
        print("No records after filters.")
        return

    by_assignee: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "high": 0, "stale": 0, "no_et": 0, "cust_wait": 0, "score": 0}
    )
    for r in records:
        assignee = r.get("Assignee", "-") or "-"
        s = by_assignee[assignee]
        s["total"] += 1
        if _priority_rank(r.get("Priority", "")) >= 4:
            s["high"] += 1
        if (_age_days(r.get("Updated", "")) or -1) >= stale_days:
            s["stale"] += 1
        if not r.get("Etrack Incident", "").strip():
            s["no_et"] += 1
        if "customer pending" in r.get("Case Status", "").lower():
            s["cust_wait"] += 1

    for s in by_assignee.values():
        s["score"] = (s["high"] * 3) + (s["stale"] * 2) + s["no_et"] + s["cust_wait"]

    ranked = sorted(by_assignee.items(), key=lambda kv: (kv[1]["score"], kv[1]["total"]), reverse=True)
    _print_table(
        ["Assignee", "Total", "HighPrio", f"Stale>={stale_days}d", "NoEtrack", "CustPending", "ActionScore"],
        [[name, d["total"], d["high"], d["stale"], d["no_et"], d["cust_wait"], d["score"]] for name, d in ranked],
    )


def print_risk_report(records: List[Dict[str, str]], stale_days: int = 7) -> None:
    """Risk report similar to j.et.rpt.py risk format."""
    print("\n=== Risk Report ===")
    if not records:
        print("No records after filters.")
        return

    risk_rows: List[List[Any]] = []
    for r in records:
        prio_rank = _priority_rank(r.get("Priority", ""))
        upd_age = _age_days(r.get("Updated", ""))
        reasons: List[str] = []

        if prio_rank >= 4:
            reasons.append("high-priority")
        if upd_age is not None and upd_age >= stale_days:
            reasons.append(f"stale>={stale_days}d")
        if not r.get("Etrack Incident", "").strip():
            reasons.append("no-etrack")
        if r.get("Status", "").strip().lower() in ("open", "new"):
            reasons.append("open/new")

        if not reasons:
            continue

        # Keep the risk report focused on high-impact rows.
        if not (prio_rank >= 4 or (upd_age is not None and upd_age >= stale_days)):
            continue

        risk_rows.append([
            r.get("Key", "-"),
            r.get("Priority", "-"),
            r.get("Status", "-"),
            r.get("Assignee", "-"),
            r.get("Assignee Manager", "-"),
            f"{upd_age}" if upd_age is not None else "-",
            r.get("Etrack Incident", "") or "-",
            ", ".join(reasons),
        ])

    risk_rows.sort(
        key=lambda row: (
            -_priority_rank(str(row[1])),
            -(int(row[5]) if str(row[5]).isdigit() else -1),
        )
    )

    print(f"High-risk issues: {len(risk_rows)}")
    _print_table(
        ["Key", "Priority", "Status", "Assignee", "Assignee Manager", "UpdAge(d)", "Etrack", "Risk Reasons"],
        risk_rows,
    )


def run_report_format(records: List[Dict[str, str]], report_format: str, stale_days: Optional[int]) -> None:
    """Run report modes similar to j.et.rpt.py analyzer formats."""
    threshold = stale_days if stale_days is not None else 14

    if report_format in ("executive", "all"):
        print_human_summary(records)
    if report_format in ("action", "all"):
        print_action_report(records, stale_days=threshold)
    if report_format in ("team", "all"):
        print_team_report(records, stale_days=min(threshold, 7) if threshold > 0 else 7)
    if report_format in ("risk", "all"):
        print_risk_report(records, stale_days=min(threshold, 7) if threshold > 0 else 7)


def print_group_by(records: List[Dict[str, str]], group_keys: List[str]) -> None:
    for key in group_keys:
        field = GROUP_BY_FIELD_MAP.get(key.strip().lower())
        if not field:
            print(f"\n(group-by '{key}' is not supported; "
                  f"valid: {', '.join(GROUP_BY_FIELD_MAP)})")
            continue

        print(f"\n=== Group by: {key} ===")
        counter: Counter = Counter()
        for record in records:
            if field == "__etrack_presence__":
                counter["has-etrack" if record.get("Etrack Incident", "").strip()
                        else "no-etrack"] += 1
            else:
                counter[record.get(field, "-") or "-"] += 1

        total = sum(counter.values()) or 1
        rows = [
            [bucket, count, f"{(100.0 * count / total):.1f}%"]
            for bucket, count in counter.most_common()
        ]
        _print_table(["Bucket", "Count", "%"], rows)


# --------------------------------------------------------------------------- #
# Live Jira lookup (uses JiraReportClient from j.et.rpt.py)
# --------------------------------------------------------------------------- #

def _load_jira_report_client():
    """Import JiraReportClient from sibling file 'j.et.rpt.py' (dotted name)."""
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "j.et.rpt.py")
    if not os.path.exists(src):
        raise RuntimeError(f"Cannot find j.et.rpt.py next to this script ({src})")
    spec = importlib.util.spec_from_file_location("_j_et_rpt", src)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.JiraReportClient


def _parse_iso_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    # Jira timestamps look like 2026-04-12T08:15:30.000+0000
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None


def _age_days(value: str) -> Optional[int]:
    ts = _parse_iso_ts(value)
    if not ts:
        return None
    return max(0, int((datetime.now(timezone.utc) - ts).total_seconds() // 86400))


def _opt_name(field: Any) -> str:
    if not field:
        return "-"
    if isinstance(field, dict):
        for k in ("displayName", "name", "value"):
            if field.get(k):
                return str(field[k])
    return str(field)


def fetch_live(records: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    keys = [r["Key"] for r in records if r.get("Key")]
    if not keys:
        return {}

    ClientCls = _load_jira_report_client()
    client = ClientCls()

    fields = ["status", "resolution", "assignee", "priority", "updated", "created"]
    print(f"Fetching live data for {len(keys)} issue(s)...", file=sys.stderr)
    issues = client.fetch_issues_by_keys(keys, fields)

    live: Dict[str, Dict[str, Any]] = {}
    for issue in issues:
        key = issue.get("key") or "-"
        f = issue.get("fields", {}) or {}
        updated = f.get("updated") or ""
        live[key] = {
            "status": _opt_name(f.get("status")),
            "resolution": _opt_name(f.get("resolution")),
            "assignee": _opt_name(f.get("assignee")),
            "priority": _opt_name(f.get("priority")),
            "updated": updated,
            "updated_age_days": _age_days(updated),
            "created": f.get("created") or "",
            "created_age_days": _age_days(f.get("created") or ""),
        }
    return live


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #

def print_list(
    records: List[Dict[str, str]],
    live: Optional[Dict[str, Dict[str, Any]]],
    stale_days: Optional[int],
    summary_len: int,
    table_format: str,
) -> None:
    print(f"\n=== List ({len(records)} issue(s)) ===")

    # If tabulate is unavailable, table output gets hard to read on narrow terminals.
    # Fall back to a record-oriented format to keep all values visible.
    if tabulate is None:
        for idx, r in enumerate(records, 1):
            key = r.get("Key", "-")
            summary_text = r.get("Summary", "-")
            summary_out = _truncate(summary_text, summary_len) if summary_len > 0 else summary_text

            print(f"[{idx}] {key}")
            if live is None:
                upd_age = _age_days(r.get("Updated", ""))
                stale = ""
                if stale_days is not None and upd_age is not None and upd_age >= stale_days:
                    stale = f"YES (>={stale_days}d)"
                print(f"  Status: {r.get('Status', '-')}")
                print(f"  Priority: {r.get('Priority', '-')}")
                print(f"  Assignee: {r.get('Assignee', '-')}")
                print(f"  Assignee Manager: {r.get('Assignee Manager', '-')}")
                print(f"  Case Status: {r.get('Case Status', '-')}")
                print(f"  Etrack: {r.get('Etrack Incident', '') or '-'}")
                if stale_days is not None:
                    print(f"  Updated(age d): {upd_age if upd_age is not None else '-'}")
                    print(f"  Stale?: {stale}")
            else:
                info = live.get(key) or {}
                age = info.get("updated_age_days")
                stale = ""
                if stale_days is not None and age is not None and age >= stale_days:
                    stale = f"YES (>={stale_days}d)"
                print(f"  Status(live): {info.get('status', '-')}")
                print(f"  Assignee(live): {info.get('assignee', '-')}")
                print(f"  Updated(age d): {age if age is not None else '-'}")
                print(f"  Case Status: {r.get('Case Status', '-')}")
                print(f"  Etrack: {r.get('Etrack Incident', '') or '-'}")
                print(f"  Stale?: {stale}")
            print(f"  Summary: {summary_out}")
            print()
        return

    if live is None:
        include_stale = stale_days is not None
        headers = ["Key", "Status", "Priority", "Assignee", "Assignee Manager", "Case Status", "Etrack"]
        if include_stale:
            headers.extend(["Updated(age d)", "Stale?"])
        headers.append("Summary")
        rows = []
        for r in records:
            row = [
                r.get("Key", "-"),
                r.get("Status", "-"),
                r.get("Priority", "-"),
                r.get("Assignee", "-"),
                r.get("Assignee Manager", "-"),
                r.get("Case Status", "-"),
                r.get("Etrack Incident", "") or "-",
            ]
            if include_stale:
                upd_age = _age_days(r.get("Updated", ""))
                stale = ""
                if upd_age is not None and stale_days is not None and upd_age >= stale_days:
                    stale = f"YES (>={stale_days}d)"
                row.extend([
                    f"{upd_age}" if upd_age is not None else "-",
                    stale,
                ])
            summary_text = r.get("Summary", "-")
            row.append(_truncate(summary_text, summary_len) if summary_len > 0 else summary_text)
            rows.append(row)
        _print_table(headers, rows, tablefmt=table_format)
        return

    headers = ["Key", "Status(live)", "Assignee(live)", "Updated(age d)",
               "Case Status", "Etrack", "Stale?", "Summary"]
    rows = []
    for r in records:
        key = r.get("Key", "-")
        info = live.get(key) or {}
        age = info.get("updated_age_days")
        stale = ""
        if stale_days is not None and age is not None and age >= stale_days:
            stale = f"YES (>={stale_days}d)"
        summary_text = r.get("Summary", "-")
        rows.append([
            key,
            info.get("status", "-"),
            info.get("assignee", "-"),
            f"{age}" if age is not None else "-",
            r.get("Case Status", "-"),
            r.get("Etrack Incident", "") or "-",
            stale,
            _truncate(summary_text, summary_len) if summary_len > 0 else summary_text,
        ])
    _print_table(headers, rows, tablefmt=table_format)


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze an FI dump table (with/without etrack, group-by, live cross-reference).",
    )
    parser.add_argument("-i", "--input", default=None,
                        help="Path to dump file (default: stdin). Use '-' for stdin.")

    # Filters
    parser.add_argument("-w", "--with-etrack", action="store_true",
                        help="Keep only FIs that have an Etrack Incident.")
    parser.add_argument("-W", "--without-etrack", action="store_true",
                        help="Keep only FIs that do NOT have an Etrack Incident.")
    parser.add_argument("-s", "--status", default=None,
                        help="Filter by Status (substring, case-insensitive).")
    parser.add_argument("-p", "--priority", default=None,
                        help="Filter by Priority (substring, case-insensitive).")
    parser.add_argument("-c", "--case-status", default=None,
                        help="Filter by Case Status (substring, case-insensitive).")
    parser.add_argument("-a", "--assignee", default=None,
                        help="Filter by Assignee (substring, case-insensitive).")
    parser.add_argument(
        "-A",
        "--assignee-manager",
        "--assignee_manager",
        "--assignee_managar",
        dest="assignee_manager",
        default=None,
        help="Filter by Assignee Manager (substring, case-insensitive).",
    )
    parser.add_argument("-m", "--summary", default=None,
                        help="Filter by Summary (substring, case-insensitive).")

    # Output controls
    parser.add_argument("-l", "--list", action="store_true",
                        help="Print one line per filtered issue.")
    parser.add_argument("-g", "--group-by", default="",
                        help="Comma-separated breakdowns. "
                             "Valid: status, priority, case-status, assignee, etrack.")
    parser.add_argument("-H", "--human-summary", action="store_true",
                        help="Print a compact human-readable executive summary with easy-to-grab stats.")
    parser.add_argument("-r", "--report-format", choices=["executive", "action", "team", "risk", "all"],
                        default=None,
                        help="Additional report formats inspired by j.et.rpt.py analyzer modes.")
    parser.add_argument("-n", "--no-counts", action="store_true",
                        help="Suppress the default Counts section.")
    parser.add_argument(
        "-S",
        "--summary-len",
        type=int,
        default=0,
        help="Summary truncate length for --list (0 = no truncation).",
    )
    parser.add_argument(
        "-t",
        "--table-format",
        choices=["github", "simple", "grid", "plain", "psql"],
        default="github",
        help="Table format used by --list output.",
    )

    # Live lookup
    parser.add_argument("-L", "--live", action="store_true",
                        help="Cross-reference with live Jira (requires JIRA_SERVER_NAME, JIRA_ACC_TOKEN).")
    parser.add_argument("-d", "--stale-days", type=int, default=None,
                        help="Flag issues not updated for N+ days. Uses dump Updated timestamp unless --live is set.")

    args = parser.parse_args()

    if args.with_etrack and args.without_etrack:
        print("Error: --with-etrack and --without-etrack are mutually exclusive.", file=sys.stderr)
        return 2

    try:
        text = _read_input(args.input)
    except OSError as exc:
        print(f"Error reading input: {exc}", file=sys.stderr)
        return 1

    raw_records = parse_dump(text)
    if not raw_records:
        print("No FI rows found in input. Is this a prettytable-style dump?", file=sys.stderr)
        return 1

    records = [normalize_record(r) for r in raw_records]
    filtered = apply_filters(
        records,
        with_etrack=args.with_etrack,
        without_etrack=args.without_etrack,
        status=args.status,
        priority=args.priority,
        case_status=args.case_status,
        assignee=args.assignee,
        assignee_manager=args.assignee_manager,
        summary=args.summary,
    )

    print(f"Parsed: {len(records)} row(s) | After filters: {len(filtered)} row(s)")

    if args.human_summary:
        print_human_summary(filtered)

    if args.report_format:
        run_report_format(filtered, args.report_format, args.stale_days)

    if not args.no_counts:
        print_counts(filtered)

    group_keys = [g.strip() for g in args.group_by.split(",") if g.strip()]
    if group_keys:
        print_group_by(filtered, group_keys)

    live: Optional[Dict[str, Dict[str, Any]]] = None
    if args.live:
        try:
            live = fetch_live(filtered)
        except Exception as exc:  # noqa: BLE001 - surface anything from import/fetch
            print(f"Warning: live fetch failed: {exc}", file=sys.stderr)
            live = {}

        if args.stale_days is not None and live:
            stale = []
            for r in filtered:
                info = live.get(r["Key"]) or {}
                age = info.get("updated_age_days")
                if age is not None and age >= args.stale_days:
                    stale.append((r["Key"], age, info.get("status", "-"),
                                  info.get("assignee", "-"), r.get("Case Status", "-"),
                                  r.get("Etrack Incident", "") or "-"))
            print(f"\n=== Stale FIs (updated >= {args.stale_days}d ago): {len(stale)} ===")
            stale.sort(key=lambda x: x[1], reverse=True)
            _print_table(
                ["Key", "Age(d)", "Status", "Assignee", "Case Status", "Etrack"],
                [list(row) for row in stale],
            )

    if args.stale_days is not None and not args.live:
        stale = []
        for r in filtered:
            age = _age_days(r.get("Updated", ""))
            if age is not None and age >= args.stale_days:
                stale.append((
                    r.get("Key", "-"),
                    age,
                    r.get("Status", "-"),
                    r.get("Assignee", "-"),
                    r.get("Case Status", "-"),
                    r.get("Etrack Incident", "") or "-",
                ))
        print(f"\n=== Stale FIs from dump Updated (>= {args.stale_days}d): {len(stale)} ===")
        stale.sort(key=lambda x: x[1], reverse=True)
        _print_table(
            ["Key", "Age(d)", "Status", "Assignee", "Case Status", "Etrack"],
            [list(row) for row in stale],
        )

    if args.list:
        print_list(filtered, live, args.stale_days, args.summary_len, args.table_format)

    return 0


if __name__ == "__main__":
    sys.exit(main())
