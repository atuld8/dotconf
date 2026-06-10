#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch validate FI issues against linked etrack and sync mismatched fields.

Features:
- Read FI IDs from file or stdin (extracts FI-XXXXX pattern from any text)
- Fetch FI details with etrack comparison using j.getJiraDetails.py -e -j
- Detect mismatches in Component and Affects Version
- Auto-sync mismatched fields using j.updateJiraDetails.py -set
- Handle edge cases: no etrack, multiple conflicting etracks, fetch/update errors
- Generate categorized success/failure reports (JSON + text)
- Mapping-only mode: apply value translations without etrack comparison

Note: Report outputs use semicolon (;) as separator for multi-value fields
      for Excel compatibility.

Usage:
  # From file
  j.validateAndSyncFIs.py ~/op/dump.validate.fi

  # From stdin
  echo "FI-12345 FI-12346" | j.validateAndSyncFIs.py -

  # Dry run (preview without changes)
  j.validateAndSyncFIs.py ~/op/dump.validate.fi -n

  # Sync only component or version
  j.validateAndSyncFIs.py ~/op/dump.validate.fi -sc   # component only
  j.validateAndSyncFIs.py ~/op/dump.validate.fi -sv   # version only

  # With value mappings (translate etrack values before applying)
  j.validateAndSyncFIs.py ~/op/dump.validate.fi -mf mappings.json

  # Mapping-only mode (apply mappings to FI values directly, no etrack)
  j.validateAndSyncFIs.py ~/op/dump.validate.fi -mf mappings.json -mo -n -v

  # Parallel processing for large batches (4x faster)
  j.validateAndSyncFIs.py ~/op/dump.validate.fi -p -w 8 -n -v

Short Options:
  -n   --dry-run          Preview without changes
  -v   --verbose          Print progress for each FI
  -d   --delay            Delay between API calls (default: 0.5s)
  -o   --output-dir       Report output directory (default: ~/op)
  -nr  --no-report        Skip report generation
  -sc  --sync-component   Sync only component
  -sv  --sync-version     Sync only version
  -mf  --mapping-file     Value mapping JSON file (uses fi_mapping section)
  -mo  --mapping-only     Apply fi_mapping without etrack comparison
  -p   --parallel         Enable parallel processing
  -w   --workers          Number of parallel workers (default: 4)

Mapping File Format (JSON):
  {
    "fi_mapping": {
      "component": {
        "CurrentFIValue": "NewValue",
        "old-comp": "NEW_COMP"
      },
      "version": {
        "6.1": "11.1",
        "6.2": "11.2"
      }
    },
    "etrack_mapping": {
      "component": {
        "EtrackValue": "TargetJiraValue"
      },
      "version": {
        "EtrackVer": "JiraVer"
      }
    }
  }

  Sections:
    fi_mapping     - Used by -mo mode: map current FI values to new values
    etrack_mapping - Used by j.updateJiraDetails.py -set -mf: map etrack values before setting
