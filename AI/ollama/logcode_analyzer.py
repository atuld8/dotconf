
#!/usr/bin/env python3
"""
Log + Code Analyzer
- Python 3.12, stdlib only (optional Pygments highlight if installed)
- Input: source root (code), log file(s)
- Output: single HTML report w/ timeline, errors, file:line citations, and code context
"""

from __future__ import annotations
import argparse
import datetime as dt
import html
import io
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

# ------------------------------
# Redaction (PII & secrets)
# ------------------------------
REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer/JWT tokens
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*\b"), r"\1***REDACTED***"),
    (re.compile(r"(?i)\b(jwt|id_token|access_token)\s*[:=]\s*[A-Za-z0-9\-\._~\+\/]+=*\b"), r"\1=***REDACTED***"),
    # AWS access/secret keys (heuristics)
    (re.compile(r"(?i)\b(AKI[A-Z0-9]{16})\b"), "***REDACTED_AWS_KEY***"),
    (re.compile(r"(?i)\b(aws_secret_access_key|secret_access_key)\s*[:=]\s*['\"]?[A-Za-z0-9\/+=]{16,}['\"]?"), r"\1=***REDACTED***"),
    # Email addresses
    (re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9\.-]+"), "***REDACTED_EMAIL***"),
    # Generic passwords and tokens
    (re.compile(r"(?i)\b(password|passwd|pwd|token|secret)\b\s*[:=]\s*['\"][^'\"\n]+['\"]"), r"\1=***REDACTED***"),
]

def redact(s: str) -> str:
    for pat, repl in REDACTION_PATTERNS:
        s = pat.sub(repl, s)
    return s

# ------------------------------
# Log parsing
# ------------------------------
STACK_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+), in ([^\n]+)')
# Common timestamp formats (extend as needed)
TS_CANDIDATES = [
    r"(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)",
    r"(?P<ts>\d{2}:\d{2}:\d{2})",
]
LEVEL_RE = re.compile(r"\b(INFO|DEBUG|WARN|WARNING|ERROR|FATAL|CRITICAL)\b")

def parse_line(line: str) -> dict[str, Any]:
    orig = line.rstrip("\n")
    line = redact(orig)
    ts = None
    for pat in TS_CANDIDATES:
        m = re.search(pat, line)
        if m:
            ts = m.group("ts")
            break
    lvl = None
    m = LEVEL_RE.search(line)
    if m:
        lvl = m.group(1)
    return {"raw": orig, "redacted": line, "ts": ts, "level": lvl}

def parse_stack(lines: list[str], start_idx: int) -> tuple[list[dict[str, Any]], int]:
    frames = []
    i = start_idx
    while i < len(lines):
        m = STACK_FRAME_RE.search(lines[i])
        if not m:
            break
        file, ln, func = m.group(1), int(m.group(2)), m.group(3)
        frames.append({"file": file, "line": ln, "func": func, "raw": redact(lines[i].rstrip("\n"))})
        i += 1
    return frames, i

# ------------------------------
# Code helpers
# ------------------------------
def load_file_snippet(path: Path, line_no: int, radius: int = 6) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    start = max(1, line_no - radius)
    end = min(len(content), line_no + radius)
    buf = io.StringIO()
    for n in range(start, end + 1):
        mark = ">>" if n == line_no else "  "
        text = html.escape(content[n - 1])
        buf.write(f"{mark} {n:5d}: {text}\n")
    return buf.getvalue()

