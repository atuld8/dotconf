#!/usr/bin/env python3
"""
Python replacement for et_data_in_col.awk for data WITHOUT headers.

This script processes tab-separated (TSV) data that does not include a header row.
Headers are supplied via --headers (or loaded from last-run cache metadata).

The key difference from equery_formatter.py is:
- equery_formatter.py expects the first line to be headers (from equery output)
- esql_formatter.py requires headers via --headers (or --last cache)

Supports LOCAL and REMOTE execution, last-run cache, column filters, and sorting.

USAGE:
    esql_formatter.py SOURCE --headers HEADERS [options]

INPUT SOURCE (one required):
    -r, --query       Run esql -r <queryname> (auto-saves last-run cache)
    -e, --command     Run a shell command that emits TSV rows
    -f, --file        Read TSV from a file
    -T, --stdin       Read TSV from stdin
    -L, --last        Reuse last --query/--command fetch (no re-query)
    -M, --last-info   Show last-run cache metadata and exit
    -l, --list-headers  List column names for filters (-F) and output (-c)

HEADERS:
    -H, --headers     Comma-separated column names in data order
                      Optional width: INCIDENT:20,STATE:30,ABSTRACT
                      Optional with -L when cache stores headers

FILTER (-F / --filter include, -X / --exclude-filter exclude):
    See -G / --filter-help for full syntax reference.
    COL=VAL             include exact match
    COL!=VAL            exclude exact match
    COL~PAT             include substring (%% wildcards optional)
    COL!~PAT            exclude substring
    COL=!X_1            exclude exact shorthand (_ in token)
    COL=!X              exclude substring shorthand (no _ in token)
    COL in (A,B,C)      OR include list (exclude list with -X)
    COL like %%pat%%      include substring (SQL-style)
    COL not like %%pat%%  exclude substring (SQL-style)
    COL^PAT / COL$PAT   starts with / ends with
    COL=/regex/         regex include
    COL=@empty / @nempty  empty / non-empty field

    Same column repeated (include): OR. Same column repeated (exclude): drop if any match.
    Different columns: AND. Pipeline: fetch -> filter -> sort -> display.

SORT (-S / --sort):
    COL                 ascending
    COL:desc            descending
    COL:numeric         numeric ascending
    COL:numeric:desc    numeric descending

OUTPUT / CACHE:
    -c, --cols          Columns to show or emit (with -o)
    -o, --raw           Emit filtered TSV only (no table)
    -n, --count         Print record count only
    -i, --ignore-case   Case-insensitive filter values and sort
    -s, --ssh           Remote SSH target (user@host)
    -A, --no-auto-ssh   Disable auto-SSH when local esql missing
    -N, --no-cache      Do not update last-run cache after fetch
    -d, --cache-dir     Override cache directory
    -G, --filter-help   Print full filter syntax reference

EXAMPLES:

    # Fetch from etrack (cached automatically)
    ./esql_formatter.py -r MY_QUERY -H INCIDENT,STATE,VERSION,KEYWORD,ABSTRACT

    # Re-filter last run without re-querying etrack
    ./esql_formatter.py --last --filter VERSION=11.1.0.1 --filter VERSION=11.1
    ./esql_formatter.py --last --filter STATE=Open --filter 'ABSTRACT~%%crash%%'

    # Keyword include / exclude
    ./esql_formatter.py --last --filter KEYWORD=X_1
    ./esql_formatter.py --last --exclude-filter KEYWORD=X_1
    ./esql_formatter.py --last --exclude-filter KEYWORD=X
    ./esql_formatter.py --last --filter 'KEYWORD=!X_1' --filter 'KEYWORD=!X'

    # Sort
    ./esql_formatter.py --last --sort VERSION:desc --sort INCIDENT:numeric
    ./esql_formatter.py --last --filter STATE=Open --sort PRIORITY:numeric:desc

    # Cache info and raw output
    ./esql_formatter.py --last-info
    ./esql_formatter.py --last --filter VERSION^11.1 --raw

    # File / stdin (no cache unless --query/--command)
    ./esql_formatter.py --file data.tsv -H INCIDENT,STATE,ABSTRACT --cols INCIDENT,STATE
    cat data.tsv | ./esql_formatter.py --stdin -H INCIDENT,STATE,ABSTRACT

NOTES:
- Input data must be TAB-separated; no header row in the data itself
- Filter on raw TSV before formatting; do not filter the rendered table
- Last-run cache: ~/.cache/esql_formatter/last.tsv + last.meta.json

Original AWK equivalent:
    cat data.txt | awk -F "\\t" -f ~/scripts/et_data_in_col.awk -v noheader=1 -v cols=INCIDENT,STATE
"""

FILTER_SYNTAX_HELP = """
FILTER SYNTAX (-F / --filter include, -X / --exclude-filter exclude)
  Column names are case-insensitive (state = STATE). Use -i for case-insensitive values.

  Include (keep matching rows):
    COL=VALUE              exact match             STATE=OPEN
    COL~PATTERN            contains (%% optional)   ABSTRACT~%%crash%%
    COL^PATTERN            starts with             VERSION^11.1
    COL$PATTERN            ends with               VERSION$0.1
    COL=/regex/            regex match             ABSTRACT=/FI-\\d+/
    COL in (A,B,C)         OR list                 VERSION in (11.1,11.2)
    COL like %%pat%%       SQL contains            ABSTRACT like %%memory%%
    COL=@empty             field is empty          TARGET_VERSION=@empty
    COL=@nempty            field is not empty      KEYWORD=@nempty

  Exclude (drop matching rows):
    -X COL=VALUE           exact exclude           KEYWORD=X_1  (_ => exact)
    -X COL=VALUE           substring exclude       KEYWORD=X    (no _ => substring)
    COL!=VALUE             exact exclude           STATE!=CLOSED
    COL!~PATTERN           substring exclude       ABSTRACT!~deprecated
    COL=!TOKEN             shorthand exclude       KEYWORD=!X_1 (exact), KEYWORD=!X (substring)
    COL not like %%pat%%   SQL exclude contains    KEYWORD not like %%X%%

  Combining filters:
    Same column, repeated -F     OR within that column
    Same column, repeated -X     drop if ANY exclude matches
    Different columns            AND across columns
    Use -i                       case-insensitive value matching

  Examples:
    %(prog)s --last -i -F STATE=open -F 'ABSTRACT~%%crash%%'
    %(prog)s --last -F VERSION=11.1.0.1 -F VERSION=11.1
    %(prog)s --last -X KEYWORD=X_1 -X KEYWORD=X --cols INCIDENT,STATE,KEYWORD
"""