"""

from __future__ import print_function

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure console output is UTF-8 safe
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Path to jira scripts (same directory as this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GET_DETAILS_SCRIPT = os.path.join(SCRIPT_DIR, 'j.getJiraDetails.py')
UPDATE_SCRIPT = os.path.join(SCRIPT_DIR, 'j.updateJiraDetails.py')

# Global mappings (loaded from file)
VALUE_MAPPINGS: Dict[str, Dict[str, str]] = {
    "component": {},
    "version": {},
}


# ---------------------------------------------------------------------------
# Result Categories
# ---------------------------------------------------------------------------

class ResultCategory:
    SUCCESS = 'success'                    # Updated FI successfully
    SKIP_NO_MISMATCH = 'skip_no_mismatch'  # FI matches etrack, no update needed
    FAIL_NO_ETRACK = 'fail_no_etrack'      # No etrack linked to FI
    FAIL_MULTI_ETRACK = 'fail_multi_etrack'  # Multiple etracks with conflicting values
    FAIL_FETCH = 'fail_fetch'              # Error fetching FI or etrack details
    FAIL_UPDATE = 'fail_update'            # Update command failed


# ---------------------------------------------------------------------------
# FI Extraction
# ---------------------------------------------------------------------------

def load_mappings(filepath: str, section: str = 'fi_mapping') -> Dict[str, Dict[str, str]]:
    """Load value mappings from a JSON file.

    Args:
        filepath: Path to JSON mapping file
        section: Which section to load ('fi_mapping' or 'etrack_mapping')

    Returns:
        Dict with 'component' and 'version' mappings

    File format:
    {
        "fi_mapping": {
            "component": {"CurrentFIValue": "NewValue"},
            "version": {"6.1": "11.1"}
        },
        "etrack_mapping": {
            "component": {"EtrackValue": "TargetJiraValue"},
            "version": {"EtrackVer": "JiraVer"}
        }
    }
    """
    mappings: Dict[str, Dict[str, str]] = {"component": {}, "version": {}}

    if not filepath:
        return mappings

    expanded_path = os.path.expanduser(filepath)
    if not os.path.isfile(expanded_path):
        print(f"Warning: Mapping file not found: {expanded_path}", file=sys.stderr)
        return mappings

    try:
        with open(expanded_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Get the appropriate section
        section_data = data.get(section, {})
        if not section_data:
            print(f"Warning: Section '{section}' not found in mapping file", file=sys.stderr)
            return mappings

        # Normalize keys to lowercase for case-insensitive matching
        if "component" in section_data:
            mappings["component"] = {
                k.lower(): v for k, v in section_data["component"].items()
            }
        if "version" in section_data:
            mappings["version"] = {
                k.lower(): v for k, v in section_data["version"].items()
            }

        return mappings

    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in mapping file: {e}", file=sys.stderr)
        return mappings
    except Exception as e:
        print(f"Warning: Error loading mapping file: {e}", file=sys.stderr)
        return mappings


def apply_mapping(value: str, mapping_type: str, mappings: Dict[str, Dict[str, str]]) -> Tuple[str, bool]:
    """Apply value mapping if available.

    Args:
        value: Original value
        mapping_type: 'component' or 'version'
        mappings: Loaded mappings dict

    Returns:
        Tuple of (mapped_value, was_mapped)
    """
    if not value or value == "-":
        return value, False

    type_mappings = mappings.get(mapping_type, {})
    if not type_mappings:
        return value, False

    # Try exact match (case-insensitive)
    normalized = value.lower().strip()
    if normalized in type_mappings:
        return type_mappings[normalized], True

    return value, False


def extract_fi_ids(text: str) -> List[str]:
    """Extract unique FI IDs from any text input.

    Args:
        text: Any text containing FI-XXXXX patterns

    Returns:
        List of unique FI IDs in order of first appearance
    """
    pattern = re.compile(r'\bFI-\d+\b', re.IGNORECASE)
    matches = pattern.findall(text)
    # Normalize to uppercase and deduplicate while preserving order
    seen: Set[str] = set()
    result: List[str] = []
    for fi in matches:
        fi_upper = fi.upper()
        if fi_upper not in seen:
            seen.add(fi_upper)
            result.append(fi_upper)
    return result


def read_fi_ids_from_file(filepath: str) -> List[str]:
    """Read FI IDs from a file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return extract_fi_ids(content)


def read_fi_ids_from_stdin() -> List[str]:
    """Read FI IDs from stdin."""
    content = sys.stdin.read()
    return extract_fi_ids(content)


# ---------------------------------------------------------------------------
# FI Details Fetching
# ---------------------------------------------------------------------------

