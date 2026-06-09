#!/usr/bin/env python3

"""
Fetch and print generic Jira issue details.

Features:
- Fetch issue details using: /rest/api/2/issue/<ISSUE-KEY>
- Show common Jira metadata in console-friendly output
- Show latest comments via --show-comments
- Show arbitrary fields via --show-field
- Show raw Jira JSON via --verbose

Environment variables expected:
- JIRA_SERVER_NAME
- JIRA_ACC_TOKEN
"""

import argparse
import html
import json
import os
import re
import sys
import textwrap
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


# Ensure console output remains safe even when the shell locale is ASCII.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
else:  # pragma: no cover
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
from dotenv import load_dotenv

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover
    tabulate = None


def _normalize_timestamp(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
        return dt.strftime("%Y-%m-%d %H:%M %Z")
    except ValueError:
        return value


def _opt_value(field: Any) -> str:
    if field is None:
        return "-"
    if isinstance(field, dict):
        for key in ("value", "displayName", "name", "key"):
            if field.get(key):
                return str(field[key])
    if isinstance(field, list):
        values = []
        for item in field:
            if isinstance(item, dict):
                # Special handling: if dict has 'name', prefer that
                if "name" in item:
                    values.append(str(item["name"]))
                else:
                    values.append(_opt_value(item))
            else:
                values.append(str(item))
        values = [value for value in values if value and value != "-"]
        return ", ".join(values) if values else "-"
    return str(field)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _compact_text(value: Any, max_len: int = 220) -> str:
    text = _clean_text(value)
    if not text:
        return "-"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _clean_text_for_long_output(value: Any) -> str:
    if value is None:
        return ""

    text = html.unescape(str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    replacements = [
        (r"<br\s*/?>", "\n"),
        (r"</p>", "\n\n"),
        (r"<p[^>]*>", ""),
        (r"</div>", "\n"),
        (r"<div[^>]*>", ""),
        (r"<li[^>]*>", "\n- "),
        (r"</li>", ""),
        (r"</tr>", "\n"),
        (r"<tr[^>]*>", ""),
        (r"</td>", " | "),
        (r"<td[^>]*>", ""),
        (r"</th>", " | "),
        (r"<th[^>]*>", ""),
        (r"</h[1-6]>", "\n"),
        (r"<h[1-6][^>]*>", "\n"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", " ", text)

    normalized_lines: List[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            continue
        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip()


def _truncate_text(text: str, max_len: int) -> str:
    if max_len <= 0 or len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _format_multiline_text(
    value: Any,
    max_len: int = 450,
    width: int = 110,
    indent: str = "    ",
    style: str = "paragraph",
) -> str:
    if style == "wrapped":
        compact = _compact_text(value, max_len=max_len)
        if compact == "-":
            return "-"
        return textwrap.fill(compact, width=width, initial_indent=indent, subsequent_indent=indent)

    text = _clean_text_for_long_output(value)
    if not text:
        return "-"

    text = _truncate_text(text, max_len=max_len)
    if style == "raw":
        return "\n".join(f"{indent}{line}" if line else "" for line in text.split("\n"))

    bullet_pattern = re.compile(r"^((?:[-*•]|\d+[.)]))\s+(.*)$")
    safe_width = max(width, len(indent) + 20)
    rendered_lines: List[str] = []
    for line in text.split("\n"):
        if not line:
            if rendered_lines and rendered_lines[-1] != "":
                rendered_lines.append("")
            continue

        match = bullet_pattern.match(line)
        if match:
            bullet = match.group(1)
            content = match.group(2)
            rendered_lines.append(
                textwrap.fill(
                    content,
                    width=safe_width,
                    initial_indent=f"{indent}{bullet} ",
                    subsequent_indent=f"{indent}{' ' * (len(bullet) + 1)}",
                )
            )
            continue

        rendered_lines.append(
            textwrap.fill(
                line,
                width=safe_width,
                initial_indent=indent,
                subsequent_indent=indent,
            )
        )

    return "\n".join(rendered_lines) if rendered_lines else "-"


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _has_display_value(value: Any) -> bool:
    if _is_empty_value(value):
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "-"}
    if isinstance(value, list):
        return any(_has_display_value(item) for item in value)
    if isinstance(value, dict):
        if "watchCount" in value:
            try:
                return int(value.get("watchCount", 0)) > 0
            except (TypeError, ValueError):
                return True
        return _opt_value(value).strip() not in {"", "-"}
    return True


def _format_watchers_value(value: Any) -> str:
    if not isinstance(value, dict):
        return _format_selected_field_value(value)

    watch_count = value.get("watchCount")
    is_watching = value.get("isWatching")
    if watch_count is None and is_watching is None:
        return _format_selected_field_value(value)

    count_text = str(watch_count) if watch_count is not None else "-"
    if isinstance(is_watching, bool):
        return f"{count_text} (isWatching: {'yes' if is_watching else 'no'})"
    return count_text


def _parse_legacy_sprint_string(raw: str) -> Optional[str]:
    if "greenhopper.service.sprint.Sprint@" not in raw or "[" not in raw or "]" not in raw:
        return None

    match = re.search(r"\[(.*)\]", raw)
    if not match:
        return None

    content = match.group(1)
    parts = re.findall(r"(\w+)=([^,\]]*)", content)
    if not parts:
        return None

    data: Dict[str, str] = {}
    for key, value in parts:
        data[key] = value.strip()

    name = data.get("name") or data.get("id") or "Sprint"
    detail_parts: List[str] = []
    if data.get("id"):
        detail_parts.append(f"id: {data['id']}")
    if data.get("state"):
        detail_parts.append(f"state: {str(data['state']).lower()}")
    if data.get("rapidViewId"):
        detail_parts.append(f"board: {data['rapidViewId']}")

    if detail_parts:
        return f"{name} ({', '.join(detail_parts)})"
    return name


def _format_sprint_value(value: Any) -> str:
    if value is None:
        return "-"

    if isinstance(value, str):
        parsed = _parse_legacy_sprint_string(value)
        return parsed if parsed else value

    if isinstance(value, list):
        sprint_items: List[str] = []
        for item in value:
            if isinstance(item, str):
                parsed = _parse_legacy_sprint_string(item)
                sprint_items.append(parsed if parsed else item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("id") or _opt_value(item)
                state = item.get("state")
                sprint_id = item.get("id")
                details: List[str] = []
                if sprint_id:
                    details.append(f"id: {sprint_id}")
                if state:
                    details.append(f"state: {str(state).lower()}")
                sprint_items.append(f"{name} ({', '.join(details)})" if details else str(name))
            else:
                sprint_items.append(str(item))

        sprint_items = [item for item in sprint_items if item and item != "-"]
        return ", ".join(sprint_items) if sprint_items else "-"

    if isinstance(value, dict):
        name = value.get("name") or value.get("id") or _opt_value(value)
        state = value.get("state")
        sprint_id = value.get("id")
        details: List[str] = []
        if sprint_id:
            details.append(f"id: {sprint_id}")
        if state:
            details.append(f"state: {str(state).lower()}")
        return f"{name} ({', '.join(details)})" if details else str(name)

    return str(value)


def _extract_linked_fis(issue_data: Dict[str, Any]) -> List[str]:
    fields = issue_data.get("fields", {})
    fi_set: Set[str] = set()

    for link in fields.get("issuelinks", []):
        for side in ("inwardIssue", "outwardIssue"):
            linked_issue = link.get(side)
            if not linked_issue:
                continue
            key = linked_issue.get("key", "")
            if re.match(r"^FI-\d+$", key):
                fi_set.add(key)

    case_fis = fields.get("customfield_20707")
    if case_fis:
        for found in re.findall(r"FI-\d+", str(case_fis)):
            fi_set.add(found)

    return sorted(fi_set, key=lambda value: int(value.split("-")[1]))


def _extract_etrack_ids_with_sources(issue: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract etrack IDs from various fields with their sources.

    Checks the following sources:
    - customfield_33802: Etrack Incident
    - customfield_36508: Etrack Ref/Alt
    - Field named "NBU R&D Ticket" (or "NBU R&D Ticket:")
    - Field named "Etrack Incident (Internal)" (or "Etrack Incident (Internal):")

    Returns:
        Dict mapping etrack_id -> list of source field names
    """
    sources: Dict[str, List[str]] = {}
    fields = issue.get("fields", {}) if isinstance(issue.get("fields"), dict) else issue

    def add_ids(raw_value: Any, source_name: str):
        if raw_value:
            for match in re.findall(r"\d+", str(raw_value)):
                if int(match) >= 100000:  # Filter small numbers
                    if match not in sources:
                        sources[match] = []
                    if source_name not in sources[match]:
                        sources[match].append(source_name)

    # Check known customfield IDs
    add_ids(fields.get("customfield_33802"), "EI")
    add_ids(fields.get("customfield_36508"), "ER")

    # Check by field name using names mapping
    names = issue.get("names") if isinstance(issue.get("names"), dict) else {}
    name_patterns = {
        "nbu r&d ticket": "RD",
        "nbu r&d ticket:": "RD",
        "etrack incident (internal)": "INT",
        "etrack incident (internal):": "INT",
    }
    for key, mapped_name in names.items():
        if not isinstance(mapped_name, str):
            continue
        normalized = mapped_name.strip().casefold()
        for pattern, display_name in name_patterns.items():
            if normalized == pattern or normalized.startswith(pattern.rstrip(":")):
                add_ids(fields.get(key), display_name)
                break

    return sources


def _extract_etrack_ids(issue: Dict[str, Any]) -> List[str]:
    """Extract etrack IDs from various fields.

    Filters out numbers < 100000 as real etrack IDs are typically 6-7 digits.
    """
    sources = _extract_etrack_ids_with_sources(issue)
    return sorted(sources.keys(), key=int) if sources else []


def _is_meaningful_text(value: str) -> bool:
    if not value:
        return False
    normalized = value.strip().casefold()
    placeholders = {
        "-",
        "n/a",
        "na",
        "none",
        "null",
        "tbd",
        "not started",
        "not-started",
    }
    if normalized in placeholders:
        return False
    # Reject values that are only a label/word followed by punctuation with no real content.
    # e.g. "Current status-", "Next Steps -", "Status:"
    stripped_punct = re.sub(r"[\s\-–—:*_]+$", "", normalized)
    if not stripped_punct:
        return False
    return True


def _strip_field_label_prefix(text: str, label: str) -> str:
    """Remove the field label itself from the start of a value, e.g. 'Current Status: foo' -> 'foo'."""
    pattern = re.compile(
        r"^" + re.escape(label) + r"[\s\-–—:*_]+",
        re.IGNORECASE,
    )
    return pattern.sub("", text).strip()


def _extract_current_status_and_next_steps(fields: Dict[str, Any], comments: List[Dict[str, Any]]) -> Dict[str, str]:
    current_status = _strip_field_label_prefix(
        _clean_text_for_long_output(fields.get("customfield_11202")), "current status"
    )
    next_steps = _strip_field_label_prefix(
        _clean_text_for_long_output(fields.get("customfield_11203")), "next steps"
    )

    table_text = str(fields.get("customfield_27600") or "")
    if table_text:
        if not _is_meaningful_text(current_status):
            status_match = re.search(
                r"Current\s*Status</b>\s*</td>\s*</tr>\s*<tr>\s*<td>(.*?)</td>",
                table_text,
                re.IGNORECASE | re.DOTALL,
            )
            if status_match:
                current_status = _strip_field_label_prefix(
                    _clean_text_for_long_output(status_match.group(1)), "current status"
                )
            next_steps_match = re.search(
                r"Next\s*Steps</b>\s*</td>\s*</tr>\s*<tr>\s*<td>(.*?)</td>",
                table_text,
                re.IGNORECASE | re.DOTALL,
            )
            if next_steps_match:
                next_steps = _strip_field_label_prefix(
                    _clean_text_for_long_output(next_steps_match.group(1)), "next steps"
                )

    if not (_is_meaningful_text(current_status) and _is_meaningful_text(next_steps)):
        for comment in reversed(comments):
            body = _clean_text_for_long_output(comment.get("body") or "")
            if not body:
                continue

            if not _is_meaningful_text(current_status):
                status_match = re.search(r"Current\s*Status\s*[:=]\s*(.+?)(?:\*|$)", body, re.IGNORECASE)
                if status_match:
                    candidate = _clean_text_for_long_output(status_match.group(1))
                    if _is_meaningful_text(candidate):
                        current_status = candidate

            if not _is_meaningful_text(next_steps):
                next_steps_match = re.search(r"Next\s*Steps\s*[:=]\s*(.+?)(?:\*|$)", body, re.IGNORECASE)
                if next_steps_match:
                    candidate = _clean_text_for_long_output(next_steps_match.group(1))
                    if _is_meaningful_text(candidate):
                        next_steps = candidate

            if _is_meaningful_text(current_status) and _is_meaningful_text(next_steps):
                break

    result: Dict[str, str] = {}
    if _is_meaningful_text(current_status):
        result["current_status"] = current_status
    if _is_meaningful_text(next_steps):
        result["next_steps"] = next_steps
    return result


def _extract_html_table_rows(table_html: str) -> List[List[str]]:
    rows: List[List[str]] = []
    if not table_html:
        return rows

    for tr_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr_html, flags=re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        cleaned = [
            re.sub(r"\s+", " ", _clean_text_for_long_output(cell)).strip()
            for cell in cells
        ]
        cleaned = [cell for cell in cleaned if cell]
        if cleaned:
            rows.append(cleaned)

    return rows


def _extract_field_issues_for_customer_table(fields: Dict[str, Any]) -> List[List[str]]:
    raw_html = str(fields.get("customfield_27600") or "")
    if not raw_html:
        return []

    heading_pattern = re.compile(
        r"Field(?:\s|&nbsp;|<[^>]+>)*Issues(?:\s|&nbsp;|<[^>]+>)*For(?:\s|&nbsp;|<[^>]+>)*This(?:\s|&nbsp;|<[^>]+>)*Customer",
        re.IGNORECASE,
    )
    heading_match = heading_pattern.search(raw_html)
    if not heading_match:
        return []

    table_matches = list(re.finditer(r"<table\b[^>]*>.*?</table>", raw_html, flags=re.IGNORECASE | re.DOTALL))
    if not table_matches:
        return []

    selected_table_html: Optional[str] = None
    for match in table_matches:
        if match.start() > heading_match.end():
            selected_table_html = match.group(0)
            break

    if selected_table_html is None:
        for match in table_matches:
            if match.start() <= heading_match.start() <= match.end():
                selected_table_html = match.group(0)
                break

    if not selected_table_html:
        return []

    rows = _extract_html_table_rows(selected_table_html)
    if not rows:
        return []

    filtered_rows: List[List[str]] = []
    for row in rows:
        normalized_row = " ".join(row).casefold()
        if "field issues for this customer" in normalized_row:
            continue
        filtered_rows.append(row)

    return filtered_rows


def _prepare_field_issues_table(rows: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
    if not rows:
        return ([], [])

    max_cols = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in rows]

    header_candidate = normalized_rows[0]
    header_tokens = {
        "key", "issue", "summary", "status", "priority", "severity", "assignee", "customer", "case"
    }
    header_like = any(
        any(token in cell.casefold() for token in header_tokens)
        for cell in header_candidate
        if cell
    )

    if header_like and len(normalized_rows) > 1:
        headers = [cell if cell else f"Column {index + 1}" for index, cell in enumerate(header_candidate)]
        return (headers, normalized_rows[1:])

    headers = [f"Column {index + 1}" for index in range(max_cols)]
    return (headers, normalized_rows)


def _extract_case_account_name(issue: Dict[str, Any], fields: Dict[str, Any]) -> str:
    """Resolve the customer's 'Case Account Name' from the issue."""
    value = _field_value_by_any_name(
        issue,
        ["Case Account Name", "Account Name", "Customer Name"],
    )
    if _is_empty_value(value):
        # Fall back to scanning customfields whose names match.
        names = issue.get("names") if isinstance(issue.get("names"), dict) else {}
        for key, mapped_name in names.items():
            if not isinstance(mapped_name, str):
                continue
            normalized = mapped_name.strip().casefold()
            if normalized in {"case account name", "account name", "customer name"}:
                value = fields.get(key)
                if not _is_empty_value(value):
                    break

    text = _opt_value(value).strip()
    if not text or text == "-":
        return ""
    return text


def _fetch_customer_field_issue_rows(
    jira: "JiraClient", customer_name: str, active_only: bool = False
) -> List[List[str]]:
    """Fetch one-liner rows for FI issues matching the customer via JQL."""
    escaped = _jql_escape(customer_name)
    jql = f'project = FI AND "Case Account Name" ~ "{escaped}"'
    if active_only:
        jql += " AND statusCategory != Done"
    jql += " ORDER BY updated DESC"

    issues = jira.search_issues(jql, max_results=200)
    rows: List[List[str]] = []
    for issue in issues:
        issue_fields = issue.get("fields", {}) or {}
        rows.append([
            issue.get("key", "-"),
            _opt_value(issue_fields.get("status")),
            _opt_value(issue_fields.get("priority")),
            _opt_value(issue_fields.get("assignee")),
            _normalize_timestamp(issue_fields.get("updated")),
            _compact_text(issue_fields.get("summary"), max_len=120),
        ])
    return rows


def _fetch_etrack_details(etrack_ids: List[str]) -> Dict[str, Dict[str, str]]:
    details: Dict[str, Dict[str, str]] = {}
    if not etrack_ids:
        return details

    try:
        from account_manager.etrack_integration import EtrackExecutor
    except ImportError:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.dirname(script_dir)
        if workspace_root not in sys.path:
            sys.path.insert(0, workspace_root)

        try:
            from account_manager.etrack_integration import EtrackExecutor
        except ImportError as exc:
            for et in etrack_ids:
                details[et] = {
                    "state": "-",
                    "assignee": "-",
                    "severity": "-",
                    "priority": "-",
                    "version": "-",
                    "component": "-",
                    "abstract": f"Etrack module unavailable: {exc}",
                }
            return details

    try:
        executor = EtrackExecutor()
    except RuntimeError as exc:
        for et in etrack_ids:
            details[et] = {
                "state": "-",
                "assignee": "-",
                "severity": "-",
                "priority": "-",
                "version": "-",
                "component": "-",
                "abstract": f"Unable to initialize Etrack executor: {exc}",
            }
        return details

    for et in etrack_ids:
        info = executor.get_etrack_info(et)
        if info:
            abstract = (info.abstract or "-").strip()
            if len(abstract) > 140:
                abstract = abstract[:140] + "..."
            details[et] = {
                "state": info.state or "-",
                "assignee": info.assignee or "-",
                "severity": info.severity or "-",
                "priority": info.priority or "-",
                "version": info.version or "-",
                "component": info.component or "-",
                "abstract": abstract,
            }
        else:
            details[et] = {
                "state": "-",
                "assignee": "-",
                "severity": "-",
                "priority": "-",
                "version": "-",
                "component": "-",
                "abstract": "No etrack details found",
            }

    return details


class JiraClient:
    def __init__(self):
        load_dotenv()
        self.server = os.getenv("JIRA_SERVER_NAME")
        self.token = os.getenv("JIRA_ACC_TOKEN")
        self.base_url = f"https://{self.server}" if self.server else None
        self.timeout = 30
        self._fields_by_name: Optional[Dict[str, str]] = None

        if not self.base_url or not self.token:
            raise RuntimeError("Missing JIRA_SERVER_NAME or JIRA_ACC_TOKEN in environment")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """GET with retry on transient network/TLS errors (exponential backoff).

        Uses a fresh Session per attempt with ``Connection: close`` to avoid
        stale keep-alive sockets — a common cause of
        ``[SSL: UNEXPECTED_EOF_WHILE_READING]`` on macOS (LibreSSL) talking to
        Jira behind a load balancer that may drop idle TLS sessions.
        """
        max_retries = 5
        last_exc: Optional[Exception] = None
        request_headers = dict(self.headers)
        request_headers["Connection"] = "close"

        for attempt in range(1, max_retries + 1):
            session = requests.Session()
            try:
                try:
                    response = session.get(
                        url,
                        headers=request_headers,
                        params=params,
                        timeout=self.timeout,
                    )
                except requests.exceptions.SSLError as exc:
                    # Transient SSL/EOF errors — retry.
                    msg = str(exc)
                    is_transient_ssl = (
                        "UNEXPECTED_EOF_WHILE_READING" in msg
                        or "EOF occurred in violation of protocol" in msg
                        or "SSLEOFError" in msg
                        or "ConnectionResetError" in msg
                        or "bad record mac" in msg.lower()
                    )
                    if is_transient_ssl and attempt < max_retries:
                        last_exc = exc
                        wait = min(2 ** attempt, 30)
                        print(
                            f"Transient SSL error calling Jira (attempt {attempt}/{max_retries}): {exc}. "
                            f"Retrying in {wait}s...",
                            file=sys.stderr,
                        )
                        time.sleep(wait)
                        continue
                    raise RuntimeError(
                        f"TLS/SSL error while connecting to Jira ({self.server}). "
                        f"Please check VPN/proxy/certificate setup. Details: {exc}"
                    ) from exc
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        requests.exceptions.ChunkedEncodingError) as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        wait = min(2 ** attempt, 30)
                        print(
                            f"Network error calling Jira (attempt {attempt}/{max_retries}): {exc}. "
                            f"Retrying in {wait}s...",
                            file=sys.stderr,
                        )
                        time.sleep(wait)
                        continue
                    raise RuntimeError(f"Network error while calling Jira ({self.server}): {exc}") from exc
                except requests.exceptions.RequestException as exc:
                    raise RuntimeError(f"Network error while calling Jira ({self.server}): {exc}") from exc

                # Retry on transient server-side errors as well.
                if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    wait = min(2 ** attempt, 30)
                    print(
                        f"Jira returned {response.status_code} (attempt {attempt}/{max_retries}). "
                        f"Retrying in {wait}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue

                return response
            finally:
                session.close()

        # Should not reach here, but keep a safe fallback.
        raise RuntimeError(
            f"Network error while calling Jira ({self.server}) after {max_retries} attempts: {last_exc}"
        )

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {"expand": "names"}
        response = self._get(url, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch {issue_key}: {response.status_code} {response.text[:400]}")
        return response.json()

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/rest/api/2/search"
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": "*all",   # return all fields including custom fields
            "expand": "names",  # include field-id→display-name mapping per issue
        }
        response = self._get(url, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to search issues: {response.status_code} {response.text[:400]}")
        return response.json().get("issues", [])

    def get_field_key_by_name(self, display_name: str) -> Optional[str]:
        if self._fields_by_name is None:
            url = f"{self.base_url}/rest/api/2/field"
            response = self._get(url)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to fetch Jira fields: {response.status_code} {response.text[:400]}"
                )

            self._fields_by_name = {}
            for field in response.json():
                name = field.get("name")
                field_id = field.get("id")
                if isinstance(name, str) and isinstance(field_id, str):
                    self._fields_by_name[_normalize_field_selector(name)] = field_id

        return self._fields_by_name.get(_normalize_field_selector(display_name))

    def get_issue_status_batch(self, issue_keys: List[str]) -> Dict[str, Dict[str, str]]:
        if not issue_keys:
            return {}

        unique_keys = sorted(set(issue_keys))
        jql = f"key in ({', '.join(unique_keys)})"

        url = f"{self.base_url}/rest/api/2/search"
        params = {
            "jql": jql,
            "maxResults": len(unique_keys),
            "fields": "status,resolution,assignee,priority,updated",
        }

        response = self._get(url, params=params)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch linked issue statuses: {response.status_code} {response.text[:400]}"
            )

        payload = response.json()
        result: Dict[str, Dict[str, str]] = {}
        for issue in payload.get("issues", []):
            fields = issue.get("fields", {})
            result[issue.get("key", "")] = {
                "status": _opt_value(fields.get("status")),
                "resolution": _opt_value(fields.get("resolution")),
                "assignee": _opt_value(fields.get("assignee") or {}),
                "priority": _opt_value(fields.get("priority")),
                "updated": _normalize_timestamp(fields.get("updated")),
            }

        for key in unique_keys:
            if key not in result:
                result[key] = {
                    "status": "NOT_FOUND",
                    "resolution": "-",
                    "assignee": "-",
                    "priority": "-",
                    "updated": "-",
                }

        return result


def _print_table(rows: List[List[str]], headers: List[str]):
    if tabulate:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
        return

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def fmt(values: List[str]) -> str:
        return " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(values))

    print(fmt(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(fmt(row))


def _summary_rows_to_dict(summary_rows: List[List[str]]) -> Dict[str, str]:
    return {label: value for label, value in summary_rows}


def _summary_value(summary_rows: List[List[str]], label: str) -> str:
    for row_label, row_value in summary_rows:
        if row_label == label:
            return row_value
    return "-"


def _is_cap_fi_profile(summary_rows: List[List[str]], profile_type: str) -> bool:
    if profile_type != "fi":
        return False
    cap_value = _summary_value(summary_rows, "CAP Involvement")
    return cap_value.strip().casefold() == "cap"


def _extract_subtasks(fields: Dict[str, Any]) -> List[Dict[str, str]]:
    raw_subtasks = fields.get("subtasks")
    if not isinstance(raw_subtasks, list):
        return []

    items: List[Dict[str, str]] = []
    for task in raw_subtasks:
        if not isinstance(task, dict):
            continue

        task_fields = task.get("fields") or {}
        if not isinstance(task_fields, dict):
            task_fields = {}

        items.append(
            {
                "key": str(task.get("key") or "-"),
                "summary": _compact_text(task_fields.get("summary"), max_len=120),
                "status": _opt_value(task_fields.get("status")),
                "assignee": _opt_value(task_fields.get("assignee")),
                "type": _opt_value(task_fields.get("issuetype")),
            }
        )

    return items


def _extract_subtasks_from_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    seen: Set[str] = set()

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        key = str(issue.get("key") or "-")
        if key in seen:
            continue
        seen.add(key)

        task_fields = issue.get("fields") or {}
        if not isinstance(task_fields, dict):
            task_fields = {}

        items.append(
            {
                "key": key,
                "summary": _compact_text(task_fields.get("summary"), max_len=120),
                "status": _opt_value(task_fields.get("status")),
                "assignee": _opt_value(task_fields.get("assignee")),
                "type": _opt_value(task_fields.get("issuetype")),
            }
        )

    return items


def _print_compact_segments(segments: List[str], max_width: int = 140) -> None:
    if not segments:
        return

    current_line = segments[0]
    for segment in segments[1:]:
        candidate = f"{current_line} | {segment}"
        if len(candidate) <= max_width:
            current_line = candidate
        else:
            print(current_line)
            current_line = segment
    print(current_line)


def _field_value_by_name(issue: Dict[str, Any], display_name: str) -> Any:
    fields = issue.get("fields")
    names = issue.get("names")
    if not isinstance(fields, dict) or not isinstance(names, dict):
        return None

    normalized_name = _normalize_field_selector(display_name)
    for key, mapped_name in names.items():
        if key in fields and isinstance(mapped_name, str):
            if _normalize_field_selector(mapped_name) == normalized_name:
                return fields.get(key)
    return None


def _field_value_by_any_name(issue: Dict[str, Any], display_names: List[str]) -> Any:
    for display_name in display_names:
        value = _field_value_by_name(issue, display_name)
        if value is not None and not _is_empty_value(value):
            return value
    return None


def _format_history_value(value: Any) -> str:
    if _is_empty_value(value):
        return "-"

    items: List[str] = []

    def _normalize_history_item(raw: str) -> str:
        text = raw.strip()
        if not text:
            return ""

        # Normalize wiki-style bracket wrappers to avoid double-bracketing in output.
        while True:
            if text.startswith("[[") and text.endswith("]]") and len(text) > 4:
                text = text[1:-1].strip()
                continue
            if text.startswith("[") and text.endswith("]") and len(text) > 2:
                text = text[1:-1].strip()
                continue
            break

        return text

    if isinstance(value, list):
        for item in value:
            text = _normalize_history_item(_opt_value(item))
            if text and text != "-":
                items.append(text)
    else:
        text = _normalize_history_item(_opt_value(value))
        if text and text != "-":
            if "," in text:
                items.extend([_normalize_history_item(part) for part in text.split(",") if _normalize_history_item(part)])
            else:
                items.append(text)

    if not items:
        return "-"
    return "[" + ", ".join(items) + "]"


def _extract_timeline_context(issue: Dict[str, Any]) -> Dict[str, str]:
    component_history = _field_value_by_any_name(issue, ["Component History"])
    aged_reason_history = _field_value_by_any_name(issue, ["Aged Reason History"])
    timeline_value = _field_value_by_any_name(issue, ["Timeline"])

    context: Dict[str, str] = {}

    component_history_text = _format_history_value(component_history)
    if component_history_text != "-":
        context["component_history"] = component_history_text

    aged_reason_history_text = _format_history_value(aged_reason_history)
    if aged_reason_history_text != "-":
        context["aged_reason_history"] = aged_reason_history_text

    timeline_text = _clean_timeline_text(timeline_value)
    if _is_meaningful_text(timeline_text):
        context["timeline"] = timeline_text

    return context


def _extract_rca_ca_context(issue: Dict[str, Any]) -> Dict[str, str]:
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        return {}

    result: Dict[str, str] = {}

    values: List[tuple[str, Any]] = [
        ("FI RCA Category", _field_value_by_name(issue, "FI RCA Category")),
        ("Action Taken", _field_value_by_name(issue, "Action Taken")),
        ("RCA Notes", _field_value_by_name(issue, "RCA Notes")),
        ("Bug Signature", _field_value_by_name(issue, "Bug Signature")),
        ("Etrack-Resolution", _field_value_by_any_name(issue, ["Etrack-Resolution", "Etrack Resolution"])),
    ]

    for label, value in values:
        formatted = _format_selected_field_value(value)
        if formatted and formatted != "-":
            result[label] = formatted

    return result


def _clean_timeline_text(value: Any) -> str:
    if value is None:
        return ""

    text = html.unescape(str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Preserve timeline markers such as "<22 Apr 2026 : 12:29 PM>" while stripping HTML tags.
    protected: Dict[str, str] = {}

    def _protect_marker(match: Any) -> str:
        key = f"__TL_MARKER_{len(protected)}__"
        protected[key] = match.group(1)
        return key

    text = re.sub(
        r"(<\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s*:\s*\d{1,2}:\d{2}\s*(?:AM|PM)>)",
        _protect_marker,
        text,
    )

    replacements = [
        (r"<br\s*/?>", "\n"),
        (r"</p>", "\n\n"),
        (r"<p[^>]*>", ""),
        (r"</div>", "\n"),
        (r"<div[^>]*>", ""),
        (r"<li[^>]*>", "\n- "),
        (r"</li>", ""),
        (r"</tr>", "\n"),
        (r"<tr[^>]*>", ""),
        (r"</td>", " | "),
        (r"<td[^>]*>", ""),
        (r"</th>", " | "),
        (r"<th[^>]*>", ""),
        (r"</h[1-6]>", "\n"),
        (r"<h[1-6][^>]*>", "\n"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", " ", text)

    for key, marker in protected.items():
        text = text.replace(key, marker)

    # Enforce a portal-like block structure so timeline remains readable.
    marker_pattern = r"(<\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s*:\s*\d{1,2}:\d{2}\s*(?:AM|PM)>)"
    text = re.sub(rf"\s*{marker_pattern}\s*", r"\n\1\n", text)
    text = re.sub(r"\s*(Next Steps|Current Status)\s*", r"\n\1\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    normalized_lines: List[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            continue

        # Drop table delimiter artifacts like '|', '||', '| |', etc.
        if re.fullmatch(r"[|\s]+", line):
            continue

        parts = [part.strip() for part in re.split(r"\s*\|\s*", line) if part.strip()]
        if parts:
            for part in parts:
                if part != "|" and not re.fullmatch(r"[|\s]+", part):
                    normalized_lines.append(part)
        elif not re.fullmatch(r"[|\s]+", line):
            normalized_lines.append(line)

    final_lines: List[str] = []
    for line in normalized_lines:
        if line == "":
            if final_lines and final_lines[-1] != "":
                final_lines.append("")
            continue

        if re.match(r"^<\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s*:\s*\d{1,2}:\d{2}\s*(?:AM|PM)>$", line):
            if final_lines and final_lines[-1] != "":
                final_lines.append("")
            final_lines.append(line)
            continue

        final_lines.append(line)

    # Final pass: keep timeline headers on separate lines if any were collapsed.
    structured_lines: List[str] = []
    for line in final_lines:
        if line == "":
            if structured_lines and structured_lines[-1] != "":
                structured_lines.append("")
            continue

        parts = re.split(r"\b(Next Steps|Current Status)\b", line)
        if len(parts) == 1:
            structured_lines.append(line)
            continue

        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.casefold() == "next steps":
                part = "----- Next Steps -----"
            structured_lines.append(part)

    return "\n".join(structured_lines).strip()


def _resolve_profile_type(requested_type: str, issue_key: str) -> str:
    normalized = requested_type.strip().lower()
    if normalized == "auto":
        if re.match(r"^FI-\d+$", issue_key):
            return "fi"
        if re.match(r"^PVM-\d+$", issue_key):
            return "pvm"
        return "generic"
    if normalized == "default":
        return "generic"
    return normalized


def _jql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _field_key_to_jql_ref(field_key: str) -> str:
    if field_key.startswith("customfield_"):
        return f"cf[{field_key.split('_', 1)[1]}]"
    return f'"{field_key}"'


def _build_fi_search_jql(jira: JiraClient, raw_query: str) -> str:
    """Build a JQL query to find FI issues linked to an FI key, eTrack incident, or SFDC case.

    Numeric-type fields (etrack incident, etrack ref, case#) only support = equality.
    Text/string fields (Salesforce Case # / Link) support ~ fuzzy search.
    """
    stripped = raw_query.strip()
    if not stripped:
        raise ValueError("Search query is empty")

    clauses: List[str] = []

    # --- Direct FI key(s) (e.g. FI-59868) ---
    fi_keys = [m.upper() for m in re.findall(r"FI-\d+", stripped, re.IGNORECASE)]
    if fi_keys:
        if len(fi_keys) == 1:
            clauses.append(f'key = "{_jql_escape(fi_keys[0])}"')
        else:
            fi_values = ", ".join(f'"{_jql_escape(k)}"' for k in sorted(set(fi_keys)))
            clauses.append(f"key in ({fi_values})")

    # --- Numeric tokens → eTrack Incident (cf[33802]) ---
    # cf[33802] = Etrack Incident : multi-value numeric field; use "in (v)" to match any entry
    # cf[36508] = Etrack Ref      : text field, only supports ~
    # cf[11814] = Case#           : text field, only supports ~
    numeric_tokens = list(dict.fromkeys(re.findall(r"\d{4,}", stripped)))
    if numeric_tokens:
        et_ref = _field_key_to_jql_ref("customfield_33802")
        in_values = ", ".join(numeric_tokens)
        clauses.append(f"{et_ref} in ({in_values})")

    # Text-search fields: Etrack Ref, Case#, Salesforce fields — all use ~
    is_pure_fi_key = re.fullmatch(r"FI-\d+", stripped, re.IGNORECASE) is not None
    if not is_pure_fi_key:
        text_field_keys: List[str] = ["customfield_36508", "customfield_11814"]
        for field_name in ("Salesforce Case #", "Salesforce Case Link"):
            field_key = jira.get_field_key_by_name(field_name)
            if field_key:
                text_field_keys.append(field_key)
        for field_key in text_field_keys:
            field_ref = _field_key_to_jql_ref(field_key)
            clauses.append(f'{field_ref} ~ "{_jql_escape(stripped)}"')

    if not clauses:
        raise ValueError(f"Unable to build FI search JQL for query: {stripped}")

    return f"project = FI AND ({' OR '.join(clauses)}) ORDER BY updated DESC"


def _first_present_display_value(*values: Any) -> str:
    for value in values:
        formatted = _format_selected_field_value(value)
        if formatted and formatted != "-":
            return formatted
    return "-"


def _extract_sfdc_case_number(issue: Dict[str, Any]) -> str:
    fields = issue.get("fields", {})
    return _first_present_display_value(
        _field_value_by_name(issue, "Salesforce Case #"),
        _field_value_by_name(issue, "Case#"),
        fields.get("customfield_11814"),
    )


def _parse_sfdc_case_links(raw: str) -> List[Dict[str, str]]:
    """Parse Jira wiki-markup links: '[label|url] [label|url] ...' -> list of {label, url}."""
    results: List[Dict[str, str]] = []
    for match in re.finditer(r"\[([^|\]]+)\|([^\]]+)\]", raw):
        results.append({"label": match.group(1).strip(), "url": match.group(2).strip()})
    return results


def _format_sfdc_case_links_for_display(links: List[Dict[str, str]]) -> str:
    if not links:
        return "-"

    parts: List[str] = []
    for link in links:
        label = str(link.get("label", "-")).strip() or "-"
        parts.append(label)
    return ", ".join(parts) if parts else "-"


def _print_sfdc_case_links_section(links: List[Dict[str, str]]) -> None:
    print("\n* SalesForce Case Links:")
    rows: List[List[str]] = []
    for link in links:
        label = str(link.get("label", "-")).strip() or "-"
        url = str(link.get("url", "-")).strip() or "-"
        rows.append([label, url])
    _print_table(rows, ["Case #", "Link"])


def _extract_sfdc_case_links(issue: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract SFDC Case Link field using multiple name variations and fallbacks."""
    fields = issue.get("fields", {})
    names = issue.get("names", {})

    # Try standard name variations
    for field_name in ("Salesforce Case Link", "Salesforce Case", "SFDC Case Link"):
        raw = _first_present_display_value(_field_value_by_name(issue, field_name))
        if raw != "-":
            links = _parse_sfdc_case_links(raw)
            if links:
                return links
            # Fallback: treat as plain case number(s)
            links = []
            for token in raw.split():
                token = token.strip(",;")
                if token:
                    links.append({"label": token, "url": "-"})
            if links:
                return links

    # Fallback: search names map for any field containing "salesforce" (case-insensitive)
    for field_key, display_name in names.items():
        if isinstance(display_name, str) and "salesforce" in display_name.lower():
            value = fields.get(field_key)
            if value:
                raw = _format_selected_field_value(value)
                if raw and raw != "-":
                    links = _parse_sfdc_case_links(raw)
                    if links:
                        return links

    return []


def _build_fi_search_result(issue: Dict[str, Any], jira_client: "JiraClient" = None) -> Dict[str, Any]:
    # If the issue doesn't have names mapping (from search endpoint), fetch it directly
    if not issue.get("names") and jira_client and issue.get("key"):
        try:
            issue = jira_client.get_issue(issue["key"])
        except Exception:
            pass  # Fall back to partial data

    fields = issue.get("fields", {})
    etrack_ids = _extract_etrack_ids(issue)
    sfdc_links = _extract_sfdc_case_links(issue)

    return {
        "FI": issue.get("key", "-"),
        "Status": _opt_value(fields.get("status")),
        "Assignee": _opt_value(fields.get("assignee")),
        "Etrack IDs": ", ".join(etrack_ids) if etrack_ids else "-",
        "Etrack Ref": _first_present_display_value(fields.get("customfield_36508")),
        "SFDC Case #": _extract_sfdc_case_number(issue),
        "SFDC Cases": sfdc_links,  # list of {label, url}
        "Summary": _compact_text(fields.get("summary", "-"), max_len=100),
    }


def _print_fi_search_results(raw_query: str, issues: List[Dict[str, Any]], output_format: str, debug: bool = False, jira_client: "JiraClient" = None):
    results = [_build_fi_search_result(issue, jira_client) for issue in issues]

    if output_format == "json":
        # Serialize SFDC Cases as list of {label, url}
        print(json.dumps({"query": raw_query, "matches": results}, indent=2, ensure_ascii=False))
        return

    print(f"FI search query: {raw_query}")
    print(f"Matches: {len(results)}")

    # Debug: show available fields
    if debug and issues:
        print("\n[DEBUG] Checking field data...", file=sys.stderr)
        import sys
        fields = issues[0].get("fields", {})
        names = issues[0].get("names", {})
        print(f"[DEBUG] Total custom fields in response: {len([k for k in fields.keys() if k.startswith('customfield')])}", file=sys.stderr)
        print(f"[DEBUG] Records in 'names' dict: {len(names)}", file=sys.stderr)

        # Show known Case/Salesforce custom field IDs
        print("\n[DEBUG] Known custom fields queried:", file=sys.stderr)
        for cf_id in ["customfield_11814", "customfield_36508", "customfield_33802"]:
            value = fields.get(cf_id, "NOT_PRESENT")
            display_name = names.get(cf_id, "NO_NAME_MAPPING")
            print(f"  {cf_id}: {display_name} = {str(value)[:150]}", file=sys.stderr)

        # Show any field that might contain 'salesforce' or 'case'
        print("\n[DEBUG] All custom fields containing 'salesforce' or 'case':", file=sys.stderr)
        matched = False
        for cf_key in sorted(fields.keys()):
            if "customfield" in cf_key:
                display_name = names.get(cf_key, cf_key)
                if "salesforce" in str(display_name).lower() or "case" in str(display_name).lower():
                    value = fields.get(cf_key, "")
                    print(f"  {cf_key}: {display_name} = {str(value)[:150]}", file=sys.stderr)
                    matched = True
        if not matched:
            print("  (none found)", file=sys.stderr)

        print(file=sys.stderr)

    print()

    # Expand one row per SFDC case link; repeat FI info on subsequent rows.
    rows: List[List[str]] = []
    for item in results:
        sfdc_links = item["SFDC Cases"]  # list of {label, url}
        if not sfdc_links:
            sfdc_links = [{"label": "-", "url": "-"}]
        for idx, link in enumerate(sfdc_links):
            case_num = link["label"]
            case_url = link["url"] if link["url"] != "-" else "-"
            rows.append([
                item["FI"] if idx == 0 else "",
                item["Status"] if idx == 0 else "",
                item["Assignee"] if idx == 0 else "",
                item["Etrack IDs"] if idx == 0 else "",
                item["Etrack Ref"] if idx == 0 else "",
                item["SFDC Case #"] if idx == 0 else "",
                case_num,
                case_url,
                item["Summary"] if idx == 0 else "",
            ])

    _print_table(
        rows,
        ["FI", "Status", "Assignee", "Etrack IDs", "Etrack Ref", "SFDC Case #", "SFDC Case", "SFDC URL", "Summary"],
    )


def _append_if_present(rows: List[List[str]], label: str, value: Any, formatter: Optional[Any] = None):
    if not _has_display_value(value):
        return
    formatted = formatter(value) if formatter else _format_selected_field_value(value)
    if formatted and formatted != "-":
        rows.append([label, formatted])


def _get_default_optional_fields(issue: Dict[str, Any], profile_type: str, etrack_ids: List[str]) -> List[List[str]]:
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        return []

    rows: List[List[str]] = []
    sfdc_case_links = _extract_sfdc_case_links(issue)

    _append_if_present(rows, "Solution", _field_value_by_name(issue, "Solution"))
    _append_if_present(rows, "Progress Status", _field_value_by_name(issue, "Progress Status"))
    _append_if_present(rows, "Severity", fields.get("severity", _field_value_by_name(issue, "Severity")))
    _append_if_present(rows, "Epic Link", _field_value_by_name(issue, "Epic Link"))
    _append_if_present(rows, "Sprint", _field_value_by_name(issue, "Sprint"), formatter=_format_sprint_value)
    _append_if_present(
        rows,
        "Watchers",
        fields.get("watches") or _field_value_by_name(issue, "Watchers"),
        formatter=_format_watchers_value,
    )
    _append_if_present(rows, "Watcher Groups", _field_value_by_name(issue, "Watcher Groups"))

    _append_if_present(rows, "Case Status", fields.get("customfield_16200"))
    _append_if_present(rows, "CAP Involvement", _field_value_by_name(issue, "CAP Involvement"))
    _append_if_present(rows, "Etrack-Resolution", _field_value_by_any_name(issue, ["Etrack-Resolution", "Etrack Resolution"]))
    _append_if_present(rows, "FI RCA Category", _field_value_by_name(issue, "FI RCA Category"))
    _append_if_present(rows, "Action Taken", _field_value_by_name(issue, "Action Taken"))
    # Show actual Etrack Incident field value (customfield_33802)
    _append_if_present(rows, "Etrack Incident", fields.get("customfield_33802"))
    # Show NBU R&D Ticket if different from Etrack Incident
    nbu_rnd_value = _field_value_by_any_name(issue, ["NBU R&D Ticket", "NBU R&D Ticket:"])
    _append_if_present(rows, "NBU R&D Ticket", nbu_rnd_value)
    _append_if_present(rows, "Etrack Ref", fields.get("customfield_36508"))
    _append_if_present(rows, "Case#", fields.get("customfield_11814"))
    if sfdc_case_links:
        rows.append(["SalesForce Case Link", _format_sfdc_case_links_for_display(sfdc_case_links)])
    case_priority_value = _first_present_display_value(
        _field_value_by_name(issue, "Case Priority"),
    )
    if profile_type == "fi":
        rows.append(["Case Priority", case_priority_value if case_priority_value else "-"])
    elif case_priority_value != "-":
        rows.append(["Case Priority", case_priority_value])
    _append_if_present(rows, "Customer", fields.get("customfield_18901"))
    _append_if_present(rows, "Business Unit", _field_value_by_name(issue, "Business Unit"))
    if profile_type == "fi":
        _append_if_present(rows, "Assignee Manager", _field_value_by_name(issue, "Assignee Manager"))
    _append_if_present(rows, "Slack", fields.get("customfield_24004"))

    if profile_type == "pvm":
        _append_if_present(rows, "Security Issue Watchers", _field_value_by_name(issue, "Security Issue Watchers"))
        _append_if_present(rows, "CVSS Score", _field_value_by_name(issue, "CVSS Score"))
        _append_if_present(rows, "Impact", _field_value_by_name(issue, "Impact"))
        _append_if_present(rows, "Source", _field_value_by_name(issue, "Source"))
        _append_if_present(rows, "Security Level", _field_value_by_name(issue, "Security Level"))


    versions_value = _field_value_by_name(issue, "Affects Version/s")
    if not _is_empty_value(versions_value):
        rows.append(["Affects Version/s", _opt_value(versions_value)])

    if profile_type == "fi":
        label_order = {
            "Solution": 1,
            "Progress Status": 2,
            "Severity": 3,
            "Case Status": 4,
            "CAP Involvement": 5,
            "Etrack-Resolution": 6,
            "FI RCA Category": 7,
            "Action Taken": 8,
            "Etrack Incident": 9,
            "NBU R&D Ticket": 10,
            "Etrack Ref": 11,
            "Case#": 12,
            "SalesForce Case Link": 13,
            "Case Priority": 14,
            "Customer": 15,
            "Business Unit": 16,
            "Assignee Manager": 17,
            "Epic Link": 18,
            "Sprint": 19,
            "Watchers": 20,
            "Watcher Groups": 21,
            "Slack": 22,
            "Affects Version/s": 22,
        }
        rows.sort(key=lambda row: label_order.get(row[0], 100))
    elif profile_type == "pvm":
        label_order = {
            "Severity": 1,
            "Security Level": 2,
            "CVSS Score": 3,
            "Impact": 4,
            "Source": 5,
            "Security Issue Watchers": 6,
            "Watchers": 7,
            "Watcher Groups": 8,
            "Epic Link": 9,
            "Sprint": 10,
            "Affects Version/s": 11,
        }
        rows.sort(key=lambda row: label_order.get(row[0], 100))

    return rows


def _build_summary_rows(
    issue_key: str,
    fields: Dict[str, Any],
    comments: List[Dict[str, Any]],
    attachments: List[Dict[str, Any]],
    watchers: Any,
    default_optional_rows: List[List[str]],
) -> List[List[str]]:
    return [
        ["Issue", issue_key],
        ["Summary", fields.get("summary", "-")],
        ["Project", _opt_value(fields.get("project"))],
        ["Type", _opt_value(fields.get("issuetype"))],
        ["Priority", _opt_value(fields.get("priority"))],
        ["Status", _opt_value(fields.get("status"))],
        ["Resolution", _opt_value(fields.get("resolution"))],
        ["Assignee", _opt_value(fields.get("assignee"))],
        ["Reporter", _opt_value(fields.get("reporter"))],
        ["Creator", _opt_value(fields.get("creator"))],
        ["Parent", _opt_value(fields.get("parent"))],
        ["Components", _opt_value(fields.get("components"))],
        ["Labels", _opt_value(fields.get("labels"))],
        ["Fixed Version/s", _opt_value(fields.get("fixVersions"))],
        ["Affects Versions", _opt_value(fields.get("versions"))],
        *default_optional_rows,
        ["Comments", str(len(comments))],
        ["Attachments", str(len(attachments))],
        ["Watcher Count", str(watchers)],
        ["Created", _normalize_timestamp(fields.get("created"))],
        ["Updated", _normalize_timestamp(fields.get("updated"))],
        ["Resolved", _normalize_timestamp(fields.get("resolutiondate"))],
    ]


def _print_summary(summary_rows: List[List[str]], output_format: str, profile_type: str):
    is_cap_fi = _is_cap_fi_profile(summary_rows, profile_type)

    optional_labels = [
        "Solution",
        "Progress Status",
        "Severity",
        "Case Status",
        "CAP Involvement",
        "Etrack-Resolution",
        "FI RCA Category",
        "Action Taken",
        "Etrack Incident",
        "NBU R&D Ticket",
        "Etrack Ref",
        "Case#",
        "SalesForce Case Link",
        "Case Priority",
        "Customer",
        "Business Unit",
        "Assignee Manager",
        "Epic Link",
        "Sprint",
        "Watchers",
        "Watcher Groups",
        "Slack",
        "Fixed Version/s",
        "Affects Version/s",
        "Resolved",
        "Security Issue Watchers",
        "CVSS Score",
        "Impact",
        "Source",
        "Security Level",
    ]

    if output_format == "json":
        print(json.dumps(_summary_rows_to_dict(summary_rows), indent=2, ensure_ascii=False))
        return

    if output_format == "minimal":
        if profile_type == "fi":
            if is_cap_fi:
                print("* CAP-FI PROFILE")
            print(
                f"* Issue: {_summary_value(summary_rows, 'Issue')} | * Status: {_summary_value(summary_rows, 'Status')} | "
                f"* Assignee: {_summary_value(summary_rows, 'Assignee')} | * Customer: {_summary_value(summary_rows, 'Customer')} | "
                f"* Etrack Ref: {_summary_value(summary_rows, 'Etrack Ref')}"
            )
        elif profile_type == "pvm":
            print(
                f"* Issue: {_summary_value(summary_rows, 'Issue')} | * Status: {_summary_value(summary_rows, 'Status')} | "
                f"* Assignee: {_summary_value(summary_rows, 'Assignee')} | * Security Level: {_summary_value(summary_rows, 'Security Level')} | "
                f"* CVSS Score: {_summary_value(summary_rows, 'CVSS Score')} | "
                f"* Fixed Version/s: {_summary_value(summary_rows, 'Fixed Version/s')} | "
                f"* Resolved: {_summary_value(summary_rows, 'Resolved')}"
            )
        else:
            print(
                f"* Issue: {_summary_value(summary_rows, 'Issue')} | * Status: {_summary_value(summary_rows, 'Status')} | "
                f"* Assignee: {_summary_value(summary_rows, 'Assignee')} | * Priority: {_summary_value(summary_rows, 'Priority')}"
            )
        return

    if output_format == "table":
        print()
        if is_cap_fi:
            print("* CAP-FI PROFILE")
        _print_table(summary_rows, ["Field", "Value"])
        return

    if output_format == "grouped":
        print()
        if is_cap_fi:
            print("* CAP-FI PROFILE")
        print(f"* Issue: {_summary_value(summary_rows, 'Issue')}")
        print(f"* Summary: {_summary_value(summary_rows, 'Summary')}")
        print("\n* State:")
        print(f"  * Project: {_summary_value(summary_rows, 'Project')}")
        print(f"  * Type: {_summary_value(summary_rows, 'Type')}")
        print(f"  * Priority: {_summary_value(summary_rows, 'Priority')}")
        print(f"  * Status: {_summary_value(summary_rows, 'Status')}")
        print(f"  * Resolution: {_summary_value(summary_rows, 'Resolution')}")
        print("\n* People:")
        print(f"  * Assignee: {_summary_value(summary_rows, 'Assignee')}")
        print(f"  * Reporter: {_summary_value(summary_rows, 'Reporter')}")
        print(f"  * Creator: {_summary_value(summary_rows, 'Creator')}")
        print("\n* Metadata:")
        print(f"  * Parent: {_summary_value(summary_rows, 'Parent')}")
        print(f"  * Components: {_summary_value(summary_rows, 'Components')}")
        print(f"  * Labels: {_summary_value(summary_rows, 'Labels')}")
        print(f"  * Fixed Version/s: {_summary_value(summary_rows, 'Fixed Version/s')}")
        print(f"  * Affects Versions: {_summary_value(summary_rows, 'Affects Versions')}")
        optional_present = [
            label
            for label in optional_labels
            if _summary_value(summary_rows, label) != "-" or (profile_type == "fi" and label == "Case Priority")
        ]
        if optional_present:
            print("\n* Additional:")
            for label in optional_present:
                print(f"  * {label}: {_summary_value(summary_rows, label)}")
        print("\n* Activity:")
        print(f"  * Comments: {_summary_value(summary_rows, 'Comments')}")
        print(f"  * Attachments: {_summary_value(summary_rows, 'Attachments')}")
        print(f"  * Watcher Count: {_summary_value(summary_rows, 'Watcher Count')}")
        print(f"  * Created: {_summary_value(summary_rows, 'Created')}")
        print(f"  * Updated: {_summary_value(summary_rows, 'Updated')}")
        print(f"  * Resolved: {_summary_value(summary_rows, 'Resolved')}")
        return

    separator = "-" * 140

    print()
    if is_cap_fi:
        print("* CAP-FI PROFILE")
        print(separator)
    print(
        f"* Issue: {_summary_value(summary_rows, 'Issue')} | "
        f"* Project: {_summary_value(summary_rows, 'Project')} | "
        f"* Type: {_summary_value(summary_rows, 'Type')} | "
        f"* Priority: {_summary_value(summary_rows, 'Priority')} | "
        f"* Status: {_summary_value(summary_rows, 'Status')} | "
        f"* Resolution: {_summary_value(summary_rows, 'Resolution')}"
    )
    print(separator)
    print(f"* Summary: {_compact_text(_summary_value(summary_rows, 'Summary'), max_len=180)}")
    print(separator)
    print(
        f"* Assignee: {_summary_value(summary_rows, 'Assignee')} | "
        f"* Reporter: {_summary_value(summary_rows, 'Reporter')} | "
        f"* Components: {_summary_value(summary_rows, 'Components')} | "
        f"* Labels: {_summary_value(summary_rows, 'Labels')}"
    )
    print(separator)

    # Print optional fields in compact format as well
    optional_parts = []
    pvm_long_parts = []
    for label in optional_labels:
        if profile_type != "pvm" and label in {"Fixed Version/s", "Resolved"}:
            continue
        value = _summary_value(summary_rows, label)
        if value == "-" and not (profile_type == "fi" and label == "Case Priority"):
            continue

        if profile_type == "pvm" and label in {"Solution", "Progress Status"}:
            formatted_value = value
        else:
            formatted_value = _compact_text(value, max_len=80)

        field_prefix = "* "
        part = f"{field_prefix}{label}: {formatted_value}"
        if profile_type == "pvm" and label in {"Solution", "Progress Status"}:
            pvm_long_parts.append(part)
        else:
            optional_parts.append(part)

    if optional_parts:
        for part in optional_parts:
            print(part)
        print(separator)
    elif pvm_long_parts:
        for part in pvm_long_parts:
            print(part)
        print(separator)

    print(
        f"* Updated: {_summary_value(summary_rows, 'Updated')} | "
        f"* Comments: {_summary_value(summary_rows, 'Comments')} | "
        f"* Attachments: {_summary_value(summary_rows, 'Attachments')} | "
        f"* Watcher Count: {_summary_value(summary_rows, 'Watcher Count')}"
    )


def _filtered_issue_for_verbose(issue: Dict[str, Any], include_empty_customfields: bool) -> Dict[str, Any]:
    if include_empty_customfields:
        return issue

    cloned_issue: Dict[str, Any] = dict(issue)
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        return cloned_issue

    filtered_fields: Dict[str, Any] = {}
    for key, value in fields.items():
        if key.startswith("customfield_") and _is_empty_value(value):
            continue
        filtered_fields[key] = value

    cloned_issue["fields"] = filtered_fields
    return cloned_issue


def _replace_customfield_keys_with_names(issue: Dict[str, Any]) -> Dict[str, Any]:
    names = issue.get("names")
    if not isinstance(names, dict):
        return issue

    def rename_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            renamed: Dict[str, Any] = {}
            for key, value in obj.items():
                new_key = key
                if isinstance(key, str) and key.startswith("customfield_"):
                    mapped = names.get(key)
                    if isinstance(mapped, str) and mapped.strip():
                        new_key = mapped.strip()
                candidate_key = new_key
                if candidate_key in renamed and candidate_key != key:
                    candidate_key = f"{candidate_key} ({key})"
                renamed[candidate_key] = rename_obj(value)
            return renamed
        if isinstance(obj, list):
            return [rename_obj(item) for item in obj]
        return obj

    transformed = rename_obj(issue)
    if isinstance(transformed, dict):
        transformed.pop("names", None)
    return transformed


def _prune_verbose_noise(issue: Any) -> Any:
    noisy_keys = {
        "avatarUrls",
        "self",
        "iconUrl",
        "thumbnail",
    }

    def prune_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            pruned: Dict[str, Any] = {}
            for key, value in obj.items():
                if key in noisy_keys:
                    continue
                pruned[key] = prune_obj(value)
            return pruned
        if isinstance(obj, list):
            return [prune_obj(item) for item in obj]
        return obj

    return prune_obj(issue)


def _normalize_field_selector(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _split_field_selectors(raw_values: List[str]) -> List[str]:
    selectors: List[str] = []
    for raw in raw_values:
        for part in raw.split(","):
            candidate = part.strip()
            if candidate:
                selectors.append(candidate)
    return selectors


def _resolve_field_selector(issue: Dict[str, Any], selector: str) -> Optional[str]:
    fields = issue.get("fields")
    names = issue.get("names")
    if not isinstance(fields, dict):
        return None

    if selector in fields:
        return selector

    normalized_selector = _normalize_field_selector(selector)
    if isinstance(names, dict):
        for key, display_name in names.items():
            if key in fields and isinstance(display_name, str):
                if _normalize_field_selector(display_name) == normalized_selector:
                    return key
    return None


def _format_selected_field_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        simple_value = _opt_value(value)
        simple_markers = {"value", "name", "displayName", "key"}
        if any(marker in value for marker in simple_markers) and simple_value != "-":
            return simple_value
    if isinstance(value, list):
        simple_items = [_opt_value(item) for item in value]
        filtered = [item for item in simple_items if item and item != "-"]
        if filtered:
            return ", ".join(filtered)

    cleaned_value = _prune_verbose_noise(value)
    return json.dumps(cleaned_value, indent=2, ensure_ascii=False)


def _compact_selected_field_rows(rows: List[List[str]], max_len: int = 200) -> List[List[str]]:
    compact_rows: List[List[str]] = []
    for requested, field_name, value in rows:
        compact_rows.append([requested, field_name, _compact_text(value, max_len=max_len)])
    return compact_rows


def _get_selected_field_rows(issue: Dict[str, Any], selectors: List[str]) -> List[List[str]]:
    fields = issue.get("fields")
    names = issue.get("names")
    if not isinstance(fields, dict):
        return []

    rows: List[List[str]] = []
    for selector in selectors:
        resolved_key = _resolve_field_selector(issue, selector)
        if not resolved_key:
            rows.append([selector, "NOT_FOUND", "-"])
            continue

        display_name = resolved_key
        if isinstance(names, dict):
            mapped_name = names.get(resolved_key)
            if isinstance(mapped_name, str) and mapped_name.strip():
                display_name = mapped_name.strip()

        rows.append([
            selector,
            display_name,
            _format_selected_field_value(fields.get(resolved_key)),
        ])

    return rows


def _build_json_output(
    profile_type: str,
    summary_rows: List[List[str]],
    sfdc_case_links: List[Dict[str, str]],
    status_context: Dict[str, str],
    linked_fis: List[str],
    linked_status: Optional[Dict[str, Dict[str, str]]],
    show_etrack_details: bool,
    etrack_ids: List[str],
    etrack_info: Optional[Dict[str, Dict[str, str]]],
    show_comments: int,
    comments: List[Dict[str, Any]],
    requested_fields: List[str],
    selected_field_rows: List[List[str]],
    subtasks: List[Dict[str, str]],
    timeline_context: Dict[str, str],
    include_timeline_section: bool,
    rca_ca_context: Dict[str, str],
    include_rca_ca_section: bool,
    field_issues_for_customer_rows: List[List[str]],
    include_field_issues_for_customer_section: bool,
    customer_field_issues_headers: Optional[List[str]] = None,
    customer_field_issues_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "profile": profile_type,
        "summary": _summary_rows_to_dict(summary_rows),
    }

    if sfdc_case_links:
        payload["salesforce_case_links"] = [
            {
                "case_number": (str(link.get("label", "-")).strip() or "-"),
                "link": (str(link.get("url", "-")).strip() or "-"),
            }
            for link in sfdc_case_links
        ]

    if status_context:
        payload["current_context"] = status_context

    if linked_fis:
        payload["linked_fis"] = []
        for fi_key in linked_fis:
            item: Dict[str, Any] = {"FI": fi_key}
            if linked_status:
                item.update(linked_status.get(fi_key, {}))
            payload["linked_fis"].append(item)

    if show_etrack_details:
        payload["etrack_details"] = []
        for etrack_id in etrack_ids:
            detail = {"Incident": etrack_id}
            if etrack_info:
                detail.update(etrack_info.get(etrack_id, {}))
            payload["etrack_details"].append(detail)

    if show_comments > 0:
        latest = comments[-show_comments:] if comments else []
        payload["comments"] = [
            {
                "author": (comment.get("author") or {}).get("displayName", "-"),
                "created": _normalize_timestamp(comment.get("created")),
                "body": (comment.get("body") or "").strip(),
            }
            for comment in latest
        ]

    if requested_fields:
        payload["selected_fields"] = [
            {
                "requested": requested,
                "field": field_name,
                "value": value,
            }
            for requested, field_name, value in selected_field_rows
        ]

    if subtasks:
        payload["subtasks"] = subtasks

    if include_timeline_section and timeline_context:
        payload["timeline_context"] = timeline_context

    if include_rca_ca_section and rca_ca_context:
        payload["rca_ca_context"] = rca_ca_context

    if include_field_issues_for_customer_section:
        meta = customer_field_issues_meta or {}
        headers = customer_field_issues_headers or [
            "Key", "Status", "Priority", "Assignee", "Updated", "Summary"
        ]
        payload["customer_field_issues"] = {
            "customer_name": meta.get("customer_name", "-"),
            "active_only": bool(meta.get("active_only", False)),
            "headers": headers,
            "rows": field_issues_for_customer_rows,
        }
        if meta.get("error"):
            payload["customer_field_issues"]["error"] = meta["error"]

    return payload


def _resolve_enabled_sections(mode: str, raw_sections: str) -> Set[str]:
    available_sections = {
        "summary",
        "description",
        "status",
        "customer-field-issues",
        "rca-ca",
        "subtasks",
        "linked-fis",
        "etrack",
        "comments",
        "fields",
        "timeline",
        "verbose",
    }

    mode_defaults: Dict[str, Set[str]] = {
        "standard": {"summary", "description", "status", "rca-ca", "subtasks", "linked-fis", "etrack", "comments", "fields", "verbose"},
        "summary": {"summary", "description"},
        "investigate": {"summary", "description", "status", "rca-ca", "subtasks", "linked-fis", "etrack", "comments", "fields", "timeline", "verbose"},
        "ops": {"summary", "status", "rca-ca", "subtasks", "linked-fis", "etrack", "comments"},
    }

    if raw_sections.strip():
        selected = {part.strip().lower() for part in raw_sections.split(",") if part.strip()}
        invalid = sorted(selected - available_sections)
        if invalid:
            raise ValueError(
                f"Invalid --sections value(s): {', '.join(invalid)}. "
                f"Allowed: {', '.join(sorted(available_sections))}."
            )
        return selected

    return set(mode_defaults.get(mode, mode_defaults["standard"]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Get Jira issue details (generic + FI profiles).",
        usage=(
            "%(prog)s [-h] [-t|--type {auto,fi,pvm,generic,default}] [-s|--search] "
            "[-S|--search-debug] [-e|--show-etrack-details] [-c|--show-comments SHOW_COMMENTS] "
            "[--sub-task|--sub-tasks] "
            "[-m|--mode {standard,summary,investigate,ops}] [-x|--sections sections] "
            "[--timeline] [--list-customer-field-issues] [--list-active-customer-field-issues] "
            "[-E|--show-empty] [-l|--long-text-style {paragraph,wrapped,raw}] "
            "[-w|--wrap-width WRAP_WIDTH] [-d|--desc {none,short,mid,full}] "
            "[-v|--verbose] [-i|--include-empty-customfields] [-f|--show-field SHOW_FIELD] "
            "[-F|--format {compact,grouped,table,minimal,json}] issue_key"
        ),
    )
    parser.add_argument("issue_key", help="Issue key (for example, PROJ-12345)")
    parser.add_argument(
        "-t",
        "--type",
        "-type",
        dest="issue_type",
        default="auto",
        choices=["auto", "fi", "pvm", "generic", "default"],
        help="Profile type: auto (default), fi, pvm, generic, or default.",
    )
    parser.add_argument(
        "-s",
        "--search",
        action="store_true",
        help=(
            "FI search mode. With --type fi, treat the positional value as an FI, "
            "etrack incident, or Salesforce case identifier and return associated FI details."
        ),
    )
    parser.add_argument(
        "-S",
        "--search-debug",
        action="store_true",
        help="With --search, print available Salesforce fields for debugging.",
    )
    parser.add_argument(
        "-e",
        "--show-etrack-details",
        action="store_true",
        help=(
            "If etrack incident IDs are present, fetch and show etrack summary details "
            "(hard override: enables etrack section). "
            "Source codes: EI=Etrack Incident, ER=Etrack Ref, RD=NBU R&D Ticket, INT=Etrack Incident (Internal)."
        ),
    )
    parser.add_argument(
        "-c",
        "--show-comments",
        type=int,
        default=2,
        help="Number of latest comments to show (default: 2). Use 0 to disable comments.",
    )
    parser.add_argument(
        "-st",
        "--sub-task",
        "--sub-tasks",
        dest="sub_tasks",
        action="store_true",
        help=(
            "Include sub-task related information even in modes that do not show it by default. "
            "For Epic issues, this also includes Epic child issues."
        ),
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["standard", "summary", "investigate", "ops"],
        default="standard",
        help="Display preset mode: standard (default), summary, investigate, or ops.",
    )
    parser.add_argument(
        "-x",
        "--sections",
        default="",
        help=(
            "Comma-separated sections to display (overrides --mode). "
            "Allowed: summary,description,status,customer-field-issues,rca-ca,subtasks,linked-fis,etrack,comments,fields,timeline,verbose"
        ),
    )
    parser.add_argument(
        "-tl",
        "--timeline",
        action="store_true",
        help="Include timeline history section (Component History, Aged Reason History, and Timeline field).",
    )
    parser.add_argument(
        "-cfi",
        "--list-customer-field-issues",
        dest="list_customer_field_issues",
        action="store_true",
        help=(
            "List FI issues for the same customer via JQL "
            "(`project = FI AND \"Case Account Name\" ~ \"<customer>\" ORDER BY updated DESC`)."
        ),
    )
    parser.add_argument(
        "-acfi",
        "--list-active-customer-field-issues",
        dest="list_active_customer_field_issues",
        action="store_true",
        help=(
            "Same as --list-customer-field-issues but restricted to active (non-Done) FI issues."
        ),
    )
    parser.add_argument(
        "-E",
        "--show-empty",
        action="store_true",
        help="Show section headers even when no data is available.",
    )
    parser.add_argument(
        "-l",
        "--long-text-style",
        choices=["paragraph", "wrapped", "raw"],
        default="paragraph",
        help="Format for long text fields and comments: paragraph (default), wrapped, or raw.",
    )
    parser.add_argument(
        "-w",
        "--wrap-width",
        type=int,
        default=110,
        help="Wrap width for long text output (default: 110).",
    )
    parser.add_argument(
        "-d",
        "--desc",
        choices=["none", "short", "mid", "full"],
        default="short",
        help="Description display: none (hide), short (default, 300 chars), mid (700 chars), full (no truncation).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose output section with full raw Jira response JSON (hard override: enables verbose section).",
    )
    parser.add_argument(
        "-i",
        "--include-empty-customfields",
        action="store_true",
        help="With --verbose, include customfield_* entries even when null or empty.",
    )
    parser.add_argument(
        "-f",
        "--show-field",
        action="append",
        default=[],
        help=(
            "Show specific Jira fields by field key or display name. "
            "Can be repeated or comma-separated (hard override: enables fields section)."
        ),
    )
    parser.add_argument(
        "-F",
        "--format",
        choices=["compact", "grouped", "table", "minimal", "json"],
        default="compact",
        help="Summary output format: compact (default), grouped, table, minimal, or json.",
    )
    args = parser.parse_args()

    raw_issue_input = args.issue_key.strip()
    if not raw_issue_input:
        print("Issue key/search value cannot be empty")
        return 2

    if args.search and args.issue_type not in {"auto", "fi"}:
        print("Error: --search is only supported with --type fi or --type auto")
        return 2

    issue_key = raw_issue_input.upper()
    if not args.search and not re.match(r"^[A-Z][A-Z0-9_]*-\d+$", issue_key):
        print(f"Invalid Jira issue key format: {issue_key}. Expected PROJECT-<digits>")
        return 2

    profile_type = "fi" if args.search else _resolve_profile_type(args.issue_type, issue_key)
    try:
        enabled_sections = _resolve_enabled_sections(args.mode, args.sections)
        if args.sub_tasks:
            enabled_sections.add("subtasks")
        if args.show_etrack_details:
            enabled_sections.add("etrack")
        if args.verbose:
            enabled_sections.add("verbose")
        if args.show_field:
            enabled_sections.add("fields")
        if args.timeline:
            enabled_sections.add("timeline")
        if args.list_customer_field_issues or args.list_active_customer_field_issues:
            enabled_sections.add("customer-field-issues")
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    try:
        jira = JiraClient()
        if args.search:
            search_jql = _build_fi_search_jql(jira, raw_issue_input)
            issues = jira.search_issues(search_jql)
            if not issues:
                print(f"No matching FI issues found for: {raw_issue_input}")
                return 1
            _print_fi_search_results(raw_issue_input, issues, args.format, debug=args.search_debug, jira_client=jira)
            return 0

        issue = jira.get_issue(issue_key)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    fields = issue.get("fields", {})
    comments = (fields.get("comment") or {}).get("comments", [])
    attachments = fields.get("attachment", [])
    watchers = (fields.get("watches") or {}).get("watchCount", "-")
    status_context = _extract_current_status_and_next_steps(fields, comments)
    linked_fis = _extract_linked_fis(issue)
    linked_status: Optional[Dict[str, Dict[str, str]]] = None
    etrack_sources = _extract_etrack_ids_with_sources(issue)
    etrack_ids = sorted(etrack_sources.keys(), key=int) if etrack_sources else []
    sfdc_case_links = _extract_sfdc_case_links(issue)
    timeline_context = _extract_timeline_context(issue)

    customer_field_issues_active_only = bool(args.list_active_customer_field_issues)
    customer_field_issues_requested = bool(
        args.list_customer_field_issues or args.list_active_customer_field_issues
    )
    customer_field_issues_rows: List[List[str]] = []
    customer_field_issues_headers: List[str] = [
        "Key", "Status", "Priority", "Assignee", "Updated", "Summary"
    ]
    customer_field_issues_meta: Dict[str, Any] = {}
    if customer_field_issues_requested:
        customer_name = _extract_case_account_name(issue, fields)
        customer_field_issues_meta["customer_name"] = customer_name or "-"
        customer_field_issues_meta["active_only"] = customer_field_issues_active_only
        if customer_name:
            try:
                customer_field_issues_rows = _fetch_customer_field_issue_rows(
                    jira, customer_name, active_only=customer_field_issues_active_only
                )
            except RuntimeError as exc:
                customer_field_issues_meta["error"] = str(exc)

    rca_ca_context = _extract_rca_ca_context(issue)
    etrack_info: Optional[Dict[str, Dict[str, str]]] = None
    subtasks = _extract_subtasks(fields)

    # Jira Epics often have no native subtasks[]; when explicitly requested,
    # fall back to listing Epic child issues.
    issue_type_name = str((fields.get("issuetype") or {}).get("name", "")).strip().lower()
    if args.sub_tasks and not subtasks and issue_type_name == "epic":
        epic_children: List[Dict[str, Any]] = []
        epic_key_escaped = _jql_escape(issue.get("key", issue_key))
        for epic_jql in [
            f'"Epic Link" = "{epic_key_escaped}" ORDER BY key ASC',
            f'parent = "{epic_key_escaped}" ORDER BY key ASC',
        ]:
            try:
                epic_children = jira.search_issues(epic_jql, max_results=500)
            except RuntimeError:
                continue
            if epic_children:
                break
        if epic_children:
            subtasks = _extract_subtasks_from_issues(epic_children)

    sections_override_active = bool(args.sections.strip())
    show_etrack_requested = (
        args.show_etrack_details
        or args.mode in {"investigate", "ops"}
        or (sections_override_active and "etrack" in enabled_sections)
    )

    if linked_fis:
        try:
            linked_status = jira.get_issue_status_batch(linked_fis)
        except RuntimeError as exc:
            if args.format == "json":
                linked_status = {fi_key: {"error": str(exc)} for fi_key in linked_fis}
            else:
                print("\nLinked FIs:")
                print(f"  Unable to fetch linked FI statuses: {exc}")

    if show_etrack_requested and etrack_ids:
        etrack_info = _fetch_etrack_details(etrack_ids)

    requested_fields = _split_field_selectors(args.show_field)
    default_optional_rows = _get_default_optional_fields(issue, profile_type, etrack_ids)
    summary_rows = _build_summary_rows(
        issue.get("key", issue_key),
        fields,
        comments,
        attachments,
        watchers,
        default_optional_rows,
    )
    selected_field_rows: List[List[str]] = []

    if requested_fields:
        selected_field_rows = _get_selected_field_rows(issue, requested_fields)

    if args.format == "json":
        subtasks_for_output = subtasks if "subtasks" in enabled_sections else []
        json_payload = _build_json_output(
            profile_type,
            summary_rows,
            sfdc_case_links,
            status_context,
            linked_fis,
            linked_status,
            show_etrack_requested,
            etrack_ids,
            etrack_info,
            args.show_comments,
            comments,
            requested_fields,
            selected_field_rows,
            subtasks_for_output,
            timeline_context,
            "timeline" in enabled_sections,
            rca_ca_context,
            "rca-ca" in enabled_sections,
            field_issues_for_customer_rows=customer_field_issues_rows,
            include_field_issues_for_customer_section="customer-field-issues" in enabled_sections,
            customer_field_issues_headers=customer_field_issues_headers,
            customer_field_issues_meta=customer_field_issues_meta,
        )
        print(json.dumps(json_payload, indent=2, ensure_ascii=False))
        return 0

    print(
        f"profile={profile_type} type_arg={args.issue_type} mode={args.mode} "
        f"format={args.format} desc={args.desc} comments={args.show_comments} "
        f"etrack={'on' if show_etrack_requested else 'off'} "
        f"long={args.long_text_style}/{args.wrap_width}"
    )
    section_separator = "-" * 140

    if "summary" in enabled_sections:
        _print_summary(summary_rows, args.format, profile_type)

    description = fields.get("description")
    _desc_max_len = {"short": 300, "mid": 700, "full": 0}
    if "description" in enabled_sections:
        if args.desc != "none" and description and _is_meaningful_text(_clean_text(description)):
            print(section_separator)
            print("\n* Description:")
            print(
                _format_multiline_text(
                    description,
                    max_len=_desc_max_len.get(args.desc, 300),
                    width=args.wrap_width,
                    indent="  ",
                    style=args.long_text_style,
                )
            )
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Description: None")
            print(section_separator)

    if "status" in enabled_sections:
        aged_reason_value = _format_selected_field_value(_field_value_by_name(issue, "Aged Reason"))
        if status_context:
            print(section_separator)
            if aged_reason_value != "-":
                print(f"\n* Aged Reason: {aged_reason_value}")
            print("\n* Current Status / Next Steps:")
            if "current_status" in status_context:
                print("  * Current Status:")
                print(
                    _format_multiline_text(
                        status_context["current_status"],
                        max_len=450,
                        width=args.wrap_width,
                        style=args.long_text_style,
                    )
                )
            if "next_steps" in status_context:
                if "current_status" in status_context:
                    print()
                print("  * Next Steps:")
                print(
                    _format_multiline_text(
                        status_context["next_steps"],
                        max_len=450,
                        width=args.wrap_width,
                        style=args.long_text_style,
                    )
                )
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            if aged_reason_value != "-":
                print(f"\n* Aged Reason: {aged_reason_value}")
            print("\n* Current Status / Next Steps: None")
            print(section_separator)

    if "customer-field-issues" in enabled_sections:
        if customer_field_issues_requested:
            customer_name = customer_field_issues_meta.get("customer_name", "-")
            label_suffix = " (active only)" if customer_field_issues_active_only else ""
            print(section_separator)
            print(f"\n* Customer Field Issues{label_suffix} (customer: {customer_name}):")
            if customer_field_issues_meta.get("error"):
                print(f"  Unable to fetch customer field issues: {customer_field_issues_meta['error']}")
            elif not customer_name or customer_name == "-":
                print("  Customer (Case Account Name) is not set on this issue.")
            elif customer_field_issues_rows:
                _print_table(customer_field_issues_rows, customer_field_issues_headers)
            else:
                print("  No matching FI issues found.")
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Customer Field Issues: None")
            print(section_separator)

    if "rca-ca" in enabled_sections:
        if rca_ca_context:
            print(section_separator)
            print("\n* RCA-CA:")
            for label in ["FI RCA Category", "Action Taken", "RCA Notes", "Bug Signature", "Etrack-Resolution"]:
                value = rca_ca_context.get(label)
                if not value:
                    continue
                print(f"  * {label}:")
                print(
                    _format_multiline_text(
                        value,
                        max_len=0,
                        width=args.wrap_width,
                        indent="    ",
                        style=args.long_text_style,
                    )
                )
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* RCA-CA: None")
            print(section_separator)

    if "subtasks" in enabled_sections:
        if subtasks:
            print(section_separator)
            print("\n* Sub-tasks:")
            rows = []
            for item in subtasks:
                rows.append([
                    item.get("key", "-"),
                    item.get("type", "-"),
                    item.get("status", "-"),
                    item.get("assignee", "-"),
                    item.get("summary", "-"),
                ])
            _print_table(rows, ["Key", "Type", "Status", "Assignee", "Summary"])
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Sub-tasks: None")
            print(section_separator)

    if "linked-fis" in enabled_sections:
        if linked_fis:
            print(section_separator)
            print("\n* Linked FIs:")
            rows = []
            for linked_key in linked_fis:
                data = (linked_status or {}).get(linked_key, {})
                rows.append([
                    linked_key,
                    data.get("status", "-"),
                    data.get("resolution", "-"),
                    data.get("assignee", "-"),
                    data.get("updated", "-"),
                ])
            _print_table(rows, ["FI", "Status", "Resolution", "Assignee", "Updated"])
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Linked FIs: None")
            print(section_separator)

    if "etrack" in enabled_sections:
        if show_etrack_requested:
            print(section_separator)
            print("\n* Etrack details:")
            if not etrack_ids:
                print("  * No etrack incident linked in Jira fields.")
            else:
                rows = []
                for et in etrack_ids:
                    info = (etrack_info or {}).get(et, {})
                    source_list = etrack_sources.get(et, [])
                    source_str = ", ".join(source_list) if source_list else "-"
                    rows.append([
                        et,
                        source_str,
                        info.get("state", "-"),
                        info.get("severity", "-"),
                        info.get("priority", "-"),
                        info.get("version", "-"),
                        info.get("component", "-"),
                        info.get("assignee", "-"),
                        info.get("abstract", "-"),
                    ])
                _print_table(rows, ["Incident", "Src", "State", "Severity", "Priority", "Version", "Component", "Assignee", "Abstract"])
                print("  Legend: EI=Etrack Incident, ER=Etrack Ref, RD=NBU R&D Ticket, INT=Etrack Incident (Internal)")

            if args.show_etrack_details:
                if sfdc_case_links:
                    _print_sfdc_case_links_section(sfdc_case_links)
                elif args.show_empty:
                    print("\n* SalesForce Case Links: None")
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Etrack details: disabled (use --show-etrack-details or mode investigate/ops)")
            print(section_separator)

    if "comments" in enabled_sections:
        if args.show_comments > 0 and comments:
            print(section_separator)
            print(f"\n* Latest {min(args.show_comments, len(comments))} comment(s):")
            latest = comments[-args.show_comments:]
            for index, comment in enumerate(latest, 1):
                author = (comment.get("author") or {}).get("displayName", "-")
                created = _normalize_timestamp(comment.get("created"))
                print(f"  * {index}. {author} @ {created}")
                print(
                    _format_multiline_text(
                        comment.get("body"),
                        max_len=450,
                        width=args.wrap_width,
                        indent="     ",
                        style=args.long_text_style,
                    )
                )
                if index < len(latest):
                    print()
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Comments: None")
            print(section_separator)

    if "fields" in enabled_sections:
        if requested_fields:
            print(section_separator)
            print("\n* Selected Fields:")
            _print_table(_compact_selected_field_rows(selected_field_rows), ["Requested", "Field", "Value"])
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Selected Fields: None (use --show-field)")
            print(section_separator)

    if "timeline" in enabled_sections:
        if timeline_context:
            print(section_separator)
            print("\n* Timeline:")

            if "component_history" in timeline_context:
                print(f"  * Component History: {timeline_context['component_history']}")

            if "aged_reason_history" in timeline_context:
                print(f"  * Aged Reason History: {timeline_context['aged_reason_history']}")

            if "timeline" in timeline_context:
                print("  * Timeline:")
                print(
                    _format_multiline_text(
                        timeline_context["timeline"],
                        max_len=0,
                        width=args.wrap_width,
                        indent="    ",
                        style="raw",
                    )
                )
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\n* Timeline: None")
            print(section_separator)

    if "verbose" in enabled_sections and args.verbose:
        print(section_separator)
        print("\n* Verbose Output:")
        verbose_issue = _filtered_issue_for_verbose(issue, args.include_empty_customfields)
        verbose_issue = _replace_customfield_keys_with_names(verbose_issue)
        verbose_issue = _prune_verbose_noise(verbose_issue)
        print(json.dumps(verbose_issue, indent=2, ensure_ascii=False))
        print(section_separator)
    elif "verbose" in enabled_sections and args.show_empty:
        print(section_separator)
        print("\n* Verbose Output: disabled (use --verbose)")
        print(section_separator)

    return 0


if __name__ == "__main__":
    sys.exit(main())