SHORT_OPTIONS_HELP = """
SHORT OPTIONS (all flags have a long form):
  Input:     -r/--query  -f/--file  -T/--stdin  -e/--command  -L/--last
  Info:      -M/--last-info  -l/--list-headers  -H/--headers  -G/--filter-help
  Filter:    -F/--filter  -X/--exclude-filter  -S/--sort  -i/--ignore-case
  Output:    -c/--cols  -o/--raw  -n/--count
  Remote:    -s/--ssh  -A/--no-auto-ssh
  Cache:     -N/--no-cache  -d/--cache-dir
"""

CLI_USAGE = """%(prog)s [-h]
        [-f FILE | -T | -e CMD | -r QUERY | -L | -M]
        [-l] [-H HEADERS] [-s SSH] [-c COLS]
        [-F EXPR] [-X EXPR] [-S COL] [-i]
        [-A] [-N] [-d DIR] [-o] [-n] [-G]"""

import sys
import subprocess
import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cmp_to_key
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class ShortFirstHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Show short option before long option in help lines (-f, --file)."""

    def _format_action_invocation(self, action):
        if not action.option_strings:
            return super()._format_action_invocation(action)

        def sort_key(option: str) -> tuple:
            if option.startswith('--'):
                return (1, option)
            return (0, option)

        ordered = sorted(action.option_strings, key=sort_key)
        saved = action.option_strings
        action.option_strings = ordered
        try:
            return super()._format_action_invocation(action)
        finally:
            action.option_strings = saved


class EsqlFormatter:
    """Format SQL output (without headers) into a table with customizable columns."""

    # Predefined column widths matching the AWK script
    COLUMN_WIDTHS = {
        'ABSTRACT': 90,
        'CATEGORY': 20,
        'CHANGED_BY': 20,
        'COMPONENT': 30,
        'DATE_CLOSED': 11,
        'DATE_FIXED': 11,
        'DATE_OPENED': 14,
        'DEFAULT': 12,
        'INCIDENT': 8,
        'KEYWORD': 20,
        'LAST_CHANGED': 11,
        'PLATFORM': 13,
        'PRIORITY': 3,
        'PRODUCT': 10,
        'PROGRESS_STATUS': 40,
        'REPORTER': 20,
        'SEVERITY': 3,
        'STATE': 10,
        'SUBSCRIBE': 40,
        'TYPE': 17,
        'TARGET_BUILD': 13,
        'TARGET_VERSION': 10,
        'USER_DEFINED': 20,
        'USER_DEFINED2': 30,
        'VERSION': 8,
    }

    def __init__(self, headers: List[str], columns: Optional[List[str]] = None,
                 custom_widths: Optional[Dict[str, int]] = None):
        """
        Initialize formatter with specified headers and optional column selection.

        Args:
            headers: List of header names in order (matches data columns)
            columns: List of column names to display, or None for all columns
            custom_widths: Dict mapping header names to custom widths (optional)
        """
        self.headers = headers
        self.columns = columns
        self.custom_widths = custom_widths or {}
        self.column_indices = {}
        self.display_columns = []
        self.column_widths = {}
        
        self._setup_columns()

    def get_column_width(self, column_name: str) -> int:
        """Get the width for a column. Priority: custom > predefined > default."""
        if column_name in self.custom_widths:
            return self.custom_widths[column_name]
        return self.COLUMN_WIDTHS.get(column_name, self.COLUMN_WIDTHS['DEFAULT'])

    def _setup_columns(self) -> None:
        """Setup column mappings and display columns."""
        # Create index mapping for quick lookup
        self.column_indices = {col: idx for idx, col in enumerate(self.headers)}

        # Determine which columns to display
        if self.columns is None or '*' in self.columns:
            self.display_columns = self.headers
        else:
            # Only include columns that exist in the header
            self.display_columns = [col for col in self.columns if col in self.column_indices]

            # Warn about missing columns
            missing = set(self.columns) - set(self.headers)
            if missing:
                print(f"Warning: Columns not found in headers: {', '.join(missing)}",
                      file=sys.stderr)

        # Setup column widths
        for col in self.display_columns:
            self.column_widths[col] = self.get_column_width(col)

    def print_separator(self) -> None:
        """Print a separator line."""
        total_width = sum(self.column_widths.values()) + len(self.display_columns) * 3 + 1
        print('-' * total_width)

    def print_row(self, values: List[str]) -> None:
        """
        Print a row with proper formatting.

        Args:
            values: List of values corresponding to all columns
        """
        print('|', end='')
        for col in self.display_columns:
            idx = self.column_indices[col]
            width = self.column_widths[col]

            # Get value and truncate if needed
            value = values[idx] if idx < len(values) else ''
            value = value.replace('\n', ' | ')
            truncated = value[:width] if len(value) > width else value

            print(f' {truncated:<{width}} |', end='')
        print()

    def format_data(self, lines: List[str]) -> None:
        """
        Format and print the data.

        Args:
            lines: List of data lines (NO header line)
        """
        if not lines:
            print("No data to format")
            return

        if not self.display_columns:
            print("No valid columns to display")
            return

        # Print header (from provided headers)
        self.print_separator()
        self.print_row(self.headers)
        self.print_separator()

        # Print data rows
        record_count = 0
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                values = line.split('\t')
                self.print_row(values)
                record_count += 1

        # Print footer
        self.print_separator()
        print(f"\nTotal number of records: {record_count}")


DEFAULT_CACHE_DIR = Path.home() / '.cache' / 'esql_formatter'
LAST_TSV = 'last.tsv'
LAST_META = 'last.meta.json'


@dataclass
class FilterSpec:
    """Single column filter predicate."""

    column: str
    op: str
    value: str = ''


@dataclass
class ColumnFilterGroup:
    """Filters on one column. Include specs are OR'd; any exclude spec rejects the row."""

    column: str
    specs: List[FilterSpec] = field(default_factory=list)