def fetch_fi_details(fi_id: str, timeout: int = 60, with_etrack: bool = True) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch FI details using j.getJiraDetails.py --format json.

    Args:
        fi_id: The FI issue key (e.g., FI-12345)
        timeout: Command timeout in seconds
        with_etrack: Include etrack comparison (-e flag)

    Returns:
        Tuple of (details_dict, error_message)
        - On success: (dict, None)
        - On failure: (None, error_string)
    """
    cmd = ['python3', GET_DETAILS_SCRIPT, fi_id, '--format', 'json']
    if with_etrack:
        cmd.insert(3, '-e')  # Insert after fi_id

    try:
        # Use shell to inherit environment (for JIRA_SERVER_NAME, JIRA_ACC_TOKEN)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=SCRIPT_DIR,
            env=os.environ.copy()  # Inherit current environment
        )

        # Check for errors in stderr (ignore warnings)
        stderr = result.stderr.strip() if result.stderr else ""
        # Filter out common warnings that don't indicate failure
        error_lines = [
            line for line in stderr.split('\n')
            if line and not any(skip in line for skip in [
                'NotOpenSSLWarning', 'urllib3', 'warnings.warn'
            ])
        ]

        if result.returncode != 0:
            error_msg = '\n'.join(error_lines) if error_lines else f"Exit code {result.returncode}"
            return None, error_msg

        # Parse JSON output
        stdout = result.stdout.strip()
        if not stdout:
            return None, "Empty response"

        try:
            data = json.loads(stdout)
            return data, None
        except json.JSONDecodeError as e:
            # Try to extract JSON from mixed output (stdout might have extra text)
            json_match = re.search(r'\{[\s\S]*\}', stdout)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return data, None
                except json.JSONDecodeError:
                    pass
            return None, f"JSON parse error: {e}"

    except subprocess.TimeoutExpired:
        return None, f"Timeout after {timeout}s"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Mismatch Analysis
# ---------------------------------------------------------------------------

def analyze_etrack_mismatches(
    fi_data: Dict[str, Any],
    check_component: bool = True,
    check_version: bool = True,
) -> Dict[str, Any]:
    """Analyze etrack mismatches from FI details.

    Args:
        fi_data: JSON output from j.getJiraDetails.py -e --format json
        check_component: Whether to check component mismatches
        check_version: Whether to check version mismatches

    Returns:
        Dict with analysis results:
        {
            "has_etrack": bool,
            "etrack_ids": list,
            "has_conflict": bool,  # Multiple etracks with different values
            "conflict_details": str,  # Description of conflict
            "mismatches": [  # List of mismatches to fix
                {"field": "Component", "fi_value": "X", "etrack_value": "Y", "etrack_id": "123"},
                ...
            ],
            "all_match": bool,  # True if no mismatches
        }
    """
    result = {
        "has_etrack": False,
        "etrack_ids": [],
        "has_conflict": False,
        "conflict_details": "",
        "mismatches": [],
        "all_match": True,
    }

    # Get etrack IDs from etrack_details array
    etrack_details = fi_data.get("etrack_details", [])
    etrack_ids = [str(et.get("Incident", "")) for et in etrack_details if et.get("Incident")]
    if not etrack_ids:
        return result

    result["has_etrack"] = True
    result["etrack_ids"] = etrack_ids

    # Get mismatch data (flat array of mismatches)
    # Format: [{"fi_id": ..., "etrack_id": ..., "field": ..., "fi_value": ..., "etrack_value": ...}, ...]
    etrack_mismatches = fi_data.get("etrack_fi_mismatches", [])
    if not etrack_mismatches:
        # No mismatches reported - all match
        return result

    # Collect values from each etrack for conflict detection
    component_values: Dict[str, str] = {}  # etrack_id -> component
    version_values: Dict[str, str] = {}    # etrack_id -> version

    for mismatch in etrack_mismatches:
        et_id = str(mismatch.get("etrack_id", ""))
        field = mismatch.get("field", "")
        etrack_value = mismatch.get("etrack_value", "-")

        if field == "Component":
            component_values[et_id] = etrack_value
        elif field == "Version":
            version_values[et_id] = etrack_value

    # Check for conflicts between etracks (only if multiple etracks)
    conflicts = []
    if len(etrack_ids) > 1:
        unique_components = set(v for v in component_values.values() if v and v != "-")
        unique_versions = set(v for v in version_values.values() if v and v != "-")

        if check_component and len(unique_components) > 1:
            conflicts.append(f"Component: {unique_components}")
        if check_version and len(unique_versions) > 1:
            conflicts.append(f"Version: {unique_versions}")

    if conflicts:
        result["has_conflict"] = True
        result["conflict_details"] = "; ".join(conflicts)
        return result

    # No conflicts - collect mismatches to fix (use first etrack as source)
    first_etrack_id = etrack_ids[0]

    for mismatch in etrack_mismatches:
        et_id = str(mismatch.get("etrack_id", ""))
        if et_id != first_etrack_id:
            continue  # Only use first etrack for updates

        field = mismatch.get("field", "")
        if field == "Component" and check_component:
            result["mismatches"].append({
                "field": "Component",
                "fi_value": mismatch.get("fi_value", "-"),
                "etrack_value": mismatch.get("etrack_value", "-"),
                "etrack_id": et_id,
            })
            result["all_match"] = False
        elif field == "Version" and check_version:
            result["mismatches"].append({
                "field": "Version",
                "fi_value": mismatch.get("fi_value", "-"),
                "etrack_value": mismatch.get("etrack_value", "-"),
                "etrack_id": et_id,
            })
            result["all_match"] = False

    return result


def extract_fi_values(fi_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extract current component and version from FI data.

    Args:
        fi_data: JSON output from j.getJiraDetails.py --format json

    Returns:
        Dict with 'component' and 'version' keys
    """
    summary = fi_data.get("summary", {})
    return {
        "component": summary.get("Components", "-"),
        "version": summary.get("Affects Versions") or summary.get("Affects Version/s", "-"),
    }


def analyze_mapping_updates(
    fi_data: Dict[str, Any],
    mappings: Dict[str, Dict[str, str]],
    check_component: bool = True,
    check_version: bool = True,
) -> Dict[str, Any]:
    """Analyze what FI values need to be updated via mapping.

    Args:
        fi_data: JSON output from j.getJiraDetails.py --format json
        mappings: Value mappings dict
        check_component: Whether to check component
        check_version: Whether to check version

    Returns:
        Dict with analysis results:
        {
            "fi_component": str,
            "fi_version": str,
            "updates": [
                {"field": "Component", "old_value": "X", "new_value": "Y"},
                ...
            ],
            "has_updates": bool,
        }
    """
    fi_values = extract_fi_values(fi_data)
    result = {
        "fi_component": fi_values["component"],
        "fi_version": fi_values["version"],
        "updates": [],
        "has_updates": False,
    }

    # Check component mapping
    if check_component and fi_values["component"] and fi_values["component"] != "-":
        mapped_comp, was_mapped = apply_mapping(fi_values["component"], "component", mappings)
        if was_mapped:
            result["updates"].append({
                "field": "Component",
                "old_value": fi_values["component"],
                "new_value": mapped_comp,
            })
            result["has_updates"] = True

    # Check version mapping
    if check_version and fi_values["version"] and fi_values["version"] != "-":
        mapped_ver, was_mapped = apply_mapping(fi_values["version"], "version", mappings)
        if was_mapped:
            result["updates"].append({
                "field": "Version",
                "old_value": fi_values["version"],
                "new_value": mapped_ver,
            })
            result["has_updates"] = True

    return result


