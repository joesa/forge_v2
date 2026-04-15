"""Idea generation — produces app ideas from questionnaire answers using LLM."""
from __future__ import annotations

import json
from typing import Any

import anthropic

from app.config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def generate_ideas(
    answers: dict[str, Any],
    *,
    count: int = 5,
) -> list[dict[str, Any]]:
    """Generate unique app ideas from questionnaire answers."""
    prompt = (
        f"Based on the following user questionnaire answers, generate {count} unique, "
        f"creative full-stack application ideas. Each idea should be distinct, feasible, "
        f"and commercially viable.\n\n"
        f"User answers:\n{json.dumps(answers, indent=2)}\n\n"
        f"Return a JSON array of {count} objects, each with:\n"
        f'- "title": short catchy app name (1-2 words)\n'
        f'- "tagline": one-sentence description of the product\n'
        f'- "uniqueness": number 1-10 rating how unique this idea is\n'
        f'- "complexity": number 1-10 rating how complex to build\n'
        f'- "problem": 1-2 sentences describing the problem it solves\n'
        f'- "solution": 1-2 sentences describing the solution approach\n'
        f'- "market": estimated total addressable market (e.g. "$4.2B")\n'
        f'- "revenue": estimated first-year revenue potential (e.g. "$120k ARR Y1")\n'
        f'- "stack": array of 3-4 key technologies (e.g. ["Next.js", "Supabase", "OpenAI"])\n'
        f'- "description": 2-3 sentence full description\n'
        f'- "tech_stack": object with "frontend", "backend", "database" keys\n'
        f'- "market_analysis": one sentence on target market\n\n'
        f"Return ONLY the JSON array, no markdown fences, no explanation."
    )

    response = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.8,
        messages=[
            {"role": "user", "content": prompt},
        ],
        system="You are an expert startup idea generator and market analyst. Return valid JSON only.",
    )

    content = response.content[0].text if response.content else "[]"
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    ideas: list[dict[str, Any]] = json.loads(content)
    return ideas[:count]
