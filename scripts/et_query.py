#!/usr/bin/env python3

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional, Sequence

DEFAULT_FIELDS = [
    "INCIDENT",
    "ASSIGNED_TO",
    "STATE",
    "TYPE",
    "VERSION",
    "COMPONENT",
    "SEVERITY",
    "CHANGED_BY",
    "CUSTOMER",
    "ABSTRACT",
]

SEP_RE = re.compile(r"[\s,]+")
VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EtQueryError(Exception):
    pass


def _split_tokens(raw: str) -> List[str]:
    if not raw:
        return []
    return [token.strip() for token in SEP_RE.split(raw) if token.strip()]


def _normalize_fields(raw: Optional[str], option_name: str) -> List[str]:
    if not raw:
        return []
    fields = [field.strip().upper() for field in raw.split(",") if field.strip()]
    if not fields:
        return []
    invalid = [field for field in fields if not VALID_IDENTIFIER_RE.match(field)]
    if invalid:
        raise EtQueryError(
            f"Invalid {option_name} value(s): {', '.join(invalid)}. "
            "Use comma-separated SQL column names like INCIDENT,COMPONENT."
        )
    return fields


def _parse_incidents_from_file(path: str) -> List[str]:
    incidents: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                incidents.extend(_split_tokens(line.strip()))
    except OSError as exc:
        raise EtQueryError(f"Unable to read file '{path}': {exc}") from exc
    return incidents


def _parse_incidents_from_stdin() -> List[str]:
    if sys.stdin.isatty():
        return []
    content = sys.stdin.read()
    return _split_tokens(content)


def _normalize_incidents(raw_values: Sequence[str]) -> List[str]:
    unique: List[str] = []
    seen = set()
    invalid: List[str] = []

    for value in raw_values:
        token = value.strip()
        if not token:
            continue
        if not token.isdigit():
            invalid.append(token)
            continue
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)

    if invalid:
        raise EtQueryError(
            f"Invalid incident value(s): {', '.join(invalid)}. "
            "Incident IDs must be numeric."
        )
    return unique


def _resolve_fields(args: argparse.Namespace) -> List[str]:
    include_fields = _normalize_fields(args.fields, "--fields") if args.fields else DEFAULT_FIELDS.copy()
    exclude_fields = set(_normalize_fields(args.exclude, "--exclude"))

    result = [field for field in include_fields if field not in exclude_fields]
    if not result:
        raise EtQueryError("No fields remain after applying --exclude.")
    return result


def _resolve_output_columns(fields: List[str], args: argparse.Namespace) -> List[str]:
    include_cols = _normalize_fields(args.include_cols, "--include-cols")
    exclude_cols = set(_normalize_fields(args.exclude_cols, "--exclude-cols"))

    if include_cols:
        unknown = [column for column in include_cols if column not in fields]
        if unknown:
            raise EtQueryError(
                "Unknown --include-cols value(s): "
                f"{', '.join(unknown)}. Available fields: {', '.join(fields)}"
            )
        selected = include_cols
    else:
        selected = fields.copy()

    result = [column for column in selected if column not in exclude_cols]
    if not result:
        raise EtQueryError("No output columns remain after applying include/exclude column filters.")
    return result


def _safe_sql_identifier(identifier: str) -> str:
    if not VALID_IDENTIFIER_RE.match(identifier):
        raise EtQueryError(f"Invalid SQL identifier: {identifier}")
    return identifier.upper()


def _safe_sql_incident(incident: str) -> str:
    if not incident.isdigit():
        raise EtQueryError(f"Invalid incident for SQL: {incident}")
    return str(int(incident))


def _build_sql(fields: List[str], incidents: List[str]) -> str:
    safe_fields = [_safe_sql_identifier(field) for field in fields]
    safe_incidents = [_safe_sql_incident(incident) for incident in incidents]
    field_list = ", ".join(safe_fields)
    incident_list = ", ".join(safe_incidents)
    return (
        f"SELECT DISTINCT {field_list} "
        f"FROM INCIDENT_VIEW WHERE INCIDENT IN ({incident_list})"
    )


def _resolve_esql_command() -> List[str]:
    local_esql = shutil.which("esql")
    if local_esql:
        return [local_esql]

    remote_host = os.getenv("RMTCMD_HOST")
    if remote_host:
        return ["ssh", remote_host, "esql"]

    raise EtQueryError("esql command not found. Install esql or set RMTCMD_HOST for SSH fallback.")


