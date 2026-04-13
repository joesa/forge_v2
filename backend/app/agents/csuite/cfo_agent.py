from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CFOOutput


class CFOAgent(BaseCSuiteAgent):
    name = "cfo"
    schema = CFOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a CFO agent. Given an app idea, define a pricing strategy, estimate unit "
            "economics (cost per user, ARPU, gross margin), estimate CAC and LTV, and provide "
            "a breakeven analysis. Be specific to the type of product described."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        return f"App idea: {desc}"
