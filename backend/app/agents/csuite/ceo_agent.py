from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CEOOutput


class CEOAgent(BaseCSuiteAgent):
    name = "ceo"
    schema = CEOOutput

    async def _run(self, idea_spec: dict) -> dict:
        description = idea_spec.get("description", "")
        return {
            "market_opportunity": {
                "tam": f"Total addressable market for: {description[:80]}",
                "sam": "Subset of TAM reachable with current model",
                "som": "Realistic obtainable market in year 1",
            },
            "business_model": "SaaS subscription with usage-based tiers",
            "revenue_strategy": "Freemium → Pro conversion with enterprise upsell",
            "competitive_moat": "AI-native development speed + zero-broken-build guarantee",
        }