# ---------------------------------------------------------------------------
# Update Execution
# ---------------------------------------------------------------------------

def sync_fi_with_etrack(
    fi_id: str,
    etrack_id: str,
    sync_component: bool = True,
    sync_version: bool = True,
    dry_run: bool = False,
    timeout: int = 60,
    component_value: Optional[str] = None,
    version_value: Optional[str] = None,
) -> Tuple[bool, str]:
    """Sync FI fields from etrack using j.updateJiraDetails.py.

    Args:
        fi_id: The FI issue key
        etrack_id: The etrack ID to sync from
        sync_component: Sync component field
        sync_version: Sync affects version field
        dry_run: Preview changes without applying
        timeout: Command timeout in seconds
        component_value: Optional direct component value (overrides etrack sync)
        version_value: Optional direct version value (overrides etrack sync)

    Returns:
        Tuple of (success, message)
    """
    # If we have direct values (from mapping), use direct update instead of etrack sync
    use_direct_update = (component_value is not None or version_value is not None)

    if use_direct_update:
        cmd = ['python3', UPDATE_SCRIPT, fi_id]
        if sync_component and component_value:
            cmd.extend(['-c', component_value])
        if sync_version and version_value:
            cmd.extend(['--av', version_value])
    else:
        # Use etrack sync mode
        cmd = ['python3', UPDATE_SCRIPT, fi_id, '-set', etrack_id]
        if sync_component:
            cmd.append('-sc')
        if sync_version:
            cmd.append('-sav')

    if dry_run:
        cmd.append('--dry-run')

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=SCRIPT_DIR,
            env=os.environ.copy()
        )

        output = result.stdout.strip()
        if result.stderr:
            output += "\n" + result.stderr.strip()

        if result.returncode == 0:
            return True, output
        else:
            return False, output

    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

# Thread-safe print lock for verbose output
_print_lock = threading.Lock()


def _process_single_fi(
    fi_id: str,
    sync_component: bool,
    sync_version: bool,
    dry_run: bool,
    mappings: Dict[str, Dict[str, str]],
    mapping_only: bool,
) -> Tuple[str, Dict[str, Any]]:
    """Process a single FI and return (category, entry).

    Args:
        fi_id: FI issue key
        sync_component: Sync component field
        sync_version: Sync version field
        dry_run: Preview mode
        mappings: Value mappings
        mapping_only: Apply mappings without etrack

    Returns:
        Tuple of (ResultCategory, entry_dict)
    """
    entry: Dict[str, Any] = {"fi_id": fi_id}

    # Step 1: Fetch FI details
    fi_data, fetch_error = fetch_fi_details(fi_id, with_etrack=not mapping_only)

    if fetch_error:
        entry["error"] = fetch_error
        return ResultCategory.FAIL_FETCH, entry

    # MAPPING-ONLY MODE
    if mapping_only:
        analysis = analyze_mapping_updates(
            fi_data, mappings,
            check_component=sync_component,
            check_version=sync_version,
        )

        if not analysis["has_updates"]:
            entry["status"] = "No mapping applies"
            entry["fi_component"] = analysis["fi_component"]
            entry["fi_version"] = analysis["fi_version"]
            return ResultCategory.SKIP_NO_MISMATCH, entry

        comp_update = next((u for u in analysis["updates"] if u["field"] == "Component"), None)
        ver_update = next((u for u in analysis["updates"] if u["field"] == "Version"), None)
        new_comp = comp_update["new_value"] if comp_update else None
        new_ver = ver_update["new_value"] if ver_update else None

        success, message = sync_fi_with_etrack(
            fi_id=fi_id, etrack_id="N/A",
            sync_component=comp_update is not None,
            sync_version=ver_update is not None,
            dry_run=dry_run, timeout=60,
            component_value=new_comp, version_value=new_ver,
        )

        entry["updates"] = analysis["updates"]
        entry["sync_message"] = message
        entry["final_component"] = new_comp
        entry["final_version"] = new_ver

        if success:
            entry["status"] = "Updated" if not dry_run else "Would update"
            return ResultCategory.SUCCESS, entry
        else:
            entry["error"] = message
            return ResultCategory.FAIL_UPDATE, entry

    # ETRACK MODE
    analysis = analyze_etrack_mismatches(
        fi_data,
        check_component=sync_component,
        check_version=sync_version,
    )
    entry["etrack_ids"] = analysis["etrack_ids"]

    if not analysis["has_etrack"]:
        entry["error"] = "No Etrack Incident linked"
        return ResultCategory.FAIL_NO_ETRACK, entry

    if analysis["has_conflict"]:
        entry["error"] = f"Conflicting etrack values: {analysis['conflict_details']}"
        return ResultCategory.FAIL_MULTI_ETRACK, entry

    if analysis["all_match"]:
        entry["status"] = "All fields match"
        return ResultCategory.SKIP_NO_MISMATCH, entry

    # Sync mismatched fields
    mismatches = analysis["mismatches"]
    entry["mismatches"] = mismatches

    has_comp_mismatch = has_ver_mismatch = False
    fi_comp_value = fi_ver_value = None
    etrack_comp_value = etrack_ver_value = None
    final_comp_value = final_ver_value = None
    comp_mapped = ver_mapped = False

    for m in mismatches:
        if m["field"] == "Component":
            has_comp_mismatch = True
            fi_comp_value = m["fi_value"]
            etrack_comp_value = m["etrack_value"]
            final_comp_value, comp_mapped = apply_mapping(etrack_comp_value, "component", mappings)
        elif m["field"] == "Version":
            has_ver_mismatch = True
            fi_ver_value = m["fi_value"]
            etrack_ver_value = m["etrack_value"]
            final_ver_value, ver_mapped = apply_mapping(etrack_ver_value, "version", mappings)

    etrack_id = mismatches[0]["etrack_id"]
    use_mapped_values = comp_mapped or ver_mapped

    success, message = sync_fi_with_etrack(
        fi_id=fi_id, etrack_id=etrack_id,
        sync_component=has_comp_mismatch, sync_version=has_ver_mismatch,
        dry_run=dry_run, timeout=60,
        component_value=final_comp_value if use_mapped_values else None,
        version_value=final_ver_value if use_mapped_values else None,
    )

    entry["sync_etrack_id"] = etrack_id
    entry["sync_message"] = message
    entry["final_component"] = final_comp_value
    entry["final_version"] = final_ver_value
    entry["component_mapped"] = comp_mapped
    entry["version_mapped"] = ver_mapped
    # Store for verbose output
    entry["_verbose_data"] = {
        "has_comp": has_comp_mismatch, "has_ver": has_ver_mismatch,
        "fi_comp": fi_comp_value, "fi_ver": fi_ver_value,
        "et_comp": etrack_comp_value, "et_ver": etrack_ver_value,
        "final_comp": final_comp_value, "final_ver": final_ver_value,
        "comp_mapped": comp_mapped, "ver_mapped": ver_mapped,
        "etrack_id": etrack_id,
    }

    if success:
        entry["status"] = "Updated" if not dry_run else "Would update"
        return ResultCategory.SUCCESS, entry
    else:
        entry["error"] = message
        return ResultCategory.FAIL_UPDATE, entry


