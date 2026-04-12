"""Layer 9 — Hotfix Agent: real implementation replacing Session 2.4 stub.

Identifies failing file from gate result, extracts relevant code,
generates targeted fix at temperature=0. Hard limit: 3 attempts.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.agents.state import PipelineState

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass
class HotfixResult:
    applied: bool
    agent_number: int
    description: str
    files_modified: list[str] = field(default_factory=list)
    attempts: int = 0
    patches: list[dict] = field(default_factory=list)


async def apply_hotfix(
    state: PipelineState,
    agent_number: int,
    gate_result: dict,
    *,
    ai_fn=None,
) -> HotfixResult:
    """Attempt to auto-fix a gate failure after a build agent.

    Args:
        state: Current pipeline state (contains generated_files).
        agent_number: Which build agent triggered the failure.
        gate_result: Gate validation result with error details.
        ai_fn: Optional async callable(prompt: str) -> str for generating fixes.
               If None, uses rule-based fixes only.

    Returns:
        HotfixResult with applied=True if any fix was successful.
    """
    generated_files = state.get("generated_files", {})
    reason = gate_result.get("reason", "")
    details = gate_result.get("details", {})
    errors = gate_result.get("errors", [])

    failing_file = _identify_failing_file(reason, details, errors, generated_files)

    result = HotfixResult(
        applied=False,
        agent_number=agent_number,
        description="",
        files_modified=[],
        attempts=0,
        patches=[],
    )

    if not failing_file:
        result.description = "could_not_identify_failing_file"
        logger.warning(
            "Hotfix agent %d: cannot identify failing file from gate result",
            agent_number,
        )
        return result

    original_content = generated_files.get(failing_file, "")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result.attempts = attempt
        current_content = generated_files.get(failing_file, original_content)

        fix = await _generate_fix(
            failing_file=failing_file,
            content=current_content,
            reason=reason,
            errors=errors,
            details=details,
            ai_fn=ai_fn,
        )

        if fix is None:
            logger.info(
                "Hotfix agent %d attempt %d: no fix generated for %s",
                agent_number, attempt, failing_file,
            )
            continue

        patched_content = fix["patched_content"]
        patch_desc = fix["description"]

        if patched_content == current_content:
            logger.info(
                "Hotfix agent %d attempt %d: fix produced identical content",
                agent_number, attempt,
            )
            continue

        # Apply the patch
        generated_files[failing_file] = patched_content
        result.patches.append({
            "attempt": attempt,
            "file": failing_file,
            "description": patch_desc,
        })
        result.files_modified = [failing_file]
        result.applied = True
        result.description = patch_desc

        logger.info(
            "Hotfix agent %d attempt %d: applied fix to %s — %s",
            agent_number, attempt, failing_file, patch_desc,
        )
        return result

    result.description = f"exhausted_{MAX_ATTEMPTS}_attempts"
    logger.warning(
        "Hotfix agent %d: exhausted %d attempts for %s",
        agent_number, MAX_ATTEMPTS, failing_file,
    )
    return result


def _identify_failing_file(
    reason: str,
    details: dict,
    errors: list,
    generated_files: dict[str, str],
) -> str | None:
    """Identify the file that caused the gate failure."""
    # Check details for explicit file reference
    if isinstance(details, dict):
        for key in ("file", "failing_file", "path", "filename"):
            if key in details and details[key] in generated_files:
                return details[key]

    # Check errors list for file references
    if isinstance(errors, list):
        for err in errors:
            if isinstance(err, dict):
                for key in ("file", "path", "filename"):
                    if key in err and err[key] in generated_files:
                        return err[key]
            elif isinstance(err, str):
                match = _extract_file_from_error(err, generated_files)
                if match:
                    return match

    # Try extracting file path from reason string
    if reason:
        match = _extract_file_from_error(reason, generated_files)
        if match:
            return match

    return None


_FILE_PATH_RE = re.compile(r"[\w/.-]+\.\w{1,4}")


def _extract_file_from_error(text: str, generated_files: dict[str, str]) -> str | None:
    """Extract a file path from an error string that matches a generated file."""
    for m in _FILE_PATH_RE.finditer(text):
        candidate = m.group(0)
        if candidate in generated_files:
            return candidate
    return None


async def _generate_fix(
    *,
    failing_file: str,
    content: str,
    reason: str,
    errors: list,
    details: dict,
    ai_fn=None,
) -> dict | None:
    """Generate a fix for the failing file.

    Uses ai_fn if provided, otherwise falls back to rule-based fixes.
    Returns {"patched_content": str, "description": str} or None.
    """
    # Try AI-powered fix if ai_fn is available
    if ai_fn is not None:
        prompt = _build_fix_prompt(failing_file, content, reason, errors)
        try:
            ai_response = await ai_fn(prompt)
            if ai_response and ai_response.strip():
                # Extract code from AI response
                patched = _extract_code_block(ai_response, content)
                if patched and patched != content:
                    return {
                        "patched_content": patched,
                        "description": f"ai_fix: {reason[:80]}",
                    }
        except Exception as e:
            logger.warning("AI fix generation failed: %s", e)

    # Fall back to rule-based fixes
    return _apply_rule_based_fix(failing_file, content, reason, errors, details)


def _build_fix_prompt(
    failing_file: str,
    content: str,
    reason: str,
    errors: list,
) -> str:
    """Build the prompt for AI-powered fix generation."""
    error_text = "\n".join(
        str(e) for e in errors[:5]
    ) if errors else reason

    return (
        f"Fix the following file that failed validation.\n"
        f"File: {failing_file}\n"
        f"Error: {error_text}\n\n"
        f"Current content:\n```\n{content}\n```\n\n"
        f"Return ONLY the corrected file content, nothing else."
    )


def _extract_code_block(response: str, fallback: str) -> str:
    """Extract code from a markdown code block, or return full response."""
    # Try to find fenced code block
    match = re.search(r"```[\w]*\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    # If response looks like code (not prose), use it directly
    lines = response.strip().split("\n")
    if len(lines) > 1 and not lines[0].startswith(("Here", "The", "I ")):
        return response.strip() + "\n"
    return fallback


def _apply_rule_based_fix(
    failing_file: str,
    content: str,
    reason: str,
    errors: list,
    details: dict,
) -> dict | None:
    """Apply rule-based fixes for common issues."""
    # Fix: missing export
    if "missing_export" in reason or "not exported" in reason.lower():
        if "export" not in content and content.strip():
            first_line = content.split("\n")[0]
            if first_line.startswith(("function ", "const ", "class ")):
                patched = content.replace(first_line, f"export {first_line}", 1)
                return {
                    "patched_content": patched,
                    "description": "added_missing_export",
                }

    # Fix: missing import
    if "undefined" in reason.lower() or "not defined" in reason.lower():
        if isinstance(details, dict):
            symbol = details.get("symbol", "")
            source = details.get("source", "")
            if symbol and source:
                import_line = f'import {{ {symbol} }} from "{source}";\n'
                patched = import_line + content
                return {
                    "patched_content": patched,
                    "description": f"added_import_{symbol}_from_{source}",
                }

    # Fix: syntax error — missing semicolon (TypeScript/JavaScript)
    if failing_file.endswith((".ts", ".tsx", ".js", ".jsx")):
        if "semicolon" in reason.lower() or "expected ;" in reason.lower():
            if isinstance(errors, list) and errors:
                first_err = errors[0] if isinstance(errors[0], str) else str(errors[0])
                line_match = re.search(r"line\s*(\d+)", first_err, re.IGNORECASE)
                if line_match:
                    line_num = int(line_match.group(1)) - 1
                    lines = content.split("\n")
                    if 0 <= line_num < len(lines):
                        line = lines[line_num].rstrip()
                        if not line.endswith((";", "{", "}", ",", "(")):
                            lines[line_num] = line + ";"
                            return {
                                "patched_content": "\n".join(lines),
                                "description": f"added_semicolon_line_{line_num + 1}",
                            }

    # Fix: missing return type (TypeScript)
    if "return_type" in reason.lower() and failing_file.endswith((".ts", ".tsx")):
        if "): {" in content or "):{" in content:
            patched = re.sub(
                r"\)\s*:\s*\{",
                "): void {" if "return" not in content else "): unknown {",
                content,
                count=1,
            )
            if patched != content:
                return {
                    "patched_content": patched,
                    "description": "added_return_type_annotation",
                }

    return None
