"""Layer 6 — Error Boundary Injector.

Wraps all page-level React components in ErrorBoundary.
Called by ReviewAgent ONLY — never in individual build agents.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── ErrorBoundary component source ───────────────────────────────

ERROR_BOUNDARY_COMPONENT = """\
import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary]', error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2 style={{ color: '#ef4444', fontSize: '1.25rem', fontWeight: 'bold' }}>
            Something went wrong
          </h2>
          <p style={{ color: '#9ca3af', marginTop: '0.5rem' }}>
            {this.state.error?.message ?? 'An unexpected error occurred'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              background: '#6d28d9',
              color: '#fff',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
"""

# ── Public API ───────────────────────────────────────────────────


def inject_error_boundaries(
    generated_files: dict[str, str],
) -> dict:
    """Inject ErrorBoundary wrappers around all page-level components.

    Called by ReviewAgent ONLY — never in individual build agents 1-9.

    Returns {
        "files": dict[str, str],  # Updated file contents
        "injected_count": int,
        "error_boundary_file": str,  # Path to the ErrorBoundary component
        "pages_wrapped": list[str],  # Which pages were wrapped
    }
    """
    updated_files = dict(generated_files)
    pages_wrapped: list[str] = []

    # Determine component directory
    error_boundary_path = _find_component_dir(generated_files) + "/ErrorBoundary.tsx"

    # Always ensure ErrorBoundary component exists
    if error_boundary_path not in updated_files:
        updated_files[error_boundary_path] = ERROR_BOUNDARY_COMPONENT

    # Find all page files
    page_files = _find_page_files(generated_files)

    for filepath in page_files:
        content = updated_files[filepath]

        # Skip if already wrapped
        if "ErrorBoundary" in content:
            continue

        wrapped = _wrap_page_in_boundary(filepath, content, error_boundary_path)
        if wrapped != content:
            updated_files[filepath] = wrapped
            pages_wrapped.append(filepath)

    logger.info(
        "Injected ErrorBoundary into %d/%d pages",
        len(pages_wrapped), len(page_files),
    )

    return {
        "files": updated_files,
        "injected_count": len(pages_wrapped),
        "error_boundary_file": error_boundary_path,
        "pages_wrapped": pages_wrapped,
    }


# ── Internal helpers ─────────────────────────────────────────────

# Match: export default function PageName(...)  or  export default PageName
_DEFAULT_EXPORT_FN = re.compile(
    r'export\s+default\s+function\s+(\w+)\s*\([^)]*\)\s*\{',
)
_DEFAULT_EXPORT_CONST = re.compile(
    r'export\s+default\s+(\w+)\s*;',
)
_CONST_COMPONENT = re.compile(
    r'(?:export\s+)?const\s+(\w+)\s*(?::\s*React\.FC[^=]*)?\s*=\s*(?:\([^)]*\)|)\s*(?:=>|\{)',
)


def _find_component_dir(files: dict[str, str]) -> str:
    """Find the components directory from existing file paths."""
    for fp in files:
        if "/components/" in fp:
            idx = fp.index("/components/")
            return fp[:idx + len("/components")]

    # Fallback
    return "src/components"


def _find_page_files(files: dict[str, str]) -> list[str]:
    """Identify page-level files from generated files."""
    page_files: list[str] = []
    for filepath in files:
        lower = filepath.lower()
        if any(kw in lower for kw in ("/pages/", "/views/", "/screens/")):
            if lower.endswith((".tsx", ".jsx")):
                page_files.append(filepath)
        elif lower.endswith("/page.tsx") or lower.endswith("/page.jsx"):
            page_files.append(filepath)
    return page_files


def _wrap_page_in_boundary(
    filepath: str,
    content: str,
    error_boundary_path: str,
) -> str:
    """Wrap a page component's default export in ErrorBoundary."""
    # Calculate relative import path
    import_path = _relative_import(filepath, error_boundary_path)

    # Try: export default function PageName(...) {
    match = _DEFAULT_EXPORT_FN.search(content)
    if match:
        component_name = match.group(1)
        return _wrap_function_export(content, component_name, import_path)

    # Try: export default PageName;
    match = _DEFAULT_EXPORT_CONST.search(content)
    if match:
        component_name = match.group(1)
        return _wrap_const_export(content, component_name, import_path)

    # No default export found — skip
    return content


def _wrap_function_export(
    content: str,
    component_name: str,
    import_path: str,
) -> str:
    """Wrap an `export default function X` in ErrorBoundary."""
    # Replace `export default function X` → `function X`
    content = re.sub(
        r'export\s+default\s+function\s+' + re.escape(component_name),
        f'function {component_name}',
        content,
        count=1,
    )

    # Add import at top (after existing imports)
    import_line = f"import {{ ErrorBoundary }} from '{import_path}';\n"
    content = _add_import(content, import_line)

    # Add wrapped default export at bottom
    wrapper = (
        f"\nexport default function {component_name}WithBoundary() {{\n"
        f"  return (\n"
        f"    <ErrorBoundary>\n"
        f"      <{component_name} />\n"
        f"    </ErrorBoundary>\n"
        f"  );\n"
        f"}}\n"
    )
    content = content.rstrip() + "\n" + wrapper

    return content


def _wrap_const_export(
    content: str,
    component_name: str,
    import_path: str,
) -> str:
    """Wrap an `export default X;` in ErrorBoundary."""
    # Replace `export default X;` with wrapped version
    import_line = f"import {{ ErrorBoundary }} from '{import_path}';\n"
    content = _add_import(content, import_line)

    content = re.sub(
        r'export\s+default\s+' + re.escape(component_name) + r'\s*;',
        (
            f"export default function {component_name}WithBoundary() {{\n"
            f"  return (\n"
            f"    <ErrorBoundary>\n"
            f"      <{component_name} />\n"
            f"    </ErrorBoundary>\n"
            f"  );\n"
            f"}}"
        ),
        content,
        count=1,
    )

    return content


def _add_import(content: str, import_line: str) -> str:
    """Add an import statement after existing imports."""
    # Find last import line
    lines = content.split("\n")
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i

    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1, import_line.rstrip())
    else:
        lines.insert(0, import_line.rstrip())

    return "\n".join(lines)


def _relative_import(from_file: str, to_file: str) -> str:
    """Calculate relative import path between two files."""
    from_parts = from_file.rsplit("/", 1)[0].split("/")
    to_parts = to_file.rsplit("/", 1)
    to_dir = to_parts[0].split("/")
    to_name = to_parts[1].replace(".tsx", "").replace(".ts", "")

    # Find common prefix
    common = 0
    for a, b in zip(from_parts, to_dir):
        if a == b:
            common += 1
        else:
            break

    ups = len(from_parts) - common
    downs = to_dir[common:]

    if ups == 0:
        path = "./" + "/".join(downs + [to_name])
    else:
        path = "/".join([".."] * ups + downs + [to_name])

    return path
