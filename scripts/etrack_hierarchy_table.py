#!/usr/bin/env python3
"""
Fetch and display full eTrack hierarchy as a table.

This script accepts an incident ID, resolves the super incident (unless explicitly
provided as super), recursively fetches all child incidents, gathers details per
incident, and prints a configurable table.

Default columns:
    INCIDENT,SINCIDENT,TYPE,VERSION,TARGET_VERSION,TARGET_BUILD,ASSIGNED_TO,STATE,RESOLUTION,ABSTRACT

Examples:
    ./etrack_hierarchy_table.py 4203299
    ./etrack_hierarchy_table.py 4203299 --include-cols INCIDENT,SINCIDENT,STATE,ABSTRACT
    ./etrack_hierarchy_table.py 4203299 --exclude-cols TARGET_VERSION,VERSION
    ./etrack_hierarchy_table.py 4203299 --as-super
    ./etrack_hierarchy_table.py 4203299 --ssh user@server
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections import deque
from typing import Dict, List, Optional, Sequence, Set, Tuple

VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_COLUMNS = [
    "INCIDENT",
    "SINCIDENT",
    "PARENT_FLAG",
    "TYPE",
    "VERSION",
    "TARGET_VERSION",
    "TARGET_BUILD",
    "ASSIGNED_TO",
    "STATE",
    "RESOLUTION",
    "ABSTRACT",
]

COLUMN_WIDTHS = {
    "INCIDENT": 10,
    "SINCIDENT": 10,
    "PARENT_FLAG": 3,
    "TYPE": 15,
    "VERSION": 10,
    "TARGET_VERSION": 12,
    "TARGET_BUILD": 12,
    "ASSIGNED_TO": 20,
    "STATE": 12,
    "RESOLUTION": 20,
    "DATE_OPENED": 12,
    "ABSTRACT": 120,
    "DEFAULT": 12,
}

FIELD_ALIAS = {
    "INCIDENT": "INCIDENT",
    "TYPE": "TYPE",
    "VERSION": "VERSION",
    "TARGET_VERSION": "TARGET_VERSION",
    "TARGET_BUILD": "TARGET_BUILD",
    "ASSIGNED_TO": "ASSIGNED_TO",
    "STATE": "STATE",
    "RESOLUTION": "RESOLUTION",
    "DATE_OPENED": "DATE_OPENED",
    "ABSTRACT": "ABSTRACT",
}


class EtrackHierarchyError(Exception):
    pass


class TableRenderer:
    def __init__(self, columns: List[str]):
        self.columns = columns
        self.widths = {
            col: COLUMN_WIDTHS.get(col, COLUMN_WIDTHS["DEFAULT"]) for col in columns
        }

    def _separator(self) -> str:
        return "+" + "+".join("-" * (self.widths[c] + 2) for c in self.columns) + "+"

    def _row(self, row: Dict[str, str]) -> str:
        cells: List[str] = []
        for col in self.columns:
            value = str(row.get(col, ""))
            width = self.widths[col]
            if len(value) > width:
                value = value[:width]
            cells.append(value.ljust(width))
        return "| " + " | ".join(cells) + " |"

    def render(self, rows: List[Dict[str, str]]) -> str:
        sep = self._separator()
        header = self._row({c: c for c in self.columns})
        output = [sep, header, sep]
        for row in rows:
            output.append(self._row(row))
        output.append(sep)
        return "\n".join(output)


class EtrackHierarchyFetcher:
    def __init__(
        self,
        ssh_target: Optional[str] = None,
        verbose: bool = False,
        debug: bool = False,
        command_timeout: int = 20,
    ):
        self.ssh_target = ssh_target
        self.verbose = verbose
        self.debug = debug
        self.command_timeout = command_timeout
        self._details_cache: Dict[str, str] = {}
        self._parsed_details_cache: Dict[str, Dict[str, str]] = {}
        self._query_count = 0

    def _resolve_esql_command(self) -> List[str]:
        if self.ssh_target:
            return [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                self.ssh_target,
                "esql",
            ]

        local_esql = shutil.which("esql")
        if local_esql:
            return [local_esql]

        raise EtrackHierarchyError("esql command not found. Install esql or use --ssh user@host.")

    def _run_esql(self, sql: str) -> str:
        import time
        cmd = self._resolve_esql_command()
        self._query_count += 1
        if self.verbose and not self.debug:
            print(f"[ESQL #{self._query_count}] Running query...", file=sys.stderr)
        if self.debug:
            print(f"\n[ESQL #{self._query_count}] Executing:", file=sys.stderr)
            print(f"{sql}", file=sys.stderr)
            print(f"---", file=sys.stderr)

        start_time = time.time()

        timeouts = [self.command_timeout, max(self.command_timeout * 3, self.command_timeout + 30)]
        result: Optional[subprocess.CompletedProcess[bytes]] = None
        for attempt, timeout_s in enumerate(timeouts, start=1):
            try:
                result = subprocess.run(
                    cmd,
                    input=sql.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout_s,
                    check=False,
                )
                break
            except subprocess.TimeoutExpired:
                if attempt == len(timeouts):
                    raise EtrackHierarchyError(
                        f"esql query timed out after {timeout_s}s. "
                        "Try increasing --timeout."
                    )
                if self.verbose:
                    print(
                        f"[WARN] esql timed out at {timeout_s}s, retrying once with a larger timeout...",
                        file=sys.stderr,
                    )
                continue
            except OSError as exc:
                raise EtrackHierarchyError(f"Unable to execute esql: {exc}") from exc

        if result is None:
            raise EtrackHierarchyError("esql execution failed unexpectedly.")

        elapsed = time.time() - start_time
        if self.debug:
            print(f"[ESQL #{self._query_count}] Completed in {elapsed:.2f}s", file=sys.stderr)
        elif self.verbose:
            print(f"[ESQL #{self._query_count}] Completed in {elapsed:.2f}s", file=sys.stderr)

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            message = stderr or stdout or f"esql failed with exit code {result.returncode}"
            raise EtrackHierarchyError(message)

        return result.stdout.decode("utf-8", errors="replace")

    def _parse_esql_output(self, raw_output: str, fields: List[str]) -> List[Dict[str, str]]:
        records: List[Dict[str, str]] = []
        expected_cols = len(fields)

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("---") or stripped.startswith("===") or stripped.startswith("+"):
                continue

            lower = stripped.lower()
            if "row selected" in lower or "rows selected" in lower or lower.startswith("warning:"):
                continue

            if "|" in stripped:
                parts = [part.strip() for part in re.split(r"\|", stripped)]
                parts = [part for part in parts if part != ""]
            else:
                parts = [part.strip() for part in stripped.split("\t")]

            if not parts:
                continue

            if len(parts) == expected_cols and [p.upper() for p in parts] == fields:
                continue

            if len(parts) < expected_cols:
                parts.extend([""] * (expected_cols - len(parts)))
            elif len(parts) > expected_cols:
                head = parts[: expected_cols - 1]
                tail = " ".join(parts[expected_cols - 1 :]).strip()
                parts = head + [tail]

            records.append({fields[idx]: parts[idx] for idx in range(expected_cols)})

        return records

    def _parse_bulk_eprint_output(self, raw_output: str) -> Dict[str, Dict[str, str]]:
        """Parse bulk eprint output into per-incident records.

        Handles sections delimited by "Information for:" and extracts:
        - incident, superincident, parent_incident, type, version, target_version,
          target_build, assigned_to, state, resolution, date_opened, abstract
        """
        records: Dict[str, Dict[str, str]] = {}
        current_incident: Optional[str] = None
        current_record: Dict[str, str] = {}
        in_description = False
        description_lines: List[str] = []

        for line in raw_output.splitlines():
            stripped = line.strip()
            lower = stripped.lower()

            # Check for section delimiter
            if "information for:" in lower:
                # Save previous record if any
                if current_incident:
                    if description_lines:
                        current_record["DESCRIPTION"] = " ".join(description_lines).strip()
                    records[current_incident] = current_record

                # Reset for new incident
                current_incident = None
                current_record = {}
                in_description = False
                description_lines = []
                continue

            # End of description section
            if in_description and ("information for:" in lower or (not stripped and current_incident)):
                in_description = False
                continue

            # Start of description
            if lower == "description:":
                in_description = True
                continue

            if in_description:
                if stripped:
                    description_lines.append(stripped)
                continue

            # Parse key: value pairs
            if ":" in line:
                match = re.match(r"^\s*([A-Za-z_]+)\s*:\s*(.*)$", line)
                if match:
                    key = match.group(1).strip().lower()
                    value = match.group(2).strip()

                    key_map = {
                        "incident": "INCIDENT",
                        "superincident": "SUPERINCIDENT",
                        "parent_incident": "PARENT_INCIDENT",
                        "type": "TYPE",
                        "version": "VERSION",
                        "target_version": "TARGET_VERSION",
                        "target_build": "TARGET_BUILD",
                        "assigned_to": "ASSIGNED_TO",
                        "state": "STATE",
                        "resolution": "RESOLUTION",
                        "date_opened": "DATE_OPENED",
                        "abstract": "ABSTRACT",
                    }

                    if key in key_map:
                        current_record[key_map[key]] = value
                        if key == "incident" and not current_incident:
                            current_incident = value

        # Save final record
        if current_incident:
            if description_lines:
                current_record["DESCRIPTION"] = " ".join(description_lines).strip()
            records[current_incident] = current_record

        return records

    def _safe_sql_incident(self, incident: str) -> str:
        if not incident.isdigit():
            raise EtrackHierarchyError(f"Invalid incident for SQL: {incident}")
        return str(int(incident))

    def _run_command(self, cmd: Sequence[str]) -> str:
        import time

        full_cmd = list(cmd)
        if self.ssh_target:
            full_cmd = [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                self.ssh_target,
            ] + list(cmd)

        start_time = time.time()
        if self.verbose and not self.debug:
            print("[INFO] Running external command...", file=sys.stderr)
        if self.debug:
            print(f"[INFO] Running: {' '.join(full_cmd)}", file=sys.stderr)

        try:
            result = subprocess.run(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.command_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise EtrackHierarchyError(
                f"Command timed out after {self.command_timeout}s: {' '.join(full_cmd)}"
            ) from exc
        except OSError as exc:
            raise EtrackHierarchyError(
                f"Unable to run command {' '.join(full_cmd)}: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            msg = stderr or stdout or f"Exit code {result.returncode}"
            raise EtrackHierarchyError(
                f"Command failed ({' '.join(full_cmd)}): {msg}"
            )

        elapsed = time.time() - start_time
        if self.verbose:
            print(f"[INFO] External command completed in {elapsed:.2f}s", file=sys.stderr)

        return result.stdout.decode("utf-8", errors="replace")

    def _extract_first_line(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return ""

    def _parse_super_from_eprint_a_line(self, line: str, incident: str) -> str:
        # Example child line:
        # 4194050 (4191185) user OPEN ...
        # The number in parentheses is the super incident for child incidents.
        match = re.search(r"\((\d+)\)", line)
        if match:
            return match.group(1)
        return incident

    def _parse_hierarchy_from_eprint_a_line(self, line: str, root_incident: str) -> List[str]:
        # Example super line:
        # 4191185 (4191186 4191187 4194049 4194050 4194051) user OPEN ...
        # Treat all numbers inside parentheses as hierarchy members plus root.
        incidents: List[str] = [root_incident]
        seen: Set[str] = {root_incident}

        match = re.search(r"\(([^)]*)\)", line)
        if not match:
            return incidents

        for token in re.findall(r"\d+", match.group(1)):
            if token not in seen:
                seen.add(token)
                incidents.append(token)

        return incidents

    def _bulk_prefetch_details_vdk(self, incidents: List[str], chunk_size: int = 100) -> Dict[str, str]:
        """Prefetch bulk eprint -vdK details and extract parent_incident mappings.

        Returns dict mapping incident -> parent_incident for immediate parent relationships.
        """
        if not incidents:
            return {}

        parent_incident_map: Dict[str, str] = {}

        for idx in range(0, len(incidents), chunk_size):
            chunk = incidents[idx : idx + chunk_size]
            output = self._run_command(["eprint", "-vdK"] + chunk)
            parsed = self._parse_bulk_eprint_output(output)

            # Cache per-incident details for fast field extraction later.
            for incident in chunk:
                if incident in parsed:
                    details_lines: List[str] = []
                    row = parsed[incident]
                    # Also cache the parsed row for hierarchy tree display
                    self._parsed_details_cache[incident] = row
                    for key, value in row.items():
                        if key == "INCIDENT":
                            details_lines.append(f"incident: {value}")
                        elif key == "SUPERINCIDENT":
                            details_lines.append(f"superincident: {value}")
                        elif key == "PARENT_INCIDENT":
                            details_lines.append(f"parent_incident: {value}")
                            if str(value).isdigit():
                                parent_incident_map[incident] = str(value)
                        elif key == "ABSTRACT":
                            details_lines.append(f"abstract: {value}")
                        elif key == "TYPE":
                            details_lines.append(f"type: {value}")
                        elif key == "VERSION":
                            details_lines.append(f"version: {value}")
                        elif key == "TARGET_VERSION":
                            details_lines.append(f"target_version: {value}")
                        elif key == "TARGET_BUILD":
                            details_lines.append(f"target_build: {value}")
                        elif key == "ASSIGNED_TO":
                            details_lines.append(f"assigned_to: {value}")
                        elif key == "STATE":
                            details_lines.append(f"state: {value}")
                        elif key == "RESOLUTION":
                            details_lines.append(f"resolution: {value}")
                        elif key == "DATE_OPENED":
                            details_lines.append(f"date_opened: {value}")
                    self._details_cache[incident] = "\n".join(details_lines)

        return parent_incident_map

    def resolve_super_incident(self, incident: str, treat_as_super: bool) -> str:
        if treat_as_super:
            return incident

        output = self._run_command(["eprint", "-a", incident])
        first_line = self._extract_first_line(output)
        return self._parse_super_from_eprint_a_line(first_line, incident)

    def resolve_super_incident_esql(self, incident: str, treat_as_super: bool) -> str:
        if treat_as_super:
            return incident

        sql = (
            "SELECT SUPERINCIDENT FROM INCIDENT_VIEW "
            f"WHERE INCIDENT = {self._safe_sql_incident(incident)}"
        )
        rows = self._parse_esql_output(self._run_esql(sql), ["SUPERINCIDENT"])
        if rows:
            value = str(rows[0].get("SUPERINCIDENT", "")).strip()
            if value.isdigit():
                return value
        return incident

    def _get_details(self, incident: str) -> str:
        cached = self._details_cache.get(incident)
        if cached is not None:
            return cached
        details = self._run_command(["eprint", "-vdK", incident])
        self._details_cache[incident] = details
        return details

    def _extract_children(self, details_text: str) -> List[str]:
        # Match the original shell behavior: parse only lines between
        # "children" and "abstract", then use the first token per line.
        children: List[str] = []
        in_children_block = False

        for raw_line in details_text.splitlines():
            line = raw_line.rstrip("\n")
            lower = line.lower()

            if not in_children_block:
                if "children" in lower:
                    in_children_block = True
                else:
                    continue

            if "abstract" in lower:
                break

            cleaned = re.sub(r"(?i)children:\s*", "", line).strip()
            if not cleaned:
                continue

            first_token = cleaned.split()[0]
            if first_token.isdigit():
                children.append(first_token)

        if not in_children_block:
            return []

        # Preserve order but deduplicate
        seen: Set[str] = set()
        ordered: List[str] = []
        for child in children:
            if child not in seen:
                seen.add(child)
                ordered.append(child)
        return ordered

    def _fetch_children_esql(self, parent_incident: str) -> List[str]:
        sql = (
            "SELECT INCIDENT FROM INCIDENT_VIEW "
            f"WHERE SUPERINCIDENT = {self._safe_sql_incident(parent_incident)}"
        )
        rows = self._parse_esql_output(self._run_esql(sql), ["INCIDENT"])
        children: List[str] = []
        seen: Set[str] = set()
        for row in rows:
            value = str(row.get("INCIDENT", "")).strip()
            if value.isdigit() and value not in seen:
                seen.add(value)
                children.append(value)
        return children

    def fetch_all_hierarchy_esql(self, root_incident: str) -> Tuple[List[str], Dict[str, str]]:
        """Fetch all incidents under a single SUPERINCIDENT with one query."""
        sql = (
            "SELECT INCIDENT FROM INCIDENT_VIEW "
            f"WHERE SUPERINCIDENT = {self._safe_sql_incident(root_incident)}"
        )
        rows = self._parse_esql_output(self._run_esql(sql), ["INCIDENT"])

        incidents: List[str] = [root_incident]  # Include the root
        seen: Set[str] = {root_incident}
        parent_map: Dict[str, str] = {root_incident: root_incident}

        for row in rows:
            incident = str(row.get("INCIDENT", "")).strip()
            if incident.isdigit() and incident not in seen:
                incidents.append(incident)
                seen.add(incident)
                parent_map[incident] = root_incident

        return incidents, parent_map

    def fetch_hierarchy(
        self,
        root_incident: str,
        max_nodes: int = 5000,
        use_esql: bool = False,
    ) -> Tuple[List[str], Dict[str, str]]:
        if use_esql:
            # Single esql query: fetch all incidents under root SUPERINCIDENT
            incidents, parent_map = self.fetch_all_hierarchy_esql(root_incident)
            if len(incidents) > max_nodes:
                raise EtrackHierarchyError(
                    f"Hierarchy exceeded max node limit ({max_nodes})."
                )
            return incidents, parent_map

        # Non-esql: fast eprint path using one -a and batched -vdK prefetch.
        hierarchy_raw = self._run_command(["eprint", "-a", root_incident])
        hierarchy_line = self._extract_first_line(hierarchy_raw)
        incidents = self._parse_hierarchy_from_eprint_a_line(hierarchy_line, root_incident)

        if len(incidents) > max_nodes:
            raise EtrackHierarchyError(
                f"Hierarchy exceeded max node limit ({max_nodes})."
            )

        # Initialize parent_map with root pointing to itself.
        parent_map: Dict[str, str] = {root_incident: root_incident}
        for incident in incidents:
            if incident != root_incident:
                parent_map[incident] = root_incident

        # Single/batched prefetch of details and extract parent_incident relationships.
        parent_incident_map = self._bulk_prefetch_details_vdk(incidents)
        # Override parent_map with actual immediate parents where available.
        parent_map.update(parent_incident_map)

        return incidents, parent_map

    def _extract_abstract(self, incident: str) -> str:
        raw = self._run_command(["eprint", "-a", incident])
        first_non_empty = ""
        for line in raw.splitlines():
            if line.strip():
                first_non_empty = line.strip()
                break

        if not first_non_empty:
            return ""

        cleaned = re.sub(
            r"^\d+\s*[(-]*[0-9 )]*[A-Za-z_]+\s*[A-Za-z_]+\s*",
            "",
            first_non_empty,
        )

        return cleaned.strip()

    def _extract_fields_from_xeprs(self, incident: str) -> Dict[str, str]:
        output = self._run_command(["eprint", "-v", incident])
        record: Dict[str, str] = {}

        for line in output.splitlines():
            match = re.match(r"^\s*([A-Za-z_]+)\s*:\s*(.*)\s*$", line)
            if not match:
                continue
            key = match.group(1).upper()
            value = match.group(2).strip()
            if key in FIELD_ALIAS:
                record[FIELD_ALIAS[key]] = value

        return record

    def _extract_fields_from_details(self, incident: str) -> Dict[str, str]:
        details = self._get_details(incident)
        record: Dict[str, str] = {}

        key_map = {
            "type": "TYPE",
            "version": "VERSION",
            "target_version": "TARGET_VERSION",
            "target_build": "TARGET_BUILD",
            "assigned_to": "ASSIGNED_TO",
            "state": "STATE",
            "resolution": "RESOLUTION",
            "date_opened": "DATE_OPENED",
        }

        for line in details.splitlines():
            match = re.match(r"^\s*([A-Za-z_]+)\s*:\s*(.*)\s*$", line)
            if not match:
                continue
            key = match.group(1).strip().lower()
            value = match.group(2).strip()
            mapped = key_map.get(key)
            if mapped:
                record[mapped] = value

        return record

    def _extract_abstract_from_details_text(self, details_text: str) -> str:
        for line in details_text.splitlines():
            match = re.match(r"^\s*abstract\s*:\s*(.*)\s*$", line, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def fetch_records_eprint_cached(
        self,
        incidents: List[str],
        parent_map: Dict[str, str],
    ) -> List[Dict[str, str]]:
        """Build eprint-mode records from cached -vdK output in one pass.

        This avoids expensive per-incident eprint -v and eprint -a calls after
        hierarchy traversal has already populated the -vdK cache.
        """
        result: List[Dict[str, str]] = []
        for incident in incidents:
            details = self._get_details(incident)
            fields = self._extract_fields_from_details(incident)
            record = {
                "INCIDENT": incident,
                "SINCIDENT": parent_map.get(incident, incident),
                "PARENT_FLAG": "",
                "TYPE": str(fields.get("TYPE", "")),
                "VERSION": str(fields.get("VERSION", "")),
                "TARGET_VERSION": str(fields.get("TARGET_VERSION", "") or "N/A"),
                "TARGET_BUILD": str(fields.get("TARGET_BUILD", "")),
                "ASSIGNED_TO": str(fields.get("ASSIGNED_TO", "")),
                "STATE": str(fields.get("STATE", "")),
                "RESOLUTION": str(fields.get("RESOLUTION", "")),
                "DATE_OPENED": str(fields.get("DATE_OPENED", "")),
                "ABSTRACT": self._extract_abstract_from_details_text(details),
            }
            result.append(record)

        return result

    def fetch_record(self, incident: str, sincident: str) -> Dict[str, str]:
        record = {
            "INCIDENT": incident,
            "SINCIDENT": sincident,
            "PARENT_FLAG": "",
            "TYPE": "",
            "VERSION": "",
            "TARGET_VERSION": "N/A",
            "TARGET_BUILD": "",
            "ASSIGNED_TO": "",
            "STATE": "",
            "RESOLUTION": "",
            "DATE_OPENED": "",
            "ABSTRACT": "",
        }

        x_fields: Dict[str, str] = {}
        try:
            x_fields = self._extract_fields_from_xeprs(incident)
        except EtrackHierarchyError as exc:
            if self.verbose:
                print(
                    f"[WARN] eprint -v failed for {incident}; falling back to eprint -vdK ({exc})",
                    file=sys.stderr,
                )
            x_fields = self._extract_fields_from_details(incident)

        if not x_fields:
            x_fields = self._extract_fields_from_details(incident)

        for key, value in x_fields.items():
            if key in record:
                record[key] = value

        record["ABSTRACT"] = self._extract_abstract(incident)
        if not record["TARGET_VERSION"]:
            record["TARGET_VERSION"] = "N/A"

        return record

    def fetch_records_bulk_eprint(
        self,
        incidents: List[str],
        parent_map: Dict[str, str],
    ) -> List[Dict[str, str]]:
        """Fetch records using bulk eprint command with all incidents.

        Runs: eprint incident1 incident2 incident3 ...
        Parses output to extract parent_incident for accurate SINCIDENT values.
        """
        if not incidents:
            return []

        # Run bulk eprint with all incidents
        cmd = ["eprint"] + incidents
        import time
        print(f"\n[BULK_EPRINT] Executing bulk eprint with {len(incidents)} incidents", file=sys.stderr)

        start_time = time.time()
        raw_output = self._run_command(cmd)
        elapsed = time.time() - start_time
        print(f"[BULK_EPRINT] Completed in {elapsed:.2f}s", file=sys.stderr)

        # Parse bulk output
        by_incident = self._parse_bulk_eprint_output(raw_output)

        result: List[Dict[str, str]] = []
        for incident in incidents:
            src = by_incident.get(incident, {})

            # Prefer parent_incident for SINCIDENT, fall back to parent_map (from hierarchy)
            sincident = src.get("PARENT_INCIDENT", "")
            if not sincident:
                sincident = parent_map.get(incident, incident)

            record = {
                "INCIDENT": incident,
                "SINCIDENT": sincident,
                "PARENT_FLAG": "",
                "TYPE": str(src.get("TYPE", "")),
                "VERSION": str(src.get("VERSION", "")),
                "TARGET_VERSION": str(src.get("TARGET_VERSION", "") or "N/A"),
                "TARGET_BUILD": str(src.get("TARGET_BUILD", "")),
                "ASSIGNED_TO": str(src.get("ASSIGNED_TO", "")),
                "STATE": str(src.get("STATE", "")),
                "RESOLUTION": str(src.get("RESOLUTION", "")),
                "DATE_OPENED": str(src.get("DATE_OPENED", "")),
                "ABSTRACT": str(src.get("ABSTRACT", "")),
            }
            result.append(record)

        return result

    def fetch_parent_incidents_esql(self, incidents: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Fetch parent_incident and superincident from INC_BOTTOM_UP table.

        Returns tuple of (parent_map, superincident_map):
        - parent_map[incident] = TO_NUMBER (immediate parent)
        - superincident_map[incident] = TOP (superincident)
        """
        if not incidents:
            return {}, {}

        sql_incidents = ", ".join(self._safe_sql_incident(incident) for incident in incidents)
        sql = (
            "SELECT INCIDENT, TO_NUMBER, TOP FROM INC_BOTTOM_UP "
            f"WHERE TO_NUMBER IN ({sql_incidents})"
        )

        import time
        if self.debug:
            print(f"\n[ESQL] Fetching parent/superincident from INC_BOTTOM_UP", file=sys.stderr)
        start_time = time.time()

        rows = self._parse_esql_output(self._run_esql(sql), ["INCIDENT", "TO_NUMBER", "TOP"])

        elapsed = time.time() - start_time
        if self.debug:
            print(f"[ESQL] Completed in {elapsed:.2f}s", file=sys.stderr)

        parent_map: Dict[str, str] = {}
        superincident_map: Dict[str, str] = {}

        for row in rows:
            incident = str(row.get("INCIDENT", "")).strip()
            to_number = str(row.get("TO_NUMBER", "")).strip()
            top = str(row.get("TOP", "")).strip()

            if incident.isdigit() and to_number.isdigit():
                parent_map[incident] = to_number
            if incident.isdigit() and top.isdigit():
                superincident_map[incident] = top

        return parent_map, superincident_map

    def build_hierarchy_tree(self, incidents: List[str], parent_map: Dict[str, str], root_incident: str) -> Dict[str, List[str]]:
        """Build incident hierarchy tree from parent relationships.

        Returns dict mapping parent -> list of children.
        """
        tree: Dict[str, List[str]] = {}

        incident_set = set(incidents)
        for incident in incidents:
            parent = parent_map.get(incident, root_incident)

            # Avoid self-loops like root->root that break recursive rendering.
            if parent == incident:
                continue

            # Only connect edges inside the current hierarchy set.
            if parent not in incident_set and parent != root_incident:
                continue

            if parent not in tree:
                tree[parent] = []
            tree[parent].append(incident)

        for parent in list(tree.keys()):
            tree[parent] = sorted(set(tree[parent]), key=lambda value: int(value))

        return tree

    def print_hierarchy_tree(
        self,
        root: str,
        tree: Dict[str, List[str]],
        depth: int = 0,
        visited: Optional[Set[str]] = None,
    ) -> None:
        """Print hierarchy tree in nested format with incident details."""
        if visited is None:
            visited = set()

        indent = "  " * depth
        prefix = "+-- " if depth > 0 else ""

        if root in visited:
            print(f"{indent}{prefix}{root} (cycle)", flush=True)
            return

        # Extract incident details for display
        details = self._parsed_details_cache.get(root, {})
        incident_type = details.get("TYPE", "")
        version = details.get("VERSION", "")
        target_version = details.get("TARGET_VERSION", "")
        state = details.get("STATE", "")

        # Format: incident (T:type V:version TV:target_version S:state)
        details_str = ""
        if incident_type or version or target_version or state:
            details_str = f" (T:{incident_type} V:{version} TV:{target_version} S:{state})"

        print(f"{indent}{prefix}{root}{details_str}", flush=True)
        visited.add(root)

        if root in tree:
            children = tree[root]
            for child in children:
                self.print_hierarchy_tree(child, tree, depth + 1, visited)

        visited.remove(root)

    def fetch_records_esql(
        self,
        incidents: List[str],
        parent_map: Dict[str, str],
    ) -> List[Dict[str, str]]:
        if not incidents:
            return []

        sql_incidents = ", ".join(self._safe_sql_incident(incident) for incident in incidents)
        fields = [
            "INCIDENT",
            "TYPE",
            "VERSION",
            "TARGET_VERSION",
            "TARGET_BUILD",
            "ASSIGNED_TO",
            "STATE",
            "RESOLUTION",
            "DATE_OPENED",
            "ABSTRACT",
        ]
        sql = (
            "SELECT " + ", ".join(fields) + " "
            "FROM INCIDENT "
            f"WHERE INCIDENT IN ({sql_incidents})"
        )

        rows = self._parse_esql_output(self._run_esql(sql), fields)
        by_incident = {str(row.get("INCIDENT", "")).strip(): row for row in rows}

        result: List[Dict[str, str]] = []
        for incident in incidents:
            src = by_incident.get(incident, {})
            record = {
                "INCIDENT": incident,
                "SINCIDENT": parent_map.get(incident, incident),
                "PARENT_FLAG": "",
                "TYPE": str(src.get("TYPE", "")),
                "VERSION": str(src.get("VERSION", "")),
                "TARGET_VERSION": str(src.get("TARGET_VERSION", "") or "N/A"),
                "TARGET_BUILD": str(src.get("TARGET_BUILD", "")),
                "ASSIGNED_TO": str(src.get("ASSIGNED_TO", "")),
                "STATE": str(src.get("STATE", "")),
                "RESOLUTION": str(src.get("RESOLUTION", "")),
                "DATE_OPENED": str(src.get("DATE_OPENED", "")),
                "ABSTRACT": str(src.get("ABSTRACT", "")),
            }
            result.append(record)

            # Cache parsed details for hierarchy tree display
            if incident in by_incident:
                self._parsed_details_cache[incident] = {
                    "TYPE": str(by_incident[incident].get("TYPE", "")),
                    "VERSION": str(by_incident[incident].get("VERSION", "")),
                    "TARGET_VERSION": str(by_incident[incident].get("TARGET_VERSION", "")),
                    "STATE": str(by_incident[incident].get("STATE", "")),
                }

        return result