def _run_esql(sql: str, timeout: int) -> str:
    cmd = _resolve_esql_command()
    try:
        result = subprocess.run(
            cmd,
            input=sql,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise EtQueryError(f"esql query timed out after {timeout}s") from exc
    except OSError as exc:
        raise EtQueryError(f"Unable to execute esql: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        message = stderr or stdout or f"esql failed with exit code {result.returncode}"
        raise EtQueryError(message)

    return result.stdout


def _should_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("---") or stripped.startswith("===") or stripped.startswith("+"):
        return True

    lower = stripped.lower()
    if "row selected" in lower or "rows selected" in lower:
        return True
    if lower.startswith("warning:"):
        return True
    return False


def _parse_esql_output(raw_output: str, fields: List[str]) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    expected_cols = len(fields)

    for line in raw_output.splitlines():
        if _should_skip_line(line):
            continue

        stripped = line.strip()

        if "|" in stripped:
            parts = [part.strip() for part in re.split(r"\|", stripped)]
            parts = [part for part in parts if part != ""]
        else:
            parts = stripped.split("\t")
            parts = [part.strip() for part in parts]

        if not parts:
            continue

        if len(parts) == expected_cols and [part.upper() for part in parts] == fields:
            continue

        if len(parts) < expected_cols:
            parts.extend([""] * (expected_cols - len(parts)))
        elif len(parts) > expected_cols:
            head = parts[: expected_cols - 1]
            tail = " ".join(parts[expected_cols - 1 :]).strip()
            parts = head + [tail]

        record = {fields[idx]: parts[idx] for idx in range(expected_cols)}
        records.append(record)

    return records


def _format_table(records: List[Dict[str, str]], columns: List[str]) -> str:
    if not records:
        return "No rows found"

    widths = {column: len(column) for column in columns}
    for record in records:
        for column in columns:
            value = str(record.get(column, ""))
            widths[column] = min(max(widths[column], len(value)), 120)

    separator = "+" + "+".join("-" * (widths[column] + 2) for column in columns) + "+"
    header = "| " + " | ".join(column.ljust(widths[column]) for column in columns) + " |"

    lines = [separator, header, separator]
    for record in records:
        row = []
        for column in columns:
            value = str(record.get(column, ""))
            if len(value) > widths[column]:
                value = value[: max(0, widths[column] - 3)] + "..."
            row.append(value.ljust(widths[column]))
        lines.append("| " + " | ".join(row) + " |")
    lines.append(separator)
    return "\n".join(lines)


def _format_csv(records: List[Dict[str, str]], columns: List[str]) -> str:
    if not records:
        return ""
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows([{column: row.get(column, "") for column in columns} for row in records])
    return buffer.getvalue().rstrip("\n")


def _format_json(records: List[Dict[str, str]], columns: List[str]) -> str:
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(records),
        "columns": columns,
        "rows": [{column: row.get(column, "") for column in columns} for row in records],
    }
    return json.dumps(payload, indent=2)


def _format_markdown(records: List[Dict[str, str]], columns: List[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, divider]
    for row in records:
        escaped = [str(row.get(column, "")).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def _write_output(content: str, output_path: Optional[str]) -> None:
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(content)
                if content and not content.endswith("\n"):
                    handle.write("\n")
        except OSError as exc:
            raise EtQueryError(f"Unable to write output file '{output_path}': {exc}") from exc
    else:
        print(content)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query Etrack incidents and render table/CSV/JSON/Markdown output.",
        epilog=(
            "Examples:\n"
            "  et_query.py --incidents 4221396,4221397,4221398\n"
            "  et_query.py 4221396 4221397 --exclude COMPONENT\n"
            "  cat ids.txt | et_query.py --fields INCIDENT,STATE,ABSTRACT\n"
            "  et_query.py --incidents 4221396,4221397 --format json --output et.json\n"
            "  et_query.py --incidents 4221396,4221397 --include-cols INCIDENT,STATE"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("incident_ids", nargs="*", help="Incident IDs, e.g. 4221396 4221397")
    parser.add_argument(
        "--incidents",
        help="Comma/space-separated incident IDs, e.g. 4221396,4221397",
    )
    parser.add_argument("-f", "--file", help="File containing incident IDs")

    parser.add_argument(
        "--fields",
        help=(
            "Comma-separated query fields. "
            "Default: INCIDENT,ASSIGNED_TO,STATE,TYPE,VERSION,COMPONENT,SEVERITY,CHANGED_BY,CUSTOMER,ABSTRACT"
        ),
    )
    parser.add_argument("--exclude", help="Comma-separated fields to remove from selected fields")

    parser.add_argument("--include-cols", help="Comma-separated output columns to include")
    parser.add_argument("--exclude-cols", help="Comma-separated output columns to exclude")

    parser.add_argument(
        "--format",
        choices=["table", "csv", "json", "markdown"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument("--output", help="Write formatted output to file instead of stdout")

    parser.add_argument("--timeout", type=int, default=120, help="esql timeout in seconds (default: 120)")
    parser.add_argument("--show-query", action="store_true", help="Print generated SQL query to stderr")
    parser.add_argument("--verbose", action="store_true", help="Print progress details to stderr")

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        input_tokens: List[str] = []
        input_tokens.extend(args.incident_ids)

        if args.incidents:
            input_tokens.extend(_split_tokens(args.incidents))
        if args.file:
            input_tokens.extend(_parse_incidents_from_file(args.file))

        stdin_tokens = _parse_incidents_from_stdin()
        if stdin_tokens:
            input_tokens.extend(stdin_tokens)

        incidents = _normalize_incidents(input_tokens)
        if not incidents:
            raise EtQueryError(
                "No incidents provided. Use positional IDs, --incidents, --file, or stdin."
            )

        fields = _resolve_fields(args)
        output_columns = _resolve_output_columns(fields, args)

        sql = _build_sql(fields, incidents)
        if args.show_query:
            print(f"SQL: {sql}", file=sys.stderr)

        if args.verbose:
            print(f"Querying {len(incidents)} incident(s)...", file=sys.stderr)

        raw_output = _run_esql(sql, timeout=args.timeout)
        records = _parse_esql_output(raw_output, fields)

        projected_records = [
            {column: record.get(column, "") for column in output_columns} for record in records
        ]

        if args.format == "table":
            formatted = _format_table(projected_records, output_columns)
        elif args.format == "csv":
            formatted = _format_csv(projected_records, output_columns)
        elif args.format == "json":
            formatted = _format_json(projected_records, output_columns)
        else:
            formatted = _format_markdown(projected_records, output_columns)

        _write_output(formatted, args.output)

        summary = f"Total rows: {len(projected_records)}"
        if args.output:
            print(summary)
            if args.verbose:
                print(f"Wrote {args.format} output to {args.output}", file=sys.stderr)
        else:
            print(summary)

        return 0

    except EtQueryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
