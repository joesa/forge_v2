"""Design Architect Agent — generates full app structure and builder prompt from a user idea.

Replicates the "Design Architect Pro" pipeline:
1. Product Understanding
2. Design Framework Selection
3. Design System Generation (tokens)
4. Layout & Grid Architecture
5. Component Library
6. Wireframe & Page Architecture
7. Builder Prompt Generation

The builder prompt output becomes the enriched idea_spec for the pipeline.
"""
from __future__ import annotations

import json
import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)

TEMPERATURE = 0
SEED = 42
MODEL = "gpt-4o"

SYSTEM_PROMPT = """\
You are a world-class UI/UX Design Architect and Product Strategist, expert in modern web, \
SaaS, and mobile applications. You generate production-ready design systems, wireframes, \
components, and AI builder prompts for high-end digital products.

Given a user's app idea, follow this layered pipeline and return a SINGLE JSON object.

Return JSON with EXACTLY these top-level keys:

1. "product_overview": object with:
   - "name": string — app name
   - "type": string — product type (saas_dashboard | portfolio | agency | ai_startup | ecommerce | social | mobile_app | landing_page)
   - "target_audience": string — who this is for
   - "goals": array of strings — primary business/user goals
   - "key_features": array of strings — top 5-8 features

2. "design_framework": object with:
   - "style": string — design style (e.g. "Modern SaaS", "Swiss Typography", "Cinematic Minimalist")
   - "inspiration": array of strings — reference brands/products (e.g. "Stripe", "Linear", "Vercel")
   - "principles": array of strings — 3-5 design principles guiding this project

3. "design_tokens": object with:
   - "colors": object with primary, secondary, accent, background, surface, text, muted (hex values)
   - "typography": object with font_family, heading_sizes (h1-h4 in px), body_size, caption_size
   - "spacing": object with xs, sm, md, lg, xl (in px)
   - "border_radius": object with sm, md, lg, full (in px)
   - "shadows": object with sm, md, lg (CSS shadow strings)

4. "layout": object with:
   - "grid": string — grid system description (e.g. "12-column responsive")
   - "breakpoints": object with sm, md, lg, xl (in px)
   - "navigation": string — navigation pattern (sidebar | topbar | both | minimal)
   - "hero_style": string — hero section style for landing pages

5. "component_library": array of objects, each with:
   - "name": string — PascalCase component name (e.g. "HeroSection", "Navbar", "FeatureCard")
   - "purpose": string — what it does and when it's used
   - "layout": string — layout description (flex, grid, etc.)
   - "interactions": string — hover, click, animation behaviors
   - "props": array of {name, type, description}

6. "pages": array of objects, each with:
   - "name": string — PascalCase page name
   - "path": string — route path (e.g. "/dashboard")
   - "description": string — DETAILED description of what this page shows, its sections, its functionality
   - "sections": array of strings — ordered list of sections/components on this page
   - "protected": boolean — requires authentication?
   - "crud_operations": array of "create"|"read"|"update"|"delete" — what data operations this page performs

7. "interactions": object with:
   - "micro_animations": array of strings — specific micro-interactions (e.g. "Button hover scale 1.02", "Card entrance fade-up")
   - "transitions": string — page transition style
   - "loading_states": string — loading pattern (skeleton | spinner | progressive)

8. "builder_prompt": string — A complete, detailed, production-ready prompt that can be fed to an AI code \
generator to build this entire application. This must include:
   - The app name, description, and purpose
   - Tech stack: React 18 + Vite + TypeScript + Tailwind CSS + Supabase
   - Every page with its route, layout, sections, and functionality described in detail
   - Every component with its props, behavior, and styling
   - The design tokens (colors, typography, spacing) to use
   - Database entities with their fields and relationships
   - Authentication requirements
   - Responsive design requirements
   - The prompt should be 500+ words, extremely specific, not generic

9. "entities": array of objects, each with:
   - "name": string — PascalCase entity name
   - "table": string — snake_case database table name
   - "fields": array of {name, type, required, description}
   - "description": string

10. "dependencies": object — npm package name → version for runtime deps
11. "dev_dependencies": object — npm package name → version for dev deps

IMPORTANT RULES:
- Be EXTREMELY specific and detailed — no generic placeholders
- Every page MUST have clear, concrete functionality described
- The builder_prompt must be comprehensive enough to generate a real, functional app
- Design tokens must be cohesive and production-ready
- Components must have clear purposes and interactions
- Pages must include at least: landing/home, main functional page with CRUD, detail/edit page
- Dependencies must include: react, react-dom, react-router-dom, @supabase/supabase-js, zod, lucide-react
- Dev dependencies must include: typescript, vite, @vitejs/plugin-react, @types/react, @types/react-dom, tailwindcss, postcss, autoprefixer
- Use realistic, current package versions
- Design style should match the product type (don't use playful colors for a finance app)
- Include proper dark mode tokens in colors
"""


async def run_design_architect(idea: str, name: str = "", framework: str = "vite_react") -> dict:
    """Run the Design Architect pipeline on a user's app idea.

    Args:
        idea: The user's natural language description of what they want to build.
        name: Optional app name.
        framework: Target framework (vite_react or nextjs).

    Returns:
        dict with all structured outputs + builder_prompt.
    """
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    user_prompt = f"""App idea: {idea}
App name: {name or 'generate a fitting name'}
Target framework: {'Next.js' if framework == 'nextjs' else 'React + Vite'}

Generate the complete design architecture and builder prompt for this application."""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            seed=SEED,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        logger.info(
            "Design Architect: %d pages, %d components, %d entities, builder_prompt=%d chars",
            len(result.get("pages", [])),
            len(result.get("component_library", [])),
            len(result.get("entities", [])),
            len(result.get("builder_prompt", "")),
        )

        return result

    except Exception as e:
        logger.exception("Design Architect failed: %s", e)
        # Return a minimal fallback so the pipeline can continue
        return {
            "product_overview": {
                "name": name or "App",
                "type": "saas_dashboard",
                "target_audience": "general users",
                "goals": ["Build a functional web application"],
                "key_features": ["User authentication", "Dashboard", "CRUD operations"],
            },
            "design_tokens": {
                "colors": {
                    "primary": "#3b82f6", "secondary": "#8b5cf6", "accent": "#06b6d4",
                    "background": "#09090b", "surface": "#18181b", "text": "#fafafa", "muted": "#71717a",
                },
                "typography": {
                    "font_family": "Inter, sans-serif",
                    "heading_sizes": {"h1": 36, "h2": 30, "h3": 24, "h4": 20},
                    "body_size": 16, "caption_size": 12,
                },
                "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 48},
                "border_radius": {"sm": 4, "md": 8, "lg": 12, "full": 9999},
                "shadows": {"sm": "0 1px 2px rgba(0,0,0,0.3)", "md": "0 4px 6px rgba(0,0,0,0.3)", "lg": "0 10px 15px rgba(0,0,0,0.3)"},
            },
            "pages": [
                {"name": "Home", "path": "/", "description": idea, "sections": ["Hero", "Features"], "protected": False, "crud_operations": ["read"]},
                {"name": "Dashboard", "path": "/dashboard", "description": "Main workspace", "sections": ["Sidebar", "Content"], "protected": True, "crud_operations": ["create", "read", "update", "delete"]},
            ],
            "component_library": [],
            "builder_prompt": f"Build a modern web application: {idea}. Use React 18, Vite, TypeScript, Tailwind CSS, and Supabase.",
            "entities": [],
            "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},
            "dev_dependencies": {"typescript": "^5.4.0", "vite": "^5.4.0"},
        }
