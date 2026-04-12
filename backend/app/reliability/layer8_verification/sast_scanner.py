"""Layer 8b — SAST Scanner.

Semgrep + detect-secrets analysis on generated code.
Severity mapping: critical/high → Gate G11 failure.

Called from ReviewAgent only.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Severity levels ──────────────────────────────────────────────
SEVERITY_FAIL = {"CRITICAL", "HIGH"}  # These fail G11
SEVERITY_WARN = {"MEDIUM", "LOW"}  # These are warnings only


@dataclass
class SASTFinding:
    """A single SAST finding."""

    rule_id: str
    file: str
    line: int
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    message: str
    category: str  # "semgrep" | "secrets"


@dataclass
class SASTReport:
    """Full SAST scan report."""

    passed: bool = True
    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    findings: list[SASTFinding] = field(default_factory=list)


# ── Built-in patterns (no external tools needed) ─────────────────

_SECRET_PATTERNS: list[tuple[str, str]] = [
    ("hardcoded_api_key", r'(?:api[_-]?key|apikey)\s*[:=]\s*["\'][a-zA-Z0-9_\-]{20,}["\']'),
    ("hardcoded_secret", r'(?:secret|password|passwd|token)\s*[:=]\s*["\'][^"\']{8,}["\']'),
    ("aws_access_key", r'AKIA[0-9A-Z]{16}'),
    ("private_key_pem", r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'),
    ("jwt_token", r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'),
    ("supabase_service_role", r'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'),
]

_SECURITY_PATTERNS: list[tuple[str, str, str]] = [
    # (rule_id, pattern, severity)
    ("sql_injection", r'(?:query|execute)\s*\(\s*f["\']|\.raw\s*\(\s*f["\']|\+\s*(?:req|request)', "CRITICAL"),
    ("xss_dangerously_set", r'dangerouslySetInnerHTML\s*=\s*\{', "HIGH"),
    ("eval_usage", r'\beval\s*\(', "CRITICAL"),
    ("exec_usage", r'\bexec\s*\(', "HIGH"),
    ("hardcoded_cors_star", r'cors.*origin.*["\']?\*["\']?|allow_origins.*\*', "MEDIUM"),
    ("no_auth_check", r'@app\.(?:get|post|put|delete|patch)\s*\([^)]*\)\s*\nasync\s+def\s+\w+\s*\([^)]*\)(?:(?!Depends|get_current_user|require_auth).)*:', "MEDIUM"),
    ("subprocess_shell", r'subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True', "CRITICAL"),
    ("os_system_call", r'os\.system\s*\(', "HIGH"),
    ("pickle_load", r'pickle\.loads?\s*\(', "HIGH"),
    ("yaml_unsafe_load", r'yaml\.load\s*\([^)]*(?!Loader)', "HIGH"),
    ("debug_mode_enabled", r'DEBUG\s*[:=]\s*True|debug\s*[:=]\s*true|NODE_ENV.*development', "LOW"),
    ("console_log_sensitive", r'console\.log\s*\(.*(?:password|secret|token|key)', "MEDIUM"),
]


def _scan_secrets(filepath: str, content: str) -> list[SASTFinding]:
    """Scan a single file for hardcoded secrets."""
    findings: list[SASTFinding] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
            continue
        # Skip imports/requires
        if "import " in stripped or "require(" in stripped:
            continue
        # Skip env references (these are safe)
        if "process.env" in line or "os.environ" in line or "os.getenv" in line:
            continue

        for rule_id, pattern in _SECRET_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(SASTFinding(
                    rule_id=rule_id,
                    file=filepath,
                    line=line_no,
                    severity="HIGH",
                    message=f"Possible hardcoded secret detected: {rule_id}",
                    category="secrets",
                ))

    return findings


def _scan_security(filepath: str, content: str) -> list[SASTFinding]:
    """Scan a single file for security anti-patterns."""
    findings: list[SASTFinding] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, 1):
        for rule_id, pattern, severity in _SECURITY_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(SASTFinding(
                    rule_id=rule_id,
                    file=filepath,
                    line=line_no,
                    severity=severity,
                    message=f"Security issue: {rule_id}",
                    category="semgrep",
                ))

    return findings


async def run_sast_scan(
    generated_files: dict[str, str],
    *,
    use_external_tools: bool = False,
) -> dict:
    """Run SAST analysis on generated files.

    Uses built-in pattern matching. When use_external_tools=True,
    also runs Semgrep and detect-secrets if available.

    critical/high findings → G11 failure.

    Args:
        generated_files: Dict of filepath → content.
        use_external_tools: Whether to try running semgrep/detect-secrets.

    Returns:
        Dict with passed, total_findings, critical, high, medium, low, findings.
    """
    report = SASTReport()
    all_findings: list[SASTFinding] = []

    # Scan each file with built-in patterns
    for filepath, content in generated_files.items():
        if not isinstance(content, str):
            continue
        if not _is_scannable(filepath):
            continue

        all_findings.extend(_scan_secrets(filepath, content))
        all_findings.extend(_scan_security(filepath, content))

    # Optional: external tools
    if use_external_tools:
        external = await _run_external_tools(generated_files)
        all_findings.extend(external)

    # De-duplicate findings
    seen: set[str] = set()
    unique: list[SASTFinding] = []
    for f in all_findings:
        key = f"{f.rule_id}:{f.file}:{f.line}"
        if key not in seen:
            seen.add(key)
            unique.append(f)

    report.findings = unique
    report.total_findings = len(unique)
    report.critical = sum(1 for f in unique if f.severity == "CRITICAL")
    report.high = sum(1 for f in unique if f.severity == "HIGH")
    report.medium = sum(1 for f in unique if f.severity == "MEDIUM")
    report.low = sum(1 for f in unique if f.severity == "LOW")

    # critical/high → G11 failure
    if report.critical > 0 or report.high > 0:
        report.passed = False

    logger.info(
        "SAST scan: %d findings (C:%d H:%d M:%d L:%d) — %s",
        report.total_findings, report.critical, report.high,
        report.medium, report.low,
        "PASSED" if report.passed else "FAILED",
    )

    return _report_to_dict(report)


def _is_scannable(filepath: str) -> bool:
    """Check if file should be scanned."""
    scannable_ext = {
        ".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".yaml", ".yml",
        ".env", ".toml", ".cfg", ".ini",
    }
    ext = os.path.splitext(filepath)[1].lower()
    return ext in scannable_ext


async def _run_external_tools(generated_files: dict[str, str]) -> list[SASTFinding]:
    """Run external Semgrep and detect-secrets if available.

    Writes files to a temp dir, runs tools, parses JSON output.
    """
    import asyncio

    findings: list[SASTFinding] = []
    tmp_dir = tempfile.mkdtemp(prefix="forge_sast_")

    try:
        # Write files
        for filepath, content in generated_files.items():
            full_path = os.path.join(tmp_dir, filepath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

        # Try semgrep
        findings.extend(await _run_semgrep(tmp_dir))

        # Try detect-secrets
        findings.extend(await _run_detect_secrets(tmp_dir))

    except Exception:
        logger.exception("External SAST tools failed")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return findings


async def _run_semgrep(scan_dir: str) -> list[SASTFinding]:
    """Run semgrep scan if available."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_exec(
            "semgrep", "scan", "--json", "--config=auto", scan_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode not in (0, 1):  # 1 = findings exist
            return []

        data = json.loads(stdout)
        findings: list[SASTFinding] = []
        for result in data.get("results", []):
            severity = result.get("extra", {}).get("severity", "MEDIUM").upper()
            findings.append(SASTFinding(
                rule_id=result.get("check_id", "unknown"),
                file=result.get("path", ""),
                line=result.get("start", {}).get("line", 0),
                severity=severity,
                message=result.get("extra", {}).get("message", ""),
                category="semgrep",
            ))
        return findings
    except FileNotFoundError:
        logger.debug("semgrep not found — skipping")
        return []


async def _run_detect_secrets(scan_dir: str) -> list[SASTFinding]:
    """Run detect-secrets scan if available."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_exec(
            "detect-secrets", "scan", scan_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []

        data = json.loads(stdout)
        findings: list[SASTFinding] = []
        for filepath, secrets in data.get("results", {}).items():
            for secret in secrets:
                findings.append(SASTFinding(
                    rule_id=secret.get("type", "secret"),
                    file=filepath,
                    line=secret.get("line_number", 0),
                    severity="HIGH",
                    message=f"Secret detected: {secret.get('type', 'unknown')}",
                    category="secrets",
                ))
        return findings
    except FileNotFoundError:
        logger.debug("detect-secrets not found — skipping")
        return []


def _report_to_dict(report: SASTReport) -> dict:
    """Convert report to plain dict."""
    return {
        "passed": report.passed,
        "total_findings": report.total_findings,
        "critical": report.critical,
        "high": report.high,
        "medium": report.medium,
        "low": report.low,
        "findings": [
            {
                "rule_id": f.rule_id,
                "file": f.file,
                "line": f.line,
                "severity": f.severity,
                "message": f.message,
                "category": f.category,
            }
            for f in report.findings
        ],
    }
