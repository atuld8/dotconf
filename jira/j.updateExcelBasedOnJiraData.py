#!/usr/bin/env python3

import argparse
import os
import sys
import openpyxl
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jira_api import load_config, get, search_all_or_fail


def get_jira_issues(jira_ids, token):
    """Fetch Jira issues by their IDs.

    Args:
        jira_ids (str): Comma-separated string of Jira issue IDs.
        token (str): Jira API token.

    Returns:
        dict: A dictionary mapping Jira issue IDs to their details.
    """
    if not jira_ids:
        return {}
    result = {}
    batch_size = 50
    for i in range(0, len(jira_ids), batch_size):
        batch = jira_ids[i:i + batch_size]
        jql = "key in ({})".format(",".join(batch))
        try:
            issues = search_all_or_fail(
                jql, page_size=100, fields="*all", expand="",
                context=f"Jira key batch {i // batch_size + 1}", on_empty="return",
            )
        except RuntimeError as exc:
            print(f"Failed to fetch Jira issues (batch starting at {batch[0]}): {exc}",
                  file=sys.stderr)
            sys.exit(1)
        for issue in issues:
            result[issue["key"]] = issue
    return result


def get_jira_resource(jira_url, token, cache):
    """ Fetch a Jira resource by its URL. """
    if jira_url in cache:
        return cache[jira_url]
    try:
        response = get(jira_url, timeout=10)
        data = response.json() if response.ok else None
    except Exception:
        data = None
    cache[jira_url] = data
    return data


def get_jira_fields(token):
    """ Fetch Jira fields.  """
    response = get("rest/api/2/field", timeout=10)
    return response.json() if response.ok else None


def build_field_id_map(token):
    """ Build a mapping of Jira field names to their IDs. """
    fields = get_jira_fields(token)
    return {field.get("name"): field.get("id", "") for field in fields} if fields else {}


def get_field_value(fields_json, field_id):
    """ Get the value of a specific field from the fields JSON. """
    if not fields_json or field_id not in fields_json:
        return ""
    return fields_json[field_id]


def prompt_for_token():
    """ Prompt for Jira API token. """
    # Credentials/URL/SSL come from jira_api.load_config(); token kept for call compatibility
    return load_config().token


def clean_value(value):
    """
    Cleans a given value by removing newline characters and leading/trailing whitespace.

    Args:
        value: The input value to clean. Can be any type.

    Returns:
        str: The cleaned string representation of the input value. Returns an empty string if the input is falsy.
    """ 
    if not value:
        return ""
    return str(value).replace('\n', '').strip()


def update_excel_with_jira(excel_path, sheet_name, token, dry_run):
    """
    Updates an Excel workbook with data fetched from Jira issues.

    This function reads the specified Excel file and sheet, extracts Jira issue IDs from the sheet,
    fetches corresponding issue data from Jira using the provided token, and updates the sheet with
    relevant field values. Only rows with valid Jira IDs (format: 'ROSTER-<number>') are processed.
    The function supports updating columns C to T (Excel columns 3 to 20) based on header names in row 2.

    Args:
        excel_path (str): Path to the Excel workbook (.xlsx) to update.
        sheet_name (str): Name of the worksheet to update.
        token (str): Authentication token for accessing the Jira API.

    Returns:
        None

    Side Effects:
        - Modifies and saves the specified Excel file with updated Jira data.
        - Prints status and error messages to the console.
    """

    if not os.path.isfile(excel_path):
        print(f"File '{excel_path}' does not exist.")
        return

    if not excel_path.lower().endswith(".xlsx"):
        print("Only Excel Workbook (xlsx) format file is supported.")
        return

    wb = openpyxl.load_workbook(excel_path)
    print("Available sheets:", wb.sheetnames)
    if sheet_name not in wb.sheetnames:
        print(f"Sheet '{sheet_name}' not found. Please choose from: {wb.sheetnames}")
        return

    # Create a backup copy of the sheet before updating
    backup_time = datetime.now().strftime("%d-%b-%y.%H-%M")
    backup_sheet = wb.copy_worksheet(wb[sheet_name])
    backup_sheet.title = f"{sheet_name}_{backup_time}"
    wb.save(excel_path)
    print(f"Backup worksheet '{backup_sheet.title}' created inside workbook '{excel_path}'.")

    ws = wb[sheet_name]

    field_id_map = build_field_id_map(token)
    nested_cache = {}

    # Collect all Jira IDs to batch fetch
    jira_ids = []
    row_map = {}
    # Collect Jira IDs for batch fetching (no per-row print)
    for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
        jira_id = clean_value(row[1].value)
        if jira_id and str(jira_id).startswith("ROSTER-") and str(jira_id)[7:].isdigit():
            jira_ids.append(jira_id)
            row_map[jira_id] = row

    # Batch fetch issues
    issues = get_jira_issues(jira_ids, token)

    # Gather all nested URLs to fetch in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed
    nested_urls = set()
    for jira_id, row in row_map.items():
        issue = issues.get(jira_id)
        if issue:
            for col_idx in range(2, 20):
                header_name = ws.cell(row=2, column=col_idx+1).value
                field_id = field_id_map.get(header_name, "")
                field_value = get_field_value(issue.get("fields", {}), field_id)
                if isinstance(field_value, dict) and "self" in field_value:
                    nested_urls.add(field_value["self"])

    # Fetch all nested resources in parallel (cache avoids duplicate calls)
    def fetch_nested(url):
        return url, get_jira_resource(url, token, nested_cache)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_nested, url): url for url in nested_urls}
        for future in as_completed(futures):
            url, _ = future.result()
            pass  # cache is updated in get_jira_resource

    # Now update Excel
    for jira_id, row in row_map.items():
        issue = issues.get(jira_id)
        if issue:
            for col_idx in range(2, 20):  # C to T
                header_name = ws.cell(row=2, column=col_idx+1).value
                field_id = field_id_map.get(header_name, "")
                field_value = get_field_value(issue.get("fields", {}), field_id)
                if isinstance(field_value, dict) and "self" in field_value:
                    nested = nested_cache.get(field_value["self"]) or {}
                    field_value = (
                        nested.get("name") or
                        nested.get("displayName") or
                        nested.get("value") or ""
                    )
                if not dry_run:
                    cell = ws.cell(row=row[0].row, column=col_idx+1)
                    # If value is a long number, set format to scientific
                    if (isinstance(field_value, int) or isinstance(field_value, float)) and len(str(field_value)) >= 10:
                        cell.value = field_value
                        cell.number_format = '0.00E+00'
                    else:
                        cell.value = field_value
                # Only print summary if dry_run
        # Only print summary if dry_run
        elif dry_run:
            print(f"Could not retrieve data for Jira ID: {jira_id}")

    if not dry_run:
        wb.save(excel_path)
        print(f"\n\n{excel_path} Excel file updated successfully.")
    else:
        print(f"Dry run: No changes made to {excel_path}.")

def main():
    """ Update an Excel sheet with data from Jira. """
    parser = argparse.ArgumentParser(
        description="Update an Excel sheet with data from Jira based on Jira IDs in the sheet."
    )
    parser.add_argument("-f", "--file", required=True, help="Path to Excel file")
    parser.add_argument("-s", "--sheet", required=True, help="Sheet name to update")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Print data only, do not create Jira issues")
    args = parser.parse_args()
    print(f"[CMD] {' '.join(sys.argv)}", file=sys.stderr)

    token = prompt_for_token()
    update_excel_with_jira(args.file, args.sheet, token, args.dry_run)


if __name__ == "__main__":
    main()