def _format_verbose_result(category: str, entry: Dict[str, Any], dry_run: bool, mapping_only: bool) -> str:
    """Format verbose output for a processed FI."""
    fi_id = entry["fi_id"]

    if category == ResultCategory.FAIL_FETCH:
        return f"[FETCH ERROR] {entry.get('error', '-')}"
    elif category == ResultCategory.FAIL_NO_ETRACK:
        return "[NO ETRACK]"
    elif category == ResultCategory.FAIL_MULTI_ETRACK:
        return f"[CONFLICT] {entry.get('error', '-')}"
    elif category == ResultCategory.FAIL_UPDATE:
        return f"[UPDATE FAILED] {entry.get('error', '-')}"
    elif category == ResultCategory.SKIP_NO_MISMATCH:
        if mapping_only:
            return f"[OK - no mapping] Component={entry.get('fi_component', '-')}, Version={entry.get('fi_version', '-')}"
        return "[OK - no mismatch]"
    elif category == ResultCategory.SUCCESS:
        if mapping_only:
            action = "Would update" if dry_run else "Updated"
            parts = []
            for u in entry.get("updates", []):
                parts.append(f"{u['field']}: {u['old_value']} -> {u['new_value']}")
            return f"[{action}] {', '.join(parts)}"
        else:
            vd = entry.get("_verbose_data", {})
            action = "Would sync" if dry_run else "Synced"
            parts = []
            if vd.get("has_comp") and vd.get("final_comp"):
                if vd.get("comp_mapped"):
                    parts.append(f"Component: {vd['fi_comp']} -> {vd['final_comp']} (mapped from {vd['et_comp']})")
                else:
                    parts.append(f"Component: {vd['fi_comp']} -> {vd['final_comp']}")
            if vd.get("has_ver") and vd.get("final_ver"):
                if vd.get("ver_mapped"):
                    parts.append(f"Version: {vd['fi_ver']} -> {vd['final_ver']} (mapped from {vd['et_ver']})")
                else:
                    parts.append(f"Version: {vd['fi_ver']} -> {vd['final_ver']}")
            return f"[{action}] etrack {vd.get('etrack_id', '-')}: {', '.join(parts)}"
    return ""


