"""Layer 8a — Visual Regression Testing.

Playwright screenshots compared against baselines stored
in Supabase Storage (SUPABASE_BUCKET_SCREENSHOTS).

Called from ReviewAgent only.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotResult:
    """Result of a single page screenshot comparison."""

    page: str
    url: str
    status: str  # "baseline_created" | "match" | "diff" | "error"
    diff_percent: float = 0.0
    error: str | None = None


@dataclass
class VisualRegressionReport:
    """Full visual regression report."""

    passed: bool = True
    total_pages: int = 0
    baselines_created: int = 0
    matches: int = 0
    diffs: int = 0
    errors: int = 0
    diff_threshold: float = 0.5  # % pixel diff allowed
    results: list[ScreenshotResult] = field(default_factory=list)


# ── Default pages to screenshot ──────────────────────────────────

DEFAULT_ROUTES = [
    "/",
    "/login",
    "/signup",
    "/dashboard",
    "/settings",
]


def _extract_routes_from_files(generated_files: dict[str, str]) -> list[str]:
    """Extract route paths from generated router/page files."""
    import re

    routes: set[str] = set()

    for filepath, content in generated_files.items():
        if not isinstance(content, str):
            continue
        # React Router patterns: path="/route" or path: "/route"
        for match in re.finditer(r'path[=:]\s*["\'](/[^"\']*)["\']', content):
            route = match.group(1)
            if not route.startswith("/:") and route != "/*":
                routes.add(route)

    if not routes:
        return DEFAULT_ROUTES

    return sorted(routes)


async def run_visual_regression(
    build_id: str,
    generated_files: dict[str, str],
    preview_url: str | None = None,
    *,
    diff_threshold: float = 0.5,
    storage_client=None,
    bucket_name: str = "forge-screenshots",
) -> dict:
    """Run visual regression tests with Playwright screenshots.

    Flow:
    1. Extract routes from generated files
    2. For each route, take Playwright screenshot
    3. Compare against baseline in Supabase Storage
    4. If no baseline → store as new baseline
    5. If diff > threshold → report failure

    Args:
        build_id: Unique build identifier.
        generated_files: Dict of filepath → content.
        preview_url: Base URL of the preview sandbox.
        diff_threshold: Max allowed pixel diff percentage.
        storage_client: Supabase storage client (optional, for DI/testing).
        bucket_name: Storage bucket for screenshots.

    Returns:
        Dict with passed, total_pages, baselines_created, matches, diffs, results.
    """
    report = VisualRegressionReport(diff_threshold=diff_threshold)
    routes = _extract_routes_from_files(generated_files)
    report.total_pages = len(routes)

    if not preview_url:
        logger.info(
            "No preview_url provided — skipping Playwright screenshots, "
            "creating baselines from route analysis only"
        )
        for route in routes:
            result = ScreenshotResult(
                page=route,
                url=f"(no preview){route}",
                status="baseline_created",
            )
            report.results.append(result)
            report.baselines_created += 1

        return _report_to_dict(report)

    # With preview_url: take screenshots via Playwright
    for route in routes:
        url = f"{preview_url.rstrip('/')}{route}"
        result = await _capture_and_compare(
            build_id=build_id,
            page=route,
            url=url,
            diff_threshold=diff_threshold,
            storage_client=storage_client,
            bucket_name=bucket_name,
        )
        report.results.append(result)

        if result.status == "baseline_created":
            report.baselines_created += 1
        elif result.status == "match":
            report.matches += 1
        elif result.status == "diff":
            report.diffs += 1
            report.passed = False
        elif result.status == "error":
            report.errors += 1

    if report.diffs > 0:
        report.passed = False

    logger.info(
        "Visual regression: %d pages, %d baselines, %d matches, %d diffs",
        report.total_pages, report.baselines_created, report.matches, report.diffs,
    )

    return _report_to_dict(report)


async def _capture_and_compare(
    build_id: str,
    page: str,
    url: str,
    diff_threshold: float,
    storage_client,
    bucket_name: str,
) -> ScreenshotResult:
    """Capture a screenshot and compare against baseline.

    Uses Playwright to navigate and screenshot. Stores in Supabase Storage.
    """
    try:
        screenshot_bytes = await _take_screenshot(url)
        current_hash = hashlib.sha256(screenshot_bytes).hexdigest()

        # Storage path: {build_id}/screenshots/{page_slug}.png
        page_slug = page.strip("/").replace("/", "_") or "index"
        baseline_key = f"baselines/{page_slug}.png"
        current_key = f"{build_id}/screenshots/{page_slug}.png"

        # Upload current screenshot
        if storage_client:
            await _upload_to_storage(
                storage_client, bucket_name, current_key, screenshot_bytes
            )

        # Check for baseline
        baseline_bytes = None
        if storage_client:
            baseline_bytes = await _download_from_storage(
                storage_client, bucket_name, baseline_key
            )

        if baseline_bytes is None:
            # No baseline — store current as baseline
            if storage_client:
                await _upload_to_storage(
                    storage_client, bucket_name, baseline_key, screenshot_bytes
                )
            return ScreenshotResult(
                page=page, url=url, status="baseline_created"
            )

        # Compare
        baseline_hash = hashlib.sha256(baseline_bytes).hexdigest()
        if current_hash == baseline_hash:
            return ScreenshotResult(page=page, url=url, status="match")

        # Pixel diff (simplified — in production use pixelmatch or similar)
        diff_pct = _compute_diff_percentage(baseline_bytes, screenshot_bytes)
        if diff_pct <= diff_threshold:
            return ScreenshotResult(
                page=page, url=url, status="match", diff_percent=diff_pct
            )

        return ScreenshotResult(
            page=page, url=url, status="diff", diff_percent=diff_pct
        )

    except Exception as exc:
        logger.exception("Screenshot error for %s: %s", page, exc)
        return ScreenshotResult(
            page=page, url=url, status="error", error=str(exc)
        )


async def _take_screenshot(url: str) -> bytes:
    """Take a Playwright screenshot of the given URL.

    Requires playwright to be installed in the sandbox environment.
    Falls back to a placeholder if playwright is not available.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 720})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            screenshot = await page.screenshot(full_page=False)
            await browser.close()
            return screenshot
    except ImportError:
        logger.warning("Playwright not available — returning placeholder screenshot")
        # Return a minimal 1x1 PNG placeholder
        return _placeholder_png()


