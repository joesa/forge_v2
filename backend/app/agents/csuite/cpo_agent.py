from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CPOOutput


class CPOAgent(BaseCSuiteAgent):
    name = "cpo"
    schema = CPOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a CPO agent. Given an app idea, prioritize features using MoSCoW "
            "(must/should/could/wont), define MVP scope, write concrete user stories with "
            "priorities, and list measurable success metrics. All output must be specific to "
            "the application described."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        return f"App idea: {desc}"