def process_fi_batch(
    fi_ids: List[str],
    sync_component: bool = True,
    sync_version: bool = True,
    dry_run: bool = False,
    delay: float = 0.5,
    verbose: bool = False,
    mappings: Optional[Dict[str, Dict[str, str]]] = None,
    mapping_only: bool = False,
    parallel: bool = False,
    workers: int = 4,
) -> Dict[str, List[Dict[str, Any]]]:
    """Process a batch of FI IDs.

    Args:
        fi_ids: List of FI issue keys
        sync_component: Sync component mismatches
        sync_version: Sync version mismatches
        dry_run: Preview changes without applying
        delay: Delay between API calls in seconds (ignored in parallel mode)
        verbose: Print progress for each FI
        mappings: Optional value mappings for component/version translation
        mapping_only: Apply mappings to FI values directly without etrack comparison
        parallel: Enable parallel processing
        workers: Number of concurrent workers (default: 4)

    Returns:
        Dict with results categorized by outcome
    """
    if mappings is None:
        mappings = {"component": {}, "version": {}}

    results: Dict[str, List[Dict[str, Any]]] = {
        ResultCategory.SUCCESS: [],
        ResultCategory.SKIP_NO_MISMATCH: [],
        ResultCategory.FAIL_NO_ETRACK: [],
        ResultCategory.FAIL_MULTI_ETRACK: [],
        ResultCategory.FAIL_FETCH: [],
        ResultCategory.FAIL_UPDATE: [],
    }

    total = len(fi_ids)

    if parallel:
        # Parallel processing with ThreadPoolExecutor
        completed = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_fi = {
                executor.submit(
                    _process_single_fi,
                    fi_id, sync_component, sync_version,
                    dry_run, mappings, mapping_only
                ): fi_id
                for fi_id in fi_ids
            }

            for future in as_completed(future_to_fi):
                fi_id = future_to_fi[future]
                completed += 1
                try:
                    category, entry = future.result()
                    results[category].append(entry)
                    if verbose:
                        msg = _format_verbose_result(category, entry, dry_run, mapping_only)
                        with _print_lock:
                            print(f"[{completed}/{total}] {fi_id}... {msg}")
                except Exception as e:
                    results[ResultCategory.FAIL_FETCH].append({"fi_id": fi_id, "error": str(e)})
                    if verbose:
                        with _print_lock:
                            print(f"[{completed}/{total}] {fi_id}... [ERROR] {e}")
    else:
        # Sequential processing (original behavior)
        for idx, fi_id in enumerate(fi_ids, 1):
            if verbose:
                print(f"[{idx}/{total}] Processing {fi_id}...", end=" ", flush=True)

            category, entry = _process_single_fi(
                fi_id, sync_component, sync_version,
                dry_run, mappings, mapping_only
            )
            results[category].append(entry)

            if verbose:
                msg = _format_verbose_result(category, entry, dry_run, mapping_only)
                print(msg)

            if delay > 0:
                time.sleep(delay)

    return results


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def print_summary(results: Dict[str, List[Dict[str, Any]]], dry_run: bool = False) -> None:
    """Print summary to console."""
    total = sum(len(v) for v in results.values())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed:       {total}")
    print("-" * 60)

    action = "Would update" if dry_run else "Updated"
    print(f"  {action}:           {len(results[ResultCategory.SUCCESS])}")
    print(f"  Skipped (match):     {len(results[ResultCategory.SKIP_NO_MISMATCH])}")
    print("-" * 60)
    print(f"  No etrack:           {len(results[ResultCategory.FAIL_NO_ETRACK])}")
    print(f"  Multi-etrack conflict: {len(results[ResultCategory.FAIL_MULTI_ETRACK])}")
    print(f"  Fetch error:         {len(results[ResultCategory.FAIL_FETCH])}")
    print(f"  Update failed:       {len(results[ResultCategory.FAIL_UPDATE])}")
    print("=" * 60)


