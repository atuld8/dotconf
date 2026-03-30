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
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

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


def _extract_etrack_ids(fields: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []

    main_et = fields.get("customfield_33802")
    if main_et:
        candidates.extend(re.findall(r"\d+", str(main_et)))

    alt_et = fields.get("customfield_36508")
    if alt_et:
        candidates.extend(re.findall(r"\d+", str(alt_et)))

    return sorted(set(candidates), key=int)


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
                "abstract": abstract,
            }
        else:
            details[et] = {
                "state": "-",
                "assignee": "-",
                "severity": "-",
                "priority": "-",
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

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {"expand": "names"}
        response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
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
        response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to search issues: {response.status_code} {response.text[:400]}")
        return response.json().get("issues", [])

    def get_field_key_by_name(self, display_name: str) -> Optional[str]:
        if self._fields_by_name is None:
            url = f"{self.base_url}/rest/api/2/field"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
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

        response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
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


def _resolve_profile_type(requested_type: str, issue_key: str) -> str:
    normalized = requested_type.strip().lower()
    if normalized == "auto":
        return "fi" if re.match(r"^FI-\d+$", issue_key) else "generic"
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
    print("\nSalesForce Case Links:")
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
    etrack_ids = _extract_etrack_ids(fields)
    sfdc_links = _extract_sfdc_case_links(issue)

    return {
        "FI": issue.get("key", "-"),
        "Status": _opt_value(fields.get("status")),
        "Assignee": _opt_value(fields.get("assignee")),
        "Etrack Incident": ", ".join(etrack_ids) if etrack_ids else "-",
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
                item["Etrack Incident"] if idx == 0 else "",
                item["Etrack Ref"] if idx == 0 else "",
                item["SFDC Case #"] if idx == 0 else "",
                case_num,
                case_url,
                item["Summary"] if idx == 0 else "",
            ])

    _print_table(
        rows,
        ["FI", "Status", "Assignee", "Etrack Incident", "Etrack Ref", "SFDC Case #", "SFDC Case", "SFDC URL", "Summary"],
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
    if etrack_ids:
        rows.append(["Etrack Incident", ", ".join(etrack_ids)])
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
    _append_if_present(rows, "Slack", fields.get("customfield_24004"))

    if profile_type == "fi":
        label_order = {
            "Solution": 1,
            "Progress Status": 2,
            "Severity": 3,
            "Case Status": 4,
            "Etrack Incident": 5,
            "Etrack Ref": 6,
            "Case#": 7,
            "SalesForce Case Link": 8,
            "Case Priority": 9,
            "Customer": 10,
            "Epic Link": 11,
            "Sprint": 12,
            "Watchers": 13,
            "Watcher Groups": 14,
            "Slack": 15,
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
        ["Fix Versions", _opt_value(fields.get("fixVersions"))],
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
    optional_labels = [
        "Solution",
        "Progress Status",
        "Severity",
        "Case Status",
        "Etrack Incident",
        "Etrack Ref",
        "Case#",
        "SalesForce Case Link",
        "Case Priority",
        "Customer",
        "Epic Link",
        "Sprint",
        "Watchers",
        "Watcher Groups",
        "Slack",
    ]

    if output_format == "json":
        print(json.dumps(_summary_rows_to_dict(summary_rows), indent=2, ensure_ascii=False))
        return

    if output_format == "minimal":
        if profile_type == "fi":
            print(
                f"{_summary_value(summary_rows, 'Issue')} | {_summary_value(summary_rows, 'Status')} | "
                f"{_summary_value(summary_rows, 'Assignee')} | {_summary_value(summary_rows, 'Customer')} | "
                f"{_summary_value(summary_rows, 'Etrack Ref')}"
            )
        else:
            print(
                f"{_summary_value(summary_rows, 'Issue')} | {_summary_value(summary_rows, 'Status')} | "
                f"{_summary_value(summary_rows, 'Assignee')} | {_summary_value(summary_rows, 'Priority')}"
            )
        return

    if output_format == "table":
        print()
        _print_table(summary_rows, ["Field", "Value"])
        return

    if output_format == "grouped":
        print()
        print(f"Issue: {_summary_value(summary_rows, 'Issue')}")
        print(f"Summary: {_summary_value(summary_rows, 'Summary')}")
        print("\nState:")
        print(f"  Project: {_summary_value(summary_rows, 'Project')}")
        print(f"  Type: {_summary_value(summary_rows, 'Type')}")
        print(f"  Priority: {_summary_value(summary_rows, 'Priority')}")
        print(f"  Status: {_summary_value(summary_rows, 'Status')}")
        print(f"  Resolution: {_summary_value(summary_rows, 'Resolution')}")
        print("\nPeople:")
        print(f"  Assignee: {_summary_value(summary_rows, 'Assignee')}")
        print(f"  Reporter: {_summary_value(summary_rows, 'Reporter')}")
        print(f"  Creator: {_summary_value(summary_rows, 'Creator')}")
        print("\nMetadata:")
        print(f"  Parent: {_summary_value(summary_rows, 'Parent')}")
        print(f"  Components: {_summary_value(summary_rows, 'Components')}")
        print(f"  Labels: {_summary_value(summary_rows, 'Labels')}")
        print(f"  Fix Versions: {_summary_value(summary_rows, 'Fix Versions')}")
        print(f"  Affects Versions: {_summary_value(summary_rows, 'Affects Versions')}")
        optional_present = [
            label
            for label in optional_labels
            if _summary_value(summary_rows, label) != "-" or (profile_type == "fi" and label == "Case Priority")
        ]
        if optional_present:
            print("\nAdditional:")
            for label in optional_present:
                print(f"  {label}: {_summary_value(summary_rows, label)}")
        print("\nActivity:")
        print(f"  Comments: {_summary_value(summary_rows, 'Comments')}")
        print(f"  Attachments: {_summary_value(summary_rows, 'Attachments')}")
        print(f"  Watcher Count: {_summary_value(summary_rows, 'Watcher Count')}")
        print(f"  Created: {_summary_value(summary_rows, 'Created')}")
        print(f"  Updated: {_summary_value(summary_rows, 'Updated')}")
        print(f"  Resolved: {_summary_value(summary_rows, 'Resolved')}")
        return

    separator = "-" * 140

    print()
    print(
        f"Issue: {_summary_value(summary_rows, 'Issue')} | "
        f"Project: {_summary_value(summary_rows, 'Project')} | "
        f"Type: {_summary_value(summary_rows, 'Type')} | "
        f"Priority: {_summary_value(summary_rows, 'Priority')} | "
        f"Status: {_summary_value(summary_rows, 'Status')} | "
        f"Resolution: {_summary_value(summary_rows, 'Resolution')}"
    )
    print(separator)
    print(f"Summary: {_compact_text(_summary_value(summary_rows, 'Summary'), max_len=180)}")
    print(separator)
    print(
        f"Assignee: {_summary_value(summary_rows, 'Assignee')} | "
        f"Reporter: {_summary_value(summary_rows, 'Reporter')} | "
        f"Components: {_summary_value(summary_rows, 'Components')} | "
        f"Labels: {_summary_value(summary_rows, 'Labels')}"
    )
    print(separator)
    optional_parts = [
        f"{label}: {_compact_text(_summary_value(summary_rows, label), max_len=80)}"
        for label in optional_labels
        if _summary_value(summary_rows, label) != "-" or (profile_type == "fi" and label == "Case Priority")
    ]
    if optional_parts:
        _print_compact_segments(optional_parts)
        print(separator)
    print(
        f"Updated: {_summary_value(summary_rows, 'Updated')} | "
        f"Comments: {_summary_value(summary_rows, 'Comments')} | "
        f"Attachments: {_summary_value(summary_rows, 'Attachments')} | "
        f"Watcher Count: {_summary_value(summary_rows, 'Watcher Count')}"
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

    return payload


def _resolve_enabled_sections(mode: str, raw_sections: str) -> Set[str]:
    available_sections = {
        "summary",
        "description",
        "status",
        "linked-fis",
        "etrack",
        "comments",
        "fields",
        "verbose",
    }

    mode_defaults: Dict[str, Set[str]] = {
        "standard": {"summary", "description", "status", "linked-fis", "etrack", "comments", "fields", "verbose"},
        "summary": {"summary", "description"},
        "investigate": {"summary", "description", "status", "linked-fis", "etrack", "comments", "fields", "verbose"},
        "ops": {"summary", "status", "linked-fis", "etrack", "comments"},
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
            "%(prog)s [-h] [-t|--type {auto,fi,generic,default}] [-s|--search] "
            "[-S|--search-debug] [-e|--show-etrack-details] [-c|--show-comments SHOW_COMMENTS] "
            "[-m|--mode {standard,summary,investigate,ops}] [-x|--sections SECTIONS] "
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
        choices=["auto", "fi", "generic", "default"],
        help="Profile type: auto (default), fi, generic, or default.",
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
        help="If etrack incident IDs are present, fetch and show etrack summary details.",
    )
    parser.add_argument(
        "-c",
        "--show-comments",
        type=int,
        default=2,
        help="Number of latest comments to show (default: 2). Use 0 to disable comments.",
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
            "Allowed: summary,description,status,linked-fis,etrack,comments,fields,verbose"
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
        help="Show verbose output section with full raw Jira response JSON.",
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
        help="Show specific Jira fields by field key or display name. Can be repeated or comma-separated.",
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
    etrack_ids = _extract_etrack_ids(fields)
    sfdc_case_links = _extract_sfdc_case_links(issue)
    etrack_info: Optional[Dict[str, Dict[str, str]]] = None
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
            print("\nDescription:")
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
            print("\nDescription: None")
            print(section_separator)

    if "status" in enabled_sections:
        if status_context:
            print(section_separator)
            print("\nCurrent Status / Next Steps:")
            if "current_status" in status_context:
                print("  Current Status:")
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
                print("  Next Steps:")
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
            print("\nCurrent Status / Next Steps: None")
            print(section_separator)

    if "linked-fis" in enabled_sections:
        if linked_fis:
            print(section_separator)
            print("\nLinked FIs:")
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
            print("\nLinked FIs: None")
            print(section_separator)

    if "etrack" in enabled_sections:
        if show_etrack_requested:
            print(section_separator)
            print("\nEtrack details:")
            if not etrack_ids:
                print("  No etrack incident linked in Jira fields.")
            else:
                rows = []
                for et in etrack_ids:
                    info = (etrack_info or {}).get(et, {})
                    rows.append([
                        et,
                        info.get("state", "-"),
                        info.get("severity", "-"),
                        info.get("priority", "-"),
                        info.get("assignee", "-"),
                        info.get("abstract", "-"),
                    ])
                _print_table(rows, ["Incident", "State", "Severity", "Priority", "Assignee", "Abstract"])

            if args.show_etrack_details:
                if sfdc_case_links:
                    _print_sfdc_case_links_section(sfdc_case_links)
                elif args.show_empty:
                    print("\nSalesForce Case Links: None")
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\nEtrack details: disabled (use --show-etrack-details or mode investigate/ops)")
            print(section_separator)

    if "comments" in enabled_sections:
        if args.show_comments > 0 and comments:
            print(section_separator)
            print(f"\nLatest {min(args.show_comments, len(comments))} comment(s):")
            latest = comments[-args.show_comments:]
            for index, comment in enumerate(latest, 1):
                author = (comment.get("author") or {}).get("displayName", "-")
                created = _normalize_timestamp(comment.get("created"))
                print(f"  {index}. {author} @ {created}")
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
            print("\nComments: None")
            print(section_separator)

    if "fields" in enabled_sections:
        if requested_fields:
            print(section_separator)
            print("\nSelected Fields:")
            _print_table(_compact_selected_field_rows(selected_field_rows), ["Requested", "Field", "Value"])
            print(section_separator)
        elif args.show_empty:
            print(section_separator)
            print("\nSelected Fields: None (use --show-field)")
            print(section_separator)

    if "verbose" in enabled_sections and args.verbose:
        print(section_separator)
        print("\nVerbose Output:")
        verbose_issue = _filtered_issue_for_verbose(issue, args.include_empty_customfields)
        verbose_issue = _replace_customfield_keys_with_names(verbose_issue)
        verbose_issue = _prune_verbose_noise(verbose_issue)
        print(json.dumps(verbose_issue, indent=2, ensure_ascii=False))
        print(section_separator)
    elif "verbose" in enabled_sections and args.show_empty:
        print(section_separator)
        print("\nVerbose Output: disabled (use --verbose)")
        print(section_separator)

    return 0


if __name__ == "__main__":
    sys.exit(main())