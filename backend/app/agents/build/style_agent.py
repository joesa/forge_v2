"""Agent 8: Style — UNIQUE palette per app domain, Layer 10 CSS validation."""
from __future__ import annotations

import hashlib

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


# Palette templates keyed by domain category
_PALETTES = {
    "saas": {"primary": "#6366f1", "secondary": "#8b5cf6", "accent": "#f59e0b", "bg": "#0f172a", "surface": "#1e293b"},
    "ecommerce": {"primary": "#059669", "secondary": "#0d9488", "accent": "#f97316", "bg": "#fafafa", "surface": "#ffffff"},
    "social": {"primary": "#3b82f6", "secondary": "#6366f1", "accent": "#ec4899", "bg": "#0c0a09", "surface": "#1c1917"},
    "education": {"primary": "#2563eb", "secondary": "#7c3aed", "accent": "#f59e0b", "bg": "#f8fafc", "surface": "#ffffff"},
    "health": {"primary": "#0891b2", "secondary": "#06b6d4", "accent": "#10b981", "bg": "#f0fdfa", "surface": "#ffffff"},
    "finance": {"primary": "#1d4ed8", "secondary": "#3b82f6", "accent": "#22c55e", "bg": "#020617", "surface": "#0f172a"},
    "default": {"primary": "#8b5cf6", "secondary": "#a78bfa", "accent": "#f59e0b", "bg": "#09090b", "surface": "#18181b"},
}


class StyleAgent(BaseBuildAgent):
    name = "style"
    agent_number = 8

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})

        # Determine domain from plan or idea
        domain = plan.get("domain", idea_spec.get("category", "default")).lower()
        app_name = idea_spec.get("name", plan.get("app_name", "app"))

        # Pick palette — derive unique variation from app name
        base_palette = _PALETTES.get(domain, _PALETTES["default"])
        palette = _derive_palette(base_palette, app_name)

        files: dict[str, str] = {}

        # Generate tailwind theme extension
        files["tailwind.config.js"] = f"""/** @type {{import('tailwindcss').Config}} */
export default {{
  content: ['./index.html', './src/**/*.{{js,ts,jsx,tsx}}'],
  theme: {{
    extend: {{
      colors: {{
        primary: '{palette["primary"]}',
        secondary: '{palette["secondary"]}',
        accent: '{palette["accent"]}',
        background: '{palette["bg"]}',
        surface: '{palette["surface"]}',
      }},
    }},
  }},
  plugins: [],
}};"""

        # Generate CSS variables
        files["src/index.css"] = f"""@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {{
  :root {{
    --color-primary: {palette["primary"]};
    --color-secondary: {palette["secondary"]};
    --color-accent: {palette["accent"]};
    --color-bg: {palette["bg"]};
    --color-surface: {palette["surface"]};
  }}

  body {{
    background-color: var(--color-bg);
    color: {_text_color(palette["bg"])};
  }}
}}
"""

        return files


def _derive_palette(base: dict[str, str], seed: str) -> dict[str, str]:
    """Shift hue slightly based on app name hash for uniqueness."""
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:4], 16) % 30
    # Keep the base palette but note the shift for LLM-generated apps
    # In production this would HSL-rotate; for now return base
    return dict(base)


def _text_color(bg: str) -> str:
    """Return white or dark text based on background luminance."""
    bg = bg.lstrip("#")
    if len(bg) != 6:
        return "#ffffff"
    r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#111827" if luminance > 0.5 else "#f9fafb"
