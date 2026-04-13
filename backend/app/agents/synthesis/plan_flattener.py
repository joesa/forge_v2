"""Flatten ComprehensivePlan into build-ready keys.

The C-Suite outputs live under plan['cpo'], plan['cto'], etc. but build agents
need top-level keys like 'pages', 'entities', 'features', 'components'.  This
module extracts those from the nested C-Suite structure so build agents get
concrete, structured inputs instead of falling back to hardcoded defaults.
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


async def flatten_plan(plan: dict, idea_spec: dict) -> dict:
    """Add build-ready keys to the plan dict in-place and return it.

    Extracts/generates:
      - pages: list of {name, path, component, description}
      - entities: list of {name, fields: [{name, type, required}]}
      - features: list of {name, description, page, crud_ops}
      - components: list of {name, props, description}
      - dependencies / dev_dependencies: npm package dicts
      - app_name, domain, auth_strategy
    """
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    system_prompt = """\
You are a senior software architect. Given a comprehensive plan produced by 8 C-Suite \
agents plus the original idea spec, extract a concrete, build-ready specification.

Return a JSON object with EXACTLY these keys:

1. "app_name": string — short lowercase name for package.json
2. "domain": string — app domain category (e.g. "productivity", "ecommerce", "social")
3. "summary": string — 1-2 sentence description of what the app does
4. "auth_strategy": "supabase" | "none"
5. "pages": array of objects, each with:
   - "name": PascalCase page name (e.g. "Dashboard")
   - "path": route path (e.g. "/dashboard")
   - "component": component name (e.g. "DashboardPage")
   - "description": what this page shows and its interactive features
   - "protected": boolean — requires auth?
6. "entities": array of objects, each with:
   - "name": PascalCase entity name (e.g. "Task", "Project")
   - "table": snake_case Supabase table name
   - "fields": array of {name, type, required, description}
     (type is TS type: "string", "number", "boolean", "Date")
   - "description": what this entity represents
7. "features": array of objects, each with:
   - "name": feature name
   - "description": what it does (be specific about UI behavior)
   - "page": which page it belongs to
   - "crud_ops": array of "create"|"read"|"update"|"delete" operations
   - "supabase_table": which entity/table it operates on
8. "components": array of objects, each with:
   - "name": PascalCase component name
   - "description": what it renders, its interactive behavior
   - "props": array of {name, type, required}
9. "dependencies": object of npm package → version (runtime)
10. "dev_dependencies": object of npm package → version (dev)

IMPORTANT RULES:
- Every page MUST have at least one feature with real CRUD operations
- Every entity MUST be used by at least one feature
- Pages must have specific, concrete descriptions — NOT generic placeholders
- Include at least: a home/landing page, a main functional page with full CRUD, a detail/edit page
- The dashboard/main page must have ADD, EDIT, DELETE functionality — not just display
- Dependencies must include: react, react-dom, react-router-dom, @supabase/supabase-js, zod
- Dev dependencies must include: typescript, vite, @vitejs/plugin-react, @types/react, @types/react-dom, tailwindcss, postcss, autoprefixer
- Generate a REAL app with REAL functionality, not a placeholder/demo"""

    user_prompt = (
        f"App idea: {idea_spec.get('description', '')}\n"
        f"App name: {idea_spec.get('name', '')}\n\n"
        f"CPO output (features, user stories, MVP scope):\n"
        f"{json.dumps(plan.get('cpo', {}), default=str)}\n\n"
        f"CTO output (tech stack, API design):\n"
        f"{json.dumps(plan.get('cto', {}), default=str)}\n\n"
        f"CDO output (UX principles, user journeys):\n"
        f"{json.dumps(plan.get('cdo', {}), default=str)}\n\n"
        f"CSO output (auth, security):\n"
        f"{json.dumps(plan.get('cso', {}), default=str)}"
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            seed=SEED,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        flattened = json.loads(raw)

        # Merge into plan (don't overwrite C-Suite outputs)
        for key in (
            "app_name", "domain", "summary", "auth_strategy",
            "pages", "entities", "features", "components",
            "dependencies", "dev_dependencies",
        ):
            if key in flattened:
                plan[key] = flattened[key]

        logger.info(
            "Plan flattened: %d pages, %d entities, %d features, %d components",
            len(plan.get("pages", [])),
            len(plan.get("entities", [])),
            len(plan.get("features", [])),
            len(plan.get("components", [])),
        )

    except Exception as e:
        logger.error("Plan flattening failed: %s", e)
        # Fallback: inject minimal structure so agents don't get empty defaults
        plan.setdefault("pages", [
            {"name": "Home", "path": "/", "component": "HomePage",
             "description": "Landing page with app overview", "protected": False},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage",
             "description": "Main workspace with full CRUD", "protected": True},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage",
             "description": "404 page", "protected": False},
        ])
        plan.setdefault("entities", [
            {"name": "Item", "table": "items",
             "fields": [
                 {"name": "id", "type": "string", "required": True},
                 {"name": "title", "type": "string", "required": True},
                 {"name": "description", "type": "string", "required": False},
                 {"name": "completed", "type": "boolean", "required": True},
                 {"name": "user_id", "type": "string", "required": True},
                 {"name": "created_at", "type": "string", "required": True},
             ],
             "description": "Main data entity"}
        ])
        plan.setdefault("features", [
            {"name": "CRUD Items", "description": "Create, read, update, delete items",
             "page": "Dashboard", "crud_ops": ["create", "read", "update", "delete"],
             "supabase_table": "items"}
        ])
        plan.setdefault("components", [
            {"name": "Header", "props": [], "description": "Navigation header"},
            {"name": "Footer", "props": [], "description": "Page footer"},
            {"name": "Layout", "props": [{"name": "children", "type": "ReactNode", "required": True}],
             "description": "Page layout wrapper"},
        ])

    return plan