def generate_reports(
    results: Dict[str, List[Dict[str, Any]]],
    output_dir: str,
    dry_run: bool = False,
) -> Dict[str, str]:
    """Generate JSON and text reports.

    Args:
        results: Processing results by category
        output_dir: Directory to write reports
        dry_run: Whether this was a dry run

    Returns:
        Dict mapping report type to file path
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "dry_run_" if dry_run else ""

    report_files: Dict[str, str] = {}

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # JSON report (full details)
    json_file = os.path.join(output_dir, f"{prefix}validate_fi_report_{timestamp}.json")
    total = sum(len(v) for v in results.values())
    json_data = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "summary": {
            "total": total,
            "success": len(results[ResultCategory.SUCCESS]),
            "skip_no_mismatch": len(results[ResultCategory.SKIP_NO_MISMATCH]),
            "fail_no_etrack": len(results[ResultCategory.FAIL_NO_ETRACK]),
            "fail_multi_etrack": len(results[ResultCategory.FAIL_MULTI_ETRACK]),
            "fail_fetch": len(results[ResultCategory.FAIL_FETCH]),
            "fail_update": len(results[ResultCategory.FAIL_UPDATE]),
        },
        "results": results,
    }
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    report_files["json"] = json_file

    # Success report (text)
    if results[ResultCategory.SUCCESS]:
        success_file = os.path.join(output_dir, f"{prefix}success_{timestamp}.txt")
        with open(success_file, 'w', encoding='utf-8') as f:
            f.write(f"# {'DRY RUN - ' if dry_run else ''}Successfully {'Synced' if not dry_run else 'Would Sync'} FIs\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("#" + "=" * 70 + "\n\n")
            for entry in results[ResultCategory.SUCCESS]:
                fi_id = entry["fi_id"]
                etrack_id = entry.get("sync_etrack_id", "-")
                mismatches = entry.get("mismatches", [])
                changes = []
                for m in mismatches:
                    changes.append(f"{m['field']}: {m['fi_value']} -> {m['etrack_value']}")
                f.write(f"{fi_id} (etrack: {etrack_id})\n")
                for change in changes:
                    f.write(f"  {change}\n")
                f.write("\n")
        report_files["success"] = success_file

    # Failures report (text)
    failures = (
        results[ResultCategory.FAIL_NO_ETRACK] +
        results[ResultCategory.FAIL_MULTI_ETRACK] +
        results[ResultCategory.FAIL_FETCH] +
        results[ResultCategory.FAIL_UPDATE]
    )
    if failures:
        failure_file = os.path.join(output_dir, f"{prefix}failures_{timestamp}.txt")
        with open(failure_file, 'w', encoding='utf-8') as f:
            f.write(f"# {'DRY RUN - ' if dry_run else ''}Failed FIs\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("#" + "=" * 70 + "\n\n")

            # Group by category
            if results[ResultCategory.FAIL_NO_ETRACK]:
                f.write("## NO ETRACK LINKED\n")
                for entry in results[ResultCategory.FAIL_NO_ETRACK]:
                    f.write(f"  {entry['fi_id']}\n")
                f.write("\n")

            if results[ResultCategory.FAIL_MULTI_ETRACK]:
                f.write("## MULTI-ETRACK CONFLICT\n")
                for entry in results[ResultCategory.FAIL_MULTI_ETRACK]:
                    f.write(f"  {entry['fi_id']}: {entry.get('error', '-')}\n")
                f.write("\n")

            if results[ResultCategory.FAIL_FETCH]:
                f.write("## FETCH ERRORS\n")
                for entry in results[ResultCategory.FAIL_FETCH]:
                    f.write(f"  {entry['fi_id']}: {entry.get('error', '-')}\n")
                f.write("\n")

            if results[ResultCategory.FAIL_UPDATE]:
                f.write("## UPDATE FAILURES\n")
                for entry in results[ResultCategory.FAIL_UPDATE]:
                    f.write(f"  {entry['fi_id']}: {entry.get('error', '-')}\n")
                f.write("\n")

        report_files["failures"] = failure_file

    # Skip report (text) - FIs that matched
    if results[ResultCategory.SKIP_NO_MISMATCH]:
        skip_file = os.path.join(output_dir, f"{prefix}skipped_{timestamp}.txt")
        with open(skip_file, 'w', encoding='utf-8') as f:
            f.write("# Skipped FIs (no mismatch)\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("#" + "=" * 70 + "\n\n")
            for entry in results[ResultCategory.SKIP_NO_MISMATCH]:
                etrack_ids = entry.get("etrack_ids", [])
                f.write(f"{entry['fi_id']} (etracks: {'; '.join(etrack_ids)})\n")
        report_files["skipped"] = skip_file

    return report_files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch validate FI issues against linked etrack and sync mismatched fields.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="%(prog)s [-h] [-sc/--sync-component] [-sv/--sync-version] [-n/--dry-run]\n"
              "                       [-d/--delay DELAY] [-o/--output-dir DIR] [-v/--verbose]\n"
              "                       [-nr/--no-report] [-mf/--mapping-file FILE] [-mo/--mapping-only]\n"
              "                       [-p/--parallel] [-w/--workers N] [input]",
        epilog="""
Examples:
  # From file
  %(prog)s ~/op/dump.validate.fi

  # From stdin
  echo "FI-12345 FI-12346" | %(prog)s -

  # Dry run (preview changes)
  %(prog)s ~/op/dump.validate.fi --dry-run

  # Sync only component
  %(prog)s ~/op/dump.validate.fi --sync-component

  # Sync only version
  %(prog)s ~/op/dump.validate.fi --sync-version

  # With value mappings (translate component/version values)
  %(prog)s ~/op/dump.validate.fi --mapping-file mappings.json -v

  # Verbose output
  %(prog)s ~/op/dump.validate.fi -v

Mapping File Format (JSON):
  {
    "fi_mapping": {
      "component": {
        "nb-core-security-infra": "CORE_SECURITY",
        "ita-portal": "ITA_PORTAL_NEW"
      },
      "version": {
        "6.1": "11.1",
        "6.2": "11.2"
      }
    },
    "etrack_mapping": {
      "component": {
        "EtrackValue": "TargetJiraValue"
      },
      "version": {
        "EtrackVer": "JiraVer"
      }
    }
  }

  Sections:
    fi_mapping     - Used by -mo mode: map current FI values to new values
    etrack_mapping - Used by j.updateJiraDetails.py -set -mf: map etrack values
