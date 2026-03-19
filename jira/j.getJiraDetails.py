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
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def _format_multiline_text(value: Any, max_len: int = 450, width: int = 110, indent: str = "    ") -> str:
    compact = _compact_text(value, max_len=max_len)
    if compact == "-":
        return "-"
    return textwrap.fill(compact, width=width, initial_indent=indent, subsequent_indent=indent)


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


def _get_default_optional_fields(issue: Dict[str, Any]) -> List[List[str]]:
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        return []

    candidates = [
        ("Solution", _field_value_by_name(issue, "Solution")),
        ("Progress Status", _field_value_by_name(issue, "Progress Status")),
        ("Severity", fields.get("severity", _field_value_by_name(issue, "Severity"))),
        ("Epic Link", _field_value_by_name(issue, "Epic Link")),
        ("Sprint", _field_value_by_name(issue, "Sprint")),
        ("Watchers", fields.get("watches") or _field_value_by_name(issue, "Watchers")),
        ("Watcher Groups", _field_value_by_name(issue, "Watcher Groups")),
    ]

    rows: List[List[str]] = []
    for label, value in candidates:
        if _has_display_value(value):
            if label == "Watchers":
                rows.append([label, _format_watchers_value(value)])
            elif label == "Sprint":
                rows.append([label, _format_sprint_value(value)])
            else:
                rows.append([label, _format_selected_field_value(value)])
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


def _print_summary(summary_rows: List[List[str]], output_format: str):
    if output_format == "json":
        print(json.dumps(_summary_rows_to_dict(summary_rows), indent=2, ensure_ascii=False))
        return

    if output_format == "minimal":
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
        optional_labels = ["Solution", "Progress Status", "Severity", "Epic Link", "Sprint", "Watchers", "Watcher Groups"]
        optional_present = [label for label in optional_labels if _summary_value(summary_rows, label) != "-"]
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

    print()
    print(
        f"Issue: {_summary_value(summary_rows, 'Issue')} | "
        f"Project: {_summary_value(summary_rows, 'Project')} | "
        f"Type: {_summary_value(summary_rows, 'Type')} | "
        f"Priority: {_summary_value(summary_rows, 'Priority')} | "
        f"Status: {_summary_value(summary_rows, 'Status')} | "
        f"Resolution: {_summary_value(summary_rows, 'Resolution')}"
    )
    print(f"Summary: {_compact_text(_summary_value(summary_rows, 'Summary'), max_len=180)}")
    print(
        f"Assignee: {_summary_value(summary_rows, 'Assignee')} | "
        f"Reporter: {_summary_value(summary_rows, 'Reporter')} | "
        f"Components: {_summary_value(summary_rows, 'Components')} | "
        f"Labels: {_summary_value(summary_rows, 'Labels')}"
    )
    optional_labels = ["Solution", "Progress Status", "Severity", "Epic Link", "Sprint", "Watchers", "Watcher Groups"]
    optional_parts = [
        f"{label}: {_compact_text(_summary_value(summary_rows, label), max_len=80)}"
        for label in optional_labels
        if _summary_value(summary_rows, label) != "-"
    ]
    if optional_parts:
        print(" | ".join(optional_parts))
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
    summary_rows: List[List[str]],
    show_comments: int,
    comments: List[Dict[str, Any]],
    requested_fields: List[str],
    selected_field_rows: List[List[str]],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "summary": _summary_rows_to_dict(summary_rows),
    }

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Get generic Jira issue details.")
    parser.add_argument("issue_key", help="Issue key (for example, PROJ-12345)")
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
        help="With --verbose, include customfield_* entries even when null or empty.",
    )
    parser.add_argument(
        "--show-field",
        action="append",
        default=[],
        help="Show specific Jira fields by field key or display name. Can be repeated or comma-separated.",
    )
    parser.add_argument(
        "--format",
        choices=["compact", "grouped", "table", "minimal", "json"],
        default="compact",
        help="Summary output format: compact (default), grouped, table, minimal, or json.",
    )
    args = parser.parse_args()

    issue_key = args.issue_key.strip().upper()
    if not re.match(r"^[A-Z][A-Z0-9_]*-\d+$", issue_key):
        print(f"Invalid Jira issue key format: {issue_key}. Expected PROJECT-<digits>")
        return 2

    try:
        jira = JiraClient()
        issue = jira.get_issue(issue_key)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    fields = issue.get("fields", {})
    comments = (fields.get("comment") or {}).get("comments", [])
    attachments = fields.get("attachment", [])
    watchers = (fields.get("watches") or {}).get("watchCount", "-")
    requested_fields = _split_field_selectors(args.show_field)
    default_optional_rows = _get_default_optional_fields(issue)
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
            summary_rows,
            args.show_comments,
            comments,
            requested_fields,
            selected_field_rows,
        )
        print(json.dumps(json_payload, indent=2, ensure_ascii=False))
        return 0

    _print_summary(summary_rows, args.format)

    if args.show_comments > 0 and comments:
        print(f"\nLatest {min(args.show_comments, len(comments))} comment(s):")
        latest = comments[-args.show_comments:]
        for index, comment in enumerate(latest, 1):
            author = (comment.get("author") or {}).get("displayName", "-")
            created = _normalize_timestamp(comment.get("created"))
            print(f"  {index}. {author} @ {created}")
            print(_format_multiline_text(comment.get("body"), max_len=450, width=110, indent="     "))
            if index < len(latest):
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