"""Layer 10 — CSS Validator: extract classNames from TSX, find invalid Tailwind classes."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Known Tailwind CSS prefixes for quick validation
_TAILWIND_PREFIXES = frozenset({
    "bg", "text", "font", "p", "px", "py", "pt", "pb", "pl", "pr",
    "m", "mx", "my", "mt", "mb", "ml", "mr",
    "w", "h", "min-w", "min-h", "max-w", "max-h",
    "flex", "grid", "gap", "col", "row",
    "border", "rounded", "shadow", "ring",
    "opacity", "z", "top", "right", "bottom", "left",
    "inset", "overflow", "cursor", "pointer-events",
    "transition", "duration", "ease", "delay", "animate",
    "rotate", "scale", "translate", "skew", "origin",
    "space", "divide", "place", "items", "justify", "self", "content",
    "sr", "not-sr",
    "absolute", "relative", "fixed", "sticky", "static",
    "block", "inline", "hidden", "visible", "invisible",
    "container", "prose",
    "sm", "md", "lg", "xl", "2xl",
    "hover", "focus", "active", "disabled", "first", "last", "odd", "even",
    "dark", "group", "peer",
    "aspect", "object", "break", "decoration",
    "underline", "overline", "line-through", "no-underline",
    "uppercase", "lowercase", "capitalize", "normal-case",
    "truncate", "whitespace", "leading", "tracking",
    "list", "table", "caption", "accent",
    "appearance", "outline", "resize", "select", "snap",
    "scroll", "touch", "will-change",
})

# Regex for extracting className values from JSX/TSX
_CLASSNAME_RE = re.compile(
    r'className\s*=\s*["\']([^"\']+)["\']',
)
_CLASSNAME_TEMPLATE_RE = re.compile(
    r"className\s*=\s*\{`([^`]+)`\}",
)
_CN_HELPER_RE = re.compile(
    r'(?:cn|clsx|classNames?)\(\s*["\']([^"\']+)["\']',
)


@dataclass
class CSSValidationResult:
    valid: bool
    invalid_classes: list[dict] = field(default_factory=list)
    total_classes: int = 0
    files_checked: int = 0


def validate_css_classes(generated_files: dict[str, str]) -> CSSValidationResult:
    """Extract classNames from TSX files and validate them.

    Args:
        generated_files: Dict of filename → content from the build.

    Returns:
        CSSValidationResult with invalid_classes listing any problems.
    """
    all_invalid: list[dict] = []
    total_classes = 0
    files_checked = 0

    for path, content in generated_files.items():
        if not isinstance(content, str):
            continue
        if not path.endswith((".tsx", ".jsx")):
            continue

        files_checked += 1
        classes = _extract_classes(content)
        total_classes += len(classes)

        for cls in classes:
            if not _is_valid_class(cls):
                all_invalid.append({
                    "file": path,
                    "class": cls,
                    "reason": _classify_invalid(cls),
                })

    valid = len(all_invalid) == 0

    if not valid:
        logger.warning(
            "CSS validator: %d invalid classes found across %d files",
            len(all_invalid), files_checked,
        )

    return CSSValidationResult(
        valid=valid,
        invalid_classes=all_invalid,
        total_classes=total_classes,
        files_checked=files_checked,
    )


def _extract_classes(content: str) -> list[str]:
    """Extract all CSS class names from TSX content."""
    classes: list[str] = []

    for pattern in (_CLASSNAME_RE, _CLASSNAME_TEMPLATE_RE, _CN_HELPER_RE):
        for m in pattern.finditer(content):
            raw = m.group(1)
            # Split on whitespace, filter out template expressions
            for cls in raw.split():
                cls = cls.strip()
                if cls and not cls.startswith("$") and not cls.startswith("{"):
                    classes.append(cls)

    return classes


def _is_valid_class(cls: str) -> bool:
    """Check if a CSS class looks like a valid Tailwind class or custom class."""
    # Allow arbitrary value syntax: bg-[#color], w-[200px], etc.
    if "[" in cls and "]" in cls:
        return True

    # Allow negative prefix
    check = cls.lstrip("-")
    if not check:
        return False

    # Strip responsive/state prefix: sm:, md:, hover:, dark:, etc.
    while ":" in check:
        prefix, _, check = check.partition(":")
        if not check:
            return False

    # Strip important modifier
    check = check.lstrip("!")

    # Check against known prefixes
    base = check.split("-")[0] if "-" in check else check

    # Allow common standalone classes
    if base in _TAILWIND_PREFIXES:
        return True

    # Allow common full classes
    if check in _STANDALONE_CLASSES:
        return True

    # Allow custom utility classes (single word, no weird chars)
    if re.match(r"^[a-z][a-z0-9-]*$", check):
        # Could be a custom class — allow but don't flag
        return True

    return False


_STANDALONE_CLASSES = frozenset({
    "container", "prose", "sr-only", "not-sr-only",
    "truncate", "antialiased", "subpixel-antialiased",
    "italic", "not-italic", "ordinal", "slashed-zero",
    "lining-nums", "oldstyle-nums", "proportional-nums", "tabular-nums",
    "diagonal-fractions", "stacked-fractions",
    "overscroll-auto", "overscroll-contain", "overscroll-none",
    "isolate", "isolation-auto",
    "float-right", "float-left", "float-none", "clear-both",
    "box-border", "box-content",
})


def _classify_invalid(cls: str) -> str:
    """Classify why a class is invalid."""
    if re.search(r"[A-Z]", cls):
        return "contains_uppercase"
    if " " in cls:
        return "contains_space"
    if re.search(r"[^a-z0-9\-_:/!.\[\]#%]", cls):
        return "invalid_characters"
    return "unknown_utility"