def _normalize_column_list(raw: Optional[str], option_name: str) -> List[str]:
    if not raw:
        return []

    columns = [token.strip().upper() for token in raw.split(",") if token.strip()]
    invalid = [col for col in columns if not VALID_IDENTIFIER_RE.match(col)]
    if invalid:
        raise EtrackHierarchyError(
            f"Invalid {option_name} value(s): {', '.join(invalid)}"
        )

    return columns


def _resolve_output_columns(
    include_cols_raw: Optional[str],
    exclude_cols_raw: Optional[str],
    allowed_columns: List[str],
) -> List[str]:
    include_cols = _normalize_column_list(include_cols_raw, "--include-cols")
    exclude_cols = set(_normalize_column_list(exclude_cols_raw, "--exclude-cols"))

    if include_cols:
        unknown = [col for col in include_cols if col not in allowed_columns]
        if unknown:
            raise EtrackHierarchyError(
                "Unknown --include-cols value(s): "
                f"{', '.join(unknown)}. Available: {', '.join(allowed_columns)}"
            )
        selected = include_cols
    else:
        selected = allowed_columns.copy()

    result = [col for col in selected if col not in exclude_cols]
    if not result:
        raise EtrackHierarchyError(
            "No output columns remain after include/exclude filtering."
        )
    return result