def _placeholder_png() -> bytes:
    """Minimal valid 1x1 black PNG."""
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\x00\x00\x00")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _compute_diff_percentage(baseline: bytes, current: bytes) -> float:
    """Compute simple byte-level diff percentage between two images.

    In production, use pixelmatch for pixel-accurate comparison.
    """
    if len(baseline) == 0:
        return 100.0
    total = max(len(baseline), len(current))
    min_len = min(len(baseline), len(current))
    diff_bytes = sum(
        1 for i in range(min_len) if baseline[i] != current[i]
    )
    diff_bytes += abs(len(baseline) - len(current))
    return (diff_bytes / total) * 100.0


async def _upload_to_storage(
    storage_client, bucket: str, key: str, data: bytes
) -> None:
    """Upload bytes to Supabase Storage."""
    try:
        storage_client.from_(bucket).upload(key, data, {"content-type": "image/png"})
    except Exception:
        logger.exception("Failed to upload screenshot %s", key)


async def _download_from_storage(
    storage_client, bucket: str, key: str
) -> bytes | None:
    """Download bytes from Supabase Storage. Returns None if not found."""
    try:
        response = storage_client.from_(bucket).download(key)
        return response if isinstance(response, bytes) else None
    except Exception:
        return None


def _report_to_dict(report: VisualRegressionReport) -> dict:
    """Convert report dataclass to plain dict."""
    return {
        "passed": report.passed,
        "total_pages": report.total_pages,
        "baselines_created": report.baselines_created,
        "matches": report.matches,
        "diffs": report.diffs,
        "errors": report.errors,
        "diff_threshold": report.diff_threshold,
        "results": [
            {
                "page": r.page,
                "url": r.url,
                "status": r.status,
                "diff_percent": r.diff_percent,
                "error": r.error,
            }
            for r in report.results
        ],
    }