def find_log_message_sources(code_root: Path, msg: str) -> list[dict[str, Any]]:
    """Search for lines that likely printed/logged msg (best effort)."""
    msg_core = re.sub(r"[^A-Za-z0-9\s:_\-\.]", " ", msg).strip()
    msg_core = " ".join(msg_core.split())[:80]
    results: list[dict[str, Any]] = []
    if not msg_core:
        return results
    for p in code_root.rglob("*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if msg_core and msg_core.lower() in txt.lower():
            # Capture surrounding
            lines = txt.splitlines()
            for idx, line in enumerate(lines, 1):
                if msg_core.lower() in line.lower():
                    snippet = "\n".join(
                        f'{" >>" if j==idx else "   "} {j:5d}: {html.escape(lines[j-1])}'
                        for j in range(max(1, idx-3), min(len(lines), idx+3)+1)
                    )
                    results.append({"path": str(p), "line": idx, "snippet": snippet})
    return results

# ------------------------------
# Heuristic detectors (actionable hints)
# ------------------------------
HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Batch size .* greater than max batch size", re.I),
     "Chroma batch too large → split `upsert` into chunks (≤ 5,000–5,461)."),
    (re.compile(r"PydanticImportError.*BaseSettings.*pydantic-settings", re.I),
     "Pydantic v2 change → `from pydantic_settings import BaseSettings` and `pip install pydantic-settings`."),
    (re.compile(r"`?np\.float_?`? was removed|np\.float_", re.I),
     "NumPy 2.0 alias removed → pin `numpy<2` (e.g., 1.26.4) or upgrade code using `np.float64`."),
    (re.compile(r"Expected where to have exactly one operator", re.I),
     "Chroma filter validation → pass `where=None` or a valid operator (e.g., {'lang': {'$eq': 'python'}})."),
    (re.compile(r"model '.*' not found", re.I),
     "Ollama model tag missing → `ollama pull <model>` and ensure your config uses an existing tag."),
]

def derive_hints(all_text: str) -> list[str]:
    hints = []
    for pat, msg in HINTS:
        if pat.search(all_text):
            hints.append(msg)
    return sorted(set(hints))