@dataclass
class SortSpec:
    """Sort directive for one column."""

    column: str
    reverse: bool = False
    numeric: bool = False


INCLUDE_OPS = frozenset({'eq', 'contains', 'starts', 'ends', 'regex', 'empty', 'not_empty'})
EXCLUDE_OPS = frozenset({'ne', 'not_contains'})


def parse_tsv_records(text: str, num_columns: int) -> List[str]:
    """
    Parse TSV into logical rows when field values contain embedded newlines.

    esql/equery output may span multiple physical lines per record (e.g. PROGRESS_STATUS
    with sentence-per-line updates). A logical row is complete once it contains at
    least (num_columns - 1) tab characters.
    """
    if num_columns < 1:
        return []
    if num_columns == 1:
        return [line for line in text.splitlines() if line.strip()]

    expected_tabs = num_columns - 1
    records: List[str] = []
    buffer: List[str] = []

    for line in text.splitlines():
        if not line.strip() and not buffer:
            continue
        buffer.append(line)
        if '\n'.join(buffer).count('\t') >= expected_tabs:
            records.append('\n'.join(buffer))
            buffer = []

    if buffer:
        joined = '\n'.join(buffer)
        records.append(joined)
        print(
            f'Warning: trailing incomplete TSV row ({joined.count(chr(9))} tabs, '
            f'expected {expected_tabs})',
            file=sys.stderr,
        )

    return records


def validate_tsv_shape(records: List[str], headers: List[str]) -> None:
    """Warn when header count does not match parsed row width."""
    if not records or not headers:
        return

    expected_tabs = len(headers) - 1
    sample = records[0]
    actual_tabs = sample.count('\t')
    if actual_tabs == expected_tabs:
        return

    physical_lines = sum(record.count('\n') + 1 for record in records)
    print(
        f'Warning: --headers lists {len(headers)} column(s) but data rows have '
        f'{actual_tabs + 1} field(s) ({actual_tabs} tabs).',
        file=sys.stderr,
    )
    print(
        f'  Parsed {len(records)} logical record(s) from {physical_lines} physical line(s).',
        file=sys.stderr,
    )
    print(
        '  Re-run with the full -H header list matching your esql query columns '
        '(see x.esql.trencher or query definition).',
        file=sys.stderr,
    )


def records_from_text_or_lines(data: str, num_columns: int) -> List[str]:
    """Normalize raw stdout or cached text into logical TSV records."""
    return parse_tsv_records(data, num_columns)


def join_records_as_text(records: List[str]) -> str:
    return '\n'.join(records) + ('\n' if records else '')


def get_cache_dir(cache_dir: Optional[str] = None) -> Path:
    path = Path(cache_dir).expanduser() if cache_dir else DEFAULT_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_exists(cache_dir: Optional[str] = None) -> bool:
    tsv_path, meta_path = cache_paths(cache_dir)
    return tsv_path.exists() and meta_path.exists()


def cache_paths(cache_dir: Optional[str] = None) -> Tuple[Path, Path]:
    base = get_cache_dir(cache_dir)
    return base / LAST_TSV, base / LAST_META


