"""Idea generation — produces app ideas from questionnaire answers using LLM."""
from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_ideas(
    answers: dict[str, Any],
    *,
    count: int = 5,
) -> list[dict[str, Any]]:
    """Generate unique app ideas from questionnaire answers."""
    prompt = (
        f"Based on the following user questionnaire answers, generate {count} unique, "
        f"creative full-stack application ideas. Each idea should be distinct and feasible.\n\n"
        f"User answers:\n{json.dumps(answers, indent=2)}\n\n"
        f"Return a JSON array of {count} objects, each with:\n"
        f'- "title": short app name\n'
        f'- "description": 2-3 sentence description\n'
        f'- "tech_stack": object with "frontend", "backend", "database" keys\n'
        f'- "market_analysis": one sentence on target market\n\n'
        f"Return ONLY the JSON array, no markdown."
    )

    response = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert app idea generator. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        seed=42,
    )

    content = response.choices[0].message.content or "[]"
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    ideas: list[dict[str, Any]] = json.loads(content)
    return ideas[:count]
