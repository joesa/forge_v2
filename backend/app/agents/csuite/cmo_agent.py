from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CMOOutput


class CMOAgent(BaseCSuiteAgent):
    name = "cmo"
    schema = CMOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a CMO agent. Given an app idea, define a go-to-market strategy, "
            "target customer profile, prioritized growth channels, and a positioning statement. "
            "Be specific to the product described."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        return f"App idea: {desc}"