def save_last_run(
    raw_text: str,
    logical_row_count: int,
    headers: List[str],
    headers_raw: str,
    custom_widths: Dict[str, int],
    query: Optional[str] = None,
    command: Optional[str] = None,
    ssh_target: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> None:
    tsv_path, meta_path = cache_paths(cache_dir)
    if not raw_text.endswith('\n') and raw_text:
        raw_text = raw_text + '\n'
    tsv_path.write_text(raw_text, encoding='utf-8')
    physical_lines = raw_text.count('\n')
    meta = {
        'query': query,
        'command': command,
        'ssh': ssh_target,
        'headers': headers,
        'headers_raw': headers_raw,
        'custom_widths': custom_widths,
        'fetched_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'row_count': logical_row_count,
        'physical_lines': physical_lines,
        'tsv_path': str(tsv_path),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(
        f'[CACHE] Saved {logical_row_count} record(s) ({physical_lines} physical lines) -> {tsv_path}',
        file=sys.stderr,
    )


def load_last_meta(cache_dir: Optional[str] = None) -> Dict:
    _, meta_path = cache_paths(cache_dir)
    if not meta_path.exists():
        print(f"Error: No last-run cache at {meta_path}", file=sys.stderr)
        print("  Run an esql query first, e.g.: esql_formatter.py -r MY_QUERY -H INCIDENT,STATE", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(meta_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error reading cache metadata: {exc}", file=sys.stderr)
        sys.exit(1)


def load_last_run(cache_dir: Optional[str] = None) -> Tuple[str, Dict]:
    """Load cached raw TSV text and metadata."""
    tsv_path, _ = cache_paths(cache_dir)
    meta = load_last_meta(cache_dir)
    if not tsv_path.exists():
        print(f'Error: Cache data missing: {tsv_path}', file=sys.stderr)
        sys.exit(1)
    raw_text = tsv_path.read_text(encoding='utf-8')
    return raw_text, meta


def show_last_info(cache_dir: Optional[str] = None) -> None:
    meta = load_last_meta(cache_dir)
    print(f"Query:      {meta.get('query') or meta.get('command') or '(unknown)'}")
    if meta.get('ssh'):
        print(f"SSH:        {meta['ssh']}")
    print(f"Fetched:    {meta.get('fetched_at', '(unknown)')}")
    print(f"Records:    {meta.get('row_count', 0)}")
    if meta.get('physical_lines'):
        print(f"Phys lines: {meta['physical_lines']}")
    print(f"Headers:    {meta.get('headers_raw') or ','.join(meta.get('headers', []))}")
    print(f"Data file:  {meta.get('tsv_path')}")


def _strip_like_wildcards(pattern: str) -> str:
    return pattern.strip().strip("'\"").strip('%')


def _exclude_shorthand_op(token: str) -> Tuple[str, str]:
    """
    Map COL=!TOKEN shorthand to an exclude operator.

    KEYWORD=!X_1  -> exact exclude (!=), because token contains '_'
    KEYWORD=!X    -> substring exclude (!~), because token has no '_'

    Use KEYWORD!=FOO for exact exclude without underscore in the token.
    Use KEYWORD!~X_1 to substring-exclude a token that contains '_'.
    """
    if not token.startswith('!'):
        raise ValueError(f"Exclude shorthand must start with '!': {token!r}")
    inner = token[1:]
    if not inner:
        raise ValueError("Exclude shorthand missing value after '!'")
    if '_' in inner:
        return 'ne', inner
    return 'not_contains', inner


def _resolve_exclude_equals(column: str, value: str) -> FilterSpec:
    """Map COL=VAL under --exclude-filter to exact or substring exclude."""
    value = _strip_like_wildcards(value)
    if '_' in value:
        return FilterSpec(column=column, op='ne', value=value)
    return FilterSpec(column=column, op='not_contains', value=value)


def parse_filter_expr(expr: str, exclude_mode: bool = False) -> List[FilterSpec]:
    """
    Parse one --filter / --exclude-filter expression into FilterSpec objects.

    Include (--filter):
      COL=VALUE              exact match
      COL=VALUE              include exact (e.g. KEYWORD=X_1)
      COL!=VALUE             exclude exact
      COL~PATTERN            contains (optional % wildcards)
      COL!~PATTERN           exclude substring
      COL=!X_1               exclude exact shorthand (_ in token)
      COL=!X                 exclude substring shorthand (no _ in token)
      COL^PATTERN            starts with
      COL$PATTERN            ends with
      COL=/regex/            regex match
      COL=@empty             empty field
      COL=@nempty            non-empty field
      COL in (A,B,C)         OR include list
      COL like %abc%         SQL-style contains
      COL not like %abc%     SQL-style exclude substring

    Exclude (--exclude-filter), COL=VAL only:
      KEYWORD=X_1            exclude exact (token contains _)
      KEYWORD=X              exclude substring (no _ in token)
    Other operators (!=, !~, =!X, etc.) work the same as --filter.
    """
    expr = expr.strip()
    if not expr:
        raise ValueError("Empty filter expression")

    not_like_match = re.match(r'^([A-Za-z0-9_]+)\s+not\s+like\s+(.+)$', expr, re.IGNORECASE)
    if not_like_match:
        column = not_like_match.group(1).upper()
        pattern = _strip_like_wildcards(not_like_match.group(2))
        return [FilterSpec(column=column, op='not_contains', value=pattern)]

    in_match = re.match(r'^([A-Za-z0-9_]+)\s+in\s+\((.*)\)\s*$', expr, re.IGNORECASE)
    if in_match:
        column = in_match.group(1).upper()
        values = [item.strip().strip("'\"") for item in in_match.group(2).split(',') if item.strip()]
        if not values:
            raise ValueError(f"Empty IN list in filter: {expr}")
        op = 'ne' if exclude_mode else 'eq'
        return [FilterSpec(column=column, op=op, value=value) for value in values]

    like_match = re.match(r'^([A-Za-z0-9_]+)\s+like\s+(.+)$', expr, re.IGNORECASE)
    if like_match:
        column = like_match.group(1).upper()
        pattern = _strip_like_wildcards(like_match.group(2))
        if exclude_mode:
            return [FilterSpec(column=column, op='not_contains', value=pattern)]
        return [FilterSpec(column=column, op='contains', value=pattern)]

    regex_match = re.match(r'^([A-Za-z0-9_]+)=/(.+)/$', expr)
    if regex_match:
        return [FilterSpec(column=regex_match.group(1).upper(), op='regex', value=regex_match.group(2))]

    for op_token, op_name in (
        ('!~', 'not_contains'),
        ('!=', 'ne'),
        ('~', 'contains'),
        ('^', 'starts'),
        ('$', 'ends'),
        ('=', 'eq'),
    ):
        if op_token not in expr:
            continue
        column, value = expr.split(op_token, 1)
        column = column.strip().upper()
        value = value.strip()
        if not column:
            raise ValueError(f"Missing column in filter: {expr}")
        if op_name in ('contains', 'not_contains', 'starts', 'ends'):
            value = _strip_like_wildcards(value)
        if op_name == 'eq' and value in ('@empty',):
            return [FilterSpec(column=column, op='empty')]
        if op_name == 'eq' and value in ('@nempty',):
            return [FilterSpec(column=column, op='not_empty')]
        if op_name == 'eq' and value.startswith('!'):
            op_name, value = _exclude_shorthand_op(value)
            return [FilterSpec(column=column, op=op_name, value=value)]
        if exclude_mode and op_name == 'eq':
            return [_resolve_exclude_equals(column, value)]
        if exclude_mode and op_name == 'contains':
            return [FilterSpec(column=column, op='not_contains', value=value)]
        return [FilterSpec(column=column, op=op_name, value=value)]

    raise ValueError(
        f"Invalid filter syntax: {expr!r}. "
        "Use COL=VAL, COL~PAT, COL!=VAL, COL!~PAT, COL=!X_1, COL=!X, "
        "COL in (A,B), COL like %pat%, or COL not like %pat%"
    )


def group_filters(filter_specs: List[FilterSpec]) -> List[ColumnFilterGroup]:
    """Group filters by column; OR within column, AND across columns."""
    groups: Dict[str, ColumnFilterGroup] = {}
    for spec in filter_specs:
        if spec.column not in groups:
            groups[spec.column] = ColumnFilterGroup(column=spec.column, specs=[])
        groups[spec.column].specs.append(spec)
    return list(groups.values())


def _match_value(value: str, spec: FilterSpec, ignore_case: bool) -> bool:
    if ignore_case:
        value = value.casefold()
        cmp_value = spec.value.casefold()
    else:
        cmp_value = spec.value

    if spec.op == 'empty':
        return value == ''
    if spec.op == 'not_empty':
        return value != ''
    if spec.op == 'eq':
        return value == cmp_value
    if spec.op == 'ne':
        return value != cmp_value
    if spec.op == 'contains':
        return cmp_value in value
    if spec.op == 'not_contains':
        return cmp_value not in value
    if spec.op == 'starts':
        return value.startswith(cmp_value)
    if spec.op == 'ends':
        return value.endswith(cmp_value)
    if spec.op == 'regex':
        flags = re.IGNORECASE if ignore_case else 0
        return re.search(spec.value, value, flags) is not None
    raise ValueError(f"Unknown filter operator: {spec.op}")


def _exclude_matches(value: str, spec: FilterSpec, ignore_case: bool) -> bool:
    """True when the row should be dropped because this exclude rule matched."""
    if spec.op == 'ne':
        return _match_value(value, FilterSpec(spec.column, 'eq', spec.value), ignore_case)
    if spec.op == 'not_contains':
        return _match_value(value, FilterSpec(spec.column, 'contains', spec.value), ignore_case)
    raise ValueError(f"Not an exclude operator: {spec.op}")


def apply_filters(
    lines: List[str],
    headers: List[str],
    filter_groups: List[ColumnFilterGroup],
    ignore_case: bool = False,
) -> List[str]:
    """
    Return lines matching filter rules.

    Per column:
      - Include specs (eq, ~, ^, $, regex, ...): row kept if ANY include matches (OR)
      - Exclude specs (ne, !~, =!X, ...): row dropped if ANY exclude matches (OR)
      - If both exist on one column, includes must match AND no excludes may match
    Across columns: AND.
    """
    if not filter_groups:
        return lines

    column_indices = {col: idx for idx, col in enumerate(headers)}
    for group in filter_groups:
        if group.column not in column_indices:
            known = ', '.join(headers)
            print(f"Error: Filter column {group.column!r} not in headers: {known}", file=sys.stderr)
            sys.exit(1)

    filtered: List[str] = []
    for line in lines:
        values = line.split('\t')
        matched = True
        for group in filter_groups:
            idx = column_indices[group.column]
            cell = values[idx] if idx < len(values) else ''
            include_specs = [spec for spec in group.specs if spec.op in INCLUDE_OPS]
            exclude_specs = [spec for spec in group.specs if spec.op in EXCLUDE_OPS]

            if include_specs and not any(_match_value(cell, spec, ignore_case) for spec in include_specs):
                matched = False
                break
            if exclude_specs and any(_exclude_matches(cell, spec, ignore_case) for spec in exclude_specs):
                matched = False
                break
        if matched:
            filtered.append(line)
    return filtered


def parse_sort_expr(expr: str) -> SortSpec:
    """
    Parse sort expression: COL, COL:desc, COL:asc, COL:numeric, COL:numeric:desc.
    """
    expr = expr.strip()
    if not expr:
        raise ValueError("Empty --sort expression")

    parts = [part.strip() for part in expr.split(':') if part.strip()]
    column = parts[0].upper()
    reverse = False
    numeric = False

    for modifier in parts[1:]:
        token = modifier.lower()
        if token in ('desc', 'd', 'reverse', 'r'):
            reverse = True
        elif token in ('asc', 'a'):
            reverse = False
        elif token in ('numeric', 'num', 'n'):
            numeric = True
        else:
            raise ValueError(
                f"Invalid sort modifier {modifier!r} in {expr!r}. "
                "Use asc, desc, or numeric."
            )

    return SortSpec(column=column, reverse=reverse, numeric=numeric)


def _cell_value(line: str, column_indices: Dict[str, int], column: str) -> str:
    values = line.split('\t')
    idx = column_indices[column]
    return values[idx] if idx < len(values) else ''


def _compare_sort_values(left: str, right: str, spec: SortSpec, ignore_case: bool) -> int:
    if spec.numeric:
        try:
            left_num = float(left)
        except ValueError:
            left_num = float('-inf')
        try:
            right_num = float(right)
        except ValueError:
            right_num = float('-inf')
        if left_num < right_num:
            return -1
        if left_num > right_num:
            return 1
        return 0

    left_text = left.casefold() if ignore_case else left
    right_text = right.casefold() if ignore_case else right
    if left_text < right_text:
        return -1
    if left_text > right_text:
        return 1
    return 0


def sort_lines(
    lines: List[str],
    headers: List[str],
    sort_specs: List[SortSpec],
    ignore_case: bool = False,
) -> List[str]:
    """Stable multi-column sort."""
    if not sort_specs:
        return lines

    column_indices = {col: idx for idx, col in enumerate(headers)}
    for spec in sort_specs:
        if spec.column not in column_indices:
            known = ', '.join(headers)
            print(f"Error: Sort column {spec.column!r} not in headers: {known}", file=sys.stderr)
            sys.exit(1)

    def compare_lines(left: str, right: str) -> int:
        for spec in sort_specs:
            left_val = _cell_value(left, column_indices, spec.column)
            right_val = _cell_value(right, column_indices, spec.column)
            result = _compare_sort_values(left_val, right_val, spec, ignore_case)
            if result != 0:
                return -result if spec.reverse else result
        return 0

    return sorted(lines, key=cmp_to_key(compare_lines))


def emit_raw_tsv(
    lines: List[str],
    headers: Optional[List[str]] = None,
    columns: Optional[List[str]] = None,
) -> None:
    """Emit TSV rows; optionally subset/reorder columns (--cols with --raw)."""
    if not columns or not headers or columns == headers:
        for line in lines:
            print(line)
        return

    column_indices = {col: idx for idx, col in enumerate(headers)}
    pick = [col for col in columns if col in column_indices]
    for line in lines:
        values = line.split('\t')
        out = []
        for col in pick:
            idx = column_indices[col]
            out.append(values[idx] if idx < len(values) else '')
        print('\t'.join(out))


def print_header_list(headers: List[str], source: str = '') -> None:
    """Print numbered header names usable in --filter and --cols."""
    if source:
        print(f'Headers ({len(headers)}) from {source}:')
    else:
        print(f'Headers ({len(headers)}):')
    for idx, name in enumerate(headers, start=1):
        print(f'  {idx:2d}. {name}')


ESQL_SEARCH_PATHS = (
    '/usr/local/bin/esql',
    'esql',
)


def find_esql_path() -> Optional[str]:
    """Return a usable local esql binary path, or None if not installed locally."""
    for candidate in ESQL_SEARCH_PATHS:
        if os.path.isabs(candidate):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def default_ssh_target() -> Optional[str]:
    """
    Default etrack SSH target from environment (same vars as alias.remote).

    Priority: explicit ESQL_SSH, NIS_USER@NIS_SERVER, USER@ENGVM_HOST.
    """
    explicit = os.environ.get('ESQL_SSH', '').strip()
    if explicit:
        return explicit

    nis_user = os.environ.get('NIS_USER', '').strip()
    nis_server = os.environ.get('NIS_SERVER', '').strip()
    if nis_user and nis_server:
        return f'{nis_user}@{nis_server}'

    engvm_host = os.environ.get('ENGVM_HOST', '').strip()
    if engvm_host:
        login = os.environ.get('NIS_USER') or os.environ.get('USER') or os.environ.get('LOGNAME')
        if login and '@' not in engvm_host:
            return f'{login.strip()}@{engvm_host}'
        return engvm_host

    return None


def _decode_command_stdout(result: subprocess.CompletedProcess) -> str:
    return result.stdout.decode('utf-8', errors='replace')


def _report_exec_failure(label: str, cmd_display: str, exc: subprocess.CalledProcessError) -> None:
    print(f'Error executing command: {cmd_display}', file=sys.stderr)
    if exc.stderr:
        print(f'Error output: {exc.stderr.decode("utf-8", errors="replace")}', file=sys.stderr)
    sys.exit(1)


def run_esql_query(
    query_name: str,
    ssh_target: Optional[str] = None,
    auto_ssh: bool = True,
) -> str:
    """
    Run esql -r <query>. Returns raw TSV stdout (may include embedded newlines in fields).
    """
    remote_target = ssh_target
    local_esql = find_esql_path()

    if not remote_target and not local_esql and auto_ssh:
        remote_target = default_ssh_target()
        if remote_target:
            print(
                f'[AUTO] esql not found locally; running via SSH on {remote_target}',
                file=sys.stderr,
            )

    try:
        if remote_target:
            command = f'esql -r {query_name}'
            print(f'[REMOTE] Running via SSH on {remote_target}: {command}', file=sys.stderr)
            result = subprocess.run(
                ['ssh', remote_target, command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return _decode_command_stdout(result)

        if local_esql:
            cmd = [local_esql, '-r', query_name]
            print(f"[LOCAL] Running: {' '.join(cmd)}", file=sys.stderr)
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return _decode_command_stdout(result)

        print('Error: esql command not found locally.', file=sys.stderr)
        print(f'  Tried: {", ".join(ESQL_SEARCH_PATHS)}', file=sys.stderr)
        print('  Hint: pass --ssh user@host (etrack server)', file=sys.stderr)
        if auto_ssh:
            print(
                '  Or set NIS_USER + NIS_SERVER, ENGVM_HOST, or ESQL_SSH for auto-SSH',
                file=sys.stderr,
            )
        else:
            print('  Auto-SSH is off (--no-auto-ssh); pass --ssh explicitly', file=sys.stderr)
        sys.exit(1)

    except subprocess.CalledProcessError as exc:
        cmd_display = f'ssh {remote_target} esql -r {query_name}' if remote_target else f'esql -r {query_name}'
        _report_exec_failure('esql', cmd_display, exc)
    except FileNotFoundError as exc:
        print(f'Error: required command not found: {exc}', file=sys.stderr)
        if remote_target:
            print(f'  SSH target was: {remote_target}', file=sys.stderr)
            print('  Check VPN/network and test: ssh -o ConnectTimeout=10', remote_target, 'true', file=sys.stderr)
        sys.exit(1)

    return ''


def run_command(command: str, ssh_target: Optional[str] = None) -> str:
    """
    Execute a command and return output.
    Supports both LOCAL and REMOTE (SSH) execution.

    Args:
        command: Command to execute
        ssh_target: SSH target in format user@host (e.g., user@server.com)
                   If None, runs locally

    Returns:
        List of output lines
    """
    try:
        # Build full command (local or via SSH)
        if ssh_target:
            # ===== REMOTE EXECUTION: Execute via SSH =====
            cmd = ['ssh', ssh_target, command]
            print(f"[REMOTE] Running via SSH on {ssh_target}: {command}", file=sys.stderr)
        else:
            # ===== LOCAL EXECUTION =====
            cmd = command.split()
            print(f"[LOCAL] Running: {command}", file=sys.stderr)

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return _decode_command_stdout(result)

    except subprocess.CalledProcessError as e:
        _report_exec_failure('command', command, e)
    except FileNotFoundError as e:
        print(f'Error: command not found: {e}', file=sys.stderr)
        print(f'  Command: {command}', file=sys.stderr)
        if not ssh_target:
            print('  Hint: use --ssh user@host if this tool runs on a remote etrack server', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Unexpected error: {e}', file=sys.stderr)
        sys.exit(1)

    return ''


def read_from_file(filepath: str) -> str:
    """
    Read data from a file.

    Args:
        filepath: Path to the file

    Returns:
        List of lines from the file
    """
    try:
        return Path(filepath).read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def read_from_stdin() -> str:
    """Read raw TSV text from stdin."""
    return sys.stdin.read()


def parse_list_arg(arg: str) -> List[str]:
    """
    Parse comma-separated argument.

    Args:
        arg: Comma-separated values

    Returns:
        List of values
    """
    return [item.strip() for item in arg.split(',') if item.strip()]


def parse_headers_with_widths(arg: str) -> tuple:
    """
    Parse headers with optional width specification.
    
    Format: HEADER or HEADER:WIDTH
    Example: "INCIDENT:20,STATE:30,ABSTRACT" -> 
             headers=['INCIDENT','STATE','ABSTRACT'], widths={'INCIDENT':20,'STATE':30}

    Args:
        arg: Comma-separated headers with optional :WIDTH suffix

    Returns:
        Tuple of (list of header names, dict of custom widths)
    """
    headers = []
    custom_widths = {}
    
    for item in arg.split(','):
        item = item.strip()
        if not item:
            continue
        
        if ':' in item:
            parts = item.split(':', 1)
            header_name = parts[0].strip()
            try:
                width = int(parts[1].strip())
                if width > 0:
                    custom_widths[header_name] = width
                else:
                    print(f"Warning: Invalid width for {header_name}, using default", file=sys.stderr)
            except ValueError:
                print(f"Warning: Invalid width '{parts[1]}' for {header_name}, using default", file=sys.stderr)
            headers.append(header_name)
        else:
            headers.append(item)
    
    return headers, custom_widths


def parse_columns(cols_arg: Optional[str]) -> Optional[List[str]]:
    """
    Parse column specification.

    Args:
        cols_arg: Comma-separated column names or '*' or None

    Returns:
        List of column names or None for all columns
    """
    if not cols_arg or cols_arg == '*':
        return None
    return parse_list_arg(cols_arg)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Format TSV data (no header row) into a table; supports cache, filter, and sort',
        formatter_class=ShortFirstHelpFormatter,
        usage=CLI_USAGE,
        epilog=SHORT_OPTIONS_HELP + FILTER_SYNTAX_HELP + """
SORT (-S / --sort):
  COL                  ascending (default)
  COL:desc             descending
  COL:numeric          numeric ascending
  COL:numeric:desc     numeric descending
  Repeat -S for multi-column sort (left-to-right priority)

EXAMPLES:
  # Fetch from etrack (auto-cached as last run)
  %(prog)s -r MY_QUERY -H INCIDENT,STATE,VERSION,KEYWORD,ABSTRACT

  # Re-use last fetch — no etrack call
  %(prog)s -L -F VERSION=11.1.0.1 -F VERSION=11.1
  %(prog)s -L -i -F STATE=open -S VERSION:desc -c INCIDENT,STATE,VERSION

  # List columns available for -F / -c
  %(prog)s -L -l
  %(prog)s -M

  # Keyword filters
  %(prog)s -L -F KEYWORD=X_1
  %(prog)s -L -X KEYWORD=X_1
  %(prog)s -L -X KEYWORD=X
  %(prog)s -L -F 'ABSTRACT~%%crash%%' -o

  # Remote / file
  %(prog)s -r my_query -s user@server.com -H INCIDENT,STATE,ABSTRACT
  %(prog)s -f data.tsv -H INCIDENT,STATE,ABSTRACT -c STATE,INCIDENT

Cache: ~/.cache/esql_formatter/  (-N/--no-cache to skip save, -d/--cache-dir to override)
        """
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument(
        '-f', '--file',
        help='Read from file'
    )
    input_group.add_argument(
        '-T', '--stdin',
        action='store_true',
        help='Read TSV from stdin'
    )
    input_group.add_argument(
        '-e', '--command',
        help='Execute command that emits TSV rows (no header line)'
    )
    input_group.add_argument(
        '-r', '--query',
        help='Named esql query (runs: esql -r <queryname>)'
    )
    input_group.add_argument(
        '-L', '--last',
        action='store_true',
        help='Use cached data from last --query/--command fetch (no re-query)'
    )
    input_group.add_argument(
        '-M', '--last-info',
        action='store_true',
        help='Show last-run cache metadata and column list; exit'
    )

    parser.add_argument(
        '-l', '--list-headers',
        action='store_true',
        help='List column names for -F/-c (use with -L or -H); exit'
    )

    # Headers (required unless -M, or -L with cache headers)
    parser.add_argument(
        '-H', '--headers',
        required=False,
        help='Comma-separated column names in data order (INCIDENT,STATE,...). '
             'Optional widths: INCIDENT:20,ABSTRACT. Optional with -L if cached.'
    )

    # SSH target for remote execution
    parser.add_argument(
        '-s', '--ssh',
        help='SSH target (user@host) for -r/--query or -e/--command'
    )

    # Column specification
    parser.add_argument(
        '-c', '--cols',
        help='Columns to display or emit (-o): INCIDENT,STATE or * (default: all)',
        default=None
    )

    parser.add_argument(
        '-F', '--filter',
        action='append',
        default=[],
        metavar='EXPR',
        help='Include filter (see FILTER SYNTAX below). Same column: OR. Different columns: AND.'
    )

    parser.add_argument(
        '-X', '--exclude-filter',
        action='append',
        default=[],
        metavar='EXPR',
        help='Exclude filter (see FILTER SYNTAX below). KEYWORD=X_1 exact; KEYWORD=X substring.'
    )

    parser.add_argument(
        '-S', '--sort',
        action='append',
        default=[],
        metavar='COL[:asc|:desc][:numeric]',
        help='Sort by column; repeat for multi-column sort (e.g. VERSION:desc, INCIDENT:numeric)'
    )

    parser.add_argument(
        '-i', '--ignore-case',
        action='store_true',
        help='Case-insensitive filter value matching and sort'
    )

    parser.add_argument(
        '-A', '--no-auto-ssh',
        action='store_true',
        help='Do not auto-SSH when local esql missing (else NIS_USER@NIS_SERVER / ENGVM_HOST)'
    )

    parser.add_argument(
        '-N', '--no-cache',
        action='store_true',
        help='Do not update last-run cache after -r/--query or -e/--command'
    )

    parser.add_argument(
        '-d', '--cache-dir',
        help=f'Last-run cache directory (default: {DEFAULT_CACHE_DIR})'
    )

    parser.add_argument(
        '-o', '--raw',
        action='store_true',
        help='Emit filtered TSV only (respects -c/--cols); no formatted table'
    )

    parser.add_argument(
        '-n', '--count',
        action='store_true',
        help='Print matching record count only; no table output'
    )

    parser.add_argument(
        '-G', '--filter-help',
        action='store_true',
        help='Print detailed filter syntax reference and exit'
    )

    args = parser.parse_args()

    if args.filter_help:
        print(FILTER_SYNTAX_HELP.strip() % {'prog': parser.prog})
        print()
        print(SHORT_OPTIONS_HELP.strip())
        return

    if args.last_info:
        show_last_info(cache_dir=args.cache_dir)
        meta = load_last_meta(cache_dir=args.cache_dir)
        header_names = meta.get('headers') or parse_list_arg(meta.get('headers_raw', ''))
        if header_names:
            print()
            print_header_list(header_names, source='last-run cache')
        return

    if args.list_headers:
        if args.last:
            _, meta = load_last_run(cache_dir=args.cache_dir)
            headers_raw = args.headers or meta.get('headers_raw') or ','.join(meta.get('headers', []))
            source = 'last-run cache'
        elif args.headers:
            headers_raw = args.headers
            source = '--headers'
        else:
            parser.error('--list-headers requires --last or --headers (-H)')
        names, _ = parse_headers_with_widths(headers_raw)
        print_header_list(names, source=source)
        return

    if args.count and args.raw:
        parser.error('--count and --raw are mutually exclusive')

    has_input = bool(args.file or args.stdin or args.command or args.query or args.last)
    if not has_input:
        if cache_exists(cache_dir=args.cache_dir):
            print('[INFO] No input specified; using cached last run (-L/--last)', file=sys.stderr)
            args.last = True
        else:
            parser.error(
                'Must specify an input source: -r/--query, -f/--file, -T/--stdin, '
                '-e/--command, or -L/--last (no cache found yet)'
            )

    if args.ssh and not args.command and not args.query:
        parser.error("--ssh can only be used with --command or --query")

    headers_raw = args.headers
    custom_widths: Dict[str, int] = {}
    last_meta: Optional[Dict] = None
    raw_text = ''

    if args.last:
        raw_text, last_meta = load_last_run(cache_dir=args.cache_dir)
        if not headers_raw:
            headers_raw = last_meta.get('headers_raw') or ','.join(last_meta.get('headers', []))
        if not headers_raw:
            parser.error("--headers is required when cache metadata has no headers")
    else:
        if not headers_raw:
            parser.error("--headers (-H) is required unless using --last")

    headers, parsed_widths = parse_headers_with_widths(headers_raw)
    custom_widths.update(parsed_widths)
    if not headers:
        parser.error("--headers cannot be empty")

    columns = parse_columns(args.cols)

    if not args.last:
        if args.stdin:
            print("[INFO] Reading from stdin", file=sys.stderr)
            raw_text = read_from_stdin()
        elif args.file:
            print(f"[INFO] Reading from file: {args.file}", file=sys.stderr)
            raw_text = read_from_file(args.file)
        elif args.command:
            raw_text = run_command(args.command, ssh_target=args.ssh)
        elif args.query:
            raw_text = run_esql_query(
                args.query,
                ssh_target=args.ssh,
                auto_ssh=not args.no_auto_ssh,
            )
        else:
            parser.error("No input source specified")

    lines = records_from_text_or_lines(raw_text, len(headers))
    validate_tsv_shape(lines, headers)
    physical_lines = raw_text.count('\n') if raw_text else 0
    if args.last:
        print(
            f'[CACHE] Loaded {len(lines)} record(s) from last run '
            f'({physical_lines} physical lines)',
            file=sys.stderr,
        )
    elif raw_text.strip():
        print(
            f'[INFO] Parsed {len(lines)} record(s) from {physical_lines or raw_text.count(chr(10))} physical line(s)',
            file=sys.stderr,
        )

    if (args.query or args.command) and not args.no_cache and raw_text.strip():
        save_last_run(
            raw_text=raw_text,
            logical_row_count=len(lines),
            headers=headers,
            headers_raw=headers_raw,
            custom_widths=custom_widths,
            query=args.query,
            command=args.command,
            ssh_target=args.ssh,
            cache_dir=args.cache_dir,
        )

    filter_specs: List[FilterSpec] = []
    for expr in args.filter:
        try:
            filter_specs.extend(parse_filter_expr(expr, exclude_mode=False))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    for expr in args.exclude_filter:
        try:
            filter_specs.extend(parse_filter_expr(expr, exclude_mode=True))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    filter_groups = group_filters(filter_specs)
    if filter_groups:
        before = len(lines)
        lines = apply_filters(lines, headers, filter_groups, ignore_case=args.ignore_case)
        print(f"[FILTER] {before} -> {len(lines)} rows", file=sys.stderr)

    sort_specs: List[SortSpec] = []
    for expr in args.sort:
        try:
            sort_specs.append(parse_sort_expr(expr))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    if sort_specs:
        lines = sort_lines(lines, headers, sort_specs, ignore_case=args.ignore_case)
        print(f"[SORT] ordered by {', '.join(args.sort)}", file=sys.stderr)

    if args.count:
        print(len(lines))
        return

    if args.raw:
        display_cols = columns if columns else headers
        emit_raw_tsv(lines, headers=headers, columns=display_cols)
        return

    formatter = EsqlFormatter(headers=headers, columns=columns, custom_widths=custom_widths)
    formatter.format_data(lines)


if __name__ == '__main__':
    main()
