from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CEOOutput


class CEOAgent(BaseCSuiteAgent):
    name = "ceo"
    schema = CEOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a startup CEO agent. Given an app idea, analyze the market opportunity, "
            "business model, revenue strategy, and competitive moat. Be specific to the idea — "
            "do NOT give generic advice. Quantify TAM/SAM/SOM where possible."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        framework = idea_spec.get("framework", "")
        return f"App idea: {desc}\nFramework: {framework}"
