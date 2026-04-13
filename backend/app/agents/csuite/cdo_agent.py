from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CDOOutput


class CDOAgent(BaseCSuiteAgent):
    name = "cdo"
    schema = CDOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a Chief Design Officer agent. Given an app idea, define UX principles, "
            "recommend a design system, suggest brand identity (colors, typography, tone), "
            "and map out the user journey specific to this application."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        return f"App idea: {desc}"