def _validate_incident(value: str, option_name: str) -> str:
    incident = value.strip()
    if not incident or not incident.isdigit():
        raise EtrackHierarchyError(f"Invalid {option_name}: '{value}'. Must be numeric.")
    return incident


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch all eTracks in hierarchy and print tabular output.",
        epilog=(
            "Examples:\n"
            "  %(prog)s 4203299\n"
            "  %(prog)s 4203299 --as-super\n"
            "  %(prog)s 4203299 --use-eprint\n"
            "  %(prog)s 4203299 --include-cols INCIDENT,SINCIDENT,STATE,ABSTRACT\n"
            "  %(prog)s 4203299 --exclude-cols VERSION,TARGET_VERSION\n"
            "  %(prog)s 4203299 --ssh user@server"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("incident", help="Incident ID or super incident ID")
    parser.add_argument(
        "--as-super",
        action="store_true",
        help="Treat input incident as already-super incident (skip auto-resolution).",
    )
    parser.add_argument(
        "--include-cols",
        "-I",
        help="Comma-separated columns to include.",
    )
    parser.add_argument(
        "--exclude-cols",
        "-E",
        help="Comma-separated columns to exclude.",
    )
    parser.add_argument(
        "--ssh",
        help="Run commands remotely via SSH target user@host.",
    )
    parser.add_argument(
        "--use-eprint",
        dest="use_esql",
        action="store_false",
        help="Use legacy eprint-based hierarchy/details fetch.",
    )
    parser.set_defaults(use_esql=True)
    parser.add_argument(
        "--htree",
        dest="htree",
        action="store_true",
        help="Display hierarchy tree output after the table.",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=5000,
        help="Safety limit for recursive hierarchy traversal (default: 5000).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Per-command timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print command execution details to stderr.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print esql query execution traces to stderr.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        input_incident = _validate_incident(args.incident, "incident")
        fetcher = EtrackHierarchyFetcher(
            ssh_target=args.ssh,
            verbose=args.verbose,
            debug=args.debug,
            command_timeout=args.timeout,
        )

        if args.use_esql:
            root_incident = fetcher.resolve_super_incident_esql(
                input_incident,
                treat_as_super=args.as_super,
            )
        else:
            root_incident = fetcher.resolve_super_incident(
                input_incident,
                treat_as_super=args.as_super,
            )

        if args.verbose:
            print(f"[INFO] Resolved SINCIDENT: {root_incident}", file=sys.stderr)

        hierarchy_incidents, parent_map = fetcher.fetch_hierarchy(
            root_incident,
            max_nodes=args.max_nodes,
            use_esql=args.use_esql,
        )

        columns = _resolve_output_columns(
            args.include_cols,
            args.exclude_cols,
            DEFAULT_COLUMNS,
        )

        if args.use_esql:
            rows = fetcher.fetch_records_esql(hierarchy_incidents, parent_map)
            parent_overrides, _ = fetcher.fetch_parent_incidents_esql(
                hierarchy_incidents
            )
            for row in rows:
                incident = row.get("INCIDENT", "")
                if incident in parent_overrides:
                    row["SINCIDENT"] = parent_overrides[incident]
            # Update parent_map with SQL-derived parents for accurate parent flags/tree.
            parent_map.update(parent_overrides)
        else:
            rows = fetcher.fetch_records_eprint_cached(hierarchy_incidents, parent_map)

        # Identify which incidents are parents to others and add flag
        parent_incidents: Set[str] = set()
        for row in rows:
            sincident = row.get("SINCIDENT", "")
            if sincident and sincident != row.get("INCIDENT", ""):
                parent_incidents.add(sincident)

        for row in rows:
            incident = row.get("INCIDENT", "")
            if incident in parent_incidents:
                row["PARENT_FLAG"] = "*"
            else:
                row["PARENT_FLAG"] = ""

        renderer = TableRenderer(columns)
        print(renderer.render(rows))
        print(f"\nTotal rows: {len(rows)}")
        print(f"\nNote: '*' in PARENT_FLAG column indicates incident is a parent to other incidents in hierarchy")

        if args.htree:
            print(f"\n{'='*80}")
            print("HIERARCHY TREE:")
            print(f"{'='*80}")
            tree = fetcher.build_hierarchy_tree(
                hierarchy_incidents,
                parent_map,
                root_incident,
            )
            fetcher.print_hierarchy_tree(root_incident, tree)

        if args.use_esql and args.debug:
            print(f"[DEBUG] Total esql queries executed: {fetcher._query_count}", file=sys.stderr)

        return 0

    except EtrackHierarchyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
