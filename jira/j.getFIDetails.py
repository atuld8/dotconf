#!/usr/bin/env python3

"""
Fetch and print FI details from Jira with linked FI statuses.

Features:
- Fetch FI details using: /rest/api/2/issue/<FI-ID>
- Show core FI metadata in clean console output
- Show linked FI statuses (from issuelinks + Case FIs field)
- Optional etrack summary using --show-etrack-details

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
        vals = []
        for item in field:
            if isinstance(item, dict):
                vals.append(_opt_value(item))
            else:
                vals.append(str(item))
        vals = [v for v in vals if v and v != "-"]
        return ", ".join(vals) if vals else "-"
    return str(field)


class JiraClient:
    def __init__(self):
        load_dotenv()
        self.server = os.getenv("JIRA_SERVER_NAME")
        self.token = os.getenv("JIRA_ACC_TOKEN")
        self.base_url = f"https://{self.server}" if self.server else None
        self.timeout = 30

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

    def get_issue_status_batch(self, issue_keys: List[str]) -> Dict[str, Dict[str, str]]:
        if not issue_keys:
            return {}

        unique_keys = sorted(set(issue_keys))
        key_str = ", ".join(unique_keys)
        jql = f"key in ({key_str})"

        url = f"{self.base_url}/rest/api/2/search"
        params = {
            "jql": jql,
            "maxResults": len(unique_keys),
            "fields": "status,resolution,assignee,priority,updated",
        }

        response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch linked FI statuses: {response.status_code} {response.text[:400]}"
            )

        payload = response.json()
        result = {}
        for issue in payload.get("issues", []):
            fields = issue.get("fields", {})
            assignee = fields.get("assignee") or {}
            result[issue.get("key", "")] = {
                "status": _opt_value(fields.get("status")),
                "resolution": _opt_value(fields.get("resolution")),
                "assignee": _opt_value(assignee),
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


def _extract_linked_fis(issue_data: Dict[str, Any]) -> List[str]:
    fields = issue_data.get("fields", {})
    fi_set: Set[str] = set()

    # 1) From explicit issue links
    for link in fields.get("issuelinks", []):
        for side in ("inwardIssue", "outwardIssue"):
            issue = link.get(side)
            if not issue:
                continue
            key = issue.get("key", "")
            if re.match(r"^FI-\d+$", key):
                fi_set.add(key)

    # 2) From Case FIs style field: e.g. "FI-59142,FI-61974"
    case_fis = fields.get("customfield_20707")
    if case_fis:
        text = str(case_fis)
        for found in re.findall(r"FI-\d+", text):
            fi_set.add(found)

    return sorted(fi_set, key=lambda x: int(x.split("-")[1]))


def _extract_etrack_ids(fields: Dict[str, Any]) -> List[str]:
    candidates = []

    # Main etrack incident custom field (typically numeric or comma-separated)
    main_et = fields.get("customfield_33802")
    if main_et:
        candidates.extend(re.findall(r"\d+", str(main_et)))

    # Alternate textual etrack field may contain "ET-4216356"
    alt_et = fields.get("customfield_36508")
    if alt_et:
        candidates.extend(re.findall(r"\d+", str(alt_et)))

    # Unique, preserve numeric order
    unique = sorted(set(candidates), key=int)
    return unique


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
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


def _format_multiline_text(value: Any, max_len: int = 450, width: int = 110, indent: str = "    ") -> str:
    compact = _compact_text(value, max_len=max_len)
    if compact == "-":
        return "-"
    return textwrap.fill(compact, width=width, initial_indent=indent, subsequent_indent=indent)


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
    return normalized not in placeholders


def _extract_current_status_and_next_steps(fields: Dict[str, Any], comments: List[Dict[str, Any]]) -> Dict[str, str]:
    current_status = _clean_text(fields.get("customfield_11202"))
    next_steps = _clean_text(fields.get("customfield_11203"))

    table_text = str(fields.get("customfield_27600") or "")
    if table_text:
        if not _is_meaningful_text(current_status):
            status_match = re.search(
                r"Current\s*Status</b>\s*</td>\s*</tr>\s*<tr>\s*<td>(.*?)</td>",
                table_text,
                re.IGNORECASE | re.DOTALL,
            )
            if status_match:
                current_status = _clean_text(status_match.group(1))

        if not _is_meaningful_text(next_steps):
            next_steps_match = re.search(
                r"Next\s*Steps</b>\s*</td>\s*</tr>\s*<tr>\s*<td>(.*?)</td>",
                table_text,
                re.IGNORECASE | re.DOTALL,
            )
            if next_steps_match:
                next_steps = _clean_text(next_steps_match.group(1))

    if not (_is_meaningful_text(current_status) and _is_meaningful_text(next_steps)):
        for comment in reversed(comments):
            body = _clean_text((comment.get("body") or ""))
            if not body:
                continue

            if not _is_meaningful_text(current_status):
                status_match = re.search(r"Current\s*Status\s*[:=]\s*(.+?)(?:\*|$)", body, re.IGNORECASE)
                if status_match:
                    candidate = _clean_text(status_match.group(1))
                    if _is_meaningful_text(candidate):
                        current_status = candidate

            if not _is_meaningful_text(next_steps):
                next_steps_match = re.search(r"Next\s*Steps\s*[:=]\s*(.+?)(?:\*|$)", body, re.IGNORECASE)
                if next_steps_match:
                    candidate = _clean_text(next_steps_match.group(1))
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
        # When launched from jira/ directly, parent workspace root may not be in sys.path
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
                "abstract": abstract,
            }
        else:
            details[et] = {
                "state": "-",
                "assignee": "-",
                "abstract": "No etrack details found",
            }
    return details


def _print_table(rows: List[List[str]], headers: List[str]):
    if tabulate:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
        return

    # Fallback simple formatter
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))

    def fmt(values: List[str]) -> str:
        return " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))


def _summary_rows_to_dict(summary_rows: List[List[str]]) -> Dict[str, str]:
    return {label: value for label, value in summary_rows}


def _build_summary_rows(
    issue_key: str,
    fields: Dict[str, Any],
    comments: List[Dict[str, Any]],
    attachments: List[Dict[str, Any]],
    watchers: Any,
    etrack_ids: List[str],
) -> List[List[str]]:
    etrack_label = ", ".join(etrack_ids) if etrack_ids else "-"
    return [
        ["FI", issue_key],
        ["Summary", fields.get("summary", "-")],
        ["Type", _opt_value(fields.get("issuetype"))],
        ["Priority", _opt_value(fields.get("priority"))],
        ["Status", _opt_value(fields.get("status"))],
        ["Resolution", _opt_value(fields.get("resolution"))],
        ["Case Status", _opt_value(fields.get("customfield_16200"))],
        ["Assignee", _opt_value(fields.get("assignee"))],
        ["Reporter", _opt_value(fields.get("reporter"))],
        ["Creator", _opt_value(fields.get("creator"))],
        ["Etrack Incident", etrack_label],
        ["Etrack Ref", _opt_value(fields.get("customfield_36508"))],
        ["Case#", _opt_value(fields.get("customfield_11814"))],
        ["Customer", _opt_value(fields.get("customfield_18901"))],
        ["Component", _opt_value(fields.get("components"))],
        ["Slack", _opt_value(fields.get("customfield_24004"))],
        ["Comments", str(len(comments))],
        ["Attachments", str(len(attachments))],
        ["Watchers", str(watchers)],
        ["Created", _normalize_timestamp(fields.get("created"))],
        ["Updated", _normalize_timestamp(fields.get("updated"))],
        ["Resolved", _normalize_timestamp(fields.get("resolutiondate"))],
    ]


def _summary_value(summary_rows: List[List[str]], label: str) -> str:
    for row_label, row_value in summary_rows:
        if row_label == label:
            return row_value
    return "-"


def _print_summary(summary_rows: List[List[str]], output_format: str):
    if output_format == "json":
        print(json.dumps(_summary_rows_to_dict(summary_rows), indent=2, ensure_ascii=False))
        return

    if output_format == "minimal":
        print(
            f"{_summary_value(summary_rows, 'FI')} | {_summary_value(summary_rows, 'Status')} | "
            f"{_summary_value(summary_rows, 'Assignee')} | {_summary_value(summary_rows, 'Customer')} | "
            f"{_summary_value(summary_rows, 'Etrack Ref')}"
        )
        return

    if output_format == "table":
        print()
        _print_table(summary_rows, ["Field", "Value"])
        return

    if output_format == "grouped":
        print()
        print(f"FI: {_summary_value(summary_rows, 'FI')}")
        print(f"Summary: {_summary_value(summary_rows, 'Summary')}")
        print("\nState:")
        print(f"  Type: {_summary_value(summary_rows, 'Type')}")
        print(f"  Priority: {_summary_value(summary_rows, 'Priority')}")
        print(f"  Status: {_summary_value(summary_rows, 'Status')}")
        print(f"  Resolution: {_summary_value(summary_rows, 'Resolution')}")
        print(f"  Case Status: {_summary_value(summary_rows, 'Case Status')}")
        print("\nPeople:")
        print(f"  Assignee: {_summary_value(summary_rows, 'Assignee')}")
        print(f"  Reporter: {_summary_value(summary_rows, 'Reporter')}")
        print(f"  Creator: {_summary_value(summary_rows, 'Creator')}")
        print("\nTracking:")
        print(f"  Etrack Incident: {_summary_value(summary_rows, 'Etrack Incident')}")
        print(f"  Etrack Ref: {_summary_value(summary_rows, 'Etrack Ref')}")
        print(f"  Case#: {_summary_value(summary_rows, 'Case#')}")
        print(f"  Customer: {_summary_value(summary_rows, 'Customer')}")
        print(f"  Component: {_summary_value(summary_rows, 'Component')}")
        print(f"  Slack: {_summary_value(summary_rows, 'Slack')}")
        print("\nActivity:")
        print(f"  Comments: {_summary_value(summary_rows, 'Comments')}")
        print(f"  Attachments: {_summary_value(summary_rows, 'Attachments')}")
        print(f"  Watchers: {_summary_value(summary_rows, 'Watchers')}")
        print(f"  Created: {_summary_value(summary_rows, 'Created')}")
        print(f"  Updated: {_summary_value(summary_rows, 'Updated')}")
        print(f"  Resolved: {_summary_value(summary_rows, 'Resolved')}")
        return

    print()
    print(
        f"{_summary_value(summary_rows, 'FI')} | {_summary_value(summary_rows, 'Type')} | "
        f"{_summary_value(summary_rows, 'Priority')} | {_summary_value(summary_rows, 'Status')} | "
        f"{_summary_value(summary_rows, 'Resolution')}"
    )
    print(_compact_text(_summary_value(summary_rows, "Summary"), max_len=180))
    print(
        f"Assignee: {_summary_value(summary_rows, 'Assignee')} | "
        f"Case Status: {_summary_value(summary_rows, 'Case Status')} | "
        f"Customer: {_summary_value(summary_rows, 'Customer')} | "
        f"ET: {_summary_value(summary_rows, 'Etrack Incident')} | "
        f"Case: {_summary_value(summary_rows, 'Case#')}"
    )
    print(
        f"Component: {_summary_value(summary_rows, 'Component')} | "
        f"Updated: {_summary_value(summary_rows, 'Updated')} | "
        f"Comments: {_summary_value(summary_rows, 'Comments')} | "
        f"Attachments: {_summary_value(summary_rows, 'Attachments')} | "
        f"Watchers: {_summary_value(summary_rows, 'Watchers')}"
    )


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


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
        if filtered and all(not isinstance(item, (dict, list)) for item in value):
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
    summary_rows: List[List[str]],
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
        "summary": _summary_rows_to_dict(summary_rows),
    }

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
        if etrack_ids:
            payload["etrack_details"] = []
            for etrack_id in etrack_ids:
                detail = {"Incident": etrack_id}
                if etrack_info:
                    detail.update(etrack_info.get(etrack_id, {}))
                payload["etrack_details"].append(detail)
        else:
            payload["etrack_details"] = []

    if show_comments > 0 and comments:
        latest = comments[-show_comments:]
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Get FI details from Jira.")
    parser.add_argument("fi_id", help="FI ID (e.g., FI-61974)")
    parser.add_argument(
        "--show-etrack-details",
        action="store_true",
        help="If Etrack Incident is present, fetch and show etrack summary details.",
    )
    parser.add_argument(
        "--show-comments",
        type=int,
        default=2,
        help="Number of latest comments to show (default: 2). Use 0 to disable comments.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output section with full raw Jira response JSON.",
    )
    parser.add_argument(
        "--include-empty-customfields",
        action="store_true",
        help="With --verbose, include customfield_* entries even when null/empty.",
    )
    parser.add_argument(
        "--show-field",
        action="append",
        default=[],
        help="Show specific Jira fields in compact output by field key or display name. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--format",
        choices=["compact", "grouped", "table", "minimal", "json"],
        default="compact",
        help="Summary output format: compact (default), grouped, table, minimal, or json.",
    )
    args = parser.parse_args()

    fi_id = args.fi_id.strip().upper()
    if not re.match(r"^FI-\d+$", fi_id):
        print(f"Invalid FI format: {fi_id}. Expected FI-<digits>")
        return 2

    try:
        jira = JiraClient()
        issue = jira.get_issue(fi_id)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    fields = issue.get("fields", {})
    comments = (fields.get("comment") or {}).get("comments", [])
    attachments = fields.get("attachment", [])
    watchers = (fields.get("watches") or {}).get("watchCount", "-")
    etrack_ids = _extract_etrack_ids(fields)
    requested_fields = _split_field_selectors(args.show_field)
    summary_rows = _build_summary_rows(issue.get("key", fi_id), fields, comments, attachments, watchers, etrack_ids)
    status_context = _extract_current_status_and_next_steps(fields, comments)
    linked_fis = _extract_linked_fis(issue)
    linked_status: Optional[Dict[str, Dict[str, str]]] = None
    etrack_info: Optional[Dict[str, Dict[str, str]]] = None
    selected_field_rows: List[List[str]] = []

    if linked_fis:
        try:
            linked_status = jira.get_issue_status_batch(linked_fis)
        except RuntimeError as exc:
            if args.format == "json":
                linked_status = {fi_key: {"error": str(exc)} for fi_key in linked_fis}
            else:
                print(f"\nLinked FIs:")
                print(f"  Unable to fetch linked FI statuses: {exc}")

    if args.show_etrack_details and etrack_ids:
        etrack_info = _fetch_etrack_details(etrack_ids)

    if requested_fields:
        selected_field_rows = _get_selected_field_rows(issue, requested_fields)

    if args.format == "json":
        json_payload = _build_json_output(
            summary_rows,
            status_context,
            linked_fis,
            linked_status,
            args.show_etrack_details,
            etrack_ids,
            etrack_info,
            args.show_comments,
            comments,
            requested_fields,
            selected_field_rows,
        )
        print(json.dumps(json_payload, indent=2, ensure_ascii=False))
        return 0

    _print_summary(summary_rows, args.format)

    if status_context:
        print("\nCurrent Status / Next Steps:")
        if "current_status" in status_context:
            print("  Current Status:")
            print(_format_multiline_text(status_context["current_status"], max_len=450))
        if "next_steps" in status_context:
            if "current_status" in status_context:
                print()
            print("  Next Steps:")
            print(_format_multiline_text(status_context["next_steps"], max_len=450))

    if linked_fis:
        print("\nLinked FIs:")
        try:
            rows = []
            for lk in linked_fis:
                data = (linked_status or {}).get(lk, {})
                rows.append([
                    lk,
                    data.get("status", "-"),
                    data.get("resolution", "-"),
                    data.get("assignee", "-"),
                    data.get("updated", "-"),
                ])
            _print_table(rows, ["FI", "Status", "Resolution", "Assignee", "Updated"])
        except RuntimeError as exc:
            print(f"  Unable to fetch linked FI statuses: {exc}")
    else:
        print("\nLinked FIs: None")

    # Optional Etrack details
    if args.show_etrack_details:
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
                    info.get("assignee", "-"),
                    info.get("abstract", "-"),
                ])
            _print_table(rows, ["Incident", "State", "Assignee", "Abstract"])

    # Latest comments
    if args.show_comments > 0 and comments:
        print(f"\nLatest {min(args.show_comments, len(comments))} comment(s):")
        latest = comments[-args.show_comments:]
        for idx, comment in enumerate(latest, 1):
            author = (comment.get("author") or {}).get("displayName", "-")
            created = _normalize_timestamp(comment.get("created"))
            print(f"  {idx}. {author} @ {created}")
            print(_format_multiline_text(comment.get("body"), max_len=450, width=110, indent="     "))
            if idx < len(latest):
                print()

    if requested_fields:
        print("\nSelected Fields:")
        _print_table(_compact_selected_field_rows(selected_field_rows), ["Requested", "Field", "Value"])

    if args.verbose:
        print("\nVerbose Output:")
        verbose_issue = _filtered_issue_for_verbose(issue, args.include_empty_customfields)
        verbose_issue = _replace_customfield_keys_with_names(verbose_issue)
        verbose_issue = _prune_verbose_noise(verbose_issue)
        print(json.dumps(verbose_issue, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