"""
    )

    parser.add_argument(
        'input',
        nargs='?',
        default='-',
        help='Input file with FI IDs, or "-" for stdin (default: stdin)'
    )

    sync_group = parser.add_argument_group('Sync Options')
    sync_group.add_argument(
        '-sc', '--sync-component',
        action='store_true',
        dest='sync_component_only',
        help='Sync only component field (not version)'
    )
    sync_group.add_argument(
        '-sv', '--sync-version',
        action='store_true',
        dest='sync_version_only',
        help='Sync only version field (not component)'
    )

    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        help='Preview changes without applying'
    )
    parser.add_argument(
        '-d', '--delay',
        type=float,
        default=0.5,
        help='Delay between API calls in seconds (default: 0.5)'
    )
    parser.add_argument(
        '-o', '--output-dir',
        default=os.path.expanduser('~/op'),
        help='Directory for report files (default: ~/op)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print progress for each FI'
    )
    parser.add_argument(
        '-nr', '--no-report',
        action='store_true',
        help='Skip generating report files'
    )
    parser.add_argument(
        '-mf', '--mapping-file',
        type=str,
        metavar='FILE',
        help='JSON file with component/version value mappings (see doc for format)'
    )
    parser.add_argument(
        '-mo', '--mapping-only',
        action='store_true',
        help='Apply mappings to FI values directly without etrack comparison'
    )
    parser.add_argument(
        '-p', '--parallel',
        action='store_true',
        help='Enable parallel processing for faster execution'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        metavar='N',
        help='Number of parallel workers (default: 4, use with -p)'
    )

    args = parser.parse_args()

    # Determine which fields to sync
    # If neither --sync-component nor --sync-version specified, sync both
    if args.sync_component_only and args.sync_version_only:
        # Both specified = sync both
        sync_component = True
        sync_version = True
    elif args.sync_component_only:
        sync_component = True
        sync_version = False
    elif args.sync_version_only:
        sync_component = False
        sync_version = True
    else:
        # Default: sync both
        sync_component = True
        sync_version = True

    # Read FI IDs
    if args.input == '-':
        fi_ids = read_fi_ids_from_stdin()
        if not fi_ids:
            print("Error: No FI IDs found in stdin", file=sys.stderr)
            return 1
    else:
        input_path = os.path.expanduser(args.input)
        if not os.path.isfile(input_path):
            print(f"Error: File not found: {input_path}", file=sys.stderr)
            return 1
        fi_ids = read_fi_ids_from_file(input_path)
        if not fi_ids:
            print(f"Error: No FI IDs found in {input_path}", file=sys.stderr)
            return 1

    print(f"Found {len(fi_ids)} unique FI IDs to process")
    if args.dry_run:
        print("[DRY RUN MODE - no changes will be made]")

    sync_fields = []
    if sync_component:
        sync_fields.append("Component")
    if sync_version:
        sync_fields.append("Version")
    print(f"Syncing: {', '.join(sync_fields)}")

    # Load value mappings if specified
    mappings: Dict[str, Dict[str, str]] = {"component": {}, "version": {}}
    if args.mapping_file:
        mappings = load_mappings(args.mapping_file)
        if mappings["component"] or mappings["version"]:
            print(f"Loaded mappings: {len(mappings['component'])} component, {len(mappings['version'])} version")

    # Validate mapping-only mode
    if args.mapping_only:
        if not args.mapping_file:
            print("Error: --mapping-only requires --mapping-file", file=sys.stderr)
            return 1
        if not mappings["component"] and not mappings["version"]:
            print("Error: --mapping-only specified but mapping file is empty", file=sys.stderr)
            return 1
        print("Mode: Mapping-only (no etrack comparison)")

    if args.parallel:
        print(f"Parallel mode: {args.workers} workers")

    print()

    # Process batch
    results = process_fi_batch(
        fi_ids=fi_ids,
        sync_component=sync_component,
        sync_version=sync_version,
        dry_run=args.dry_run,
        delay=args.delay,
        verbose=args.verbose,
        mappings=mappings,
        mapping_only=args.mapping_only,
        parallel=args.parallel,
        workers=args.workers,
    )

    # Print summary
    print_summary(results, dry_run=args.dry_run)

    # Generate reports
    if not args.no_report:
        output_dir = os.path.expanduser(args.output_dir)
        report_files = generate_reports(results, output_dir, dry_run=args.dry_run)
        print("\nReports generated:")
        for report_type, filepath in report_files.items():
            print(f"  {report_type}: {filepath}")

    # Return non-zero if there were failures
    total_failures = (
        len(results[ResultCategory.FAIL_NO_ETRACK]) +
        len(results[ResultCategory.FAIL_MULTI_ETRACK]) +
        len(results[ResultCategory.FAIL_FETCH]) +
        len(results[ResultCategory.FAIL_UPDATE])
    )
    return 1 if total_failures > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
