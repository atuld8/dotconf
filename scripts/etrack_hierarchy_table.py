#!/usr/bin/env python3
"""
Fetch and display full eTrack hierarchy as a table.

This script accepts an incident ID, resolves the super incident (unless explicitly
provided as super), recursively fetches all child incidents, gathers details per
incident, and prints a configurable table.

USAGE:
    etrack_hierarchy_table.py INCIDENT [options]

    Quick flags: -S/--as-super  -1/--single  -N/--skip-hierarchy  -R/--ssh
                 -A/-P/-B/-C deliverable  -q/--quiet  -v/--verbose  -d/--debug
                 (full list: run with -h)

Default columns:
    INCIDENT,SINCIDENT,PARENT_FLAG,TYPE,VERSION,TARGET_VERSION,TARGET_BUILD,
    ASSIGNED_TO,STATE,RESOLUTION,ABSTRACT

When -R/--ssh is omitted, auto-SSH uses ETRACK_SSH, ENGVM_HOST, or NIS_USER@NIS_SERVER.

Examples:
    ./etrack_hierarchy_table.py 4203299
    ./etrack_hierarchy_table.py 4203299 -1
    ./etrack_hierarchy_table.py 4203299 -N
    ./etrack_hierarchy_table.py 4203299 -q
    ./etrack_hierarchy_table.py 4203299 -y incident-view
    ./etrack_hierarchy_table.py 4203299 -p
    ./etrack_hierarchy_table.py 4203299 -I INCIDENT,SINCIDENT,STATE,ABSTRACT
    ./etrack_hierarchy_table.py 4203299 -E TARGET_VERSION,VERSION
    ./etrack_hierarchy_table.py 4203299 -S
    ./etrack_hierarchy_table.py 4203299 -R user@server
    ./etrack_hierarchy_table.py 4232810 -R user@server -B -N
    ./etrack_hierarchy_table.py 4230893 -A -N
    ./etrack_hierarchy_table.py 4230893 -P -N -D
    ./etrack_hierarchy_table.py 4234410 -A -N -D
    ./etrack_hierarchy_table.py 4234410 -C -N -D
    ./etrack_hierarchy_table.py 4230893 -P -N -G eprint -F
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

HIERARCHY_SHORT_OPTIONS_HELP = """
OPTION GROUPS (every long option has a short form):
  Input & scope:       -S/--as-super  -1/--single  -N/--skip-hierarchy
  Output format:       -I/--include-cols  -E/--exclude-cols  -t/--htree
                       -D/--include-deliverable-details  -U/--full-deliverable-details
                       -F/--stale-only
  Deliverable reports: -A/--auto-deliverable  -P/--as-eeb-pkg  -B/--as-bundle
                       -C/--as-standard-eeb  -G/--deliverable-details-source
                       -j/--deliverable-parallel
  Data source:         -y/--hierarchy-source  -p/--use-eprint
  Remote access:       -R/--ssh  -Z/--no-auto-ssh  -X/--no-ssh-multiplex
  Performance:         -m/--max-nodes  -T/--timeout  -z/--retries  -g/--retry-delay
  Logging:             -q/--quiet  -v/--verbose  -d/--debug
"""

HIERARCHY_USAGE = """%(prog)s INCIDENT [-h]
        [-S, --as-super] [-1, --single] [-N, --skip-hierarchy] [-t, --htree]
        [-I COLS, --include-cols COLS] [-E COLS, --exclude-cols COLS]
        [-R SSH, --ssh SSH] [-Z, --no-auto-ssh] [-X, --no-ssh-multiplex]
        [-A, --auto-deliverable] [-P, --as-eeb-pkg] [-B, --as-bundle]
        [-C, --as-standard-eeb]
        [-D, --include-deliverable-details]
        [-U, --full-deliverable-details]
        [-G SRC, --deliverable-details-source SRC] [-F, --stale-only]
        [-j N, --deliverable-parallel N]
        [-y SRC, --hierarchy-source SRC] [-p, --use-eprint]
        [-m N, --max-nodes N] [-T SEC, --timeout SEC]
        [-z N, --retries N] [-g SEC, --retry-delay SEC]
        [-q, --quiet] [-v, --verbose] [-d, --debug]"""


class ShortLongHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Show short before long as '-S, --as-super' in usage and option help."""

    def _format_action_invocation(self, action):
        if not action.option_strings:
            return super()._format_action_invocation(action)

        opts = sorted(
            action.option_strings,
            key=lambda option: (option.startswith('--'), option),
        )

        if action.nargs == 0:
            return ', '.join(opts)

        if action.metavar is not None:
            metavar = action.metavar
        elif action.choices is not None:
            metavar = '{' + ','.join(map(str, action.choices)) + '}'
        else:
            metavar = self._get_default_metavar_for_optional(action)

        if metavar:
            if isinstance(metavar, tuple):
                return ', '.join(opts) + ' ' + ' '.join(metavar)
            return ', '.join(opts) + ' ' + str(metavar)
        return ', '.join(opts)

    def _format_actions_usage(self, actions, groups):
        """Include long option names in the usage summary (argparse uses short only)."""
        parts: List[str] = []
        for action in actions:
            if action.option_strings:
                parts.append('[%s]' % self._format_action_invocation(action))
            elif action.metavar:
                parts.append(action.metavar)
            else:
                parts.append(action.dest)
        return ' '.join(parts)


HIERARCHY_SOURCES = ("inc-bottom-up", "incident-view", "eprint")
DELIVERABLE_DETAIL_SOURCES = ("esql", "eprint", "auto")
DEFAULT_HIERARCHY_SOURCE = "inc-bottom-up"
DEFAULT_DELIVERABLE_PARALLEL = 8
DEFAULT_DELIVERABLE_DETAILS_SOURCE = "esql"
DELIVERABLE_FULL_DETAIL_ROW_LIMIT = 24
DEFAULT_COMMAND_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0

SSH_ERROR_RULES: List[Tuple[re.Pattern[str], str, bool]] = [
    (re.compile(r"Could not resolve hostname", re.I), "dns", True),
    (re.compile(r"nodename nor servname provided", re.I), "dns", True),
    (re.compile(r"Temporary failure in name resolution", re.I), "dns", True),
    (re.compile(r"Connection timed out", re.I), "timeout", True),
    (re.compile(r"Operation timed out", re.I), "timeout", True),
    (re.compile(r"Connection reset", re.I), "network", True),
    (re.compile(r"Broken pipe", re.I), "network", True),
    (re.compile(r"Connection refused", re.I), "network", True),
    (re.compile(r"No route to host", re.I), "network", True),
    (re.compile(r"Network is unreachable", re.I), "network", True),
    (re.compile(r"Control socket connect", re.I), "multiplex", True),
    (re.compile(r"ControlMaster", re.I), "multiplex", True),
    (re.compile(r"Permission denied", re.I), "auth", False),
    (re.compile(r"Host key verification failed", re.I), "hostkey", False),
    (re.compile(r"Authentication failed", re.I), "auth", False),
    (re.compile(r"Could not resolve address", re.I), "dns", True),
]

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


class CommandTimeoutError(EtrackHierarchyError):
    pass


def _ssh_host_from_target(ssh_target: Optional[str]) -> str:
    if not ssh_target:
        return "remote host"
    return ssh_target.split("@", 1)[-1]


def normalize_ssh_target(target: Optional[str]) -> Optional[str]:
    """Normalize -R/--ssh to user@host; prepend NIS_USER/USER when host has no @."""
    if not target:
        return None
    target = target.strip()
    if not target:
        return None
    if "@" in target:
        return target
    login = (
        os.environ.get("NIS_USER")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
    )
    if login:
        return f"{login.strip()}@{target}"
    return target


def default_ssh_target() -> Optional[str]:
    """
    Default etrack SSH target from environment.

    Priority: ETRACK_SSH, USER@ENGVM_HOST, NIS_USER@NIS_SERVER.
    """
    explicit = os.environ.get("ETRACK_SSH", "").strip()
    if explicit:
        return explicit

    engvm_host = os.environ.get("ENGVM_HOST", "").strip()
    if engvm_host:
        login = os.environ.get("NIS_USER") or os.environ.get("USER") or os.environ.get("LOGNAME")
        if login and "@" not in engvm_host:
            return f"{login.strip()}@{engvm_host}"
        return engvm_host

    nis_user = os.environ.get("NIS_USER", "").strip()
    nis_server = os.environ.get("NIS_SERVER", "").strip()
    if nis_user and nis_server:
        return f"{nis_user}@{nis_server}"

    return None


def classify_command_error(stderr: str, returncode: int) -> Tuple[str, bool]:
    text = stderr or ""
    for pattern, category, retryable in SSH_ERROR_RULES:
        if pattern.search(text):
            return category, retryable
    if returncode == 255 and (re.search(r"\bssh\b", text, re.I) or not text.strip()):
        return "ssh", True
    return "unknown", False


def format_command_error(
    error_label: str,
    ssh_target: Optional[str],
    detail: str,
    category: str,
    context: Optional[str] = None,
) -> str:
    host = _ssh_host_from_target(ssh_target)
    lines = [f"{error_label} failed"]
    if ssh_target:
        lines[0] += f" via SSH to {ssh_target}"
    if context:
        lines.append(f"  Context: {context}")

    hints: List[str] = []
    if category == "dns":
        lines.append("  Cause: hostname could not be resolved (DNS)")
        hints = [
            "Connect to corporate VPN",
            f"Verify: nslookup {host}",
            "Check: echo $ENGVM_HOST (or your --ssh target)",
            f"Optional: add {host} to /etc/hosts if you know the IP",
        ]
    elif category == "timeout":
        if ssh_target:
            lines.append("  Cause: SSH connection timed out")
        else:
            lines.append("  Cause: command timed out")
        hints = [
            "Verify VPN/network connectivity" if ssh_target else None,
            f"Test: ssh -o ConnectTimeout=10 {ssh_target} true" if ssh_target else None,
            "Try increasing --timeout",
        ]
        hints = [hint for hint in hints if hint]
    elif category == "network":
        lines.append("  Cause: network connection error")
        hints = [
            "Verify VPN/network connectivity",
            f"Test: ssh {ssh_target or host} true",
        ]
    elif category == "multiplex":
        lines.append("  Cause: stale SSH multiplex (ControlMaster) socket")
        hints = [
            "Retry usually succeeds automatically",
            "Or disable multiplex: --no-ssh-multiplex / -X",
        ]
    elif category == "auth":
        lines.append("  Cause: SSH authentication failed")
        hints = [
            "Verify SSH keys/agent: ssh-add -l",
            f"Test: ssh {ssh_target or host} true",
        ]
    elif category == "hostkey":
        lines.append("  Cause: SSH host key verification failed")
        hints = [
            f"Update known_hosts for {host}",
            f"Test: ssh {ssh_target or host} true",
        ]
    elif category == "ssh":
        lines.append("  Cause: SSH connection error")
        hints = [
            "Verify VPN/network connectivity",
            f"Test: ssh -o ConnectTimeout=10 {ssh_target or host} true",
            "Or disable multiplex: --no-ssh-multiplex / -X",
        ]
    elif category == "unknown" and "exit code 255" in detail:
        lines.append("  Cause: remote command failed (often SSH)")
        hints = [
            f"Test: ssh -o ConnectTimeout=10 {ssh_target or host} true",
            "Or disable multiplex: --no-ssh-multiplex / -X",
        ]

    if detail:
        first_line = detail.splitlines()[0].strip()
        if first_line:
            lines.append(f"  Detail: {first_line}")

    if hints:
        lines.append("  Try:")
        lines.extend(f"    - {hint}" for hint in hints)

    return "\n".join(lines)


