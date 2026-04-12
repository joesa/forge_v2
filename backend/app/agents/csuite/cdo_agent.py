from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CDOOutput


class CDOAgent(BaseCSuiteAgent):
    name = "cdo"
    schema = CDOOutput

    async def _run(self, idea_spec: dict) -> dict:
        return {
            "ux_principles": [
                "Progressive disclosure",
                "Immediate feedback",
                "Consistent visual hierarchy",
                "Accessibility-first design",
            ],
            "design_system_recommendation": "Tailwind CSS with custom design tokens",
            "brand_identity": {
                "primary_color": "#6C5CE7",
                "typography": "Inter / JetBrains Mono",
                "tone": "Professional yet approachable",
            },
            "user_journey_map": [
                {"step": "landing", "action": "Discover product", "emotion": "curious"},
                {"step": "onboarding", "action": "Describe idea", "emotion": "excited"},
                {"step": "building", "action": "Watch pipeline", "emotion": "anticipation"},
                {"step": "editor", "action": "Customize code", "emotion": "empowered"},
                {"step": "deploy", "action": "Go live", "emotion": "accomplished"},
            ],
        }