# ------------------------------
# HTML rendering
# ------------------------------
def html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8" />
<title>{html.escape(title)}</title>
<style>
body {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background:#0b0e14; color:#e6e1cf; padding:20px; }}
h1,h2,h3 {{ color:#c2d94c; }}
a {{ color:#59c2ff; }}
.code {{ background:#1f2430; padding:12px; border-radius:6px; white-space:pre; overflow:auto; }}
.grid {{ display:grid; grid-template-columns: 1fr; gap:16px; }}
.card {{ background:#1a1e27; border-radius:6px; padding:12px; }}
.warn {{ color:#ffcc66; }}
.err  {{ color:#ff8f40; }}
.meta {{ color:#a6accd; }}
.kv   {{ color:#d5ff80; }}
</style>
</head><body>
{body}
</body></html>
"""

def render_report(code_root: Path, events: list[dict[str, Any]], stacks: list[dict[str, Any]]) -> str:
    # Compose
    all_text = "\n".join(e["redacted"] for e in events)
    hints = derive_hints(all_text)

    # Timeline
    tl = io.StringIO()
    tl.write("<h2>Timeline</h2>\n<div class='grid'>\n")
    for e in events:
        lvl = e.get("level") or ""
        cls = "err" if "ERR" in lvl.upper() or "FATAL" in lvl.upper() else ("warn" if "WARN" in lvl.upper() else "meta")
        ts = e.get("ts") or ""
        tl.write(f"<div class='card'><div class='{cls}'><b>{html.escape(lvl or 'LOG')}</b> {html.escape(ts)}</div>")
        tl.write(f"<div class='code'>{html.escape(e['redacted'])}</div></div>\n")
    tl.write("</div>\n")

    # Stacks
    st = io.StringIO()
    st.write("<h2>Stack Traces & Code Context</h2>\n<div class='grid'>\n")
    for s in stacks:
        st.write("<div class='card'>")
        st.write("<div class='meta'>Stack:</div>")
        st.write("<div class='code'>")
        for f in s["frames"]:
            st.write(html.escape(f"{f['raw']}\n"))
        st.write("</div>")
        # Code contexts
        for f in s["frames"]:
            fpath = Path(f["file"])
            # Try both absolute and relative to code_root
            candidate = fpath if fpath.exists() else (code_root / fpath.name)
            snippet = load_file_snippet(candidate, f["line"], radius=6)
            if snippet:
                st.write(f"<div class='meta'>Context: {html.escape(str(candidate))}:{f['line']}</div>")
                st.write(f"<div class='code'>{snippet}</div>")
        st.write("</div>\n")
    st.write("</div>\n")

    # Message → Source search
    ms = io.StringIO()
    ms.write("<h2>Message → Source Matches</h2>\n<div class='grid'>\n")
    for e in events[:250]:  # cap for performance
        msg = e["redacted"]
        hits = find_log_message_sources(code_root, msg)
        if hits:
            ms.write("<div class='card'>")
            ms.write(f"<div class='meta'>Log:</div><div class='code'>{html.escape(msg)}</div>")
            for h in hits:
                ms.write(f"<div class='meta kv'>Match: {html.escape(h['path'])}:{h['line']}</div>")
                ms.write(f"<div class='code'>{h['snippet']}</div>")
            ms.write("</div>\n")
    ms.write("</div>\n")

    # Hints
    hi = io.StringIO()
    hi.write("<h2>Actionable Hints</h2>\n")
    if hints:
        hi.write("<ul>\n")
        for h in hints:
            hi.write(f"<li>{html.escape(h)}</li>\n")
        hi.write("</ul>\n")
    else:
        hi.write("<div class='meta'>No known patterns detected.</div>\n")

    # Policy banner (org guidance)
    policy = (
        "<h2>Logging Hygiene</h2>"
        "<ul>"
        "<li>Redacted likely secrets/PII in report (tokens, emails). Validate against your team’s logging policy.</li>"
        "<li>Rotate logs and set retention; forward to a centralized store (e.g., SIEM/syslog) when applicable.</li>"
        "</ul>"
    )

    body = f"<h1>Log + Code Analyzer</h1><div class='meta'>Project: {html.escape(str(code_root))}</div>" + tl.getvalue() + st.getvalue() + ms.getvalue() + hi.getvalue() + policy
    return html_page("Log + Code Analyzer", body)

# ------------------------------
# Main
# ------------------------------
def main():
    ap = argparse.ArgumentParser(description="Analyze logs against source code and produce an HTML report.")
    ap.add_argument("--code-root", required=True, help="Path to source code root")
    ap.add_argument("--log", required=True, nargs="+", help="One or more log files (supports glob via shell)")
    ap.add_argument("--out", default="log_analysis_report.html", help="Output HTML file")
    args = ap.parse_args()

    code_root = Path(args.code_root).resolve()
    if not code_root.exists():
        print(f"[!] code-root not found: {code_root}", file=sys.stderr); sys.exit(1)

    log_paths: list[Path] = []
    for lp in args.log:
        p = Path(lp)
        if p.exists():
            log_paths.append(p)
        else:
            print(f"[!] log not found: {lp}", file=sys.stderr)

    if not log_paths:
        print("[!] no valid log files found", file=sys.stderr); sys.exit(2)

    # Load and parse
    raw_lines: list[str] = []
    for p in log_paths:
        try:
            raw_lines.extend(p.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception as ex:
            print(f"[!] failed to read {p}: {ex}", file=sys.stderr)

    # Events
    events: list[dict[str, Any]] = [parse_line(l) for l in raw_lines if l.strip()]

    # Stack traces (Python-style)
    stacks: list[dict[str, Any]] = []
    i = 0
    while i < len(raw_lines):
        if raw_lines[i].strip().startswith("Traceback (most recent call last):"):
            frames, j = parse_stack(raw_lines, i + 1)
            stacks.append({"frames": frames})
            i = j
        else:
            i += 1

    html_report = render_report(code_root, events, stacks)
    Path(args.out).write_text(html_report, encoding="utf-8")
    print(f"[✓] Report written to {args.out}")

if __name__ == "__main__":
    main()