TRENCHER_COMMENT_HEADER_RE = re.compile(
    r"^\((\d+)\)\s+@\s+svc_rmntrencher\s+"
    r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\s+\w+)\s*$",
    re.MULTILINE,
)
EPRINT_COMMENT_HEADER_RE = re.compile(
    r"^\(\d+\)\s+@\s+\S+",
    re.MULTILINE,
)
EEB_PKG_MARKER = "*** This is an EEB Package"
EEB_BUNDLE_MARKER = "*** This is an EEB Bundle"
EEB_VERSION_RE = re.compile(r"This is EEB version\s*:\s*(\d+)", re.IGNORECASE)
EEB_CONSTITUENT_RE = re.compile(r"EEB\s+et\s+(\d+)\s+v(\d+)", re.IGNORECASE)
ET_CONSTITUENT_RE = re.compile(r"\bET\s+(\d+)\b", re.IGNORECASE)
ARTIFACT_LINE_RE = re.compile(r"^(\d+)\s+(\d+)\s+(\S+/)(.+)$")
URL_RE = re.compile(r"https://[^\s\]>]+")

# Internal kind ids (stable in code) -> user-facing labels
DELIVERABLE_KINDS: Tuple[str, ...] = ("eeb-pkg", "bundle", "eeb-standard")
DELIVERABLE_KIND_LABELS: Dict[str, str] = {
    "eeb-pkg": "EEB PACKAGE",
    "bundle": "EEB BUNDLE",
    "eeb-standard": "STANDARD EEB",
}
DELIVERABLE_KIND_HINT_CODES: Dict[str, str] = {
    "eeb-pkg": "PKG",
    "bundle": "BUNDLE",
    "eeb-standard": "STANDARD",
}


def deliverable_kind_label(kind: str) -> str:
    """User-facing deliverable type name for reports and errors."""
    return DELIVERABLE_KIND_LABELS.get(kind, kind.upper())


def deliverable_kind_hint_code(kind: str) -> str:
    """Short type code for DELIVERABLE SUMMARY tables."""
    return DELIVERABLE_KIND_HINT_CODES.get(kind, kind.upper()[:8])


@dataclass
class ConstituentRef:
    incident: str
    embedded_version: Optional[int] = None
    in_bundle_contains: bool = True


@dataclass
class ArtifactRow:
    checksum: str
    size: str
    platform: str
    filename: str

    @property
    def path(self) -> str:
        return f"{self.platform}/{self.filename}"


@dataclass
class PlatformPackage:
    secure_file: str
    package_name: str

    @property
    def platform(self) -> str:
        return self.secure_file.split("/", 1)[0]


@dataclass
class DeliverableVersion:
    kind: str
    incident: str
    eeb_version: int
    product_version: str
    primary: str
    comment_num: str
    comment_date: str
    constituents: List[ConstituentRef] = field(default_factory=list)
    artifacts: List[ArtifactRow] = field(default_factory=list)
    platform_packages: List[PlatformPackage] = field(default_factory=list)
    links: Dict[str, str] = field(default_factory=dict)
    readme_notes: str = ""
    problem_description: str = ""
    submission_type: str = ""
    install_on: str = ""


def extract_trencher_comments(comments_text: str) -> str:
    """Return concatenated svc_rmntrencher comment blocks from full eprint -c output."""
    headers = list(EPRINT_COMMENT_HEADER_RE.finditer(comments_text))
    if not headers:
        return ""

    parts: List[str] = []
    for index, match in enumerate(headers):
        if "svc_rmntrencher" not in match.group(0):
            continue
        start = match.start()
        end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(comments_text)
        )
        parts.append(comments_text[start:end])
    return "".join(parts)


