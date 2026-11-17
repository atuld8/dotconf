#!/usr/bin/env python3
"""Shared Jira Cloud/Server API helpers for scripts in this folder.

Environment:
  JIRA_SERVER_NAME   host (e.g. cohesity.atlassian.net)
  JIRA_ACC_TOKEN     Cloud API token or Server/DC PAT
  JIRA_USER_EMAIL    required for Cloud Basic auth (aliases: JIRA_EMAIL, JIRA_USER)
  JIRA_AUTH_MODE     optional: basic|bearer
  JIRA_CLOUD         optional: 1/0 force Cloud vs Server
  JIRA_CLOUD_ID      optional: api.atlassian.com gateway id for scoped tokens
  JIRA_CA_BUNDLE / REQUESTS_CA_BUNDLE / SSL_CERT_FILE
  JIRA_INSECURE_SSL  optional: 1 disable TLS verify
  JIRA_STRICT_SSL    optional: 1 forbid Zscaler keyUsage auto-relax
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

# Prefer macOS Keychain/Secure Transport when available (Zscaler-friendly).
_TRUSTSTORE_ENABLED = False
try:
    import truststore  # type: ignore

    truststore.inject_into_ssl()
    _TRUSTSTORE_ENABLED = True
except Exception:
    _TRUSTSTORE_ENABLED = False


def truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_jira_host(server: Optional[str]) -> str:
    if not server:
        return ""
    host = server.strip()
    host = re.sub(r"^https?://", "", host, flags=re.IGNORECASE)
    host = host.split("/", 1)[0].rstrip("/")
    return host


def detect_jira_cloud(server: Optional[str]) -> bool:
    force = (os.getenv("JIRA_CLOUD") or "").strip().lower()
    if force in {"1", "true", "yes", "on"}:
        return True
    if force in {"0", "false", "no", "off"}:
        return False
    host = normalize_jira_host(server).lower()
    return host.endswith(".atlassian.net") or host == "atlassian.net"


def _certifi_ca_bundle() -> Optional[str]:
    try:
        import certifi  # type: ignore
    except ImportError:
        return None
    path = certifi.where()
    return path if path and os.path.exists(path) else None


def _export_macos_keychain_certs(output_path: Path) -> bool:
    keychains = [
        "/Library/Keychains/System.keychain",
        "/System/Library/Keychains/SystemRootCertificates.keychain",
    ]
    chunks: List[bytes] = []
    for keychain in keychains:
        if not os.path.exists(keychain):
            continue
        try:
            result = subprocess.run(
                ["security", "find-certificate", "-a", "-p", keychain],
                check=False,
                capture_output=True,
            )
        except OSError:
            continue
        if result.returncode == 0 and result.stdout and b"BEGIN CERTIFICATE" in result.stdout:
            chunks.append(result.stdout.rstrip() + b"\n")
    if not chunks:
        return False
    certifi_path = _certifi_ca_bundle()
    if certifi_path:
        try:
            chunks.append(Path(certifi_path).read_bytes())
        except OSError:
            pass
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"".join(chunks))
    return output_path.is_file() and output_path.stat().st_size > 0


def macos_combined_ca_bundle() -> Optional[str]:
    if sys.platform != "darwin":
        return None
    cache_dir = Path(os.getenv("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "jira-tools"
    cache_path = cache_dir / "macos-keychain-ca-bundle.pem"
    try:
        if cache_path.is_file() and (time.time() - cache_path.stat().st_mtime) < 86400:
            return str(cache_path)
    except OSError:
        pass
    try:
        if _export_macos_keychain_certs(cache_path):
            return str(cache_path)
    except OSError:
        return None
    return None


def resolve_ssl_verify() -> Union[bool, str]:
    if truthy_env("JIRA_INSECURE_SSL"):
        print(
            "WARNING: JIRA_INSECURE_SSL=1 — TLS certificate verification is disabled.",
            file=sys.stderr,
        )
        return False
    for env_name in ("JIRA_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        configured = (os.getenv(env_name) or "").strip()
        if configured:
            if not os.path.exists(configured):
                raise RuntimeError(f"{env_name} path does not exist: {configured}")
            return configured
    mac_bundle = macos_combined_ca_bundle()
    if mac_bundle:
        return mac_bundle
    certifi_bundle = _certifi_ca_bundle()
    if certifi_bundle:
        return certifi_bundle
    return True


def is_zscaler_keyusage_ssl_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "key usage extension" in msg or (
        "certificate_verify_failed" in msg and "key usage" in msg
    )


def ssl_error_hint(exc: BaseException) -> str:
    hints = ["TLS/SSL verification failed while connecting to Jira."]
    if is_zscaler_keyusage_ssl_error(exc) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
        hints.append(
            "On macOS + Zscaler, OpenSSL/LibreSSL reject the Zscaler Root CA "
            "(missing keyUsage extension)."
        )
        hints.append(
            "Fix options: "
            "(1) /opt/homebrew/bin/python3 -m pip install truststore, "
            "(2) export JIRA_INSECURE_SSL=1."
        )
    return " ".join(hints) + f" Details: {exc}"


@dataclass
class JiraConfig:
    server: str
    base_url: str
    token: str
    email: str
    is_cloud: bool
    auth_mode: str
    headers: Dict[str, str]
    verify: Union[bool, str]
    cloud_id: str = ""


_CONFIG: Optional[JiraConfig] = None
_SSL_RELAXED = False
_WARNED_SSL_RELAX = False


def load_config(*, reload: bool = False) -> JiraConfig:
    """Load Jira connection settings from the environment."""
    global _CONFIG, _SSL_RELAXED, _WARNED_SSL_RELAX
    if _CONFIG is not None and not reload:
        return _CONFIG

    load_dotenv()
    server = normalize_jira_host(os.getenv("JIRA_SERVER_NAME"))
    token = (os.getenv("JIRA_ACC_TOKEN") or "").strip()
    email = (
        os.getenv("JIRA_USER_EMAIL")
        or os.getenv("JIRA_EMAIL")
        or os.getenv("JIRA_USER")
        or ""
    ).strip()
    cloud_id = (os.getenv("JIRA_CLOUD_ID") or "").strip()
    is_cloud = detect_jira_cloud(server)

    if not server or not token:
        raise RuntimeError("Missing JIRA_SERVER_NAME or JIRA_ACC_TOKEN in environment")

    if is_cloud and cloud_id:
        base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
    else:
        base_url = f"https://{server}"

    auth_mode = (os.getenv("JIRA_AUTH_MODE") or "").strip().lower()
    if not auth_mode:
        auth_mode = "basic" if is_cloud else "bearer"

    if auth_mode == "basic":
        if not email:
            raise RuntimeError(
                "Jira Cloud Basic auth requires JIRA_USER_EMAIL (or JIRA_EMAIL) "
                "together with JIRA_ACC_TOKEN (API token from "
                "https://id.atlassian.com/manage-profile/security/api-tokens)."
            )
        encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        auth_header = f"Basic {encoded}"
    elif auth_mode == "bearer":
        auth_header = f"Bearer {token}"
    else:
        raise RuntimeError(
            f"Unsupported JIRA_AUTH_MODE={auth_mode!r} (expected 'basic' or 'bearer')"
        )

    verify = resolve_ssl_verify()
    _SSL_RELAXED = verify is False
    _WARNED_SSL_RELAX = False

    _CONFIG = JiraConfig(
        server=server,
        base_url=base_url,
        token=token,
        email=email,
        is_cloud=is_cloud,
        auth_mode=auth_mode,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        verify=verify,
        cloud_id=cloud_id,
    )
    return _CONFIG


def get_config() -> JiraConfig:
    return load_config()


def load_config_or_exit(*, exit_code: int = 1) -> JiraConfig:
    """Load config or exit with a clear Cloud/Server setup message."""
    try:
        return load_config()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "Set JIRA_SERVER_NAME, JIRA_ACC_TOKEN"
            ", and for Cloud also JIRA_USER_EMAIL.",
            file=sys.stderr,
        )
        sys.exit(exit_code)


def log_connection(cfg: Optional[JiraConfig] = None) -> JiraConfig:
    """Print non-secret connection diagnostics to stderr."""
    cfg = cfg or load_config()
    print(
        f"[INFO] Jira {cfg.server} | cloud={cfg.is_cloud} | "
        f"auth={cfg.auth_mode} | base={cfg.base_url}",
        file=sys.stderr,
    )
    return cfg


def empty_search_hints(jql: str, *, cfg: Optional[JiraConfig] = None) -> None:
    """Print actionable hints when a JQL search returns zero issues."""
    cfg = cfg or load_config()
    print(f"[INFO] JQL returned 0 issues: {jql}", file=sys.stderr)
    try:
        me = whoami()
        label = (
            me.get("displayName")
            or me.get("emailAddress")
            or me.get("accountId")
            or me.get("name")
            or "?"
        )
        print(f"[INFO] Authenticated as: {label}", file=sys.stderr)
    except Exception as exc:
        print(f"[ERROR] Auth/connectivity check failed: {exc}", file=sys.stderr)
        print(
            "[HINT] Fix auth first (JIRA_SERVER_NAME / JIRA_ACC_TOKEN"
            + (" / JIRA_USER_EMAIL" if cfg.is_cloud else "")
            + ").",
            file=sys.stderr,
        )
    if cfg.is_cloud and re.search(r"\bAssignee\s+in\s*\(", jql or "", re.I):
        print(
            "[HINT] On Jira Cloud, Assignee in (username) often matches nothing. "
            "Use accountId/email or assignee = currentUser().",
            file=sys.stderr,
        )
    print(
        "[HINT] Retry with a broader JQL or verify project key/permissions on Cloud.",
        file=sys.stderr,
    )


def search_all_or_fail(
    jql: str,
    *,
    page_size: int = 50,
    fields: Union[str, List[str]] = "*all",
    expand: str = "names",
    max_total: Optional[int] = None,
    context: str = "Jira search",
    on_empty: str = "return",
) -> List[Dict[str, Any]]:
    """Paginated search with clear failure logging.

    on_empty:
      - \"return\": return [] after printing hints (default)
      - \"exit\": print hints and sys.exit(2)
      - \"raise\": raise RuntimeError after hints
    """
    cfg = load_config()
    endpoint = (
        "POST /rest/api/3/search/jql" if cfg.is_cloud else "GET /rest/api/2/search"
    )
    print(
        f"[INFO] {context}: searching via {endpoint} "
        f"(page_size={page_size}, max_total={max_total})",
        file=sys.stderr,
    )
    try:
        issues = search_all_issues(
            jql,
            page_size=page_size,
            fields=fields,
            expand=expand,
            max_total=max_total,
        )
    except Exception as exc:
        print(f"[ERROR] {context} failed: {exc}", file=sys.stderr)
        print(f"[ERROR] JQL was: {jql}", file=sys.stderr)
        try:
            whoami()
        except Exception as auth_exc:
            print(f"[ERROR] Auth check also failed: {auth_exc}", file=sys.stderr)
        raise RuntimeError(f"{context} failed: {exc}") from exc

    print(f"[INFO] {context}: fetched {len(issues)} issue(s)", file=sys.stderr)
    if not issues:
        empty_search_hints(jql, cfg=cfg)
        if on_empty == "exit":
            sys.exit(2)
        if on_empty == "raise":
            raise RuntimeError(f"{context} returned 0 issues for JQL: {jql}")
    return issues


def _absolute_url(path_or_url: str, cfg: JiraConfig) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{cfg.base_url.rstrip('/')}/{path_or_url.lstrip('/')}"


def request(
    method: str,
    path_or_url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    timeout: float = 30,
    max_retries: int = 5,
    headers: Optional[Dict[str, str]] = None,
) -> requests.Response:
    """HTTP request with Cloud/Server auth, SSL handling, and transient retries."""
    global _SSL_RELAXED, _WARNED_SSL_RELAX

    cfg = load_config()
    url = _absolute_url(path_or_url, cfg)
    request_headers = dict(cfg.headers)
    if headers:
        request_headers.update(headers)
    request_headers["Connection"] = "close"

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        session = requests.Session()
        try:
            try:
                response = session.request(
                    method.upper(),
                    url,
                    headers=request_headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=timeout,
                    verify=cfg.verify,
                )
            except requests.exceptions.SSLError as exc:
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

                if (
                    not _SSL_RELAXED
                    and not truthy_env("JIRA_STRICT_SSL")
                    and is_zscaler_keyusage_ssl_error(exc)
                ):
                    cfg.verify = False
                    _SSL_RELAXED = True
                    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
                    if not _WARNED_SSL_RELAX:
                        _WARNED_SSL_RELAX = True
                        print(
                            "WARNING: TLS verify failed due to Zscaler CA missing keyUsage "
                            "(OpenSSL/LibreSSL). Retrying with verification disabled for this run. "
                            "Preferred fix: /opt/homebrew/bin/python3 -m pip install truststore",
                            file=sys.stderr,
                        )
                    continue

                raise RuntimeError(
                    f"TLS/SSL error while connecting to Jira ({cfg.server}). "
                    f"{ssl_error_hint(exc)}"
                ) from exc
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ) as exc:
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
                raise RuntimeError(
                    f"Network error while calling Jira ({cfg.server}): {exc}"
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise RuntimeError(
                    f"Network error while calling Jira ({cfg.server}): {exc}"
                ) from exc

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

    raise RuntimeError(
        f"Network error while calling Jira ({cfg.server}) after {max_retries} attempts: {last_exc}"
    )


def get(path_or_url: str, **kwargs: Any) -> requests.Response:
    return request("GET", path_or_url, **kwargs)


def post(path_or_url: str, **kwargs: Any) -> requests.Response:
    return request("POST", path_or_url, **kwargs)


def put(path_or_url: str, **kwargs: Any) -> requests.Response:
    return request("PUT", path_or_url, **kwargs)


def delete(path_or_url: str, **kwargs: Any) -> requests.Response:
    return request("DELETE", path_or_url, **kwargs)


def search_issues(
    jql: str,
    *,
    max_results: int = 50,
    fields: Union[str, List[str]] = "*all",
    expand: str = "names",
    start_at: int = 0,
) -> Dict[str, Any]:
    """Run a JQL search. Uses /rest/api/3/search/jql on Cloud; /rest/api/2/search elsewhere."""
    cfg = load_config()
    # Cloud enhanced search typically caps page size around 100.
    cloud_page_cap = 100
    if cfg.is_cloud:
        field_list: List[str]
        if isinstance(fields, str):
            field_list = [f.strip() for f in fields.split(",") if f.strip()] or ["*all"]
        else:
            field_list = list(fields)
        page_size = max(1, min(int(max_results), cloud_page_cap))
        payload: Dict[str, Any] = {
            "jql": jql,
            "maxResults": page_size,
            "fields": field_list,
        }
        if expand:
            payload["expand"] = expand
        # Cloud enhanced search uses nextPageToken; startAt is ignored.
        response = post("rest/api/3/search/jql", json=payload)
        endpoint = "POST /rest/api/3/search/jql"
    else:
        params: Dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
            "fields": fields if isinstance(fields, str) else ",".join(fields),
        }
        if expand:
            params["expand"] = expand
        response = get("rest/api/2/search", params=params)
        endpoint = "GET /rest/api/2/search"

    if response.status_code != 200:
        body = (response.text or "").strip().replace("\n", " ")
        raise RuntimeError(
            f"Failed to search issues via {endpoint}: "
            f"HTTP {response.status_code} — {body[:600]}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Search via {endpoint} returned non-JSON body: {(response.text or '')[:300]}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Search via {endpoint} returned unexpected JSON type {type(data).__name__}"
        )
    if "issues" not in data:
        # Surface Cloud/Server error payloads that came back as HTTP 200 unexpectedly.
        raise RuntimeError(
            f"Search via {endpoint} returned no 'issues' key. "
            f"Keys={sorted(data.keys())[:20]} body={str(data)[:400]}"
        )
    return data


def whoami() -> Dict[str, Any]:
    """Return the authenticated user profile (useful connectivity/auth check)."""
    cfg = load_config()
    path = "rest/api/3/myself" if cfg.is_cloud else "rest/api/2/myself"
    response = get(path)
    if response.status_code != 200:
        body = (response.text or "").strip().replace("\n", " ")
        raise RuntimeError(
            f"Auth check failed ({path}): HTTP {response.status_code} — {body[:400]}"
        )
    return response.json()


def search_all_issues(
    jql: str,
    *,
    page_size: int = 50,
    fields: Union[str, List[str]] = "*all",
    expand: str = "names",
    max_total: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Paginate through JQL results for Cloud (nextPageToken) and Server (startAt)."""
    cfg = load_config()
    issues: List[Dict[str, Any]] = []
    names: Optional[Dict[str, str]] = None

    if cfg.is_cloud:
        next_token: Optional[str] = None
        field_list: List[str]
        if isinstance(fields, str):
            field_list = [f.strip() for f in fields.split(",") if f.strip()] or ["*all"]
        else:
            field_list = list(fields)
        while True:
            payload: Dict[str, Any] = {
                "jql": jql,
                "maxResults": page_size,
                "fields": field_list,
            }
            if expand:
                payload["expand"] = expand
            if next_token:
                payload["nextPageToken"] = next_token
            response = post("rest/api/3/search/jql", json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to search issues: {response.status_code} {response.text[:400]}"
                )
            data = response.json()
            batch = data.get("issues") or []
            if names is None and isinstance(data.get("names"), dict):
                names = data["names"]
            if names:
                for issue in batch:
                    issue.setdefault("names", names)
            issues.extend(batch)
            if max_total is not None and len(issues) >= max_total:
                return issues[:max_total]
            next_token = data.get("nextPageToken")
            if not next_token or not batch:
                break
        return issues

    start_at = 0
    while True:
        data = search_issues(
            jql,
            max_results=page_size,
            fields=fields,
            expand=expand,
            start_at=start_at,
        )
        batch = data.get("issues") or []
        if names is None and isinstance(data.get("names"), dict):
            names = data["names"]
        if names:
            for issue in batch:
                issue.setdefault("names", names)
        issues.extend(batch)
        if max_total is not None and len(issues) >= max_total:
            return issues[:max_total]
        total = int(data.get("total") or 0)
        start_at += len(batch)
        if not batch or start_at >= total:
            break
    return issues


def user_search(query: str, *, max_results: int = 50) -> List[Dict[str, Any]]:
    """Search users. Cloud uses ``query``; Server/DC still accepts ``username``."""
    cfg = load_config()
    if cfg.is_cloud:
        response = get(
            "rest/api/3/user/search",
            params={"query": query, "maxResults": max_results},
        )
    else:
        response = get(
            "rest/api/2/user/search",
            params={"username": query, "maxResults": max_results},
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to search users: {response.status_code} {response.text[:400]}"
        )
    data = response.json()
    return data if isinstance(data, list) else []


def format_user_row(user: Dict[str, Any]) -> List[str]:
    """Normalize Cloud (accountId) and Server (key/name) user objects for display."""
    return [
        str(user.get("accountId") or user.get("key") or "-"),
        str(user.get("displayName") or user.get("name") or "-"),
        str(user.get("emailAddress") or "N/A"),
    ]