class TrencherDeliverableParser:
    @staticmethod
    def _block_has_eeb_version(block: str) -> bool:
        return EEB_VERSION_RE.search(block) is not None

    @classmethod
    def _is_standard_eeb_block(cls, block: str) -> bool:
        """Standard single-ET deliverable (no Package/Bundle marker)."""
        if EEB_PKG_MARKER in block or EEB_BUNDLE_MARKER in block:
            return False
        return cls._block_has_eeb_version(block)

    def parse(
        self,
        comments_text: str,
        incident: str,
        kind: str,
    ) -> List[DeliverableVersion]:
        blocks = self._extract_service_request_blocks(comments_text, incident)
        versions: List[DeliverableVersion] = []

        for comment_num, comment_date, block in blocks:
            if kind == "eeb-pkg":
                if EEB_PKG_MARKER not in block:
                    continue
            elif kind == "bundle":
                if EEB_BUNDLE_MARKER not in block:
                    continue
            elif kind == "eeb-standard":
                if not self._is_standard_eeb_block(block):
                    continue
            else:
                continue

            parsed = self._parse_block(
                block,
                incident=incident,
                kind=kind,
                comment_num=comment_num,
                comment_date=comment_date,
            )
            if parsed:
                versions.append(parsed)

        versions.sort(key=lambda item: item.eeb_version)
        return versions

    def detect_kinds(self, comments_text: str, incident: str) -> List[str]:
        blocks = self._extract_service_request_blocks(comments_text, incident)
        kinds: List[str] = []
        seen: Set[str] = set()
        for _, _, block in blocks:
            if EEB_PKG_MARKER in block and "eeb-pkg" not in seen:
                seen.add("eeb-pkg")
                kinds.append("eeb-pkg")
            if EEB_BUNDLE_MARKER in block and "bundle" not in seen:
                seen.add("bundle")
                kinds.append("bundle")
            if self._is_standard_eeb_block(block) and "eeb-standard" not in seen:
                seen.add("eeb-standard")
                kinds.append("eeb-standard")
        return kinds

    def _extract_service_request_blocks(
        self,
        comments_text: str,
        incident: str,
    ) -> List[Tuple[str, str, str]]:
        blocks: List[Tuple[str, str, str]] = []
        headers = list(TRENCHER_COMMENT_HEADER_RE.finditer(comments_text))

        for match in re.finditer(
            rf"^Service request:\s*{re.escape(incident)}\s*$",
            comments_text,
            re.MULTILINE,
        ):
            service_start = match.start()
            comment_num = "?"
            comment_date = "?"
            block_start = service_start
            for header in headers:
                if header.start() < service_start:
                    comment_num = header.group(1)
                    comment_date = header.group(2)
                    block_start = header.start()
                else:
                    break

            tail = comments_text[match.end() :]
            end_offset = len(tail)
            next_header = EPRINT_COMMENT_HEADER_RE.search(tail)
            if next_header:
                end_offset = next_header.start()
            block = comments_text[block_start : match.end() + end_offset]
            blocks.append((comment_num, comment_date, block))

        return blocks

    def _parse_block(
        self,
        block: str,
        incident: str,
        kind: str,
        comment_num: str,
        comment_date: str,
    ) -> Optional[DeliverableVersion]:
        eeb_version_match = EEB_VERSION_RE.search(block)
        product_match = re.search(
            r"This EEB is built for Product version\s*:\s*(.+)$",
            block,
            re.MULTILINE,
        )
        primary_match = re.search(
            r"Service request's primary:\s*(\d+)",
            block,
        )
        submission_match = re.search(
            r"Submission Type:\s*(.+)$",
            block,
            re.MULTILINE,
        )
        install_on_match = re.search(
            r"Install on:\s*(.+)$",
            block,
            re.MULTILINE,
        )
        if not eeb_version_match:
            return None

        eeb_version = int(eeb_version_match.group(1))
        if kind == "eeb-pkg":
            constituents = self._parse_pkg_constituents(block)
        elif kind == "bundle":
            constituents = self._parse_bundle_constituents(block, incident=incident)
        else:
            constituents = [
                ConstituentRef(
                    incident=incident,
                    embedded_version=eeb_version,
                )
            ]

        readme_notes = self._extract_section(block, "Readme Notes:")
        problem_description = self._extract_section(block, "Problem Description:")

        return DeliverableVersion(
            kind=kind,
            incident=incident,
            eeb_version=eeb_version,
            product_version=(product_match.group(1).strip() if product_match else ""),
            primary=(primary_match.group(1) if primary_match else ""),
            comment_num=comment_num,
            comment_date=comment_date,
            constituents=constituents,
            artifacts=self._parse_artifacts(block),
            platform_packages=self._dedupe_platform_packages(
                self._parse_platform_packages(block)
            ),
            links=self._parse_links(block),
            readme_notes=readme_notes,
            problem_description=problem_description,
            submission_type=(
                submission_match.group(1).strip() if submission_match else ""
            ),
            install_on=(install_on_match.group(1).strip() if install_on_match else ""),
        )

    def _parse_pkg_constituents(self, block: str) -> List[ConstituentRef]:
        constituents: List[ConstituentRef] = []
        seen: Set[str] = set()
        for match in EEB_CONSTITUENT_RE.finditer(block):
            incident = match.group(1)
            if incident in seen:
                continue
            seen.add(incident)
            constituents.append(
                ConstituentRef(
                    incident=incident,
                    embedded_version=int(match.group(2)),
                )
            )
        return constituents

    @staticmethod
    def _sanitize_text_for_incident_scan(text: str) -> str:
        cleaned = re.sub(r"pid=\d+", " ", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"https?://\S+", " ", cleaned)
        return cleaned

    @classmethod
    def _extract_readme_extra_incidents(
        cls,
        section: str,
        *,
        exclude: Set[str],
    ) -> List[str]:
        """Extract ETs referenced as line headers: '4220256: description...'."""
        if not section:
            return []

        extras: List[str] = []
        seen: Set[str] = set()
        cleaned = cls._sanitize_text_for_incident_scan(section)

        for match in re.finditer(r"(?m)^\s*(\d{6,7})\s*:", cleaned):
            token = match.group(1)
            if token in exclude or token in seen:
                continue
            seen.add(token)
            extras.append(token)

        return extras

    def _parse_bundle_constituents(
        self,
        block: str,
        incident: str = "",
    ) -> List[ConstituentRef]:
        bundle_list: List[ConstituentRef] = []
        extras: List[ConstituentRef] = []
        seen_in_bundle: Set[str] = set()
        seen_all: Set[str] = set()

        list_match = re.search(
            r"The bundle contains the following Etracks:\s*(.*?)(?:\n\s*\n|\nCompleted Testing Steps:)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        if list_match:
            for match in ET_CONSTITUENT_RE.finditer(list_match.group(1)):
                incident_id = match.group(1)
                if incident_id not in seen_in_bundle:
                    seen_in_bundle.add(incident_id)
                    seen_all.add(incident_id)
                    bundle_list.append(
                        ConstituentRef(
                            incident=incident_id,
                            in_bundle_contains=True,
                        )
                    )

        exclude = set(seen_all)
        if incident:
            exclude.add(incident)

        for section in (
            self._extract_section_raw(block, "Readme Notes:"),
            self._extract_section_raw(block, "Problem Description:"),
        ):
            for token in self._extract_readme_extra_incidents(section, exclude=exclude):
                if token in seen_all:
                    continue
                seen_all.add(token)
                exclude.add(token)
                extras.append(
                    ConstituentRef(
                        incident=token,
                        in_bundle_contains=False,
                    )
                )

        return bundle_list + extras

    @staticmethod
    def _dedupe_platform_packages(
        packages: List[PlatformPackage],
    ) -> List[PlatformPackage]:
        deduped: List[PlatformPackage] = []
        seen: Set[Tuple[str, str]] = set()
        for package in packages:
            key = (package.platform, package.package_name)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(package)
        return deduped

    def _parse_artifacts(self, block: str) -> List[ArtifactRow]:
        artifacts: List[ArtifactRow] = []
        for line in block.splitlines():
            match = ARTIFACT_LINE_RE.match(line.strip())
            if not match:
                continue
            platform = match.group(3).rstrip("/")
            artifacts.append(
                ArtifactRow(
                    checksum=match.group(1),
                    size=match.group(2),
                    platform=platform,
                    filename=match.group(4),
                )
            )
        return artifacts

    def _parse_platform_packages(self, block: str) -> List[PlatformPackage]:
        packages: List[PlatformPackage] = []
        seen: Set[Tuple[str, str]] = set()

        for match in re.finditer(
            r"Secure file (\S+)\s*\n\s+(NetBackup_\S+)",
            block,
        ):
            secure_file = match.group(1)
            package_name = match.group(2)
            key = (secure_file.split("/", 1)[0], package_name)
            if key in seen:
                continue
            seen.add(key)
            packages.append(
                PlatformPackage(
                    secure_file=secure_file,
                    package_name=package_name,
                )
            )

        for match in re.finditer(r"Secure file (\S+/)([^\s\n]+)", block):
            platform = match.group(1).rstrip("/")
            filename = match.group(2)
            secure_file = f"{platform}/{filename}"
            key = (platform, filename)
            if key in seen:
                continue
            seen.add(key)
            packages.append(
                PlatformPackage(
                    secure_file=secure_file,
                    package_name=filename,
                )
            )

        return packages

    def _parse_links(self, block: str) -> Dict[str, str]:
        links: Dict[str, str] = {}
        for url in URL_RE.findall(block):
            lower = url.lower()
            if "retrieve.php" in lower:
                links.setdefault("retrieve", url)
            elif "changesets/" in lower:
                links.setdefault("changeset", url)
            elif "view_cksum.php" in lower:
                links.setdefault("checksum", url)
            elif "stash.veritas.com" in lower and "compare/diff" in lower:
                links.setdefault("stash_diff", url)
            elif "stash.veritas.com" in lower and "pull-requests" in lower:
                links.setdefault("review", url)
            else:
                links.setdefault("other", url)
        return links

    @staticmethod
    def _extract_section_raw(block: str, heading: str) -> str:
        match = re.search(
            rf"{re.escape(heading)}\s*(.*?)(?:\n[A-Z][A-Za-z /']+:|$)",
            block,
            re.DOTALL,
        )
        if not match:
            return ""
        return match.group(1)

    @staticmethod
    def _extract_section(block: str, heading: str) -> str:
        raw = TrencherDeliverableParser._extract_section_raw(block, heading)
        if not raw:
            return ""
        return " ".join(raw.split())


def _format_chunked_list(
    items: Sequence[str],
    prefix: str,
    per_line: int = 7,
    continuation_indent: str = "         ",
) -> List[str]:
    if not items:
        return []
    lines: List[str] = []
    for index in range(0, len(items), per_line):
        chunk = ", ".join(items[index : index + per_line])
        if index == 0:
            lines.append(f"{prefix}{chunk}")
        else:
            lines.append(f"{continuation_indent}{chunk}")
    return lines


def _parse_artifact_size_bytes(size_str: str) -> int:
    try:
        return int(str(size_str).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _format_artifact_size(total_bytes: int) -> str:
    if total_bytes <= 0:
        return "-"
    for unit, divisor in (
        ("TB", 1024**4),
        ("GB", 1024**3),
        ("MB", 1024**2),
        ("KB", 1024),
        ("B", 1),
    ):
        if total_bytes >= divisor or unit == "B":
            value = total_bytes / divisor
            if unit == "B":
                return f"{total_bytes:,}{unit}"
            return f"{value:.1f}{unit}"
    return str(total_bytes)


def _classify_artifact_filename(filename: str) -> str:
    lower = filename.lower()
    if "eebinstaller_" in lower:
        return "eebinstaller"
    if lower.startswith("nbapp_eeb_et"):
        return "rpm"
    if "index" in lower:
        return "index"
    if any(
        token in lower
        for token in (
            "install_failure",
            "install_verify",
            "post_uninstall",
            "preprocess_install",
            "install-",
        )
    ):
        return "install-script"
    if lower.endswith(".war"):
        return "war"
    if lower.endswith(".exe"):
        return "exe"
    if lower.endswith(".rpm"):
        return "rpm"
    return "other"


def _summarize_artifact_types(type_counts: Counter) -> str:
    if not type_counts:
        return "-"
    parts = [
        f"{kind}×{count}" if count > 1 else kind
        for kind, count in sorted(type_counts.items())
    ]
    text = ", ".join(parts)
    if len(text) > 44:
        return text[:41] + "..."
    return text


_PLATFORM_SORT_ORDER = ("AMD64", "linuxR_x86", "linuxS_x86")

_PLATFORM_PACKAGE_TYPE_SORT = {
    "primary-set": 0,
    "war": 1,
    "install-script": 2,
    "jar": 3,
    "other": 4,
}


def _sort_platforms(platforms: Set[str]) -> List[str]:
    order = {platform: index for index, platform in enumerate(_PLATFORM_SORT_ORDER)}
    return sorted(platforms, key=lambda platform: (order.get(platform, 99), platform))


def _format_platform_coverage(platforms: Set[str], all_platforms: Set[str]) -> str:
    if platforms == all_platforms and len(all_platforms) > 1:
        return f"all ({len(all_platforms)})"
    linux_only = {"linuxR_x86", "linuxS_x86"}
    if platforms == linux_only:
        return "linux×2"
    text = ", ".join(_sort_platforms(platforms))
    if len(text) > 40:
        return text[:37] + "..."
    return text


def _classify_platform_package(name: str) -> str:
    lower = name.lower()
    if lower.startswith("netbackup_") and ("_eeb" in lower or "_set" in lower):
        return "primary-set"
    if lower.endswith(".war"):
        return "war"
    if lower.endswith(".jar"):
        return "jar"
    if lower.endswith(".exe") or lower.endswith(".sh"):
        return "install-script"
    if any(
        token in lower
        for token in (
            "install_failure",
            "install_verify",
            "post_uninstall",
            "preprocess_install",
            "install-",
        )
    ):
        return "install-script"
    return "other"


class DeliverableReporter:
    PKG_SR_DETAIL_COLUMNS = [
        "ET",
        "EMBEDDED",
        "LATEST",
        "STATUS",
        "TYPE",
        "STATE",
        "VERSION",
        "TARGET_VERSION",
        "RESOLUTION",
        "ASSIGNED_TO",
        "ABSTRACT",
    ]
    PKG_CONSTITUENT_COLUMNS = PKG_SR_DETAIL_COLUMNS  # backward-compatible alias
    BUNDLE_SR_DETAIL_COLUMNS = [
        "ET",
        "SOURCE",
        "LATEST_EEB",
        "TYPE",
        "STATE",
        "VERSION",
        "TARGET_VERSION",
        "RESOLUTION",
        "ASSIGNED_TO",
        "ABSTRACT",
    ]
    BUNDLE_CONSTITUENT_COLUMNS = BUNDLE_SR_DETAIL_COLUMNS  # backward-compatible alias

    def render(
        self,
        versions: List[DeliverableVersion],
        enriched: Dict[str, Dict[str, str]],
        latest_versions: Dict[str, Optional[int]],
        include_details: bool = False,
        full_details: bool = False,
        stale_only: bool = False,
    ) -> str:
        sections: List[str] = []
        for version in versions:
            sections.append(
                self._render_version(
                    version,
                    enriched,
                    latest_versions,
                    include_details=include_details,
                    full_details=full_details,
                    stale_only=stale_only,
                )
            )
        return "\n".join(sections)

    def render_hints(
        self,
        incident: str,
        versions_by_kind: Dict[str, List[DeliverableVersion]],
    ) -> str:
        if not versions_by_kind:
            return ""

        present_kinds = [
            kind for kind in DELIVERABLE_KINDS if kind in versions_by_kind
        ]
        kind_label = " + ".join(
            deliverable_kind_label(kind) for kind in present_kinds
        )
        if len(present_kinds) == 1:
            only = present_kinds[0]
            if only == "eeb-pkg":
                suggest = "-P"
            elif only == "bundle":
                suggest = "-B"
            else:
                suggest = "-C"
        else:
            suggest = "-A"

        has_bundle = "bundle" in versions_by_kind
        hint_rows: List[Dict[str, str]] = []
        for kind in DELIVERABLE_KINDS:
            for version in versions_by_kind.get(kind, []):
                comment_date = version.comment_date.split()[0] if version.comment_date else "?"
                row: Dict[str, str] = {
                    "TYPE": deliverable_kind_hint_code(kind),
                    "VER": str(version.eeb_version),
                    "COMMENT": f"#{version.comment_num} {comment_date}",
                    "PRODUCT": version.product_version,
                    "PRIMARY": version.primary,
                    "ETs": str(len(version.constituents)),
                }
                if has_bundle:
                    if kind == "bundle":
                        in_bundle = sum(
                            1 for c in version.constituents if c.in_bundle_contains
                        )
                        row["BUNDLE"] = str(in_bundle)
                        row["README*"] = str(len(version.constituents) - in_bundle)
                    else:
                        row["BUNDLE"] = ""
                        row["README*"] = ""
                hint_rows.append(row)

        columns = ["TYPE", "VER", "COMMENT", "PRODUCT", "PRIMARY", "ETs"]
        if has_bundle:
            columns.extend(["BUNDLE", "README*"])

        renderer = TableRenderer(columns)
        renderer.widths.update(
            {
                "TYPE": 9,
                "VER": 4,
                "COMMENT": 18,
                "PRODUCT": 20,
                "PRIMARY": 10,
                "ETs": 4,
                "BUNDLE": 7,
                "README*": 8,
            }
        )

        lines = [
            f"\n{'=' * 72}",
            f"DELIVERABLE SUMMARY — ET {incident} ({kind_label})",
            f"Full report: re-run with {suggest}",
            f"{'=' * 72}",
            renderer.render_with_count(hint_rows),
        ]

        if "eeb-pkg" in versions_by_kind:
            for version in versions_by_kind.get("eeb-pkg", []):
                if not version.constituents:
                    continue
                embedded = [
                    f"{c.incident}(v{c.embedded_version})"
                    if c.embedded_version is not None
                    else c.incident
                    for c in version.constituents
                ]
                lines.extend(
                    _format_chunked_list(
                        embedded,
                        prefix=f"v{version.eeb_version} SRs in package: ",
                    )
                )

        if "bundle" in versions_by_kind:
            for version in versions_by_kind.get("bundle", []):
                in_bundle = [
                    c.incident
                    for c in version.constituents
                    if c.in_bundle_contains
                ]
                if in_bundle:
                    lines.extend(
                        _format_chunked_list(
                            in_bundle,
                            prefix=f"v{version.eeb_version} SRs in bundle: ",
                        )
                    )

        return "\n".join(lines)

    def _render_version(
        self,
        version: DeliverableVersion,
        enriched: Dict[str, Dict[str, str]],
        latest_versions: Dict[str, Optional[int]],
        include_details: bool = False,
        full_details: bool = False,
        stale_only: bool = False,
    ) -> str:
        title = deliverable_kind_label(version.kind)
        lines = [
            f"\n{'=' * 88}",
            f"{title} REPORT - ET {version.incident} - EEB v{version.eeb_version}",
            f"Comment #{version.comment_num} @ {version.comment_date}",
            f"{'=' * 88}",
            self._render_summary_table(version, enriched),
        ]

        if version.kind == "eeb-pkg":
            lines.append(
                self._render_constituent_table(
                    version,
                    enriched,
                    latest_versions,
                    self.PKG_SR_DETAIL_COLUMNS,
                    include_embedded=True,
                    stale_only=stale_only,
                )
            )
            lines.append(
                self._render_status_summary(
                    version,
                    latest_versions,
                    stale_only=stale_only,
                )
            )
        elif version.kind == "bundle":
            lines.append(
                self._render_constituent_table(
                    version,
                    enriched,
                    latest_versions,
                    self.BUNDLE_SR_DETAIL_COLUMNS,
                    include_embedded=False,
                    stale_only=False,
                )
            )

        if include_details:
            shipping_rows: Optional[List[Dict[str, str]]] = None
            if version.kind in ("eeb-pkg", "bundle") and version.artifacts:
                shipping_rows = self._build_sr_shipping_rows(version)
                lines.append(
                    self._render_sr_shipping_details(
                        version,
                        shipping_rows=shipping_rows,
                        full_details=full_details,
                    )
                )

            if version.platform_packages:
                lines.append(
                    self._render_platform_packages(version, full_details=full_details)
                )

            if version.links:
                lines.append(self._render_links(version))

            if version.artifacts:
                lines.append(
                    self._render_artifacts(
                        version,
                        shipping_rows=shipping_rows,
                        full_details=full_details,
                    )
                )

        return "\n".join(lines)

    def _render_summary_table(
        self,
        version: DeliverableVersion,
        enriched: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        enriched = enriched or {}
        if version.kind == "eeb-pkg":
            service_label = "Package ET"
        elif version.kind == "bundle":
            service_label = "Bundle ET"
        else:
            service_label = "Service ET"

        rows = [
            {"FIELD": "Deliverable Type", "VALUE": deliverable_kind_label(version.kind)},
            {"FIELD": service_label, "VALUE": version.incident},
            {"FIELD": "Primary/Super", "VALUE": version.primary},
            {"FIELD": "Product Version", "VALUE": version.product_version},
            {"FIELD": "EEB Version", "VALUE": str(version.eeb_version)},
        ]

        if version.kind == "eeb-standard":
            if version.submission_type:
                rows.append({"FIELD": "Submission Type", "VALUE": version.submission_type})
            if version.install_on:
                rows.append({"FIELD": "Install On", "VALUE": version.install_on})
            details = enriched.get(version.incident, {})
            if details:
                rows.extend(
                    [
                        {"FIELD": "TYPE", "VALUE": details.get("TYPE", "")},
                        {"FIELD": "STATE", "VALUE": details.get("STATE", "")},
                        {"FIELD": "VERSION", "VALUE": details.get("VERSION", "")},
                    ]
                )
        else:
            label = (
                "Service Requests"
                if version.kind in ("eeb-pkg", "bundle")
                else "Constituents"
            )
            rows.append({"FIELD": label, "VALUE": str(len(version.constituents))})

        if version.kind == "bundle":
            in_bundle = sum(1 for c in version.constituents if c.in_bundle_contains)
            extras = len(version.constituents) - in_bundle
            rows.append({"FIELD": "In bundle contains", "VALUE": str(in_bundle)})
            rows.append({"FIELD": "Extra (readme/desc)", "VALUE": str(extras)})

        rows.extend(
            [
                {
                    "FIELD": "Problem Description",
                    "VALUE": version.problem_description[:120],
                },
                {"FIELD": "Readme Notes", "VALUE": version.readme_notes[:120]},
            ]
        )
        renderer = TableRenderer(["FIELD", "VALUE"])
        renderer.widths["FIELD"] = 20
        renderer.widths["VALUE"] = 64
        return "\nSUMMARY:\n" + renderer.render_with_count(rows)

    def _render_constituent_table(
        self,
        version: DeliverableVersion,
        enriched: Dict[str, Dict[str, str]],
        latest_versions: Dict[str, Optional[int]],
        columns: List[str],
        include_embedded: bool,
        stale_only: bool = False,
    ) -> str:
        rows: List[Dict[str, str]] = []
        for constituent in version.constituents:
            details = enriched.get(constituent.incident, {})
            latest = latest_versions.get(constituent.incident)
            row = {
                "ET": constituent.incident,
                "TYPE": details.get("TYPE", ""),
                "STATE": details.get("STATE", ""),
                "VERSION": details.get("VERSION", ""),
                "TARGET_VERSION": details.get("TARGET_VERSION", ""),
                "RESOLUTION": details.get("RESOLUTION", ""),
                "ASSIGNED_TO": details.get("ASSIGNED_TO", ""),
                "ABSTRACT": details.get("ABSTRACT", ""),
            }
            if include_embedded:
                embedded = constituent.embedded_version
                row["EMBEDDED"] = str(embedded) if embedded is not None else ""
                row["LATEST"] = str(latest) if latest is not None else ""
                status = self._version_status(embedded, latest)
                row["STATUS"] = status
                if stale_only and not status.startswith("STALE"):
                    continue
            else:
                row["LATEST_EEB"] = str(latest) if latest is not None else ""
                if version.kind == "bundle":
                    row["SOURCE"] = (
                        "BUNDLE" if constituent.in_bundle_contains else "README*"
                    )
            rows.append(row)

        renderer = TableRenderer(columns)
        renderer.widths["ABSTRACT"] = 80
        renderer.widths["ASSIGNED_TO"] = 18
        renderer.widths["RESOLUTION"] = 16
        renderer.widths["TARGET_VERSION"] = 12
        if version.kind == "bundle":
            renderer.widths["SOURCE"] = 8
        title = (
            "SR DETAILS (SERVICE REQUESTS IN PACKAGE):"
            if version.kind == "eeb-pkg"
            else "SR DETAILS (SERVICE REQUESTS IN BUNDLE):"
            if version.kind == "bundle"
            else "CONSTITUENT ETRACKS:"
        )
        if stale_only and not rows:
            return f"\n{title}\n(no stale constituents for this version)\nTotal rows: 0"

        output = f"\n{title}\n" + renderer.render_with_count(rows)
        if version.kind == "bundle":
            extras = [
                constituent.incident
                for constituent in version.constituents
                if not constituent.in_bundle_contains
            ]
            if extras:
                output += (
                    "\nNote: SOURCE=README* means ET appears only in Problem "
                    "Description/Readme Notes, NOT in the trusted 'bundle contains' "
                    f"list: {', '.join(extras)}"
                )
        return output

    def _render_status_summary(
        self,
        version: DeliverableVersion,
        latest_versions: Dict[str, Optional[int]],
        stale_only: bool = False,
    ) -> str:
        current = 0
        stale = 0
        unknown = 0
        newer = 0
        stale_items: List[str] = []

        for constituent in version.constituents:
            latest = latest_versions.get(constituent.incident)
            status = self._version_status(constituent.embedded_version, latest)
            if status == "CURRENT":
                current += 1
            elif status.startswith("STALE"):
                stale += 1
                stale_items.append(
                    f"{constituent.incident} v{constituent.embedded_version}"
                    f"→latest v{latest}"
                )
            elif status.startswith("NEWER"):
                newer += 1
            else:
                unknown += 1

        summary = (
            f"VERSION SUMMARY: {current} CURRENT, {stale} STALE, "
            f"{unknown} UNKNOWN, {newer} NEWER"
        )
        if stale_items:
            summary += f" | Stale: {', '.join(stale_items)}"
        if stale_only:
            summary += " | (filtered to STALE only)"
        return f"\n{summary}\n"

    @staticmethod
    def _version_status(
        embedded: Optional[int],
        latest: Optional[int],
    ) -> str:
        if embedded is None or latest is None:
            return "UNKNOWN"
        if embedded == latest:
            return "CURRENT"
        if embedded < latest:
            return f"STALE (+{latest - embedded})"
        return f"NEWER ({embedded}>{latest})"

    @staticmethod
    def _artifact_sr_label(
        artifact: ArtifactRow,
        package_et: str,
        constituent_ids: Sequence[str],
        deliverable_kind: str = "eeb-pkg",
    ) -> str:
        """Map a shipping artifact filename to a constituent ET or bundle/package ET."""
        filename = artifact.filename.upper()
        for incident in constituent_ids:
            token = incident.upper()
            if (
                f"_{token}_" in filename
                or f"ET{token}" in filename
                or filename.startswith(f"{token}.")
            ):
                return incident
        if package_et in artifact.filename:
            prefix = "BUNDLE" if deliverable_kind == "bundle" else "PKG"
            return f"{prefix}/{package_et}"
        if deliverable_kind == "bundle":
            return f"BUNDLE/{package_et}"
        return "?"

    def _build_sr_shipping_rows(self, version: DeliverableVersion) -> List[Dict[str, str]]:
        constituent_ids = [c.incident for c in version.constituents]
        rows: List[Dict[str, str]] = []
        for artifact in version.artifacts:
            rows.append(
                {
                    "SR": self._artifact_sr_label(
                        artifact,
                        version.incident,
                        constituent_ids,
                        deliverable_kind=version.kind,
                    ),
                    "PLATFORM": artifact.platform,
                    "FILE": artifact.filename,
                    "SIZE": artifact.size,
                    "CHECKSUM": artifact.checksum,
                }
            )
        rows.sort(key=lambda row: (row["SR"], row["PLATFORM"], row["FILE"]))
        return rows

    def _sr_shipping_heading(self, version: DeliverableVersion) -> str:
        if version.kind == "bundle":
            return (
                "SR SHIPPING (binaries in bundle; shared files labeled "
                f"BUNDLE/{version.incident}):"
            )
        return "SR SHIPPING (binaries per service request in package):"

    def _render_sr_shipping_summary(self, rows: List[Dict[str, str]]) -> str:
        by_sr: Dict[str, List[Dict[str, str]]] = {}
        for row in rows:
            by_sr.setdefault(row["SR"], []).append(row)

        summary_rows: List[Dict[str, str]] = []
        for sr in sorted(by_sr.keys()):
            sr_rows = by_sr[sr]
            platforms = sorted({row["PLATFORM"] for row in sr_rows})
            total_bytes = sum(_parse_artifact_size_bytes(row["SIZE"]) for row in sr_rows)
            type_counts = Counter(
                _classify_artifact_filename(row["FILE"]) for row in sr_rows
            )
            summary_rows.append(
                {
                    "SR": sr,
                    "PLATFORMS": ", ".join(platforms),
                    "FILES": str(len(sr_rows)),
                    "TOTAL_SIZE": _format_artifact_size(total_bytes),
                    "ARTIFACT_TYPES": _summarize_artifact_types(type_counts),
                }
            )

        renderer = TableRenderer(
            ["SR", "PLATFORMS", "FILES", "TOTAL_SIZE", "ARTIFACT_TYPES"]
        )
        renderer.widths.update(
            {
                "SR": 14,
                "PLATFORMS": 40,
                "FILES": 5,
                "TOTAL_SIZE": 10,
                "ARTIFACT_TYPES": 44,
            }
        )
        return "SR SHIPPING SUMMARY:\n" + renderer.render_with_count(summary_rows)

    def _render_sr_shipping_details(
        self,
        version: DeliverableVersion,
        shipping_rows: Optional[List[Dict[str, str]]] = None,
        full_details: bool = False,
    ) -> str:
        rows = shipping_rows if shipping_rows is not None else self._build_sr_shipping_rows(version)
        parts = [f"\n{self._sr_shipping_heading(version)}", self._render_sr_shipping_summary(rows)]

        show_full = full_details or len(rows) <= DELIVERABLE_FULL_DETAIL_ROW_LIMIT
        if show_full:
            renderer = TableRenderer(["SR", "PLATFORM", "FILE", "SIZE", "CHECKSUM"])
            renderer.widths["SR"] = 14
            renderer.widths["FILE"] = 48
            parts.append("\nSR SHIPPING DETAILS (full):\n" + renderer.render_with_count(rows))
        elif rows:
            parts.append(
                f"(Full listing: {len(rows)} rows; use --full-deliverable-details to show all)"
            )
        return "\n".join(parts)

    def _build_platform_package_full_rows(
        self, version: DeliverableVersion
    ) -> List[Dict[str, str]]:
        return [
            {
                "PLATFORM": package.platform,
                "PACKAGE_NAME": package.package_name,
            }
            for package in TrencherDeliverableParser._dedupe_platform_packages(
                version.platform_packages
            )
        ]

    def _build_platform_package_summary_rows(
        self, full_rows: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        by_name: Dict[str, Set[str]] = {}
        for row in full_rows:
            by_name.setdefault(row["PACKAGE_NAME"], set()).add(row["PLATFORM"])

        all_platforms: Set[str] = set()
        for platforms in by_name.values():
            all_platforms |= platforms

        summary_rows: List[Dict[str, str]] = []
        for name in by_name:
            platforms = by_name[name]
            summary_rows.append(
                {
                    "PACKAGE_NAME": name,
                    "TYPE": _classify_platform_package(name),
                    "PLATFORMS": _format_platform_coverage(platforms, all_platforms),
                }
            )

        summary_rows.sort(
            key=lambda row: (
                _PLATFORM_PACKAGE_TYPE_SORT.get(row["TYPE"], 99),
                row["PACKAGE_NAME"],
            )
        )
        return summary_rows

    def _render_platform_packages_summary(
        self, summary_rows: List[Dict[str, str]]
    ) -> str:
        renderer = TableRenderer(["PACKAGE_NAME", "TYPE", "PLATFORMS"])
        renderer.widths.update(
            {
                "PACKAGE_NAME": 48,
                "TYPE": 14,
                "PLATFORMS": 12,
            }
        )
        return "PLATFORM PACKAGES SUMMARY:\n" + renderer.render_with_count(summary_rows)

    def _render_platform_packages(
        self, version: DeliverableVersion, full_details: bool = False
    ) -> str:
        full_rows = self._build_platform_package_full_rows(version)
        summary_rows = self._build_platform_package_summary_rows(full_rows)
        unique_count = len(summary_rows)
        parts = [
            f"\nPLATFORM PACKAGES ({unique_count} unique packages, "
            f"{len(full_rows)} platform entries):",
            self._render_platform_packages_summary(summary_rows),
        ]

        show_full = full_details or len(full_rows) <= DELIVERABLE_FULL_DETAIL_ROW_LIMIT
        if show_full:
            renderer = TableRenderer(["PLATFORM", "PACKAGE_NAME"])
            renderer.widths["PACKAGE_NAME"] = 48
            parts.append(
                "\nPLATFORM PACKAGES (full):\n" + renderer.render_with_count(full_rows)
            )
        elif full_rows:
            parts.append(
                f"(Full listing: {len(full_rows)} rows; "
                "use --full-deliverable-details to show all)"
            )
        return "\n".join(parts)

    def _render_links(self, version: DeliverableVersion) -> str:
        rows = [{"TYPE": key.upper(), "URL": url} for key, url in version.links.items()]
        renderer = TableRenderer(["TYPE", "URL"])
        renderer.widths["URL"] = 72
        return "\nLINKS:\n" + renderer.render_with_count(rows)

    def _render_artifacts_summary(
        self,
        version: DeliverableVersion,
        shipping_rows: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        if shipping_rows is None:
            shipping_rows = self._build_sr_shipping_rows(version)

        by_platform: Dict[str, List[Dict[str, str]]] = {}
        for row in shipping_rows:
            by_platform.setdefault(row["PLATFORM"], []).append(row)

        summary_rows: List[Dict[str, str]] = []
        for platform in sorted(by_platform.keys()):
            platform_rows = by_platform[platform]
            total_bytes = sum(
                _parse_artifact_size_bytes(row["SIZE"]) for row in platform_rows
            )
            type_counts = Counter(
                _classify_artifact_filename(row["FILE"]) for row in platform_rows
            )
            summary_rows.append(
                {
                    "PLATFORM": platform,
                    "FILES": str(len(platform_rows)),
                    "SRs": str(len({row["SR"] for row in platform_rows})),
                    "TOTAL_SIZE": _format_artifact_size(total_bytes),
                    "ARTIFACT_TYPES": _summarize_artifact_types(type_counts),
                }
            )

        renderer = TableRenderer(
            ["PLATFORM", "FILES", "SRs", "TOTAL_SIZE", "ARTIFACT_TYPES"]
        )
        renderer.widths.update(
            {
                "PLATFORM": 12,
                "FILES": 5,
                "SRs": 4,
                "TOTAL_SIZE": 10,
                "ARTIFACT_TYPES": 44,
            }
        )
        return "\nARTIFACTS SUMMARY:\n" + renderer.render_with_count(summary_rows)

    def _render_artifacts(
        self,
        version: DeliverableVersion,
        shipping_rows: Optional[List[Dict[str, str]]] = None,
        full_details: bool = False,
    ) -> str:
        rows = [
            {
                "PLATFORM": artifact.platform,
                "FILE": artifact.filename,
                "SIZE": artifact.size,
                "CHECKSUM": artifact.checksum,
            }
            for artifact in version.artifacts
        ]
        parts = [self._render_artifacts_summary(version, shipping_rows=shipping_rows)]

        show_full = full_details or len(rows) <= DELIVERABLE_FULL_DETAIL_ROW_LIMIT
        if show_full:
            renderer = TableRenderer(["PLATFORM", "FILE", "SIZE", "CHECKSUM"])
            renderer.widths["FILE"] = 48
            parts.append("\nARTIFACTS (full):\n" + renderer.render_with_count(rows))
        elif rows:
            parts.append(
                f"(Full listing: {len(rows)} rows; use --full-deliverable-details to show all)"
            )
        return "\n".join(parts)


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

    def render_with_count(self, rows: List[Dict[str, str]]) -> str:
        return f"{self.render(rows)}\nTotal rows: {len(rows)}"


class EtrackHierarchyFetcher:
    def __init__(
        self,
        ssh_target: Optional[str] = None,
        verbose: bool = False,
        debug: bool = False,
        quiet: bool = False,
        command_timeout: int = 20,
        deliverable_parallel: int = DEFAULT_DELIVERABLE_PARALLEL,
        ssh_multiplex: bool = True,
        max_retries: int = DEFAULT_COMMAND_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        self.ssh_target = ssh_target
        self.verbose = verbose
        self.debug = debug
        self.quiet = quiet
        self.command_timeout = command_timeout
        self.deliverable_parallel = max(1, deliverable_parallel)
        self.ssh_multiplex = ssh_multiplex
        self.max_retries = max(0, max_retries)
        self.retry_delay = max(0.0, retry_delay)
        self._ssh_multiplex_disabled = False
        self._details_cache: Dict[str, str] = {}
        self._parsed_details_cache: Dict[str, Dict[str, str]] = {}
        self._comments_cache: Dict[str, str] = {}
        self._latest_eeb_version_cache: Dict[str, Optional[int]] = {}
        self._query_count = 0

    def _ssh_multiplex_active(self) -> bool:
        return bool(
            self.ssh_target
            and self.ssh_multiplex
            and not self._ssh_multiplex_disabled
        )

    def _ssh_control_path(self) -> str:
        assert self.ssh_target is not None
        digest = hashlib.sha256(self.ssh_target.encode("utf-8")).hexdigest()[:16]
        cache_dir = os.path.join(
            os.path.expanduser("~"),
            ".cache",
            "etrack_hierarchy_table",
        )
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"ssh-{digest}")

    def _ssh_options(self, for_close: bool = False) -> List[str]:
        options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
        use_multiplex = for_close or self._ssh_multiplex_active()
        if self.ssh_target and self.ssh_multiplex and use_multiplex:
            options.extend(
                [
                    "-o",
                    "ControlMaster=auto",
                    "-o",
                    f"ControlPath={self._ssh_control_path()}",
                    "-o",
                    "ControlPersist=300",
                ]
            )
        return options

    def _ssh_command_prefix(self) -> List[str]:
        if not self.ssh_target:
            return []
        return ["ssh", *self._ssh_options(), self.ssh_target]

    def _recover_ssh_multiplex(self) -> None:
        if self.debug:
            print(
                "[WARN] Stale SSH multiplex socket; resetting connection...",
                file=sys.stderr,
            )
        self.close_ssh()
        self._ssh_multiplex_disabled = True

    def close_ssh(self) -> None:
        if not self.ssh_target or not self.ssh_multiplex:
            return
        subprocess.run(
            [
                "ssh",
                *self._ssh_options(for_close=True),
                "-O",
                "exit",
                self.ssh_target,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def _run_subprocess(
        self,
        cmd: Sequence[str],
        *,
        timeout: int,
        input_data: Optional[bytes] = None,
        allow_failure: bool = False,
        acceptable_returncodes: Tuple[int, ...] = (0,),
        error_label: str = "Command",
        context: Optional[str] = None,
        retry_on_timeout: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        last_detail = ""
        last_category = "unknown"

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                delay = self.retry_delay * (2 ** (attempt - 1))
                if not self.quiet:
                    print(
                        f"[WARN] {error_label} transient failure "
                        f"(retry {attempt}/{self.max_retries}, timeout={timeout}s): "
                        f"{last_detail}",
                        file=sys.stderr,
                    )
                    print(
                        f"       Retrying in {delay:.0f}s... "
                        f"(increase --timeout / -T if this persists)",
                        file=sys.stderr,
                    )
                time.sleep(delay)

            try:
                result = subprocess.run(
                    list(cmd),
                    input=input_data,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                last_detail = f"timed out after {timeout}s"
                last_category = "timeout"
                if retry_on_timeout and attempt < self.max_retries:
                    continue
                raise CommandTimeoutError(
                    format_command_error(
                        error_label,
                        self.ssh_target,
                        last_detail,
                        "timeout",
                        context=context,
                    )
                ) from exc
            except OSError as exc:
                last_detail = str(exc)
                last_category = "network"
                if attempt < self.max_retries and self.ssh_target:
                    continue
                raise EtrackHierarchyError(
                    format_command_error(
                        error_label,
                        self.ssh_target,
                        last_detail,
                        last_category,
                        context=context,
                    )
                ) from exc

            if result.returncode in acceptable_returncodes or allow_failure:
                return result

            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            last_detail = stderr or stdout or f"exit code {result.returncode}"
            last_category, retryable = classify_command_error(
                last_detail,
                result.returncode,
            )

            if last_category == "multiplex" and retryable:
                self._recover_ssh_multiplex()
                if attempt < self.max_retries:
                    continue

            if retryable and attempt < self.max_retries:
                continue

            raise EtrackHierarchyError(
                format_command_error(
                    error_label,
                    self.ssh_target,
                    last_detail,
                    last_category,
                    context=context,
                )
            )

        raise EtrackHierarchyError(
            format_command_error(
                error_label,
                self.ssh_target,
                last_detail or "unknown error",
                last_category,
                context=context,
            )
        )

    def _resolve_esql_command(self) -> List[str]:
        if self.ssh_target:
            return self._ssh_command_prefix() + ["esql"]

        local_esql = shutil.which("esql")
        if local_esql:
            return [local_esql]

        raise EtrackHierarchyError(
            "esql command not found locally. Install esql, use -R/--ssh user@host, "
            "or set ETRACK_SSH / ENGVM_HOST / NIS_USER+NIS_SERVER for auto-SSH."
        )

    def _run_esql(self, sql: str) -> str:
        cmd = self._resolve_esql_command()
        self._query_count += 1
        if not self.quiet and not self.debug:
            print(f"[ESQL #{self._query_count}] Running query...", file=sys.stderr)
        if self.debug:
            print(f"\n[ESQL #{self._query_count}] Executing:", file=sys.stderr)
            print(f"{sql}", file=sys.stderr)
            print(f"---", file=sys.stderr)

        start_time = time.time()
        timeouts = [
            self.command_timeout,
            max(self.command_timeout * 3, self.command_timeout + 30),
        ]
        result: Optional[subprocess.CompletedProcess[bytes]] = None
        last_timeout_error: Optional[EtrackHierarchyError] = None

        for attempt, timeout_s in enumerate(timeouts, start=1):
            try:
                result = self._run_subprocess(
                    cmd,
                    timeout=timeout_s,
                    input_data=sql.encode("utf-8"),
                    error_label=f"ESQL #{self._query_count}",
                    context="esql query",
                    retry_on_timeout=False,
                )
                break
            except CommandTimeoutError as exc:
                if attempt < len(timeouts):
                    last_timeout_error = exc
                    if not self.quiet:
                        print(
                            f"[WARN] esql timed out at {timeout_s}s "
                            f"(--timeout {self.command_timeout}); retrying once "
                            f"with {timeouts[1]}s...",
                            file=sys.stderr,
                        )
                    continue
                raise

        if result is None:
            if last_timeout_error is not None:
                raise last_timeout_error
            raise EtrackHierarchyError("esql execution failed unexpectedly.")

        elapsed = time.time() - start_time
        if self.debug:
            print(
                f"[ESQL #{self._query_count}] Completed in {elapsed:.2f}s",
                file=sys.stderr,
            )
        elif not self.quiet:
            print(
                f"[ESQL #{self._query_count}] Completed in {elapsed:.2f}s",
                file=sys.stderr,
            )

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

            # esql output is tab-delimited; pipe characters may appear inside
            # field values (e.g. "[PVM-6926|8.8]" in ABSTRACT).
            if "\t" in stripped:
                parts = [part.strip() for part in stripped.split("\t")]
            elif "|" in stripped:
                parts = [part.strip() for part in re.split(r"\|", stripped)]
                parts = [part for part in parts if part != ""]
            else:
                parts = [part.strip() for part in stripped.split()]

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
        full_cmd = list(cmd)
        if self.ssh_target:
            full_cmd = self._ssh_command_prefix() + list(cmd)

        start_time = time.time()
        if not self.quiet and not self.debug:
            print("[INFO] Running external command...", file=sys.stderr)
        if self.debug:
            print(f"[INFO] Running: {' '.join(full_cmd)}", file=sys.stderr)

        display_cmd = " ".join(cmd)
        result = self._run_subprocess(
            full_cmd,
            timeout=self.command_timeout,
            error_label="Command",
            context=display_cmd,
        )

        elapsed = time.time() - start_time
        if not self.quiet:
            print(f"[INFO] External command completed in {elapsed:.2f}s", file=sys.stderr)

        return result.stdout.decode("utf-8", errors="replace")

    def _run_shell_pipeline(
        self,
        shell_cmd: str,
        timeout: Optional[int] = None,
        allow_failure: bool = False,
    ) -> str:
        timeout = timeout or self.command_timeout
        if self.ssh_target:
            cmd = self._ssh_command_prefix() + [shell_cmd]
        else:
            cmd = ["bash", "-lc", shell_cmd]

        start_time = time.time()
        if not self.quiet and not self.debug:
            print("[INFO] Running filtered remote command...", file=sys.stderr)
        if self.debug:
            print(f"[INFO] Shell pipeline: {shell_cmd}", file=sys.stderr)

        try:
            result = self._run_subprocess(
                cmd,
                timeout=timeout,
                allow_failure=allow_failure,
                acceptable_returncodes=(0, 1),
                error_label="Shell pipeline",
                context=shell_cmd,
            )
        except EtrackHierarchyError:
            if allow_failure:
                if self.debug:
                    print(
                        f"[WARN] Filtered command failed after retries: {shell_cmd}",
                        file=sys.stderr,
                    )
                return ""
            raise

        elapsed = time.time() - start_time
        if not self.quiet:
            print(
                f"[INFO] Filtered command completed in {elapsed:.2f}s",
                file=sys.stderr,
            )

        return result.stdout.decode("utf-8", errors="replace")

    def get_trencher_comments(self, incident: str) -> str:
        cached = self._comments_cache.get(f"trencher:{incident}")
        if cached is not None:
            return cached

        comments = extract_trencher_comments(self.get_comments(incident))
        self._comments_cache[f"trencher:{incident}"] = comments
        return comments

    def get_comments(self, incident: str) -> str:
        cached = self._comments_cache.get(incident)
        if cached is not None:
            return cached
        comments = self._run_command(["eprint", "-c", incident])
        self._comments_cache[incident] = comments
        return comments

    def get_latest_eeb_version(self, incident: str) -> Optional[int]:
        return self.get_latest_eeb_versions_batch([incident]).get(incident)

    def get_latest_eeb_versions_batch(
        self,
        incidents: List[str],
    ) -> Dict[str, Optional[int]]:
        if not incidents:
            return {}

        result: Dict[str, Optional[int]] = {}
        missing: List[str] = []
        for incident in incidents:
            if incident in self._latest_eeb_version_cache:
                result[incident] = self._latest_eeb_version_cache[incident]
            else:
                missing.append(incident)

        if not missing:
            return result

        if self.debug:
            print(
                f"[INFO] Resolving latest EEB version for {len(missing)} ET(s) "
                f"(parallel={self.deliverable_parallel})...",
                file=sys.stderr,
            )

        if self.ssh_target:
            batch_result = self._get_latest_eeb_versions_batch_remote(missing)
        else:
            batch_result = self._get_latest_eeb_versions_batch_local(missing)

        for incident in missing:
            latest = batch_result.get(incident)
            self._latest_eeb_version_cache[incident] = latest
            result[incident] = latest

        return result

    def _get_latest_eeb_versions_batch_remote(
        self,
        incidents: List[str],
    ) -> Dict[str, Optional[int]]:
        safe_ids = [self._safe_sql_incident(incident) for incident in incidents]
        ids_str = " ".join(safe_ids)
        parallel = self.deliverable_parallel
        shell_cmd = (
            f"for id in {ids_str}; do "
            f"while [ $(jobs -rp | wc -l | tr -d ' ') -ge {parallel} ]; do "
            f"wait -n 2>/dev/null || wait; done; "
            f"( v=$(eprint -c \"$id\" 2>/dev/null | grep 'This is EEB version' | "
            r"sed -n 's/.*: \([0-9][0-9]*\)/\1/p' | sort -n | tail -1); "
            f"printf '%s %s\\n' \"$id\" \"${{v:-}}\" ) & "
            f"done; wait"
        )
        batch_timeout = min(
            max(self.command_timeout, 60 + len(incidents) * 5),
            900,
        )
        output = self._run_shell_pipeline(
            shell_cmd,
            timeout=batch_timeout,
            allow_failure=True,
        )
        return self._parse_latest_eeb_version_lines(output, incidents)

    def _get_latest_eeb_versions_batch_local(
        self,
        incidents: List[str],
    ) -> Dict[str, Optional[int]]:
        parsed: Dict[str, Optional[int]] = {}

        def _lookup(incident_id: str) -> Tuple[str, Optional[int]]:
            shell_cmd = (
                f"eprint -c {incident_id} 2>/dev/null | "
                "grep 'This is EEB version' | "
                r"sed -n 's/.*: \([0-9][0-9]*\)/\1/p' | "
                "sort -n | tail -1"
            )
            output = self._run_shell_pipeline(shell_cmd, allow_failure=True).strip()
            latest = int(output) if output.isdigit() else None
            return incident_id, latest

        with ThreadPoolExecutor(max_workers=self.deliverable_parallel) as pool:
            futures = [pool.submit(_lookup, incident) for incident in incidents]
            for future in as_completed(futures):
                incident_id, latest = future.result()
                parsed[incident_id] = latest

        return parsed

    @staticmethod
    def _parse_latest_eeb_version_lines(
        output: str,
        incidents: List[str],
    ) -> Dict[str, Optional[int]]:
        parsed: Dict[str, Optional[int]] = {incident: None for incident in incidents}
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            incident_id, version_text = parts
            if incident_id in parsed:
                parsed[incident_id] = (
                    int(version_text) if version_text.isdigit() else None
                )
        return parsed

    def detect_deliverable_kinds(self, incident: str) -> List[str]:
        comments = self.get_trencher_comments(incident)
        return TrencherDeliverableParser().detect_kinds(comments, incident)

    def render_deliverable_hints(self, incident: str) -> str:
        try:
            comments = self.get_trencher_comments(incident)
        except EtrackHierarchyError as exc:
            summary = str(exc).splitlines()[0]
            print(
                f"[WARN] Could not fetch trencher comments for ET {incident}; "
                f"skipping DELIVERABLE SUMMARY: {summary}",
                file=sys.stderr,
            )
            return ""

        parser = TrencherDeliverableParser()
        kinds = parser.detect_kinds(comments, incident)
        if not kinds:
            return ""

        versions_by_kind: Dict[str, List[DeliverableVersion]] = {}
        for kind in kinds:
            versions_by_kind[kind] = parser.parse(comments, incident, kind)

        if self.debug:
            print(
                f"[DEBUG] Deliverable hints for ET {incident}: "
                f"{', '.join(versions_by_kind.keys())}",
                file=sys.stderr,
            )

        return DeliverableReporter().render_hints(incident, versions_by_kind)

    def fetch_incident_details_map(
        self,
        incidents: List[str],
        use_esql: bool,
    ) -> Dict[str, Dict[str, str]]:
        if not incidents:
            return {}

        if use_esql:
            parent_map = {incident: incident for incident in incidents}
            records = self.fetch_records_esql(incidents, parent_map)
        else:
            self._bulk_prefetch_details_vdk(incidents)
            parent_map = {incident: incident for incident in incidents}
            records = self.fetch_records_eprint_cached(incidents, parent_map)

        return {
            str(record.get("INCIDENT", "")).strip(): record for record in records
        }

    def render_deliverable_report(
        self,
        incident: str,
        kind: str,
        deliverable_use_esql: bool,
        include_details: bool = False,
        full_details: bool = False,
        stale_only: bool = False,
    ) -> str:
        comments = self.get_trencher_comments(incident)
        versions = TrencherDeliverableParser().parse(comments, incident, kind)
        if not versions:
            raise EtrackHierarchyError(
                f"No {deliverable_kind_label(kind)} deliverable comments found in "
                f"svc_rmntrencher comments for ET {incident}."
            )

        constituent_ids: List[str] = []
        seen: Set[str] = set()
        for version in versions:
            for constituent in version.constituents:
                if constituent.incident not in seen:
                    seen.add(constituent.incident)
                    constituent_ids.append(constituent.incident)

        if self.debug:
            print(
                f"[DEBUG] Fetching details for {len(constituent_ids)} constituent ET(s)...",
                file=sys.stderr,
            )

        enriched: Dict[str, Dict[str, str]] = {}
        latest_versions: Dict[str, Optional[int]] = {}

        with ThreadPoolExecutor(max_workers=2) as pool:
            details_future = pool.submit(
                self.fetch_incident_details_map,
                constituent_ids,
                deliverable_use_esql,
            )
            latest_future = pool.submit(
                self.get_latest_eeb_versions_batch,
                constituent_ids,
            )
            enriched = details_future.result()
            latest_versions = latest_future.result()

        return DeliverableReporter().render(
            versions,
            enriched,
            latest_versions,
            include_details=include_details,
            full_details=full_details,
            stale_only=stale_only,
        )

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

    def fetch_all_hierarchy_inc_bottom_up(
        self, root_incident: str
    ) -> Tuple[List[str], Dict[str, str]]:
        """Fetch hierarchy members and parent links from INC_BOTTOM_UP (fast)."""
        sql = (
            "SELECT INCIDENT, TO_NUMBER, TOP FROM INC_BOTTOM_UP "
            f"WHERE TOP = {self._safe_sql_incident(root_incident)}"
        )
        rows = self._parse_esql_output(
            self._run_esql(sql), ["INCIDENT", "TO_NUMBER", "TOP"]
        )

        incidents: List[str] = [root_incident]
        seen: Set[str] = {root_incident}
        parent_map: Dict[str, str] = {root_incident: root_incident}

        for row in rows:
            incident = str(row.get("INCIDENT", "")).strip()
            to_number = str(row.get("TO_NUMBER", "")).strip()
            if incident.isdigit() and incident not in seen:
                incidents.append(incident)
                seen.add(incident)
                if to_number.isdigit():
                    parent_map[incident] = to_number
                else:
                    parent_map[incident] = root_incident

        return incidents, parent_map

    def fetch_all_hierarchy_incident_view(
        self, root_incident: str
    ) -> Tuple[List[str], Dict[str, str]]:
        """Fetch all incidents under a single SUPERINCIDENT via INCIDENT_VIEW (slow)."""
        sql = (
            "SELECT INCIDENT FROM INCIDENT_VIEW "
            f"WHERE SUPERINCIDENT = {self._safe_sql_incident(root_incident)}"
        )
        rows = self._parse_esql_output(self._run_esql(sql), ["INCIDENT"])

        incidents: List[str] = [root_incident]
        seen: Set[str] = {root_incident}
        parent_map: Dict[str, str] = {root_incident: root_incident}

        for row in rows:
            incident = str(row.get("INCIDENT", "")).strip()
            if incident.isdigit() and incident not in seen:
                incidents.append(incident)
                seen.add(incident)
                parent_map[incident] = root_incident

        return incidents, parent_map

    def fetch_hierarchy_eprint(
        self, root_incident: str
    ) -> Tuple[List[str], Dict[str, str]]:
        """Fetch hierarchy using eprint -a and batched -vdK prefetch."""
        hierarchy_raw = self._run_command(["eprint", "-a", root_incident])
        hierarchy_line = self._extract_first_line(hierarchy_raw)
        incidents = self._parse_hierarchy_from_eprint_a_line(
            hierarchy_line, root_incident
        )

        parent_map: Dict[str, str] = {root_incident: root_incident}
        for incident in incidents:
            if incident != root_incident:
                parent_map[incident] = root_incident

        parent_incident_map = self._bulk_prefetch_details_vdk(incidents)
        parent_map.update(parent_incident_map)

        return incidents, parent_map

    def fetch_hierarchy(
        self,
        root_incident: str,
        max_nodes: int = 5000,
        hierarchy_source: str = DEFAULT_HIERARCHY_SOURCE,
    ) -> Tuple[List[str], Dict[str, str]]:
        if hierarchy_source == "inc-bottom-up":
            incidents, parent_map = self.fetch_all_hierarchy_inc_bottom_up(
                root_incident
            )
        elif hierarchy_source == "incident-view":
            incidents, parent_map = self.fetch_all_hierarchy_incident_view(
                root_incident
            )
        elif hierarchy_source == "eprint":
            incidents, parent_map = self.fetch_hierarchy_eprint(root_incident)
        else:
            raise EtrackHierarchyError(
                f"Unknown hierarchy source: {hierarchy_source}. "
                f"Choose from: {', '.join(HIERARCHY_SOURCES)}"
            )

        if len(incidents) > max_nodes:
            raise EtrackHierarchyError(
                f"Hierarchy exceeded max node limit ({max_nodes})."
            )

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
            if self.debug:
                print(
                    f"[DEBUG] eprint -v failed for {incident}; falling back to eprint -vdK ({exc})",
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
            f"WHERE INCIDENT IN ({sql_incidents})"
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


def _resolve_deliverable_use_esql(args: argparse.Namespace) -> bool:
    source = args.deliverable_details_source
    if source == "auto":
        return args.use_esql
    return source == "esql"


def _resolve_deliverable_kinds(
    fetcher: EtrackHierarchyFetcher,
    incident: str,
    args: argparse.Namespace,
) -> List[str]:
    kinds: List[str] = []
    if args.as_eeb_pkg:
        kinds.append("eeb-pkg")
    if args.as_bundle:
        kinds.append("bundle")
    if args.as_standard_eeb:
        kinds.append("eeb-standard")
    if args.auto_deliverable:
        for kind in fetcher.detect_deliverable_kinds(incident):
            if kind not in kinds:
                kinds.append(kind)

    ordered: List[str] = []
    for kind in DELIVERABLE_KINDS:
        if kind in kinds:
            ordered.append(kind)
    return ordered


def _validate_incident(value: str, option_name: str) -> str:
    incident = value.strip()
    if not incident or not incident.isdigit():
        raise EtrackHierarchyError(f"Invalid {option_name}: '{value}'. Must be numeric.")
    return incident


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}m {remainder:.1f}s"


def _render_single_et_table(
    fetcher: EtrackHierarchyFetcher,
    input_incident: str,
    args: argparse.Namespace,
) -> None:
    """Fetch and print one ET row (used by --single and -N without deliverable flags)."""
    columns = _resolve_output_columns(
        args.include_cols,
        args.exclude_cols,
        DEFAULT_COLUMNS,
    )
    parent_map = {input_incident: input_incident}
    if args.use_esql:
        rows = fetcher.fetch_records_esql([input_incident], parent_map)
    else:
        rows = fetcher.fetch_records_eprint_cached([input_incident], parent_map)

    for row in rows:
        row["SINCIDENT"] = input_incident
        row["PARENT_FLAG"] = ""

    renderer = TableRenderer(columns)
    print(renderer.render_with_count(rows))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch all eTracks in hierarchy and print tabular output.",
        formatter_class=ShortLongHelpFormatter,
        usage=HIERARCHY_USAGE,
        epilog=(
            "Examples:\n"
            "  %(prog)s 4203299\n"
            "  %(prog)s 4203299 -N\n"
            "  %(prog)s 4203299 -1\n"
            "  %(prog)s 4203299 -q\n"
            "  %(prog)s 4203299 -S\n"
            "  %(prog)s 4203299 -y incident-view\n"
            "  %(prog)s 4203299 -p\n"
            "  %(prog)s 4203299 -I INCIDENT,SINCIDENT,STATE,ABSTRACT\n"
            "  %(prog)s 4203299 -E VERSION,TARGET_VERSION\n"
            "  %(prog)s 4232810 -R user@server\n"
            "  %(prog)s 4232810 -R user@server -B -N\n"
            "  %(prog)s 4230893 -A -N\n"
            "  %(prog)s 4230893 -P -N -D\n"
            "  %(prog)s 4234410 -A -N -D\n"
            "  %(prog)s 4234410 -C -N -D\n"
            "  %(prog)s 4230893 -P -N -G eprint -F\n"
            "\n"
            "Default run prints hierarchy plus a lightweight DELIVERABLE SUMMARY\n"
            "for the input ET when svc_rmntrencher comments indicate pkg/bundle/standard.\n"
            "Deliverable types: EEB PACKAGE (-P), EEB BUNDLE (-B), STANDARD EEB (-C).\n"
            "Use -A to auto-detect type; add -D for SR shipping details per constituent,\n"
            "PLATFORM PACKAGES, LINKS, and full ARTIFACTS list.\n"
            "Note: -F/--stale-only applies to EEB package (-P/-A) reports only.\n"
            "\n"
            + HIERARCHY_SHORT_OPTIONS_HELP
            + "\n"
            "Auto-SSH (when -R omitted): ETRACK_SSH, ENGVM_HOST, NIS_USER@NIS_SERVER\n"
            "\n"
            "Hierarchy sources (-y/--hierarchy-source):\n"
            "  inc-bottom-up  fast INC_BOTTOM_UP esql query (default)\n"
            "  incident-view  slow INCIDENT_VIEW esql query\n"
            "  eprint         eprint -a based discovery"
        ),
    )

    parser.add_argument("incident", help="Incident ID or super incident ID")

    scope_group = parser.add_argument_group(
        "Input & scope",
        "Which ET(s) to fetch and how the incident ID is interpreted.",
    )
    scope_group.add_argument(
        "-S",
        "--as-super",
        action="store_true",
        help="Treat input incident as already-super incident (skip auto-resolution).",
    )
    scope_group.add_argument(
        "-1",
        "--single",
        action="store_true",
        help="Fetch one ET row only (no hierarchy walk).",
    )
    scope_group.add_argument(
        "-N",
        "--skip-hierarchy",
        action="store_true",
        help=(
            "Skip hierarchy table/tree output. Without -A/-P/-B, prints one ET "
            "summary row for the input incident (same as -1/--single)."
        ),
    )

    format_group = parser.add_argument_group(
        "Output format",
        "Columns shown, tree layout, and deliverable report content.",
    )
    format_group.add_argument(
        "-I",
        "--include-cols",
        help="Comma-separated columns to include.",
    )
    format_group.add_argument(
        "-E",
        "--exclude-cols",
        help="Comma-separated columns to exclude.",
    )
    format_group.add_argument(
        "-t",
        "--htree",
        dest="htree",
        action="store_true",
        help="Display hierarchy tree output after the table.",
    )
    format_group.add_argument(
        "-D",
        "--include-deliverable-details",
        action="store_true",
        help=(
            "Include SR shipping, artifacts, and platform-package summaries, "
            "PLATFORM PACKAGES, and LINKS "
            "(all deliverable types; excluded by default). Large lists show summary "
            "only unless -U/--full-deliverable-details is set."
        ),
    )
    format_group.add_argument(
        "-U",
        "--full-deliverable-details",
        action="store_true",
        help=(
            "With -D, also print full per-file SR SHIPPING DETAILS and ARTIFACTS tables "
            f"(default: full tables only when row count ≤ {DELIVERABLE_FULL_DETAIL_ROW_LIMIT})."
        ),
    )
    format_group.add_argument(
        "-F",
        "--stale-only",
        action="store_true",
        help=(
            "In EEB package reports, show only constituents whose embedded EEB "
            "version is older than the latest available."
        ),
    )

    deliverable_group = parser.add_argument_group(
        "Deliverable reports",
        "Parse svc_rmntrencher deliverables: EEB PACKAGE (-P), EEB BUNDLE (-B), "
        "STANDARD EEB (-C). Use -A to auto-detect type.",
    )
    deliverable_group.add_argument(
        "-A",
        "--auto-deliverable",
        action="store_true",
        help=(
            "Auto-detect deliverable type (EEB PACKAGE, EEB BUNDLE, or STANDARD EEB) "
            "from svc_rmntrencher comments and print full per-version reports. "
            "-P/-B/-C override or add to detected kinds."
        ),
    )
    deliverable_group.add_argument(
        "-P",
        "--as-eeb-pkg",
        action="store_true",
        help=(
            "Parse svc_rmntrencher EEB Package deliverable comments and print "
            "per-version package tables with constituent version checks."
        ),
    )
    deliverable_group.add_argument(
        "-B",
        "--as-bundle",
        action="store_true",
        help=(
            "Parse svc_rmntrencher EEB Bundle deliverable comments and print "
            "per-version bundle tables with constituent ET details."
        ),
    )
    deliverable_group.add_argument(
        "-C",
        "--as-standard-eeb",
        action="store_true",
        help=(
            "Parse svc_rmntrencher standard single-ET EEB deliverable comments "
            "(Submission Type: standard NetBackup submittal) and print shipping "
            "details. TYPE column shows STANDARD."
        ),
    )
    deliverable_group.add_argument(
        "-G",
        "--deliverable-details-source",
        choices=list(DELIVERABLE_DETAIL_SOURCES),
        default=DEFAULT_DELIVERABLE_DETAILS_SOURCE,
        help=(
            "Source for constituent TYPE/STATE/ABSTRACT in package/bundle reports "
            "(default: esql). Use 'auto' to follow hierarchy mode, or 'eprint' "
            "when esql is unavailable."
        ),
    )
    deliverable_group.add_argument(
        "--deliverable-parallel",
        "-j",
        type=int,
        default=DEFAULT_DELIVERABLE_PARALLEL,
        help=(
            "Parallel workers for constituent latest-EEB lookups in package/bundle "
            f"reports (default: {DEFAULT_DELIVERABLE_PARALLEL})."
        ),
    )

    source_group = parser.add_argument_group(
        "Data source",
        "How hierarchy members and ET fields are fetched (esql vs eprint).",
    )
    source_group.add_argument(
        "-p",
        "--use-eprint",
        dest="use_esql",
        action="store_false",
        help=(
            "Use eprint for hierarchy discovery and incident details "
            "(equivalent to -y eprint with no esql detail fetch)."
        ),
    )
    parser.set_defaults(use_esql=True)
    source_group.add_argument(
        "-y",
        "--hierarchy-source",
        choices=list(HIERARCHY_SOURCES),
        default=DEFAULT_HIERARCHY_SOURCE,
        help=(
            "How to discover hierarchy members (default: inc-bottom-up). "
            "inc-bottom-up uses fast INC_BOTTOM_UP esql; "
            "incident-view uses slow INCIDENT_VIEW esql; "
            "eprint uses eprint -a. Ignored when -p/--use-eprint is set."
        ),
    )

    remote_group = parser.add_argument_group(
        "Remote access",
        "SSH target and connection behavior when esql/eprint run remotely.",
    )
    remote_group.add_argument(
        "-R",
        "--ssh",
        help=(
            "Run commands remotely via SSH target user@host. "
            "When omitted, auto-SSH uses ETRACK_SSH, ENGVM_HOST, or NIS_USER@NIS_SERVER."
        ),
    )
    remote_group.add_argument(
        "-Z",
        "--no-auto-ssh",
        action="store_true",
        help="Do not auto-SSH when -R/--ssh is omitted and local esql is missing.",
    )
    remote_group.add_argument(
        "-X",
        "--no-ssh-multiplex",
        action="store_true",
        help="Disable SSH connection reuse (ControlMaster) for remote commands.",
    )

    perf_group = parser.add_argument_group(
        "Performance & limits",
        "Timeouts, retries, and safety caps on hierarchy traversal.",
    )
    perf_group.add_argument(
        "-m",
        "--max-nodes",
        type=int,
        default=5000,
        help="Safety limit for recursive hierarchy traversal (default: 5000).",
    )
    perf_group.add_argument(
        "-T",
        "--timeout",
        type=int,
        default=60,
        help="Per-command timeout in seconds (default: 60). Retries use a larger timeout.",
    )
    perf_group.add_argument(
        "-z",
        "--retries",
        type=int,
        default=DEFAULT_COMMAND_RETRIES,
        help=(
            "Max retries for transient SSH/network failures "
            f"(default: {DEFAULT_COMMAND_RETRIES}). Use 0 to disable."
        ),
    )
    perf_group.add_argument(
        "-g",
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help=(
            "Base delay in seconds between retries; doubles each attempt "
            f"(default: {DEFAULT_RETRY_DELAY})."
        ),
    )

    log_group = parser.add_argument_group(
        "Logging",
        "Progress and diagnostic output on stderr.",
    )
    log_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress messages (ESQL running/completed, external commands).",
    )
    log_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="One-line ESQL/command progress on stderr (default unless -q).",
    )
    log_group.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Print esql SQL text and detailed operational traces to stderr.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    start_time = time.perf_counter()
    args = parse_args(argv)
    if args.full_deliverable_details:
        args.include_deliverable_details = True
    fetcher: Optional[EtrackHierarchyFetcher] = None
    exit_code = 1

    try:
        input_incident = _validate_incident(args.incident, "incident")
        ssh_target = normalize_ssh_target(args.ssh)
        if not ssh_target and not args.no_auto_ssh:
            ssh_target = default_ssh_target()
            if ssh_target:
                print(f"[INFO] Auto-SSH: {ssh_target}", file=sys.stderr)

        fetcher = EtrackHierarchyFetcher(
            ssh_target=ssh_target,
            verbose=args.verbose,
            debug=args.debug,
            quiet=args.quiet,
            command_timeout=args.timeout,
            deliverable_parallel=args.deliverable_parallel,
            ssh_multiplex=not args.no_ssh_multiplex,
            max_retries=args.retries,
            retry_delay=args.retry_delay,
        )
        deliverable_kinds = _resolve_deliverable_kinds(fetcher, input_incident, args)
        deliverable_use_esql = _resolve_deliverable_use_esql(args)

        show_single_row = args.single or (args.skip_hierarchy and not deliverable_kinds)

        if args.single and args.htree:
            print("[WARN] --htree ignored with --single/-1.", file=sys.stderr)

        if (
            args.skip_hierarchy
            and args.auto_deliverable
            and not (args.as_eeb_pkg or args.as_bundle or args.as_standard_eeb)
            and not deliverable_kinds
        ):
            raise EtrackHierarchyError(
                f"No EEB package, bundle, or standard EEB deliverable comments "
                f"found for ET {input_incident}."
            )

        if args.stale_only and "eeb-pkg" not in deliverable_kinds:
            if deliverable_kinds:
                print(
                    "[WARN] --stale-only/-F applies to EEB package reports only.",
                    file=sys.stderr,
                )
            else:
                raise EtrackHierarchyError(
                    "--stale-only/-F requires an EEB package report (-P or -A)."
                )

        if deliverable_kinds and args.debug:
            kind_labels = ", ".join(
                deliverable_kind_label(kind) for kind in deliverable_kinds
            )
            print(
                f"[DEBUG] Deliverable types: {kind_labels}",
                file=sys.stderr,
            )
            print(
                f"[DEBUG] Deliverable details source: "
                f"{'esql' if deliverable_use_esql else 'eprint'}",
                file=sys.stderr,
            )

        if args.skip_hierarchy and args.debug:
            print("[DEBUG] Skipping hierarchy output (-N)", file=sys.stderr)

        if show_single_row:
            if args.debug and args.skip_hierarchy and not args.single:
                print(
                    "[DEBUG] -N without deliverable flags: fetching one ET summary row",
                    file=sys.stderr,
                )
            _render_single_et_table(fetcher, input_incident, args)
        elif not args.skip_hierarchy:
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

            hierarchy_source = (
                "eprint" if not args.use_esql else args.hierarchy_source
            )

            if args.debug:
                print(f"[DEBUG] Resolved SINCIDENT: {root_incident}", file=sys.stderr)
                print(
                    f"[DEBUG] Hierarchy source: {hierarchy_source}",
                    file=sys.stderr,
                )

            hierarchy_incidents, parent_map = fetcher.fetch_hierarchy(
                root_incident,
                max_nodes=args.max_nodes,
                hierarchy_source=hierarchy_source,
            )

            columns = _resolve_output_columns(
                args.include_cols,
                args.exclude_cols,
                DEFAULT_COLUMNS,
            )

            if args.use_esql:
                rows = fetcher.fetch_records_esql(hierarchy_incidents, parent_map)
                if hierarchy_source == "incident-view":
                    parent_overrides, _ = fetcher.fetch_parent_incidents_esql(
                        hierarchy_incidents
                    )
                    for row in rows:
                        incident = row.get("INCIDENT", "")
                        if incident in parent_overrides:
                            row["SINCIDENT"] = parent_overrides[incident]
                    parent_map.update(parent_overrides)
            else:
                rows = fetcher.fetch_records_eprint_cached(
                    hierarchy_incidents, parent_map
                )

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
            print(renderer.render_with_count(rows))
            if args.debug:
                print(
                    "\nNote: '*' in PAR column = parent incident in hierarchy",
                    file=sys.stderr,
                )

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
            print(
                f"[DEBUG] Total esql queries executed: {fetcher._query_count}",
                file=sys.stderr,
            )

        if deliverable_kinds:
            for kind in deliverable_kinds:
                print(fetcher.render_deliverable_report(
                    input_incident,
                    kind=kind,
                    deliverable_use_esql=deliverable_use_esql,
                    include_details=args.include_deliverable_details,
                    full_details=args.full_deliverable_details,
                    stale_only=args.stale_only and kind == "eeb-pkg",
                ))
        elif not args.skip_hierarchy or show_single_row:
            hints = fetcher.render_deliverable_hints(input_incident)
            if hints:
                print(hints)

        exit_code = 0

    except EtrackHierarchyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        elapsed = time.perf_counter() - start_time
        print(f"\nTotal time: {_format_elapsed(elapsed)}", file=sys.stderr)
        if fetcher is not None:
            fetcher.close_ssh()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
